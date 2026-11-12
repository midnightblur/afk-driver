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
sys.path.insert(0, str(PLUGIN / "skills" / "autopilot" / "scripts"))

from tracker import envelope  # noqa: E402
from tracker.envelope import Refusal, need, ok  # noqa: E402
from plan_contract import plan_file, read_text, rules_of  # noqa: E402

TEST_LIMIT = 1800
GIT_LIMIT = 120
TAIL_LINES = 20
LEVELS = ("low", "high")
TEST_FILE = re.compile(r"(^|/)(tests?|specs?|__tests__|fixtures|fakes)/|(^|/)test_[^/]+$|_test\.[^/]+$|\.(test|spec)\.[^/]+$|Tests?\.[^/]+$")


def _path(payload):
    plan, subtask = Path(str(need(payload, "plan"))), str(need(payload, "subtask"))
    if not plan.is_dir():
        raise Refusal("bad-payload", f"no plan folder at {plan}")
    return plan / "review" / f"{subtask}.tdd.json"


def _rules(payload):
    """The rule set of the plan; 1 when the folder has no PLAN.md."""
    path = plan_file(Path(str(payload["plan"])))
    return rules_of(read_text(path)) if path.is_file() else 1


def _row_of(payload, rules):
    """The plan row of a cycle or a no-test entry: `row` (VR-NNN), `test` (file::name), `level`. A `> Rules: 2` plan needs `row`."""
    row, level = payload.get("row"), payload.get("level") or "low"
    if rules == 2 and not row:
        raise Refusal("bad-payload", "a `> Rules: 2` plan needs `row`: the VR-NNN id of the plan row this work is for")
    if level not in LEVELS:
        raise Refusal("bad-payload", f"`level` must be one of {', '.join(LEVELS)}, not {level}")
    return {"row": str(row) if row else None, "test": str(payload["test"]) if payload.get("test") else None, "level": level}


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
    row = _row_of(payload, _rules(payload))
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
    cycle.update(**row, command=command, red={"head": _git(".", "rev-parse", "HEAD").strip(), "exit": exit_code})
    _save(path, state)
    return ok(behavior=behavior, exit=exit_code, output=tail)


def _show(top, head, name):
    """The bytes of `name` at `head`; None when `head` has no such file."""
    done = subprocess.run(["git", "show", f"{head}:{name}"], cwd=top, capture_output=True, stdin=subprocess.DEVNULL, timeout=GIT_LIMIT)
    return done.stdout if done.returncode == 0 else None


def _on_parent(cycle):
    """Run the cycle's test with every code file as it was at the red head; the test files stay. Every file is put back.

    The served repository's CI runs mutation where it has a tool (PLAN.md D-1); this is the check without one (PRD AC-021).
    """
    top, head = _git(".", "rev-parse", "--show-toplevel").strip(), cycle["red"]["head"]
    names = _git(top, "diff", "--no-renames", "--name-only", "-z", head).split("\0")
    names += _git(top, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    paths = [Path(top) / name for name in _code_files(names)]
    kept = {path: path.read_bytes() if path.is_file() else None for path in paths}
    try:
        for path in paths:
            old = _show(top, head, path.relative_to(top).as_posix())
            if old is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(old)
        return _run(cycle["command"])
    finally:
        for path, data in kept.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)


def green(payload):
    path, behavior = _path(payload), str(need(payload, "behavior"))
    state = _load(path)
    cycle = next((item for item in state["cycles"] if item["behavior"] == behavior and item["green"] is None), None)
    if cycle is None:
        raise Refusal("no-red", f"no failing test is on record for {behavior}: run `red` first")
    exit_code, tail = _run(cycle["command"])
    if exit_code != 0:
        raise Refusal("not-green", "the test still fails", exit=exit_code, output=tail)
    if (cycle.get("level") or "low") == "low" and _rules(payload) == 2:
        exit_code, tail = _on_parent(cycle)
        if exit_code == 0:
            raise Refusal("passes-on-parent", "VC-1: the test also passes on the code of the commit its red ran on, so it does not fail without the change", output=tail)
    cycle["green"] = {"head": _git(".", "rev-parse", "HEAD").strip(), "exit": 0}
    _save(path, state)
    return ok(behavior=behavior)


def no_test(payload):
    path, why = _path(payload), str(need(payload, "why"))
    row = _row_of(payload, _rules(payload))
    state = _load(path)
    state["no_test"].append({"why": why, **row, "head": _git(".", "rev-parse", "HEAD").strip()})
    _save(path, state)
    return ok(recorded=len(state["no_test"]))


def _first_head(heads, base, cwd):
    """The oldest of these heads on the first-parent line from `base` to HEAD; None when none is on it."""
    order = [base, *reversed(_git(cwd, "rev-list", "--first-parent", f"{base}..HEAD").split())]
    known = [head for head in heads if head in order]
    return min(known, key=order.index) if known else None


def verdict(plan, subtask, base, cwd="."):
    """Each way this subtask's record breaks the test-first order; empty when it holds.

    A high-level cycle needs no green here: its green comes at the end gate. Code may change only after the first
    `red` or `no-test` entry; a no-test entry of a row covers the work after it, not the work before it. A no-test
    entry with no row, as old calls make, keeps the check off as before.
    """
    state = _load(Path(plan) / "review" / f"{subtask}.tdd.json")
    if not state["cycles"] and not state["no_test"]:
        return [{"code": "no-tdd-record", "reason": "no `red` and no `no-test` is on record"}]
    failures = [{"code": "red-open", "reason": f"no `green` is on record for {cycle['behavior']}"}
                for cycle in state["cycles"] if cycle["green"] is None and (cycle.get("level") or "low") != "high"]
    if any(entry.get("row") is None for entry in state["no_test"]):
        return failures
    heads = [cycle["red"]["head"] for cycle in state["cycles"]] + [entry["head"] for entry in state["no_test"]]
    first = _first_head(heads, base, cwd)
    if first is not None:
        names = _git(cwd, "log", "--first-parent", "--no-merges", "--name-only", "--format=", f"{base}..{first}").splitlines()
        early = _code_files(names)
        if early:
            failures.append({"code": "code-before-red", "reason": f"VC-1: commits before the first failing test or no-test entry changed code: {', '.join(early)}"})
    return failures


VERBS = {"red": red, "green": green, "no-test": no_test}


def main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
