"""The disk side of propose-verification, from the repository root (SDD §8 row "propose-verification files").

`verification_files.py start --ticket KEY [--target REF]`: the session paths, and the live state of the repository
  config: {block, proven_here}. Refuses `missing-input` naming the writer of a missing PRD, SDD or grill log.
  The newest session with a page document and no `written` row resumes.
`verification_files.py sync --doc FILE --log FILE`: copies each new note of the page into this skill's log section.
`verification_files.py write --spec-dir DIR --plan FILE --doc FILE [--target REF]`: writes VERIFICATION.md.
  Format and refusal codes: VERIFICATION-FORMAT.md. On a pass it writes the INDEX.md row and, for a page with a
  session, the `written` row of the log.

`--target` names the branch the feature merges into; by default the first of origin/HEAD, origin/main,
origin/master, main and master that exists. A commit of this feature is HEAD, or a commit of HEAD that the target
does not hold.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
PLUGIN = SKILL.parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))
sys.path.insert(0, str(SKILL.parent / "to-prd" / "scripts"))
sys.path.insert(0, str(SKILL.parent / "use-lavish" / "scripts"))

import afkv2_config  # noqa: E402
import prd_files  # noqa: E402
from grill_common import Parser, Refusal, page_documents, read_json, serve, write_text  # noqa: E402
from page_home import ticket_slug  # noqa: E402
from round_document import session_notes  # noqa: E402

SKILL_NAME = "propose-verification"
DOC_PREFIX = f"{SKILL_NAME}-"
SECTION = "## Verification plan"
WRITTEN = "- Settled: verification written"
NOTE_ROW = re.compile(r"^- Note: (\S+) · ")
FILE_NAME = "VERIFICATION.md"
INDEX_ROW = "Verification plan"
WRITERS = {"PRD.md": "/afkv2:to-prd", "SDD.md": "/afkv2:propose-solution", "GRILL-LOG.md": "/afkv2:grill-requirements"}
TARGETS = ("origin/HEAD", "origin/main", "origin/master", "main", "master")
GIT_SECONDS = 60

LEVELS = ("static", "unit", "integration", "contract", "api", "ui-e2e", "acceptance")
HIGH = frozenset({"api", "ui-e2e", "acceptance"})
ROW_ID = re.compile(r"VR-\d{3}")
CRITERION_ID = re.compile(r"AC-\d{3,}")
RETIRED = re.compile(r"retired: \S.*")
LOWER = re.compile(rf"lower: ({'|'.join(LEVELS)}) to ({'|'.join(LEVELS)}) · (\S+)")
EMPTY = "—"

ROWS_HEADING, INTERNAL_HEADING, BOUNDARIES_HEADING = "Plan rows", "Criteria with no user-visible outcome", "Boundaries"
COLUMNS = ("Id", "Criteria", "Story", "Given", "When", "Then", "Level", "Tier", "Data", "Environment", "Status")
FIELDS = ("id", "criteria", "story", "given", "when", "then", "level", "tier", "data", "environment", "status")
TEXT_FIELDS = ("given", "when", "then")
OPTIONAL_FIELDS = ("story", "data", "environment")
CELL_SPLIT = re.compile(r"(?<!\\)\|")


def tier_of(level):
    return "high" if level in HIGH else "low"


# --- the live state (SDD §6 I-13) ---------------------------------------------------------------------------------

def _git(repo_root, *args):
    """The stripped output, or None when git refuses."""
    try:
        done = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                              timeout=GIT_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _feature_commits(repo_root, target):
    """HEAD and each commit of HEAD that the target does not hold."""
    head = _git(repo_root, "rev-parse", "HEAD")
    if head is None:
        raise Refusal("git-failed", f"{repo_root}: git rev-parse HEAD failed")
    refs = [target] if target else list(TARGETS)
    ref = next((name for name in refs if _git(repo_root, "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}")), None)
    if ref is None:
        raise Refusal("no-target", f"none of {', '.join(refs)} names a commit; pass --target with the branch the "
                                   f"feature merges into")
    listed = _git(repo_root, "rev-list", f"{ref}..HEAD") or ""
    return {head, *listed.split()}


def _config(repo_root):
    config = afkv2_config.read_config(repo_root)
    if not config["ok"]:
        raise Refusal(config["error"]["code"], config["error"]["reason"])
    return config


def live_state(repo_root, target=None):
    """{block, proven_here}: the config holds a live block, and its proof ran at a commit of this feature."""
    live = _config(repo_root).get("live")
    if live is None:
        return {"block": False, "proven_here": False}
    head = live.get("proven_head")
    full = _git(repo_root, "rev-parse", "--verify", "--quiet", f"{head}^{{commit}}") if head else None
    return {"block": True, "proven_here": full is not None and full in _feature_commits(repo_root, target)}


# --- start and sync -----------------------------------------------------------------------------------------------

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


def _ensure_section(log):
    text = Path(log).read_text("utf-8")
    if not re.search(rf"^{re.escape(SECTION)}$", text, re.M):
        write_text(log, text.rstrip("\n") + f"\n\n{SECTION}\n")


def _written(log, session):
    return any(line.startswith(WRITTEN) and line.endswith(f"· session {session}") for line in _section_parts(log)[1])


def _new_session(pages):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    session, attempt = f"s-{stamp}", 1
    while (pages / f"{DOC_PREFIX}{session}.json").exists():
        attempt += 1
        session = f"s-{stamp}-{attempt}"
    return session


def start(argv):
    parser = Parser(add_help=False)
    parser.add_argument("--ticket")
    parser.add_argument("--target")
    args = parser.parse_args(argv)
    if not args.ticket:
        raise Refusal("missing-input", "missing ticket key; the invocation of this skill gives it",
                      missing="ticket key", writer="the invocation of this skill")
    config = _config(None)
    spec_dir = Path(config["spec_folder"]) / ticket_slug(args.ticket)
    for name, writer in WRITERS.items():
        if not (spec_dir / name).is_file():
            raise Refusal("missing-input", f"missing {spec_dir / name}; {writer} writes it", missing=str(spec_dir / name),
                          writer=writer)
    log, pages = spec_dir / "GRILL-LOG.md", spec_dir / "pages"
    _ensure_section(log)
    sessions = sorted(path.stem[len(DOC_PREFIX):] for path in page_documents(pages, DOC_PREFIX))
    resumed = sessions[-1] if sessions and not _written(log, sessions[-1]) else None
    session = resumed or _new_session(pages)
    doc, raw_file = pages / f"{DOC_PREFIX}{session}.json", pages / f"{DOC_PREFIX}{session}.raw.txt"
    verification = spec_dir / FILE_NAME
    return {"ok": True, "ticket": args.ticket, "spec_dir": spec_dir.as_posix(), "prd": (spec_dir / "PRD.md").as_posix(),
            "sdd": (spec_dir / "SDD.md").as_posix(), "log": log.as_posix(),
            "requirement_adrs": (spec_dir / "adr" / "requirements").as_posix(),
            "design_adrs": (spec_dir / "adr" / "design").as_posix(), "verification": verification.as_posix(),
            "verification_exists": verification.is_file(), "doc": doc.as_posix(), "session": session,
            "resume": resumed is not None, "raw_file": raw_file.as_posix(),
            "live": live_state(config["repo_root"], args.target)}


def sync(argv):
    parser = Parser(add_help=False)
    for name in ("--doc", "--log"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    for path in (args.doc, args.log):
        if not Path(path).is_file():
            raise Refusal("missing-input", f"missing {path}", missing=str(path))
    doc = read_json(args.doc)
    head, rows, tail = _section_parts(args.log)
    known = {found.group(1) for found in map(NOTE_ROW.match, rows) if found}
    new = [f"- Note: {note['id']} · R{note['round']} · on {note['target']}: {json.dumps(note['text'], ensure_ascii=False)}"
           for note in session_notes(doc) if note["id"] not in known]
    if new:
        _write_section(args.log, head, rows + new, tail)
    return {"ok": True, "notes": len(new), "rows": len(known) + len(new)}


# --- the plan rows ------------------------------------------------------------------------------------------------

def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _marked(doc, card):
    """True when a card of the page is settled by the developer's mark."""
    return any(item.get("id") == card and item.get("state") == "settled_by_mark"
               and (item.get("settled") or {}).get("by") == "mark"
               for rnd in (doc or {}).get("rounds") or [] for item in rnd.get("items") or [])


