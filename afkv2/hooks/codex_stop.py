"""Codex Stop hook: when this session has a page waiting, wait for the answer and hand it back.

No record: no output. Answer: `{"decision": "block", "reason": <raw response>}`. No answer within
the wait: a warning that names the fallback, no block. This hook never fails the agent's stop.
Side questions from the page are asked in the Codex pane with `/side` (`side_question.py`); their
answers are not read until the owner's live check defines the markers, so the page says so.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
for folder in (PLUGIN_ROOT / "scripts", PLUGIN_ROOT / "engine"):
    sys.path.insert(0, str(folder))

from afkv2_config import Refusal, data_folder  # noqa: E402

import engine  # noqa: E402
import launcher  # noqa: E402
import prompt_lines  # noqa: E402

WAIT_SECONDS = 3600
SLICE_MS = 60_000
RETRY_SECONDS = 5
FALLBACK = "After you send the page, write one chat message; the agent then polls the page."
NO_PANE = "Not answered: Codex does not run in a herdr pane. Ask it in the Codex chat."


def _raw(detail: dict, document: str | None, round_prompts: list[dict], side: bool) -> str:
    """The raw response of the round's prompts, read against the page document; the joined text without one."""
    if document and round_prompts:
        try:
            return engine.poll_raw(document, round_prompts)
        except (Refusal, KeyError, TypeError, AttributeError, StopIteration):
            pass
    return "\n".join(str(p.get("prompt", "")) for p in round_prompts) if side else detail["raw"]


def _side_answers(questions: list[str], ask) -> str:
    """Markdown of the answers to the side questions, asked in the agent's Codex pane."""
    import side_question

    ask = ask or (lambda question: side_question.ask(question, harness="codex"))
    results = [ask(question) for question in questions]
    for result in results:
        if result["status"] == "unanswered":  # the agent never sees a side question from this hook
            result["answer"] = NO_PANE
    return side_question.reply_markdown(results)


def _reply_file(text: str) -> str:
    handle, path = tempfile.mkstemp(prefix="afkv2-btw-", suffix=".md")
    with os.fdopen(handle, "wb") as out:
        out.write(text.encode("utf-8"))
    return path


def wait_for_answer(page: str, timeout_s: float = WAIT_SECONDS, poll=launcher.poll_status,
                    sleep=time.sleep, clock=time.monotonic, document: str | None = None,
                    ask=None, reply=launcher.run) -> tuple[str, str]:
    """`(status, raw)`: status is feedback, or the reason the wait ended with no answer.

    Each poll is one slice: a host poll with a time limit sends no bytes until it answers, and
    the client gives up on a silent request after 300 s (inferred from the Node default).
    A send of side questions only is answered on the page and the wait goes on; the agent never
    sees it. A side question sent with the round is answered on the page before the round returns.
    A round send is kept beside the document until ingest (`engine.keep_delivery`); a kept send answers first.
    A send that ends the session with no round prompt is `ended`.
    """
    deadline = clock() + timeout_s
    pending = None
    keep = document is not None and Path(document).is_file()
    kept = engine.kept_delivery(document) if keep else None
    while True:
        remaining_ms = int((deadline - clock()) * 1000)
        if kept is not None:
            status, detail, kept = "feedback", kept, None
        elif remaining_ms <= 0:
            return "timeout", ""
        else:
            argv = ["poll", page, "--timeout-ms", str(min(remaining_ms, SLICE_MS))]
            status, detail = poll([*argv, "--agent-reply-file", pending] if pending else argv)
            if status == "feedback" and keep:
                engine.keep_delivery(document, detail)
        if pending:
            os.unlink(pending)
            pending = None
        if status == "feedback":
            round_prompts, questions = prompt_lines.split_side_questions(detail.get("prompts") or [])
            if not round_prompts and detail.get("session_ended"):
                return "ended", ""
            if questions:
                text = _side_answers(questions, ask)
                if not round_prompts and not detail.get("session_ended"):
                    pending = _reply_file(text)
                    continue
                shown = _reply_file(text)
                try:
                    reply(["reply", page, "--agent-reply-file", shown])
                finally:
                    os.unlink(shown)
            return status, _raw(detail, document, round_prompts, bool(questions))
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
    status, raw = wait_for_answer(record["page"], document=record.get("document"))
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
