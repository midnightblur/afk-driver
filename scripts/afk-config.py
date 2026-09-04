"""The one reader of a consuming repository's AFK configuration.

Skills and bash hooks must never interpret the configuration file themselves —
two readers drift, and a gate that disagrees with the skill it gates is worse
than no gate. Everything goes through this module:

    python scripts/afk-config.py validate [FILE]
    python scripts/afk-config.py effective --json
    python scripts/afk-config.py export-shell
    python scripts/afk-config.py get <dotted.key>

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
}

# Per-developer values: whose machine this is, not what the repository is.
# They belong in the gitignored `.afk/config.local.yaml` overlay, never in the
# committed file — `trackerAssignee` and `mrReviewer` name a person, and the
# paths are one machine's. Absence is a supported state: a key's consumer fails
# closed and names the key (`skills/afk/bug/CONFIG.md`).
DEVELOPER_KEYS = {"trackerAssignee", "mrReviewer", "worktreeBasePath", "ideBinary"}

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
