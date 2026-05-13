"""CLI-level smoke tests via ``cli.main`` factory injection.

Two cases — they cover the exit branches of ``cli.main`` end-to-end without
re-testing what the unit tests already cover:

- C-A: happy-path drain. Same shape as the manual SMOKE.md run, fully local.
- C-B: preflight fails on missing ``GITLAB_TOKEN`` → exit 2.
"""

from __future__ import annotations

from pathlib import Path

from afk_driver import cli
from afk_driver.backend_select import Backend, RepoCoords
from afk_driver.gitlab_client import GitLabClient

from tests.fakes import (
    FakeClaude,
    FakeTransport,
    GitLabWorld,
    JiraWorld,
    MonorepoBuilder,
    seed_enhancement_parent_with_subtasks,
    success_committing,
)


def _jira_backend_resolver(gitlab_world):
    """ST08 made ``cli.main`` resolve the backend via ``backend_select.resolve``
    BEFORE pre-flight. The MonorepoBuilder fake uses a local ``origin.git``
    bare-repo URL that matches neither ``github.com`` nor the configured
    GitLab host, so the default resolver would raise
    ``BackendResolutionError``. These smoke tests intentionally test the
    Jira branch end-to-end; we inject a resolver that returns a Jira
    backend bound to the test's ``GitLabClient`` (constructed against the
    test's fake glab runner ``gitlab_world``)."""
    def _resolve(_cwd, _cfg, **_kw):
        return Backend(
            tracker=None,  # cli materialises JiraClient from env-var creds
            scm=GitLabClient(runner=gitlab_world),
            repo_coords=RepoCoords(backend="jira", host="gitlab.example"),
        )
    return _resolve


def _redirect_home(monkeypatch, home: Path) -> None:
    """Point ``Path.home()`` at a tmp dir on both Windows and Unix.
    config.defaults() reads ``Path.home() / ".afk-driver"`` for log_root /
    digest_root / worktree_root, so without this every cli test would
    pollute the user's real ``~/.afk-driver/``.
    """
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def test_cli_main_happy_path(tmp_path, monkeypatch):
    monorepo = MonorepoBuilder().build(tmp_path)

    jira_world = JiraWorld()
    seed_enhancement_parent_with_subtasks(
        jira_world,
        "P2P-1220",
        summary="cli smoke",
        subtask_specs=(("P2P-1230", "wire-through"),),
    )
    gitlab_world = GitLabWorld()
    claude = FakeClaude().plan(
        "P2P-1230",
        success_committing({"src/cli_smoke.txt": "wired\n"}),
    )

    monkeypatch.setenv("GITLAB_TOKEN", "fake")
    monkeypatch.setattr(
        "afk_driver.runner.shutil.which",
        lambda name: f"/fake/bin/{name}",
    )
    _redirect_home(monkeypatch, tmp_path / "home")

    digest_path = tmp_path / "digest.md"
    rc = cli.main(
        argv=[
            "--repo-root", str(monorepo.repo_root),
            "--digest-out", str(digest_path),
            "--jira-base", "https://jira.example",
            "--jira-email", "test@example.com",
            "--jira-token", "fake-token",
        ],
        transport_factory=lambda *_a: FakeTransport(jira_world),
        glab_runner_factory=lambda: gitlab_world,
        claude_runner_factory=lambda log_root: claude,
        backend_resolver=_jira_backend_resolver(gitlab_world),
    )

    assert rc == 0
    assert digest_path.is_file()
    digest_content = digest_path.read_text(encoding="utf-8")
    assert "P2P-1220" in digest_content
    assert "P2P-1230" in digest_content

    # Sanity: full pipeline drained — JiraWorld reflects Dev-CR/Merge end
    # state on both parent + SubTask, MR opened with one ticked checklist
    # entry.
    assert jira_world.issues["P2P-1220"].status == "Dev-CR/Merge"
    assert jira_world.issues["P2P-1230"].status == "Dev-CR/Merge"
    assert len(gitlab_world.mrs) == 1
    assert "[x] P2P-1230 wire-through" in gitlab_world.mrs[0].description


def test_cli_main_preflight_fails_when_gitlab_token_missing(tmp_path, monkeypatch, capsys):
    monorepo = MonorepoBuilder().build(tmp_path)

    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.setattr(
        "afk_driver.runner.shutil.which",
        lambda name: f"/fake/bin/{name}",
    )
    _redirect_home(monkeypatch, tmp_path / "home")

    rc = cli.main(
        argv=[
            "--repo-root", str(monorepo.repo_root),
            "--jira-base", "https://jira.example",
            "--jira-email", "test@example.com",
            "--jira-token", "fake-token",
        ],
        backend_resolver=_jira_backend_resolver(None),
    )

    assert rc == 2
    err = capsys.readouterr().err
    assert "preflight" in err.lower()
    assert "GITLAB_TOKEN" in err
