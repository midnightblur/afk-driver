"""The git-side backstop: installed hooks refuse an agent's commit or branch move where the guard would.

Disposable repositories only; the plugin's own checkout and git config are never touched.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = PLUGIN_ROOT / "hooks" / "install-git-hooks.sh"


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")

IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")
AGENT_VARS = ("AFK_PROVIDER", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "CLAUDECODE", "AFK_ALLOW_PROTECTED",
              "AFK_WORKTREE_OP", "GH_TOKEN", "GITHUB_TOKEN", "GITLAB_TOKEN", "AFK_GITHUB_API_URL", "AFK_GITLAB_API_URL")


def human() -> dict:
    return {k: v for k, v in os.environ.items() if k not in AGENT_VARS}


def agent(**extra: str) -> dict:
    return dict(human(), CLAUDECODE="1", CLAUDE_PLUGIN_ROOT=str(PLUGIN_ROOT), **extra)


def git(cwd: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *IDENTITY, *args], capture_output=True, text=True,
                          env=env or human(), timeout=120)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository on `trunk` with a `main` branch (protected by the fallback rule) and no remote."""
    path = tmp_path / "repo"
    path.mkdir()
    for args in (("init", "-q", "-b", "trunk"), ("commit", "-q", "--allow-empty", "-m", "seed"),
                 ("branch", "main"), ("branch", "feature")):
        assert git(path, *args).returncode == 0
    return path


def install(repo: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([str(BASH), INSTALLER.as_posix()], capture_output=True, text=True, cwd=repo,
                          env=env or agent(), timeout=120)


def hooks_dir(repo: Path) -> Path:
    return Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path", "hooks").stdout.strip())


def test_the_installer_covers_a_repository_with_no_afk_folder(repo):
    done = install(repo)
    assert done.returncode == 0, done.stderr
    assert (hooks_dir(repo) / "pre-commit").is_file() and (hooks_dir(repo) / "reference-transaction").is_file()
    before = (hooks_dir(repo) / "pre-commit").read_text(encoding="utf-8")
    assert install(repo).returncode == 0
    assert (hooks_dir(repo) / "pre-commit").read_text(encoding="utf-8") == before


def test_a_foreign_hook_is_kept_and_a_hooks_path_is_skipped_with_a_notice(repo, tmp_path):
    (hooks_dir(repo) / "pre-commit").write_text("#!/bin/sh\necho foreign\n", encoding="utf-8")
    done = install(repo, agent())
    assert "pre-existing non-AFK pre-commit hook" in done.stderr
    assert "foreign" in (hooks_dir(repo) / "pre-commit").read_text(encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()
    for args in (("init", "-q", "-b", "trunk"), ("config", "core.hooksPath", ".husky")):
        assert git(other, *args).returncode == 0
    done = install(other)
    assert done.returncode == 0 and "core.hooksPath" in done.stderr
    assert not (other / ".husky").exists() and not (other / ".git" / "hooks" / "pre-commit").exists()


def commit(where: Path, env: dict, *extra: str) -> subprocess.CompletedProcess:
    return git(where, "commit", "-q", "--allow-empty", "-m", "c", *extra, env=env)


def test_an_agent_commit_in_the_main_checkout_is_refused_and_a_human_one_passes(repo):
    install(repo)
    head = git(repo, "rev-parse", "HEAD").stdout
    refused = commit(repo, agent())
    assert refused.returncode != 0 and "main checkout" in refused.stderr
    assert git(repo, "rev-parse", "HEAD").stdout == head
    assert commit(repo, human()).returncode == 0


def test_no_verify_still_meets_the_ref_transaction_veto(repo):
    install(repo)
    refused = commit(repo, agent(), "--no-verify")
    assert refused.returncode != 0 and "main checkout" in refused.stderr


@pytest.mark.parametrize("override", [{"AFK_ALLOW_PROTECTED": "1"}, {"AFK_WORKTREE_OP": "1"}])
def test_the_override_and_the_plugin_marker_pass(repo, override):
    install(repo)
    assert commit(repo, agent(**override)).returncode == 0


def test_an_agent_commit_in_a_worktree_is_refused_only_on_a_protected_branch(repo, tmp_path):
    install(repo)
    assert git(repo, "worktree", "add", "-q", str(tmp_path / "prot"), "main").returncode == 0
    assert git(repo, "worktree", "add", "-q", str(tmp_path / "free"), "feature").returncode == 0
    refused = commit(tmp_path / "prot", agent())
    assert refused.returncode != 0 and "protected" in refused.stderr
    assert commit(tmp_path / "prot", human()).returncode == 0
    assert commit(tmp_path / "free", agent()).returncode == 0


@pytest.mark.parametrize("move", [("switch", "-q", "feature"), ("checkout", "-q", "feature"),
                                  ("reset", "-q", "--hard", "HEAD"), ("switch", "-q", "--detach")])
def test_an_agent_branch_move_in_the_main_checkout_is_refused_and_a_human_one_passes(repo, move):
    install(repo)
    commit(repo, human())
    head = git(repo, "symbolic-ref", "-q", "HEAD").stdout
    if move[0] == "reset":
        move = ("reset", "-q", "--hard", "HEAD~1")
    refused = git(repo, *move, env=agent())
    assert refused.returncode != 0, refused.stdout
    git(repo, "reset", "-q", "--hard", env=human())
    assert git(repo, "symbolic-ref", "-q", "HEAD").stdout == head
    assert git(repo, *move, env=human()).returncode == 0


def test_a_new_worktree_branch_from_the_main_checkout_is_not_a_move(repo, tmp_path):
    install(repo)
    made = git(repo, "worktree", "add", "-q", "-b", "fresh", str(tmp_path / "fresh"), env=agent())
    assert made.returncode == 0, made.stderr
    made = git(repo, "worktree", "add", "-q", "--detach", str(tmp_path / "det"), env=agent())
    assert made.returncode == 0, made.stderr
    made = git(repo, "worktree", "add", "-q", str(tmp_path / "old"), "feature", env=agent())
    assert made.returncode == 0, made.stderr
    assert git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip() == "trunk"


def test_the_marker_of_the_plugin_is_not_left_on_for_plain_git(repo):
    install(repo)
    assert git(repo, "switch", "-q", "feature", env=agent()).returncode != 0


def test_a_human_is_never_gated_even_with_the_hooks_installed(repo):
    install(repo)
    assert git(repo, "switch", "-q", "feature", env=human()).returncode == 0
    assert commit(repo, human()).returncode == 0
