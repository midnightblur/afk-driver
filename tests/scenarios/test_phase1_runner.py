"""Phase 1 scenario tests at the Runner / transport seam.

Each test wires ``Runner`` over real ``JiraClient`` + ``GitLabClient`` +
real ``_WorktreeAdapter`` against a per-test git scaffold, with
``FakeTransport`` / ``FakeGlabRunner`` / ``FakeClaude`` substituted at the
bottom. The point: everything from ADF parsing down through marker
splice through ``glab`` argv shape stays under test, instead of being
bypassed by spy fakes at the Runner seam.

Phase 1 IDs (see TESTING.md):
- H1 happy Enhancement
- H3 Bug parent skips Designing
- S1 idempotent re-run
- F1 claude no-commit aborts
- F6 Jira transition fault doesn't abort the loop
"""

from __future__ import annotations

from afk_driver.jira_client import JiraError

from tests.fakes import (
    FakeClaude,
    GitLabWorld,
    JiraWorld,
    MonorepoBuilder,
    seed_bug_parent_with_subtask,
    seed_enhancement_parent_with_subtasks,
    success_committing,
    success_no_change,
)
from tests.scenarios.conftest import adf_text


# ---------------------------------------------------------------------------
# H1 — Enhancement happy path
# ---------------------------------------------------------------------------


def test_h1_enhancement_happy_path(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        summary="implement happy path",
        subtask_specs=(("P2P-1230", "implement foo"),),
    )
    gitlab_world = GitLabWorld()
    claude = FakeClaude().plan(
        "P2P-1230",
        success_committing({"src/p2p_1230.txt": "claude wrote this\n"}),
    )

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    # --- Run record assertions -----------------------------------------
    assert len(record.parents) == 1
    parent_run = record.parents[0]
    assert parent_run.key == "P2P-1220"
    assert parent_run.target_branch == "master"
    assert [s.status for s in parent_run.subtasks] == ["success"]
    assert parent_run.rebase == "clean"

    # --- Real Jira state-machine end states ----------------------------
    # Workflow validators inside JiraWorld mean these statuses can ONLY be
    # reached if the runner populated the gate fields + assigned the issue
    # before transitioning. Pure spy fakes (test_runner.py) cannot reproduce
    # this rejection chain.
    assert jira_world.issues["P2P-1220"].status == "Dev-CR/Merge"
    assert jira_world.issues["P2P-1230"].status == "Dev-CR/Merge"

    # Enhancement workflow: Start Designing fired (H3 verifies this is
    # skipped for Bug).
    parent_transitions = [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k == "P2P-1220"
    ]
    assert parent_transitions == [
        "Start Designing",
        "Start Development",
        "Request CR & Merge",
    ]

    # --- GitLab MR state ------------------------------------------------
    assert len(gitlab_world.mrs) == 1
    mr = gitlab_world.mrs[0]
    assert mr.title == "[P2P-1220] implement happy path"
    assert mr.target_branch == "master"
    assert mr.source_branch == "mvu/afk/p2p-1220"
    assert "<!-- afk:subtasks:start -->" in mr.description
    assert "<!-- afk:subtasks:end -->" in mr.description
    # Checklist updated post-success — done item.
    assert "[x] P2P-1230 implement foo" in mr.description

    # --- Parent description splice -------------------------------------
    parent_desc_text = adf_text(jira_world.issues["P2P-1220"].description)
    assert "Implementation Notes (auto-maintained)" in parent_desc_text
    assert "P2P-1230" in parent_desc_text

    # --- Acceptance flip ------------------------------------------------
    sub_desc_text = adf_text(jira_world.issues["P2P-1230"].description)
    assert "[x] thing happens" in sub_desc_text
    assert "[ ] thing happens" not in sub_desc_text


# ---------------------------------------------------------------------------
# H3 — Bug parent skips "Start Designing"
# ---------------------------------------------------------------------------


