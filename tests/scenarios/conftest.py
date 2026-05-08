"""Shared scenario harness helpers.

Builds a Runner with real ``JiraClient`` + ``GitLabClient`` + real
``_WorktreeAdapter`` over a per-test git scaffold, with the seams below
those layers swapped to in-memory fakes (FakeTransport, FakeGlabRunner,
FakeClaude).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from afk_driver.cli import _WorktreeAdapter
from afk_driver.config import defaults
from afk_driver.gitlab_client import GitLabClient
from afk_driver.jira_client import JiraClient, JiraConfig
from afk_driver.runner import Runner

from tests.fakes import FakeClaude, FakeTransport, GitLabWorld, JiraWorld
from tests.fakes.monorepo import MonorepoFixture


def make_runner(
    *,
    jira_world: JiraWorld,
    gitlab_world: GitLabWorld,
    claude: FakeClaude,
    monorepo: MonorepoFixture,
    tmp_path: Path,
    retry_count: int = 2,
) -> Runner:
    jira = JiraClient(
        JiraConfig(base_url="https://jira.example", email="test@example", api_token="fake-token"),
        FakeTransport(jira_world),
    )
    gitlab = GitLabClient(runner=gitlab_world)
    cfg = replace(
        defaults(),
        worktree_root=tmp_path / "worktrees",
        log_root=tmp_path / "logs",
        digest_root=tmp_path / "digests",
        retry_count=retry_count,
    )
    return Runner(
        jira=jira,
        gitlab=gitlab,
        worktrees=_WorktreeAdapter(),
        claude_runner=claude,
        config=cfg,
        repo_root=monorepo.repo_root,
        progress=lambda msg: None,
    )


def adf_text(adf: dict | None) -> str:
    """Flatten ADF text nodes for substring assertions on description state."""
    if not adf:
        return ""
    parts: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            text = node.get("text")
            if isinstance(text, str):
                parts.append(text)
            content = node.get("content")
            if isinstance(content, list):
                for child in content:
                    walk(child)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(adf)
    return " | ".join(parts)


@pytest.fixture
def runner_factory(tmp_path):
    """Convenience fixture: ``runner_factory(jira_world, gitlab_world, claude, monorepo)``."""

    def _factory(
        jira_world: JiraWorld,
        gitlab_world: GitLabWorld,
        claude: FakeClaude,
        monorepo: MonorepoFixture,
        *,
        retry_count: int = 2,
    ) -> Runner:
        return make_runner(
            jira_world=jira_world,
            gitlab_world=gitlab_world,
            claude=claude,
            monorepo=monorepo,
            tmp_path=tmp_path,
            retry_count=retry_count,
        )

    return _factory
