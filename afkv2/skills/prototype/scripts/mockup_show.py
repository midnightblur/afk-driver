"""A mockup in lavish, through the launcher: a page with no page document (SDD §3; ADR-0003 of ticket 207).

`mockup_show.py show --mockup FILE`: opens the file itself with `--plain` and answers `url`; a tab record keeps the
  tab that shows it, so a later show adds `--no-open` and answers `tab` `reused`. On Codex (`CODEX_THREAD_ID` set) it
  writes the waiting record with a null document. Refuses `no-host` when the launcher runs no host (lavish missing, at
  another version, or `LAVISH_AXI_HOST` set); its reason holds the `file://` path.
`mockup_show.py wait --mockup FILE --notes-file NOTES`: one host poll; writes each note to NOTES as
  `{uid, prompt, selector, tag, text}` and answers `count` and `ended`; a closed page or browser writes no
  note and answers `ended`; a poll that is still waiting answers `count` 0. Refuses `no-session`, `no-host` as show
  does, and `notes-unwritten` with the notes in its `notes` field when NOTES cannot be written after the poll.
`mockup_show.py reply --mockup FILE --reply-file REPLY`: shows REPLY (Markdown) on the open mockup. Refuses
  `no-session`.
`mockup_show.py end --mockup FILE`: ends the session and clears the waiting record and the tab record, also when FILE
  is gone. Never refuses on the host.

Each answer is one JSON object; exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
PLUGIN = SKILL.parents[1]
sys.path.insert(0, str(SKILL.parent / "use-lavish" / "scripts"))
sys.path.insert(0, str(PLUGIN / "engine"))
sys.path.insert(0, str(PLUGIN / "scripts"))

import afkv2_config  # noqa: E402
import launcher  # noqa: E402
from grill_common import Parser, Refusal, serve  # noqa: E402
from shell import inject  # noqa: E402

THREAD_VARIABLE = "CODEX_THREAD_ID"
ENDED = ("ended", "browser_disconnected")  # the developer closed the page or the browser
TAB_GONE = (*ENDED, "no-session")  # no browser tab shows the mockup any more
NOTE_FIELDS = ("uid", "prompt", "selector", "tag", "text")  # lavish poll at 0.1.86 (SDD §9b)
TABS_FOLDER = "mockup-tabs"


def _mockup(path, exists=True):
    """The absolute mockup path: the Codex Stop hook polls it from another working folder."""
    page = Path(path).resolve()
    if not launcher.HTML.search(page.name) or (exists and not page.is_file()):
        raise Refusal("unreadable", f"{path}: no .html mockup there", 2)
    return page


def _data_folder():
    """The afkv2 data folder, with the refusal in the answer envelope of this script."""
    try:
        return afkv2_config.data_folder()
    except afkv2_config.Refusal as refusal:
        raise Refusal(refusal.code, refusal.reason, 2) from None


def _thread_folder():
    """The data folder on Codex, else None: Codex needs it for the waiting record, so it is checked before the host."""
    return _data_folder() if os.environ.get(THREAD_VARIABLE) else None


def _tab_record(page):
    """The record that a browser tab shows the mockup, or None with no data folder: lavish keeps no such state."""
    try:
        folder = _data_folder()
    except Refusal:
        return None
    key = os.path.normcase(str(page)).encode("utf-8")
    return folder / TABS_FOLDER / f"{hashlib.sha256(key).hexdigest()[:12]}.json"


def _forget_tab(page):
    record = _tab_record(page)
    if record is not None:
        record.unlink(missing_ok=True)


def _no_host(page, cause):
    """The refusal when the launcher runs no host: the developer opens the file itself and notes in chat."""
    uri, cause = page.resolve().as_uri(), cause.strip().rstrip(".")
    return Refusal("no-host", f"lavish cannot show the mockup: {cause}. Give the developer {uri} and take the notes "
                              "in chat; /afkv2:setup fixes the install", file=uri)


def cmd_show(argv):
    """Open the mockup as it is: `--plain` writes no afkv2 runtime into the file."""
    parser = Parser(add_help=False)
    parser.add_argument("--mockup", required=True)
    args = parser.parse_args(argv)
    page = _mockup(args.mockup)
    folder, tab = _thread_folder(), _tab_record(page)
    reused = tab is not None and tab.is_file()  # lavish opens a browser tab on each open without --no-open
    code, out = launcher.run(["open", str(page), *(["--no-open"] if reused else []), launcher.PLAIN_FLAG])
    if code in launcher.FALLBACK_EXITS:
        raise _no_host(page, out)
    if code != 0:
        raise Refusal("host-error", f"lavish open: exit {code}: {out.strip()}")
    session = launcher.parse_host_output(out).get("session") or {}
    if session.get("status") != "opened":
        reused = False
        _forget_tab(page)
    elif tab is not None and not reused:
        inject.write_if_changed(tab, json.dumps({"page": str(page), "url": session.get("url")}).encode("utf-8"))
    record = None
    if folder is not None:  # Codex: the Stop hook waits on this record; a mockup has no page document
        record = str(launcher.write_waiting_record(folder, os.environ[THREAD_VARIABLE], None, str(page)))
    return {"ok": True, "page": str(page), "url": session.get("url"), "status": session.get("status"),
            "tab": "reused" if reused else None, "waiting_record": record}


def cmd_wait(argv):
    """One host poll. The host hands a send over once, so the notes file is written before the answer."""
    parser = Parser(add_help=False)
    parser.add_argument("--mockup", required=True)
    parser.add_argument("--notes-file", required=True)
    args = parser.parse_args(argv)
    page = _mockup(args.mockup)
    folder, notes_file = _thread_folder(), _notes_file(args.notes_file)
    status, detail = launcher.poll_status(["poll", str(page)])
    if status == "fallback":
        raise _no_host(page, detail["reason"])
    ended = status in ENDED or (status == "feedback" and detail["session_ended"])
    if status in TAB_GONE or ended:
        _forget_tab(page)
    if status == "no-session":
        raise Refusal("no-session", f"no lavish session shows {page}; run show first")
    if status not in ("feedback", "waiting", *ENDED):
        raise Refusal("host-error", f"lavish poll: {status}: {detail.get('reason')}")
    prompts = detail["prompts"] if status == "feedback" else []
    notes = [{field: prompt.get(field) for field in NOTE_FIELDS} for prompt in prompts]
    try:
        inject.write_if_changed(notes_file, json.dumps(notes, indent=2, ensure_ascii=False).encode("utf-8"))
    except OSError as problem:  # the host hands a send over once: the notes go back in the refusal
        raise Refusal("notes-unwritten", f"cannot write the notes file {notes_file}: {problem}; the notes are in "
                                         "the field notes", notes=notes) from None
    if folder is not None and status != "waiting":
        launcher.clear_waiting_record(folder, os.environ[THREAD_VARIABLE])
    return {"ok": True, "status": status, "count": len(notes), "ended": ended, "notes_file": str(notes_file)}


def _notes_file(path):
    """The notes file path, checked before the poll: its folder exists or is made, and the path is no folder."""
    notes_file = Path(path)
    try:
        notes_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as problem:
        raise Refusal("unreadable", f"notes file {path}: cannot make its folder: {problem}", 2) from None
    if notes_file.is_dir() or not notes_file.parent.is_dir():
        raise Refusal("unreadable", f"notes file {path}: the path is a folder or has no folder", 2)
    return notes_file


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
    page = _mockup(args.mockup, exists=False)
    code, out = launcher.run(["end", str(page)])
    _forget_tab(page)
    thread = os.environ.get(THREAD_VARIABLE)
    if thread:
        try:
            launcher.clear_waiting_record(_data_folder(), thread)
        except Refusal:  # no data folder, so no waiting record to clear
            pass
    parsed = {} if code in launcher.FALLBACK_EXITS else launcher.parse_host_output(out)
    return {"ok": True, "ended": code == 0, "host": str(parsed.get("error") or out.strip())}


VERBS = {"show": cmd_show, "wait": cmd_wait, "reply": cmd_reply, "end": cmd_end}


def main(argv):
    return serve(_dispatch, argv)


def _dispatch(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", 2)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
