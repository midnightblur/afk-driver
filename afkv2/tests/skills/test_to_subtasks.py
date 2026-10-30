"""Tests for the to-subtasks skill.

The plan check runs as the command `/afkv2:autopilot` starts, or in process. The dry runs take every
command from the fenced `sh step=...` blocks of SKILL.md, in a temporary git repository, with the
recorded fakes of the page engine and the config reader (fakes/). Once S1 and S3 merge, the same plan
also goes through the real engine and the real start gate.
"""

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
SKILL_DIR = SKILLS / "to-subtasks"
CHECK = SKILL_DIR / "scripts" / "check_plan.py"
HERE = Path(__file__).resolve().parent
FAKES = HERE / "fakes"
FIXTURES = HERE / "fixtures"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import check_plan as cp  # noqa: E402
import plan_files  # noqa: E402

import design_files  # noqa: E402

STATIC_ROW = "| static | `git --version` | the tool runs |"


def contract(subtask, scope="src/**", rows=STATIC_ROW, produces=None, consumes=(), blocked=()):
    name = subtask[5:].replace("-", "_")
    produced = produces if produces is not None else [f"src/{subtask}.py#def build_{name}_part( — the code"]
    return "\n".join([
        f"# {subtask}", "", "## Goal", "Build it.", "", "## Complexity", "standard", "",
        "## Design refs", "- SDD: SDD.md#§8 L7 — the module", "", "## Scope",
        *[f"- {glob}" for glob in ([scope] if isinstance(scope, str) else scope)], "",
        "## Seams", "(none)", "", "## Acceptance", "- [ ] It works. (PRD §AC-001)", "",
        "## Produces", *[f"- {line}" for line in produced], "",
        "## Consumes", *([f"- {line}" for line in consumes] or ["(none)"]), "",
        "## Verification", "| Tier | Check (command or method) | Proves |", "|------|---------------------------|--------|",
        rows, "", "## Context excerpts", "> (PRD §AC-001) It works.", "", "## Parent PRD", "specs/PROJ-1/PRD.md", "",
        "## Parent SDD", "specs/PROJ-1/SDD.md", "", "## Blocked by", *([f"- {item}" for item in blocked] or ["(none)"]), "",
        "## Conflict procedure", "Record it or stop.", ""])


def plan_text(subtasks, header=""):
    rows = [f"| {rank} | {subtask} | title | pending | — | static | — |" for rank, subtask in enumerate(subtasks, 1)]
    return "\n".join(["# Execution Plan", "", "> Parent ticket: PROJ-1   Mode: cited", "> Last updated: 2026-01-05",
                      *([header] if header else []), "", "## Progress tracker", "",
                      "| # | Subtask | Title | Status | Blocked by | Tiers | Seams |",
                      "|---|---------|-------|--------|------------|-------|-------|", *rows, ""])


def write_plan(folder, contracts, header=""):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "PLAN.md").write_text(plan_text(list(contracts), header), "utf-8")
    for subtask, text in contracts.items():
        (folder / f"{subtask}.md").write_text(text, "utf-8")
    return folder


def failures_of(answer):
    return [] if answer["ok"] else answer["error"]["failures"]


def codes_of(answer):
    return sorted({failure["code"] for failure in failures_of(answer)})


def check(folder, contracts, header=""):
    return cp.check_plan(write_plan(folder / "plan", contracts, header))


def run_check(plan, *args):
    run = subprocess.run([sys.executable, str(CHECK), str(plan), *args], capture_output=True, text=True,
                         encoding="utf-8", timeout=60)
    return run.returncode, json.loads(run.stdout)


@pytest.fixture(autouse=True)
def programs_on_the_path(monkeypatch):
    """In process, every program is on the PATH but `no-such-...`, on any machine."""
    monkeypatch.setattr(cp.shutil, "which", lambda name: None if name.startswith("no-such") else name)


@pytest.fixture
def clean():
    return {"0001-a": contract("0001-a"), "0002-b": contract("0002-b", blocked=["0001-a"])}


# The command: one JSON object, exit 0, 1 or 2.

def test_a_clean_plan_exits_0(tmp_path, clean):
    code, answer = run_check(write_plan(tmp_path / "plan", clean))
    assert (code, answer["ok"]) == (0, True)
    assert answer["subtasks"] == ["0001-a", "0002-b"]


def test_every_failure_is_listed_with_exit_1(tmp_path, clean):
    clean["0002-b"] = contract("0002-b", produces=["src/b.py#short — the code"],
                               consumes=["0009-x src/x.py#def nothing_at_all( — it"])
    code, answer = run_check(write_plan(tmp_path / "plan", clean))
    assert code == 1
    assert answer["error"]["code"] == "plan-check-failed"
    assert codes_of(answer) == ["A-UNKNOWN-PRODUCER", "B-SHORT"]
    for failure in failures_of(answer):
        assert set(failure) >= {"code", "where", "reason"}


def test_a_folder_with_no_plan_exits_2(tmp_path):
    code, answer = run_check(tmp_path)
    assert code == 2 and answer["ok"] is False
    assert "PLAN.md" in answer["error"]["reason"]


