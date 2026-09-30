#!/usr/bin/env python3
"""Detached helper of the H-2 move: cut the worktree, then type `/cd <path>` into the pane.

    afk-move.py --repo <main root> --name <name> --session <id> --provider <name> [--pane <id>] [--cwd <dir>]
                [--marker <file>]

The guard starts this and refuses at once, naming the path it will create. Outside a
terminal workspace (no `--pane`) it only creates; the refusal already printed the `/cd` line.
Inside one it waits for the agent to be idle and reads the pane: it types the unquoted
line only when the composer is empty or holds the helper's own earlier `/cd` line, then
reads the pane back. A refusal message from the harness means try again (up to 3 times,
about 2 minutes); silence, an unreadable pane or a composer with the human's text means
stop, never type twice. The outcome goes into `--marker`: `created` or `error`.
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
COMPOSER = re.compile(r"^\s*[›>❯]\s?(.*?)\s*$")
ATTEMPTS, WAIT_IDLE, SETTLE = 3, 40.0, 2.0


def bash() -> str | None:
    spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found = module.find_bash()
    return str(found) if found else shutil.which("bash")


def create(args) -> tuple[Path | None, str]:
    """`(the created path, "")` or `(None, why it failed)`."""
    shell = bash()
    if shell is None:
        return None, "no POSIX shell to run create-worktree"
    env = dict(os.environ, AFK_PLUGIN_ROOT=str(PLUGIN_ROOT), AFK_PROVIDER=args.provider)
    done = subprocess.run([shell, (HERE / "create-worktree").as_posix(), "--repo", Path(args.repo).as_posix(),
                           "--name", args.name, "--session", args.session], capture_output=True, text=True,
                          cwd=args.cwd or args.repo, env=env, timeout=900)
    found = re.findall(r"^WORKTREE_PATH=(.+)$", done.stdout, re.M)
    if done.returncode == 0 and found:
        return Path(found[-1].strip()), ""
    failed = re.findall(r"^ERROR=(.+)$", done.stderr, re.M)
    return None, (failed[-1] if failed else done.stderr.strip()[-300:] or "create-worktree made no worktree")


def record(marker: str, **outcome: str) -> None:
    """Write the creation outcome into the pane's move marker."""
    if not marker:
        return
    try:
        target = Path(marker)
        body = json.loads(target.read_text(encoding="utf-8"))
        body.pop("error", None)
        body.update(outcome)
        target.write_text(json.dumps(body), encoding="utf-8")
    except (OSError, ValueError):
        pass


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


def read_pane(binary: str, pane: str) -> str:
    return subprocess.run([binary, "agent", "read", pane, "--lines", "40"], capture_output=True,
                          text=True, timeout=30).stdout


def composer_text(seen: str) -> str | None:
    """The text after the last prompt glyph in the pane, or None when no composer line shows."""
    for line in reversed(seen.splitlines()):
        found = COMPOSER.match(line)
        if found:
            return found.group(1)
    return None


def type_line(binary: str, pane: str, path: Path) -> None:
    """Type `/cd <path>` until the harness confirms it or refuses for good."""
    for _ in range(ATTEMPTS):
        if not idle(binary, pane):
            continue
        text = composer_text(read_pane(binary, pane))
        if text is None:
            return  # an unreadable pane may hold the human's half-written message
        if text and not text.startswith("/cd "):
            return  # the human is typing: the refusal already printed the line
        if text:
            subprocess.run([binary, "agent", "send-keys", pane, "ctrl+u"], capture_output=True, timeout=30)
        subprocess.run([binary, "agent", "prompt", pane, f"/cd {path}"], capture_output=True, timeout=30)
        time.sleep(SETTLE)
        seen = read_pane(binary, pane)
        if DONE.search(seen) or not REFUSED.search(seen):
            return


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    for flag in ("repo", "name", "session", "provider", "pane", "cwd", "marker"):
        parser.add_argument(f"--{flag}", default="")
    args = parser.parse_args(argv)
    path, error = create(args)
    record(args.marker, **({"created": str(path)} if path is not None else {"error": error}))
    binary = os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr")
    if path is not None and args.pane and binary:
        type_line(binary, args.pane, path)
    return 0 if path is not None else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
