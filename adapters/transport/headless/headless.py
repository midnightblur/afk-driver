"""Headless runs: the plugin starts the harness with no terminal, under an operating-system job.

The run takes its whole task at its start and writes its output to the `log` file the caller names; its
handle is its process id. It takes no message after the start and has no pane, so agent-send and agent-list
answer unsupported. Payloads and answers: CONTRACT.md beside this file.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import contract  # noqa: E402
import launch  # noqa: E402
import process  # noqa: E402
from contract import Payload, bad, unavailable, unsupported  # noqa: E402

READ_CAP = 1 << 20


def _status_path(log: str) -> Path:
    return Path(log + ".status.json")


def _read_status(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _spawn_owner(argv: list[str], env: dict[str, str]) -> None:
    if not process.WINDOWS:
        subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        return
    detached = 0x00000008 | 0x00000200          # DETACHED_PROCESS, CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True, creationflags=detached | 0x01000000)
    except OSError:     # the caller's job refuses breakaway: the owner's own job nests inside it
        subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True, creationflags=detached)


class Headless:
    def agent_start(self, p: Payload, deadline: contract.Deadline) -> dict:
        harness = p.choice("harness", launch.HARNESSES)
        prompt, cwd, log = p.text("prompt"), p.text("cwd"), p.text("log")
        model, effort = p.text("model", False), p.text("effort", False)
        args, extra = p.texts("args"), p.mapping("env")
        if not os.path.isdir(cwd):
            raise bad(p.verb, f"field `cwd`: {cwd} is not a folder")
        run = launch.headless(harness, prompt, model=model, effort=effort, args=args)
        binary = shutil.which(run.binary)
        if not binary:
            raise unavailable(f"`{run.binary}` is not on PATH, so no headless {harness} run can start")
        status = _status_path(log)
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        status.unlink(missing_ok=True)
        env = {**os.environ, **run.env, **extra}
        _spawn_owner([sys.executable, str(HERE / "job.py"), "--status", str(status), "--log", log,
                      "--cwd", cwd, "--", binary, *run.args], env)
        end = time.monotonic() + min(15.0, deadline.left())
        state = _read_status(status)
        while (state is None or ("pid" not in state and "error" not in state)) and time.monotonic() < end:
            time.sleep(0.1)
            state = _read_status(status)
        if not state or "pid" not in state:
            raise unavailable((state or {}).get("error") or "the run's job owner reported no process in time")
        pid = state["pid"]
        return {"kind": "headless", "handle": str(pid), "pid": pid,
                "started_at": state.get("started_at") or process.creation_time(pid) or contract.now(),
                "session_id": "", "log": log}

    def agent_send(self, p: Payload, deadline: contract.Deadline) -> dict:
        raise unsupported("a headless run takes its whole task at its start and no message after it")

    def agent_status(self, p: Payload, deadline: contract.Deadline) -> dict:
        pid = p.integer("pid")
        if process.alive(pid):
            return {"alive": True, "state": "running", "since": process.creation_time(pid)}
        log = p.text("log", False)
        state = _read_status(_status_path(log)) if log else None
        since = None
        if log and _status_path(log).exists():
            since = time.strftime(contract.TIME_FORMAT, time.gmtime(_status_path(log).stat().st_mtime))
        return {"alive": False, "state": "exited", "since": since,
                "exit_code": (state or {}).get("exit_code")}

    def agent_read(self, p: Payload, deadline: contract.Deadline) -> dict:
        log = p.text("log")
        marker = p.text("since_marker", False) or "0"
        if not marker.isdigit():
            raise bad(p.verb, f"field `since_marker`: {marker!r} is not a marker this kind gave")
        offset = int(marker)
        try:
            size = os.path.getsize(log)
        except OSError:
            raise bad(p.verb, f"field `log`: {log} cannot be read") from None
        if offset > size:
            raise bad(p.verb, f"field `since_marker`: {offset} is past the end of the output")
        with open(log, "rb") as handle:
            handle.seek(offset)
            chunk = handle.read(READ_CAP)
        end = offset + len(chunk)
        return {"text": chunk.decode("utf-8", "replace"), "marker": str(end), "complete": end >= size}

    def agent_stop(self, p: Payload, deadline: contract.Deadline) -> dict:
        pid, force = p.integer("pid", False), p.boolean("force")
        if pid is None:
            return {"stopped": True, "method": "no process id given"}
        if not process.alive(pid):
            return {"stopped": True, "method": "not running"}
        survivors = process.kill_tree(pid, force=force, wait_s=min(20.0, deadline.left()))
        if survivors:
            return {"stopped": False, "reason": f"{len(survivors)} processes survived the kill",
                    "survivors": survivors}
        return {"stopped": True, "method": "killed the process tree"}

    def agent_list(self, p: Payload, deadline: contract.Deadline) -> dict:
        raise unsupported("a headless run has no pane id to list it by")


if __name__ == "__main__":
    sys.exit(contract.run(Headless(), sys.argv[1:]))