def _check_row(raw, doc):
    where = f"row {raw.get('id') if isinstance(raw, dict) else raw!r}"
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not ROW_ID.fullmatch(raw["id"]):
        raise Refusal("bad-row", f"{where}: id is `VR-NNN`, 3 digits")
    unknown = sorted(set(raw) - set(FIELDS))
    if unknown:
        raise Refusal("bad-row", f"{where}: unknown fields {unknown}")
    level = raw.get("level")
    if level not in LEVELS:
        raise Refusal("bad-row", f"{where}: level {level!r} is not one of {', '.join(LEVELS)}")
    if raw.get("tier") not in (None, tier_of(level)):
        raise Refusal("tier-mismatch", f"{where}: level {level} is tier {tier_of(level)}, not {raw['tier']!r}")
    for field in TEXT_FIELDS:
        if not _text(raw.get(field)):
            raise Refusal("bad-row", f"{where}: {field} is 1 sentence")
    for field in OPTIONAL_FIELDS:
        if raw.get(field) is not None and not _text(raw[field]):
            raise Refusal("bad-row", f"{where}: {field} is text or null")
    criteria = raw.get("criteria")
    if not isinstance(criteria, list) or not all(isinstance(c, str) and CRITERION_ID.fullmatch(c) for c in criteria):
        raise Refusal("bad-row", f"{where}: criteria is a list of `AC-NNN` ids")
    if not criteria and tier_of(level) == "high":
        raise Refusal("bad-row", f"{where}: a high-level row names the criteria it proves")
    status = raw.get("status", "active")
    lower = LOWER.fullmatch(status) if isinstance(status, str) else None
    if not (status == "active" or (isinstance(status, str) and RETIRED.fullmatch(status)) or lower):
        raise Refusal("bad-row", f"{where}: status is `active`, `retired: <why>` or `lower: <from> to <to> · <card>`")
    if lower:
        higher, lowered, card = lower.groups()
        if LEVELS.index(lowered) >= LEVELS.index(higher) or lowered != level:
            raise Refusal("bad-row", f"{where}: `lower:` goes from a higher level to the row's level {level}")
        if not _marked(doc, card):
            raise Refusal("lower-level-unmarked", f"{where}: card {card} holds no mark of the developer for the lower level")
    return {"id": raw["id"], "criteria": list(criteria), "story": raw.get("story"), "given": raw["given"].strip(),
            "when": raw["when"].strip(), "then": raw["then"].strip(), "level": level, "tier": tier_of(level),
            "data": raw.get("data"), "environment": raw.get("environment"), "status": status}