def test_no_argument_exits_2():
    run = subprocess.run([sys.executable, str(CHECK)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert run.returncode == 2 and json.loads(run.stdout)["ok"] is False


def test_a_contract_that_is_no_utf8_exits_2(tmp_path, clean):
    plan = write_plan(tmp_path / "plan", clean)
    (plan / "0001-a.md").write_bytes(b"\xff\xfe not text")
    code, answer = run_check(plan)
    assert code == 2 and "0001-a.md" in answer["error"]["reason"]


# (a) The contract graph.

def consumer_plan(line):
    return {"0001-a": contract("0001-a", produces=["src/a.py#def build_alpha( — the code"]),
            "0002-b": contract("0002-b", consumes=[line], blocked=["0001-a"])}


def test_a_consumer_of_a_produced_anchor_passes(tmp_path):
    assert check(tmp_path, consumer_plan("0001-a src/a.py#def build_alpha( — it"))["ok"]


@pytest.mark.parametrize("line, code", [
    ("0009-z src/a.py#def build_alpha( — it", "A-UNKNOWN-PRODUCER"),
    ("0001-a src/a.py#def build_other( — it", "A-NOT-PRODUCED"),
    ("not a line", "SYNTAX"),
])
def test_a_broken_consumer_is_refused(tmp_path, line, code):
    assert codes_of(check(tmp_path, consumer_plan(line))) == [code]


def test_a_consumer_of_a_later_subtask_is_refused(tmp_path):
    contracts = {"0001-a": contract("0001-a", consumes=["0002-b src/b.py#def build_beta_x( — it"]),
                 "0002-b": contract("0002-b", produces=["src/b.py#def build_beta_x( — the code"])}
    assert codes_of(check(tmp_path, contracts)) == ["A-FORWARD"]


def test_one_anchor_from_2_subtasks_is_refused(tmp_path):
    line = "src/a.py#def build_alpha( — the code"
    contracts = {"0001-a": contract("0001-a", produces=[line]), "0002-b": contract("0002-b", produces=[line])}
    assert codes_of(check(tmp_path, contracts)) == ["A-COLLISION"]


# (b) The anchor quality.

@pytest.mark.parametrize("anchor, code", [("class", "B-GENERIC"), ("short", "B-SHORT")])
def test_a_weak_anchor_is_refused(tmp_path, anchor, code):
    assert code in codes_of(check(tmp_path, {"0001-a": contract("0001-a", produces=[f"src/a.py#{anchor} — the code"])}))


def test_a_produces_bullet_with_no_anchor_is_refused(tmp_path):
    assert codes_of(check(tmp_path, {"0001-a": contract("0001-a", produces=["src/a.py — the code"])})) == ["SYNTAX"]


def test_a_materialized_seam_is_refused(tmp_path):
    contracts = {"0001-a": contract("0001-a", produces=["src/a.py#def build_alpha( — the code [materialized]"])}
    assert codes_of(check(tmp_path, contracts)) == ["MATERIALIZED-SEAM"]


# The section set of the format file.

def test_the_format_file_states_the_frozen_sections():
    required, optional = cp.contract_sections()
    assert required == ("Goal", "Complexity", "Design refs", "Scope", "Seams", "Acceptance", "Produces", "Verification",
                        "Context excerpts", "Parent PRD", "Parent SDD", "Blocked by", "Conflict procedure")
    assert optional == ("Review", "Consumes")


def test_the_format_file_holds_the_conflict_anchor_once():
    assert (SKILL_DIR / "SUBTASK-CONTRACT.md").read_text("utf-8").count("## Conflict procedure") == 1


def test_the_format_file_has_no_materialized_seams():
    assert "materialized" not in (SKILL_DIR / "SUBTASK-CONTRACT.md").read_text("utf-8")


def test_a_missing_or_foreign_section_is_refused(tmp_path, clean):
    clean["0001-a"] = clean["0001-a"].replace("## Seams", "## Sea")
    failures = failures_of(check(tmp_path, clean))
    assert {failure["code"] for failure in failures} == {"SECTION"}
    assert len(failures) == 2


def test_a_heading_inside_a_code_fence_is_no_section(tmp_path, clean):
    clean["0001-a"] = clean["0001-a"].replace("Build it.", "Build it.\n\n```\n## Other\n```")
    assert check(tmp_path, clean)["ok"]


# The tracker and the contract files agree.

def test_a_contract_with_no_tracker_row_is_refused(tmp_path, clean):
    plan = write_plan(tmp_path / "plan", clean)
    (plan / "0003-c.md").write_text(contract("0003-c"), "utf-8")
    assert codes_of(cp.check_plan(plan)) == ["TRACKER"]


def test_a_tracker_row_with_no_contract_is_refused(tmp_path, clean):
    plan = write_plan(tmp_path / "plan", clean)
    (plan / "0002-b.md").unlink()
    assert codes_of(cp.check_plan(plan)) == ["TRACKER"]


# SDD §7 v1 defects: a gate the repository cannot run is decided when the plan is cut.

def api_row(check="`curl http://localhost/health`"):
    return f"{STATIC_ROW}\n| api | {check} | the endpoint answers |"


@pytest.mark.parametrize("tier", ["api", "e2e", "browser", "e2e/browser", "ui-e2e"])
def test_a_live_tier_in_a_repository_with_no_app_is_refused(tmp_path, tier):
    rows = f"{STATIC_ROW}\n| {tier} | the flow runs in a browser | the flow |"
    failures = failures_of(check(tmp_path, {"0001-a": contract("0001-a", rows=rows)}))
    assert [item["code"] for item in failures] == ["gate-cannot-run"]
    assert failures[0]["where"] == f"0001-a tier {tier}"
    assert "not applicable: <reason>" in failures[0]["next"]


def test_an_app_line_of_none_still_refuses_a_live_tier(tmp_path):
    answer = check(tmp_path, {"0001-a": contract("0001-a", rows=api_row())}, header="> App: none")
    assert codes_of(answer) == ["gate-cannot-run"]


def test_a_repository_with_an_app_may_keep_a_live_tier(tmp_path):
    assert check(tmp_path, {"0001-a": contract("0001-a", rows=api_row())}, header="> App: http://localhost:8080")["ok"]


def test_a_program_not_on_the_path_is_refused(tmp_path):
    rows = "| static | `no-such-program-here --check src` | it runs |"
    failures = failures_of(check(tmp_path, {"0001-a": contract("0001-a", rows=rows)}))
    assert [item["code"] for item in failures] == ["gate-cannot-run"]
    assert "no-such-program-here" in failures[0]["reason"]


def test_the_command_reads_the_real_path(tmp_path):
    rows = "| static | `no-such-program-here --check` | it runs |"
    code, answer = run_check(write_plan(tmp_path / "plan", {"0001-a": contract("0001-a", rows=rows)}))
    assert code == 1 and codes_of(answer) == ["gate-cannot-run"]


def test_prose_in_a_code_span_is_no_program(tmp_path):
    rows = "| static | every `Agent Skills` file has `name` and `description` | it parses |"
    assert check(tmp_path, {"0001-a": contract("0001-a", rows=rows)})["ok"]


# The form of a gate the plan names not applicable (D-56).

@pytest.mark.parametrize("cell", ["not applicable: this repository has no running app",
                                  "not applicable:no app", "not applicable: `no-such-program-here x` is absent"])
def test_the_not_applicable_form_passes(tmp_path, cell):
    assert check(tmp_path, {"0001-a": contract("0001-a", rows=api_row(cell))})["ok"]


@pytest.mark.parametrize("cell", ["not applicable", "not applicable:", "not applicable:   ", "Not applicable: no app",
                                  "NOT APPLICABLE: no app", "not-applicable: no app", "n/a", "N/A", "na", "none", "skip",
                                  "skipped", "-", "—", ""])
def test_another_not_applicable_form_is_refused(tmp_path, cell):
    answer = check(tmp_path, {"0001-a": contract("0001-a", rows=api_row(cell))})
    assert codes_of(answer) == ["bad-not-applicable"]
    assert "not applicable: <reason>" in failures_of(answer)[0]["reason"]


# SDD §7 v1 defects: each check path has an owner in the chain of the subtask.

def path_row(path):
    return f"| unit | `python -m pytest {path} -q` | it passes |"


def chain_plan(path, scope_a="src/**", scope_b="lib/**", blocked=("0001-a",)):
    return {"0001-a": contract("0001-a", scope=scope_a),
            "0002-b": contract("0002-b", scope=scope_b, rows=path_row(path), blocked=blocked)}


def test_a_check_path_no_scope_in_the_chain_owns_is_refused(tmp_path):
    failures = failures_of(check(tmp_path, chain_plan("tests/test_other.py")))
    assert [item["code"] for item in failures] == ["check-path-unowned"]
    assert failures[0]["where"] == "0002-b tier unit"
    assert "tests/test_other.py" in failures[0]["reason"]


def test_the_subtasks_own_scope_owns_a_check_path(tmp_path):
    assert check(tmp_path, chain_plan("lib/test_b.py"))["ok"]


def test_the_scope_of_a_subtask_it_waits_on_owns_a_check_path(tmp_path):
    assert check(tmp_path, chain_plan("src/test_a.py"))["ok"]


def test_the_chain_follows_a_wait_through_a_middle_subtask(tmp_path):
    contracts = {"0001-a": contract("0001-a", scope="src/**"),
                 "0002-m": contract("0002-m", scope="mid/**", blocked=["0001-a"]),
                 "0003-c": contract("0003-c", scope="lib/**", rows=path_row("src/test_a.py"), blocked=["0002-m"])}
    assert check(tmp_path, contracts)["ok"]


def test_the_scope_of_a_subtask_it_does_not_wait_on_owns_nothing(tmp_path):
    assert codes_of(check(tmp_path, chain_plan("src/test_a.py", blocked=()))) == ["check-path-unowned"]


def test_a_later_subtask_owns_nothing_for_an_earlier_one(tmp_path):
    contracts = {"0001-a": contract("0001-a", scope="src/**", rows=path_row("lib/test_b.py")),
                 "0002-b": contract("0002-b", scope="lib/**", blocked=["0001-a"])}
    assert codes_of(check(tmp_path, contracts)) == ["check-path-unowned"]


def test_a_wait_in_a_circle_ends_the_chain(tmp_path):
    contracts = {"0001-a": contract("0001-a", scope="src/**", rows=path_row("tests/x.py"), blocked=["0002-b"]),
                 "0002-b": contract("0002-b", scope="lib/**", blocked=["0001-a"])}
    assert codes_of(check(tmp_path, contracts)) == ["check-path-unowned"]


@pytest.mark.parametrize("scope, path, owned", [
    ("src/**", "src/a/b.py", True),
    ("src/**", "src", True),
    ("src/*", "src/a.py", True),
    ("src/*", "src/a/b.py", False),
    ("src/a.py", "src/a.py", True),
    ("src/a.py", "src/ab.py", False),
    ("src/a/**", "src", True),
    ("src/**/SKILL.md", "src/x/SKILL.md", True),
    ("src/**", "src/**/SKILL.md", True),
    ("src/skills/**", "src/skills/**/SKILL.md", True),
    ("src/other/**", "src/skills/**/SKILL.md", False),
    ("`src/**` — the code", "src/x.py", True),
    ("src/x.py   # one line only", "src/x.py", True),
    ("# docs only", "src/x.py", False),
])
def test_a_scope_owns_a_path(tmp_path, scope, path, owned):
    contracts = {"0001-a": contract("0001-a", scope=scope, rows=f"| unit | `python -m pytest {path} -q` | it passes |")}
    assert check(tmp_path, contracts)["ok"] is owned


@pytest.mark.parametrize("cell", [
    "`python -m pytest tests/x.py -q`", "`./mvnw -f pom.xml test`", "`scripts/run_all`", "`rg -F \"a b\" notes.md`",
    r"`python tests\x.py -q`",
])
def test_each_path_form_is_read_from_a_check_cell(tmp_path, cell):
    answer = check(tmp_path, {"0001-a": contract("0001-a", rows=f"| unit | {cell} | it passes |")})
    assert "check-path-unowned" in codes_of(answer)


@pytest.mark.parametrize("cell", [
    "`git --version`", "`python -m pkg.module -q`", "`curl http://example.test/a/b`", "`python --basetemp=x/y -q`",
    "`git diff origin/main`", "`python /abs/tool.py -q`", "`python -c \"a/b.py\"`", "`python tool.py > out/report.txt`",
    "run tests/x.py by hand",
])
def test_other_words_of_a_check_cell_are_no_paths(tmp_path, cell):
    rows = f"| unit | {cell} | it passes |"
    answer = check(tmp_path, {"0001-a": contract("0001-a", scope=["src/**", "tool.py"], rows=rows)})
    assert "check-path-unowned" not in codes_of(answer)


def test_a_not_applicable_row_needs_no_path_owner(tmp_path):
    rows = "| unit | not applicable: `python tests/x.py` needs a service | it passes |"
    assert check(tmp_path, {"0001-a": contract("0001-a", rows=rows)})["ok"]


# The disk and git side: every command comes from a fence of SKILL.md.

SKILL_MD = SKILL_DIR / "SKILL.md"
PLAN_FORMAT = SKILL_DIR / "PLAN-FORMAT.md"
SPEC_FIXTURES = FIXTURES / "propose_solution"
PLAN_FIXTURES = FIXTURES / "to_subtasks"
START_GATE = SKILLS / "autopilot" / "scripts" / "start_gate.py"
PLAN_CONTRACT = SKILLS / "autopilot" / "scripts" / "plan_contract.py"
ENGINE = PLUGIN / "engine" / "engine.py"
PLAN_FILES = "scripts/plan_files.py"
STEP = re.compile(r"^ *```sh step=([\w-]+)\n *(.*?)\n *```", re.S | re.M)
STEP_ORDER = ["start", "check", "citations", "commit", "division", "present", "wait", "ingest", "apply-readings", "approve"]
FEATURE = "feat/PROJ-1"
RUN = "feat/PROJ-1-run"
APPROVAL_LINE = re.compile(r"> Division: approved (\d{4}-\d{2}-\d{2})\s*")


def skill_steps():
    return dict(STEP.findall(SKILL_MD.read_text("utf-8")))


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, f"git {args}: {done.stderr}"
    return done.stdout.strip()


def new_repo(path, branch=FEATURE):
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", branch)
    for key, value in (("user.name", "Test"), ("user.email", "test@example.test"), ("core.autocrlf", "false")):
        git(path, "config", key, value)
    return path


def commit_all(path, message="work"):
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", message)


class World:
    """A plugin tree with the fakes, and a feature branch that holds the code and the spec folder."""

    def __init__(self, root, prd=True, sdd=True, config=True):
        self.root, self.plugin, self.repo = root, root / "plugin", root / "repo"
        self.calls, self.raw = root / "calls.log", root / "raw-response.txt"
        for skill in ("to-subtasks", "propose-solution", "grill", "to-prd"):
            shutil.copytree(SKILLS / skill, self.plugin / "skills" / skill, ignore=shutil.ignore_patterns("__pycache__"))
        for fake, target in (("fake_engine.py", "engine/engine.py"), ("fake_config.py", "scripts/afkv2_config.py")):
            (self.plugin / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(FAKES / fake, self.plugin / target)
        new_repo(self.repo)
        if config:
            (self.repo / ".afkv2").mkdir()
            (self.repo / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "specs", "tracker": {"kind": "jira"}}), "utf-8")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "export.py").write_text("# the export\n", "utf-8")
        self.spec = self.repo / "specs" / "PROJ-1"
        self.spec.mkdir(parents=True)
        if prd:
            for name in ("PRD.md", "INDEX.md"):
                shutil.copy(SPEC_FIXTURES / "spec" / name, self.spec / name)
        if sdd:
            shutil.copy(SPEC_FIXTURES / "design" / "SDD.md", self.spec / "SDD.md")
            shutil.copytree(SPEC_FIXTURES / "design" / "adr", self.spec / "adr" / "design")
        (self.repo / "README.md").write_text("A repository.\n", "utf-8")
        commit_all(self.repo, "the feature branch")
        self.env = {"FAKE_CALL_LOG": str(self.calls), "FAKE_POLL_RAW": str(self.raw)}
        self.scratch = root / "scratch"
        self.scratch.mkdir()

    def run(self, step, expect=0, **values):
        """Run one stated command with its placeholders filled; return its one JSON answer."""
        command = skill_steps()[step]
        filled = {"python": Path(sys.executable), "this skill's folder": self.plugin / "skills" / "to-subtasks",
                  **{key.replace("_", " "): value for key, value in values.items()}}
        for name, value in filled.items():
            command = command.replace(f"<{name}>", Path(value).as_posix() if isinstance(value, Path) else str(value))
        left = re.findall(r"<[^<>]+>", command)
        assert not left, f"{step}: unfilled {left}"
        return self._answer(shlex.split(command), self.repo, expect, step)

    def _answer(self, command, cwd, expect, label):
        done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=120,
                              env={**os.environ, **self.env}, encoding="utf-8")
        assert done.returncode == expect, f"{label}: {done.returncode}\n{done.stdout}\n{done.stderr}"
        return json.loads(done.stdout)

    def plan_files(self, *args, cwd=None, expect=0):
        """A verb or a flag that no fence states."""
        script = self.plugin / "skills" / "to-subtasks" / PLAN_FILES
        return self._answer([sys.executable, str(script), *args], cwd or self.repo, expect, args[0])

    def start(self, expect=0):
        return self.run("start", expect=expect, ticket_key="PROJ-1")

    def cut(self, started):
        """Write the fixture plan into the run worktree: the work of the agent at the cut."""
        plan = Path(started["plan"])
        plan.mkdir(exist_ok=True)
        for path in (PLAN_FIXTURES / "plan").glob("*.md"):
            shutil.copy(path, plan / path.name)
        return plan

    def committed_plan(self):
        started = self.start()
        self.cut(started)
        self.run("commit", plan=started["plan"], message="the plan")
        return started

    def division(self, started, expect=0, why=None, replace=False):
        why_file = self.scratch / "why.json"
        why_file.write_text(json.dumps(why) if why is not None else (PLAN_FIXTURES / "why.json").read_text("utf-8"), "utf-8")
        if replace:
            return self.plan_files("division", "--replace", "--plan", started["plan"], "--doc", started["doc"], "--session", started["session"],
                                   "--ticket", "PROJ-1", "--why", str(why_file), expect=expect)
        return self.run("division", expect=expect, plan=started["plan"], doc=started["doc"], session=started["session"],
                        ticket_key="PROJ-1", why_file=why_file)

    def doc(self, started):
        return json.loads((self.repo / started["doc"]).read_text("utf-8"))

    def card(self, started):
        current = next(rnd for rnd in self.doc(started)["rounds"] if rnd["state"] == "current")
        return next(item for item in current["items"] if item["kind"] == "signoff")

    def answer(self, started, raw):
        self.raw.write_bytes(raw.encode("utf-8"))
        self.run("present", doc=started["doc"])
        self.run("wait", doc=started["doc"], raw_file=started["raw_file"])
        return self.run("ingest", doc=started["doc"], raw_file=started["raw_file"])

    def sign(self, started):
        card_id = self.card(started)["id"]
        self.answer(started, f"{card_id}: sign")
        return card_id

    def readings(self, started, content):
        path = self.scratch / "readings.json"
        path.write_text(json.dumps(content), "utf-8")
        return self.run("apply-readings", doc=started["doc"], readings=path)

    def approve(self, started, expect=0):
        return self.run("approve", expect=expect, plan=started["plan"], doc=started["doc"], spec_dir=self.spec)

    def plan_file(self, started):
        return Path(started["plan"]) / "PLAN.md"

    def header(self, started):
        return self.plan_file(started).read_text("utf-8").split("## ")[0].splitlines()

    def change_plan(self, started):
        path = Path(started["plan"]) / "0001-export-rows.md"
        path.write_text(path.read_text("utf-8").replace("one row per order", "one row per order line"), "utf-8")
        self.run("commit", plan=started["plan"], message="changed")


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def error_of(answer):
    assert answer["ok"] is False
    return answer["error"]


