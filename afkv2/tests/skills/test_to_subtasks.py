"""Tests for the to-subtasks skill.

The plan check runs as the command `/afkv2:autopilot` starts, or in process. The dry runs take every
command from the fenced `sh step=...` blocks of SKILL.md, in a temporary git repository, with the
recorded fakes of the page engine and the config reader (fakes/). Once S1 and S3 merge, the same plan
also goes through the real engine and the real start gate.
"""

import json
import subprocess
import sys
from pathlib import Path

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
