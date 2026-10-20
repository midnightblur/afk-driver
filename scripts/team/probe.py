"""The machine probe: which transport kind this session can use, and the hand-in of that kind to the dispatcher.

`resolve_kind` reads `transport.kind` and `transport.pane-switch` through the configuration reader, detects
each pane tool in this session, and answers the kind, why, and any conflict between configuration and
detection by name; with no pane tool usable it resolves the subagent kind and says so. `dispatch` runs one
transport verb in its own shell: it loads the configuration first, then sets the resolved kind, so no
configuration load can blank it. It never exports AFK_CFG_LOADED or AFK_CONFIG, drops an inherited AFK_CFG_LOADED so the
configuration always loads, pins AFK_PLUGIN_ROOT to this plugin, and never edits the dispatcher.

    probe.py resolve [--harness claude|codex ...]
    probe.py run <kind> <verb> '<json>'
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / "adapters" / "transport"))
sys.path.insert(0, str(PLUGIN / "adapters" / "transport" / "multiplexer"))
import contract  # noqa: E402
import herdr  # noqa: E402
import launch  # noqa: E402

KINDS = ("subagent", "headless", "multiplexer", "desktop")
PANE_KINDS = ("multiplexer", "desktop")          # best first
SUBAGENT_SAYS = "no pane transport is usable in this session, so role agents run as subagents"


def _config(key: str, root: Path, env: Mapping[str, str], run: Callable) -> str | None:
    """One configured value; an absent key, an empty `transport:` section and a null all read as absent."""
    done = run([sys.executable, str(PLUGIN / "scripts" / "afk-config.py"), "get", key], cwd=str(root),
               capture_output=True, text=True, timeout=30, env=dict(env), check=False)
    value = done.stdout.strip() if done.returncode == 0 else ""
    return value or None


def detect(env: Mapping[str, str], harnesses: tuple[str, ...], *, which: Callable = shutil.which,
           run: Callable = subprocess.run) -> list[dict]:
    """Each pane tool's state in this session: usable, fixable (a named setting), outside, broken or absent."""
    return [herdr.detect(env, harnesses, which=which, run=run).as_dict() | {"kind": "multiplexer"}]


def resolve_kind(root: Path | str = ".", *, env: Mapping[str, str] | None = None,
                 harnesses: tuple[str, ...] | None = None, which: Callable = shutil.which,
                 run: Callable = subprocess.run) -> dict:
    """The best kind this session can use, or the conflict that stops one: {kind, source, says, conflict, tools}."""
    env = dict(os.environ if env is None else env)
    root = Path(root)
    if harnesses is None:
        harnesses = tuple(h for h in launch.HARNESSES if which(h, path=env.get("PATH")))
    forced = _config("transport.kind", root, env, run)
    switch = _config("transport.pane-switch", root, env, run)
    tools = detect(env, harnesses, which=which, run=run)
    usable = [t for t in tools if t["status"] == "usable"]
    result = {"kind": None, "source": None, "says": "", "conflict": None, "tools": tools,
              "harnesses": list(harnesses)}
    if forced:
        result["source"] = "config"
        problem = _forced_problem(forced, switch, tools, harnesses)
        if problem:
            return {**result, "conflict": problem}
        return {**result, "kind": forced, "says": f"transport.kind forces the {forced} kind"}
    result["source"] = "detected"
    if switch == "subagent":
        return {**result, "source": "config", "kind": "subagent",
                "says": "transport.pane-switch is subagent, so role agents run as subagents"}
    for kind in PANE_KINDS:
        found = next((t for t in usable if t["kind"] == kind), None)
        if found:
            says = f"{found['tool']} runs this session, so role agents run in {found['tool']} panes"
            if not found["tabs"]:
                says += f"; {found['tool']} cannot make tabs, so agents open in panes of this tab"
            return {**result, "kind": kind, "tool": found["tool"], "says": says}
    fixable = [s for t in tools if t["status"] == "fixable" for s in t["settings"]]
    says = SUBAGENT_SAYS
    if fixable:
        says += "; to use panes, fix: " + "; ".join(f"{s['name']} (`{s['fix']}`)" for s in fixable)
    return {**result, "kind": "subagent", "says": says}


def _forced_problem(forced: str, switch: str | None, tools: list[dict], harnesses: tuple[str, ...]) -> dict | None:
    if forced in PANE_KINDS and switch == "subagent":
        return {"name": "pane switch against forced kind",
                "detail": f"transport.kind is {forced}, but transport.pane-switch is subagent"}
    if forced in PANE_KINDS:
        own = [t for t in tools if t["kind"] == forced]
        if not any(t["status"] == "usable" for t in own):
            states = "; ".join(f"{t['tool']} is {t['status']}: {t['reason']}" for t in own) \
                or f"no {forced} tool is detected"
            return {"name": f"{forced} forced but not usable",
                    "detail": f"transport.kind is {forced}, but detection says: {states}"}
    if forced == "headless" and not harnesses:
        return {"name": "headless forced but no harness",
                "detail": "transport.kind is headless, but neither claude nor codex is on PATH"}
    return None


def dispatch(kind: str, verb: str, payload: Mapping, *, root: Path | str = ".",
             env: Mapping[str, str] | None = None, plugin: Path = PLUGIN) -> tuple[int, str, str]:
    """Run one verb of `kind` through the unchanged dispatcher, in a shell of its own."""
    if kind not in KINDS:
        raise ValueError(f"unknown transport kind {kind!r}; one of {', '.join(KINDS)}")
    bash = _bash()
    if bash is None:
        return 2, "", "afk: no POSIX shell found to run the transport dispatcher\n"
    child = {k: v for k, v in (os.environ if env is None else env).items() if k != "AFK_CFG_LOADED"}
    child["AFK_PLUGIN_ROOT"] = str(plugin)
    script = ('. "$AFK_PLUGIN_ROOT/hooks/lib/adapter.sh" || exit 2; afk_config_load; AFK_CFG_TRANSPORT=$1; '
              'afk_adapter transport "$2" "$3"')
    seconds = contract.BUDGET_MS[verb] / 1000 + 15 if verb in contract.BUDGET_MS else 30
    done = subprocess.run([str(bash), "-c", script, "probe", kind, verb, json.dumps(payload)],
                          cwd=str(root), capture_output=True, text=True, timeout=seconds, env=child, check=False)
    return done.returncode, done.stdout, done.stderr


def _bash() -> Path | None:
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_probe", PLUGIN / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="probe.py")
    sub = parser.add_subparsers(dest="command", required=True)
    res = sub.add_parser("resolve")
    res.add_argument("--harness", action="append", choices=launch.HARNESSES)
    one = sub.add_parser("run")
    one.add_argument("kind", choices=KINDS)
    one.add_argument("verb")
    one.add_argument("payload")
    args = parser.parse_args(argv)
    if args.command == "resolve":
        found = resolve_kind(Path.cwd(), harnesses=tuple(args.harness) if args.harness else None)
        sys.stdout.write(json.dumps(found, sort_keys=True) + "\n")
        return 0
    try:
        payload = json.loads(args.payload)
    except ValueError as problem:
        sys.stdout.write(json.dumps({"error": True, "operation": args.verb, "reason": str(problem)}) + "\n")
        return 2
    code, out, err = dispatch(args.kind, args.verb, payload, root=Path.cwd())
    sys.stdout.write(out)
    sys.stderr.write(err)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
