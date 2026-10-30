"""Start or resume a grill session: `grill_start.py --ticket KEY`, from the repository root.

Answers ticket, spec_dir, log, doc, session, resume, raw_file and raw_pending. A refusal for a
missing input names the file and the skill that writes it. Creates the grill log section; the
document itself appears at the first build.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from grill_common import PLUGIN_ROOT, Parser, Refusal, read_json, run_command, serve
from grill_log import exit_gate_passed, ensure_section

CONFIG = ".afkv2/config.json"
SETUP = "/afkv2:setup"


def _missing(missing, writer):
    return Refusal("missing-input", f"missing {missing}; {writer} writes it", missing=missing, writer=writer)


def read_config():
    try:
        config = run_command(PLUGIN_ROOT / "scripts" / "afkv2_config.py", ["read"], 60)
    except Refusal as refusal:
        if refusal.code == "no-config":
            raise _missing(CONFIG, SETUP) from refusal
        raise
    if not (config.get("tracker") or {}).get("kind"):
        raise _missing(f"{CONFIG} tracker.kind", SETUP)
    return config


def ticket_slug(ticket):
    return re.sub(r"[^\w.-]+", "-", ticket).strip("-")


def _new_session(pages):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    session, attempt = f"s-{stamp}", 1
    while (pages / f"grill-{session}.json").exists():
        attempt += 1
        session = f"s-{stamp}-{attempt}"
    return session


def _open_session(pages, log):
    """The newest document whose session has no passed exit gate; a grill resumes it."""
    documents = sorted(pages.glob("grill-*.json"), key=lambda path: path.stat().st_mtime)
    if not documents:
        return None
    session = documents[-1].stem[len("grill-"):]
    return None if exit_gate_passed(log, session) else session


def _raw_pending(raw_file, doc):
    """True when a polled answer waits on disk and the document does not hold it yet."""
    if not raw_file.exists():
        return False
    if not doc.exists():
        return True
    raw = raw_file.read_bytes().decode("utf-8", "replace")
    stored = [r.get("raw") for rnd in read_json(doc).get("rounds", []) for r in rnd.get("responses") or []]
    return raw not in stored


def start(argv):
    parser = Parser(add_help=False)
    parser.add_argument("--ticket")
    args = parser.parse_args(argv)
    if not args.ticket:
        raise _missing("ticket key", "the invocation of this skill")
    config = read_config()
    spec_dir = Path(config["spec_folder"]) / ticket_slug(args.ticket)
    pages, log = spec_dir / "pages", spec_dir / "GRILL-LOG.md"
    ensure_section(log, args.ticket)
    resumed = _open_session(pages, log)
    session = resumed or _new_session(pages)
    doc, raw_file = pages / f"grill-{session}.json", pages / f"grill-{session}.raw.txt"
    return {"ok": True, "ticket": args.ticket, "tracker": config["tracker"]["kind"], "spec_dir": spec_dir.as_posix(),
            "log": log.as_posix(), "doc": doc.as_posix(), "session": session, "resume": bool(resumed),
            "raw_file": raw_file.as_posix(), "raw_pending": _raw_pending(raw_file, doc)}


if __name__ == "__main__":
    sys.exit(serve(start))
