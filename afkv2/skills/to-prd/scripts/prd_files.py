"""The disk side of to-prd, from the repository root.

`prd_files.py start --ticket KEY`: the paths of the spec folder; refuses a grill that is not settled.
`prd_files.py check --prd FILE`: the sections and the ids of a PRD, and against its last commit.
`prd_files.py index --index FILE --ticket KEY --summary-file FILE --adr-dir DIR`: create or update INDEX.md.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "grill" / "scripts"))

from grill_common import Parser, Refusal, serve, write_text  # noqa: E402
from grill_log import exit_gate_passed  # noqa: E402
from grill_start import read_config, ticket_slug  # noqa: E402

GRILL = "/afkv2:grill"
SECTIONS = ("Problem Statement", "Solution", "User Stories", "Acceptance Criteria", "Worked examples",
            "Access & validation policy", "Implementation Decisions", "Testing Decisions", "Out of Scope",
            "Further Notes")
ID = re.compile(r"\b(?:AC-\d{3,}|WE-\d{2,})\b")
CRITERION_LINE = re.compile(r"^\s*- \[[ xX]\] (.*)$")
CRITERION = re.compile(r"(AC-\d{3,})\b\s*(.*)$")
EXAMPLE = re.compile(r"^### (WE-\d{2,})\b\s*(.*)$")
FORMAT_FILE = Path(__file__).resolve().parents[1] / "INDEX-FORMAT.md"
TEMPLATE = re.compile(r"^```markdown index-template\n(.*?)^```$", re.S | re.M)
LEDGER_ROW = re.compile(r"^- (?:Ledger|Term): (.*) → (pending|unverified-external)\b", re.M)


def _section(markdown, name):
    found = re.search(rf"^## {re.escape(name)}[ \t]*\n(.*?)(?=^## |\Z)", markdown, re.S | re.M)
    return found.group(1) if found else None


def _newest_session(pages):
    names = sorted(path.stem[len("grill-"):] for path in pages.glob("grill-*.json"))
    return names[-1] if names else None


def _grill_rows(log):
    rows = LEDGER_ROW.findall(Path(log).read_text("utf-8"))
    return ([claim for claim, state in rows if state == "pending"],
            [claim for claim, state in rows if state == "unverified-external"])


def start(argv):
    parser = Parser(add_help=False)
    parser.add_argument("--ticket", required=True)
    args = parser.parse_args(argv)
    config = read_config()
    spec_dir = Path(config["spec_folder"]) / ticket_slug(args.ticket)
    log = spec_dir / "GRILL-LOG.md"
    session = _newest_session(spec_dir / "pages")
    if not log.exists() or session is None or not exit_gate_passed(log, session):
        missing = f"a passed exit gate in {log}"
        raise Refusal("missing-input", f"missing {missing}; {GRILL} writes it", missing=missing, writer=GRILL)
    pending, unverified = _grill_rows(log)
    if pending:
        raise Refusal("missing-input", f"pending rows in {log}: {pending}; {GRILL} closes them",
                      missing=pending, writer=GRILL)
    adr_dir = spec_dir / "adr" / "requirements"
    return {"ok": True, "ticket": args.ticket, "spec_dir": str(spec_dir), "log": str(log), "session": session,
            "prd": str(spec_dir / "PRD.md"), "adr_dir": str(adr_dir), "index": str(spec_dir / "INDEX.md"),
            "run_dir": str(spec_dir / "run"), "tracker_kind": config["tracker"]["kind"],
            "resume": (spec_dir / "PRD.md").exists(), "unverified_external": unverified}


def definitions(markdown):
    """Every (id, its text) that the Acceptance Criteria and Worked examples sections define, in order."""
    found = []
    for line in (_section(markdown, "Acceptance Criteria") or "").splitlines():
        bullet = CRITERION_LINE.match(line)
        criterion = CRITERION.match(bullet.group(1)) if bullet else None
        found.append(criterion.groups() if criterion else (None, bullet.group(1)) if bullet else None)
    for line in (_section(markdown, "Worked examples") or "").splitlines():
        if line.startswith("### "):
            example = EXAMPLE.match(line)
            found.append(example.groups() if example else (None, line))
    return [item for item in found if item]


def _number(identifier):
    return int(identifier.split("-")[1])


def id_problems(markdown):
    problems = [f"no section `## {name}`" for name in SECTIONS if _section(markdown, name) is None]
    seen = set()
    for identifier, text in definitions(markdown):
        if identifier is None:
            problems.append(f"no id on: {text}")
        elif identifier in seen:
            problems.append(f"{identifier} is defined twice")
        seen.add(identifier)
    if not any(identifier and identifier.startswith("AC-") for identifier in seen):
        problems.append("no acceptance criterion")
    return problems


def _same_text(text):
    return " ".join(text.split())


def renumber_problems(previous, current):
    """An id stays for good: its line stays, a new id is above every old one, and its text moves to no other id."""
    old, new = dict(definitions(previous)), dict(definitions(current))
    old.pop(None, None)
    new.pop(None, None)
    problems = [f"{identifier} is gone: keep its line with `retired: <why>`" for identifier in old if identifier not in new]
    old_text = {_same_text(text): identifier for identifier, text in old.items()}
    for identifier, text in new.items():
        moved = old_text.get(_same_text(text))
        if moved and moved != identifier and _same_text(old.get(identifier, "")) != _same_text(text):
            problems.append(f"the text of {moved} now stands under {identifier}: an id is never renumbered")
        family = identifier.split("-")[0]
        highest = max((_number(item) for item in old if item.startswith(family)), default=0)
        if identifier not in old and _number(identifier) <= highest:
            problems.append(f"{identifier} is new, but ids of its family go up to {highest}: an id is never reused")
    return problems


def _committed(prd):
    prd = Path(prd).resolve()
    run = subprocess.run(["git", "-C", str(prd.parent), "show", f"HEAD:./{prd.name}"],
                         capture_output=True, timeout=60)
    return run.stdout.decode("utf-8", "replace").replace("\r\n", "\n") if run.returncode == 0 else None


def check(argv):
    parser = Parser(add_help=False)
    parser.add_argument("--prd", required=True)
    args = parser.parse_args(argv)
    try:
        markdown = Path(args.prd).read_text("utf-8").replace("\r\n", "\n")
    except OSError as error:
        raise Refusal("unreadable", f"{args.prd}: {error}", 2) from error
    problems = id_problems(markdown)
    previous = _committed(args.prd)
    if previous is not None:
        problems += renumber_problems(previous, markdown)
    if problems:
        raise Refusal("bad-prd", "; ".join(problems), problems=problems)
    ids = [identifier for identifier, _ in definitions(markdown)]
    return {"ok": True, "criteria": sum(i.startswith("AC-") for i in ids), "examples": sum(i.startswith("WE-") for i in ids),
            "compared_with_commit": previous is not None}


def set_row(index, artifact, where, state):
    """Upsert the row of `artifact` in the artifact table, and change nothing else."""
    index = Path(index)
    lines = index.read_text("utf-8").split("\n")
    row = f"| {artifact} | {where} | {state} |"
    table = [number for number, line in enumerate(lines) if line.startswith("|")]
    for number in table:
        if [cell.strip() for cell in lines[number].split("|")][1] == artifact:
            lines[number] = row
            break
    else:
        if not table:
            raise Refusal("bad-index", f"{index} has no artifact table")
        lines.insert(table[-1] + 1, row)
    write_text(index, "\n".join(lines))


def _template(ticket):
    found = TEMPLATE.search(FORMAT_FILE.read_text("utf-8"))
    if not found:
        raise Refusal("bad-format", f"{FORMAT_FILE} has no index template")
    return found.group(1).replace("{TICKET-ID}", ticket)


def index(argv):
    parser = Parser(add_help=False)
    for name in ("--index", "--ticket", "--summary-file", "--adr-dir"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    path = Path(args.index)
    summary = Path(args.summary_file).read_text("utf-8").strip()
    text = path.read_text("utf-8") if path.exists() else _template(args.ticket)
    head, marker, tail = text.partition("\n## Artifacts")
    if not marker:
        raise Refusal("bad-index", f"{path} has no `## Artifacts` section")
    write_text(path, f"{head.splitlines()[0]}\n\n{summary}\n{marker}{tail}")
    count = len(list(Path(args.adr_dir).glob("*.md")))
    set_row(path, "PRD", "PRD.md", "draft")
    set_row(path, "Requirement ADRs", "adr/requirements/", f"{count} records" if count else "—")
    return {"ok": True, "index": str(path), "requirement_adrs": count}


VERBS = {"start": start, "check": check, "index": index}


def main(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", 2)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(serve(main))
