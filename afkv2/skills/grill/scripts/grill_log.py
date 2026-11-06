"""Write this skill's section of GRILL-LOG.md and the glossary, from the repository root.

  row  --log L --kind K (--text T | --text-file F)     one agent row, overwritten in place
  sync --doc D --log L                                 rows that come from the page document
  term --log L --term T (--glossary G --definition D | --pending)
  gate --doc D --log L                                 the mechanical part of the exit gate; on a version 2 page
                                                       also its questions for others, stories and worked examples;
                                                       a pass answers `stale` and `changed`, each empty when nothing,
                                                       and writes the gate row and the `Last pass` row

Row grammar: GRILL-LOG-FORMAT.md. Other sections of the file stay byte for byte.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "use-lavish" / "scripts"))

from grill_common import Parser, Refusal, page_documents, read_json, serve, write_text  # noqa: E402
from round_document import (ASKING, _carried, _carries_card, _components, card_notes, current_round,  # noqa: E402
                            format_1, is_version_2, returning, signature_missing, steer_targets, steers)

SECTION = "## Requirements grill"
KEYED_KINDS = {"Ledger", "Term", "Policy", "Staples", "Spinoff", "Takeover"}
SINGLE_KINDS = {"Round 0", "Examples", "Devil", "Escape"}
REQUIRED_KINDS = ("Policy", "Staples", "Examples", "Devil")
STATUS_ROW = re.compile(r"^.+ → (pending|(verified|refuted) \(.+\)|unverified-external\b.*)$")
# A takeover row: the round and the time of one entry of `session.takeovers`, as take-over answers them.
TAKEOVER_ROW = re.compile(r"^R[1-9][0-9]* · \d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$")
# The run branch of a feature branch. Lockstep copy of check_plan.RUN_SUFFIX of to-subtasks, not imported: a test world
# copies only the skills it runs. test_grill_v2.py compares them.
RUN_SUFFIX = "-run"
GIT_LIMIT_S = 30
GATE_PASSED = "- Settled: exit gate passed"
# The round of the session's last passed end check; `changed` measures from it. A sync keeps it.
LAST_PASS_ROW = re.compile(r"^- Last pass: R([1-9][0-9]*) · session (\S+)$")
EXAMPLE_KINDS = ("frequent", "edge", "risky")
# The page lists whose entries carry change lines, with the field that names each entry (SDD §4).
ENTRY_TEXT = {"sections": ("section", "title"), "stories": ("story", "text"), "examples": ("example", "title"),
              "questions": ("question", "question")}
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
    if kind == "Takeover" and not TAKEOVER_ROW.match(value):
        raise Refusal("bad-row", f"a Takeover row reads `R<n> · <at>`, the round and the time take-over answers: {text!r}")
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


def _field_text(item, name, prefix=""):
    """The text of a decided field. A field with a label carries its grade as a badge; an older card has the
    grade or the prefix in its text already."""
    for component in _components(item["body"]):
        if component.get("id") == f"{item['id']}-{name}":
            props = component.get("props") or {}
            if not props.get("label"):
                return props.get("text")
            return f"{props['badge']}: {props['text']}" if props.get("badge") else prefix + props["text"]
    return None


def _note_lines(doc, item, targets):
    """The rows of the notes that name the card, from the session list."""
    return [f"  owner note on {item['id']} ({note['id']}): {json.dumps(note['text'], ensure_ascii=False)}"
            for note in card_notes(doc, item, targets)]


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
    tail += [value for value in (_field_text(item, "evidence"), _field_text(item, "reverse", "reverse: ")) if value]
    return " · ".join(tail)


def _item_row(doc, item, is_current, targets):
    title, card, notes = _first_text(item), f"· card {item['id']}", _note_lines(doc, item, targets)
    if item.get("settled") and item["state"] in ("settled_by_mark", "settled_by_note"):
        return [f"- Settled: {title} · {_how_settled(doc, item)} {card}", *notes]
    if is_current and item["kind"] in ASKING:
        return [f"- Open: {title} {card}", *notes]
    if not notes:
        return None
    kind = "Carried" if item["kind"] in ASKING else "Info"
    return [f"- {kind}: {title} {card}", *notes]


def _document_rows(doc):
    session = doc["session"]["id"]
    rows = [[f"- Session: {session} · page document pages/grill-{session}.json"]]
    current, targets = current_round(doc), steer_targets(doc)
    for rnd in doc["rounds"]:
        for item in rnd["items"]:
            row = _item_row(doc, item, rnd is current, targets)
            if row:
                rows.append(row)
    rows += [[f"- Steer: {note['target']} ({note['id']}): {json.dumps(note['text'], ensure_ascii=False)}"]
             for note in steers(doc)]
    return rows


def _session_documents(doc_path):
    """This document and every older grill document beside it, oldest session first."""
    doc_path = Path(doc_path)
    docs = [format_1(read_json(doc_path))]
    docs += [format_1(read_json(path)) for path in page_documents(doc_path.parent, "grill-")
             if path.resolve() != doc_path.resolve()]
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
    pattern = re.compile(rf"^\*\*{re.escape(term)}\*\*:[^\n]*\n(?:(?!`)[^\n]+\n?)*", re.M)
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
    failures += [f"sign-off card {item['id']} is {item['state']} and holds no sign mark"
                 for rnd in doc["rounds"] for item in rnd["items"]
                 if signature_missing(item) and not _carried(doc, item, rnd["n"])]
    return failures


def _v2_failures(doc):
    """The end check of a version 2 page's lists (SDD §3 row "grill end check"); each failure starts with its code. A
    page with no story and no worked example keeps today's check: the log's Examples row (decision D-24)."""
    failures = []
    for question in doc.get("questions") or []:
        if question.get("state") == "open":
            failures.append(("question-open", f"{question['id']}: {question['question']} (who: {', '.join(question['who'])})"))
        if question.get("state") == "dropped" and not ((question.get("dropped") or {}).get("reason") or "").strip():
            failures.append(("drop-no-reason", f"{question['id']}: {question['question']}"))
    stories, examples = doc.get("stories") or [], doc.get("examples") or []
    covered = {story_id for example in examples for story_id in example.get("stories") or []}
    failures += [("story-without-example", f"{story['id']}: {story['text']}") for story in stories
                 if story["id"] not in covered]
    if stories or examples:
        kinds = {example.get("kind") for example in examples}
        failures += [("kind-missing", f"no worked example of kind {kind}") for kind in EXAMPLE_KINDS if kind not in kinds]
    return [f"{code}: {text}" for code, text in failures]


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


def _last_pass(block, session):
    """The round that the block's `Last pass` row holds for the session, else None."""
    found = LAST_PASS_ROW.match(block[0])
    return int(found.group(1)) if found and found.group(2) == session else None


