"""The one reader of a consuming repository's AFK configuration.

Skills and bash hooks must never interpret the configuration file themselves —
two readers drift, and a gate that disagrees with the skill it gates is worse
than no gate. Everything goes through this module:

    python scripts/afk-config.py init [--force]
    python scripts/afk-config.py validate [FILE]
    python scripts/afk-config.py effective --json
    python scripts/afk-config.py export-shell
    python scripts/afk-config.py get <dotted.key>
    python scripts/afk-config.py resolve <developerKey>

Standard library only. The file format is a documented SUBSET of YAML — block
maps indented by two spaces, block lists written `- item`, plain and quoted
scalars, `#` comments. Flow maps `{}`, flow lists `[]`, anchors, aliases and
multiple documents are REJECTED, not silently mis-parsed. `CONFIG.md` is the
normative description of both the subset and the schema.

Discovery, highest precedence first:

    $AFK_CONFIG                        (an explicit file)
    <git root>/.afk/config.local.yaml  (gitignored per-developer overlay)
    <git root>/.afk/config.yaml        (committed, the repository's contract)
    ~/.afk/config.yaml                 (per-machine defaults)
    built-in defaults

Layers are deep-merged: a mapping merges key by key, any other value replaces.
The local overlay may not change `schema`.

Secrets never live in a configuration file. A file names ENVIRONMENT VARIABLES;
the values come from the environment or a harness credential store.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

SCHEMA = 1

TRACKERS = ("jira", "github-issues", "none")
FORGES = ("gitlab", "github", "none")
NOTES = ("repo-files", "notion", "obsidian")
BUILD_GATES = ("maven", "npm")

TOP_LEVEL = {
    "schema", "toolkit-version", "tracker", "forge", "notes", "build-gates",
    "jira", "github-issues", "gitlab", "github", "git", "repo-files",
    "obsidian", "notion", "artifacts", "maven", "npm", "verification",
    "repo-hooks", "setup", "developer",
    "tracker-defaults", "forge-defaults",
}

# Per-developer values: whose machine this is, not what the repository is.
# Every one is OPTIONAL. Their home is `~/.afk/config.yaml`, which covers every
# checkout on the machine; the gitignored `.afk/config.local.yaml` overlay is for
# a value that differs in ONE checkout. Never the committed file.
#
# Two of them have a committed team-wide fallback, because "who reviews" and
# "who is assigned" are facts about a team and not about a laptop:
#   developer.trackerAssignee -> tracker-defaults.assignee
#   developer.mrReviewer      -> forge-defaults.reviewer
# Resolution is developer value, then team default, then fail closed naming both
# (`skills/afk/bug/CONFIG.md` owns the fail-closed matrix). `worktreeBasePath` has
# no default because it is DERIVED (`worktree_base`), and `ideBinary` has none
# because no default could be right.
DEVELOPER_KEYS = {"trackerAssignee", "mrReviewer", "worktreeBasePath", "ideBinary"}

# developer key -> the committed key that stands in when it is unset.
DEVELOPER_FALLBACKS = {
    "trackerAssignee": "tracker-defaults.assignee",
    "mrReviewer": "forge-defaults.reviewer",
}

DEFAULTS: dict = {
    "schema": SCHEMA,
    "tracker": "none",
    "forge": "none",
    "notes": "repo-files",
    "git": {"base-branch": "auto", "branch-pattern": ""},
    "repo-files": {"spec-dir": "docs/afk/{workId}"},
}


class ConfigError(Exception):
    """A configuration file this toolkit refuses to guess about."""


# --------------------------------------------------------------------------
# YAML subset parser
# --------------------------------------------------------------------------

_KEY = re.compile(r"^(?P<key>[A-Za-z0-9_.-]+)\s*:(?:\s+(?P<value>.*))?$")
_ITEM = re.compile(r"^-(?:\s+(?P<value>.*))?$")


def _strip_comment(line: str) -> str:
    """Drop a trailing `#` comment that is not inside a quoted scalar."""
    out = []
    quote = ""
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            out.append(char)
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
            out.append(char)
        elif char == "#" and (not out or out[-1] in " \t"):
            break
        else:
            out.append(char)
        index += 1
    return "".join(out).rstrip()


def _scalar(raw: str, where: str):
    text = raw.strip()
    if not text:
        return ""
    if text[0] in "{[":
        raise ConfigError(
            f"{where}: flow syntax is not part of the supported subset: {text!r}. "
            "Write a block map or a block list; express an empty list by omitting the key."
        )
    if text[0] in "&*":
        raise ConfigError(f"{where}: anchors and aliases are not supported: {text!r}")
    if text[0] in "|>":
        raise ConfigError(f"{where}: block scalars are not supported: {text!r}")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        body = text[1:-1]
        if text[0] == '"':
            body = body.replace('\\"', '"').replace("\\\\", "\\")
        else:
            body = body.replace("''", "'")
        return body
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~"):
        return None
    if re.fullmatch(r"[+-]?\d+", text):
        return int(text)
    if re.fullmatch(r"[+-]?\d*\.\d+", text):
        return float(text)
    return text


def parse(text: str, where: str = "<config>"):
    """Parse the documented YAML subset. Raises ConfigError on anything else."""
    lines = []
    for number, raw in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        if raw.strip().startswith("---") or raw.strip() == "...":
            raise ConfigError(f"{where}:{number}: multi-document files are not supported")
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        if "\t" in stripped[: len(stripped) - len(stripped.lstrip())]:
            raise ConfigError(f"{where}:{number}: indent with spaces, never tabs")
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((number, indent, stripped.strip()))

    position = 0

    def block(indent: int):
        nonlocal position
        if position >= len(lines):
            return {}
        if _ITEM.match(lines[position][2]):
            return sequence(indent)
        return mapping(indent)

    def mapping(indent: int) -> dict:
        nonlocal position
        result: dict = {}
        while position < len(lines):
            number, own_indent, content = lines[position]
            if own_indent < indent:
                break
            if own_indent > indent:
                raise ConfigError(f"{where}:{number}: unexpected indent")
            match = _KEY.match(content)
            if not match:
                raise ConfigError(f"{where}:{number}: expected `key: value`, got {content!r}")
            key = match.group("key")
            value = match.group("value")
            if key in result:
                raise ConfigError(f"{where}:{number}: duplicate key {key!r}")
            position += 1
            if value is None or value == "":
                if position < len(lines) and lines[position][1] > indent:
                    result[key] = block(lines[position][1])
                elif position < len(lines) and _ITEM.match(lines[position][2]) \
                        and lines[position][1] == indent:
                    result[key] = sequence(indent)
                else:
                    result[key] = None
            else:
                result[key] = _scalar(value, f"{where}:{number}")
        return result

    def sequence(indent: int) -> list:
        nonlocal position
        result: list = []
        while position < len(lines):
            number, own_indent, content = lines[position]
            if own_indent < indent:
                break
            if own_indent > indent:
                raise ConfigError(f"{where}:{number}: unexpected indent in a list")
            match = _ITEM.match(content)
            if not match:
                break
            value = match.group("value")
            position += 1
            if value is None or value == "":
                if position < len(lines) and lines[position][1] > indent:
                    result.append(block(lines[position][1]))
                else:
                    result.append(None)
            elif _KEY.match(value):
                # `- key: value` opens a map whose first key sits on the dash line.
                inner_indent = own_indent + 2
                lines.insert(position, (number, inner_indent, value))
                result.append(mapping(inner_indent))
            else:
                result.append(_scalar(value, f"{where}:{number}"))
        return result

    document = block(lines[0][1]) if lines else {}
    if position != len(lines):
        number = lines[position][0]
        raise ConfigError(f"{where}:{number}: could not parse the rest of the file")
    if document is None:
        document = {}
    if not isinstance(document, dict):
        raise ConfigError(f"{where}: the top level must be a mapping")
    return document


# --------------------------------------------------------------------------
# Discovery and merge
# --------------------------------------------------------------------------

def git_root(start: Path | None = None) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(start or Path.cwd()), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    top = out.stdout.strip()
    return Path(top) if out.returncode == 0 and top else None


def deep_merge(base: dict, overlay: dict) -> dict:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def layers(root: Path | None) -> list[tuple[str, Path]]:
    """Configuration files, LOWEST precedence first."""
    found: list[tuple[str, Path]] = []
    home = Path.home() / ".afk" / "config.yaml"
    if home.is_file():
        found.append(("home", home))
    if root is not None:
        repo = root / ".afk" / "config.yaml"
        if repo.is_file():
            found.append(("repo", repo))
        local = root / ".afk" / "config.local.yaml"
        if local.is_file():
            found.append(("local", local))
    named = os.environ.get("AFK_CONFIG")
    if named:
        path = Path(named)
        if not path.is_file():
            raise ConfigError(f"AFK_CONFIG names a file that does not exist: {named}")
        found.append(("env", path))
    return found


def load(root: Path | None = None) -> dict:
    if root is None:
        root = git_root()
    effective = dict(DEFAULTS)
    for kind, path in layers(root):
        document = parse(path.read_text(encoding="utf-8"), str(path))
        if kind == "local" and "schema" in document:
            raise ConfigError(f"{path}: the local overlay may not set `schema`")
        effective = deep_merge(effective, document)
    return effective


# --------------------------------------------------------------------------
# Schema validation
# --------------------------------------------------------------------------

def _choice(problems: list[str], config: dict, key: str, allowed: tuple[str, ...]) -> None:
    value = config.get(key)
    if value is None:
        return
    if value not in allowed:
        problems.append(f"{key}: {value!r} is not one of {', '.join(allowed)}")


def validate(config: dict, root: Path | None = None) -> list[str]:
    problems: list[str] = []

    if config.get("schema") != SCHEMA:
        problems.append(f"schema: expected {SCHEMA}, got {config.get('schema')!r}")

    for key in sorted(set(config) - TOP_LEVEL):
        problems.append(f"{key}: unknown top-level key")

    _choice(problems, config, "tracker", TRACKERS)
    _choice(problems, config, "forge", FORGES)
    _choice(problems, config, "notes", NOTES)

    gates = config.get("build-gates")
    if gates is not None:
        if not isinstance(gates, list):
            problems.append(
                "build-gates: must be a block list; express `no build gates` by omitting the key"
            )
        else:
            for gate in gates:
                if gate not in BUILD_GATES:
                    problems.append(
                        f"build-gates: {gate!r} is not one of {', '.join(BUILD_GATES)}"
                    )

    tiers = (config.get("verification") or {}).get("tiers") if isinstance(
        config.get("verification"), dict) else None
    if tiers is not None:
        if not isinstance(tiers, dict):
            problems.append("verification.tiers: must be a mapping of tier name to command")
        else:
            for name, tier in tiers.items():
                if not isinstance(tier, dict) or "command" not in tier:
                    problems.append(f"verification.tiers.{name}: needs a `command`")
                    continue
                args = tier.get("args")
                if args is not None and not isinstance(args, list):
                    problems.append(f"verification.tiers.{name}.args: must be a block list")

    hooks = config.get("repo-hooks")
    if hooks is not None:
        if not isinstance(hooks, str):
            problems.append("repo-hooks: must be a repository-relative path")
        elif root is not None:
            target = (root / hooks).resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError:
                problems.append(f"repo-hooks: {hooks} resolves outside the repository root")

    for family, key in (("tracker", "jira"), ("tracker", "github-issues")):
        block_value = config.get(key)
        if block_value is not None and not isinstance(block_value, dict):
            problems.append(f"{key}: must be a mapping")

    creds = (config.get("jira") or {}).get("credentials-env") if isinstance(
        config.get("jira"), dict) else None
    if creds is not None and not isinstance(creds, list):
        problems.append("jira.credentials-env: must be a block list of variable NAMES")

    for block, key in (("tracker-defaults", "assignee"), ("forge-defaults", "reviewer")):
        value = config.get(block)
        if value is None:
            continue
        if not isinstance(value, dict):
            problems.append(f"{block}: must be a mapping")
            continue
        for extra in sorted(set(value) - {key}):
            problems.append(f"{block}.{extra}: unknown key; expected `{key}`")
        if key in value and not isinstance(value[key], str):
            problems.append(f"{block}.{key}: must be a string")

    developer = config.get("developer")
    if developer is not None:
        if not isinstance(developer, dict):
            problems.append("developer: must be a mapping")
        else:
            for key in sorted(set(developer) - DEVELOPER_KEYS):
                problems.append(
                    f"developer.{key}: unknown key; expected one of "
                    f"{', '.join(sorted(DEVELOPER_KEYS))}"
                )
            for key, value in developer.items():
                if key in DEVELOPER_KEYS and not isinstance(value, str):
                    problems.append(f"developer.{key}: must be a string")

    return problems


# --------------------------------------------------------------------------
# Resolving a developer value
# --------------------------------------------------------------------------

def worktree_base(root: Path | None = None) -> Path | None:
    """Where worktrees go when nobody said: beside the main checkout.

    `--git-common-dir` answers with the MAIN checkout's `.git` even from inside
    a worktree, which is the whole point: every worktree of one repository then
    derives the same directory. A repository whose git dir is elsewhere entirely
    (a bare clone, a `GIT_DIR` pointing outside the tree) gets `None`, and the
    caller asks for the key instead of guessing.
    """
    start = root or git_root() or Path.cwd()
    common = _git(start, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        return None
    main_checkout = Path(common).parent
    if main_checkout.name in ("", "/") or not main_checkout.name:
        return None
    return main_checkout.parent / (main_checkout.name + "-worktrees")


def developer_value(config: dict, key: str, root: Path | None = None) -> str | None:
    """A `developer.<key>`, its committed team default, or None.

    One function so that every consumer resolves in the same order. `None` means
    fail closed and name both places the value could come from — never invent one.
    """
    value = get(config, f"developer.{key}")
    if isinstance(value, str) and value.strip():
        return value
    fallback = DEVELOPER_FALLBACKS.get(key)
    if fallback:
        value = get(config, fallback)
        if isinstance(value, str) and value.strip():
            return value
    if key == "worktreeBasePath":
        derived = worktree_base(root)
        if derived is not None:
            return str(derived).replace("\\", "/")
    return None


# --------------------------------------------------------------------------
# Scaffolding a starter file
# --------------------------------------------------------------------------

def _git(root: Path, *args: str) -> str:
    """A git command's stdout, or an empty string when it cannot answer."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def detect_forge(root: Path) -> tuple[str, str, str]:
    """`(forge, remote name, host)` read from the origin remote.

    Detection is by HOST, not by URL shape: a self-hosted GitLab is still
    GitLab, and a repository with no remote gets `none` rather than a guess.
    """
    remote = "origin"
    url = _git(root, "remote", "get-url", remote)
    if not url:
        names = _git(root, "remote").splitlines()
        if not names:
            return "none", "", ""
        remote = names[0].strip()
        url = _git(root, "remote", "get-url", remote)
    if not url:
        return "none", "", ""

    rest = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", url)      # scheme
    rest = re.sub(r"^[^@/]+@", "", rest)                        # ssh user
    host = re.split(r"[/:]", rest, maxsplit=1)[0].lower()

    if "gitlab" in host:
        return "gitlab", remote, host
    if "github" in host:
        return "github", remote, host
    return "none", remote, host


