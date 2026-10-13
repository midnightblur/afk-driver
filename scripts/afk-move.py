#!/usr/bin/env afk-python
"""Detached helper of the H-2 move: cut the worktree, then type `/cd <path>` into the pane.

    afk-move.py --repo <main root> --name <name> --session <id> --provider <name> [--pane <id>] [--cwd <dir>]
                [--marker <file>]

The guard starts this and refuses at once, naming the path it will create. Outside a
terminal workspace (no `--pane`) it only creates; the refusal already printed the `/cd` line.
Inside one it first proves the pane is the refused session's own agent (kind, session id,
cwd; an agent started from another agent's pane inherits its pane id), waits for it to be
idle, proves it again, and reads the pane: it types the unquoted
line only when the composer is empty or holds the helper's own earlier `/cd` line, then
reads the pane back. The wait for idle lasts up to 10 minutes per attempt: the agent may
still be answering the refusal. A refusal message from the harness means try again (up to 3
times); silence, an unreadable pane or a composer with the human's text means stop, never
type twice. The outcome goes into `--marker`: `created` or `error`. Every step, wait result
and exception goes to `<git dir>/afk-worktrees/<name>.log`, never a token.
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
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
SGR = re.compile(r"\x1b\[[0-9;]*m")
DIM = re.compile(r"^(?:\x1b\[0?m| )*\x1b\[2m")
UI: dict = {}  # the harness's move_ui facts, from hooks/lib/providers/<provider>.json
DONE = REFUSED = COMPOSER = GLYPH = None
ATTEMPTS, WAIT_IDLE, SETTLE = 3, 600.0, 2.0
LOG: Path | None = None
WHO: dict = {}  # the refused session: provider name, session id, main checkout path


def configure(provider: str) -> bool:
    """Load the provider's `move_ui` facts (typed command, outcome patterns, prompt glyphs)."""
    global UI, DONE, REFUSED, COMPOSER, GLYPH
    try:
        name = re.sub(r"[^a-z0-9_-]", "", provider.lower())
        ui = json.loads((PLUGIN_ROOT / "hooks" / "lib" / "providers" / f"{name}.json")
                        .read_text(encoding="utf-8"))["move_ui"]
        glyphs = f"[{re.escape(ui['prompt_glyphs'])}]"
        DONE, REFUSED = re.compile(ui["done"], re.I), re.compile(ui["refused"], re.I)
        GLYPH, COMPOSER = re.compile(glyphs), re.compile(rf"^\s*{glyphs}\s?(.*?)\s*$")
        UI = ui
    except (OSError, ValueError, KeyError, TypeError, re.error):
        UI = {}
    return bool(UI)


def typed_line(path: Path) -> str:
    return UI["command"].format(path=path)


def line_prefix() -> str:
    """The head of the typed line before the path: how the helper recognises its own earlier line."""
    return UI["command"].partition("{path}")[0]


def log(message: str) -> None:
    """Append one timestamped line to this move's log; logging never fails the move."""
    if LOG is None:
        return
    try:
        with open(LOG, "a", encoding="utf-8") as out:
            out.write(f"{time.strftime('%H:%M:%S')} {message}\n")
    except OSError:
        pass


