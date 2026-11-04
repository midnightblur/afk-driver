"""Where an ad-hoc page lives (requirement ADR-0002), from the repository root.

  start --topic T [--ticket K] [--private]  answers `doc`, `session`, `raw_file` and `home` of a new page session.
                                            With a ticket and content the repository's readers may see, the page
                                            lives in the ticket's spec folder (`home: spec`); with no ticket, or with
                                            `--private`, in the data folder's `pages/<repository name>/`
                                            (`home: data`). With no topic it refuses `no-topic`. It writes nothing:
                                            the round builder writes the document, `--private` included.
  track --doc D --ticket K                  moves the page and its side files into the ticket's spec folder and
                                            answers `doc` (the new path) and `moved`. The document moves last, so a
                                            second run moves what is left. Refuses `needs-ticket` and `private`.

The repository name is the folder of the main checkout, also from a linked worktree.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from grill_common import EXIT_UNREADABLE, PLUGIN_ROOT, Parser, Refusal, read_json, serve, write_json
from round_document import FORMAT_0, SCHEMA, format_1

sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from afkv2_config import Refusal as ConfigRefusal, data_folder, read_config  # noqa: E402

SKILL = "use-lavish"
PAGES = "pages"


def ticket_slug(ticket):
    """The ticket's folder name in the spec folder, as the grill names it."""
    return re.sub(r"[^\w.-]+", "-", ticket).strip("-")


def repository_name(start):
    """The folder name of the main checkout of the repository that holds `start`; the folder's own name outside one."""
    start = Path(start).resolve()
    root = next((folder for folder in (start, *start.parents) if (folder / ".git").exists()), None)
    if root is None:
        return start.name
    dot_git = root / ".git"
    if dot_git.is_file():
        line = dot_git.read_text("utf-8", "replace").strip()
        gitdir = Path(line[len("gitdir:"):].strip()) if line.startswith("gitdir:") else None
        if gitdir is not None and gitdir.parent.name == "worktrees":
            return gitdir.parent.parent.parent.name
    return root.name


def _spec_pages(ticket):
    config = read_config()
    if not config["ok"]:
        raise Refusal(config["error"]["code"], config["error"]["reason"])
    return Path(config["spec_folder"]).resolve() / ticket_slug(ticket) / PAGES


def _data_pages():
    try:
        return (data_folder() / PAGES / repository_name(Path.cwd())).resolve()
    except ConfigRefusal as refusal:
        raise Refusal(refusal.code, refusal.reason, EXIT_UNREADABLE) from refusal


def _new_session(pages):
    """`s-<UTC stamp>`, with a count when a page of any skill in the folder already holds that id."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    session, attempt = f"s-{stamp}", 1
    while any(Path(pages).glob(f"*-{session}.json")):
        attempt += 1
        session = f"s-{stamp}-{attempt}"
    return session


def start_page(topic, ticket=None, private=False):
    if not (topic or "").strip():
        raise Refusal("no-topic", "start needs --topic: ask the human in chat what the page is about, and open no page")
    home = "spec" if ticket and not private else "data"
    pages = _spec_pages(ticket) if home == "spec" else _data_pages()
    session = _new_session(pages)
    doc = pages / f"{SKILL}-{session}.json"
    raw_file = doc.with_name(f"{SKILL}-{session}.raw.txt")
    return {"ok": True, "doc": doc.as_posix(), "session": session, "raw_file": raw_file.as_posix(), "home": home}


def _side_files(doc):
    """The files beside a document that carry its name and one more suffix: the page, the raw answer, the records."""
    return sorted(path for path in doc.parent.glob(f"{doc.stem}.*") if path.name != doc.name and path.is_file())


def track_page(doc, ticket):
    if not (ticket or "").strip():
        raise Refusal("needs-ticket", "track needs --ticket: ask the human which ticket the page belongs to")
    doc = Path(doc).resolve()
    target = _spec_pages(ticket) / doc.name
    if doc.is_file():
        raw = read_json(doc)
        if not isinstance(raw, dict) or raw.get("schema") not in (SCHEMA, FORMAT_0):
            raise Refusal("unreadable", f"{doc} is no page document of format 0 or 1", EXIT_UNREADABLE)
        page = format_1(raw)
        if page["session"].get("private"):
            raise Refusal("private", "the page is marked private: say what must come out of it before it can live in "
                                     "the repository")
    elif not target.is_file():
        raise Refusal("unreadable", f"no page at {doc} and none at {target}", EXIT_UNREADABLE)
    if doc.parent == target.parent:
        return {"ok": True, "doc": target.as_posix(), "moved": []}
    if doc.is_file() and target.exists():
        raise Refusal("exists", f"{target} exists already; move or remove one of the 2 pages first")
    target.parent.mkdir(parents=True, exist_ok=True)
    moved = []
    for side in _side_files(doc):
        os.replace(side, target.parent / side.name)
        moved.append((target.parent / side.name).as_posix())
    if doc.is_file():
        page["session"]["ticket"] = page["session"].get("ticket") or ticket
        write_json(target, page)
        doc.unlink()
        moved.append(target.as_posix())
    return {"ok": True, "doc": target.as_posix(), "moved": moved}


def main(argv):
    parser = Parser(add_help=False)
    parser.add_argument("verb", choices=["start", "track"])
    parser.add_argument("--topic")
    parser.add_argument("--ticket")
    parser.add_argument("--private", action="store_true")
    parser.add_argument("--doc")
    args = parser.parse_args(argv)
    if args.verb == "start":
        return start_page(args.topic, args.ticket, args.private)
    if not args.doc:
        raise Refusal("usage", "track needs --doc", EXIT_UNREADABLE)
    return track_page(args.doc, args.ticket)


if __name__ == "__main__":
    sys.exit(serve(main))
