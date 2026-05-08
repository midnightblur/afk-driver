"""Phase 3 scenario tests at the Runner / transport seam.

Phase 3a (in tree, this file):
- F4 test_fail then success on retry — exercises the retry loop in
  ``_process_subtask`` end-to-end, which Phase 1+2 never hit (every prior
  scenario succeeds first try).
- B1 existing MR by parent_key — the ``branch_override`` plumbing through
  ``WorktreeSpec``. Phase 2 F2 only covers the *failure* (>1 match) path.
- B2 foreign worktree reuse — ``find_worktree_for_branch`` +
  ``path_override``. Real load-bearing code, currently zero integration
  coverage.

Phase 3b (deferred, per TESTING.md): H4, C1/C2/C3, S3.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.fakes import (
    FakeClaude,
    GitLabWorld,
    JiraWorld,
    MonorepoBuilder,
    seed_enhancement_parent_with_subtasks,
    success_committing,
)
from tests.fakes import test_fail_step as fail_step  # avoid pytest collecting helper


# ---------------------------------------------------------------------------
# F4 — test_fail then success on retry
# ---------------------------------------------------------------------------


def test_f4_retry_after_test_fail(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        summary="retry scenario",
        subtask_specs=(("P2P-1230", "flaky tests"),),
    )
    gitlab_world = GitLabWorld()
    # Plan: first attempt fails the test suite, second attempt commits clean.
    # The runner's retry loop must: (a) re-spawn claude on test_fail,
    # (b) NOT mutate ticket lifecycle between attempts, (c) ultimately
    # transition to Dev-CR/Merge once an attempt commits successfully.
    claude = (
        FakeClaude()
        .plan(
            "P2P-1230",
            fail_step("3 unit tests failed"),
            success_committing({"src/p2p_1230.txt": "fixed second time\n"}),
        )
    )

    runner = runner_factory(
        jira_world, gitlab_world, claude, monorepo, retry_count=2,
    )
    record = runner.one_pass()

    sub_run = record.parents[0].subtasks[0]
    assert sub_run.status == "success"
    assert sub_run.attempts == 2
    assert claude.call_history == [("P2P-1230", 1), ("P2P-1230", 2)], (
        "claude must be re-invoked exactly once after test_fail"
    )

    # SubTask still reaches the end state.
    assert jira_world.issues["P2P-1230"].status == "Dev-CR/Merge"
    assert jira_world.issues["P2P-1220"].status == "Dev-CR/Merge"

    # Critical: Start Designing / Start Development fire ONCE, not per attempt.
    sub_transitions = [
        n for kind, k, n in jira_world.events
        if kind == "transition" and k == "P2P-1230"
    ]
    assert sub_transitions == [
        "Start Designing", "Start Development", "Request CR & Merge",
    ], f"unexpected per-attempt re-firing: {sub_transitions}"

    # No abort comment — retry succeeded.
    sub_comments = jira_world.issues["P2P-1230"].comments
    assert not any(
        "aborted" in (str(c.get("body")).lower()) for c in sub_comments
    ), f"unexpected abort comment after successful retry: {sub_comments!r}"


# ---------------------------------------------------------------------------
# B1 — existing MR by parent_key -> branch_override
# ---------------------------------------------------------------------------


def _seed_remote_branch(
    monorepo,
    tmp_path: Path,
    branch_name: str,
    *,
    file_rel: str = "src/handprepped.txt",
    file_content: str = "hand-prepped\n",
) -> None:
    """Push a branch off master to ``origin`` via a separate clone.

    Used by B1 to model "user opened an MR by hand against a non-template
    branch". The branch lives on ``origin`` only — the worktree_manager's
    ``_branch_exists_remote`` path then drives ``git fetch`` + ``git
    worktree add --track``.
    """
    seed = tmp_path / f"seed-{branch_name.replace('/', '-')}"
    subprocess.run(
        ["git", "clone", "-q", str(monorepo.bare_remote), str(seed)],
        check=True, capture_output=True,
    )
    subprocess.run(["git", "config", "user.email", "seed@test"], cwd=seed, check=True)
    subprocess.run(["git", "config", "user.name", "seed"], cwd=seed, check=True)
    subprocess.run(
        ["git", "checkout", "-q", "-b", branch_name], cwd=seed, check=True,
    )
    target = seed / file_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(file_content, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=seed, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", f"seed {branch_name}"],
        cwd=seed, check=True,
    )
    subprocess.run(
        ["git", "push", "-q", "-u", "origin", branch_name],
        cwd=seed, check=True,
    )


def test_b1_existing_mr_by_parent_key_triggers_branch_override(
    tmp_path, runner_factory,
):
    monorepo = MonorepoBuilder().build(tmp_path)

    hand_prepped = "kapteyn/development/mvu/handprepped-feature"
    _seed_remote_branch(monorepo, tmp_path, hand_prepped)

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        summary="existing-MR reuse",
        subtask_specs=(("P2P-1230", "wire feature"),),
    )
    gitlab_world = GitLabWorld()
    seeded_mr = gitlab_world.seed_existing_mr(
        source_branch=hand_prepped,
        target_branch="master",
        title="[P2P-1220] existing-MR reuse",
        description=(
            "AFK auto-managed Draft MR for P2P-1220.\n\n"
            "<!-- afk:subtasks:start -->\n<!-- afk:subtasks:end -->"
        ),
    )

    claude = FakeClaude().plan(
        "P2P-1230",
        success_committing({"src/b1.txt": "wired\n"}),
    )

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    parent_run = record.parents[0]
    assert [s.status for s in parent_run.subtasks] == ["success"]
    assert parent_run.mr_url == seeded_mr.web_url, (
        "must reuse the hand-prepped MR, not open a new one"
    )

    # No second MR opened for the auto-managed mvu/afk/p2p-1220 branch.
    assert len(gitlab_world.mrs) == 1, (
        f"expected exactly one MR (the seeded one); got {len(gitlab_world.mrs)}"
    )
    assert gitlab_world.mrs[0].source_branch == hand_prepped

    # Worktree was created at the managed path (path_override unset because
    # no foreign worktree existed) but ON the hand-prepped branch.
    managed_path = tmp_path / "worktrees" / "P2P-1220"
    assert managed_path.is_dir()
    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(managed_path), capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert current_branch == hand_prepped, (
        f"worktree must check out the hand-prepped branch, got {current_branch!r}"
    )

    # Claude's commit landed on the hand-prepped branch.
    assert (managed_path / "src/b1.txt").is_file()
    # Reused MR's checklist got the tick.
    assert "[x] P2P-1230 wire feature" in gitlab_world.mrs[0].description

    # SubTask reached Dev-CR/Merge on the reused branch.
    assert jira_world.issues["P2P-1230"].status == "Dev-CR/Merge"
    assert jira_world.issues["P2P-1220"].status == "Dev-CR/Merge"


# ---------------------------------------------------------------------------
# B2 — foreign worktree reuse via path_override
# ---------------------------------------------------------------------------


def test_b2_foreign_worktree_reused_via_path_override(tmp_path, runner_factory):
    monorepo = MonorepoBuilder().build(tmp_path)

    foreign_branch = "kapteyn/development/mvu/foreign-feature"
    foreign_path = tmp_path / "foreign-workspace"
    # Create both the branch AND the foreign worktree off master (so
    # ``find_worktree_for_branch`` parses ``git worktree list --porcelain``
    # and surfaces this path).
    subprocess.run(
        [
            "git", "worktree", "add", str(foreign_path),
            "-b", foreign_branch, "master",
        ],
        cwd=str(monorepo.repo_root),
        check=True, capture_output=True,
    )

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        summary="foreign worktree reuse",
        subtask_specs=(("P2P-1230", "carry on"),),
    )
    gitlab_world = GitLabWorld()
    gitlab_world.seed_existing_mr(
        source_branch=foreign_branch,
        target_branch="master",
        title="[P2P-1220] foreign worktree reuse",
        description=(
            "AFK auto-managed Draft MR for P2P-1220.\n\n"
            "<!-- afk:subtasks:start -->\n<!-- afk:subtasks:end -->"
        ),
    )

    claude = FakeClaude().plan(
        "P2P-1230",
        success_committing({"src/b2.txt": "in foreign worktree\n"}),
    )

    runner = runner_factory(jira_world, gitlab_world, claude, monorepo)
    record = runner.one_pass()

    parent_run = record.parents[0]
    assert [s.status for s in parent_run.subtasks] == ["success"]

    # No managed worktree at the default path — runner reused the foreign one.
    managed_path = tmp_path / "worktrees" / "P2P-1220"
    assert not managed_path.exists(), (
        f"managed worktree must NOT have been created; found {managed_path}"
    )

    # Claude's commit landed in the foreign worktree.
    assert (foreign_path / "src/b2.txt").is_file(), (
        "claude side-effect must execute against the foreign path, not the "
        "managed one"
    )
    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(foreign_path), capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert current_branch == foreign_branch

    # Single MR (the seeded one), end state reached.
    assert len(gitlab_world.mrs) == 1
    assert gitlab_world.mrs[0].source_branch == foreign_branch
    assert "[x] P2P-1230 carry on" in gitlab_world.mrs[0].description
    assert jira_world.issues["P2P-1230"].status == "Dev-CR/Merge"
    assert jira_world.issues["P2P-1220"].status == "Dev-CR/Merge"
