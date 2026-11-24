"""The meeting summaries of 1 meeting: 1 comment per ticket, and each changed description, after 1 sign.

`meetings.py start --date YYYY-MM-DD --title TITLE`: makes the private run folder of the meeting and names its key,
`YYYY-MM-DD — TITLE`, which is the title of each comment.
`meetings.py outline --run-dir DIR --ticket KEY`: the to-prd outline of the ticket's live description, and its
meeting comments in `meetings.md`, in `DIR/<ticket key>/description`.
`meetings.py preview --run-dir DIR`: for each folder `DIR/<ticket key>/` that holds `summary.md`, builds the comment
and its receipt; with `TICKET.md` there too, builds the whole new description by the to-prd publish (its outline
folder is `DIR/<ticket key>/description`). Writes the page round and `preview.json`. Writes nothing to a ticket.
`meetings.py post --run-dir DIR --receipt RECEIPT --doc PAGE`: runs only when `i-publish` of the page holds the
developer's sign mark for this receipt. Per ticket: the description first (stale check, read-back), then the comment.
"""

from __future__ import annotations

import hashlib
import html
import re
import sys
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS / "to-prd" / "scripts"))
sys.path.insert(0, str(SCRIPTS / "grill-requirements" / "scripts"))
sys.path.insert(0, str(SCRIPTS / "use-lavish" / "scripts"))

import publish  # noqa: E402
import round_document  # noqa: E402
from grill_common import EXIT_UNREADABLE, Parser, Refusal, read_json, serve, write_json, write_text  # noqa: E402
from grill_start import read_config  # noqa: E402

MEETING_FILE = "meeting.json"
SUMMARY = "summary.md"
TICKET = "TICKET.md"
DESCRIPTION = "description"
PREVIEW = "preview.json"
ROUND = "preview-round.json"
SIGN_CARD = "i-publish"
TITLE_LIMIT = 200


def meeting_key(day, title):
    """The title of each comment of this meeting: the date, a long dash, the title."""
    try:
        date.fromisoformat(day)
    except ValueError:
        raise Refusal("bad-payload", f"--date {day!r} is no YYYY-MM-DD date") from None
    title = " ".join(str(title).split())
    if not title or len(title) > TITLE_LIMIT:
        raise Refusal("bad-payload", f"--title must hold 1 to {TITLE_LIMIT} characters")
    return f"{day} — {title}"


def start(day, title, data_folder):
    key = meeting_key(day, title)
    slug = re.sub(r"[^\w.-]+", "-", f"{day}-{title}").strip("-")[:80]
    run_dir = Path(data_folder) / "meetings" / slug
    run_dir.mkdir(parents=True, exist_ok=True)
    write_text(run_dir / ".gitignore", "*\n")
    write_json(run_dir / MEETING_FILE, {"title": key})
    return {"ok": True, "title": key, "run_dir": str(run_dir)}


def comment_receipt(ticket, title, block_text):
    """The port computes the same digest and refuses another text."""
    return hashlib.sha256((ticket + title + block_text).encode("utf-8")).hexdigest()


def sign_receipt(receipts):
    """1 digest over every write of the meeting: the sign covers all of them, and nothing else."""
    return hashlib.sha256("".join(sorted(receipts)).encode("utf-8")).hexdigest()


def _tickets(run_dir):
    found = sorted(folder.name for folder in run_dir.iterdir() if folder.is_dir() and (folder / SUMMARY).is_file())
    if not found:
        raise Refusal("no-summary", f"no `<ticket key>/{SUMMARY}` in {run_dir}")
    return found


def _comment(ticket, title, summary, kind, config, tracker):
    """The comment the ticket gets: its payload, its text for the page, and its receipt."""
    if kind == publish.GITHUB:
        text = tracker("block-text", {"markdown": summary})["block_text"]
        payload = {"key": ticket, "title": title, "markdown": text}
        shown = f"<pre>{html.escape(text)}</pre>"
    else:
        site = tracker("issue-get", {"key": ticket}).get("site")
        nodes = tracker("md-to-adf", {"markdown": summary})["content"]
        nodes = publish.link_ticket_keys(nodes, publish._projects(ticket, config), site)
        text = tracker("adf-text", {"adf": nodes})["block_text"]
        payload = {"key": ticket, "title": title, "adf": nodes}
        shown = publish._html(nodes, {})
    return payload, shown, comment_receipt(ticket, title, text)


