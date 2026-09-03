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
#   D. every agents/*.md has a providers/codex/agents/afk-toolkit-*.toml stub;
#   E. hooks.json events/matchers stay inside CAPABILITIES.md's literal shared
#      subset declarations;
#   F. no generated activation/mirror tree is tracked;
#   G. every hooks/lib/providers/*.sh adapter has envelope fixtures under
#      hooks/tests/envelopes/<provider>/;
#   H. the PROVIDERS.md supported-harness registry and the adapters on disk are
#      one list;
#   I. every shell handler and hook launcher is LF-only, since a harness copies
#      this tree verbatim into its plugin cache and runs it through a POSIX shell;
#   J. every hooks.json command goes through hooks/run-hook.py, so no command
#      string depends on a shell dialect or on a bare `bash`.
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

  local py=python findings rc=0
  command -v python >/dev/null 2>&1 || py=python3
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
excluded_prose = {"PROVIDERS.md", "CAPABILITIES.md", "providers/CONFORMANCE.md"}
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
    stub = plugin / "providers/codex/agents" / f"afk-toolkit-{agent.stem}.toml"
    if not stub.is_file():
        problems.append(f"{rel(agent)}: missing {rel(stub)}")


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
hooks_path = plugin / "hooks/hooks.json"
try:
    hooks_payload = json.loads(read(hooks_path))
except json.JSONDecodeError as exc:
    problems.append(f"hooks/hooks.json: invalid JSON ({exc})")
    hooks_payload = {}
hook_map = hooks_payload.get("hooks", {})
if not isinstance(hook_map, dict):
    problems.append("hooks/hooks.json: hooks must be an object")
    hook_map = {}
if shared_events is not None:
    for event in sorted(set(hook_map) - shared_events):
        problems.append(f"hooks/hooks.json: event {event!r} is outside the shared subset")
if shared_matchers is not None:
    for event, groups in hook_map.items():
        if not isinstance(groups, list):
            problems.append(f"hooks/hooks.json: event {event!r} handlers must be an array")
            continue
        for index, group in enumerate(groups):
            if not isinstance(group, dict):
                problems.append(f"hooks/hooks.json: {event}[{index}] must be an object")
                continue
            matcher = group.get("matcher", "*")
            if not isinstance(matcher, str):
                problems.append(f"hooks/hooks.json: {event}[{index}] matcher must be a string")
                continue
            for token in filter(None, (part.strip() for part in matcher.split("|"))):
                if token not in shared_matchers:
                    problems.append(
                        f"hooks/hooks.json: matcher {token!r} is outside the shared subset"
                    )


# J. One launch mechanism. A command string is parsed by whichever shell the
# harness chose, and `bash` names the WSL stub on many Windows machines, so
# every handler goes through the launcher and no command carries shell syntax.
launcher = re.compile(
    r'^python "\$\{CLAUDE_PLUGIN_ROOT\}/hooks/run-hook\.py"'
    r'(?: --soft)?'
    r'(?: plugin [A-Za-z0-9._-]+\.sh(?: [A-Za-z0-9._=-]+)*'
    r'| repo-list (?:SessionStart|PreToolUse|Stop))$'
)
for event, groups in hook_map.items():
    if not isinstance(groups, list):
        continue
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        for handler in group.get("hooks", []) or []:
            if not isinstance(handler, dict):
                continue
            command = handler.get("command", "")
            if not isinstance(command, str) or not launcher.match(command):
                problems.append(
                    f"hooks/hooks.json: {event}[{index}] command must be "
                    f'python "${{CLAUDE_PLUGIN_ROOT}}/hooks/run-hook.py" '
                    f"[--soft] plugin <handler.sh> [args] | repo-list <event> - got {command!r}"
                )


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
for script in sorted(list(plugin.rglob("*.sh")) + list(plugin.glob("hooks/*.py"))):
    try:
        if b"\r" in script.read_bytes():
            problems.append(
                f"{rel(script)}: CRLF line endings; shell handlers must be LF "
                f"(see the .gitattributes rule)"
            )
    except OSError as exc:
        problems.append(f"{rel(script)}: cannot read ({exc})")


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
  . "$_d/gate-context.sh"; gate_ctx_build
  . "$_d/gate-cache.sh"
  . "$_d/gate-metrics.sh"
  gate_native_contract; exit $?
fi
