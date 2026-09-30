#!/usr/bin/env python3
"""Detached helper of the H-2 move: cut the worktree, then type `/cd <path>` into the pane.

    afk-move.py --repo <main root> --name <name> --session <id> --provider <name> [--pane <id>] [--cwd <dir>]

The guard starts this and refuses at once, naming the path it will create. Outside a
terminal workspace (no `--pane`) it only creates; the refusal already printed the `/cd` line.
Inside one it waits for the agent to be idle, clears the composer, types the unquoted
line, and reads the pane back: a refusal message from the harness means try again (up to
3 times, about 2 minutes); silence or an unreadable pane means stop, never type twice.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
DONE = re.compile(r"Working directory changed", re.I)
REFUSED = re.compile(r"disabled while a task|Cannot access directory|not trusted|background terminal", re.I)
ATTEMPTS, WAIT_IDLE, SETTLE = 3, 40.0, 2.0


def bash() -> str | None:
    spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found = module.find_bash()
    return str(found) if found else shutil.which("bash")


def create(args) -> Path | None:
    shell = bash()
    if shell is None:
        return None
    env = dict(os.environ, AFK_PLUGIN_ROOT=str(PLUGIN_ROOT), AFK_PROVIDER=args.provider)
    done = subprocess.run([shell, (HERE / "create-worktree").as_posix(), "--repo", Path(args.repo).as_posix(),
                           "--name", args.name, "--session", args.session], capture_output=True, text=True,
                          cwd=args.cwd or args.repo, env=env, timeout=900)
    found = re.findall(r"^WORKTREE_PATH=(.+)$", done.stdout, re.M)
    return Path(found[-1].strip()) if done.returncode == 0 and found else None


def herdr_json(binary: str, *argv: str):
    done = subprocess.run([binary, *argv], capture_output=True, text=True, timeout=30)
    try:
        return json.loads(done.stdout)
    except ValueError:
        return None


def idle(binary: str, pane: str) -> bool:
    deadline = time.monotonic() + WAIT_IDLE
    while time.monotonic() < deadline:
        answer = herdr_json(binary, "agent", "get", pane) or {}
        status = ((answer.get("result") or {}).get("agent") or {}).get("agent_status")
        if status in ("idle", "done"):
            return True
        time.sleep(1.0)
    return False


def type_line(binary: str, pane: str, path: Path) -> None:
    """Type `/cd <path>` until the harness confirms it or refuses for good."""
    for _ in range(ATTEMPTS):
        if not idle(binary, pane):
            continue
        subprocess.run([binary, "agent", "send-keys", pane, "ctrl+u"], capture_output=True, timeout=30)
        subprocess.run([binary, "agent", "prompt", pane, f"/cd {path}"], capture_output=True, timeout=30)
        time.sleep(SETTLE)
        seen = subprocess.run([binary, "agent", "read", pane, "--lines", "40"], capture_output=True,
                              text=True, timeout=30).stdout
        if DONE.search(seen) or not REFUSED.search(seen):
            return


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    for flag in ("repo", "name", "session", "provider", "pane", "cwd"):
        parser.add_argument(f"--{flag}", default="")
    args = parser.parse_args(argv)
    path = create(args)
    binary = os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr")
    if path is not None and args.pane and binary:
        type_line(binary, args.pane, path)
    return 0 if path is not None else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
