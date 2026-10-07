#!/usr/bin/env bash
# Native plugin contract gate. Keeps the committed AFK tree consumable by every
# supported harness without generated mirrors or harness vocabulary leaking into
# skill/doctrine prose.
#
# Checks, in one batched Python scan:
#   A. skill/doctrine prose uses no provider env/tool/runtime vocabulary unless
#      a line-specific native-contract-allow.txt entry explains the exception;
#   B. SKILL.md top-level frontmatter uses only Agent Skills or documented Claude
#      skill keys;
#   C. skills on disk equal BOTH native manifests;
#   D. every agents/*.md has a providers/codex/agents/afk-*.toml stub;
#   E. hooks.json events/matchers stay inside CAPABILITIES.md's literal shared
#      subset declarations;
#   F. no generated activation/mirror tree is tracked;
#   G. every hooks/lib/providers/*.sh adapter has envelope fixtures under
#      hooks/tests/envelopes/<provider>/;
#   H. the PROVIDERS.md supported-harness registry and the adapters on disk are
#      one list;
#   I. every shell handler and hook launcher is LF-only, since a harness copies
#      this tree verbatim into its plugin cache and runs it through a POSIX shell;
#   J. both manifests run `afk-python` (run-hook.py or a protected-branch hook), equal modulo the root
#      variable; no live surface, this file included, names `python`, `python3`, `py -3` or the old override;
#   K. every hooks/lib/providers/<name>_*.py helper has a matching <name>.sh
#      that references it, and no other plugin file references it (unit
#      tests under scripts/tests/ exempted — they load the helper directly);
#   L. agent files carry the model and effort of their PROVIDERS.md tier;
#   M. every hook entry in both manifests runs through the launcher with an
#      explicit timeout and a launcher deadline below it, and no Stop-path gate
#      source scans repository content except through hooks/lib/bounded_scan.py.
#      An exception names its own bound in native-contract-allow.txt (rules
#      hook-deadline, repo-scan).
#
# Disable: NATIVE_CONTRACT_GATE_DISABLE=1, or repo file
# .claude/hooks/.gate-disabled. Assumes cwd = gated repo root when sourced.

set -u

