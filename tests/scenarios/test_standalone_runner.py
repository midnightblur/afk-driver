"""Standalone-ticket scenario tests at the Runner / transport seam.

A "standalone" is a labelled top-level ticket (Enhancement / Bug) carrying
the ``afk-agents`` label directly with no labelled SubTasks under it. The
driver collapses the parent loop and the per-subtask loop onto the single
ticket: one Draft MR, one claude spawn, one lifecycle through
Designing/Developing/Request CR & Merge.

Scenarios:
- ST1  standalone Enhancement happy path
- ST2  standalone Bug skips Start Designing
- ST3  mixed-label parent (label on parent AND on its subtask) → skip
       standalone, run subtasks (label on parent treated as residue)
- STF1 claude success but no commit → standalone aborts on the work key
       (transitions back to Dev-Pending on the SAME ticket — distinct
       from the SubTask-flow F1 which transitions a SubTask, not parent)
- STF4 claude returns test_fail then success → retry loop fires, ticket
       reaches Dev-CR/Merge, lifecycle transitions fire ONCE (not per
       attempt)
- STF5 missing fix_versions / Target Branch → short-circuit before MR
       lookup; no claude, no transitions, no worktree
"""

from __future__ import annotations

import pytest

from tests.fakes import (
    FakeClaude,
    GitLabWorld,
    JiraWorld,
    MonorepoBuilder,
    seed_enhancement_parent_with_subtasks,
    seed_standalone,
    success_committing,
    success_no_change,
)
from tests.fakes import test_fail_step as fail_step  # avoid pytest collection
from tests.fakes.fake_claude import contract_mismatch_step
from tests.fakes.jira_world import CF_TARGET_BRANCH, JiraIssue
from tests.scenarios.conftest import adf_text


# ---------------------------------------------------------------------------
# ST1 — standalone Enhancement happy path
# ---------------------------------------------------------------------------


