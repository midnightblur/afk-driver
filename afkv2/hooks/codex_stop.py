"""Codex Stop hook: when this session has a page waiting, wait for the answer and hand it back.

No record: no output. Answer: `{"decision": "block", "reason": <raw response>}`. No answer within
the wait: a warning that names the fallback, no block. This hook never fails the agent's stop.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
for folder in (PLUGIN_ROOT / "scripts", PLUGIN_ROOT / "engine"):
    sys.path.insert(0, str(folder))

from afkv2_config import Refusal, data_folder  # noqa: E402

import launcher  # noqa: E402

WAIT_SECONDS = 3600
SLICE_MS = 60_000
RETRY_SECONDS = 5
FALLBACK = "After you send the page, write one chat message; the agent then polls the page."


def wait_for_answer(page: str, timeout_s: float = WAIT_SECONDS, poll=launcher.poll_status,
                    sleep=time.sleep, clock=time.monotonic) -> tuple[str, str]:
    """`(status, raw)`: status is feedback, or the reason the wait ended with no answer.

    Each poll is one slice: a host poll with a time limit sends no bytes until it answers, and
    the client gives up on a silent request after 300 s (inferred from the Node default).
    """
    deadline = clock() + timeout_s
    while True:
        remaining_ms = int((deadline - clock()) * 1000)
        if remaining_ms <= 0:
            return "timeout", ""
        status, detail = poll(["poll", page, "--timeout-ms", str(min(remaining_ms, SLICE_MS))])
        if status == "feedback":
            return status, detail["raw"]
        if status in ("ended", "fallback", "no-session"):
            return status, ""
        if status != "waiting":
            sleep(RETRY_SECONDS)


def main(stdin: str) -> str | None:
    """The hook's stdout, or None for no output."""
    try:
        event = json.loads(stdin)
        session = event["session_id"]
        folder = data_folder()
    except (ValueError, KeyError, TypeError, Refusal):
        return None
    record = launcher.read_waiting_record(folder, session)
    if record is None:
        return None
    status, raw = wait_for_answer(record["page"])
    launcher.clear_waiting_record(folder, session)
    if status == "feedback":
        return json.dumps({"decision": "block", "reason": raw})
    return json.dumps({"systemMessage": f"The page got no answer ({status}). {FALLBACK}"})


if __name__ == "__main__":
    try:
        output = main(sys.stdin.buffer.read().decode("utf-8", "replace"))
    except Exception as problem:  # the hook must not turn an engine fault into a failed stop
        output = json.dumps({"systemMessage": f"The page wait failed: {problem}. {FALLBACK}"})
    if output is not None:
        sys.stdout.write(output)
    sys.exit(0)