# Start: the inputs and the run branch.

def test_the_run_branch_name_is_the_feature_branch_with_run(world):
    started = world.start()
    assert (started["branch"], started["run_branch"]) == (FEATURE, RUN)
    assert Path(started["worktree"]).resolve() == Path(f"{world.repo}-run").resolve()
    assert git(started["worktree"], "rev-parse", "--abbrev-ref", "HEAD") == RUN


def test_start_answers_the_input_paths_and_the_paths_a_contract_cites(world):
    started = world.start()
    assert (Path(started["prd"]), Path(started["sdd"])) == (world.spec / "PRD.md", world.spec / "SDD.md")
    assert (started["parent_prd"], started["parent_sdd"]) == ("specs/PROJ-1/PRD.md", "specs/PROJ-1/SDD.md")
    assert Path(started["doc"]).parent == world.spec / "pages" and Path(started["doc"]).name.startswith("propose-solution-division-")
    assert started["resume"] is False


def test_the_run_branch_is_an_orphan_with_no_file(world):
    started = world.start()
    assert git(started["worktree"], "ls-files") == ""
    assert git(started["worktree"], "rev-list", "--count", "HEAD") == "1"
    done = subprocess.run(["git", "merge-base", FEATURE, RUN], cwd=world.repo, capture_output=True, timeout=60)
    assert done.returncode == 1, "the run branch shares no commit with the feature branch"


