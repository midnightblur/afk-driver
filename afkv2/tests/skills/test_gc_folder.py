"""The folder removal of gc: a rename proves no process uses the folder, then the delete, then git forgets the worktree. Real Windows renames."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(AFKV2 / "skills" / "gc" / "scripts"))
sys.path.insert(0, str(AFKV2 / "ports"))

import folder_remove  # noqa: E402
from gc_repo import build_gc_repo, git  # noqa: E402
from tracker.envelope import Refusal  # noqa: E402

windows_only = pytest.mark.skipif(os.name != "nt", reason="the folder removal runs on Windows only")


@pytest.fixture
def repo(tmp_path):
    return build_gc_repo(tmp_path)


def known_worktrees(repo):
    lines = git(repo.main, "worktree", "list", "--porcelain").splitlines()
    return {Path(line[len("worktree "):]).resolve() for line in lines if line.startswith("worktree ")}


def read_only(path, text="kept\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.chmod(path, stat.S_IREAD)


@windows_only
def test_a_free_folder_is_renamed_deleted_with_its_read_only_files_and_git_forgets_it(repo):
    read_only(repo.run / "plan" / "locked.md")
    read_only(repo.run / "deep" / "er" / "locked.txt")
    assert repo.run.resolve() in known_worktrees(repo)

    answer = folder_remove.remove_worktree_folder(repo.main, repo.run)

    assert answer["result"] == "removed"
    assert answer["folder"] == str(repo.run)
    assert isinstance(answer["seconds"], float) and answer["seconds"] >= 0
    assert not repo.run.exists()
    assert not Path(str(repo.run) + folder_remove.REMOVING_SUFFIX).exists()
    assert folder_remove.REMOVING_SUFFIX == ".gc-removing"
    assert repo.run.resolve() not in known_worktrees(repo)
    assert repo.feature.exists()


def entries(folder):
    """Every entry under `folder`, relative, with each file's bytes: the proof that nothing was touched."""
    return {path.relative_to(folder).as_posix(): path.read_bytes() if path.is_file() else None
            for path in Path(folder).rglob("*")}


def test_on_a_system_that_is_not_windows_the_removal_refuses_and_touches_nothing(repo, monkeypatch):
    monkeypatch.setattr(folder_remove, "WINDOWS", False)
    leftover = Path(str(repo.run) + folder_remove.REMOVING_SUFFIX)
    leftover.mkdir()
    before = entries(repo.run)

    with pytest.raises(Refusal) as refused:
        folder_remove.remove_worktree_folder(repo.main, repo.run)

    assert refused.value.code == "not-windows"
    assert entries(repo.run) == before
    assert leftover.is_dir()
    assert repo.run.resolve() in known_worktrees(repo)
