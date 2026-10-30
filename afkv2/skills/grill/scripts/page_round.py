"""Drive one page round through the engine verbs (SDD §3), from the repository root.

  present --doc D                 check, render, show, in that order; stops at the first refusal
  wait    --doc D --raw-file F    poll; writes the raw response to F, byte for byte
  ingest  --doc D --raw-file F    ingest; deletes F; answers what the round pass must read

The raw text waits in a file because the document holds it only after ingest. Poll has no time
limit here: it returns when the human sends the round.
"""

from __future__ import annotations

import sys
from pathlib import Path

from grill_common import PLUGIN_ROOT, Parser, Refusal, read_json, run_command, serve
from round_document import pending

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
    _engine("show", doc)
    return {"ok": True, "page": page}


def wait(doc, raw_file):
    answer = _engine("poll", doc, timeout=None)
    raw = answer.get("raw")
    if not isinstance(raw, str):
        raise Refusal("bad-answer", f"poll answered no `raw` text; its fields: {sorted(answer)}", verb="poll")
    path = Path(raw_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw.encode("utf-8"))
    return {"ok": True, "raw_file": raw_file, "bytes": path.stat().st_size}


def ingest(doc, raw_file):
    if not Path(raw_file).is_file():
        raise Refusal("unreadable", f"no raw response at {raw_file}", 2, verb="ingest")
    _engine("ingest", doc, "--raw-file", raw_file)
    Path(raw_file).unlink()
    return {"ok": True, **pending(read_json(doc))}


def main(argv):
    parser = Parser(add_help=False)
    parser.add_argument("verb", choices=["present", "wait", "ingest"])
    parser.add_argument("--doc", required=True)
    parser.add_argument("--raw-file")
    args = parser.parse_args(argv)
    if args.verb == "present":
        return present(args.doc)
    if not args.raw_file:
        raise Refusal("usage", f"{args.verb} needs --raw-file", 2)
    return wait(args.doc, args.raw_file) if args.verb == "wait" else ingest(args.doc, args.raw_file)


if __name__ == "__main__":
    sys.exit(serve(main))
