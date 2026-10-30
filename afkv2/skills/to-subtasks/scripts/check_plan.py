"""The plan check: `check_plan.py <plan folder>`. It answers one JSON object and writes nothing.

Exit 0: `{"ok": true, "subtasks": [...], "division": {"approved", "date"}, "base": ...}`.
Exit 1: `{"ok": false, "error": {"code": "plan-check-failed", "reason", "failures": [{"code", "where", "reason"}]}}`,
with every failure listed. Exit 2: the folder, PLAN.md or a contract cannot be read.

Rule codes:
  A-UNKNOWN-PRODUCER, A-FORWARD, A-NOT-PRODUCED, A-COLLISION  the contract graph
  B-GENERIC, B-SHORT, B-AMBIGUOUS                             the anchor quality
  SYNTAX, MATERIALIZED-SEAM, SECTION, TRACKER, bad-approval   the shape of the plan
  gate-cannot-run, bad-not-applicable                         a gate the repository cannot run
  check-path-unowned                                          a check path with no owner in the chain

A plan without the division line passes: `division.approved` is false, and `/afkv2:autopilot` reads the line
itself. `base` names what the anchors and the check paths were compared with: on a run branch that is the
feature branch, because the run branch holds no code.

Lockstep copies of `start_gate.py` in `/afkv2:autopilot`, which is not merged yet and so is not imported:
`NOT_APPLICABLE`, `is_not_applicable`, `LIVE_TIERS`, `SPAN`, `PROGRAM`, the rule of `_programs`, `RUN_SUFFIX`
and the division line. `plan_contract.py` there holds a copy of the contract headings.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL.parent / "grill" / "scripts"))

from grill_common import EXIT_UNREADABLE, Parser, Refusal, serve  # noqa: E402

FORMAT_FILE = SKILL / "SUBTASK-CONTRACT.md"
TEMPLATE = re.compile(r"^```markdown contract-template\n(.*?)^```$", re.S | re.M)
OPTIONAL_MARK = "<optional"
HEADING = re.compile(r"## (.+?)\s*")
FENCE = re.compile(r"\s*(```|~~~)")
SEPARATOR = re.compile(r":?-+:?")
SUBTASK_FILE = re.compile(r"^(\d{4})-[a-z0-9][a-z0-9-]*\.md$")
CONSUMES_LINE = re.compile(r"(\d{4}-[a-z0-9][a-z0-9-]*)\s+(.*)")
GENERIC_ANCHORS = {"class", "interface", "void", "function", "def", "method", "struct", "enum", "type", "record"}
MIN_ANCHOR = 12
V1_SEAM_MARK = "[materialized]"
RUN_SUFFIX = "-run"
DIVISION_MARK = "> Division:"
APPROVAL_TEXT = "> Division: approved "
APPROVAL = re.compile(re.escape(APPROVAL_TEXT) + r"(\d{4}-\d{2}-\d{2})\s*")
GIT_LIMIT_S = 60
NOT_APPLICABLE = "not applicable:"
LIVE_TIERS = {"api", "e2e", "browser", "e2e/browser", "ui-e2e"}
SPAN = re.compile(r"`([^`]+)`")
PROGRAM = re.compile(r"[a-z0-9][\w.-]*")
SKIP_WORDS = {"", "-", "—", "n/a", "na", "none", "skip", "skipped"}
APP_MARK = "> App:"
NO_APP = {"", "none"}
QUOTED = re.compile(r"\"[^\"]*\"|'[^']*'")
FILE_NAME = re.compile(r"[A-Za-z_][\w-]*\.[a-z][a-z0-9]{0,4}")
NOT_A_PATH = re.compile(r"^[-/~]|^[A-Za-z]:|^origin/|://|[\"'<>{}$%=|&]")
WILDCARD = re.compile(r"[*?]")
NEXT_IS_NO_PATH = {">", ">>", "2>", "-m"}


def failure(code, where, reason, **extra):
    return {"code": code, "where": where, "reason": reason, **extra}


def read_text(path):
    try:
        return Path(path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise Refusal("unreadable", f"cannot read {path}: {error}", EXIT_UNREADABLE) from error


def sections_of(text):
    """Each `## ` heading outside a code fence, with the text under it."""
    found, name, lines, fenced = {}, None, [], False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
        heading = None if fenced else HEADING.fullmatch(line)
        if heading:
            if name is not None:
                found[name] = "\n".join(lines).strip()
            name, lines = heading.group(1), []
        elif name is not None:
            lines.append(line)
    if name is not None:
        found[name] = "\n".join(lines).strip()
    return found


def contract_sections():
    """(required, optional) headings, from the one file that states them."""
    template = TEMPLATE.search(read_text(FORMAT_FILE))
    if not template:
        raise Refusal("unreadable", f"{FORMAT_FILE} has no contract template", EXIT_UNREADABLE)
    lines = template.group(1).splitlines()
    required, optional = [], []
    for index, line in enumerate(lines):
        if line.startswith("## "):
            target = optional if lines[index + 1].startswith(OPTIONAL_MARK) else required
            target.append(line[3:].strip())
    return tuple(required), tuple(optional)


def split_cells(line):
    """The cells of one table line. A `|` inside a code span stays in its cell."""
    cells, cell, in_code = [], [], False
    for char in line.strip().strip("|"):
        if char == "`":
            in_code = not in_code
        if char == "|" and not in_code:
            cells.append("".join(cell).strip())
            cell = []
        else:
            cell.append(char)
    cells.append("".join(cell).strip())
    return cells


def table_rows(text):
    """The rows of the first table in `text`, header first, with no separator line."""
    rows = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            if rows:
                break
            continue
        cells = split_cells(line)
        if not all(SEPARATOR.fullmatch(cell) for cell in cells):
            rows.append(cells)
    return rows


def split_anchor(text):
    """(file, anchor) of `<file>#<anchor> — words`; the first `#` ends the file, and ` — ` ends the anchor."""
    path, mark, anchor = text.split(" — ", 1)[0].strip().partition("#")
    return (path.strip(), anchor.strip()) if mark and path.strip() and anchor.strip() else None


@dataclass(frozen=True)
class Subtask:
    id: str
    rank: int
    sections: dict

    def bullets(self, name):
        return [line[2:].strip() for line in self.sections.get(name, "").splitlines() if line.startswith("- ")]

    @property
    def blocked_by(self):
        return [bullet.split()[0] for bullet in self.bullets("Blocked by")]

    @property
    def scope(self):
        """The globs of `## Scope`, without a backtick or the words after the glob."""
        cut = (bullet.split(" #")[0].split(" — ")[0].strip().strip("`") for bullet in self.bullets("Scope"))
        return [glob for glob in cut if glob and not glob.startswith("#")]


def contract_paths(plan):
    """The contract files of a plan folder, in rank order."""
    return sorted(path for path in Path(plan).iterdir() if SUBTASK_FILE.match(path.name))


def read_subtasks(plan):
    return [Subtask(path.stem, int(SUBTASK_FILE.match(path.name).group(1)), sections_of(read_text(path)))
            for path in contract_paths(plan)]


def _header_lines(plan_text):
    """The PLAN.md lines above the first `## ` heading."""
    header = []
    for line in plan_text.splitlines():
        if line.startswith("## "):
            break
        header.append(line)
    return header


def division_of(plan_text):
    """({"approved", "date"}, failures) from the header of PLAN.md."""
    lines = [line for line in _header_lines(plan_text) if line.startswith(DIVISION_MARK)]
    if not lines:
        return {"approved": False, "date": None}, []
    match = APPROVAL.fullmatch(lines[0])
    if len(lines) > 1 or not match:
        return {"approved": False, "date": None}, [failure(
            "bad-approval", "PLAN.md", f"the header needs one `{DIVISION_MARK}` line with the word approved and a date; it has: {lines}")]
    return {"approved": True, "date": match.group(1)}, []


def _git(cwd, *args):
    """git's stdout as bytes, or None when git refuses or gives no answer in time."""
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL, timeout=GIT_LIMIT_S)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def _folder_of(glob):
    """The literal folder a glob starts from; a path with no wildcard is itself."""
    wildcard = WILDCARD.search(glob)
    return glob if not wildcard else glob[:wildcard.start()].rpartition("/")[0]


