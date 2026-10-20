"""The spawn permission check: confirm, through the provider layer, that the one allow rule covering the team entry
script for every transport verb is in an allow list, and that no block-list entry matches a verb command, in the
settings files the adapter names; or refuse naming /afk:setup and the rule when the adapter printed one.
Organization-managed settings are not read.

The provider adapter owns the rule text, the settings files the harness reads and the lists in them
(PROVIDERS.md "Spawn allow rule"); this module reads them in a bash child and holds no harness fact itself.
The rule matches every command of the form `INVOCATION <verb> ...`, so it covers all six transport verbs.

    permission.py check [--root DIR]   one JSON answer; exit 0 ok, 1 refused
    permission.py rule [--json]        the rule text (a JSON string with --json), empty when none is needed
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / "adapters" / "transport"))
import contract  # noqa: E402

INVOCATION = 'afk-python "${AFK_PLUGIN_ROOT}/scripts/afk-team.py"'
ENTRY_NAME = "afk-team.py"
SETUP = "/afk:setup"

_ADAPTER = r'''
. "$1/hooks/lib/provider.sh" || exit 2
host() { if command -v cygpath >/dev/null 2>&1; then cygpath -m -- "$1"; else printf '%s\n' "$1"; fi; }
p=$(afk_provider)
printf 'provider\t%s\n' "$p"
[ "$p" != unknown ] || exit 0
need() { command -v "$1" >/dev/null 2>&1 || { printf 'undefined\t%s\n' "$1"; exit 3; }; }
need "afk_${p}_spawn_allow_rule"
r=$("afk_${p}_spawn_allow_rule")
printf 'rule\t%s\n' "$r"
[ -n "$r" ] || exit 0
need "afk_${p}_spawn_rule_files"
need "afk_${p}_spawn_rule_lists"
need "afk_${p}_spawn_rule_blocks"
"afk_${p}_spawn_rule_files" "$2" | while IFS= read -r f; do printf 'file\t%s\n' "$(host "$f")"; done
"afk_${p}_spawn_rule_lists" | while IFS= read -r l; do printf 'list\t%s\n' "$l"; done
'''

_BLOCKS = r'''
. "$1/hooks/lib/provider.sh" </dev/null || exit 2
p=$(afk_provider </dev/null)
shift
n=0
while IFS= read -r entry; do
  n=$((n + 1)) entry=${entry%$'\r'}
  hit=$("afk_${p}_spawn_rule_blocks" "$entry" "$@" </dev/null) && status=0 || status=$?
  case $status in
    0) printf '%s\t%s\n' "$n" "$hit" ;;
    1) ;;
    *) printf 'afk_%s_spawn_rule_blocks exited %s\n' "$p" "$status" >&2; exit 4 ;;
  esac
done
'''


def verb_commands() -> list[str]:
    """One command per transport verb, in the form the rule must match."""
    return [f"{INVOCATION} {verb} '{{}}'" for verb in contract.VERBS]


def check_spawn_permission(root: Path | str = ".", *, env: Mapping[str, str] | None = None,
                           run: Callable = subprocess.run) -> dict:
    """check() → ok, or a refusal carrying the adapter's rule text, "" if it printed none.

    Returns {ok, provider, rule, problem, says, files}."""
    adapter = _adapter(Path(root).resolve(), env, run)
    if "error" in adapter:
        return _refuse(adapter.get("provider", "unknown"), adapter.get("rule", ""), "provider-layer",
                       f"{adapter['error']}; run {SETUP}; nothing was started", [])
    provider, rule = adapter["provider"], adapter["rule"]
    if provider == "unknown":
        return {"ok": True, "provider": provider, "rule": "", "problem": None, "files": [],
                "says": "no provider adapter detects this session's harness, so no spawn allow rule is checked; "
                        "set AFK_PROVIDER to check one"}
    if not rule:
        return {"ok": True, "provider": provider, "rule": "", "problem": None, "files": [],
                "says": f"the {provider} adapter names no spawn allow rule, so none is needed"}
    allowed, blocked, stale, read = [], [], [], []
    for path in adapter["files"]:
        settings = _load(path)
        if settings is None:
            continue
        read.append(path)
        for kind, key in adapter["lists"]:
            entries = _entries(settings, key)
            if kind == "allow":
                if rule in entries:
                    allowed.append(path)
                stale += [(path, e) for e in entries if ENTRY_NAME in e and e != rule]
            else:
                blocked += [(path, key, e) for e in entries if "\n" not in e]
    allow_key = next((key for kind, key in adapter["lists"] if kind == "allow"), "allow list")
    target = adapter["files"][0] if adapter["files"] else "the user settings file"
    hits = _blocks([e for _, _, e in blocked], env, run) if blocked else {}
    if "error" in hits:
        return _refuse(provider, rule, "provider-layer", f"{hits['error']}; run {SETUP}; nothing was started", read)
    if hits:
        first = min(hits)
        holder, key, entry = blocked[first]
        return _refuse(provider, rule, "blocked", f"{holder} {key} holds `{entry}`, which matches `{hits[first]}`; "
                       f"the harness reads it before {allow_key}, so the spawn rule `{rule}` does not apply; "
                       f"remove it there, then run {SETUP}; nothing was started", read)
    if allowed:
        return {"ok": True, "provider": provider, "rule": rule, "problem": None, "files": read,
                "says": f"the spawn rule is in {allowed[0]} {allow_key}"}
    if stale:
        holder, entry = stale[0]
        return _refuse(provider, rule, "stale", f"{holder} {allow_key} holds `{entry}`, which is not the current "
                       f"spawn rule; replace it with `{rule}`, then run {SETUP}; nothing was started", read)
    return _refuse(provider, rule, "missing", f"the spawn rule `{rule}` is in no allow list of the settings files "
                   f"read; add it to {allow_key} in {target}, then run {SETUP}; nothing was started", read)


def _refuse(provider: str, rule: str, problem: str, says: str, files: list[str]) -> dict:
    return {"ok": False, "provider": provider, "rule": rule, "problem": problem, "says": says, "files": files}


def _adapter(root: Path, env: Mapping[str, str] | None, run: Callable) -> dict:
    bash = _bash()
    if bash is None:
        return {"error": "no POSIX shell found to read the provider layer"}
    child = dict(os.environ if env is None else env)
    try:
        done = run([str(bash), "-c", _ADAPTER, "permission", str(PLUGIN), str(root)], capture_output=True,
                   text=True, encoding="utf-8", timeout=30, env=child, check=False)
    except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError) as problem:
        return {"error": f"the provider layer did not answer: {problem}"}
    found: dict = {"provider": "unknown", "rule": "", "files": [], "lists": []}
    undefined = ""
    for line in done.stdout.splitlines():
        field, _, value = line.partition("\t")
        if field == "undefined":
            undefined = value
        elif field in ("provider", "rule"):
            found[field] = value
        elif field == "file" and value not in found["files"]:
            found["files"].append(value)
        elif field == "list" and len(value.split()) == 2:
            found["lists"].append(tuple(value.split()))
    if undefined:
        found["error"] = (f"the {found['provider']} adapter does not define {undefined}; add it as PROVIDERS.md "
                          '"Spawn allow rule" says')
    elif done.returncode != 0:
        found["error"] = f"the provider layer exited {done.returncode}: {done.stderr.strip()}"
    return found


def _blocks(entries: list[str], env: Mapping[str, str] | None, run: Callable) -> dict:
    """{index into entries: the first verb command that entry matches}, by the adapter's matcher."""
    bash = _bash()
    if bash is None:
        return {"error": "no POSIX shell found to read the provider layer"}
    child = dict(os.environ if env is None else env)
    try:
        done = run([str(bash), "-c", _BLOCKS, "permission", str(PLUGIN), *verb_commands()],
                   input="".join(f"{e}\n" for e in entries), capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=30, env=child, check=False)
    except (OSError, subprocess.TimeoutExpired) as problem:
        return {"error": f"the provider layer did not answer: {problem}"}
    if done.returncode != 0:
        return {"error": f"the provider layer exited {done.returncode}: {done.stderr.strip()}"}
    hits = {}
    for line in done.stdout.splitlines():
        index, _, command = line.partition("\t")
        if index.isdigit() and 0 < int(index) <= len(entries):
            hits.setdefault(int(index) - 1, command)
    return hits


def _load(path: str) -> object | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _entries(settings: object, key: str) -> list[str]:
    node = settings
    for part in key.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return [e for e in node if isinstance(e, str)] if isinstance(node, list) else []


def _bash() -> Path | None:
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_permission", PLUGIN / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="permission.py")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("check")
    one.add_argument("--root", default=".")
    text = sub.add_parser("rule")
    text.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "check":
        answer = check_spawn_permission(Path(args.root))
        sys.stdout.write(json.dumps(answer, sort_keys=True) + "\n")
        return 0 if answer["ok"] else 1
    adapter = _adapter(Path.cwd(), None, subprocess.run)
    if "error" in adapter:
        sys.stderr.write(f"afk: {adapter['error']}\n")
        return 1
    if adapter["rule"]:
        sys.stdout.write((json.dumps(adapter["rule"]) if args.json else adapter["rule"]) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
