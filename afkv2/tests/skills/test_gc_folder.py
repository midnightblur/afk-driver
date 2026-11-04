"""The folder removal of gc: a rename proves no process uses the folder, then the delete, then git forgets the worktree. Real Windows renames."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from contextlib import contextmanager
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


@contextmanager
def a_process_in(folder):
    """A child process whose working folder is `folder`, alive until the block ends; it reports ready once it runs."""
    child = subprocess.Popen([sys.executable, "-c", "import sys; print('ready', flush=True); sys.stdin.read()"],
                             cwd=folder, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "ready"
        yield child
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        child.stdout.close()


@contextmanager
def a_file_open_in(folder):
    with open(Path(folder) / "plan" / "PLAN.md", "rb") as handle:
        yield handle


HOLDERS = {
    "working folder": (lambda repo: a_process_in(repo.run), "in-use"),
    "subfolder": (lambda repo: a_process_in(repo.run / "plan"), "in-use-or-no-right"),
    "open file": (lambda repo: a_file_open_in(repo.run), "in-use-or-no-right"),
}


@windows_only
@pytest.mark.parametrize("holder", sorted(HOLDERS))
def test_a_folder_in_use_refuses_by_its_windows_error_and_every_entry_stays(repo, holder):
    hold, code = HOLDERS[holder]
    before = entries(repo.run)

    with hold(repo), pytest.raises(Refusal) as refused:
        folder_remove.remove_worktree_folder(repo.main, repo.run)

    assert refused.value.code == code
    assert entries(repo.run) == before
    assert not Path(str(repo.run) + folder_remove.REMOVING_SUFFIX).exists()
    assert repo.run.resolve() in known_worktrees(repo)
    assert git(repo.main, "branch", "--list", repo.run_branch)


def leftover_of(folder):
    return Path(str(folder) + folder_remove.REMOVING_SUFFIX)


@windows_only
def test_a_leftover_folder_is_deleted_before_the_rename(repo):
    leftover = leftover_of(repo.run)
    read_only(leftover / "half" / "deleted.txt")

    answer = folder_remove.remove_worktree_folder(repo.main, repo.run)

    assert answer["result"] == "removed"
    assert not repo.run.exists()
    assert not leftover.exists()
    assert repo.run.resolve() not in known_worktrees(repo)


@windows_only
def test_a_leftover_with_no_folder_left_is_deleted_and_the_folder_counts_as_removed(repo):
    read_only(repo.run / "plan" / "locked.md")
    leftover = leftover_of(repo.run)
    os.rename(repo.run, leftover)

    answer = folder_remove.remove_worktree_folder(repo.main, repo.run)

    assert answer["result"] == "removed"
    assert isinstance(answer["seconds"], float)
    assert not leftover.exists()
    assert repo.run.resolve() not in known_worktrees(repo)


@windows_only
def test_the_new_name_taken_by_a_file_refuses_name_taken_and_touches_nothing(repo):
    taken = leftover_of(repo.run)
    taken.write_text("not gc's folder\n", encoding="utf-8")
    before = entries(repo.run)

    with pytest.raises(Refusal) as refused:
        folder_remove.remove_worktree_folder(repo.main, repo.run)

    assert refused.value.code == "name-taken"
    assert entries(repo.run) == before
    assert taken.read_text(encoding="utf-8") == "not gc's folder\n"
    assert repo.run.resolve() in known_worktrees(repo)


@windows_only
def test_a_folder_already_gone_answers_already_gone_and_git_forgets_it(repo):
    shutil.rmtree(repo.run)
    assert repo.run.resolve() in known_worktrees(repo)

    answer = folder_remove.remove_worktree_folder(repo.main, repo.run)

    assert answer["result"] == "already gone"
    assert isinstance(answer["seconds"], float)
    assert repo.run.resolve() not in known_worktrees(repo)


@windows_only
def test_any_other_rename_error_refuses_rename_failed_with_the_windows_text(repo, tmp_path):
    no_parent = tmp_path / "no-parent" / "feature-run"

    with pytest.raises(Refusal) as refused:
        folder_remove.remove_worktree_folder(repo.main, no_parent)

    assert refused.value.code == "rename-failed"
    assert "The system cannot find the path specified" in refused.value.reason
    assert refused.value.extra["winerror"] == 3
    assert repo.run.resolve() in known_worktrees(repo)


@windows_only
def test_a_delete_that_fails_refuses_delete_failed_and_keeps_the_leftover_for_the_next_run(repo):
    leftover = leftover_of(repo.run)
    (leftover / "held.txt").parent.mkdir()
    (leftover / "held.txt").write_text("held\n", encoding="utf-8")
    before = entries(repo.run)

    with open(leftover / "held.txt", "rb"), pytest.raises(Refusal) as refused:
        folder_remove.remove_worktree_folder(repo.main, repo.run)

    assert refused.value.code == "delete-failed"
    assert refused.value.extra["folder"] == str(leftover)
    assert leftover.is_dir()
    assert entries(repo.run) == before
    assert repo.run.resolve() in known_worktrees(repo)

    answer = folder_remove.remove_worktree_folder(repo.main, repo.run)

    assert answer["result"] == "removed"
    assert not leftover.exists() and not repo.run.exists()
