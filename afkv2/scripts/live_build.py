"""Prove the live build of a repository: start it, wait for an HTTP answer, stop it.

Command: `live_build.py prove|check [--start DIR] [--live JSON]`. `prove` writes the proven `live` block
into `.afkv2/config.json`; `check` writes nothing. Exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import signal
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import IO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from afkv2_config import Refusal, exit_code, live_block, read_config  # noqa: E402

POLL_SECONDS = 0.25
PROBE_SECONDS = 2
STOP_SECONDS = 15
GIT_SECONDS = 60
OUTPUT_TAIL = 800


@dataclass
class LiveHandle:
    repo_root: Path
    live: dict
    process: subprocess.Popen
    output: IO[bytes]


def prove(repo_root, live: dict | None = None) -> dict:
    """Prove the build, then write the block with `proven_at` and `proven_head`. Nothing is written on a refusal."""
    try:
        config_file, block = _block(repo_root, live)
        _prove(config_file.parent.parent, block)
        block = {**block, "proven_at": date.today().isoformat(), "proven_head": _head(config_file.parent.parent)}
        _write(config_file, block)
        return {"ok": True, "live": block}
    except Refusal as refusal:
        return _refused(refusal)


def check(repo_root, live: dict | None = None) -> dict:
    """The proof of `prove`, with no write."""
    try:
        config_file, block = _block(repo_root, live)
        _prove(config_file.parent.parent, block)
        return {"ok": True, "live": block}
    except Refusal as refusal:
        return _refused(refusal)


def start_live(repo_root, live: dict | None = None) -> LiveHandle:
    """Start the build and wait for its first answer. Raises `Refusal`; a refused start leaves no process."""
    config_file, block = _block(repo_root, live)
    root = config_file.parent.parent
    if _answers(block["address"]):
        raise Refusal("live-start-failed", f"{block['address']} already answers before the start: another server holds it")
    output = tempfile.TemporaryFile()
    process = subprocess.Popen(block["start"], shell=True, cwd=root, stdin=subprocess.DEVNULL, stdout=output,
                               stderr=subprocess.STDOUT, **_group())
    handle = LiveHandle(root, block, process, output)
    try:
        _wait_ready(handle)
    except BaseException:
        _kill_tree(process)
        output.close()
        raise
    return handle


def stop_live(handle: LiveHandle) -> None:
    """Stop what `start_live` began: the `stop` command, else the process tree. Any process left is then killed."""
    try:
        failure = _run_stop(handle) if handle.live["stop"] else None
        _kill_tree(handle.process)
        if failure is None and not _gone(handle):
            failure = f"{handle.live['address']} still answers after the stop"
        if failure:
            raise Refusal("live-stop-failed", failure)
    finally:
        _kill_tree(handle.process)
        handle.output.close()


def _run_stop(handle: LiveHandle) -> str | None:
    """Run the stop command in its own process group. A run past STOP_SECONDS is killed with its tree."""
    with tempfile.TemporaryFile() as output:
        stop = subprocess.Popen(handle.live["stop"], shell=True, cwd=handle.repo_root, stdin=subprocess.DEVNULL,
                                stdout=output, stderr=subprocess.STDOUT, **_group())
        try:
            code = stop.wait(timeout=STOP_SECONDS)
        except subprocess.TimeoutExpired:
            _kill_tree(stop)
            return f"the stop command ran past {STOP_SECONDS} s"
        if code != 0:
            return f"the stop command exited {code}: {_read_tail(output)}"
    _wait_exit(handle.process, STOP_SECONDS)
    return None


def _prove(repo_root: Path, block: dict) -> None:
    stop_live(start_live(repo_root, block))


def _block(repo_root, live: dict | None) -> tuple[Path, dict]:
    config = read_config(repo_root, with_live=live is None)
    if not config["ok"]:
        raise Refusal(config["error"]["code"], config["error"]["reason"])
    if live is not None:
        return Path(config["config_file"]), live_block(live)
    if "live" not in config:
        raise Refusal("live-undefined", f"{config['config_file']} has no live block")
    return Path(config["config_file"]), config["live"]


def _wait_ready(handle: LiveHandle) -> None:
    deadline = time.monotonic() + handle.live["ready_seconds"]
    while True:
        if _answers(handle.live["address"]):
            return
        code = handle.process.poll()
        if code is not None:
            raise Refusal("live-start-failed", f"the start exited {code} before an answer: {_read_tail(handle.output)}")
        if time.monotonic() >= deadline:
            raise Refusal("live-no-answer", f"no HTTP answer at {handle.live['address']} in {handle.live['ready_seconds']} s")
        time.sleep(POLL_SECONDS)


def _answers(address: str) -> bool:
    """Any HTTP answer, an error status too, counts. The probe skips proxies and does not check a certificate:
    it asks only whether the build serves."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                         urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    try:
        with opener.open(address, timeout=PROBE_SECONDS):
            return True
    except urllib.error.HTTPError:
        return True
    except (OSError, ValueError, http.client.HTTPException):
        return False


def _gone(handle: LiveHandle) -> bool:
    deadline = time.monotonic() + STOP_SECONDS
    while _answers(handle.live["address"]):
        if time.monotonic() >= deadline:
            return False
        time.sleep(POLL_SECONDS)
    return True


def _group() -> dict:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _kill_tree(process: subprocess.Popen) -> None:
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=STOP_SECONDS)
        except subprocess.TimeoutExpired:
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    _wait_exit(process, STOP_SECONDS)


def _wait_exit(process: subprocess.Popen, seconds: float) -> None:
    try:
        process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        pass


def _head(repo_root: Path) -> str:
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=GIT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Refusal("git-failed", f"git rev-parse HEAD: {error}") from None
    if done.returncode != 0:
        raise Refusal("git-failed", f"git rev-parse HEAD: {done.stderr.strip()}")
    return done.stdout.strip()


def _write(config_file: Path, block: dict) -> None:
    temporary = config_file.with_suffix(".tmp")
    try:
        raw = json.loads(config_file.read_text(encoding="utf-8"))
        raw["live"] = block
        temporary.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, config_file)
    except (OSError, ValueError) as error:
        temporary.unlink(missing_ok=True)
        raise Refusal("config-write-failed", f"{config_file}: {error}") from None


def _read_tail(output: IO[bytes]) -> str:
    """The last OUTPUT_TAIL characters of the output file, read from near its end only."""
    size = output.seek(0, os.SEEK_END)
    output.seek(max(0, size - OUTPUT_TAIL * 4))
    return output.read().decode("utf-8", "replace").strip()[-OUTPUT_TAIL:]


def _refused(refusal: Refusal) -> dict:
    return {"ok": False, "error": {"code": refusal.code, "reason": refusal.reason}}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise Refusal("usage", message)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(prog="live_build.py", add_help=False)
    parser.add_argument("verb", choices=["prove", "check"])
    parser.add_argument("--start", default=None)
    parser.add_argument("--live", default=None)
    try:
        args = parser.parse_args(argv)
        try:
            live = None if args.live is None else json.loads(args.live)
        except json.JSONDecodeError as error:
            raise Refusal("usage", f"--live: {error}") from None
        answer = (prove if args.verb == "prove" else check)(Path(args.start or os.getcwd()), live)
    except Refusal as refusal:
        answer = _refused(refusal)
    print(json.dumps(answer))
    return exit_code(answer)


if __name__ == "__main__":
    sys.exit(main())