def test_st1_standalone_enhancement_happy_path(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_standalone(
        jira_world,
        "P2P-1500",
        summary="small enhancement, no subtasks",
        issuetype="Enhancement",
    )
    gitlab_world = GitLabWorld()
    claude = FakeClaude().plan(
        "P2P-1500",
        success_committing({"src/p2p_1500.txt": "wired\n"}),
    )

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    # One ParentRun emitted, with a single self-keyed SubTaskRun.
    assert len(record.parents) == 1
    parent_run = record.parents[0]
    assert parent_run.key == "P2P-1500"
    assert parent_run.issuetype == "Enhancement"
    assert parent_run.target_branch == "master"
    assert parent_run.rebase == "clean"
    assert [s.key for s in parent_run.subtasks] == ["P2P-1500"]
    assert [s.status for s in parent_run.subtasks] == ["success"]

    # Ticket reaches end state via real workflow validators in JiraWorld.
    assert jira_world.issues["P2P-1500"].status == "Dev-CR/Merge"

    # Enhancement workflow: Designing fires.
    transitions = [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k == "P2P-1500"
    ]
    assert transitions == [
        "Start Designing",
        "Start Development",
        "Request CR & Merge",
    ]

    # Single Draft MR opened, no checklist (standalone has no list of items).
    assert len(gitlab_world.mrs) == 1
    mr = gitlab_world.mrs[0]
    assert mr.title == "[P2P-1500] small enhancement, no subtasks"
    assert mr.target_branch == "master"
    assert mr.source_branch == "mvu/afk/p2p-1500"
    assert "<!-- afk:subtasks:start -->" in mr.description
    assert "<!-- afk:subtasks:end -->" in mr.description
    # No checklist tick because there's no checklist (single-item lists are
    # noise) — the marker block stays empty.
    assert "[x] P2P-1500" not in mr.description

    # Acceptance flipped on the standalone itself (this is where /afk-go
    # would have done its work in real life).
    desc_text = adf_text(jira_world.issues["P2P-1500"].description)
    assert "[x] thing happens" in desc_text
    assert "[ ] thing happens" not in desc_text

    # Claude spawned exactly once on the standalone key.
    assert claude.call_history == [("P2P-1500", 1)]


# ---------------------------------------------------------------------------
# ST2 — standalone Bug skips "Start Designing"
# ---------------------------------------------------------------------------


def test_st2_standalone_bug_skips_designing(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_standalone(
        jira_world,
        "P2P-9500",
        summary="small bug, no subtasks",
        issuetype="Bug",
    )
    gitlab_world = GitLabWorld()
    claude = FakeClaude().plan(
        "P2P-9500",
        success_committing({"src/p2p_9500_fix.txt": "fixed\n"}),
    )

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    parent_run = record.parents[0]
    assert parent_run.key == "P2P-9500"
    assert parent_run.issuetype == "Bug"
    assert [s.status for s in parent_run.subtasks] == ["success"]

    transitions = [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k == "P2P-9500"
    ]
    assert "Start Designing" not in transitions, (
        "Bug workflow has no Designing step — runner must not call it"
    )
    assert transitions == ["Start Development", "Request CR & Merge"]
    assert jira_world.issues["P2P-9500"].status == "Dev-CR/Merge"


# ---------------------------------------------------------------------------
# ST3 — mixed-label parent prefers SubTask flow
# ---------------------------------------------------------------------------


def test_st3_mixed_label_parent_skips_standalone(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    # seed_enhancement_parent_with_subtasks labels the SubTask. Add the
    # label to the parent too, so it shows up in the JQL search alongside
    # its own SubTask. The runner must recognise the parent is "covered"
    # by a labelled SubTask and NOT drive it as standalone.
    parent, _subs = seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        summary="parent with one labelled subtask",
        subtask_specs=(("P2P-1230", "do the work"),),
    )
    parent.labels.append("afk-agents")

    gitlab_world = GitLabWorld()
    claude = FakeClaude().plan(
        "P2P-1230",
        success_committing({"src/p2p_1230.txt": "done\n"}),
    )

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    # Exactly one ParentRun (the SubTask flow), not two — i.e. the parent
    # was NOT also driven as standalone.
    assert len(record.parents) == 1
    parent_run = record.parents[0]
    assert [s.key for s in parent_run.subtasks] == ["P2P-1230"]

    # Single MR opened. If standalone had also fired, find_open_mr_by_parent_key
    # would have surfaced a duplicate or we'd have two MRs in the world.
    assert len(gitlab_world.mrs) == 1

    # Claude spawned once for the SubTask, never with the parent key.
    assert ("P2P-1220", 1) not in claude.call_history
    assert claude.call_history == [("P2P-1230", 1)]

    # Both reach end state via the SubTask flow (parent transitions in
    # _process_parent, SubTask in _process_subtask).
    assert jira_world.issues["P2P-1220"].status == "Dev-CR/Merge"
    assert jira_world.issues["P2P-1230"].status == "Dev-CR/Merge"


# ---------------------------------------------------------------------------
# STF1 — claude success but no commit -> standalone aborts on the work key
# ---------------------------------------------------------------------------


def test_stf1_standalone_no_commit_aborts(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_standalone(
        jira_world,
        "P2P-1501",
        summary="standalone with no-op claude",
        issuetype="Enhancement",
    )
    gitlab_world = GitLabWorld()
    # success_no_change(): outcome=success, no file writes, no commit.
    # The same pre/post head_sha gate that protects SubTasks (F1) must
    # protect standalone too — but the abort transitions on the SAME ticket
    # that ran Designing/Developing, which is the path F1 cannot exercise.
    claude = FakeClaude().plan("P2P-1501", success_no_change())

    runner = runner_factory(
        jira_world, gitlab_world, claude, monorepo, retry_count=1,
    )
    record = runner.one_pass()

    parent_run = record.parents[0]
    assert [s.status for s in parent_run.subtasks] == ["aborted"]
    sub_run = parent_run.subtasks[0]
    assert "no code changes" in (sub_run.detail or "").lower()

    # Critical: ticket walks Designing/Developing, then back to Dev-Pending
    # via Request Development. End state is Dev-Pending, NOT Dev-CR/Merge.
    issue = jira_world.issues["P2P-1501"]
    assert issue.status == "Dev-Pending"

    transitions = [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k == "P2P-1501"
    ]
    assert "Request Development" in transitions, (
        "standalone abort must transition the work key BACK to Dev-Pending"
    )
    assert "Request CR & Merge" not in transitions, (
        "must not have advanced to Dev-CR/Merge after a no-commit run"
    )

    # Acceptance NOT flipped (work didn't land).
    desc_text = adf_text(issue.description)
    assert "[ ] thing happens" in desc_text

    # Abort comment posted on the same key.
    assert any(
        "aborted" in adf_text(c.get("body")).lower() for c in issue.comments
    )


# ---------------------------------------------------------------------------
# STF4 — test_fail then success on retry, lifecycle fires once
# ---------------------------------------------------------------------------


def test_stf4_standalone_retry_after_test_fail(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_standalone(
        jira_world,
        "P2P-1502",
        summary="standalone with flaky tests",
        issuetype="Enhancement",
    )
    gitlab_world = GitLabWorld()
    claude = FakeClaude().plan(
        "P2P-1502",
        fail_step("3 unit tests failed"),
        success_committing({"src/p2p_1502.txt": "fixed second time\n"}),
    )

    runner = runner_factory(
        jira_world, gitlab_world, claude, monorepo, retry_count=2,
    )
    record = runner.one_pass()

    sub_run = record.parents[0].subtasks[0]
    assert sub_run.status == "success"
    assert sub_run.attempts == 2
    assert claude.call_history == [("P2P-1502", 1), ("P2P-1502", 2)], (
        "claude must be re-invoked exactly once after test_fail"
    )

    # End state reached.
    assert jira_world.issues["P2P-1502"].status == "Dev-CR/Merge"

    # Lifecycle transitions fire ONCE — retry must not re-fire Designing /
    # Development between attempts.
    transitions = [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k == "P2P-1502"
    ]
    assert transitions == [
        "Start Designing", "Start Development", "Request CR & Merge",
    ], f"unexpected per-attempt re-firing: {transitions}"

    # No abort comment — retry succeeded.
    comments = jira_world.issues["P2P-1502"].comments
    assert not any(
        "aborted" in adf_text(c.get("body")).lower() for c in comments
    ), f"unexpected abort comment after successful retry: {comments!r}"


# ---------------------------------------------------------------------------
# STF5 — missing required field short-circuits standalone before MR lookup
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario,mutation,expected_reason_substr",
    [
        (
            "no fixVersions",
            lambda issue: issue.fix_versions.clear(),
            "fixVersions",
        ),
        (
            "no Target Branch CF",
            lambda issue: issue.custom_fields.pop(CF_TARGET_BRANCH, None),
            "Target Branch",
        ),
    ],
)
def test_stf5_standalone_skip_when_required_field_missing(
    tmp_path, runner_factory, scenario, mutation, expected_reason_substr,
):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_standalone(
        jira_world,
        "P2P-1503",
        summary=f"standalone missing-field: {scenario}",
        issuetype="Enhancement",
    )
    mutation(jira_world.issues["P2P-1503"])
    gitlab_world = GitLabWorld()
    claude = FakeClaude()  # must not be invoked

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    parent_run = record.parents[0]
    assert expected_reason_substr in parent_run.skip_reason, (
        f"expected skip_reason to mention {expected_reason_substr!r}, "
        f"got {parent_run.skip_reason!r}"
    )
    # Self-keyed SubTaskRun was emitted but marked skipped (the digest
    # depends on subtasks always being non-empty for standalone runs).
    assert [s.status for s in parent_run.subtasks] == ["skipped"]

    # Short-circuit: no MR lookup, no worktree, no claude, no transitions.
    assert claude.call_history == []
    assert gitlab_world.mrs == []
    assert jira_world.issues["P2P-1503"].status == "Dev-Pending"
    assert not [
        n for kind, k, n in jira_world.events if kind == "transition"
    ]
    assert not (tmp_path / "worktrees" / "P2P-1503").exists()


# ---------------------------------------------------------------------------
# STF6 — standalone contract_mismatch with locked producer (S3 closure)
# ---------------------------------------------------------------------------


def test_stf6_standalone_contract_mismatch_locked_producer_routes_to_corrective(
    tmp_path, runner_factory,
):
    """When a standalone consumer hits ``contract_mismatch`` and names a
    producer ticket whose Jira status is past Dev-Developing (already merged
    in a prior drain pass, or living in a different drain pool entirely), the
    runner's abort comment must NOT tell the human to re-open the producer —
    re-opening would mean reverting a merge. Both the consumer-side abort
    comment and the producer-side mismatch comment must use the locked
    framing: emit a corrective SubTask, do not retry as-is.

    Standalones are the most exposed case here because they often reference
    producers that aren't even in the current drain pool, so the producer
    has had every opportunity to land on master while the consumer was
    waiting on humans to triage the parent label.
    """
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    # Producer issue exists in Jira but is past the lock point. It is NOT
    # AFK-labelled, so the drain pass won't run it — it just exists for
    # status-fetch purposes. (In production this is the typical shape: a
    # SubTask from last week that's now merged.)
    jira_world.add_issue(
        JiraIssue(
            key="P2P-1599",
            summary="LockedProducerSDK already merged",
            status="Dev-CR/Merge",
            issuetype="SubTask",
        )
    )
    seed_standalone(
        jira_world,
        "P2P-1600",
        summary="standalone consumer hits drift on a merged producer",
        issuetype="Enhancement",
    )
    gitlab_world = GitLabWorld()
    claude = FakeClaude().plan(
        "P2P-1600",
        contract_mismatch_step("P2P-1599"),
    )

    runner = runner_factory(
        jira_world, gitlab_world, claude, monorepo, retry_count=2,
    )
    runner.one_pass()

    # Consumer-side abort comment posted on the standalone work key.
    consumer = next(
        adf_text(c["body"])
        for c in jira_world.issues["P2P-1600"].comments
        if "contract mismatch" in adf_text(c["body"]).lower()
    )
    assert "past the lock point" in consumer.lower(), consumer
    assert "corrective subtask" in consumer.lower(), consumer
    assert "Dev-CR/Merge" in consumer

    # Producer-side mismatch comment posted on P2P-1599.
    producer = next(
        adf_text(c["body"])
        for c in jira_world.issues["P2P-1599"].comments
        if "contract break" in adf_text(c["body"]).lower()
    )
    assert "do not re-open" in producer.lower() or "do **not** re-open" in producer.lower(), producer
    assert "corrective subtask" in producer.lower(), producer

    # No retry: contract_mismatch is single-attempt.
    assert claude.call_history == [("P2P-1600", 1)]