def test_a_second_start_reuses_the_run_worktree(world):
    first, second = world.start(), world.start()
    assert (first["created"], second["created"]) == (True, False)
    assert Path(first["worktree"]).resolve() == Path(second["worktree"]).resolve()


def test_start_needs_no_grill_log(world):
    assert not (world.spec / "GRILL-LOG.md").exists()
    assert world.start()["ok"]


@pytest.mark.parametrize("kwargs, name, writer", [
    ({"prd": False}, "PRD.md", "/afkv2:to-prd"),
    ({"sdd": False}, "SDD.md", "/afkv2:propose-solution"),
])
def test_a_missing_input_stops_and_names_its_writer(tmp_path, kwargs, name, writer):
    error = error_of(World(tmp_path, **kwargs).start(expect=1))
    assert error["code"] == "missing-input"
    assert error["missing"].endswith(name) and error["writer"] == writer and writer in error["reason"]


@pytest.mark.parametrize("source, link, writer", [
    ("PRD.md", "adr/requirements/0009-gone.md", "/afkv2:to-prd"),
    ("SDD.md", "adr/design/0009-gone.md", "/afkv2:propose-solution"),
])
def test_a_linked_adr_that_is_missing_names_its_writer(world, source, link, writer):
    with open(world.spec / source, "a", encoding="utf-8") as out:
        out.write(f"\nSee [the ADR]({link}).\n")
    error = error_of(world.start(expect=1))
    assert error["code"] == "missing-input"
    assert Path(error["missing"]) == world.spec / link and error["writer"] == writer


