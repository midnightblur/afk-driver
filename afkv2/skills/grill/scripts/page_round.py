"""Drive one page round through the engine verbs (SDD §3), from the repository root.

  present --doc D                 check, render, show, in that order; stops at the first refusal.
                                  It records the round before show: after a failed show, chat shows the round.
  wait    --doc D --raw-file F    poll; writes the raw response to F, byte for byte, and the host's prompts
                                  to F.prompts.json, for audit. Answers side questions on the page and polls
                                  again; `btw` lists the side questions left to the agent, and `raw_file`
                                  is null when the send held no round answer
  reply   --doc D --reply-file F  shows the Markdown in F on the page
  ingest  --doc D --raw-file F    ingest; deletes F, F.prompts.json and the shown record; answers what the
                                  round pass must read

The raw text waits in a file because the document holds it only after ingest. Poll has no time
limit here: it returns when the human sends the round.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from grill_common import PLUGIN_ROOT, Parser, Refusal, read_json, run_command, serve
from round_document import pending, record_shown, shown_record

ENGINE = PLUGIN_ROOT / "engine" / "engine.py"
TIMEOUT_S = 120


def _engine(verb, doc, *args, timeout=TIMEOUT_S):
    try:
        return run_command(ENGINE, [verb, str(doc), *args], timeout)
    except Refusal as refusal:
        raise Refusal(refusal.code, refusal.reason, refusal.exit_code, verb=verb) from refusal


def present(doc):
    _engine("check", doc)
    page = _engine("render", doc).get("page")
    record_shown(doc)
    _engine("show", doc)
    return {"ok": True, "page": page}


def _side_question():
    """The side-question module of the engine, loaded only when a send holds a side question."""
    folder = str(PLUGIN_ROOT / "engine")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import side_question
    return side_question


def _answer_side_questions(questions):
    """(Markdown of the answered questions, the questions left to the agent)."""
    if not questions:
        return "", []
    module = _side_question()
    results = [module.ask(question) for question in questions]
    shown = [r for r in results if r["status"] != "unanswered"]
    return module.reply_markdown(shown), [r["question"] for r in results if r["status"] == "unanswered"]


def reply_file_of(raw_file):
    return Path(f"{raw_file}.reply.md")


def _write_reply(raw_file, text):
    path = reply_file_of(raw_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def wait(doc, raw_file):
    """Poll until the human sends the round. A send of side questions only is answered here, on the page,
    and the wait goes on. A side question with no terminal to ask in returns to the agent in `btw`."""
    pending = None
    while True:
        answer = _engine("poll", doc, *(["--reply-file", str(pending)] if pending else []), timeout=None)
        if pending:
            pending.unlink(missing_ok=True)
            pending = None
        raw = answer.get("raw")
        if not isinstance(raw, str):
            raise Refusal("bad-answer", f"poll answered no `raw` text; its fields: {sorted(answer)}", verb="poll")
        questions = answer.get("btw") or []
        text, left = _answer_side_questions(questions)
        side_only = bool(questions) and answer.get("round_prompts") == 0 and not answer.get("session_ended")
        if side_only and not left:
            pending = _write_reply(raw_file, text)
            continue
        if text:
            left = _show_reply(doc, raw_file, text, questions, left)
        if side_only:
            return {"ok": True, "raw_file": None, "btw": left}
        return {**_write_raw(raw_file, raw, answer), "btw": left}


def _show_reply(doc, raw_file, text, questions, left):
    """Show the answers on the page; when the page refuses, every question goes back to the agent."""
    path = _write_reply(raw_file, text)
    try:
        _engine("reply", doc, "--reply-file", str(path))
    except Refusal:
        return list(questions)
    finally:
        path.unlink(missing_ok=True)
    return left


def _write_raw(raw_file, raw, answer):
    path = Path(raw_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw.encode("utf-8"))
    prompts = prompts_file(raw_file)
    prompts.write_text(json.dumps(answer.get("prompts") or [], indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "raw_file": raw_file, "bytes": path.stat().st_size, "prompts_file": str(prompts)}


def reply(doc, reply_file):
    if not Path(reply_file).is_file():
        raise Refusal("unreadable", f"no reply at {reply_file}", 2, verb="reply")
    _engine("reply", doc, "--reply-file", reply_file)
    return {"ok": True}


def prompts_file(raw_file):
    """The host's prompts of one answer, beside its raw file: the audit of how the raw text was built."""
    return Path(f"{raw_file}.prompts.json")


def ingest(doc, raw_file):
    if not Path(raw_file).is_file():
        raise Refusal("unreadable", f"no raw response at {raw_file}", 2, verb="ingest")
    _engine("ingest", doc, "--raw-file", raw_file)
    Path(raw_file).unlink()
    prompts_file(raw_file).unlink(missing_ok=True)
    shown_record(doc).unlink(missing_ok=True)
    return {"ok": True, **pending(read_json(doc))}


def main(argv):
    parser = Parser(add_help=False)
    parser.add_argument("verb", choices=["present", "wait", "ingest", "reply"])
    parser.add_argument("--doc", required=True)
    parser.add_argument("--raw-file")
    parser.add_argument("--reply-file")
    args = parser.parse_args(argv)
    if args.verb == "present":
        return present(args.doc)
    if args.verb == "reply":
        if not args.reply_file:
            raise Refusal("usage", "reply needs --reply-file", 2)
        return reply(args.doc, args.reply_file)
    if not args.raw_file:
        raise Refusal("usage", f"{args.verb} needs --raw-file", 2)
    return wait(args.doc, args.raw_file) if args.verb == "wait" else ingest(args.doc, args.raw_file)


if __name__ == "__main__":
    sys.exit(serve(main))
