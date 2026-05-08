"""Scenario harness fakes — keep real JiraClient + GitLabClient + worktree_manager
in the loop and substitute the seams below them.

See TESTING.md for design + regression-simulator caveat.
"""

from tests.fakes.fake_claude import (
    FakeClaude,
    Step,
    other_step,
    success_committing,
    success_no_change,
    success_no_commit,
    test_fail_step,
    timeout_step,
)
from tests.fakes.gitlab_world import FakeGlabRunner, GitLabWorld
from tests.fakes.jira_world import (
    FakeTransport,
    JiraIssue,
    JiraWorld,
    seed_bug_parent_with_subtask,
    seed_enhancement_parent_with_subtasks,
    seed_standalone,
)
from tests.fakes.monorepo import MonorepoBuilder, MonorepoFixture

__all__ = [
    "FakeClaude",
    "FakeGlabRunner",
    "FakeTransport",
    "GitLabWorld",
    "JiraIssue",
    "JiraWorld",
    "MonorepoBuilder",
    "MonorepoFixture",
    "Step",
    "other_step",
    "seed_bug_parent_with_subtask",
    "seed_enhancement_parent_with_subtasks",
    "seed_standalone",
    "success_committing",
    "success_no_change",
    "success_no_commit",
    "test_fail_step",
    "timeout_step",
]