def _existing(ticket, title, tracker):
    """`(expect_hash, state)` of the comment with this title: none yet, or the 1 comment the port may edit."""
    same = [item for item in tracker("meeting-comments", {"key": ticket}).get("comments") or []
            if item.get("title") == title]
    if len(same) > 1:
        raise Refusal("duplicate-meeting", f"{ticket} holds {len(same)} comments titled {title!r}: merge them by hand")
    if same and not same[0].get("own"):
        raise Refusal("not-own", f"the comment {title!r} on {ticket} has another author: it stays as it is")
    return (same[0].get("comment_hash"), "edits the comment") if same else (None, "posts a new comment")


def _card(ticket, state, shown, description):
    parts = [f"<h3>The comment: {html.escape(state)}</h3>{shown}"]
    if description:
        page = read_json(Path(description["round_input"]))
        parts.append(f"<h3>The description: {html.escape(description['action'])}</h3>")
        parts.append(page["items"][0]["body"]["html"])
        if description.get("dropped"):
            parts.append("<p>Removed from the description: " + "; ".join(
                html.escape(f"node {item['index']}: {item['text']}") for item in description["dropped"]) + "</p>")
    return {"id": f"i-{re.sub(r'[^a-z0-9]+', '-', ticket.lower()).strip('-')}", "kind": "info",
            "title": f"What {ticket} gets",
            "body": {"type": "freestyle", "id": f"i-{re.sub(r'[^a-z0-9]+', '-', ticket.lower()).strip('-')}-text",
                     "props": {"reason": "the exact comment and description text of 1 ticket"},
                     "html": "".join(parts)}}


def preview(run_dir, tracker=publish.call_tracker, config=None):
    run_dir = Path(run_dir)
    config = config if config is not None else (read_config().get("tracker") or {})
    kind = config.get("kind")
    if kind not in publish.TRACKER_NAMES:
        raise Refusal("no-publish", f"the tracker kind is {kind}: nothing is published")
    title = read_json(run_dir / MEETING_FILE)["title"]
    tickets, cards, receipts = [], [], []
    for ticket in _tickets(run_dir):
        folder = run_dir / ticket
        summary = (folder / SUMMARY).read_text("utf-8").replace("\r\n", "\n")
        payload, shown, receipt = _comment(ticket, title, summary, kind, config, tracker)
        expect_hash, state = _existing(ticket, title, tracker)
        entry = {"key": ticket, "comment": payload, "comment_receipt": receipt, "expect_hash": expect_hash,
                 "description": None}
        receipts.append(receipt)
        description = None
        if (folder / TICKET).is_file():
            if kind == publish.GITHUB:
                description = publish.build_github_ticket_preview(ticket, None, folder / TICKET, folder / DESCRIPTION,
                                                                  tracker)
            else:
                description = publish.build_ticket_preview(ticket, None, folder / TICKET, folder / DESCRIPTION,
                                                           publish._projects(ticket, config), tracker)
            entry["description"] = {"preview": description["preview"], "receipt": description["receipt"],
                                    "already_published": description["already_published"]}
            receipts.append(description["receipt"])
        tickets.append({**entry, "state": state})
        cards.append(_card(ticket, state, shown, description))
    signed = sign_receipt(receipts)
    write_json(run_dir / PREVIEW, {"title": title, "kind": kind, "receipt": signed, "tickets": tickets})
    keys = ", ".join(item["key"] for item in tickets)
    sign = {"id": SIGN_CARD, "kind": "signoff", "title": f"Publish the meeting into {keys}",
            "body": {"type": "text", "id": f"{SIGN_CARD}-text", "props": {"markdown": True, "text": (
                f"Sign to write each comment and each description above, for the meeting **{title}**. Receipt "
                f"`{signed[:8]}`. Any other mark or a note changes nothing on a ticket.")}}}
    write_json(run_dir / ROUND, {
        "short_title": f"Meeting {title}"[:40], "step": "Meeting summaries",
        "banner": {"settled": [], "unlocks": [f"the comments and descriptions of {keys}"], "parked": []},
        "items": [*cards, sign]})
    return {"ok": True, "title": title, "receipt": signed, "preview": str(run_dir / PREVIEW),
            "round_input": str(run_dir / ROUND),
            "tickets": [{"key": item["key"], "comment": item["state"],
                         "description": bool(item["description"])} for item in tickets]}


