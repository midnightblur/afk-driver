"""Phase 2 scenario tests at the Runner / transport seam.

Phase 2 IDs (see TESTING.md):
- H2 multi-SubTask drain on one parent (3 subs, all green)
- F2 ambiguous MR (>1 open MRs match parent_key) -> parent skipped
- F3 rebase conflict -> conflict comment, parent stays at Dev-Developing
- F5 missing fixVersions / Target Branch -> parent skipped (parametrized)
- S2 mid-state re-entry: parent already at Dev-Developing
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from afk_driver.gitlab_client import GitLabError

from tests.fakes import (
    FakeClaude,
    GitLabWorld,
    JiraWorld,
    MonorepoBuilder,
    seed_enhancement_parent_with_subtasks,
    success_committing,
)
from tests.fakes.jira_world import CF_TARGET_BRANCH, JiraIssue
from tests.scenarios.conftest import adf_text


# ---------------------------------------------------------------------------
# H2 — multi-SubTask drain on one parent
# ---------------------------------------------------------------------------


def test_h2_multi_subtask_drain(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        summary="multi-sub drain",
        subtask_specs=(
            ("P2P-1230", "first sub"),
            ("P2P-1231", "second sub"),
            ("P2P-1232", "third sub"),
        ),
    )
    gitlab_world = GitLabWorld()
    claude = (
        FakeClaude()
        .plan("P2P-1230", success_committing({"src/p2p_1230.txt": "1\n"}))
        .plan("P2P-1231", success_committing({"src/p2p_1231.txt": "2\n"}))
        .plan("P2P-1232", success_committing({"src/p2p_1232.txt": "3\n"}))
    )

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    parent_run = record.parents[0]
    assert [s.key for s in parent_run.subtasks] == [
        "P2P-1230", "P2P-1231", "P2P-1232",
    ], "SubTasks must process in JQL/seed order"
    assert all(s.status == "success" for s in parent_run.subtasks)
    assert parent_run.rebase == "clean"

    # All four issues end at Dev-CR/Merge.
    assert jira_world.issues["P2P-1220"].status == "Dev-CR/Merge"
    for key in ("P2P-1230", "P2P-1231", "P2P-1232"):
        assert jira_world.issues[key].status == "Dev-CR/Merge", key

    # Parent transitions fire exactly once (no per-SubTask re-firing).
    parent_transitions = [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k == "P2P-1220"
    ]
    assert parent_transitions == [
        "Start Designing", "Start Development", "Request CR & Merge",
    ]

    # MR checklist ticks every sub.
    assert len(gitlab_world.mrs) == 1
    mr_desc = gitlab_world.mrs[0].description
    assert "[x] P2P-1230 first sub" in mr_desc
    assert "[x] P2P-1231 second sub" in mr_desc
    assert "[x] P2P-1232 third sub" in mr_desc

    # Implementation Notes splice mentions every sub.
    parent_desc_text = adf_text(jira_world.issues["P2P-1220"].description)
    assert "Implementation Notes (auto-maintained)" in parent_desc_text
    for key in ("P2P-1230", "P2P-1231", "P2P-1232"):
        assert key in parent_desc_text, key

    # FakeClaude saw exactly one attempt per key, in order.
    assert claude.call_history == [
        ("P2P-1230", 1), ("P2P-1231", 1), ("P2P-1232", 1),
    ]


# ---------------------------------------------------------------------------
# F2 — ambiguous MR: 2 open MRs match parent_key -> parent skipped
# ---------------------------------------------------------------------------


def test_f2_ambiguous_mr_skips_parent(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        summary="ambiguous MR scenario",
        subtask_specs=(("P2P-1230", "noop"),),
    )
    gitlab_world = GitLabWorld()
    # Two open MRs whose titles both reference the parent key. The runner's
    # find_open_mr_by_parent_key must raise GitLabError; the runner traps
    # it as a per-parent skip rather than aborting the pass.
    gitlab_world.seed_existing_mr(
        source_branch="kapteyn/development/mvu/foo",
        target_branch="master",
        title="[P2P-1220] hand-prepped foo",
    )
    gitlab_world.seed_existing_mr(
        source_branch="kapteyn/development/mvu/bar",
        target_branch="master",
        title="[P2P-1220] hand-prepped bar",
    )
    claude = FakeClaude()  # plan intentionally empty — should not be invoked

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    parent_run = record.parents[0]
    assert "MR lookup failed" in parent_run.skip_reason
    assert "ambiguous" in parent_run.skip_reason
    assert parent_run.subtasks == [], "must not even start SubTasks"

    # Side-effect surfaces are untouched.
    assert claude.call_history == []
    assert len(gitlab_world.mrs) == 2, "no new MR opened"
    assert jira_world.issues["P2P-1220"].status == "Dev-Pending"
    assert jira_world.issues["P2P-1230"].status == "Dev-Pending"
    # No transitions fired on either issue.
    assert not [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k in ("P2P-1220", "P2P-1230")
    ]
    # No worktree was created on disk.
    assert not (tmp_path / "worktrees" / "P2P-1220").exists()


# ---------------------------------------------------------------------------
# F3 — rebase conflict: comment posted, parent stays at Dev-Developing
# ---------------------------------------------------------------------------


def _advance_origin_master(monorepo, tmp_path: Path, file_rel: str, content: str) -> None:
    """Push a divergent commit to ``origin/master`` without touching repo_root.

    The runner branches the worktree off ``master`` (local ref) at its
    current tip, then later rebases onto ``origin/master``. To force a
    conflict at rebase time we advance origin/master AFTER the local
    master ref has been captured but BEFORE the rebase fires — and the
    cleanest way is to push from a separate clone so repo_root's local
    state is unchanged.
    """
    advance = tmp_path / "advance"
    subprocess.run(
        ["git", "clone", "-q", str(monorepo.bare_remote), str(advance)],
        check=True, capture_output=True,
    )
    subprocess.run(["git", "config", "user.email", "adv@test"], cwd=advance, check=True)
    subprocess.run(["git", "config", "user.name", "adv"], cwd=advance, check=True)
    target = advance / file_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=advance, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", f"advance master ({file_rel})"],
        cwd=advance, check=True,
    )
    subprocess.run(
        ["git", "push", "-q", "origin", "master"], cwd=advance, check=True,
    )


def test_f3_rebase_conflict_comments_and_skips_request_cr(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        summary="rebase conflict scenario",
        subtask_specs=(("P2P-1230", "edit readme"),),
    )
    gitlab_world = GitLabWorld()
    # Claude rewrites README.md on the worktree branch; origin/master will
    # have a different rewrite of the same file by rebase time.
    claude = FakeClaude().plan(
        "P2P-1230",
        success_committing({"README.md": "claude version\n"}),
    )

    # Push a conflicting change to origin/master (separate clone — repo_root's
    # local master ref is unchanged, so the worktree still branches off the
    # original head).
    _advance_origin_master(monorepo, tmp_path, "README.md", "master ahead\n")

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    parent_run = record.parents[0]
    assert parent_run.rebase == "conflict"
    assert [s.status for s in parent_run.subtasks] == ["success"], (
        "claude committed cleanly; rebase outcome is parent-level, not per-SubTask"
    )

    # Parent transitions: Start Designing + Start Development fired BEFORE the
    # rebase; Request CR & Merge must NOT have fired.
    parent_transitions = [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k == "P2P-1220"
    ]
    assert parent_transitions == ["Start Designing", "Start Development"]
    assert "Request CR & Merge" not in parent_transitions
    assert jira_world.issues["P2P-1220"].status == "Dev-Developing"

    # SubTask still reached Dev-CR/Merge (its lifecycle completes before the
    # parent-level rebase).
    assert jira_world.issues["P2P-1230"].status == "Dev-CR/Merge"

    # Conflict comment posted on the parent.
    parent_comments = jira_world.issues["P2P-1220"].comments
    assert any(
        "rebase" in adf_text(c.get("body")).lower()
        and "conflict" in adf_text(c.get("body")).lower()
        for c in parent_comments
    ), f"no rebase-conflict comment on parent: {parent_comments!r}"


# ---------------------------------------------------------------------------
# F5 — missing fixVersions / Target Branch -> parent skipped (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scenario", "mutation", "expected_reason_substr"),
    [
        (
            "no fixVersions",
            lambda issue: issue.fix_versions.clear(),
            "fixVersions",
        ),
        (
            "no Target Branch",
            lambda issue: issue.custom_fields.pop(CF_TARGET_BRANCH, None),
            "Target Branch",
        ),
    ],
)
def test_f5_skip_when_required_parent_field_missing(
    tmp_path, runner_factory, scenario, mutation, expected_reason_substr,
):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        summary=f"missing-field scenario: {scenario}",
        subtask_specs=(("P2P-1230", "noop"),),
    )
    mutation(jira_world.issues["P2P-1220"])
    gitlab_world = GitLabWorld()
    claude = FakeClaude()  # must not be invoked

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    parent_run = record.parents[0]
    assert expected_reason_substr in parent_run.skip_reason, (
        f"expected skip_reason to mention {expected_reason_substr!r}, "
        f"got {parent_run.skip_reason!r}"
    )
    assert parent_run.subtasks == []
    # Short-circuit: no MR lookup, no worktree, no claude, no transitions.
    assert claude.call_history == []
    assert gitlab_world.mrs == []
    assert jira_world.issues["P2P-1220"].status == "Dev-Pending"
    assert jira_world.issues["P2P-1230"].status == "Dev-Pending"
    assert not [
        n for kind, k, n in jira_world.events
        if kind == "transition"
    ]
    assert not (tmp_path / "worktrees" / "P2P-1220").exists()


# ---------------------------------------------------------------------------
# S2 — parent already at Dev-Developing -> mid-state re-entry
# ---------------------------------------------------------------------------


def test_s2_parent_mid_state_dev_developing(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    # Realistic mid-state: parent already past Dev-Pending, with assignee set
    # (a real-world Dev-Developing parent always has one — Rule 1 of the
    # workflow validator would have rejected the prior transition otherwise).
    # The runner must NOT re-fire Start Designing / Start Development for the
    # parent, but must still drain its Dev-Pending SubTasks and ultimately
    # transition the parent to Dev-CR/Merge.
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        summary="mid-state re-entry",
        subtask_specs=(("P2P-1230", "finish the work"),),
        parent_status="Dev-Developing",
    )
    jira_world.issues["P2P-1220"].assignee = {"accountId": jira_world.account_id}

    gitlab_world = GitLabWorld()
    claude = FakeClaude().plan(
        "P2P-1230",
        success_committing({"src/s2.txt": "ok\n"}),
    )

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    parent_run = record.parents[0]
    assert [s.status for s in parent_run.subtasks] == ["success"]
    assert parent_run.rebase == "clean"

    parent_transitions = [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k == "P2P-1220"
    ]
    # Critical: NO Start Designing / Start Development on a mid-state parent.
    assert "Start Designing" not in parent_transitions
    assert "Start Development" not in parent_transitions
    assert parent_transitions == ["Request CR & Merge"]

    # SubTask still walks the full Dev-Pending lifecycle.
    sub_transitions = [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k == "P2P-1230"
    ]
    assert sub_transitions == [
        "Start Designing", "Start Development", "Request CR & Merge",
    ]

    assert jira_world.issues["P2P-1220"].status == "Dev-CR/Merge"
    assert jira_world.issues["P2P-1230"].status == "Dev-CR/Merge"
