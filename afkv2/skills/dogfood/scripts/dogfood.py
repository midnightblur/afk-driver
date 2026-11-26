"""The dogfood session between the main pane and the afkv2 pane: `dogfood.py <verb> [options]`.

Verbs:
  start --ask-file F   main pane: open the afkv2 pane and start its agent with the ask, or send the ask to the live one
  status               either pane: the state of the session, or null

Each verb prints 1 JSON object, `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`, and exits 0 ok,
1 refused, 2 unreadable input. The caller is the pane of `HERDR_PANE_ID`, never an argument. dogfood.py is the only
writer of the state file `dogfood-<main pane>.json` in the afkv2 data folder; every herdr and git call goes through
the runner, a `HerdrRunner` of the proposer engine.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN / "skills" / "use-lavish" / "scripts"))
sys.path.insert(0, str(PLUGIN / "skills" / "setup" / "scripts"))
sys.path.insert(1, str(PLUGIN / "scripts"))

from grill_common import EXIT_UNREADABLE, Parser, Refusal  # noqa: E402
from places import Places, write_atomic  # noqa: E402
from proposer_engine import HerdrRunner  # noqa: E402
from setup import read_install_record  # noqa: E402

STATE_VERSION = 1
HARNESS = "claude"
AGENT_ARGS = ["--model", "opus", "--effort", "max", "--dangerously-skip-permissions"]
START_MS, PROMPT_MS = "90000", "30000"
COMMAND_S = 120
AGENT_FILE = Path("afkv2") / "skills" / "dogfood" / "AGENT.md"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# herdr, through the runner.

def _parsed(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def _herdr_code(out, err):
    for text in (err, out):
        data = _parsed(text)
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            return data["error"].get("code")
    return None


def _herdr_binary(env, runner):
    return env.get("HERDR_BIN_PATH") or runner.which("herdr")


def _herdr(env, runner, *args, timeout=COMMAND_S):
    return runner.run([_herdr_binary(env, runner), *args], timeout=timeout)


def _herdr_ok(env, runner, *args, timeout=COMMAND_S):
    code, out, err = _herdr(env, runner, *args, timeout=timeout)
    if code != 0:
        raise Refusal("herdr-failed", f"herdr {' '.join(args[:2])}: {_herdr_code(out, err) or (err or out).strip()}")
    return _parsed(out) or {}


def _herdr_pane(env, runner):
    """The pane of the caller; refuses outside herdr (herdr playbook H-9)."""
    if env.get("HERDR_ENV") != "1" or not env.get("HERDR_PANE_ID") or not _herdr_binary(env, runner):
        raise Refusal("outside-herdr", "this session does not run in a herdr pane, or herdr is not on PATH: start "
                                       "herdr, then run the skill again from a pane in it")
    return env["HERDR_PANE_ID"]


# The plugin source.

def _source(env, runner):
    """The source line of the install record, checked again: a main checkout of the afkv2 plugin source."""
    source = read_install_record(_places(env)).get("source", "").strip()
    if not source:
        raise Refusal("no-source", "the install record has no source line: run /afkv2:setup, which records the "
                                   "main checkout of the plugin source")
    problem = _source_problem(Path(source), runner)
    if problem:
        raise Refusal("source-broken", f"the source line {source} {problem}: run /afkv2:setup to record the main "
                                       f"checkout of the plugin source again")
    return source


def _source_problem(source, runner):
    if not source.is_dir():
        return "names no folder"
    text = runner.read_text(source / "afkv2" / ".claude-plugin" / "plugin.json")
    manifest = _parsed(text) if isinstance(text, str) else None
    if not isinstance(manifest, dict) or manifest.get("name") != "afkv2":
        return "holds no afkv2 plugin manifest"
    code, out, err = runner.run(["git", "-C", str(source), "rev-parse", "--path-format=absolute", "--git-dir",
                                 "--git-common-dir"])
    dirs = out.splitlines()
    if code != 0 or len(dirs) < 2:
        return f"is not a git repository ({(err or out).strip()})"
    if Path(dirs[0].strip()) != Path(dirs[1].strip()):
        return "is a linked worktree, not the main checkout"
    return None


# The state file.

def _places(env):
    return Places.from_env(env)


def state_path(env, main_pane):
    safe = "".join(char if char.isascii() and (char.isalnum() or char in "_-") else "_" for char in main_pane)
    return _places(env).data / f"dogfood-{safe}.json"


def _write_state(env, state):
    write_atomic(state_path(env, state["main_pane"]), (json.dumps(state, indent=2) + "\n").encode("utf-8"))


# The verbs.

def _agent_name(main_pane):
    return f"dogfood-{hashlib.sha256(main_pane.encode('utf-8')).hexdigest()[:4]}"


def _role_prompt(source, ask):
    return (f"You are the afkv2 agent of a dogfood session. Read {Path(source) / AGENT_FILE} and follow it. "
            f"The first ask:\n\n{ask}")


def _start_agent(env, runner, name, pane):
    """Start the afkv2 agent in its pane: Claude, the model and effort of AC-005, full auto-approval (H-4)."""
    code, out, err = _herdr(env, runner, "agent", "start", name, "--kind", HARNESS, "--pane", pane, "--timeout",
                            START_MS, "--", *AGENT_ARGS, timeout=COMMAND_S)
    if code != 0:
        problem = _herdr_code(out, err) or (err or out).strip()
        if problem == "agent_not_ready":
            raise Refusal("agent-not-ready", f"the agent {name} shows a dialog at startup, or did not get ready in "
                                             f"{int(START_MS) // 1000} s; its pane is closed")
        raise Refusal("herdr-failed", f"herdr agent start: {problem}; the pane is closed")


def verb_start(args, env, runner):
    """Open the afkv2 pane beside the main pane, start its agent, write the state, then send the role and the ask."""
    main_pane = _herdr_pane(env, runner)
    ask = Path(args.ask_file).read_text(encoding="utf-8")
    source = _source(env, runner)
    name = _agent_name(main_pane)
    split = _herdr_ok(env, runner, "pane", "split", "--pane", main_pane, "--direction", "right", "--cwd", source,
                      "--no-focus")
    pane = ((split.get("result") or {}).get("pane") or {}).get("pane_id")
    if not pane:
        raise Refusal("herdr-failed", "herdr pane split answered no pane id")
    try:
        _start_agent(env, runner, name, pane)
        state = {"version": STATE_VERSION, "main_pane": main_pane, "agent": name, "afkv2_pane": pane,
                 "harness": HARNESS, "source": source, "base": None, "worktrees": [], "notes": [],
                 "wrap_reported": False, "started": _now()}
        _write_state(env, state)
    except BaseException:
        _herdr(env, runner, "pane", "close", pane)
        raise
    _herdr_ok(env, runner, "agent", "prompt", name, _role_prompt(source, ask), "--wait", "--until", "working",
              "--timeout", PROMPT_MS)
    return {"ok": True, "status": "opened", "agent": name, "pane": pane, "state": state}


VERBS = {"start": verb_start}


def _parser():
    parser = Parser(prog="dogfood.py")
    verbs = parser.add_subparsers(dest="verb", required=True)
    verbs.add_parser("start").add_argument("--ask-file", required=True)
    return parser


def main(argv, env, runner, out=print):
    """Run 1 verb; print 1 JSON object; return the exit code."""
    try:
        args = _parser().parse_args(argv)
        answer = VERBS[args.verb](args, env, runner)
        code = 0
    except Refusal as refusal:
        answer = {"ok": False, "error": {"code": refusal.code, "reason": refusal.reason}, **refusal.extra}
        code = refusal.exit_code
    out(json.dumps(answer))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ, HerdrRunner()))
