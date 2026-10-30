"""The disk side of propose-solution, from the repository root.

`design_files.py start --ticket KEY`: the paths of the spec folder; refuses a missing input and names its writer.
`design_files.py row --log FILE --kind K --text T`: one row of this skill's section of the grill log.
`design_files.py gate --doc FILE --spec-dir DIR`: the mechanical part of the design gate; lists every failure.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL.parent / "to-prd" / "scripts"))
sys.path.insert(0, str(SKILL.parent / "grill" / "scripts"))

import design_round as dr  # noqa: E402
import grill_log  # noqa: E402
import grill_start  # noqa: E402
import prd_files  # noqa: E402
from grill_common import Parser, Refusal, read_json, serve, write_text  # noqa: E402

TO_PRD = "/afkv2:to-prd"
SECTION = "## Solution design"
KINDS = {"Premise", "Spinoff", "Escape"}
PREMISE = re.compile(r"^- Premise: (.+) → (pending|refuted)\b", re.M)
GATE_PASSED = "- Settled: design gate passed"
DOC_PREFIX = f"{dr.SKILL_NAME}-"
TEMPLATE = re.compile(r"^```markdown sdd-template\n(.*?)^```$", re.S | re.M)
FENCE = re.compile(r"^```.*?^```$", re.S | re.M)
BLOCKERS = re.compile(r"\bTBD\b|\bTODO\b|\bFIXME\b|\bXXX\b|\?\?\?|\bADR-NNNN\b|_?FILL[_-]?IN_?|\[\?\]"
                      r"|<\?>|<placeholder>|<fill>|<TICKET-ID>|<NNNN>|<service>"
                      r"|\{Feature Name\}|\{YYYY-MM-DD\}|\{who\}|\{system\}"
                      r"|\(decide later\)|\(unresolved\)|\(open\)")
BLOCKING_LAYERS = {"L2", "L3", "L4", "L5", "L6", "L7", "L9"}
EMPTY_CELLS = {"", "—", "-"}
ADR_NAME = re.compile(r"^(\d{4})-.+\.md$")
ADR_SECTIONS = ("Decision", "Alternatives Considered")
SDD_NAME = "SDD.md"
OPEN_QUESTIONS = "§13 Open Questions"
REGISTER = "§0 Binding Contract"


def _new_session(pages):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    session, attempt = f"s-{stamp}", 1
    while (pages / f"{DOC_PREFIX}{session}.json").exists():
        attempt += 1
        session = f"s-{stamp}-{attempt}"
    return session


def gate_passed(log, session):
    return any(line.startswith(GATE_PASSED) and line.endswith(f"· session {session}")
               for line in Path(log).read_text("utf-8").splitlines())


def _open_session(pages, log):
    """The newest document whose session has no passed design gate; a run resumes it."""
    sessions = sorted(path.stem[len(DOC_PREFIX):] for path in pages.glob(f"{DOC_PREFIX}*.json"))
    return sessions[-1] if sessions and not gate_passed(log, sessions[-1]) else None


def ensure_section(log):
    log = Path(log)
    text = log.read_text("utf-8")
    if not re.search(rf"^{re.escape(SECTION)}$", text, re.M):
        write_text(log, text.rstrip("\n") + f"\n\n{SECTION}\n")


def start(argv):
    parser = Parser(add_help=False)
    parser.add_argument("--ticket")
    args = parser.parse_args(argv)
    if not args.ticket:
        raise Refusal("missing-input", "missing ticket key; the invocation of this skill gives it",
                      missing="ticket key", writer="the invocation of this skill")
    paths = prd_files.start(["--ticket", args.ticket])
    spec_dir, prd = Path(paths["spec_dir"]), Path(paths["prd"])
    if not prd.is_file():
        raise Refusal("missing-input", f"missing {prd}; {TO_PRD} writes it", missing=str(prd), writer=TO_PRD)
    log, pages = Path(paths["log"]), spec_dir / "pages"
    ensure_section(log)
    resumed = _open_session(pages, log)
    session = resumed or _new_session(pages)
    doc, raw_file = pages / f"{DOC_PREFIX}{session}.json", pages / f"{DOC_PREFIX}{session}.raw.txt"
    sdd = spec_dir / SDD_NAME
    return {"ok": True, "ticket": args.ticket, "spec_dir": spec_dir.as_posix(), "prd": prd.as_posix(), "log": log.as_posix(),
            "requirement_adrs": (spec_dir / "adr" / "requirements").as_posix(), "sdd": sdd.as_posix(),
            "sdd_exists": sdd.exists(), "adr_dir": (spec_dir / "adr" / "design").as_posix(), "doc": doc.as_posix(),
            "session": session, "resume": bool(resumed), "raw_file": raw_file.as_posix(),
            "raw_pending": grill_start._raw_pending(raw_file, doc), "unverified_external": paths["unverified_external"]}


def _section_parts(log):
    """(text up to the section's first row, its rows, the text after the section)."""
    text = Path(log).read_text("utf-8")
    found = re.search(rf"^{re.escape(SECTION)}\n", text, re.M)
    if not found:
        raise Refusal("no-section", f"{log} has no {SECTION} section")
    rest = text[found.end():]
    following = re.search(r"^## ", rest, re.M)
    end = following.start() if following else len(rest)
    return text[:found.end()], [line for line in rest[:end].splitlines() if line.strip()], rest[end:]


def _write_section(log, head, rows, tail):
    body = "\n" + "\n".join(rows) + "\n" if rows else ""
    write_text(log, head + body + ("\n" + tail if tail else ""))


def _upsert(log, key, row):
    head, rows, tail = _section_parts(log)
    rows = [row if line == key or line.startswith(key + " → ") else line for line in rows]
    if row not in rows:
        rows.append(row)
    _write_section(log, head, rows, tail)


def row(argv):
    parser = Parser(add_help=False)
    for name in ("--log", "--kind", "--text"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    if args.kind not in KINDS:
        raise Refusal("unknown-kind", f"{args.kind!r} is not one of {sorted(KINDS)}")
    value = " ".join(args.text.split())
    if args.kind == "Premise" and not grill_log.STATUS_ROW.match(value):
        raise Refusal("bad-row", f"a Premise row reads `<claim> → pending | verified (<citation>) | refuted (<citation>) | "
                                 f"unverified-external (human acknowledged)`: {args.text!r}")
    text = f"- {args.kind}: {value}"
    key = f"- {args.kind}: " if args.kind == "Escape" else f"- {args.kind}: {value.split(' → ')[0]}"
    if args.kind == "Escape":
        head, rows, tail = _section_parts(args.log)
        _write_section(args.log, head, [line for line in rows if not line.startswith(key)] + [text], tail)
    else:
        _upsert(args.log, key, text)
    return {"ok": True, "row": text}


def sdd_template():
    found = TEMPLATE.search((SKILL / "SDD-FORMAT.md").read_text("utf-8"))
    if not found:
        raise Refusal("bad-format", "SDD-FORMAT.md has no SDD template")
    return found.group(1)


def sdd_headings():
    return re.findall(r"^## (§.+)$", sdd_template(), re.M)


def _cells(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def blocker_problems(markdown):
    problems = []
    title_block, *sections = re.split(r"^## ", FENCE.sub("", markdown), flags=re.M)
    for heading, text in [("title block", title_block), *((part.splitlines()[0], part) for part in sections)]:
        problems += [f"{heading}: blocker `{token}`" for token in sorted(set(BLOCKERS.findall(text)))]
    return problems


def _open_question_problems(markdown):
    problems = []
    for line in (prd_files._section(markdown, OPEN_QUESTIONS) or "").splitlines():
        cells = _cells(line) if line.startswith("|") else []
        if len(cells) > 2 and cells[1] in BLOCKING_LAYERS and cells[2].lower() == "yes":
            problems.append(f"{OPEN_QUESTIONS}: an open question blocks the executor: {cells[0]}")
    return problems


def _register_problems(markdown, doc):
    rows = {}
    for line in (prd_files._section(markdown, REGISTER) or "").splitlines():
        found = re.match(r"^\| (HL-\d)\b", line)
        if found:
            rows[found.group(1)] = _cells(line)
    problems = []
    for key in dr.group_keys("locked"):
        cells = rows.get(key)
        if cells is None:
            problems.append(f"{key}: no row in the §0 register")
            continue
        status, signer, wording = (cells + ["", "", ""])[2:5]
        node = dr.node_id("locked", key)
        asked = bool(dr._cards(doc, node))
        if status == "signed":
            if signer in EMPTY_CELLS or wording in EMPTY_CELLS:
                problems.append(f"{key}: signed needs who, date and the human's words")
            if not dr.is_settled(doc, node):
                problems.append(f"{key}: signed, but no card holds its signature")
        elif status == "n/a":
            if asked:
                problems.append(f"{key}: n/a, but a card asks it")
            if wording in EMPTY_CELLS:
                problems.append(f"{key}: n/a needs its reason")
        else:
            problems.append(f"{key}: status is {status or 'empty'}; the register holds signed or n/a")
    return problems


def _sdd_problems(path, doc):
    if not path.is_file():
        return [f"no {SDD_NAME}: write it by SDD-FORMAT.md"]
    markdown = path.read_text("utf-8").replace("\r\n", "\n")
    problems = [f"no section `## {heading}`" for heading in sdd_headings()
                if prd_files._section(markdown, heading) is None]
    return problems + blocker_problems(markdown) + _open_question_problems(markdown) + _register_problems(markdown, doc)


def _adr_problems(paths):
    problems = []
    for path in paths:
        found = ADR_NAME.match(path.name)
        if not found:
            problems.append(f"{path.name}: the name must be `NNNN-<title>.md`")
            continue
        text = path.read_text("utf-8").replace("\r\n", "\n")
        title = f"# ADR-{found.group(1)} — "
        if not text.startswith(title):
            problems.append(f"{path.name}: the title must start `{title}`")
        if not re.search(r"^> Status: \S", text, re.M):
            problems.append(f"{path.name}: no `> Status:` line")
        problems += [f"{path.name}: no section `## {name}`" for name in ADR_SECTIONS if not re.search(rf"^## {name}$", text, re.M)]
    return problems


def _fork_problems(doc, records):
    problems = []
    for rnd in doc["rounds"]:
        for item in rnd["items"]:
            settled = item["state"] in ("settled_by_mark", "settled_by_note")
            if item["kind"] == "debate" and settled and not re.search(rf"(?<![\w-]){re.escape(item['id'])}(?![\w-])", records):
                problems.append(f"fork {item['id']} stands in no ADR and not in {SDD_NAME}")
    return problems


def _premise_problems(log):
    head, rows, tail = _section_parts(log)
    return [f"{state}: {claim}" for claim, state in PREMISE.findall("\n".join(rows))]


def gate(argv):
    parser = Parser(add_help=False)
    for name in ("--doc", "--spec-dir"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    doc, spec_dir = read_json(args.doc), Path(args.spec_dir)
    log, sdd, adr_dir = spec_dir / "GRILL-LOG.md", spec_dir / SDD_NAME, spec_dir / "adr" / "design"
    adrs = sorted(adr_dir.glob("*.md"))
    records = "\n".join(path.read_text("utf-8") for path in [*adrs, sdd] if path.is_file())
    failures = [*grill_log._doc_failures(doc), *dr.unfinished(doc), *_premise_problems(log),
                *_sdd_problems(sdd, doc), *_adr_problems(adrs), *_fork_problems(doc, records)]
    if failures:
        raise Refusal("design-gate", f"{len(failures)} design-gate checks failed", failures=failures)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    head, rows, tail = _section_parts(log)
    session = f"· session {doc['session']['id']}"
    rows = [line for line in rows if not (line.startswith(GATE_PASSED) and line.endswith(session))]
    _write_section(log, head, [*rows, f"{GATE_PASSED} {today} {session}"], tail)
    index = spec_dir / "INDEX.md"
    if index.is_file():
        prd_files.set_row(index, "SDD", SDD_NAME, "draft")
        prd_files.set_row(index, "Design ADRs", "adr/design/", f"{len(adrs)} records" if adrs else "—")
    return {"ok": True, "passed": today, "design_adrs": len(adrs), "index_missing": not index.is_file()}


VERBS = {"start": start, "row": row, "gate": gate}


def main(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", 2)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(serve(main))