def test_a_missing_config_names_setup(tmp_path):
    error = error_of(World(tmp_path, config=False).start(expect=1))
    assert error["code"] == "missing-input" and "/afkv2:setup" in error["reason"]


def test_no_run_branch_exists_after_a_refused_start(tmp_path):
    world = World(tmp_path, sdd=False)
    world.start(expect=1)
    assert git(world.repo, "branch", "--list", RUN) == ""


def test_an_sdd_with_a_blocker_goes_back_to_its_writer(world):
    sdd = world.spec / "SDD.md"
    sdd.write_text(sdd.read_text("utf-8").replace("## §14 L9", "TODO later.\n\n## §14 L9"), "utf-8")
    error = error_of(world.start(expect=1))
    assert error["code"] == "sdd-not-ready" and error["writer"] == "/afkv2:propose-solution" and error["problems"]


def test_start_refuses_on_a_run_branch(world):
    started = world.start()
    answer = world.plan_files("start", "--ticket", "PROJ-1", cwd=started["worktree"], expect=1)
    assert error_of(answer)["code"] == "not-feature-branch"


def test_start_with_no_ticket_names_the_invocation(world):
    assert "invocation" in error_of(world.plan_files("start", expect=1))["writer"]


# The plan lands on the run branch only.

def test_the_plan_lands_on_the_run_branch_only(world):
    started = world.committed_plan()
    tree = git(world.repo, "ls-tree", "-r", "--name-only", RUN).splitlines()
    assert sorted(tree) == ["plan/0001-export-rows.md", "plan/0002-export-endpoint.md", "plan/PLAN.md"]
    feature = git(world.repo, "ls-tree", "-r", "--name-only", FEATURE).splitlines()
    assert not [name for name in feature if name.startswith("plan/")]
    assert git(started["worktree"], "status", "--porcelain") == ""


def test_the_slice_of_a_fixture_passes_the_check(world):
    started = world.committed_plan()
    answer = world.run("check", plan=started["plan"])
    assert answer["ok"] and answer["subtasks"] == ["0001-export-rows", "0002-export-endpoint"]
    assert answer["base"] == f"refs/heads/{FEATURE}"
    assert world.run("citations", plan=started["plan"], spec_dir=world.spec)["contracts"] == 2


@pytest.mark.parametrize("name", ["PRD.md", "SDD.md", "GRILL-LOG.md", "INDEX.md", "adr/design/0001-a.md", "pages/round.json"])
def test_commit_refuses_a_spec_folder_file_in_the_plan(world, name):
    started = world.start()
    plan = world.cut(started)
    (plan / name).parent.mkdir(parents=True, exist_ok=True)
    (plan / name).write_text("spec\n", "utf-8")
    error = error_of(world.run("commit", expect=1, plan=plan, message="the plan"))
    assert error["code"] == "not-a-run-file" and error["files"] == [f"plan/{name}"]
    assert git(started["worktree"], "rev-list", "--count", "HEAD") == "1"


def test_commit_refuses_a_file_outside_the_plan_folder(world):
    started = world.start()
    plan = world.cut(started)
    (Path(started["worktree"]) / "notes.md").write_text("notes\n", "utf-8")
    assert error_of(world.run("commit", expect=1, plan=plan, message="the plan"))["files"] == ["notes.md"]


def test_commit_refuses_outside_the_run_branch(world):
    folder = world.repo / "plan"
    folder.mkdir()
    (folder / "PLAN.md").write_text("# plan\n", "utf-8")
    assert error_of(world.run("commit", expect=1, plan=folder, message="the plan"))["code"] == "not-run-branch"


