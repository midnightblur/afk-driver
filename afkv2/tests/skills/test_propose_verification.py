"""Tests for the propose-verification skill: the session paths, the notes copy, and VERIFICATION.md.

A throwaway git repository holds the config, the spec folder and the feature branch. No herdr, no page host and no
live build run here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
SKILL_DIR = PLUGIN / "skills" / "propose-verification"
SCRIPT = SKILL_DIR / "scripts" / "verification_files.py"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import verification_files as vf  # noqa: E402
from grill_common import Refusal  # noqa: E402

TICKET = "PROJ-7"
PRD = """# PRD — sample

## Acceptance Criteria

- [ ] AC-001 The list page → shows each order with its total.
- [ ] AC-002 A bad order id → the API answers 404.
- [ ] AC-003 retired: merged into AC-001
- [ ] AC-004 The order store keeps a total in cents.
"""


def git(repo, *args):
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def commit(repo, name, text="x\n"):
    (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", name)
    return git(repo, "rev-parse", "HEAD")


class Repo(type(Path())):
    """The repository path, with the commit the target branch holds."""
    old_head = None


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / ".afkv2").mkdir()
    (root / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "docs", "tracker": {"kind": "jira"}}),
                                                 encoding="utf-8")
    old = commit(root, "base.txt")
    git(root, "checkout", "-q", "-b", "feat/x")
    spec = root / "docs" / TICKET
    (spec / "pages").mkdir(parents=True)
    (spec / "PRD.md").write_text(PRD, encoding="utf-8")
    (spec / "SDD.md").write_text("# SDD\n", encoding="utf-8")
    (spec / "GRILL-LOG.md").write_text("# Grill log\n\n## Requirements\n", encoding="utf-8")
    (spec / "INDEX.md").write_text("# PROJ-7\n\n| Artifact | Where | State |\n|---|---|---|\n| PRD | PRD.md | draft |\n",
                                   encoding="utf-8")
    git(root, "add", "-A")
    git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "spec")
    root = Repo(root)
    root.old_head = old
    return root


def set_live(repo, proven_head):
    config = json.loads((repo / ".afkv2" / "config.json").read_text(encoding="utf-8"))
    config["live"] = {"start": "python -m http.server 4999", "address": "http://127.0.0.1:4999", "ready_seconds": 30,
                      "stop": None, "needs": [], "proven_at": "2026-11-11", "proven_head": proven_head}
    (repo / ".afkv2" / "config.json").write_text(json.dumps(config), encoding="utf-8")


def row(rid, criteria, level, **extra):
    base = {"id": rid, "criteria": criteria, "story": "1", "given": "an order of 2 lines",
            "when": "the user opens the list", "then": "the order shows its total, 12.50", "level": level,
            "data": "seed orders | 2 lines", "environment": "the live build", "status": "active"}
    return {**base, **extra}


def plan(**extra):
    base = {"ticket": TICKET, "app": "config",
            "rows": [row("VR-001", ["AC-001"], "ui-e2e"), row("VR-002", ["AC-002"], "api"),
                     row("VR-003", ["AC-004"], "unit"), row("VR-004", [], "static")],
            "internal": [{"criterion": "AC-004", "why": "a storage detail no user sees"}],
            "boundaries": []}
    return {**base, **extra}


def doc_with(item_id, state="settled_by_mark", by="mark"):
    item = {"id": item_id, "kind": "confirm", "state": state, "title": "t"}
    if state.startswith("settled"):
        item["settled"] = {"by": by, "round": 1, "signal": "accept"}
    return {"schema": "afkv2.page/2", "notes": [], "rounds": [{"n": 1, "items": [item]}]}


def write(repo, payload, doc=None):
    return vf.write_verification(repo / "docs" / TICKET, payload, doc or doc_with("c-none"), repo_root=repo,
                                 target="main")


def refused(code, repo, payload, doc=None):
    with pytest.raises(Refusal) as caught:
        write(repo, payload, doc)
    assert caught.value.code == code, caught.value.reason
    return caught.value


# --- write and read_rows ---------------------------------------------------------------------------------------

def test_write_then_read_rows_round_trips_every_field(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    answer = write(repo, plan())
    path = Path(answer["verification"])
    assert path == repo / "docs" / TICKET / "VERIFICATION.md"
    text = path.read_text(encoding="utf-8")
    assert "Owner" not in text
    assert "> App: config" in text
    rows = vf.read_rows(path)
    assert [r["id"] for r in rows] == ["VR-001", "VR-002", "VR-003", "VR-004"]
    first = rows[0]
    assert first["criteria"] == ["AC-001"] and first["level"] == "ui-e2e" and first["tier"] == "high"
    assert first["given"] == "an order of 2 lines" and first["then"] == "the order shows its total, 12.50"
    assert first["data"] == "seed orders | 2 lines" and first["environment"] == "the live build"
    assert first["status"] == "active" and first["story"] == "1"
    assert rows[2]["tier"] == "low" and rows[3]["criteria"] == []
    assert set(first) == {"id", "criteria", "story", "given", "when", "then", "level", "tier", "data",
                          "environment", "status"}


def test_write_sets_the_index_row(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    write(repo, plan())
    spec = repo / "docs" / TICKET
    assert "| Verification plan | VERIFICATION.md | draft |" in (spec / "INDEX.md").read_text(encoding="utf-8")


def test_read_rows_reads_columns_by_header_name(tmp_path):
    path = tmp_path / "VERIFICATION.md"
    path.write_text("# Verification plan\n\n## Plan rows\n\n"
                    "| Level | Id | Tier | Criteria | Story | Given | When | Then | Data | Environment | Status | Later |\n"
                    "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
                    "| api | VR-009 | high | AC-002, AC-005 | — | g | w | t \\| more | — | env | retired: gone | x |\n",
                    encoding="utf-8")
    [only] = vf.read_rows(path)
    assert only["id"] == "VR-009" and only["level"] == "api" and only["criteria"] == ["AC-002", "AC-005"]
    assert only["then"] == "t | more" and only["story"] is None and only["data"] is None
    assert only["status"] == "retired: gone"


def test_read_rows_refuses_a_file_without_a_needed_column(tmp_path):
    path = tmp_path / "VERIFICATION.md"
    path.write_text("## Plan rows\n\n| Id | Level |\n|---|---|\n| VR-001 | api |\n", encoding="utf-8")
    with pytest.raises(Refusal) as caught:
        vf.read_rows(path)
    assert caught.value.code == "bad-verification"


def test_a_second_write_keeps_each_old_id(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    write(repo, plan())
    rows = [row("VR-001", ["AC-001"], "ui-e2e"), row("VR-002", ["AC-002"], "api")]
    refused("row-dropped", repo, plan(rows=rows))
    rows += [row("VR-003", ["AC-004"], "unit", status="retired: the store keeps no total"),
             row("VR-004", [], "static", status="retired: no lint rule")]
    write(repo, plan(rows=rows))
    assert [r["status"] for r in vf.read_rows(repo / "docs" / TICKET / "VERIFICATION.md")][2].startswith("retired:")


# --- the row rules -----------------------------------------------------------------------------------------------

def test_each_user_visible_criterion_needs_an_active_high_row(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    rows = [row("VR-001", ["AC-001"], "ui-e2e"), row("VR-002", ["AC-002"], "integration")]
    reason = refused("ac-no-high-row", repo, plan(rows=rows)).reason
    assert "AC-002" in reason and "AC-001" not in reason
    retired = [row("VR-001", ["AC-001"], "ui-e2e"), row("VR-002", ["AC-002"], "api", status="retired: dropped")]
    assert "AC-002" in refused("ac-no-high-row", repo, plan(rows=retired)).reason


def test_a_criterion_with_no_user_visible_outcome_needs_no_high_row(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    rows = [row("VR-001", ["AC-001"], "ui-e2e"), row("VR-002", ["AC-002"], "api")]
    write(repo, plan(rows=rows))
    refused("ac-no-high-row", repo, plan(rows=rows, internal=[]))


def test_a_retired_criterion_needs_no_row_and_takes_no_active_row(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    rows = [row("VR-001", ["AC-001", "AC-003"], "ui-e2e"), row("VR-002", ["AC-002"], "api")]
    assert "AC-003" in refused("criterion-retired", repo, plan(rows=rows)).reason


def test_an_unknown_criterion_refuses(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    rows = [row("VR-001", ["AC-001", "AC-099"], "ui-e2e"), row("VR-002", ["AC-002"], "api")]
    assert "AC-099" in refused("criterion-unknown", repo, plan(rows=rows)).reason
    refused("criterion-unknown", repo, plan(internal=[{"criterion": "AC-098", "why": "x"}]))


@pytest.mark.parametrize("bad, code", [
    ({"id": "VR-1"}, "bad-row"),
    ({"level": "smoke"}, "bad-row"),
    ({"tier": "low"}, "tier-mismatch"),
    ({"then": " "}, "bad-row"),
    ({"criteria": []}, "bad-row"),
    ({"status": "parked"}, "bad-row"),
    ({"status": "lower: ui-e2e to api"}, "bad-row"),
    ({"status": "lower: api to ui-e2e · c-low"}, "bad-row"),
])
def test_a_bad_row_refuses(repo, bad, code):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    rows = [{**row("VR-001", ["AC-001"], "ui-e2e"), **bad}, row("VR-002", ["AC-002"], "api")]
    refused(code, repo, plan(rows=rows))


def test_a_reused_id_refuses(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    rows = [row("VR-001", ["AC-001"], "ui-e2e"), row("VR-001", ["AC-002"], "api")]
    refused("bad-row", repo, plan(rows=rows))


def test_a_lower_level_needs_the_developers_mark(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    rows = [row("VR-001", ["AC-001"], "api", status="lower: ui-e2e to api · c-low"), row("VR-002", ["AC-002"], "api")]
    refused("lower-level-unmarked", repo, plan(rows=rows), doc_with("c-low", state="open"))
    refused("lower-level-unmarked", repo, plan(rows=rows), doc_with("c-other"))
    write(repo, plan(rows=rows), doc_with("c-low"))
    stored = vf.read_rows(repo / "docs" / TICKET / "VERIFICATION.md")[0]
    assert stored["status"] == "lower: ui-e2e to api · c-low" and stored["level"] == "api"


def test_a_lower_level_below_high_still_covers_its_criterion(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    rows = [row("VR-001", ["AC-001"], "unit", status="lower: ui-e2e to unit · c-low"), row("VR-002", ["AC-002"], "api")]
    write(repo, plan(rows=rows), doc_with("c-low"))


# --- the boundaries (contract level) -----------------------------------------------------------------------------

def test_a_boundary_with_a_contract_test_needs_an_active_contract_row(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    boundary = {"boundary": "orders API to the portal", "contract": True, "rows": ["VR-002"], "ticket": None}
    refused("boundary-uncovered", repo, plan(boundaries=[boundary]))
    rows = [*plan()["rows"], row("VR-005", ["AC-002"], "contract")]
    write(repo, plan(rows=rows, boundaries=[{**boundary, "rows": ["VR-005"]}]))


def test_a_boundary_with_no_contract_test_needs_a_ticket_and_the_api_floor(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    boundary = {"boundary": "orders API to the portal", "contract": False, "rows": ["VR-002"],
                "ticket": "set up a contract test between the orders API and the portal"}
    write(repo, plan(boundaries=[boundary]))
    text = (repo / "docs" / TICKET / "VERIFICATION.md").read_text(encoding="utf-8")
    assert "set up a contract test between the orders API and the portal" in text
    refused("boundary-uncovered", repo, plan(boundaries=[{**boundary, "ticket": None}]))
    refused("boundary-uncovered", repo, plan(boundaries=[{**boundary, "rows": ["VR-003"]}]))
    refused("boundary-uncovered", repo, plan(boundaries=[{**boundary, "rows": ["VR-077"]}]))


# --- the live build (SDD §6 I-13) --------------------------------------------------------------------------------

def test_no_live_block_refuses_live_unproven(repo):
    assert "live" in refused("live-unproven", repo, plan()).reason


def test_a_block_proven_before_the_feature_refuses(repo):
    set_live(repo, repo.old_head)
    refused("live-unproven", repo, plan())


def test_a_block_proven_at_an_earlier_commit_of_the_feature_passes(repo):
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    commit(repo, "later.txt")
    answer = write(repo, plan())
    assert "> App: config" in Path(answer["verification"]).read_text(encoding="utf-8")


def test_a_block_proven_at_a_commit_outside_the_branch_refuses(repo):
    set_live(repo, "0" * 40)
    refused("live-unproven", repo, plan())


def test_app_none_needs_the_developers_mark(repo):
    payload = plan(app={"none": "c-none"})
    refused("live-unproven", repo, payload, doc_with("c-none", state="open"))
    refused("live-unproven", repo, payload, doc_with("c-none", state="settled_by_note", by="note"))
    answer = write(repo, payload, doc_with("c-none"))
    assert "> App: none · c-none" in Path(answer["verification"]).read_text(encoding="utf-8")


def test_a_bad_app_value_refuses(repo):
    refused("bad-payload", repo, plan(app="maybe"))


# --- start and sync ----------------------------------------------------------------------------------------------

def test_start_names_the_writer_of_a_missing_sdd(repo, monkeypatch):
    (repo / "docs" / TICKET / "SDD.md").unlink()
    monkeypatch.chdir(repo)
    with pytest.raises(Refusal) as caught:
        vf.start(["--ticket", TICKET])
    assert caught.value.code == "missing-input" and caught.value.extra["writer"] == "/afkv2:propose-solution"


def test_start_answers_the_session_paths_and_the_live_state(repo, monkeypatch):
    monkeypatch.chdir(repo)
    answer = vf.start(["--ticket", TICKET])
    spec = (repo / "docs" / TICKET).resolve()
    assert Path(answer["verification"]) == spec / "VERIFICATION.md" and answer["verification_exists"] is False
    assert Path(answer["doc"]).parent == spec / "pages"
    assert Path(answer["doc"]).name == f"propose-verification-{answer['session']}.json"
    assert answer["resume"] is False and answer["live"] == {"block": False, "proven_here": False}
    assert "## Verification plan" in (spec / "GRILL-LOG.md").read_text(encoding="utf-8")
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    assert vf.start(["--ticket", TICKET, "--target", "main"])["live"] == {"block": True, "proven_here": True}
    set_live(repo, repo.old_head)
    assert vf.start(["--ticket", TICKET, "--target", "main"])["live"] == {"block": True, "proven_here": False}


def test_start_resumes_an_open_session_and_not_a_written_one(repo, monkeypatch):
    monkeypatch.chdir(repo)
    first = vf.start(["--ticket", TICKET])
    Path(first["doc"]).write_text(json.dumps(doc_with("c-1")), encoding="utf-8")
    again = vf.start(["--ticket", TICKET])
    assert again["resume"] is True and again["session"] == first["session"]
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    vf.write_verification(repo / "docs" / TICKET, plan(), doc_with("c-1"), repo_root=repo, target="main",
                          session=first["session"])
    assert vf.start(["--ticket", TICKET])["resume"] is False


def test_sync_copies_each_new_note_once(repo, monkeypatch):
    monkeypatch.chdir(repo)
    answer = vf.start(["--ticket", TICKET])
    doc = doc_with("c-1")
    doc["notes"] = [{"id": "N-1-c-1-1", "round": 1, "target": "c-1", "item": "c-1", "text": "use 2 orders",
                     "deleted": False}]
    Path(answer["doc"]).write_text(json.dumps(doc), encoding="utf-8")
    log = Path(answer["log"])
    assert vf.sync(["--doc", answer["doc"], "--log", str(log)])["notes"] == 1
    assert vf.sync(["--doc", answer["doc"], "--log", str(log)])["notes"] == 0
    assert '- Note: N-1-c-1-1 · R1 · on c-1: "use 2 orders"' in log.read_text(encoding="utf-8")


# --- the command line ----------------------------------------------------------------------------------------------

def test_the_write_command_answers_one_json_object(repo, tmp_path):
    payload_file, doc_file = tmp_path / "plan.json", tmp_path / "doc.json"
    payload_file.write_text(json.dumps(plan()), encoding="utf-8")
    doc_file.write_text(json.dumps(doc_with("c-1")), encoding="utf-8")
    argv = [sys.executable, str(SCRIPT), "write", "--spec-dir", str(repo / "docs" / TICKET), "--plan",
            str(payload_file), "--doc", str(doc_file), "--target", "main"]
    done = subprocess.run(argv, cwd=repo, capture_output=True, text=True)
    assert done.returncode == 1 and json.loads(done.stdout)["error"]["code"] == "live-unproven"
    set_live(repo, git(repo, "rev-parse", "HEAD"))
    done = subprocess.run(argv, cwd=repo, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout
    answer = json.loads(done.stdout)
    assert answer["ok"] is True and answer["rows"] == 4


# --- the page session (SDD §3 row S-13) ------------------------------------------------------------------------------

ROUND = {"banner": {"settled": [], "unlocks": [], "parked": []},
         "items": [{"id": "c-1", "kind": "confirm", "body": {"type": "text", "id": "c-1-body", "props": {"text": "x"}}}]}


@pytest.mark.parametrize("skill, step", [("propose-verification", "Verification plan"), ("small-change", None)])
def test_a_version_2_page_of_each_new_writer_passes_the_engine_check(tmp_path, skill, step):
    sys.path.insert(0, str(PLUGIN / "skills" / "use-lavish" / "scripts"))
    import round_document as rd
    doc_path = tmp_path / f"{skill}-s-1.json"
    session = {"id": "s-1", "skill": rd._skill_of(doc_path, "s-1"), "feature": TICKET, "ticket": TICKET}
    if skill == "propose-verification":
        assert session["skill"] == skill
    else:
        session["skill"] = skill
    rd.build_round_document(doc_path, session, ROUND)
    stored = json.loads(doc_path.read_text(encoding="utf-8"))["session"]
    assert stored["skill"] == skill
    if step:
        assert stored["step"] == step


# --- the verification proposers (SDD §8 row "proposer engine"; design ADR-0008) ---------------------------------------

def test_the_verification_proposers_run_the_engine_with_their_own_adapter(tmp_path):
    from test_proposers import BASE, FakeRunner
    import verification_proposers as vp
    runner = FakeRunner(tmp_path)
    pages = tmp_path / "repo" / "docs" / "pages"
    pages.mkdir(parents=True)
    doc = pages / "propose-verification-s-1.json"
    brief = tmp_path / "brief.md"
    brief.write_text("Draft the verification plan.", encoding="utf-8")
    assert vp.VERBS == vp.engine.VERBS and vp.FAILURES == vp.engine.FAILURES
    assert vp.main(["plan", "--doc", str(doc)], runner=runner)["count"] == 2
    assert (pages / "propose-verification-s-1.proposers.json").is_file()
    answer = vp.main(["start", "--doc", str(doc), "--brief", str(brief), "--base", BASE], runner=runner)
    assert [Path(entry["worktree"]).name for entry in answer["proposers"]] == [
        "verifier-propose-verification-s-1-claude", "verifier-propose-verification-s-1-codex"]
    with pytest.raises(Refusal) as caught:
        vp.main(["start", "--doc", str(doc), "--brief", str(brief), "--base", BASE], runner=runner)
    assert caught.value.code == "same-tool" and "verification proposers" in caught.value.reason
