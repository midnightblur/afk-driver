"""The test-first record of one subtask: `tdd_log.py <verb> [json-payload]`, or the payload on stdin."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN / "ports"))

from tracker import envelope  # noqa: E402
from tracker.envelope import Refusal, need, ok  # noqa: E402

TEST_LIMIT = 1800
GIT_LIMIT = 120
TAIL_LINES = 20
TEST_FILE = re.compile(r"(^|/)(tests?|specs?|__tests__|fixtures|fakes)/|(^|/)test_[^/]+$|_test\.[^/]+$|\.(test|spec)\.[^/]+$|Tests?\.[^/]+$")


def _path(payload):
    plan, subtask = Path(str(need(payload, "plan"))), str(need(payload, "subtask"))
    if not plan.is_dir():
        raise Refusal("bad-payload", f"no plan folder at {plan}")
    return plan / "review" / f"{subtask}.tdd.json"


def _load(path):
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"cycles": [], "no_test": []}
    except (OSError, ValueError) as error:
        raise Refusal("bad-state", f"cannot read {path}: {error}") from None
    if not isinstance(state, dict) or not isinstance(state.get("cycles"), list) or not isinstance(state.get("no_test"), list):
        raise Refusal("bad-state", f"{path} is not a test-first record")
    return state


def _save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=1), encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL, timeout=GIT_LIMIT)
    if done.returncode != 0:
        raise Refusal("git-failed", f"git {args[0]}: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout.decode("utf-8", "replace")


def _run(command):
    """(exit code, last lines of the output). The shell runs the command as the contract states it."""
    try:
        done = subprocess.run(command, shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=TEST_LIMIT)
    except subprocess.TimeoutExpired:
        raise Refusal("timed-out", f"the test command ran past {TEST_LIMIT} s") from None
    text = (done.stdout + done.stderr).decode("utf-8", "replace")
    return done.returncode, "\n".join(text.splitlines()[-TAIL_LINES:])


def is_test_file(path):
    return bool(TEST_FILE.search(path.replace("\\", "/")))


def _code_files(names):
    return sorted({name for name in names if name and not is_test_file(name)})


def _uncommitted(cwd):
    """The file names of uncommitted changes, new files too. `-z` keeps each name whole."""
    entries = _git(cwd, "status", "--porcelain", "-z", "--untracked-files=all").split("\0")
    names, skip = [], False
    for entry in entries:
        if skip:
            skip = False
        elif entry:
            names.append(entry[3:])
            skip = entry[0] in "RC"
    return names


def red(payload):
    path, behavior, command = _path(payload), str(need(payload, "behavior")), str(need(payload, "command"))
    state = _load(path)
    code = _code_files(_uncommitted("."))
    if code:
        raise Refusal("code-before-red", "code files changed before this test failed: commit finished work, and move the rest out", files=code)
    exit_code, tail = _run(command)
    if exit_code == 0:
        raise Refusal("not-red", "the test passes: it proves nothing about the new behavior yet", output=tail)
    cycle = next((item for item in state["cycles"] if item["behavior"] == behavior and item["green"] is None), None)
    if cycle is None:
        cycle = {"behavior": behavior, "green": None}
        state["cycles"].append(cycle)
    cycle.update(command=command, red={"head": _git(".", "rev-parse", "HEAD").strip(), "exit": exit_code})
    _save(path, state)
    return ok(behavior=behavior, exit=exit_code, output=tail)


def green(payload):
    path, behavior = _path(payload), str(need(payload, "behavior"))
    state = _load(path)
    cycle = next((item for item in state["cycles"] if item["behavior"] == behavior and item["green"] is None), None)
    if cycle is None:
        raise Refusal("no-red", f"no failing test is on record for {behavior}: run `red` first")
    exit_code, tail = _run(cycle["command"])
    if exit_code != 0:
        raise Refusal("not-green", "the test still fails", exit=exit_code, output=tail)
    cycle["green"] = {"head": _git(".", "rev-parse", "HEAD").strip(), "exit": 0}
    _save(path, state)
    return ok(behavior=behavior)


def no_test(payload):
    path, why = _path(payload), str(need(payload, "why"))
    state = _load(path)
    state["no_test"].append({"why": why})
    _save(path, state)
    return ok(recorded=len(state["no_test"]))


def verdict(plan, subtask, base, cwd="."):
    """Each way this subtask's record breaks the test-first order; empty when it holds."""
    state = _load(Path(plan) / "review" / f"{subtask}.tdd.json")
    if not state["cycles"] and not state["no_test"]:
        return [{"code": "no-tdd-record", "reason": "no `red` and no `no-test` is on record"}]
    failures = [{"code": "red-open", "reason": f"no `green` is on record for {cycle['behavior']}"}
                for cycle in state["cycles"] if cycle["green"] is None]
    if state["cycles"] and not state["no_test"]:
        first_red = state["cycles"][0]["red"]["head"]
        names = _git(cwd, "log", "--first-parent", "--no-merges", "--name-only", "--format=", f"{base}..{first_red}").splitlines()
        early = _code_files(names)
        if early:
            failures.append({"code": "code-before-red", "reason": f"commits before the first failing test changed code: {', '.join(early)}"})
    return failures


VERBS = {"red": red, "green": green, "no-test": no_test}


def main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