def test_commit_refuses_a_plan_folder_below_the_top(world):
    started = world.start()
    folder = Path(started["worktree"]) / "docs" / "plan"
    folder.mkdir(parents=True)
    assert error_of(world.run("commit", expect=1, plan=folder, message="the plan"))["code"] == "not-run-branch"


def test_commit_with_no_change_commits_nothing(world):
    started = world.committed_plan()
    assert world.run("commit", plan=started["plan"], message="again")["committed"] is False


# The check reads the code from the feature branch when it runs on the run branch.

def test_on_the_run_branch_an_anchor_is_read_from_the_feature_branch(world):
    (world.repo / "src" / "twice.py").write_text("def twice_defined_here(\ndef twice_defined_here(\n", "utf-8")
    commit_all(world.repo)
    started = world.start()
    plan = world.cut(started)
    (plan / "0001-export-rows.md").write_text(contract("0001-export-rows", produces=["src/twice.py#def twice_defined_here( — it"]), "utf-8")
    assert "B-AMBIGUOUS" in codes_of(cp.check_plan(plan))


def test_on_the_run_branch_a_path_on_the_feature_branch_passes(world):
    started = world.start()
    plan = world.cut(started)
    rows = "| unit | `git grep -n a README.md` | it passes |"
    (plan / "0001-export-rows.md").write_text(contract("0001-export-rows", rows=rows), "utf-8")
    assert "check-path-unowned" not in codes_of(cp.check_plan(plan))


def test_on_the_run_branch_a_path_nothing_owns_is_refused(world):
    started = world.start()
    plan = world.cut(started)
    rows = "| unit | `git grep -n a docs/gone.md` | it passes |"
    (plan / "0001-export-rows.md").write_text(contract("0001-export-rows", rows=rows), "utf-8")
    assert "check-path-unowned" in codes_of(cp.check_plan(plan))


def test_a_run_branch_with_no_feature_branch_owns_nothing(tmp_path):
    repo = new_repo(tmp_path / "repo", branch=RUN)
    rows = "| unit | `git grep -n a README.md` | it passes |"
    plan = write_plan(repo / "plan", {"0001-a": contract("0001-a", rows=rows)})
    assert "check-path-unowned" in codes_of(cp.check_plan(plan))


# Citations.

def citation_answer(world, edit):
    started = world.start()
    plan = world.cut(started)
    path = plan / "0001-export-rows.md"
    path.write_text(edit(path.read_text("utf-8")), "utf-8")
    return world.run("citations", expect=1, plan=plan, spec_dir=world.spec)


@pytest.mark.parametrize("old, new, code", [
    ("(PRD §AC-001)\n", "\n", "C-NO-CITATION"),
    ("(PRD §AC-001)\n", "(PRD §AC-999)\n", "C-UNRESOLVED"),
    ("(PRD §WE-01; SDD §8)", "(PRD §WE-01; SDD §99)", "C-UNRESOLVED"),
    ("(PRD §WE-01; SDD §8)", '(PRD §WE-01; SDD §8 row "no such row")', "C-UNRESOLVED"),
    ("(ADR-0001 design)", "(ADR-0009 design)", "C-UNRESOLVED"),
    ("(PRD §WE-01; SDD §8)", "(PRD §WE-01; GRILL-LOG §1)", "C-UNRESOLVED"),
    ("(PRD §WE-01; SDD §8)", "(PRD §WE-01; PLAN.md decision D-404)", "C-UNRESOLVED"),
    ("SDD.md#§8 L7", "SDD.md#§99 L7", "C-UNRESOLVED"),
    ("adr/design/0001-join-table-for-export-runs.md", "adr/design/0009-gone.md", "C-UNRESOLVED"),
    ("specs/PROJ-1/PRD.md", "specs/PROJ-1/OTHER.md", "C-PARENT"),
    ("## Parent SDD\nspecs/PROJ-1/SDD.md", "## Parent SDD\n", "C-PARENT"),
])
def test_a_citation_that_does_not_resolve_is_refused(world, old, new, code):
    def edit(text):
        assert old in text
        return text.replace(old, new)
    assert code in codes_of(citation_answer(world, edit))


def test_a_contract_with_no_sdd_citation_is_refused(world):
    def edit(text):
        return text.replace("(PRD §WE-01; SDD §8)", "(PRD §WE-01)").replace("- SDD: SDD.md#§8 L7 — Module Decomposition — the one module\n", "")
    assert "C-NOT-CITED" in codes_of(citation_answer(world, edit))


def test_a_contract_with_no_prd_citation_is_refused(world):
    def edit(text):
        return text.replace("(PRD §AC-001)", "(SDD §8)").replace("(PRD §WE-01; SDD §8)", "(SDD §8)")
    assert "C-NOT-CITED" in codes_of(citation_answer(world, edit))


def test_a_wrapped_acceptance_bullet_reads_as_one_bullet(world):
    started = world.start()
    plan = world.cut(started)
    path = plan / "0001-export-rows.md"
    path.write_text(path.read_text("utf-8").replace("gives 2 rows. (PRD", "gives\n  2 rows. (PRD"), "utf-8")
    assert world.run("citations", plan=plan, spec_dir=world.spec)["ok"]


def test_every_citation_failure_is_listed(world):
    def edit(text):
        return text.replace("(PRD §AC-001)\n", "(PRD §AC-999)\n").replace("(PRD §WE-01; SDD §8)", "(PRD §WE-99; SDD §99)")
    assert len(failures_of(citation_answer(world, edit))) == 3


# The division.

def test_division_writes_one_sign_off_card_that_shows_every_subtask(world):
    started = world.committed_plan()
    answer = world.division(started)
    doc = world.doc(started)
    card = world.card(started)
    assert answer["card"] == card["id"] == answer["items"][0]
    assert (card["kind"], card["state"], doc["session"]["skill"]) == ("signoff", "open", "propose-solution")
    rows = card["body"]["props"]["rows"]
    assert [row[0] for row in rows] == ["0001-export-rows", "0002-export-endpoint"]
    assert rows[1][3] == "0001-export-rows" and rows[1][4] == "static, unit, api (not applicable)"
    assert all(len(row) == len(card["body"]["props"]["columns"]) for row in rows)
    assert "app: none" in card["body"]["children"][0]["props"]["text"]


@pytest.mark.parametrize("why", [{"0001-export-rows": "Only one."}, {"0001-export-rows": "a", "0002-export-endpoint": " "},
                                 {"0001-export-rows": "a", "0002-export-endpoint": "b", "0009-x": "c"}])