def detect_build_gates(root: Path) -> tuple[list[str], dict]:
    """The build gates this repository can run, and their configuration blocks."""
    gates: list[str] = []
    blocks: dict = {}

    root_pom = root / "pom.xml"
    if root_pom.is_file() or (root / "mvnw").is_file() or (root / "mvnw.cmd").is_file():
        gates.append("maven")
        # An aggregator that is not `pom.xml` is common enough that guessing is
        # worse than naming what was found.
        poms = sorted(p.name for p in root.glob("*pom.xml"))
        reactor = "pom.xml" if root_pom.is_file() else (poms[0] if poms else "pom.xml")
        blocks["maven"] = {"reactor-pom": reactor}

    if (root / "package.json").is_file():
        gates.append("npm")
        blocks["npm"] = {"workspace-root": "."}
    return gates, blocks


def detect_base_branch(root: Path) -> str:
    """The default branch name, or `auto` when git will not say."""
    head = _git(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if head:
        return head.rsplit("/", 1)[-1]
    for candidate in ("main", "master"):
        if _git(root, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{candidate}"):
            return candidate
    return "auto"


def scaffold(root: Path) -> str:
    """A starter configuration for this repository, as text.

    Every value it cannot read from the repository is written as a commented
    TODO rather than a plausible guess: a wrong value that validates is harder
    to notice than a missing one.
    """
    forge, remote, host = detect_forge(root)
    gates, blocks = detect_build_gates(root)
    base = detect_base_branch(root)
    tracker = "github-issues" if forge == "github" and host.endswith("github.com") else "none"

    lines = [
        "# AFK configuration for this repository. Committed: it is the contract",
        "# every AFK skill reads. `CONFIG.md` in the plugin is the normative",
        "# description of the schema and of the YAML subset allowed here.",
        "#",
        "# Scaffolded by `afk-config.py init`. Every `TODO` below is a value the",
        "# repository could not answer for itself.",
        f"schema: {SCHEMA}",
        "",
        f"tracker: {tracker}",
        f"forge: {forge}",
        "notes: repo-files",
    ]

    if gates:
        lines.append("build-gates:")
        lines += [f"  - {gate}" for gate in gates]
    else:
        lines += [
            "# build-gates:            # no pom.xml / package.json at the root",
            "#   - maven",
        ]

    lines.append("")
    if tracker == "none":
        lines += [
            "# Jira: set `tracker: jira` above and fill this block in.",
            "# jira:",
            "#   project: TODO             # the project key, e.g. ABC",
            "#   issue-types:",
            "#     task: Task",
            "#     bug: Bug",
            "#   transitions:",
            "#     ready-for-review: Ready for Review",
            "#   credentials-env:          # variable NAMES; never a secret",
            "#     - JIRA_BASE_URL",
            "#     - JIRA_EMAIL",
            "#     - JIRA_API_TOKEN",
        ]
    else:
        lines += [
            "github-issues:",
            "  labels:",
            "    bug: bug",
        ]
    lines.append("")

    if forge in ("gitlab", "github"):
        lines += [f"{forge}:", f"  remote: {remote or 'origin'}", ""]

    lines += ["git:", f"  base-branch: {base}"]
    lines += [
        "  # branch-pattern is a regex every work branch must match. Empty means",
        "  # anything is allowed; fill it in to make the branch-name gate bite.",
        "  branch-pattern: """,
        "",
        "repo-files:",
        "  spec-dir: docs/afk/{workId}",
        "",
    ]

    for gate in gates:
        block = blocks[gate]
        lines.append(f"{gate}:")
        for key, value in block.items():
            lines.append(f"  {key}: {value}")
        if gate == "maven":
            lines.append("  # default-module: TODO      # the module the gates build when a")
            lines.append("  # change names none; omit to build the whole reactor.")
        lines.append("")

    lines += [
        "# Team defaults. These are facts about the team, not about one machine,",
        "# so they are committed. A developer overrides either one in their own",
        "# `~/.afk/config.yaml` under `developer:`.",
        "# tracker-defaults:",
        "#   assignee: TODO            # account id or email of the default assignee",
        "# forge-defaults:",
        "#   reviewer: TODO            # forge username of the default reviewer",
    ]

    return "\n".join(lines).rstrip("\n") + "\n"


def init(root: Path, force: bool = False) -> tuple[Path, list[str]]:
    """Write the starter file. Returns its path and any validation problems."""
    target = root / ".afk" / "config.yaml"
    if target.is_file() and not force:
        raise ConfigError(
            f"{target} already exists; nothing was written. "
            f"Pass --force to replace it (the current file is not backed up)."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    text = scaffold(root)
    target.write_text(text, encoding="utf-8", newline="\n")
    config = deep_merge(dict(DEFAULTS), parse(text, str(target)))
    return target, validate(config, root)


# --------------------------------------------------------------------------
# Flattening for the shell
# --------------------------------------------------------------------------

def shell_name(path: str) -> str:
    return "AFK_CFG_" + re.sub(r"[^A-Za-z0-9]", "_", path).upper()


def flatten(node, prefix: str = "") -> list[tuple[str, object]]:
    """(dotted-path, scalar) pairs. Lists gain an explicit index and count."""
    out: list[tuple[str, object]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            out += flatten(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(node, list):
        out.append((f"{prefix}.count", len(node)))
        for index, value in enumerate(node):
            out += flatten(value, f"{prefix}.{index}")
    else:
        out.append((prefix, node))
    return out


def shell_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def export_shell(config: dict) -> str:
    lines = []
    for path, value in flatten(config):
        lines.append(f"{shell_name(path)}={shlex.quote(shell_value(value))}")
    lines.append("AFK_CFG_LOADED=1")
    return "\n".join(lines) + "\n"


def get(config: dict, dotted: str):
    node = config
    for part in dotted.split("."):
        if isinstance(node, list):
            try:
                node = node[int(part)]
                continue
            except (ValueError, IndexError):
                return None
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write(__doc__ or "")
        return 2
    command, rest = argv[0], argv[1:]
    root = git_root()

    try:
        if command == "init":
            if root is None:
                sys.stderr.write("afk-config: init must run inside a git repository\n")
                return 2
            target, problems = init(root, force="--force" in rest)
            for problem in problems:
                sys.stderr.write(f"afk-config: {problem}\n")
            if problems:
                # A scaffold that does not validate is this tool's bug, not the
                # user's: say so rather than leaving them to debug the file.
                sys.stderr.write(
                    "afk-config: the scaffold it just wrote does not validate; "
                    "please report this with the file above\n"
                )
                return 2
            sys.stdout.write(f"afk-config: wrote {target}\n")
            return 0

        if command == "validate":
            if rest:
                path = Path(rest[0])
                config = deep_merge(
                    dict(DEFAULTS), parse(path.read_text(encoding="utf-8"), str(path))
                )
                root = root if root is not None else path.parent.parent
            else:
                config = load(root)
            problems = validate(config, root)
            for problem in problems:
                sys.stderr.write(f"afk-config: {problem}\n")
            if problems:
                return 2
            sys.stdout.write("afk-config: configuration is valid\n")
            return 0

        config = load(root)
        if command == "effective":
            sys.stdout.write(json.dumps(config, indent=2, sort_keys=True) + "\n")
            return 0
        if command == "export-shell":
            sys.stdout.write(export_shell(config))
            return 0
        if command == "resolve":
            if not rest:
                sys.stderr.write(
                    "afk-config: resolve needs a developer key, e.g. "
                    "`resolve trackerAssignee`\n"
                )
                return 2
            key = rest[0].split(".")[-1]
            if key not in DEVELOPER_KEYS:
                sys.stderr.write(
                    f"afk-config: {key!r} is not a developer key; expected one of "
                    f"{', '.join(sorted(DEVELOPER_KEYS))}\n"
                )
                return 2
            resolved = developer_value(config, key, root)
            if resolved is None:
                return 1
            sys.stdout.write(shell_value(resolved) + "\n")
            return 0

        if command == "get":
            if not rest:
                sys.stderr.write("afk-config: get needs a dotted key\n")
                return 2
            value = get(config, rest[0])
            if value is None:
                return 1
            if isinstance(value, (dict, list)):
                sys.stdout.write(json.dumps(value, sort_keys=True) + "\n")
            else:
                sys.stdout.write(shell_value(value) + "\n")
            return 0
    except ConfigError as problem:
        sys.stderr.write(f"afk-config: {problem}\n")
        return 2

    sys.stderr.write(f"afk-config: unknown command {command!r}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
