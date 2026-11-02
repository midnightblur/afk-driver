"""Shared by the grill scripts: the answer envelope, atomic writes, and calling a port command."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
EXIT_REFUSED = 1
EXIT_UNREADABLE = 2


class Refusal(Exception):
    def __init__(self, code, reason, exit_code=EXIT_REFUSED, **extra):
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.exit_code = exit_code
        self.extra = extra


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Refusal("usage", message, EXIT_UNREADABLE)


def serve(handler, argv=None):
    """Run one verb; print one JSON object; return the exit code (0 ok, 1 refused, 2 unreadable input)."""
    try:
        print(json.dumps(handler(sys.argv[1:] if argv is None else argv)))
        return 0
    except Refusal as refusal:
        print(json.dumps({"ok": False, "error": {"code": refusal.code, "reason": refusal.reason, **refusal.extra}}))
        return refusal.exit_code
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": {"code": "bad-input", "reason": f"{type(error).__name__}: {error}"}}))
        return EXIT_UNREADABLE


def read_json(path):
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Refusal("unreadable", f"{path}: {error}", EXIT_UNREADABLE) from error


def write_text(path, text):
    """Replace the file in one step, with LF line ends on every platform."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_name(path.name + ".tmp")
    with open(scratch, "w", encoding="utf-8", newline="\n") as out:
        out.write(text)
    os.replace(scratch, path)


def write_json(path, value):
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def run_command(script, args, timeout):
    """Run a plugin script through this Python and return its one JSON answer; a refusal raises."""
    if not Path(script).is_file():
        raise Refusal("no-command", f"{script} does not exist in this plugin")
    env = {**os.environ, "PYTHONUTF8": "1"}
    try:
        run = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired as error:
        raise Refusal("timeout", f"{Path(script).name} {args[0]}: no answer after {timeout} s") from error
    try:
        answer = json.loads(run.stdout)
    except json.JSONDecodeError as error:
        raise Refusal("bad-answer", f"{Path(script).name} {args[0]}: exit {run.returncode}, "
                                    f"no JSON answer: {run.stderr[-500:]}") from error
    if not isinstance(answer, dict) or not answer.get("ok"):
        problem = answer.get("error") if isinstance(answer, dict) else None
        problem = problem if isinstance(problem, dict) else {}
        raise Refusal(problem.get("code", "refused"), problem.get("reason", str(answer)),
                      run.returncode or EXIT_REFUSED)
    return answer