def _covers_high(entry):
    """An active high-level row, or a `lower:` row from a high level."""
    if entry["status"] == "active":
        return entry["tier"] == "high"
    lower = LOWER.fullmatch(entry["status"])
    return bool(lower) and lower.group(1) in HIGH


def _criteria(prd):
    """(active ids, retired ids) of the PRD's acceptance criteria."""
    active, retired = [], set()
    for identifier, text in prd_files.definitions(Path(prd).read_text("utf-8")):
        if identifier and identifier.startswith("AC-"):
            (retired.add(identifier) if text.strip().startswith("retired:") else active.append(identifier))
    return active, retired


def _check_internal(internal, known):
    if not isinstance(internal, list):
        raise Refusal("bad-payload", "internal is a list of {criterion, why}")
    exempt = {}
    for entry in internal:
        if not isinstance(entry, dict) or set(entry) != {"criterion", "why"} or not _text(entry.get("why")):
            raise Refusal("bad-payload", f"internal entry {entry!r}: {{criterion, why}}")
        if entry["criterion"] not in known:
            raise Refusal("criterion-unknown", f"internal names {entry['criterion']}, which the PRD does not hold")
        exempt[entry["criterion"]] = entry["why"].strip()
    return exempt


def _check_boundaries(boundaries, rows):
    if not isinstance(boundaries, list):
        raise Refusal("bad-payload", "boundaries is a list of {boundary, contract, rows, ticket}")
    by_id = {entry["id"]: entry for entry in rows}
    checked = []
    for entry in boundaries:
        if (not isinstance(entry, dict) or set(entry) != {"boundary", "contract", "rows", "ticket"}
                or not _text(entry.get("boundary")) or not isinstance(entry.get("contract"), bool)
                or not isinstance(entry.get("rows"), list)):
            raise Refusal("bad-payload", f"boundary {entry!r}: {{boundary, contract, rows, ticket}}")
        named = [by_id.get(rid) for rid in entry["rows"]]
        if None in named:
            raise Refusal("boundary-uncovered", f"boundary {entry['boundary']}: rows {entry['rows']} name an unknown row")
        active = [row for row in named if row["status"] == "active"]
        if entry["contract"] and not any(row["level"] == "contract" for row in active):
            raise Refusal("boundary-uncovered", f"boundary {entry['boundary']}: it has contract tests, so it needs an "
                                                f"active contract row")
        if not entry["contract"] and not (_text(entry.get("ticket")) and any(row["tier"] == "high" for row in active)):
            raise Refusal("boundary-uncovered", f"boundary {entry['boundary']}: no contract test, so it needs a "
                                                f"proposed ticket and an active row at the API level or higher")
        checked.append({**entry, "boundary": entry["boundary"].strip(),
                        "ticket": entry["ticket"].strip() if _text(entry.get("ticket")) else None})
    return checked