def log_path(repo: str, name: str) -> Path | None:
    """`<git dir>/afk-worktrees/<name>.log`, beside the owner records."""
    try:
        done = subprocess.run(["git", "-C", repo, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                              capture_output=True, encoding="utf-8", errors="replace", timeout=30)
        if done.returncode != 0 or not done.stdout.strip():
            return None
        folder = Path(done.stdout.strip()) / "afk-worktrees"
        folder.mkdir(exist_ok=True)
        (folder / f"{name}.log").write_text("", encoding="utf-8")  # one move per log
        return folder / f"{name}.log"
    except (OSError, subprocess.SubprocessError):
        return None


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
                           "--name", args.name, "--session", args.session], capture_output=True, encoding="utf-8", errors="replace",
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
    done = subprocess.run([binary, *argv], capture_output=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        return json.loads(done.stdout or "")  # None or empty output is no answer
    except (ValueError, TypeError):
        return None


def idle(binary: str, pane: str) -> bool:
    deadline = time.monotonic() + WAIT_IDLE
    last = None
    while time.monotonic() < deadline:
        answer = herdr_json(binary, "agent", "get", pane) or {}
        status = ((answer.get("result") or {}).get("agent") or {}).get("agent_status")
        if status != last:
            log(f"wait: agent status {status!r}")
            last = status
        if status in ("idle", "done"):
            return True
        time.sleep(1.0)
    log(f"wait: gave up after {WAIT_IDLE:.0f}s, last status {last!r}")
    return False


def read_pane(binary: str, pane: str, fmt: str = "text") -> str:
    return subprocess.run([binary, "agent", "read", pane, "--lines", "40", "--format", fmt],
                          capture_output=True, encoding="utf-8", errors="replace", timeout=30).stdout


def composer_text(seen: str) -> str | None:
    """The human's text after the last prompt glyph, "" for an empty composer, None when none shows.

    The harness paints its empty-composer placeholder dim (SGR 2); typed text is plain, so a
    dim line reads as empty. `seen` is an ANSI read.
    """
    for line in reversed(seen.splitlines()):
        found = COMPOSER.match(SGR.sub("", line))
        if found:
            after = line[GLYPH.search(line).end():]
            return "" if DIM.match(after) else found.group(1)
    return None


def same_dir(a: str, b: str) -> bool:
    def norm(text: str) -> str:
        return os.path.normcase(os.path.normpath(text.removeprefix("\\\\?\\"))) if text else ""
    return bool(a) and norm(a) == norm(b)


def owns_pane(binary: str, pane: str) -> bool:
    """Is `pane` the refused session's own agent? A pane that cannot be proven theirs gets no typing.

    An agent started inside another agent's pane inherits that pane's id, so the id alone proves
    nothing: the pane's agent kind, a reported session id and cwd must all match. A pane herdr
    reports no session for gets nothing typed; the refusal already printed the line.
    """
    agent = ((herdr_json(binary, "agent", "get", pane) or {}).get("result") or {}).get("agent") or {}
    kind = str(agent.get("agent") or "")
    seen = str((agent.get("agent_session") or {}).get("value") or "")
    cwd = str(agent.get("cwd") or "")
    ok = (kind == WHO.get("provider") and bool(seen) and seen == WHO.get("session")
          and same_dir(cwd, WHO.get("cwd", "")))
    if kind == WHO.get("provider") and not seen:
        log(f"herdr reports no session for pane {pane}; install herdr's integration for {kind} to get the line typed")
    if not ok:
        log(f"pane {pane} belongs to another agent ({kind or '?'}/{seen or '?'}/{cwd or '?'}): nothing typed")
    return ok


def type_line(binary: str, pane: str, path: Path) -> None:
    """Type the provider's move line until the harness confirms it or refuses for good."""
    if not UI:
        log("stop: no move_ui facts for this provider")
        return
    for attempt in range(1, ATTEMPTS + 1):
        if not owns_pane(binary, pane):
            return
        log(f"attempt {attempt}: waiting for pane {pane} to be idle")
        if not idle(binary, pane):
            continue
        if not owns_pane(binary, pane):
            return  # the pane's agent changed during the wait
        text = composer_text(read_pane(binary, pane, "ansi"))
        log("composer: " + ("no composer" if text is None else "empty" if not text
                            else "own move line" if text.startswith(line_prefix())
                            else f"human text ({len(text)} chars)"))
        if text is None:
            log("stop: no composer on screen")
            return  # an unreadable pane may hold the human's half-written message
        if text and not text.startswith(line_prefix()):
            log("stop: the human is typing")
            return  # the human is typing: the refusal already printed the line
        if text:
            subprocess.run([binary, "agent", "send-keys", pane, "ctrl+u"], capture_output=True, timeout=30)
        subprocess.run([binary, "agent", "prompt", pane, typed_line(path)], capture_output=True, timeout=30)
        time.sleep(SETTLE)
        seen = read_pane(binary, pane)
        if DONE.search(seen) or not REFUSED.search(seen):
            log("done: typed, no refusal after it")
            return
        log("refused: trying again")
    log("stop: attempts used up")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    for flag in ("repo", "name", "session", "provider", "pane", "cwd", "marker"):
        parser.add_argument(f"--{flag}", default="")
    args = parser.parse_args(argv)
    global LOG
    LOG = log_path(args.repo, args.name)
    configure(args.provider)
    WHO.update(provider=args.provider, session=args.session, cwd=args.cwd or args.repo)
    try:
        return run(args)
    except BaseException:
        log("exception:\n" + traceback.format_exc())
        raise
    finally:
        log("exit")


def run(args) -> int:
    binary = os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr")
    log(f"start: pid {os.getpid()} pane {args.pane!r} herdr {binary!r} provider {args.provider!r}")
    path, error = create(args)
    log(f"create: {path}" if path is not None else f"create failed: {error}")
    record(args.marker, **({"created": str(path)} if path is not None else {"error": error}))
    if path is not None and args.pane and binary:
        type_line(binary, args.pane, path)
    elif path is not None:
        log("no pane or no herdr binary: nothing typed")
    return 0 if path is not None else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
