"""The real `hooks/worktree-create.sh` with a `claude` envelope: the output shape the harness reads.

The harness uses the bare path on stdout and fails the creation on a non-zero exit. Real
worktrees in temporary repositories under a temporary home.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HOOK = PLUGIN_ROOT / "hooks" / "worktree-create.sh"
SCRUB = ("AFK_", "CLAUDE", "CODEX", "PLUGIN_ROOT", "GIT_", "HERDR")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASH = _load("afk_run_hook_for_hook_tests", PLUGIN_ROOT / "hooks" / "run-hook.py").find_bash()
rl = _load("afk_repo_list_for_hook_tests", PLUGIN_ROOT / "scripts" / "repo_list.py")
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def listed(tmp_path, monkeypatch):
    home, root, repo = tmp_path / "home", tmp_path / "root", tmp_path / "src" / "proj"
    (home / ".afk").mkdir(parents=True)
    root.mkdir()
    repo.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    git(repo, "init", "-q", "-b", "dev")
    git(repo, "commit", "-q", "--allow-empty", "-m", "seed")
    (home / ".afk" / "config.yaml").write_text(f"developer:\n  worktreeRoot: '{root.as_posix()}'\n",
                                               encoding="utf-8")
    rl.add_repository(repo, root)
    return home, root, repo


def run_hook(home: Path, repo: Path, name: str):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(SCRUB)}
    env.update(HOME=str(home), USERPROFILE=str(home), AFK_PYTHON=sys.executable,
               CLAUDE_PLUGIN_ROOT=str(PLUGIN_ROOT))
    envelope = {"session_id": "s-hook", "transcript_path": "", "cwd": str(repo),
                "hook_event_name": "WorktreeCreate", "name": name}
    return subprocess.run([str(BASH), str(HOOK)], input=json.dumps(envelope), capture_output=True, text=True,
                          cwd=str(repo), env=env, timeout=600)


def same(a, b) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def test_success_prints_only_the_bare_path_under_the_root_and_exits_0(listed):
    home, root, repo = listed
    done = run_hook(home, repo, "hooked")
    assert done.returncode == 0, done.stderr
    assert done.stdout.count("\n") == 1 and done.stdout.endswith("\n"), repr(done.stdout)
    path = done.stdout.strip()
    assert not path.startswith("WORKTREE_PATH=")
    assert same(path, root / "proj" / "hooked") and (Path(path) / ".git").is_file()


def test_a_root_that_fails_a_rule_exits_non_zero_with_empty_stdout_and_no_worktree(listed):
    home, root, repo = listed
    (home / ".afk" / "config.yaml").write_text("developer:\n  worktreeRoot: relative/root\n", encoding="utf-8")
    done = run_hook(home, repo, "refused")
    assert done.returncode == 3 and done.stdout == ""
    assert "ERROR=worktree root: R-01 " in done.stderr
    assert git(repo, "worktree", "list", "--porcelain").count("worktree ") == 1
    assert not (root / "proj" / "refused").exists() and not (repo / ".claude" / "worktrees" / "refused").exists()