def _app_line(app, doc, repo_root, target):
    if app == "config":
        if not live_state(repo_root, target)["proven_here"]:
            raise Refusal("live-unproven", "the live block of the repository config was not proven at a commit of "
                                           "this feature: run live_build.py prove, and commit the config")
        live = _config(repo_root)["live"]
        return f"config · proven at {live['proven_head']} on {live['proven_at']}"
    if isinstance(app, dict) and set(app) == {"none"} and _text(app["none"]):
        if not _marked(doc, app["none"]):
            raise Refusal("live-unproven", f"`App: none` needs the developer's mark on card {app['none']}")
        return f"none · {app['none']}"
    raise Refusal("bad-payload", f"app is \"config\" or {{\"none\": <card id>}}, not {app!r}")


# --- the file -----------------------------------------------------------------------------------------------------

def _cell(value):
    if value is None or value == "" or value == []:
        return EMPTY
    text = ", ".join(value) if isinstance(value, list) else str(value)
    return " ".join(text.split()).replace("|", "\\|")


def _table(header, lines):
    rows = [f"| {' | '.join(header)} |", f"|{'|'.join('---' for _ in header)}|"]
    return "\n".join([*rows, *(f"| {' | '.join(_cell(value) for value in line)} |" for line in lines)])


def _render(ticket, app_line, rows, exempt, boundaries):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return "\n".join([
        f"# Verification plan — {ticket}", "", "> Parent PRD: PRD.md", "> Parent SDD: SDD.md", f"> App: {app_line}",
        f"> Last updated: {today}", "", f"## {ROWS_HEADING}", "",
        _table(COLUMNS, [[row[field] for field in FIELDS] for row in rows]), "", f"## {INTERNAL_HEADING}", "",
        _table(("Criterion", "Why"), list(exempt.items())), "", f"## {BOUNDARIES_HEADING}", "",
        _table(("Boundary", "Contract test", "Rows", "Ticket"),
               [[entry["boundary"], "yes" if entry["contract"] else "no", entry["rows"], entry["ticket"]]
                for entry in boundaries]), ""])