def _glob_regex(glob):
    parts, index = [], 0
    while index < len(glob):
        if glob.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif glob.startswith("**", index):
            parts.append(".*")
            index += 2
        else:
            parts.append({"*": "[^/]*", "?": "[^/]"}.get(glob[index], re.escape(glob[index])))
            index += 1
    return re.compile("".join(parts))


def scope_owns(glob, path):
    """True when a Scope glob holds the path, or the path is a folder or a glob around that Scope."""
    regex, root = _glob_regex(glob), _folder_of(glob)
    if WILDCARD.search(path):
        folder = _folder_of(path)
        return root == folder or root.startswith(f"{folder}/") or bool(regex.fullmatch(f"{folder}/x"))
    return bool(regex.fullmatch(path)) or root == path or root.startswith(f"{path}/")


class Base:
    """The code a plan stands on: the feature branch of a run branch, else the enclosing work tree."""

    def __init__(self, plan):
        self.plan = Path(plan)

    def _line(self, *args):
        out = _git(self.plan, *args)
        return out.decode("utf-8", "replace").strip() if out else None

    @cached_property
    def source(self):
        """("ref", name), ("tree", folder) or (None, None)."""
        branch = self._line("rev-parse", "--abbrev-ref", "HEAD")
        if branch and branch.endswith(RUN_SUFFIX):
            feature = branch[:-len(RUN_SUFFIX)]
            for ref in (f"refs/heads/{feature}", f"refs/remotes/origin/{feature}"):
                if self._line("rev-parse", "--verify", "--quiet", ref):
                    return "ref", ref
            return None, None
        top = self._line("rev-parse", "--show-toplevel")
        return ("tree", top) if top else (None, None)

    @property
    def name(self):
        return self.source[1]

    @cached_property
    def _tree(self):
        """Every file and folder of the feature branch."""
        out = _git(self.plan, "ls-tree", "-r", "-z", "--full-tree", "--name-only", self.source[1]) or b""
        found = set()
        for name in out.decode("utf-8", "replace").split("\0"):
            while name and name not in found:
                found.add(name)
                name = name.rpartition("/")[0]
        return found

    def has(self, path):
        """True when the file or folder, or the folder a glob starts from, is already in the base."""
        kind, where = self.source
        literal = _folder_of(path)
        if kind == "ref":
            return literal in self._tree
        return bool(kind and literal) and (Path(where) / literal).exists()

    def read(self, path):
        """The text of a file of the base, or None when it has no such file."""
        kind, where = self.source
        if kind == "ref":
            out = _git(self.plan, "show", f"{where}:{path}")
            return out.decode("utf-8", "replace") if out is not None else None
        target = Path(where) / path if kind else None
        return target.read_text("utf-8", "replace") if target and target.is_file() else None


