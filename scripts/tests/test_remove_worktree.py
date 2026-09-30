"""`remove-worktree.py`, the removal and prune handlers, and their registration.

Disposable repositories only. A worktree counts as plugin-made when it has an owner record.
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
SCRIPT = PLUGIN_ROOT / "scripts" / "remove-worktree.py"
IDENTITY = ("-c", "user.name=t", "-c", "user.email=t@example.com")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASH = _load("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py").find_bash()
OWNER = _load("afk_owner", PLUGIN_ROOT / "scripts" / "worktree_owner.py")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *IDENTITY, *args], check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "dev")
    git(path, "commit", "-q", "--allow-empty", "-m", "seed")
    return path


def made(repo: Path, name: str, owner: dict | None = None, record: bool = True) -> Path:
    """A linked worktree on branch `worktree-<name>` with an owner record."""
    path = repo / ".claude" / "worktrees" / name
    git(repo, "worktree", "add", "-q", "-b", f"worktree-{name}", str(path))
    if record:
        folder = repo / ".git" / "afk-worktrees"
        folder.mkdir(exist_ok=True)
        (folder / f"{name}.json").write_text(json.dumps({
            "name": name, "path": path.as_posix(), "branch": f"worktree-{name}", "harness": "claude",
            "owner": owner or {"pid": None, "ctime": None}}), encoding="utf-8")
    return path


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd,
                          timeout=120)


def branches(repo: Path) -> list[str]:
    return git(repo, "branch", "--format=%(refname:short)").split()


def test_a_clean_plugin_worktree_is_removed_with_its_branch(repo):
    path = made(repo, "clean")
    done = run("--path", str(path))
    assert done.returncode == 0, done.stderr
    assert not path.exists() and "worktree-clean" not in branches(repo)
    assert not (repo / ".git" / "afk-worktrees" / "clean.json").exists()


def test_uncommitted_work_keeps_the_worktree_and_prints_resume_and_remove(repo):
    path = made(repo, "dirty")
    (path / "w.txt").write_text("x", encoding="utf-8")
    done = run("--path", str(path))
    assert path.is_dir() and "worktree-dirty" in branches(repo)
    assert "resume: cd" in done.stderr and "--force" in done.stderr and path.as_posix() in done.stderr


def test_an_unpushed_commit_keeps_the_worktree_and_its_branch(repo):
    path = made(repo, "ahead")
    git(path, "commit", "-q", "--allow-empty", "-m", "own work")
    done = run("--path", str(path))
    assert path.is_dir() and "worktree-ahead" in branches(repo) and "exist nowhere else" in done.stderr


def test_a_commit_that_another_branch_holds_is_not_unpushed(repo):
    path = made(repo, "shared")
    git(path, "commit", "-q", "--allow-empty", "-m", "kept elsewhere")
    git(repo, "branch", "elsewhere", "worktree-shared")
    run("--path", str(path))
    assert not path.exists() and "elsewhere" in branches(repo)
    assert git(repo, "log", "-1", "--format=%s", "elsewhere") == "kept elsewhere"


def test_a_worktree_with_no_record_is_never_touched(repo):
    path = made(repo, "foreign", record=False)
    run("--path", str(path))
    assert path.is_dir()


def test_force_removes_a_kept_worktree(repo):
    path = made(repo, "forced")
    (path / "w.txt").write_text("x", encoding="utf-8")
    run("--path", str(path), "--force")
    assert not path.exists()


def test_prune_removes_only_a_clean_worktree_whose_owner_is_dead(repo):
    dead = {"pid": 2147483000, "ctime": "1"}
    gone = made(repo, "gone", dead)
    busy = made(repo, "busy", dead)
    (busy / "w.txt").write_text("x", encoding="utf-8")
    live = made(repo, "live", {"pid": os.getpid(), "ctime": OWNER.creation_time(os.getpid())})
    unknown = made(repo, "unknown")
    lost = made(repo, "lost", dead)
    import shutil
    shutil.rmtree(lost)
    done = run("--prune", cwd=repo)
    assert done.returncode == 0, done.stderr
    assert not gone.exists()
    assert busy.is_dir() and live.is_dir() and unknown.is_dir()
    assert not (repo / ".git" / "afk-worktrees" / "lost.json").exists()


def test_the_removal_handler_takes_worktree_path_or_cwd(repo):
    if BASH is None:
        pytest.skip("no POSIX shell")
    handler = PLUGIN_ROOT / "hooks" / "worktree-remove.sh"
    by_path = made(repo, "by-path")
    by_cwd = made(repo, "by-cwd")
    for key, target in (("worktree_path", by_path), ("cwd", by_cwd)):
        done = subprocess.run([str(BASH), handler.as_posix()], input=json.dumps({key: str(target)}),
                              capture_output=True, text=True, timeout=120,
                              env=dict(os.environ, AFK_PLUGIN_ROOT=str(PLUGIN_ROOT)))
        assert done.returncode == 0 and not target.exists(), done.stderr


@pytest.mark.parametrize("manifest,var,event", [("hooks.json", "CLAUDE_PLUGIN_ROOT", "WorktreeRemove"),
                                                ("hooks.codex.json", "PLUGIN_ROOT", "SessionEnd")])
def test_the_manifests_register_the_removal_and_the_prune(manifest, var, event):
    document = json.loads((PLUGIN_ROOT / "hooks" / manifest).read_text(encoding="utf-8"))["hooks"]
    commands = [h["command"] for g in document[event] for h in g["hooks"]]
    assert any("worktree-remove.sh" in c and var in c for c in commands)
    start = [h["command"] for g in document["SessionStart"] for h in g["hooks"]]
    assert any("worktree-prune.sh" in c for c in start)