def _last_pass_row(doc):
    return f"- Last pass: R{current_round(doc)['n']} · session {doc['session']['id']}"


def keep_last_pass(doc_path, log):
    """A log from before the `Last pass` row: write the row for a session whose end check passed. The current round of
    its page is the passed round, because a sync after a new round removes the gate row."""
    doc = format_1(read_json(doc_path))
    head, blocks, tail = _split(log)
    if not any(_last_pass(block, doc["session"]["id"]) is not None for block in blocks):
        write_text(log, _join(head, blocks + [[_last_pass_row(doc)]], tail))


def _changed(doc, passed):
    """Each point of the last passed round or earlier that changed later: a card a later card carries, and an entry
    with a change line on both sides of that round. An entry added later is new, not changed. No pass yet: nothing."""
    if passed is None:
        return []
    later = [card for rnd in doc["rounds"] if rnd["n"] > passed for card in rnd["items"]]
    changed = [{"id": item["id"], "kind": "card", "text": _first_text(item)}
               for rnd in doc["rounds"] if rnd["n"] <= passed for item in rnd["items"]
               if item["kind"] in ASKING and any(_carries_card(card, item["id"]) for card in later)]
    for name, (kind, field) in ENTRY_TEXT.items():
        for entry in doc.get(name) or []:
            rounds = [line.get("round", 0) for line in entry.get("changes") or []]
            if any(n <= passed for n in rounds) and any(n > passed for n in rounds):
                changed.append({"id": entry["id"], "kind": kind, "text": entry[field]})
    return changed


class _NoAnswer(Exception):
    """Git did not answer: no git program, or the shared time limit ran out."""


def _run_plan(spec_dir):
    """`<run branch>:plan/PLAN.md` when git holds the plan of this feature branch, else None. When git does not
    answer within GIT_LIMIT_S for all its calls, that spec with ` (not checked: <reason>)`: the plan can be stale."""
    deadline = time.monotonic() + GIT_LIMIT_S

    def git(*args):
        left = deadline - time.monotonic()
        if left <= 0:
            raise _NoAnswer(f"git took more than {GIT_LIMIT_S} s")
        try:
            done = subprocess.run(["git", "-C", str(spec_dir), *args], capture_output=True, stdin=subprocess.DEVNULL,
                                  timeout=left)
        except subprocess.TimeoutExpired as error:
            raise _NoAnswer(f"git took more than {GIT_LIMIT_S} s") from error
        except OSError as error:
            raise _NoAnswer(f"git did not run: {error}") from error
        return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else None
    run = f"<feature branch>{RUN_SUFFIX}"
    try:
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        if not branch or branch == "HEAD":
            return None
        run = branch + RUN_SUFFIX
        for ref in (f"refs/heads/{run}", f"refs/remotes/origin/{run}"):
            if git("cat-file", "-e", f"{ref}:plan/PLAN.md") is not None:
                return f"{run}:plan/PLAN.md"
    except _NoAnswer as error:
        return f"{run}:plan/PLAN.md (not checked: {error})"
    return None


def _later_documents(spec_dir):
    """Each document of the ticket that a later skill wrote and that exists (decision D-25). An entry is a file path,
    or the git spec `<run branch>:plan/PLAN.md` (read it with `git show`), with ` (not checked: <reason>)` when git
    did not answer."""
    spec_dir = Path(spec_dir)
    found = []
    for name, folder in (("PRD.md", "adr/requirements"), ("SDD.md", "adr/design")):
        found += [path for path in [spec_dir / name] if path.is_file()]
        found += sorted((spec_dir / folder).glob("*.md"))
    plan = _run_plan(spec_dir)
    return [path.as_posix() for path in found] + ([plan] if plan else [])


def gate(doc_path, log):
    doc = format_1(read_json(doc_path))
    head, blocks, tail = _split(log)
    failures = _doc_failures(doc) + (_v2_failures(doc) if is_version_2(doc) else []) + _log_failures(blocks)
    if failures:
        raise Refusal("exit-gate", f"{len(failures)} exit-gate checks failed", failures=failures)
    today, session = datetime.now(timezone.utc).strftime("%Y-%m-%d"), doc["session"]["id"]
    passed = next((n for n in (_last_pass(block, session) for block in blocks) if n is not None), None)
    blocks = [block for block in blocks
              if not block[0].startswith(GATE_PASSED) and _last_pass(block, session) is None]
    blocks += [[f"{GATE_PASSED} {today} · session {session}"], [_last_pass_row(doc)]]
    write_text(log, _join(head, blocks, tail))
    return {"ok": True, "passed": today, "stale": _later_documents(Path(doc_path).parent.parent),
            "changed": _changed(doc, passed)}


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