def _anchor_failures(where, path, anchor, base):
    failures = []
    if anchor.lower() in GENERIC_ANCHORS:
        failures.append(failure("B-GENERIC", where, f"the anchor {anchor!r} is a bare keyword"))
    if len(anchor) < MIN_ANCHOR:
        failures.append(failure("B-SHORT", where, f"the anchor {anchor!r} is shorter than {MIN_ANCHOR} characters"))
    text = base.read(path)
    if text is not None and text.count(anchor) >= 2:
        failures.append(failure("B-AMBIGUOUS", where, f"the anchor {anchor!r} matches {text.count(anchor)} times in {path}"))
    return failures


def _without_seam_mark(raw, where, failures):
    if not raw.endswith(V1_SEAM_MARK):
        return raw
    failures.append(failure("MATERIALIZED-SEAM", where, f"this format has no materialized seams: {raw!r}"))
    return raw[:-len(V1_SEAM_MARK)].strip()


def _consumer_failures(subtask, ranks, produced):
    failures, where = [], f"{subtask.id}.md"
    for raw in subtask.bullets("Consumes"):
        raw = _without_seam_mark(raw, where, failures)
        line = CONSUMES_LINE.match(raw)
        reference = split_anchor(line.group(2)) if line else None
        if reference is None:
            failures.append(failure("SYNTAX", where, f"a `## Consumes` line reads `<producer id> <file>#<anchor> — <what>`: {raw!r}"))
            continue
        producer = line.group(1)
        if producer not in ranks:
            failures.append(failure("A-UNKNOWN-PRODUCER", where, f"it consumes from {producer}, which is not a subtask of this plan"))
            continue
        if ranks[producer] >= subtask.rank:
            failures.append(failure("A-FORWARD", where, f"it consumes from {producer}, which does not come earlier"))
        if producer not in produced.get(reference, []):
            failures.append(failure("A-NOT-PRODUCED", where, f"{reference[0]}#{reference[1]} is not in `## Produces` of {producer}"))
    return failures


