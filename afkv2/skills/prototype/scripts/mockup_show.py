"""A mockup in lavish, through the launcher: a page with no page document (SDD §3; ADR-0003 of ticket 207).

`mockup_show.py show --mockup FILE`: opens the file itself with `--plain` and answers `url`; on Codex
  (`CODEX_THREAD_ID` set) it writes the waiting record with a null document.
`mockup_show.py wait --mockup FILE --notes-file NOTES`: one host poll; writes each note to NOTES as
  `{uid, prompt, selector, tag, text}` and answers `count` and `ended`. Refuses `no-session`.

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
NOTE_FIELDS = ("uid", "prompt", "selector", "tag", "text")  # lavish poll at 0.1.86 (SDD §9b)


def _mockup(path):
    page = Path(path)
    if not launcher.HTML.search(page.name) or not page.is_file():
        raise Refusal("unreadable", f"{path}: no .html mockup there", 2)
    return page


def cmd_show(argv):
    """Open the mockup as it is: `--plain` writes no afkv2 runtime into the file."""
    parser = Parser(add_help=False)
    parser.add_argument("--mockup", required=True)
    args = parser.parse_args(argv)
    page = _mockup(args.mockup)
    code, out = launcher.run(["open", str(page), launcher.PLAIN_FLAG])
    if code in launcher.FALLBACK_EXITS:
        raise Refusal("no-host", f"lavish cannot show the mockup: {out.strip()}. Give the developer "
                                 f"{page.resolve().as_uri()} and take the notes in chat; /afkv2:setup fixes the install",
                      file=page.resolve().as_uri())
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
    if status != "feedback":
        raise Refusal("host-error", f"lavish poll: {status}: {detail.get('reason')}")
    notes = [{field: prompt.get(field) for field in NOTE_FIELDS} for prompt in detail["prompts"]]
    notes_file = Path(args.notes_file)
    notes_file.parent.mkdir(parents=True, exist_ok=True)
    inject.write_if_changed(notes_file, json.dumps(notes, indent=2, ensure_ascii=False).encode("utf-8"))
    _clear_waiting_record()
    return {"ok": True, "status": status, "count": len(notes), "ended": detail["session_ended"],
            "notes_file": str(notes_file)}


def _clear_waiting_record():
    thread = os.environ.get(THREAD_VARIABLE)
    if thread:
        launcher.clear_waiting_record(data_folder(), thread)


VERBS = {"show": cmd_show, "wait": cmd_wait}


def main(argv):
    return serve(_dispatch, argv)


def _dispatch(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", 2)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