def write_verification(spec_dir, plan, doc, *, repo_root=None, target=None, session=None):
    """Check the plan, then write `<spec_dir>/VERIFICATION.md`; write nothing on a refusal (SDD §6 I-2, I-13)."""
    spec_dir = Path(spec_dir)
    if not isinstance(plan, dict) or not _text(plan.get("ticket")) or not isinstance(plan.get("rows"), list):
        raise Refusal("bad-payload", "the plan is one object with ticket, app, rows, internal and boundaries")
    unknown = sorted(set(plan) - {"ticket", "app", "rows", "internal", "boundaries"})
    if unknown:
        raise Refusal("bad-payload", f"unknown plan fields {unknown}")
    rows = [_check_row(raw, doc) for raw in plan["rows"]]
    ids = [row["id"] for row in rows]
    repeated = sorted({rid for rid in ids if ids.count(rid) > 1})
    if repeated:
        raise Refusal("bad-row", f"ids repeat: {', '.join(repeated)}")
    path = spec_dir / FILE_NAME
    dropped = [entry["id"] for entry in read_rows(path) if entry["id"] not in ids] if path.is_file() else []
    if dropped:
        raise Refusal("row-dropped", f"{', '.join(dropped)} stand in {path}: retire a row in place, never drop it")
    active, retired = _criteria(spec_dir / "PRD.md")
    for row in rows:
        unknown = [c for c in row["criteria"] if c not in active and c not in retired]
        if unknown:
            raise Refusal("criterion-unknown", f"row {row['id']}: {', '.join(unknown)} is not in the PRD")
        stale = [c for c in row["criteria"] if c in retired]
        if stale and not row["status"].startswith("retired:"):
            raise Refusal("criterion-retired", f"row {row['id']}: {', '.join(stale)} is retired in the PRD")
    exempt = _check_internal(plan.get("internal", []), set(active) | retired)
    covered = {c for row in rows if _covers_high(row) for c in row["criteria"]}
    missing = [c for c in active if c not in exempt and c not in covered]
    if missing:
        raise Refusal("ac-no-high-row", f"{', '.join(missing)} has a user-visible outcome and no active high-level row",
                      criteria=missing)
    boundaries = _check_boundaries(plan.get("boundaries", []), rows)
    root = Path(repo_root) if repo_root else Path(_config(spec_dir)["repo_root"])
    app_line = _app_line(plan.get("app"), doc, root, target)
    write_text(path, _render(plan["ticket"].strip(), app_line, rows, exempt, boundaries))
    index = spec_dir / "INDEX.md"
    if index.is_file():
        prd_files.set_row(index, INDEX_ROW, FILE_NAME, "draft")
    session = session or ((doc or {}).get("session") or {}).get("id")
    log = spec_dir / "GRILL-LOG.md"
    if session and log.is_file():
        _ensure_section(log)
        head, lines, tail = _section_parts(log)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        _write_section(log, head, [*lines, f"{WRITTEN} {today} · session {session}"], tail)
    return {"ok": True, "verification": path.as_posix(), "rows": len(rows),
            "high": sum(row["tier"] == "high" for row in rows), "index_missing": not index.is_file()}


def _cells(line):
    return [cell.strip().replace("\\|", "|") for cell in CELL_SPLIT.split(line.strip().strip("|"))]


def _section_table(markdown, heading):
    """The header and the body rows of the first table under `## heading`, or None without the section."""
    found = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", markdown, re.S | re.M)
    if not found:
        return None
    lines = [line for line in found.group(1).splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return [], []
    return _cells(lines[0]), [_cells(line) for line in lines[2:]]


def read_rows(path):
    """The plan rows of VERIFICATION.md, read by header name: one dict per row with the keys of FIELDS."""
    path = Path(path)
    try:
        markdown = path.read_text("utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError) as error:
        raise Refusal("unreadable", f"{path}: {error}") from error
    table = _section_table(markdown, ROWS_HEADING)
    if table is None:
        raise Refusal("bad-verification", f"{path} has no `## {ROWS_HEADING}` section")
    header, body = table
    missing = [name for name in COLUMNS if name not in header]
    if missing:
        raise Refusal("bad-verification", f"{path}: the plan rows table has no column {', '.join(missing)}")
    rows = []
    for cells in body:
        values = dict(zip(header, cells))
        entry = {field: (None if values.get(column, EMPTY) == EMPTY else values.get(column))
                 for field, column in zip(FIELDS, COLUMNS)}
        entry["criteria"] = [c.strip() for c in (entry["criteria"] or "").split(",") if c.strip()]
        rows.append(entry)
    return rows


def write(argv):
    parser = Parser(add_help=False)
    for name in ("--spec-dir", "--plan", "--doc"):
        parser.add_argument(name, required=True)
    parser.add_argument("--target")
    args = parser.parse_args(argv)
    return write_verification(args.spec_dir, read_json(args.plan), read_json(args.doc), target=args.target)


VERBS = {"start": start, "sync": sync, "write": write}


def main(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", 2)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(serve(main))