def _graph_failures(subtasks, base):
    failures, produced = [], {}
    for subtask in subtasks:
        where = f"{subtask.id}.md"
        for raw in subtask.bullets("Produces"):
            raw = _without_seam_mark(raw, where, failures)
            reference = split_anchor(raw)
            if reference is None:
                failures.append(failure("SYNTAX", where, f"a `## Produces` bullet reads `<file>#<anchor> — <contract>`: {raw!r}"))
                continue
            produced.setdefault(reference, []).append(subtask.id)
            failures.extend(_anchor_failures(where, *reference, base))
    for (path, anchor), owners in produced.items():
        if len(set(owners)) > 1:
            failures.append(failure("A-COLLISION", "PLAN.md", f"{path}#{anchor} is produced by {', '.join(owners)}"))
    ranks = {subtask.id: subtask.rank for subtask in subtasks}
    for subtask in subtasks:
        failures.extend(_consumer_failures(subtask, ranks, produced))
    return failures


def _section_failures(subtasks):
    required, optional = contract_sections()
    failures = []
    for subtask in subtasks:
        where = f"{subtask.id}.md"
        failures += [failure("SECTION", where, f"no section `## {name}`") for name in required if name not in subtask.sections]
        failures += [failure("SECTION", where, f"section `## {name}` is not in the contract format")
                     for name in subtask.sections if name not in required + optional]
    return failures


def _tracker_failures(plan_text, subtasks):
    rows = table_rows(sections_of(plan_text).get("Progress tracker", ""))
    if not rows or "Subtask" not in rows[0]:
        return [failure("TRACKER", "PLAN.md", "`## Progress tracker` has no table with a `Subtask` column")]
    column = rows[0].index("Subtask")
    tracked = [row[column] for row in rows[1:] if len(row) > column]
    files = [subtask.id for subtask in subtasks]
    return ([failure("TRACKER", "PLAN.md", f"the tracker row {item} has no contract file") for item in tracked if item not in files]
            + [failure("TRACKER", f"{item}.md", "this contract has no tracker row") for item in files if item not in tracked])


def check_paths(cell):
    """Each repository path in the code spans of a check cell. The first word of a span is a path only with a `/`."""
    paths = []
    for span in SPAN.findall(cell):
        words = QUOTED.sub(" ", span).split()
        for index, raw in enumerate(words):
            if index and words[index - 1] in NEXT_IS_NO_PATH:
                continue
            word = raw.rstrip(";,").replace("\\", "/").removeprefix("./")
            if NOT_A_PATH.search(word):
                continue
            if "/" in word or (index and FILE_NAME.fullmatch(word)):
                paths.append(word.rstrip("/"))
    return list(dict.fromkeys(paths))


def _programs(cell):
    """The program of each code span that reads as a command: 2 or more words, a lower-case name first."""
    for span in SPAN.findall(cell):
        words = span.split()
        if len(words) >= 2 and PROGRAM.fullmatch(words[0]):
            yield words[0]