gate_native_contract() {
  [ "${NATIVE_CONTRACT_GATE_DISABLE:-0}" = "1" ] && return 0
  [ -f .claude/hooks/.gate-disabled ] && return 0

  local PLUGIN_DIR PLUGIN_SCOPE; PLUGIN_DIR=$(afk_plugin_dir); PLUGIN_SCOPE=$(afk_plugin_scope)
  local MANIFEST="$PLUGIN_DIR/.claude-plugin/plugin.json"
  [ -f "$MANIFEST" ] || return 0

  local cache_key
  cache_key=$(gate_cache_key native-contract \
    "$PLUGIN_SCOPE*" ".agents/*" ".codex/*")
  gate_cache_hit native-contract "$cache_key" && return 0

  gate_metrics_begin

  local py="${AFK_PYTHON:-afk-python}" findings rc=0
  findings=$("$py" - "$PLUGIN_DIR" <<'PY'
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path


plugin_rel = Path(sys.argv[1])
repo = Path.cwd()
plugin = repo / plugin_rel
problems: list[str] = []


def rel(path: Path) -> str:
    return path.relative_to(plugin).as_posix()


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        problems.append(f"{rel(path)}: cannot read as UTF-8 ({exc})")
        return ""


# A. Provider vocabulary in skill/agent prose and plugin-root doctrine.
# Provider mapping, capability matrix, and conformance evidence are the named
# homes for provider-specific vocabulary. Historical CHANGELOG lines stay in
# scope and carry narrow allowlist entries so new coupling cannot hide there.
excluded_prose = {"PROVIDERS.md", "CAPABILITIES.md", "providers/CONFORMANCE.md", "providers/HARNESS-MATRIX.md"}
scan_files = [
    path for path in sorted(plugin.rglob("*.md"))
    if rel(path) not in excluded_prose
]

allow_file = plugin / "hooks/native-contract-allow.txt"
allow: list[tuple[str, str, re.Pattern[str]]] = []
if allow_file.is_file():
    for number, raw in enumerate(read(allow_file).splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        fields = raw.split("\t", 3)
        if len(fields) != 4 or not all(fields):
            problems.append(
                f"hooks/native-contract-allow.txt:{number}: expected path<TAB>rule<TAB>regex<TAB>reason"
            )
            continue
        path_glob, rule, pattern, _reason = fields
        try:
            allow.append((path_glob, rule, re.compile(pattern)))
        except re.error as exc:
            problems.append(
                f"hooks/native-contract-allow.txt:{number}: invalid regex ({exc})"
            )


def allowed(path: str, rule: str, line: str) -> bool:
    return any(
        fnmatch.fnmatchcase(path, path_glob)
        and (allow_rule == rule or allow_rule == "*")
        and pattern.search(line)
        for path_glob, allow_rule, pattern in allow
    )


rules = {
    "harness-env": re.compile(r"\bCLAUDECODE\b"),
    "claude-plugin-root": re.compile(r"(?<![A-Z0-9_])PLUGIN_ROOT(?![A-Z0-9_])"),
    "harness-tool": re.compile(r"\b(?:SendMessage|subagent_type)\b"),
    "mcp-prefix": re.compile(r"\bmcp__[A-Za-z0-9_-]+__"),
    "harness-name": re.compile(r"\b(?:Claude Code|(?:OpenAI )?Codex(?: CLI)?)\b"),
}
project_dir = re.compile(r"\bCLAUDE_PROJECT_DIR\b")
project_dir_fallback = re.compile(r"\$\{CLAUDE_PROJECT_DIR:-[^}\n]+\}")

for path in scan_files:
    path_rel = rel(path)
    for number, line in enumerate(read(path).splitlines(), 1):
        if project_dir.search(line) and not project_dir_fallback.search(line):
            if not allowed(path_rel, "claude-project-dir", line):
                problems.append(
                    f"{path_rel}:{number}: CLAUDE_PROJECT_DIR requires an inline fallback"
                )
        for rule, pattern in rules.items():
            if pattern.search(line) and not allowed(path_rel, rule, line):
                problems.append(f"{path_rel}:{number}: forbidden {rule} vocabulary")


# B. Top-level SKILL.md frontmatter. Indented metadata children are not keys in
# this set; only column-zero keys between the opening/closing delimiters count.
allowed_frontmatter = {
    # Agent Skills specification
    "name", "description", "license", "compatibility", "metadata", "allowed-tools",
    # Documented Claude skill extensions
    "argument-hint", "disable-model-invocation", "user-invocable", "model",
    "context", "agent", "hooks",
}
skill_files = sorted(plugin.glob("skills/**/SKILL.md"))
for path in skill_files:
    lines = read(path).splitlines()
    if not lines or lines[0].strip() != "---":
        problems.append(f"{rel(path)}: missing YAML frontmatter")
        continue
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        problems.append(f"{rel(path)}: unterminated YAML frontmatter")
        continue
    for number, line in enumerate(lines[1:end], 2):
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):", line)
        if match and match.group(1) not in allowed_frontmatter:
            problems.append(
                f"{rel(path)}:{number}: unsupported SKILL.md frontmatter key {match.group(1)!r}"
            )


# C. Disk skill membership must equal both manifests independently.
disk_skills = {
    "./" + path.parent.relative_to(plugin).as_posix()
    for path in skill_files
}


def manifest_skills(path: Path) -> set[str] | None:
    if not path.is_file():
        problems.append(f"{rel(path)}: missing native manifest")
        return None
    try:
        payload = json.loads(read(path))
    except json.JSONDecodeError as exc:
        problems.append(f"{rel(path)}: invalid JSON ({exc})")
        return None
    values = payload.get("skills")
    if not isinstance(values, list) or any(not isinstance(x, str) for x in values):
        problems.append(f"{rel(path)}: skills must be an array of paths")
        return None
    return {x.rstrip("/") for x in values}


for manifest_rel in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
    manifest_path = plugin / manifest_rel
    declared = manifest_skills(manifest_path)
    if declared is None:
        continue
    for missing in sorted(disk_skills - declared):
        problems.append(f"{manifest_rel}: skill on disk is missing: {missing}")
    for stale in sorted(declared - disk_skills):
        problems.append(f"{manifest_rel}: declared skill is absent from disk: {stale}")


# D. Each native agent definition needs a Codex TOML pointer/stub twin.
for agent in sorted(plugin.glob("agents/*.md")):
    stub = plugin / "providers/codex/agents" / f"afk-{agent.stem}.toml"
    if not stub.is_file():
        problems.append(f"{rel(agent)}: missing {rel(stub)}")


# L. PROVIDERS.md "Model tiers" is the one home of each tier's model; agent
# files are literal copies the harness parses, so they must equal their cell.
providers_text = read(plugin / "PROVIDERS.md") if (plugin / "PROVIDERS.md").is_file() else ""
tiers_sec = re.search(r"(?ms)^##\s+Model tiers\s*$(.*?)(?=^##\s|\Z)", providers_text)
if not tiers_sec:
    problems.append("PROVIDERS.md: missing the `## Model tiers` section")
else:
    tier_cells = {}
    agent_tier = {}
    for line in tiers_sec.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        ticks = [re.fullmatch(r"`([^`]+)`", c) for c in cells]
        if len(cells) == 4 and all(ticks[1:]):
            tier_cells[cells[0]] = tuple(m.group(1) for m in ticks[1:])
        elif len(cells) == 2 and ticks[0] and cells[1] and not set(cells[1]) <= set("-: "):
            agent_tier[ticks[0].group(1)] = cells[1]
    home = "PROVIDERS.md `## Model tiers`"
    on_disk = {a.stem for a in plugin.glob("agents/*.md")}
    for name in sorted(on_disk - set(agent_tier)):
        problems.append(f"agents/{name}.md: no row in the {home} Agent table")
    for name in sorted(set(agent_tier) - on_disk):
        problems.append(f"{home}: Agent row {name!r} has no agents/{name}.md")
    for tier in sorted(set(agent_tier.values()) - set(tier_cells)):
        problems.append(f"{home}: Agent table names tier {tier!r} with no tier row")
    for name in sorted(on_disk & set(agent_tier)):
        cells = tier_cells.get(agent_tier[name])
        if not cells:
            continue
        claude, codex, effort = cells
        md = plugin / "agents" / f"{name}.md"
        fm = re.match(r"(?s)---\r?\n(.*?)\r?\n---", read(md))
        got = re.search(r"(?m)^model:\s*(\S+)\s*$", fm.group(1)) if fm else None
        actual = re.sub(r"^(['\"])(.*)\1$", r"\2", got.group(1)) if got else None
        if actual != claude:
            problems.append(
                f"{rel(md)}: model expected {claude!r} (tier {agent_tier[name]}), "
                f"got {actual!r}; the home is {home}"
            )
        toml = plugin / "providers/codex/agents" / f"afk-{name}.toml"
        if toml.is_file():
            body = read(toml)
            for key, want, label in (("model", codex, "model"),
                                     ("model_reasoning_effort", effort, "effort")):
                m = re.search(rf'(?m)^{key}\s*=\s*"([^"]*)"', body)
                if not m or m.group(1) != want:
                    problems.append(
                        f"{rel(toml)}: {label} expected {want!r} (tier {agent_tier[name]}), "
                        f"got {m.group(1) if m else 'none'!r}; the home is {home}"
                    )


# E. CAPABILITIES.md owns the shared hooks.json event and matcher subset. The
# exact machine-readable declarations intentionally keep this parser trivial.
capabilities = plugin / "CAPABILITIES.md"
cap_text = read(capabilities) if capabilities.is_file() else ""


def declaration(label: str) -> set[str] | None:
    match = re.search(rf"(?mi)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", cap_text)
    if not match:
        problems.append(f"CAPABILITIES.md: missing `{label}: ...` declaration")
        return None
    return {
        token.strip().strip("`")
        for token in match.group(1).split(",")
        if token.strip().strip("`")
    }


shared_events = declaration("Shared hook events")
shared_matchers = declaration("Shared hook matchers")


def load_hook_map(rel_name: str) -> dict:
    path = plugin / rel_name
    try:
        payload = json.loads(read(path))
    except json.JSONDecodeError as exc:
        problems.append(f"{rel_name}: invalid JSON ({exc})")
        return {}
    hmap = payload.get("hooks", {})
    if not isinstance(hmap, dict):
        problems.append(f"{rel_name}: hooks must be an object")
        return {}
    return hmap


# `Provider-specific hook events: <provider>=<event>, ...` names events one harness
# has and the other lacks; each may appear in that provider's manifest only.
specific_events: dict[str, set[str]] = {}
_specific = re.search(r"(?mi)^\s*Provider-specific hook events\s*:\s*(.+?)\s*$", cap_text)
for _pair in (_specific.group(1).split(",") if _specific else []):
    _provider, _, _event = _pair.strip().strip("`").partition("=")
    if _event:
        specific_events.setdefault(_provider.strip(), set()).add(_event.strip().strip("`"))
MANIFEST_PROVIDER = {"hooks/hooks.json": "claude", "hooks/hooks.codex.json": "codex"}


def check_subset(rel_name: str, hmap: dict) -> None:
    # Each twin: the shared subset plus its own provider's declared events.
    own = specific_events.get(MANIFEST_PROVIDER.get(rel_name, ""), set())
    if shared_events is not None:
        for event in sorted(set(hmap) - shared_events - own):
            problems.append(f"{rel_name}: event {event!r} is outside the shared subset")
    if shared_matchers is None:
        return
    for event, groups in hmap.items():
        if not isinstance(groups, list):
            problems.append(f"{rel_name}: event {event!r} handlers must be an array")
            continue
        for index, group in enumerate(groups):
            if not isinstance(group, dict):
                problems.append(f"{rel_name}: {event}[{index}] must be an object")
                continue
            matcher = group.get("matcher", "*")
            if not isinstance(matcher, str):
                problems.append(f"{rel_name}: {event}[{index}] matcher must be a string")
                continue
            for token in filter(None, (part.strip() for part in matcher.split("|"))):
                if token not in shared_matchers:
                    problems.append(
                        f"{rel_name}: matcher {token!r} is outside the shared subset"
                    )


hook_map = load_hook_map("hooks/hooks.json")
check_subset("hooks/hooks.json", hook_map)
check_subset("hooks/hooks.codex.json", load_hook_map("hooks/hooks.codex.json"))


# J. One runtime, one launch mechanism: any shell may parse a command string, and `bash` can be
# the WSL stub, so every handler goes through the launcher under `afk-python`.
def launcher_form(root_var: str) -> re.Pattern[str]:
    return re.compile(
        r'^afk-python "\$\{' + root_var + r'\}/hooks/(?:'
        r'run-hook\.py"(?: --soft)?'
        r'(?: --deadline [0-9]+)?'
        r'(?: plugin [A-Za-z0-9._-]+\.sh(?: [A-Za-z0-9._=-]+)*'
        r'| repo-list (?:SessionStart|PreToolUse|PostToolUse|PostCompact|Stop))'
        r'|protected-branch-(?:guard|meter|occupancy)\.py")$'
    )


twins: dict[str, str] = {}
for manifest_rel, root_var in (("hooks/hooks.json", "CLAUDE_PLUGIN_ROOT"),
                               ("hooks/hooks.codex.json", "PLUGIN_ROOT")):
    form = launcher_form(root_var)
    hmap = load_hook_map(manifest_rel)
    for event, groups in hmap.items():
        for index, group in enumerate(groups if isinstance(groups, list) else []):
            for handler in (group.get("hooks", []) if isinstance(group, dict) else []) or []:
                command = handler.get("command", "") if isinstance(handler, dict) else ""
                if not isinstance(command, str) or not form.match(command):
                    problems.append(
                        f"{manifest_rel}: {event}[{index}] command must be "
                        f'afk-python "${{{root_var}}}/hooks/run-hook.py" '
                        f"[--soft] [--deadline N] plugin <handler.sh> [args] | repo-list <event>, "
                        f"or hooks/protected-branch-guard.py / -meter.py / -occupancy.py - got {command!r}"
                    )
    shared = {event: groups for event, groups in hmap.items()
              if event not in specific_events.get(MANIFEST_PROVIDER[manifest_rel], set())}
    twins[manifest_rel] = json.dumps(shared, sort_keys=True).replace("${" + root_var + "}", "<ROOT>")
if len(set(twins.values())) != 1:
    problems.append("hooks/hooks.json and hooks/hooks.codex.json differ beyond the root variable "
                    "and the CAPABILITIES.md provider-specific events")

for mcp_rel in (".mcp.json", ".mcp.codex.json"):
    try:
        servers = json.loads(read(plugin / mcp_rel)).get("mcpServers", {})
    except (json.JSONDecodeError, AttributeError):
        servers = {}
    for name, server in servers.items():
        if isinstance(server, dict) and server.get("command") != "afk-python":
            problems.append(f"{mcp_rel}: server {name!r} command must be afk-python, "
                            f"got {server.get('command')!r}")

# Live surfaces: a named interpreter other than afk-python is a runtime the setup never proved.
# History (CHANGELOG.md, adr/) is out of scope; explanatory text uses `interpreter` allow entries.
interpreter_word = re.compile(r"(?<![\w./\\$-])(?:python3?|py -3)(?![\w.-])(?![\"']\s*[:,\]}])")
afk_py = re.compile(r"\bAFK_PY\b")
shebang = re.compile(r"^#!.*(?<![\w-])python3?\b")
prose_command = re.compile(r"`(?:\$ )?(?:python3?|py -3) [^`]*`|^\s*(?:\$ )?(?:python3?|py -3) \S")
argv_name = re.compile(r"""\[\s*["'](?:python3?|py)["']\s*,""")
history = ("CHANGELOG.md", "adr/*")


def interpreter_problem(path_rel: str, number: int, line: str, kind: str) -> None:
    if not allowed(path_rel, "interpreter", line):
        problems.append(f"{path_rel}:{number}: {kind} names an interpreter other than afk-python "
                        f"(or the retired override); use afk-python, or add an interpreter entry to "
                        f"hooks/native-contract-allow.txt for explanatory text")


def shell_file(path: Path) -> bool:
    if path.suffix == ".sh":
        return True
    if path.suffix or not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            first = handle.readline(200)
    except OSError:
        return False
    return first.startswith(b"#!") and (b"sh" in first and b"python" not in first)


for path in sorted(plugin.rglob("*")):
    path_rel = rel(path)
    if (not path.is_file() or "/__pycache__/" in f"/{path_rel}" or "/node_modules/" in f"/{path_rel}"
            or any(fnmatch.fnmatchcase(path_rel, glob) for glob in history)
            or path_rel.startswith(".git/")):
        continue
    is_ci = path_rel.startswith(".github/")
    if path.suffix == ".py":
        lines = read(path).splitlines()
        for number, line in enumerate(lines, 1):
            if (number == 1 and shebang.search(line)) or argv_name.search(line) or afk_py.search(line):
                interpreter_problem(path_rel, number, line, "python source")
    elif path.suffix == ".md":
        fenced = False
        for number, line in enumerate(read(path).splitlines(), 1):
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            hit = prose_command.search(line) if fenced else re.search(prose_command.pattern.split("|^")[0], line)
            if hit or afk_py.search(line):
                interpreter_problem(path_rel, number, line, "prose command")
    elif shell_file(path) or is_ci and path.suffix in (".yml", ".yaml"):
        python_body = False
        for number, line in enumerate(read(path).splitlines(), 1):
            # This gate's own Python body holds the forbidden patterns as data, so it gets the .py rules.
            if python_body:
                python_body = line != "PY"
                if python_body and (argv_name.search(line) or afk_py.search(line)):
                    interpreter_problem(path_rel, number, line, "python source")
                continue
            python_body = path_rel == "hooks/native-contract-gate.sh" and line.endswith("<<'PY'")
            code = line.split(" #", 1)[0] if not line.lstrip().startswith("#") else ""
            if (code and interpreter_word.search(code)) or afk_py.search(line) \
                    or (is_ci and "setup-python" in line):
                interpreter_problem(path_rel, number, line, "CI step" if is_ci else "shell command")


# F. Generated mirrors/activation surfaces may exist locally, never in git.
try:
    tracked_raw = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=repo, stderr=subprocess.DEVNULL
    )
    tracked = tracked_raw.decode("utf-8", errors="surrogateescape").split("\0")
except (OSError, subprocess.CalledProcessError) as exc:
    problems.append(f"git ls-files failed ({exc})")
    tracked = []
for path in tracked:
    normalized = path.replace("\\", "/").strip("/")
    if normalized == ".agents/plugins/marketplace.json":
        # The one committed exception: a Codex marketplace manifest has to live
        # here for `codex plugin marketplace add` to find this repository.
        continue
    if normalized.startswith(".agents/") or normalized.startswith(".codex/"):
        problems.append(f"{path}: tracked harness activation surface is forbidden")


# G. Provider envelope fixtures are one directory per adapter.
for adapter in sorted(plugin.glob("hooks/lib/providers/*.sh")):
    fixture_dir = plugin / "hooks/tests/envelopes" / adapter.stem
    if not fixture_dir.is_dir() or not any(path.is_file() for path in fixture_dir.rglob("*")):
        problems.append(f"{rel(adapter)}: missing envelope fixtures under {rel(fixture_dir)}/")


# H. The supported-harness registry is the one list of harnesses; an adapter
# without a row (or a row without an adapter) means a half-added harness.
registry_text = read(plugin / "PROVIDERS.md") if (plugin / "PROVIDERS.md").is_file() else ""
section = re.search(
    r"(?ms)^##\s+Supported harnesses\s*$(.*?)(?=^##\s|\Z)", registry_text
)
if not section:
    problems.append("PROVIDERS.md: missing the `## Supported harnesses` registry")
else:
    declared = set(re.findall(r"(?m)^\|\s*`([a-z0-9_-]+)`\s*\|", section.group(1)))
    adapters = {path.stem for path in plugin.glob("hooks/lib/providers/*.sh")}
    for missing in sorted(adapters - declared):
        problems.append(
            f"PROVIDERS.md: adapter {missing!r} has no supported-harness registry row"
        )
    for stale in sorted(declared - adapters):
        problems.append(
            f"PROVIDERS.md: registry row {stale!r} has no hooks/lib/providers/{stale}.sh"
        )


# I. A CR byte in a shell handler is fatal wherever a POSIX shell runs it, and
# the failure is silent: the harness reports a failed hook, never a gate verdict.
# Judge the working tree, which is what a harness copies, not the index.
for script in sorted(list(plugin.rglob("*.sh")) + list(plugin.glob("hooks/**/*.py"))):
    try:
        if b"\r" in script.read_bytes():
            problems.append(
                f"{rel(script)}: CRLF line endings; shell handlers must be LF "
                f"(see the .gitattributes rule)"
            )
    except OSError as exc:
        problems.append(f"{rel(script)}: cannot read ({exc})")


# K. A hooks/lib/providers/<name>_*.py helper is provider-owned code: its own
# <name>.sh adapter is its one permitted caller (AGENTS.md "Harness-agnostic
# by default", PROVIDERS.md "Distribution law"). scripts/tests/ is exempt —
# a unit test legitimately loads the helper module directly.
for helper in sorted(plugin.glob("hooks/lib/providers/*_*.py")):
    name = helper.stem.split("_", 1)[0]
    adapter = plugin / "hooks/lib/providers" / f"{name}.sh"
    if not adapter.is_file() or helper.name not in read(adapter):
        problems.append(
            f"{rel(helper)}: no hooks/lib/providers/{name}.sh references it by name"
        )
    for candidate in plugin.rglob("*"):
        if not candidate.is_file() or candidate in (helper, adapter):
            continue
        if candidate.suffix not in {".sh", ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml"}:
            continue
        if "scripts/tests" in candidate.relative_to(plugin).as_posix():
            continue
        try:
            text = read(candidate)
        except OSError:
            continue
        if helper.name in text:
            problems.append(
                f"{rel(candidate)}: references provider helper {helper.name!r}; "
                f"only hooks/lib/providers/{name}.sh may call it"
            )


# M. Bounded hooks. A hook that outlives its harness timeout is killed with no
# verdict, so every launcher entry carries a deadline below its timeout; and a
# repository-wide content scan in a Stop-path gate must take the one bounded route.
for manifest_rel in ("hooks/hooks.json", "hooks/hooks.codex.json"):
    for event, groups in load_hook_map(manifest_rel).items():
        for group in groups if isinstance(groups, list) else []:
            for handler in (group.get("hooks", []) if isinstance(group, dict) else []) or []:
                if not isinstance(handler, dict):
                    continue
                command = handler.get("command", "")
                if not isinstance(command, str):
                    continue
                if "run-hook.py" not in command:
                    if not allowed(manifest_rel, "hook-deadline", command):
                        problems.append(
                            f"{manifest_rel}: {event} entry bypasses run-hook.py with no hook-deadline "
                            f"entry in hooks/native-contract-allow.txt naming its own deadline: {command}"
                        )
                    continue
                timeout = handler.get("timeout")
                if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
                    problems.append(f"{manifest_rel}: {event} entry has no explicit timeout: {command}")
                    continue
                found = re.search(r"--deadline ([0-9]+(?:\.[0-9]+)?)", command)
                if not found:
                    problems.append(f"{manifest_rel}: {event} entry has no --deadline: {command}")
                elif float(found.group(1)) > min(0.95 * timeout, timeout - 1):
                    problems.append(
                        f"{manifest_rel}: {event} --deadline {found.group(1)} is not below "
                        f"min(0.95*timeout, timeout-1) for timeout {timeout}: {command}"
                    )

repo_scans = [
    re.compile(r"\bgit\s+grep\b"),
    re.compile(r"(?<![\w-])rg\s"),
    re.compile(r"\bgrep\s+(?:-\w+\s+)*-\w*[rR]"),
    re.compile(r"\bfind\s+\.(?:\s|/|$)"),
    re.compile(r"\bos\.walk\("),
    re.compile(r"\.rglob\("),
]
stop_path = {
    path for pattern in ("hooks/*-gate.sh", "hooks/stop-gates.sh", "hooks/gate-*.sh",
                         "hooks/lib/*.sh", "hooks/lib/*.py")
    for path in plugin.glob(pattern)
} - {plugin / "hooks/lib/bounded_scan.py"}
for path in sorted(stop_path):
    path_rel = rel(path)
    for number, line in enumerate(read(path).splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        if any(pattern.search(line) for pattern in repo_scans) and not allowed(path_rel, "repo-scan", line):
            problems.append(
                f"{path_rel}:{number}: repository-wide content scan outside hooks/lib/bounded_scan.py; "
                f"route it through the bounded scanner or add a repo-scan entry to hooks/native-contract-allow.txt"
            )


if problems:
    print("\n".join(sorted(set(problems))))
    sys.exit(2)
PY
  ) || rc=$?

  if [ "$rc" -ne 0 ]; then
    gate_metrics_emit native-contract blocked
    {
      printf '[afk] Native contract gate: the plugin is harness-coupled or its native surfaces drifted.\n'
      [ -n "$findings" ] && printf '%s\n' "$findings"
      printf '\nFix the named source, declare shared hook capabilities in CAPABILITIES.md,\n'
      printf 'or add a narrow explained prose exception to hooks/native-contract-allow.txt.\n'
    } >&2
    return 2
  fi

  gate_metrics_emit native-contract pass
  gate_cache_store native-contract "$cache_key"
  return 0
}

# ---- standalone invocation
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _d=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  _root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$_root" || exit 0
  # provider.sh first: this gate resolves the plugin's own directory through
  # afk_plugin_dir, and without it a manual run would scope to nothing and
  # report a silent pass.
  . "$_d/lib/provider.sh"
  . "$_d/lib/config.sh"; afk_config_load
  . "$_d/gate-context.sh"; gate_ctx_build
  . "$_d/gate-cache.sh"
  . "$_d/gate-metrics.sh"
  gate_native_contract; exit $?
fi
