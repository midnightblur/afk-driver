"""Tests for the `backend_select` composition-root factory (ST06).

Coverage matches the SubTask acceptance list:

* github.com remote → GitHub backend;
* configured GitLab host → Jira backend;
* unknown host → `BackendResolutionError`;
* `force_backend` override wins over auto-detection;
* `mode = "all-repos"` short-circuits cwd inspection;
* missing `origin` remote → raise with clear message;
* invalid `force_backend` name raises typed error;
* SSH-form `git@github.com:owner/repo.git` parses correctly.

All tests inject a stub `origin_reader` so no on-disk git repo is needed.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from afk_driver.backend_select import (
    Backend,
    BackendResolutionError,
    RepoCoords,
    resolve,
)
from afk_driver.config import BackendSelectConfig, GithubConfig, defaults
from afk_driver.github_issues_client import GitHubIssuesClient
from afk_driver.github_pr_client import GitHubPrClient
from afk_driver.gitlab_client import GitLabClient


def _make_origin_reader(url: str):
    def reader(_cwd: Path) -> str:
        return url

    return reader


def _raising_reader(message: str):
    def reader(_cwd: Path) -> str:
        raise BackendResolutionError(message)

    return reader


# ---------------------------------------------------------------------------
# Happy paths — auto-detect from origin URL
# ---------------------------------------------------------------------------


def test_github_com_https_origin_resolves_to_github_backend(tmp_path: Path):
    cfg = defaults()
    backend = resolve(
        tmp_path,
        cfg,
        origin_reader=_make_origin_reader("https://github.com/me/myrepo.git"),
    )
    assert isinstance(backend, Backend)
    assert isinstance(backend.tracker, GitHubIssuesClient)
    assert isinstance(backend.scm, GitHubPrClient)
    assert backend.repo_coords == RepoCoords(
        backend="github", host="github.com", owner="me", repo="myrepo"
    )


def test_github_com_ssh_scp_form_origin_resolves(tmp_path: Path):
    cfg = defaults()
    backend = resolve(
        tmp_path,
        cfg,
        origin_reader=_make_origin_reader("git@github.com:owner/repo.git"),
    )
    assert backend.repo_coords.owner == "owner"
    assert backend.repo_coords.repo == "repo"
    assert backend.repo_coords.backend == "github"


def test_configured_gitlab_host_origin_resolves_to_jira_backend(tmp_path: Path):
    cfg = defaults()
    # Default gitlab_host = "gitlab" which is a substring of the URL.
    backend = resolve(
        tmp_path,
        cfg,
        origin_reader=_make_origin_reader(
            "https://gitlab.nakisa.com/finsuite/core-services.git"
        ),
    )
    assert backend.tracker is None  # Materialised at runner layer per SDD §5.
    assert isinstance(backend.scm, GitLabClient)
    assert backend.repo_coords.backend == "jira"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_unknown_host_raises_backend_resolution_error(tmp_path: Path):
    cfg = defaults()
    with pytest.raises(BackendResolutionError) as exc:
        resolve(
            tmp_path,
            cfg,
            origin_reader=_make_origin_reader("https://bitbucket.org/me/repo.git"),
        )
    assert "bitbucket" in str(exc.value).lower()


def test_missing_origin_remote_raises(tmp_path: Path):
    cfg = defaults()
    with pytest.raises(BackendResolutionError) as exc:
        resolve(
            tmp_path,
            cfg,
            origin_reader=_raising_reader("no origin remote in /some/cwd"),
        )
    assert "no origin" in str(exc.value)


def test_invalid_force_backend_name_raises(tmp_path: Path):
    cfg = defaults()
    cfg = replace(
        cfg, backend_select=BackendSelectConfig(force_backend="bitbucket")
    )
    with pytest.raises(BackendResolutionError) as exc:
        resolve(tmp_path, cfg, origin_reader=_make_origin_reader(""))
    assert "force_backend" in str(exc.value)
    assert "bitbucket" in str(exc.value)


# ---------------------------------------------------------------------------
# Override paths
# ---------------------------------------------------------------------------


def test_force_backend_github_overrides_unknown_origin(tmp_path: Path):
    """`force_backend = "github"` wins even when the cwd origin is unknown."""
    cfg = defaults()
    cfg = replace(
        cfg, backend_select=BackendSelectConfig(force_backend="github")
    )
    backend = resolve(
        tmp_path,
        cfg,
        origin_reader=_make_origin_reader("https://bitbucket.org/me/repo.git"),
    )
    assert isinstance(backend.tracker, GitHubIssuesClient)
    assert backend.repo_coords.backend == "github"


def test_force_backend_github_tolerates_missing_origin(tmp_path: Path):
    """Explicit override → run even outside a git worktree."""
    cfg = defaults()
    cfg = replace(
        cfg, backend_select=BackendSelectConfig(force_backend="github")
    )
    backend = resolve(
        tmp_path,
        cfg,
        origin_reader=_raising_reader("not a git repo"),
    )
    assert isinstance(backend.tracker, GitHubIssuesClient)
    # owner/repo empty because origin probe failed; that's the documented
    # fall-back shape, not an error.
    assert backend.repo_coords.owner == ""
    assert backend.repo_coords.repo == ""


def test_force_backend_jira_overrides_github_origin(tmp_path: Path):
    cfg = defaults()
    cfg = replace(
        cfg, backend_select=BackendSelectConfig(force_backend="jira")
    )
    backend = resolve(
        tmp_path,
        cfg,
        origin_reader=_make_origin_reader("https://github.com/me/repo.git"),
    )
    assert backend.tracker is None
    assert isinstance(backend.scm, GitLabClient)
    assert backend.repo_coords.backend == "jira"


def test_mode_all_repos_short_circuits_origin_inspection(tmp_path: Path):
    cfg = defaults()
    cfg = replace(cfg, github=GithubConfig(mode="all-repos"))

    calls: list[Path] = []

    def reader(cwd: Path) -> str:
        calls.append(cwd)
        return "https://bitbucket.org/owner/repo.git"  # would otherwise raise

    backend = resolve(tmp_path, cfg, origin_reader=reader)
    assert calls == []  # cwd inspection short-circuited
    assert isinstance(backend.tracker, GitHubIssuesClient)
    assert isinstance(backend.scm, GitHubPrClient)
    assert backend.repo_coords.backend == "github"
    # No owner/repo in all-repos mode — the runner derives them per parent.
    assert backend.repo_coords.owner == ""


def test_custom_gitlab_host_substring_matches(tmp_path: Path):
    cfg = defaults()
    cfg = replace(
        cfg, backend_select=BackendSelectConfig(gitlab_host="git.example.org")
    )
    backend = resolve(
        tmp_path,
        cfg,
        origin_reader=_make_origin_reader("ssh://git@git.example.org/team/proj.git"),
    )
    assert backend.repo_coords.backend == "jira"
    assert backend.repo_coords.host == "git.example.org"
