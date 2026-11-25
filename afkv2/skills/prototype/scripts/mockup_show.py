"""A mockup in lavish, through the launcher: a page with no page document (SDD §3; ADR-0003 of ticket 207).

`mockup_show.py show --mockup FILE`: opens the file itself with `--plain` and answers `url`; on Codex
  (`CODEX_THREAD_ID` set) it writes the waiting record with a null document. Refuses `no-host` when the launcher runs no
  host (lavish missing, at another version, or `LAVISH_AXI_HOST` set); its reason holds the `file://` path.
`mockup_show.py wait --mockup FILE --notes-file NOTES`: one host poll; writes each note to NOTES as
  `{uid, prompt, selector, tag, text}` and answers `count` and `ended`; a closed page or browser writes no
  note and answers `ended`. Refuses `no-session`, and `no-host` as show does.
`mockup_show.py reply --mockup FILE --reply-file REPLY`: shows REPLY (Markdown) on the open mockup. Refuses
  `no-session`.
`mockup_show.py end --mockup FILE`: ends the session and clears the waiting record. Never refuses on the host.

Each answer is one JSON object; exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
PLUGIN = SKILL.parents[1]
sys.path.insert(0, str(SKILL.parent / "use-lavish" / "scripts"))
sys.path.insert(0, str(PLUGIN / "engine"))
sys.path.insert(0, str(PLUGIN / "scripts"))

import launcher  # noqa: E402
from afkv2_config import data_folder  # noqa: E402
from grill_common import Parser, Refusal, serve  # noqa: E402
from shell import inject  # noqa: E402

THREAD_VARIABLE = "CODEX_THREAD_ID"
ENDED = ("ended", "browser_disconnected")  # the developer closed the page or the browser
NOTE_FIELDS = ("uid", "prompt", "selector", "tag", "text")  # lavish poll at 0.1.86 (SDD §9b)


def _mockup(path):
    page = Path(path)
    if not launcher.HTML.search(page.name) or not page.is_file():
        raise Refusal("unreadable", f"{path}: no .html mockup there", 2)
    return page


def _no_host(page, cause):
    """The refusal when the launcher runs no host: the developer opens the file itself and notes in chat."""
    uri = page.resolve().as_uri()
    return Refusal("no-host", f"lavish cannot show the mockup: {cause.strip()}. Give the developer {uri} and take "
                              "the notes in chat; /afkv2:setup fixes the install", file=uri)


def cmd_show(argv):
    """Open the mockup as it is: `--plain` writes no afkv2 runtime into the file."""
    parser = Parser(add_help=False)
    parser.add_argument("--mockup", required=True)
    args = parser.parse_args(argv)
    page = _mockup(args.mockup)
    code, out = launcher.run(["open", str(page), launcher.PLAIN_FLAG])
    if code in launcher.FALLBACK_EXITS:
        raise _no_host(page, out)
    if code != 0:
        raise Refusal("host-error", f"lavish open: exit {code}: {out.strip()}")
    session = launcher.parse_host_output(out).get("session") or {}
    record, thread = None, os.environ.get(THREAD_VARIABLE)
    if thread:  # Codex: the Stop hook waits on this record; a mockup has no page document
        record = str(launcher.write_waiting_record(data_folder(), thread, None, str(page)))
    return {"ok": True, "page": str(page), "url": session.get("url"), "status": session.get("status"),
            "waiting_record": record}


def cmd_wait(argv):
    """One host poll. The host hands a send over once, so the notes file is written before the answer."""
    parser = Parser(add_help=False)
    parser.add_argument("--mockup", required=True)
    parser.add_argument("--notes-file", required=True)
    args = parser.parse_args(argv)
    page = _mockup(args.mockup)
    status, detail = launcher.poll_status(["poll", str(page)])
    if status == "fallback":
        raise _no_host(page, detail["reason"])
    if status == "no-session":
        raise Refusal("no-session", f"no lavish session shows {page}; run show first")
    if status not in ("feedback", *ENDED):
        raise Refusal("host-error", f"lavish poll: {status}: {detail.get('reason')}")
    prompts = detail["prompts"] if status == "feedback" else []
    notes = [{field: prompt.get(field) for field in NOTE_FIELDS} for prompt in prompts]
    notes_file = Path(args.notes_file)
    notes_file.parent.mkdir(parents=True, exist_ok=True)
    inject.write_if_changed(notes_file, json.dumps(notes, indent=2, ensure_ascii=False).encode("utf-8"))
    _clear_waiting_record()
    return {"ok": True, "status": status, "count": len(notes),
            "ended": status in ENDED or detail["session_ended"],
            "notes_file": str(notes_file)}


def cmd_reply(argv):
    """Show a reply on the open mockup; the host returns once it takes the reply."""
    parser = Parser(add_help=False)
    parser.add_argument("--mockup", required=True)
    parser.add_argument("--reply-file", required=True)
    args = parser.parse_args(argv)
    page = _mockup(args.mockup)
    if not Path(args.reply_file).is_file():
        raise Refusal("unreadable", f"reply file {args.reply_file} does not exist", 2)
    code, out = launcher.run(["reply", str(page), "--agent-reply-file", str(args.reply_file)])
    if code in launcher.FALLBACK_EXITS:
        raise _no_host(page, out)
    if code != 0:
        parsed = launcher.parse_host_output(out)
        if parsed.get("code") == "NOT_FOUND":
            raise Refusal("no-session", f"no lavish session shows {page}; run show first")
        raise Refusal("host-error", f"lavish reply: exit {code}: {parsed.get('error') or out.strip()}")
    return {"ok": True}


def cmd_end(argv):
    """End the session and forget the Codex waiting record. Never refuses on the host: `host` says what it answered."""
    parser = Parser(add_help=False)
    parser.add_argument("--mockup", required=True)
    args = parser.parse_args(argv)
    page = _mockup(args.mockup)
    code, out = launcher.run(["end", str(page)])
    _clear_waiting_record()
    parsed = {} if code in launcher.FALLBACK_EXITS else launcher.parse_host_output(out)
    return {"ok": True, "ended": code == 0, "host": str(parsed.get("error") or out.strip())}


def _clear_waiting_record():
    thread = os.environ.get(THREAD_VARIABLE)
    if thread:
        launcher.clear_waiting_record(data_folder(), thread)


VERBS = {"show": cmd_show, "wait": cmd_wait, "reply": cmd_reply, "end": cmd_end}


def main(argv):
    return serve(_dispatch, argv)


def _dispatch(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", 2)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
