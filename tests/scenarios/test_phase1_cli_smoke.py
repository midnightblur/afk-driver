"""CLI-level smoke tests via ``cli.main`` factory injection.

Two cases — they cover the exit branches of ``cli.main`` end-to-end without
re-testing what the unit tests already cover:

- C-A: happy-path drain. Same shape as the manual SMOKE.md run, fully local.
- C-B: preflight fails on missing ``GITLAB_TOKEN`` → exit 2.
"""

from __future__ import annotations

from pathlib import Path

from afk_driver import cli

from tests.fakes import (
    FakeClaude,
    FakeTransport,
    GitLabWorld,
    JiraWorld,
    MonorepoBuilder,
    seed_enhancement_parent_with_subtasks,
    success_committing,
)


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
    )

    assert rc == 2
    err = capsys.readouterr().err
    assert "preflight" in err.lower()
    assert "GITLAB_TOKEN" in err