def _signed(doc, receipt):
    items = [item for rnd in read_json(Path(doc)).get("rounds", []) for item in rnd.get("items", [])
             if item.get("id") == SIGN_CARD]
    if not items or not round_document.holds_sign_mark(items[-1]):
        raise Refusal("no-sign", f"card {SIGN_CARD} holds no sign mark of the developer: nothing was written")
    if f"`{receipt[:8]}`" not in str((items[-1].get("body") or {}).get("props", {}).get("text", "")):
        raise Refusal("bad-receipt", "the signed card shows another receipt: show the new preview and ask again")


def _check_unchanged(run_dir, seen, kind, config, tracker):
    """Each summary and each description is still the text the developer signed."""
    receipts = []
    for entry in seen["tickets"]:
        summary = (run_dir / entry["key"] / SUMMARY).read_text("utf-8").replace("\r\n", "\n")
        _, _, receipt = _comment(entry["key"], seen["title"], summary, kind, config, tracker)
        if receipt != entry["comment_receipt"]:
            raise Refusal("bad-receipt", f"the summary of {entry['key']} changed after the preview: show a new preview")
        receipts.append(receipt)
        if entry["description"]:
            receipts.append(entry["description"]["receipt"])
    if sign_receipt(receipts) != seen["receipt"]:
        raise Refusal("bad-receipt", "the preview file changed after it was built: show a new preview")


def post(run_dir, receipt, doc, log_path, tracker=publish.call_tracker, config=None):
    run_dir = Path(run_dir)
    config = config if config is not None else (read_config().get("tracker") or {})
    seen = read_json(run_dir / PREVIEW)
    if receipt != seen.get("receipt"):
        raise Refusal("bad-receipt", "this receipt is not the receipt of the preview: show a new preview")
    _signed(doc, receipt)
    _check_unchanged(run_dir, seen, seen["kind"], config, tracker)
    results = []
    for entry in seen["tickets"]:
        done = {"key": entry["key"], "description": None, "comment": None}
        try:
            if entry["description"]:
                answer = publish.publish_after_yes(entry["description"]["preview"], entry["description"]["receipt"],
                                                   log_path, tracker)
                done["description"] = "unchanged" if answer.get("already_published") else "published"
            answer = tracker("meeting-comment-put", {**entry["comment"], "receipt": entry["comment_receipt"],
                                                     "expect_hash": entry["expect_hash"]})
            done["comment"], done["url"] = answer.get("action"), answer.get("url")
        except Refusal as refusal:
            done["error"] = {"code": refusal.code, "reason": refusal.reason}
        results.append(done)
    return {"ok": True, "title": seen["title"], "tickets": results,
            "failed": [item["key"] for item in results if "error" in item]}


def main(argv):
    parser = Parser(add_help=False)
    parser.add_argument("verb", choices=("start", "outline", "preview", "post"))
    for name in ("--date", "--title", "--run-dir", "--receipt", "--doc", "--ticket"):
        parser.add_argument(name)
    args = parser.parse_args(argv)
    needed = {"start": ("date", "title"), "outline": ("run_dir", "ticket"), "preview": ("run_dir",),
              "post": ("run_dir", "receipt", "doc")}[args.verb]
    missing = [f"--{name.replace('_', '-')}" for name in needed if not getattr(args, name)]
    if missing:
        raise Refusal("usage", f"{args.verb} needs {', '.join(missing)}", EXIT_UNREADABLE)
    try:
        if args.verb == "start":
            return start(args.date, args.title, read_config()["data_folder"])
        if args.verb == "outline":
            kind = (read_config().get("tracker") or {}).get("kind")
            return publish.outline(args.ticket, Path(args.run_dir) / args.ticket / DESCRIPTION, kind=kind)
        if args.verb == "preview":
            return preview(args.run_dir)
        return post(args.run_dir, args.receipt, args.doc,
                    Path(read_config()["data_folder"]) / publish.PUBLISHED_TICKETS)
    except OSError as error:
        raise Refusal("io-error", f"{type(error).__name__}: {error}", EXIT_UNREADABLE) from error


if __name__ == "__main__":
    sys.exit(serve(main))