def is_not_applicable(cell):
    return cell.startswith(NOT_APPLICABLE) and bool(cell[len(NOT_APPLICABLE):].strip())


def _means_not_applicable(cell):
    """True when a cell says in any words that the row does not apply."""
    return re.sub(r"[^a-z]", "", cell.lower()).startswith("notapplicable") or cell.strip().lower() in SKIP_WORDS


def _app_of(plan_text):
    """The value of the `> App:` header line; None when the repository has no app."""
    for line in _header_lines(plan_text):
        if line.startswith(APP_MARK):
            value = line[len(APP_MARK):].strip()
            return None if value.lower() in NO_APP else value
    return None


def _chain_of(subtask, by_id):
    """The subtask and every subtask it waits on, directly or through another one."""
    chain, todo = {}, [subtask.id]
    while todo:
        item = todo.pop()
        if item in by_id and item not in chain:
            chain[item] = by_id[item]
            todo.extend(by_id[item].blocked_by)
    return chain.values()


def _row_failures(where, tier, cell, app, owners, base):
    if is_not_applicable(cell):
        return []
    if _means_not_applicable(cell):
        return [failure("bad-not-applicable", where, f"write the cell as `{NOT_APPLICABLE} <reason>`, with these exact words and a reason")]
    fix = f"mark the row `{NOT_APPLICABLE} <reason>`, or slice again"
    failures = []
    if tier in LIVE_TIERS and not app:
        failures.append(failure("gate-cannot-run", where, f"this tier needs a running app, and the `{APP_MARK}` line of PLAN.md names none",
                                next=f"{fix}, or name the app in the `{APP_MARK}` line"))
    failures += [failure("gate-cannot-run", where, f"the command `{program}` is not on the PATH", next=fix)
                 for program in dict.fromkeys(_programs(cell)) if not shutil.which(program)]
    failures += [failure("check-path-unowned", where, f"no Scope in the chain of this subtask owns `{path}`, and it is not in {base.name or 'the repository'}",
                         next="add the path to the Scope of this subtask or of one it waits on, or add `## Blocked by` on its owner")
                 for path in check_paths(cell)
                 if not any(scope_owns(glob, path) for glob in owners) and not base.has(path)]
    return failures


def _gate_failures(subtasks, plan_text, base):
    app, by_id = _app_of(plan_text), {subtask.id: subtask for subtask in subtasks}
    failures = []
    for subtask in subtasks:
        owners = [glob for item in _chain_of(subtask, by_id) for glob in item.scope]
        for row in table_rows(subtask.sections.get("Verification", ""))[1:]:
            if len(row) >= 2:
                tier = row[0].strip("` ").lower()
                failures += _row_failures(f"{subtask.id} tier {tier}", tier, row[1], app, owners, base)
    return failures


def check_plan(plan):
    """One answer on one plan folder; a folder it cannot read raises a Refusal with exit 2."""
    plan = Path(plan)
    if not (plan / "PLAN.md").is_file():
        raise Refusal("unreadable", f"no PLAN.md in {plan}", EXIT_UNREADABLE)
    plan_text = read_text(plan / "PLAN.md")
    subtasks, base = read_subtasks(plan), Base(plan)
    division, failures = division_of(plan_text)
    failures += (_section_failures(subtasks) + _tracker_failures(plan_text, subtasks)
                 + _graph_failures(subtasks, base) + _gate_failures(subtasks, plan_text, base))
    if failures:
        return {"ok": False, "error": {"code": "plan-check-failed", "reason": f"{len(failures)} failures in this plan", "failures": failures}}
    return {"ok": True, "subtasks": [subtask.id for subtask in subtasks], "division": division, "base": base.name}


def main(argv):
    parser = Parser(add_help=False)
    parser.add_argument("plan")
    answer = check_plan(parser.parse_args(argv).plan)
    if not answer["ok"]:
        raise Refusal(answer["error"]["code"], answer["error"]["reason"], failures=answer["error"]["failures"])
    return answer


if __name__ == "__main__":
    sys.exit(serve(main))