def test_division_needs_one_sentence_per_subtask(world, why):
    started = world.committed_plan()
    assert error_of(world.division(started, expect=1, why=why))["code"] == "bad-why"


def test_division_refuses_a_plan_that_fails_its_check(world):
    started = world.committed_plan()
    path = Path(started["plan"]) / "0002-export-endpoint.md"
    path.write_text(path.read_text("utf-8").replace("def export_rows_for_day(", "def another_name_here("), "utf-8")
    assert error_of(world.division(started, expect=1))["code"] == "plan-check-failed"
    assert not (world.repo / started["doc"]).exists()


def test_division_refuses_a_plan_that_is_not_committed(world):
    started = world.committed_plan()
    path = Path(started["plan"]) / "0001-export-rows.md"
    path.write_text(path.read_text("utf-8") + "\nMore.\n", "utf-8")
    assert error_of(world.division(started, expect=1))["code"] == "plan-not-committed"


def test_the_digest_ignores_the_division_line_and_the_date_and_line_ends(world):
    started = world.committed_plan()
    before = plan_files.plan_digest(started["plan"])
    path = world.plan_file(started)
    text = path.read_text("utf-8")
    stamped = text.replace("> Last updated: 2026-01-05", "> Last updated: 2026-02-02\n> Division: approved 2026-02-02")
    path.write_bytes(stamped.replace("\n", "\r\n").encode("utf-8"))
    assert plan_files.plan_digest(started["plan"]) == before
    path.write_text(text.replace("The export rows", "Other title"), "utf-8")
    assert plan_files.plan_digest(started["plan"]) != before


# The approval.

def test_a_sign_mark_writes_the_division_line(world):
    started = world.committed_plan()
    world.division(started)
    world.sign(started)
    answer = world.approve(started)
    day = date.today().isoformat()
    assert answer["approved"] == day and answer["index_missing"] is False
    assert [line for line in world.header(started) if APPROVAL_LINE.fullmatch(line)] == [f"> Division: approved {day}"]
    assert world.run("check", plan=started["plan"])["division"] == {"approved": True, "date": day}
    assert git(started["worktree"], "status", "--porcelain") == ""
    assert f"> Division: approved {day}" in git(world.repo, "show", f"{RUN}:plan/PLAN.md")


def test_a_second_approve_writes_nothing_new(world):
    started = world.committed_plan()
    world.division(started)
    world.sign(started)
    first, second = world.approve(started), world.approve(started)
    assert first["head"] == second["head"]
    assert world.plan_file(started).read_text("utf-8").count("> Division:") == 1


def test_the_approval_writes_the_plan_row_of_the_index(world):
    started = world.committed_plan()
    world.division(started)
    world.sign(started)
    world.approve(started)
    index = (world.spec / "INDEX.md").read_text("utf-8")
    assert f"| Plan | {RUN}:plan/PLAN.md | 2 subtasks; division approved {date.today().isoformat()} |" in index
    assert "| PRD | PRD.md | draft |" in index


def test_an_approval_with_no_index_says_so(world):
    (world.spec / "INDEX.md").unlink()
    started = world.committed_plan()
    world.division(started)
    world.sign(started)
    assert world.approve(started)["index_missing"] is True


def test_without_the_division_line_the_plan_is_not_approved(world):
    started = world.committed_plan()
    world.division(started)
    assert world.run("check", plan=started["plan"])["division"]["approved"] is False
    assert not [line for line in world.header(started) if line.startswith("> Division:")]


def test_approve_refuses_a_plan_nobody_has_seen(world):
    started = world.committed_plan()
    assert error_of(world.approve(started, expect=1))["code"] == "not-approved"
    assert "Division" not in world.plan_file(started).read_text("utf-8")


def test_approve_refuses_an_unanswered_card(world):
    started = world.committed_plan()
    world.division(started)
    assert error_of(world.approve(started, expect=1))["code"] == "not-approved"


def test_a_changes_mark_is_no_approval(world):
    started = world.committed_plan()
    world.division(started)
    card_id = world.card(started)["id"]
    world.answer(started, f"{card_id}: changes")
    assert error_of(world.approve(started, expect=1))["code"] == "not-approved"
    world.readings(started, {"open": [{"item": card_id, "reply": "I will cut it again."}]})
    assert error_of(world.approve(started, expect=1))["code"] == "not-approved"
    assert "Division" not in world.plan_file(started).read_text("utf-8")


def test_a_sign_on_an_older_plan_does_not_approve_a_changed_plan(world):
    started = world.committed_plan()
    world.division(started)
    world.sign(started)
    world.change_plan(started)
    assert error_of(world.approve(started, expect=1))["code"] == "not-approved"
    assert "Division" not in world.plan_file(started).read_text("utf-8")


def test_a_clear_note_settles_the_card_and_approves(world):
    started = world.committed_plan()
    world.division(started)
    card_id = world.card(started)["id"]
    world.answer(started, f"{card_id}: note: Fine, go ahead.")
    note = world.card(started)["notes"][0]["id"]
    world.readings(started, {"settle": [{"item": card_id, "note": note, "reading": "Approves the division as shown."}]})
    assert world.approve(started)["ok"]


def test_a_note_that_changes_the_card_returns_it_for_a_sign_mark(world):
    """The plan changes, so only the new card, marked with sign, approves it."""
    started = world.committed_plan()
    world.division(started)
    old = world.card(started)["id"]
    world.answer(started, f"{old}: note: Merge the 2 subtasks.")
    world.readings(started, {"open": [{"item": old, "reply": "I cut it again with your change."}]})
    world.change_plan(started)
    world.division(started)
    new = world.card(started)
    assert new["id"] != old
    assert old in new["body"]["children"][-1]["props"]["text"], "the new card carries the old one"
    assert error_of(world.approve(started, expect=1))["code"] == "not-approved"
    world.sign(started)
    assert world.approve(started)["ok"]


def test_only_the_newest_card_of_the_same_plan_counts(world):
    started = world.committed_plan()
    world.division(started)
    world.sign(started)
    world.division(started)
    world.answer(started, f"{world.card(started)['id']}: changes")
    assert error_of(world.approve(started, expect=1))["code"] == "not-approved"


def test_division_takes_back_an_earlier_approval(world):
    started = world.committed_plan()
    world.division(started)
    world.sign(started)
    world.approve(started)
    world.division(started)
    assert "> Division:" not in world.plan_file(started).read_text("utf-8")
    assert git(started["worktree"], "status", "--porcelain") == ""
    assert "> Division:" not in git(world.repo, "show", f"{RUN}:plan/PLAN.md")


