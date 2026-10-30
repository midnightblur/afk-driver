"""Write this skill's section of GRILL-LOG.md and the glossary, from the repository root.

  row  --log L --kind K (--text T | --text-file F)     one agent row, overwritten in place
  sync --doc D --log L                                 rows that come from the page document
  term --log L --term T (--glossary G --definition D | --pending)
  gate --doc D --log L                                 the mechanical part of the exit gate

Row grammar: GRILL-LOG-FORMAT.md. Other sections of the file stay byte for byte.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from grill_common import Parser, Refusal, read_json, serve, write_text
from round_document import ASKING, _components, _live_notes, _map_nodes, current_round, returning

SECTION = "## Requirements grill"
KEYED_KINDS = {"Ledger", "Term", "Policy", "Staples", "Spinoff"}
SINGLE_KINDS = {"Round 0", "Examples", "Devil", "Escape"}
REQUIRED_KINDS = ("Policy", "Staples", "Examples", "Devil")
STATUS_ROW = re.compile(r"^.+ → (pending|(verified|refuted) \(.+\)|unverified-external\b.*)$")
GATE_PASSED = "- Settled: exit gate passed"
GENERATED = re.compile(r"^- (Session|Steer): |^- (Settled|Open|Carried|Info): .* · card \S+$")


def ensure_section(log, ticket=None):
    log = Path(log)
    text = log.read_text("utf-8") if log.exists() else f"# Grill log — {ticket}\n"
    if not re.search(rf"^{re.escape(SECTION)}$", text, re.M):
        write_text(log, text.rstrip("\n") + f"\n\n{SECTION}\n")


def _split(log):
    """(text before the section's rows, row blocks, text after the section)."""
    text = Path(log).read_text("utf-8")
    found = re.search(rf"^{re.escape(SECTION)}\n", text, re.M)
    if not found:
        raise Refusal("no-section", f"{log} has no {SECTION} section")
    rest = text[found.end():]
    following = re.search(r"^## ", rest, re.M)
    end = following.start() if following else len(rest)
    blocks = []
    for line in rest[:end].splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") and blocks:
            blocks[-1].append(line)
        else:
            blocks.append([line])
    return text[:found.end()], blocks, rest[end:]


def _join(head, blocks, tail):
    rows = "\n".join(line for block in blocks for line in block)
    middle = f"\n{rows}\n" if rows else ""
    return head + middle + ("\n" + tail if tail else "")


def exit_gate_passed(log, session):
    log = Path(log)
    if not log.exists():
        return False
    return any(line.startswith(GATE_PASSED) and line.endswith(f"· session {session}")
               for line in log.read_text("utf-8").splitlines())


def _row_key(kind, text):
    if kind in SINGLE_KINDS:
        return f"- {kind}: "
    return f"- {kind}: {text.split(' → ')[0]}"


def write_row(log, kind, text):
    if kind not in KEYED_KINDS | SINGLE_KINDS:
        raise Refusal("unknown-kind", f"{kind!r} is not one of {sorted(KEYED_KINDS | SINGLE_KINDS)}")
    value = json.dumps(text, ensure_ascii=False) if kind == "Round 0" else " ".join(text.split())
    if kind in ("Ledger", "Term") and not STATUS_ROW.match(value):
        raise Refusal("bad-row", f"a {kind} row reads `<text> → pending | verified (<citation>) | "
                                 f"refuted (<citation>) | unverified-external (<who acknowledged>)`: {text!r}")
    row = f"- {kind}: {value}"
    key = _row_key(kind, value)
    head, blocks, tail = _split(log)
    matches = [i for i, block in enumerate(blocks)
               if block[0] == key or block[0].startswith(key + " → ") or (kind in SINGLE_KINDS and block[0].startswith(key))]
    if matches:
        blocks[matches[0]] = [row]
    else:
        blocks.append([row])
    write_text(log, _join(head, blocks, tail))
    return {"ok": True, "row": row}


def _first_text(item):
    for component in _components(item["body"]):
        value = (component.get("props") or {}).get("text")
        if component.get("type") == "text" and value:
            return " ".join(value.split())
    return item["id"]


def _field_text(item, name):
    for component in _components(item["body"]):
        if component.get("id") == f"{item['id']}-{name}":
            return (component.get("props") or {}).get("text")
    return None


def _note_lines(item):
    return [f"  owner note on {item['id']} ({note['id']}): {json.dumps(note['text'], ensure_ascii=False)}"
            for note in _live_notes(item)]


def _accepted_date(doc, round_n):
    for rnd in doc["rounds"]:
        if rnd["n"] == round_n and rnd.get("responses"):
            return rnd["responses"][0]["received"][:10]
    return "date not recorded"


def _how_settled(doc, item):
    settled = item["settled"]
    if settled["by"] == "note":
        return f"settled by note R{settled['round']} · reading: {settled['reading']}"
    if item["kind"] != "decided":
        return f"settled by mark {settled['signal']} R{settled['round']}"
    tail = [f"decided-by agent R{settled['round']}", f"accepted {_accepted_date(doc, settled['round'])}"]
    tail += [value for value in (_field_text(item, "evidence"), _field_text(item, "reverse")) if value]
    return " · ".join(tail)


def _item_row(doc, item, is_current):
    title, card = _first_text(item), f"· card {item['id']}"
    if item.get("settled") and item["state"] in ("settled_by_mark", "settled_by_note"):
        return [f"- Settled: {title} · {_how_settled(doc, item)} {card}", *_note_lines(item)]
    if is_current and item["kind"] in ASKING:
        return [f"- Open: {title} {card}", *_note_lines(item)]
    if not _live_notes(item):
        return None
    kind = "Carried" if item["kind"] in ASKING else "Info"
    return [f"- {kind}: {title} {card}", *_note_lines(item)]


def _document_rows(doc):
    session = doc["session"]["id"]
    rows = [[f"- Session: {session} · page document pages/grill-{session}.json"]]
    current = current_round(doc)
    for rnd in doc["rounds"]:
        for item in rnd["items"]:
            row = _item_row(doc, item, rnd is current)
            if row:
                rows.append(row)
    nodes = {node.get("id") for node in _map_nodes(doc)}
    for rnd in doc["rounds"]:
        for item in rnd["items"]:
            rows += [[f"- Steer: {note['target']} ({note['id']}): {json.dumps(note['text'], ensure_ascii=False)}"]
                     for note in _live_notes(item) if note.get("target") in nodes]
    return rows


def _session_documents(doc_path):
    """This document and every older grill document beside it, oldest session first."""
    doc_path = Path(doc_path)
    docs = [read_json(doc_path)]
    docs += [read_json(path) for path in doc_path.parent.glob("grill-*.json") if path.resolve() != doc_path.resolve()]
    return sorted(docs, key=lambda doc: (doc["session"]["started"], doc["session"]["id"]))


def sync(doc_path, log):
    """Overwrite the rows that come from the documents; keep every agent row. A sync voids an old gate pass."""
    head, blocks, tail = _split(log)
    kept = [block for block in blocks if not GENERATED.match(block[0]) and not block[0].startswith(GATE_PASSED)]
    rows = [row for doc in _session_documents(doc_path) for row in _document_rows(doc)]
    write_text(log, _join(head, kept + rows, tail))
    return {"ok": True, "rows": len(rows)}


def write_term(log, term, glossary, definition):
    if glossary is None or definition is None:
        return write_row(log, "Term", f"{term} → pending")
    path = Path(glossary)
    text = path.read_text("utf-8") if path.exists() else "# Glossary\n"
    entry = f"**{term}**:\n{' '.join(definition.split())}\n"
    pattern = re.compile(rf"^\*\*{re.escape(term)}\*\*:\n(?:.+\n?)*", re.M)
    if pattern.search(text):
        text = pattern.sub(lambda _: entry, text, count=1)
    else:
        text = text.rstrip("\n") + f"\n\n{entry}"
    write_text(path, text)
    try:
        shown = Path(os.path.relpath(path)).as_posix()
    except ValueError:
        shown = path.as_posix()
    return write_row(log, "Term", f"{term} → verified ({shown})")


def _doc_failures(doc):
    current = current_round(doc)
    if current is None:
        return ["the document has no current round"]
    failures = []
    if not current.get("responses"):
        failures.append(f"round {current['n']} has no answer")
    for item in current["items"]:
        waiting = item["kind"] in ASKING and item["state"] in ("open", "blocked")
        if waiting or item["state"] == "needs_reading":
            failures.append(f"point {item['id']} is {item['state']}")
    failures += [f"point {item['id']} returned and has no new card" for item in returning(doc)]
    return failures


def _log_failures(blocks):
    rows = [block[0] for block in blocks]
    failures = []
    for row in rows:
        kind = row[2:].split(":", 1)[0]
        if kind in ("Ledger", "Term") and " → pending" in row:
            failures.append(f"pending: {row[2:]}")
        if kind == "Ledger" and " → refuted" in row:
            failures.append(f"refuted and not settled again: {row[2:]}")
    for kind in REQUIRED_KINDS:
        if not any(row.startswith(f"- {kind}: ") for row in rows):
            failures.append(f"no {kind} row")
    return failures


def gate(doc_path, log):
    doc = read_json(doc_path)
    head, blocks, tail = _split(log)
    failures = _doc_failures(doc) + _log_failures(blocks)
    if failures:
        raise Refusal("exit-gate", f"{len(failures)} exit-gate checks failed", failures=failures)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    blocks = [block for block in blocks if not block[0].startswith(GATE_PASSED)]
    blocks.append([f"{GATE_PASSED} {today} · session {doc['session']['id']}"])
    write_text(log, _join(head, blocks, tail))
    return {"ok": True, "passed": today}


def main(argv):
    parser = Parser(add_help=False)
    parser.add_argument("verb", choices=["row", "sync", "term", "gate"])
    parser.add_argument("--log", required=True)
    parser.add_argument("--doc")
    parser.add_argument("--kind")
    parser.add_argument("--text")
    parser.add_argument("--text-file")
    parser.add_argument("--term")
    parser.add_argument("--glossary")
    parser.add_argument("--definition")
    parser.add_argument("--pending", action="store_true")
    args = parser.parse_args(argv)
    if args.verb == "row":
        if args.text_file:
            try:
                args.text = Path(args.text_file).read_bytes().decode("utf-8")
            except OSError as error:
                raise Refusal("unreadable", f"{args.text_file}: {error}", 2) from error
        if not args.kind or args.text is None:
            raise Refusal("usage", "row needs --kind and --text or --text-file", 2)
        return write_row(args.log, args.kind, args.text)
    if args.verb == "term":
        if not args.term or not (args.pending or (args.glossary and args.definition)):
            raise Refusal("usage", "term needs --term and either --pending or --glossary with --definition", 2)
        return write_term(args.log, args.term, args.glossary, args.definition)
    if not args.doc:
        raise Refusal("usage", f"{args.verb} needs --doc", 2)
    return sync(args.doc, args.log) if args.verb == "sync" else gate(args.doc, args.log)


if __name__ == "__main__":
    sys.exit(serve(main))