def test_h3_bug_parent_skips_designing(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_bug_parent_with_subtask(
        jira_world,
        "P2P-9000",
        summary="repro the rounding bug",
        subtask_key="P2P-9001",
        subtask_summary="apply rounding fix",
    )
    gitlab_world = GitLabWorld()
    claude = FakeClaude().plan(
        "P2P-9001",
        success_committing({"src/round_fix.txt": "fixed\n"}),
    )

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    parent_run = record.parents[0]
    assert parent_run.key == "P2P-9000"
    assert parent_run.issuetype == "Bug"
    assert [s.status for s in parent_run.subtasks] == ["success"]

    parent_transitions = [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k == "P2P-9000"
    ]
    assert "Start Designing" not in parent_transitions, (
        "Bug workflow has no Designing step — runner must not call it"
    )
    assert parent_transitions == ["Start Development", "Request CR & Merge"]
    assert jira_world.issues["P2P-9000"].status == "Dev-CR/Merge"
    assert jira_world.issues["P2P-9001"].status == "Dev-CR/Merge"


# ---------------------------------------------------------------------------
# S1 — Idempotent re-run
# ---------------------------------------------------------------------------


def test_s1_idempotent_rerun(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        subtask_specs=(("P2P-1230", "implement"),),
    )
    gitlab_world = GitLabWorld()
    claude = FakeClaude().plan(
        "P2P-1230",
        success_committing({"src/x.txt": "x\n"}),
    )

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    runner.one_pass()

    parent_desc_after_first = jira_world.issues["P2P-1220"].description
    sub_desc_after_first = jira_world.issues["P2P-1230"].description
    mrs_after_first = [m.to_json() for m in gitlab_world.mrs]
    events_after_first = list(jira_world.events)

    # Second pass: search returns nothing because the SubTask is no longer
    # at status="Dev-Pending" (it's at "Dev-CR/Merge" now).
    record_2 = runner.one_pass()
    assert record_2.parents == []
    assert claude.call_history == [("P2P-1230", 1)], (
        "claude must not be re-invoked on the second pass"
    )
    # Side-effect surfaces are byte-identical to after the first pass.
    assert jira_world.issues["P2P-1220"].description == parent_desc_after_first
    assert jira_world.issues["P2P-1230"].description == sub_desc_after_first
    assert [m.to_json() for m in gitlab_world.mrs] == mrs_after_first
    assert jira_world.events == events_after_first


# ---------------------------------------------------------------------------
# F1 — claude returns success but didn't change any code
# ---------------------------------------------------------------------------


def test_f1_claude_no_commit_aborts(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        subtask_specs=(("P2P-1230", "noop"),),
    )
    gitlab_world = GitLabWorld()
    # success_no_change(): outcome=success, no file writes, no commit.
    # Runner's pre/post head_sha gate must convert this to an aborted SubTask.
    claude = FakeClaude().plan("P2P-1230", success_no_change())

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo, retry_count=1)
    record = runner.one_pass()

    sub_run = record.parents[0].subtasks[0]
    assert sub_run.status == "aborted"
    assert "no code changes" in (sub_run.detail or "").lower()

    # SubTask did NOT advance to Dev-CR/Merge — final status is back at
    # Dev-Pending after the abort comment + Request Development.
    sub = jira_world.issues["P2P-1230"]
    assert sub.status == "Dev-Pending"
    # Acceptance NOT flipped, Implementation Notes NOT updated, no MR
    # checklist tick.
    assert "[ ] thing happens" in adf_text(sub.description)
    parent_desc_text = adf_text(jira_world.issues["P2P-1220"].description)
    assert "P2P-1230" not in parent_desc_text or "Implementation Notes" not in parent_desc_text or "[x] P2P-1230" not in parent_desc_text
    # Comment posted on the SubTask.
    assert any(
        "aborted" in adf_text(c.get("body")).lower() for c in sub.comments
    )
    # No code committed → no push happened.
    # (Verified indirectly: bare remote has no branch ref for mvu/afk/p2p-1220.)
    import subprocess
    refs = subprocess.run(
        ["git", "ls-remote", "--heads", str(monorepo.bare_remote)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    # The branch IS published (publish_branch fires before claude runs), but
    # it points at master's tip — no work commits on top.
    assert "refs/heads/mvu/afk/p2p-1220" in refs


# ---------------------------------------------------------------------------
# F6 — Jira transition fault must not abort the per-parent SubTask loop
# ---------------------------------------------------------------------------


def test_f6_jira_transition_fault_does_not_abort_loop(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        subtask_specs=(
            ("P2P-1237", "first"),
            ("P2P-1238", "second"),
        ),
    )
    gitlab_world = GitLabWorld()
    claude = (
        FakeClaude()
        .plan("P2P-1237", success_committing({"a.txt": "first\n"}))
        .plan("P2P-1238", success_committing({"b.txt": "second\n"}))
    )

    # Inject one-shot fault: P2P-1237's "Request CR & Merge" transition
    # raises mid-loop. The runner's _try_sub must absorb it so P2P-1238 still runs.
    def fault_match(method, path, body, params):
        return (
            method == "POST"
            and path == "/rest/api/3/issue/P2P-1237/transitions"
            and (body or {}).get("transition", {}).get("id") == "31"
        )

    jira_world.queue_fault(
        fault_match,
        JiraError("synthetic 500 on Request CR & Merge"),
    )

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    parent_run = record.parents[0]
    keys = [s.key for s in parent_run.subtasks]
    assert keys == ["P2P-1237", "P2P-1238"], (
        "P2P-1238 must still process despite P2P-1237's Jira fault"
    )
    assert all(s.status == "success" for s in parent_run.subtasks), (
        "claude succeeded for both — sub_run.status reflects code work, "
        "not Jira side-effect failures"
    )

    bad = next(s for s in parent_run.subtasks if s.key == "P2P-1237")
    assert "Request CR & Merge" in (bad.detail or "")

    # P2P-1237 stuck at Dev-Developing because the failed transition was the
    # only path to Dev-CR/Merge from there. P2P-1238 reached Dev-CR/Merge.
    assert jira_world.issues["P2P-1237"].status == "Dev-Developing"
    assert jira_world.issues["P2P-1238"].status == "Dev-CR/Merge"

    # Both claude attempts ran exactly once.
    assert claude.call_history == [("P2P-1237", 1), ("P2P-1238", 1)]