def test_a_corrected_round_replaces_an_unanswered_one(world):
    started = world.committed_plan()
    first = world.division(started)
    second = world.division(started, replace=True)
    assert first["round"] == second["round"] == 1
    assert len(world.doc(started)["rounds"]) == 1


def test_a_corrected_round_keeps_carrying_a_returned_card(world):
    started = world.committed_plan()
    world.division(started)
    old = world.card(started)["id"]
    world.answer(started, f"{old}: changes")
    world.readings(started, {"open": [{"item": old, "reply": "Again."}]})
    world.division(started)
    assert world.division(started, replace=True)["round"] == 2
    assert old in world.card(started)["body"]["children"][-1]["props"]["text"]


def test_start_resumes_an_unapproved_session(world):
    started = world.committed_plan()
    world.division(started)
    again = world.start()
    assert (again["resume"], again["session"], again["doc"]) == (True, started["session"], started["doc"])


def test_an_approved_plan_starts_a_new_session(world):
    started = world.committed_plan()
    world.division(started)
    world.sign(started)
    world.approve(started)
    assert world.start()["resume"] is False


def test_a_design_session_after_the_division_session_stays_the_newest(world):
    """The engine names the file by the session skill, so propose-solution sees the division document too."""
    started = world.committed_plan()
    world.division(started)
    pages = Path(started["doc"]).parent
    (pages / f"{design_files.DOC_PREFIX}s-20200101-000000.json").write_text("{}", "utf-8")
    log = world.scratch / "log.md"
    log.write_text("", "utf-8")
    assert design_files._open_session(pages, log) == "s-20200101-000000"


def test_a_polled_answer_on_disk_is_pending_at_start(world):
    started = world.committed_plan()
    world.division(started)
    (world.repo / started["raw_file"]).write_text("an answer", "utf-8")
    assert world.start()["raw_pending"] is True


# The skill text and the format files.

def test_the_skill_states_each_step_in_order():
    assert list(skill_steps()) == STEP_ORDER


def test_the_skill_frontmatter_has_name_and_description():
    head = SKILL_MD.read_text("utf-8").split("---")[1]
    assert "name: to-subtasks" in head and "description: /afkv2:to-subtasks" in head


def test_the_links_of_the_skill_resolve():
    for path in SKILL_DIR.glob("*.md"):
        for target in re.findall(r"\]\(([^)#]+\.md)\)", path.read_text("utf-8")):
            assert (path.parent / target).is_file(), f"{path.name}: {target}"


def test_the_grill_step_named_for_the_reading_keys_states_them():
    grill = (SKILLS / "grill" / "SKILL.md").read_text("utf-8")
    step = re.search(r"^7\. .*?(?=^8\. )", grill, re.S | re.M).group(0)
    assert "apply-readings" in step and "settle" in step


def test_the_conflict_procedure_heading_stands_once():
    assert (SKILL_DIR / "SUBTASK-CONTRACT.md").read_text("utf-8").count("## Conflict procedure") == 1


def test_the_plan_template_has_each_line_autopilot_reads():
    template = PLAN_FORMAT.read_text("utf-8").split("```")[1]
    assert "> App: " in template and "## Progress tracker" in template and "| Subtask |" in template and "| Status |" in template
    assert "> Division:" not in template, "only approve writes the division line"
    assert not re.search("/af[k]:", template), "autopilot reads this in a header as a v1 plan"


@pytest.mark.parametrize("path", [path for path in sorted(SKILL_DIR.glob("**/*"), key=str) if path.is_file() and path.suffix in {".md", ".py"}], ids=lambda path: path.name)
def test_no_file_names_the_v1_plugin(path):
    assert not re.search(r"\bafk(?!v2)\b", path.read_text("utf-8"))


def test_the_fixture_contract_holds_each_section_of_the_format():
    sections = cp.sections_of((PLAN_FIXTURES / "plan" / "0002-export-endpoint.md").read_text("utf-8"))
    required, optional = cp.contract_sections()
    assert not set(required) - set(sections)
    assert "Consumes" in optional and "Review" in optional


# The S3 and S1 contracts: these run once those sessions merge.

def load_by_path(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not START_GATE.exists(), reason="S3 has not merged: start_gate.py")
def test_the_not_applicable_form_is_in_lockstep_with_the_start_gate():
    gate = load_by_path(START_GATE)
    assert gate.NOT_APPLICABLE == cp.NOT_APPLICABLE and set(gate.LIVE_TIERS) == cp.LIVE_TIERS
    for cell in ("not applicable: no app", "not applicable:", "n/a", "Not applicable: x"):
        assert gate.is_not_applicable(SimpleNamespace(check=cell)) == cp.is_not_applicable(cell), cell


@pytest.mark.skipif(not START_GATE.exists(), reason="S3 has not merged: start_gate.py")
def test_an_approved_plan_passes_each_plan_rule_of_the_real_start_gate(world):
    gate = load_by_path(START_GATE)
    started = world.committed_plan()
    world.division(started)
    world.sign(started)
    world.approve(started)
    plan, text = Path(started["plan"]), world.plan_file(started).read_text("utf-8")
    assert gate._v1_signs(plan, text) == []
    assert gate.plan_check_failures(plan) == []
    assert gate.approval_failures(text) == []
    rows, contracts, failures = gate.contracts_of(plan)
    assert failures == [] and [item.id for item in contracts] == ["0001-export-rows", "0002-export-endpoint"]
    assert [item for each in contracts for item in gate.gate_failures(each)] == []


@pytest.mark.skipif(not PLAN_CONTRACT.exists(), reason="S3 has not merged: plan_contract.py")
def test_the_contract_headings_are_in_lockstep_with_autopilot():
    module = load_by_path(PLAN_CONTRACT)
    required, optional = cp.contract_sections()
    assert set(module.REQUIRED_SECTIONS) == set(required)
    assert set(module.OPTIONAL_SECTIONS) == set(optional)


@pytest.mark.skipif(not ENGINE.exists(), reason="S1 has not merged: the page engine")
def test_the_division_document_passes_the_real_engine(world):
    started = world.committed_plan()
    world.division(started)
    for verb in ("check", "render"):
        done = subprocess.run([sys.executable, str(ENGINE), verb, started["doc"]], cwd=world.repo, capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert done.returncode == 0, done.stdout + done.stderr
