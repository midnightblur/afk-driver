"""The disk and git side of to-subtasks, from the worktree of the feature branch.

`plan_files.py start --ticket KEY`: the input paths and the run branch; refuses a missing input and names its writer.
`plan_files.py citations --plan DIR --spec-dir DIR`: each citation of each contract resolves; lists every failure.
`plan_files.py commit --plan DIR --message TEXT`: commits `plan/` on the run branch; refuses a file that is no run file.
`plan_files.py division --plan DIR --doc FILE --session S --ticket KEY --why FILE [--replace]`: the approval round.
`plan_files.py approve --plan DIR --doc FILE --spec-dir DIR`: writes the division line after the developer's approval.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILLS = SCRIPTS.parents[1]
sys.path[:0] = [str(SCRIPTS), str(SKILLS / "propose-solution" / "scripts"), str(SKILLS / "to-prd" / "scripts"), str(SKILLS / "grill" / "scripts")]

import check_plan as cp  # noqa: E402
import design_files  # noqa: E402
import grill_start  # noqa: E402
import prd_files  # noqa: E402
import round_document as rd  # noqa: E402
from grill_common import EXIT_UNREADABLE, Parser, Refusal, read_json, serve, write_text  # noqa: E402

TO_PRD = "/afkv2:to-prd"
PROPOSE = "/afkv2:propose-solution"
ADR_WRITERS = {"requirements": TO_PRD, "design": PROPOSE}
ADR_LINK = re.compile(r"adr/(requirements|design)/[\w.-]+\.md")
PAGE_SKILL = "propose-solution"
SESSION_PREFIX = "division-"
DOC_PREFIX = f"{PAGE_SKILL}-"
CARD_PREFIX = "division-"
RUN_FOLDER = "plan"
SPEC_FILES = {"PRD.md", "SDD.md", "GRILL-LOG.md", "INDEX.md", "VERIFICATION-PLAN.md", "DESIGN-BRIEF.md"}
SPEC_FOLDERS = {"adr", "pages"}
SETTLED = {"settled_by_mark", "settled_by_note"}
UNSTAMPED_LINES = (cp.DIVISION_MARK, "> Last updated:")
GIT_LIMIT_S = 120
TAG = r"\(((?:[^()\"]|\"[^\"]*\")*)\)"
BULLET_TAG = re.compile(TAG + r"\s*$")
EXCERPT_TAG = re.compile(r"^>\s*" + TAG, re.M)
SECTION_ID = re.compile(r"§([^\s,;]+)")
QUOTED_TEXT = re.compile(r"\"([^\"]*)\"")
ADR_CITATION = re.compile(r"ADR-(\d{4})(?:\s+(design|requirements))?\b")
PLAN_CITATION = re.compile(r"PLAN\.md decision (\S+)")
DESIGN_REF_SDD = re.compile(r"SDD: \S*#§(\S+)")
DESIGN_REF_ADR = re.compile(r"ADR: (\S+)")


def _git(cwd, *args):
    """git's stdout as text; a refusal names the command and git's reason."""
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, input=b"", timeout=GIT_LIMIT_S)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Refusal("git-failed", f"git {args[0]} gave no answer: {error}") from error
    if done.returncode:
        raise Refusal("git-failed", f"git {' '.join(args)}: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout.decode("utf-8", "replace").strip()


def _git_ok(cwd, *args):
    try:
        _git(cwd, *args)
    except Refusal:
        return False
    return True


def _missing(missing, writer):
    return Refusal("missing-input", f"missing {missing}; {writer} writes it", missing=str(missing), writer=writer)


def _check_inputs(spec_dir):
    prd, sdd = spec_dir / "PRD.md", spec_dir / design_files.SDD_NAME
    if not prd.is_file():
        raise _missing(prd, TO_PRD)
    if not sdd.is_file():
        raise _missing(sdd, PROPOSE)
    prd_text, sdd_text = cp.read_text(prd), cp.read_text(sdd)
    for found in ADR_LINK.finditer(prd_text + "\n" + sdd_text):
        if not (spec_dir / found.group(0)).is_file():
            raise _missing(spec_dir / found.group(0), ADR_WRITERS[found.group(1)])
    blockers = design_files.blocker_problems(sdd_text) + design_files._open_question_problems(sdd_text)
    if blockers:
        raise Refusal("sdd-not-ready", f"{sdd} still blocks an executor; {PROPOSE} closes it", problems=blockers, writer=PROPOSE)
    return prd, sdd


def _feature_branch():
    branch = _git(".", "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD" or branch.endswith(cp.RUN_SUFFIX):
        raise Refusal("not-feature-branch", f"run this from the worktree of the feature branch, not {branch}")
    return branch


def _new_run_branch(run_branch):
    """An orphan branch: one commit on the empty tree, so it can hold no spec-folder file."""
    tree = _git(".", "mktree")
    commit = _git(".", "commit-tree", tree, "-m", "Run branch: the plan and the run files of this feature")
    _git(".", "branch", run_branch, commit)


def _run_worktree(run_branch):
    """The worktree of the run branch; it creates the branch and the worktree when they do not exist."""
    ref = f"refs/heads/{run_branch}"
    for block in _git(".", "worktree", "list", "--porcelain").split("\n\n"):
        lines = block.splitlines()
        if f"branch {ref}" in lines:
            return lines[0].removeprefix("worktree "), False
    if not _git_ok(".", "rev-parse", "--verify", "--quiet", ref) and not _git_ok(".", "fetch", "origin", f"{run_branch}:{run_branch}"):
        _new_run_branch(run_branch)
    worktree = _git(".", "rev-parse", "--show-toplevel") + cp.RUN_SUFFIX
    _git(".", "worktree", "add", "-q", worktree, run_branch)
    return worktree, True


def _session_of(pages, plan):
    """The newest page document while the plan is not approved, else a new session."""
    newest = sorted(path.stem[len(DOC_PREFIX):] for path in pages.glob(f"{DOC_PREFIX}{SESSION_PREFIX}*.json"))
    plan_file = plan / "PLAN.md"
    approved = plan_file.is_file() and cp.division_of(cp.read_text(plan_file))[0]["approved"]
    if newest and not approved:
        return newest[-1], True
    return f"{SESSION_PREFIX}{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}", False


def start(argv):
    parser = Parser(add_help=False)
    parser.add_argument("--ticket")
    args = parser.parse_args(argv)
    if not args.ticket:
        raise _missing("ticket key", "the invocation of this skill")
    branch = _feature_branch()
    config = grill_start.read_config()
    spec_dir = Path(config["spec_folder"]) / grill_start.ticket_slug(args.ticket)
    prd, sdd = _check_inputs(spec_dir)
    run_branch = branch + cp.RUN_SUFFIX
    worktree, created = _run_worktree(run_branch)
    plan, pages, top = Path(worktree) / RUN_FOLDER, spec_dir / "pages", _git(".", "rev-parse", "--show-toplevel")
    session, resume = _session_of(pages, plan)
    doc, raw_file = pages / f"{DOC_PREFIX}{session}.json", pages / f"{DOC_PREFIX}{session}.raw.txt"
    return {"ok": True, "ticket": args.ticket, "spec_dir": spec_dir.as_posix(), "prd": prd.as_posix(), "sdd": sdd.as_posix(),
            "parent_prd": Path(os.path.relpath(prd.resolve(), Path(top).resolve())).as_posix(),
            "parent_sdd": Path(os.path.relpath(sdd.resolve(), Path(top).resolve())).as_posix(),
            "requirement_adrs": (spec_dir / "adr" / "requirements").as_posix(), "design_adrs": (spec_dir / "adr" / "design").as_posix(),
            "branch": branch, "run_branch": run_branch, "worktree": worktree, "created": created, "plan": plan.as_posix(),
            "plan_exists": (plan / "PLAN.md").is_file(), "doc": doc.as_posix(), "session": session, "resume": resume,
            "raw_file": raw_file.as_posix(), "raw_pending": grill_start._raw_pending(raw_file, doc)}


# Citations.

def _sdd_sections(sdd_text):
    found, name = {}, None
    for line in sdd_text.splitlines():
        heading = re.match(r"## §(\S+)", line)
        if line.startswith("## "):
            name = heading.group(1) if heading else None
            if name:
                found[name] = []
        if name:
            found[name].append(line)
    return {key: "\n".join(lines) for key, lines in found.items()}


class Sources:
    def __init__(self, spec_dir, plan):
        self.spec_dir = Path(spec_dir)
        self.prd = cp.read_text(self.spec_dir / "PRD.md")
        self.sdd = _sdd_sections(cp.read_text(self.spec_dir / design_files.SDD_NAME))
        self.plan = cp.read_text(Path(plan) / "PLAN.md")

    def _prd_problem(self, part):
        ids = SECTION_ID.findall(part)
        missing = [item for item in ids if not re.search(rf"(?<![\w-]){re.escape(item)}(?![\w-])", self.prd)]
        return f"`{part}` names no id in the PRD" if not ids or missing else None

    def _sdd_problem(self, part):
        ids = SECTION_ID.findall(part)
        if not ids or any(item not in self.sdd for item in ids):
            return f"`{part}` names no section of the SDD"
        text = "\n".join(self.sdd[item] for item in ids)
        lost = [quote for quote in QUOTED_TEXT.findall(part) if quote not in text]
        return f"`{part}`: the cited section does not hold {lost}" if lost else None

    def _adr_problem(self, part):
        number, tier = ADR_CITATION.match(part).groups()
        for folder in [tier] if tier else ADR_WRITERS:
            if list((self.spec_dir / "adr" / folder).glob(f"{number}-*.md")):
                return None
        return f"`{part}` names no ADR file"

    def resolve(self, part):
        """(what the part cites: PRD, SDD, ADR or PLAN; why it does not resolve, or None)."""
        if part.startswith("PRD"):
            return "PRD", self._prd_problem(part)
        if part.startswith("SDD"):
            return "SDD", self._sdd_problem(part)
        if ADR_CITATION.match(part):
            return "ADR", self._adr_problem(part)
        plan_part = PLAN_CITATION.match(part)
        if plan_part:
            return "PLAN", None if plan_part.group(1) in self.plan else f"`{part}` names no decision of PLAN.md"
        return None, f"`{part}` is no citation; a citation names `PRD §<id>`, `SDD §<N>`, `ADR-NNNN` or `PLAN.md decision <id>`"


def _acceptance_bullets(subtask):
    """Each `## Acceptance` bullet, with its wrapped lines."""
    bullets = []
    for line in subtask.sections.get("Acceptance", "").splitlines():
        if line.startswith("- "):
            bullets.append(line[2:].strip())
        elif bullets and line.startswith((" ", "\t")):
            bullets[-1] += " " + line.strip()
    return bullets


def _tag_failures(where, tag, sources, kinds):
    """The failures of one citation tag; `kinds` collects what it cites."""
    failures = []
    for part in (piece.strip() for piece in tag.split(";")):
        kind, problem = sources.resolve(part)
        kinds.add(kind)
        if problem:
            failures.append(cp.failure("C-UNRESOLVED", where, problem))
    return failures


def _design_ref_failures(subtask, sources, kinds):
    failures, where = [], f"{subtask.id}.md ## Design refs"
    for bullet in subtask.bullets("Design refs"):
        sdd, adr = DESIGN_REF_SDD.match(bullet), DESIGN_REF_ADR.match(bullet)
        if sdd:
            kinds.add("SDD")
            if sdd.group(1) not in sources.sdd:
                failures.append(cp.failure("C-UNRESOLVED", where, f"`{bullet}` names no section of the SDD"))
        elif adr:
            kinds.add("ADR")
            if not (sources.spec_dir / adr.group(1)).is_file():
                failures.append(cp.failure("C-UNRESOLVED", where, f"`{bullet}` names no ADR file"))
    return failures


def _parent_failures(subtask, spec_dir):
    failures = []
    for section, name in (("Parent PRD", "PRD.md"), ("Parent SDD", design_files.SDD_NAME)):
        cell = subtask.sections.get(section, "").strip()
        if not cell or Path(cell).resolve() != (spec_dir / name).resolve():
            failures.append(cp.failure("C-PARENT", f"{subtask.id}.md ## {section}", f"it reads {cell!r}, which is not {spec_dir / name}"))
    return failures


def _contract_citation_failures(subtask, sources):
    where, kinds = f"{subtask.id}.md", set()
    failures = _design_ref_failures(subtask, sources, kinds) + _parent_failures(subtask, sources.spec_dir)
    for bullet in _acceptance_bullets(subtask):
        tag = BULLET_TAG.search(bullet)
        if tag:
            failures += _tag_failures(f"{where} ## Acceptance", tag.group(1), sources, kinds)
        else:
            failures.append(cp.failure("C-NO-CITATION", f"{where} ## Acceptance", f"this bullet ends with no citation: {bullet!r}"))
    for tag in EXCERPT_TAG.findall(subtask.sections.get("Context excerpts", "")):
        failures += _tag_failures(f"{where} ## Context excerpts", tag, sources, kinds)
    failures += [cp.failure("C-NOT-CITED", where, f"this contract cites no {name} section") for name in ("PRD", "SDD") if name not in kinds]
    return failures


def citation_failures(plan, spec_dir):
    sources = Sources(spec_dir, plan)
    return [item for subtask in cp.read_subtasks(plan) for item in _contract_citation_failures(subtask, sources)]


def citations(argv):
    parser = Parser(add_help=False)
    for name in ("--plan", "--spec-dir"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    failures = citation_failures(args.plan, args.spec_dir)
    if failures:
        raise Refusal("citations-failed", f"{len(failures)} citations do not resolve", failures=failures)
    return {"ok": True, "contracts": len(cp.contract_paths(args.plan))}


# The run branch.

def _run_root(plan):
    """The top of the run branch that holds this plan folder; a refusal when it is anything else."""
    plan = Path(plan)
    if not plan.is_dir():
        raise Refusal("unreadable", f"no folder {plan}", EXIT_UNREADABLE)
    branch, top = _git(plan, "rev-parse", "--abbrev-ref", "HEAD"), _git(plan, "rev-parse", "--show-toplevel")
    if not branch.endswith(cp.RUN_SUFFIX) or (Path(top) / RUN_FOLDER).resolve() != plan.resolve():
        raise Refusal("not-run-branch", f"{plan} is not `{RUN_FOLDER}/` at the root of a `<feature branch>{cp.RUN_SUFFIX}` branch")
    return top


def _not_run_files(top):
    tracked = _git(top, "ls-files").splitlines() + _git(top, "ls-files", "--others", "--exclude-standard").splitlines()
    wrong = []
    for name in tracked:
        parts = name.split("/")
        if parts[0] != RUN_FOLDER or parts[-1] in SPEC_FILES or SPEC_FOLDERS & set(parts[1:-1]):
            wrong.append(name)
    return wrong


def commit_plan(plan, message):
    top = _run_root(plan)
    wrong = _not_run_files(top)
    if wrong:
        raise Refusal("not-a-run-file", f"the run branch holds only `{RUN_FOLDER}/` with run files, and no spec-folder file: {wrong}", files=wrong)
    if not _git(top, "status", "--porcelain", "--", RUN_FOLDER):
        return {"ok": True, "committed": False, "head": _git(top, "rev-parse", "HEAD")}
    _git(top, "add", "--", RUN_FOLDER)
    _git(top, "commit", "-q", "-m", message)
    return {"ok": True, "committed": True, "head": _git(top, "rev-parse", "HEAD")}


def commit(argv):
    parser = Parser(add_help=False)
    for name in ("--plan", "--message"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    return commit_plan(args.plan, args.message)


# The division.

def plan_digest(plan):
    """8 characters over PLAN.md and the contracts; the division line and the date do not count."""
    plan, digest = Path(plan), hashlib.sha256()
    for path in [plan / "PLAN.md", *cp.contract_paths(plan)]:
        lines = cp.read_text(path).replace("\r\n", "\n").split("\n")
        kept = [line for line in lines if not line.startswith(UNSTAMPED_LINES)] if path.name == "PLAN.md" else lines
        digest.update(path.name.encode("utf-8") + b"\0" + "\n".join(kept).encode("utf-8") + b"\0")
    return digest.hexdigest()[:8]


def _require_clean_check(plan):
    answer = cp.check_plan(plan)
    if not answer["ok"]:
        raise Refusal(answer["error"]["code"], answer["error"]["reason"], failures=answer["error"]["failures"])


def _without_division_line(plan):
    """Take back an approval: this division goes to the developer again."""
    path = Path(plan) / "PLAN.md"
    text = cp.read_text(path)
    kept = [line for line in text.split("\n") if not line.startswith(cp.DIVISION_MARK)]
    if len(kept) != text.count("\n") + 1:
        write_text(path, "\n".join(kept))
        commit_plan(plan, "plan: the division goes back to the developer")


def _gates_of(subtask):
    tiers = []
    for row in cp.table_rows(subtask.sections.get("Verification", ""))[1:]:
        tiers.append(f"{row[0]} (not applicable)" if len(row) > 1 and cp.is_not_applicable(row[1]) else row[0])
    return ", ".join(tiers)


def _division_card(plan, subtasks, why, card_id, digest, carries):
    rows = [[item.id, item.sections.get("Goal", ""), why[item.id], ", ".join(item.blocked_by) or "—", _gates_of(item)] for item in subtasks]
    app = cp._app_of(cp.read_text(Path(plan) / "PLAN.md")) or "none"
    text = (f"Sign to approve this division: {len(subtasks)} subtasks, plan digest {digest}, app: {app}. "
            "Ask for changes to get another division.")
    table = {"type": "table", "id": f"{card_id}-subtasks",
             "props": {"columns": ["Subtask", "Goal", "Why the cut is here", "Waits on", "Gates"], "rows": rows},
             "children": [{"type": "text", "id": f"{card_id}-ask", "props": {"text": text}}]}
    return {"id": card_id, "kind": "signoff", "body": table, **({"carries": carries} if carries else {})}


def _carried_cards(doc):
    current = rd.current_round(doc)
    if not current or not current.get("responses"):
        return []
    open_cards = [item["id"] for item in current["items"] if item["kind"] != "info" and item["state"] in rd.NEW_STATES]
    return list(dict.fromkeys(open_cards + [item["id"] for item in rd.returning(doc)]))


def build_division_round(plan, doc_path, session, ticket, why, replace=False):
    _run_root(plan)
    _require_clean_check(plan)
    subtasks = cp.read_subtasks(plan)
    missing = [item.id for item in subtasks if not str(why.get(item.id) or "").strip()]
    if missing or set(why) - {item.id for item in subtasks}:
        raise Refusal("bad-why", f"give one sentence per subtask on why the cut is there; missing: {missing}, unknown: {sorted(set(why) - {item.id for item in subtasks})}")
    _without_division_line(plan)
    dirty = _git(_run_root(plan), "status", "--porcelain", "--", RUN_FOLDER)
    if dirty:
        raise Refusal("plan-not-committed", f"commit the plan first; the developer approves a committed plan: {dirty}")
    doc_path = Path(doc_path)
    doc = read_json(doc_path) if doc_path.exists() else {"rounds": []}
    if replace:
        rd._drop_unanswered_round(doc)
    shown = [item["id"] for rnd in doc["rounds"] for item in rnd["items"]]
    digest = plan_digest(plan)
    card_id = f"{CARD_PREFIX}{digest}-{len(shown) + 1}"
    carries = _carried_cards(doc)
    session_fields = {"id": session, "skill": PAGE_SKILL, "feature": ticket, "ticket": ticket}
    banner = {"settled": [], "unlocks": ["/afkv2:autopilot can start on this plan"], "parked": []}
    round_input = {"banner": banner, "items": [_division_card(plan, subtasks, why, card_id, digest, carries)]}
    answer = rd.build_round_document(doc_path, session_fields, round_input, replace=replace)
    return {**answer, "card": card_id, "digest": digest}


def division(argv):
    parser = Parser(add_help=False)
    for name in ("--plan", "--doc", "--session", "--ticket", "--why"):
        parser.add_argument(name, required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    return build_division_round(args.plan, args.doc, args.session, args.ticket, read_json(args.why), args.replace)


def _approved_by_developer(doc_path, digest):
    """True when the newest division card shows this digest and the developer settled it; also the card states."""
    doc = read_json(doc_path)
    cards = [item for rnd in doc["rounds"] for item in rnd["items"] if item["id"].startswith(CARD_PREFIX) and item["kind"] == "signoff"]
    settled = bool(cards) and cards[-1]["id"].startswith(f"{CARD_PREFIX}{digest}-") and cards[-1]["state"] in SETTLED
    return settled, [f"{item['id']}: {item['state']}" for item in cards]


def _with_division_line(text, day):
    """PLAN.md with the division line at the end of its `> ` header block."""
    end = "\r\n" if "\r\n" in text else "\n"
    lines, last, above_sections = text.split(end), None, True
    for index, line in enumerate(lines):
        above_sections = above_sections and not line.startswith("## ")
        if above_sections and line.startswith("> "):
            last = index
    if last is None:
        raise Refusal("bad-plan", "PLAN.md has no `> ` header lines")
    lines.insert(last + 1, f"{cp.APPROVAL_TEXT}{day}")
    return end.join(lines)


def approve_division(plan, doc_path, spec_dir):
    run_top = _run_root(plan)
    _require_clean_check(plan)
    path = Path(plan) / "PLAN.md"
    settled, states = _approved_by_developer(doc_path, plan_digest(plan)) if Path(doc_path).is_file() else (False, [])
    if not settled:
        raise Refusal("not-approved", f"the developer has not approved this plan; cards of this plan: {states or 'none'}", cards=states)
    division_state = cp.division_of(cp.read_text(path))[0]
    day = division_state["date"]
    if not division_state["approved"]:
        day = date.today().isoformat()
        write_text(path, _with_division_line(cp.read_text(path), day))
    committed = commit_plan(plan, f"plan: division approved {day}")
    index = Path(spec_dir) / "INDEX.md"
    if index.is_file():
        branch = _git(run_top, "rev-parse", "--abbrev-ref", "HEAD")
        prd_files.set_row(index, "Plan", f"{branch}:{RUN_FOLDER}/PLAN.md", f"{len(cp.contract_paths(plan))} subtasks; division approved {day}")
    return {"ok": True, "approved": day, "head": committed["head"], "index_missing": not index.is_file()}


def approve(argv):
    parser = Parser(add_help=False)
    for name in ("--plan", "--doc", "--spec-dir"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    return approve_division(args.plan, args.doc, args.spec_dir)


VERBS = {"start": start, "citations": citations, "commit": commit, "division": division, "approve": approve}


def main(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the first word is one of {sorted(VERBS)}", EXIT_UNREADABLE)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(serve(main))
