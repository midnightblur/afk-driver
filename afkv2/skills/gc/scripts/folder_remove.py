"""Remove one worktree folder on Windows: a rename to `<folder>.gc-removing` proves no process uses it, then the delete, then git forgets the worktree."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN / "ports"))

from tracker.envelope import Refusal  # noqa: E402

REMOVING_SUFFIX = ".gc-removing"
GIT_LIMIT = 60
WINDOWS = os.name == "nt"


def _make_writable_and_retry(function, path, error):
    """A read-only file or folder refuses its delete on Windows: clear the flag and delete again."""
    if not isinstance(error, PermissionError):
        raise error
    os.chmod(path, stat.S_IWRITE)
    function(path)


def _delete(removing):
    """Delete a `.gc-removing` folder. A delete that stops half way keeps the rest of it for the next run."""
    try:
        shutil.rmtree(removing, onexc=_make_writable_and_retry)
    except OSError as error:
        raise Refusal("delete-failed", f"the delete of {removing} stopped: {error.strerror} ({error.filename}); "
                                       "close what uses it and run gc again to finish it",
                      folder=str(removing), winerror=getattr(error, "winerror", None)) from None


def _prune(repo):
    done = subprocess.run(["git", "worktree", "prune"], cwd=repo, capture_output=True, text=True, encoding="utf-8",
                          stdin=subprocess.DEVNULL, timeout=GIT_LIMIT)
    if done.returncode != 0:
        raise Refusal("git-failed", f"git worktree prune in {repo}: {done.stderr.strip()}")


GONE = 2
REFUSED_RENAME = {
    32: ("in-use", "a process uses {folder} as its working folder; close it and run gc again"),
    5: ("in-use-or-no-right", "a process uses a file or subfolder of {folder}, or gc has no right to rename it; "
                              "close what uses it and run gc again"),
    183: ("name-taken", "{removing} exists and is not a folder gc left; move it away and run gc again"),
}


def _rename(folder, removing):
    """The rename that proves no process uses `folder`. False when the folder is already gone.

    A refused rename touched nothing; its Windows error names the cause."""
    try:
        os.rename(folder, removing)
    except OSError as error:
        winerror = getattr(error, "winerror", None)
        if winerror == GONE:
            return False
        code, reason = REFUSED_RENAME.get(winerror, ("rename-failed", "Windows refused to rename {folder}: {text}"))
        raise Refusal(code, reason.format(folder=folder, removing=removing, text=error.strerror) + "; nothing was touched",
                      folder=str(folder), winerror=winerror) from None
    return True


def remove_worktree_folder(repo, folder):
    """Rename `folder` to its name plus `.gc-removing`, delete it, and run `git worktree prune` in `repo`.
    A leftover `.gc-removing` folder is deleted first; with no folder left, the folder counts as removed.

    Answer `{"folder", "result", "seconds"}`, `result` `removed` or `already gone`.
    Refuse `not-windows` elsewhere, before any touch, and the code of a refused rename."""
    if not WINDOWS:
        raise Refusal("not-windows", "gc deletes a worktree folder on Windows only; nothing was touched", folder=str(folder))
    start = time.monotonic()
    removing = Path(str(folder) + REMOVING_SUFFIX)
    resumed = removing.is_dir()
    if resumed:
        _delete(removing)  # The leftover of a delete that stopped half way: finish it first.
    if resumed and not os.path.lexists(folder):
        result = "removed"
    elif _rename(folder, removing):
        _delete(removing)
        result = "removed"
    else:
        result = "already gone"
    _prune(repo)
    return {"folder": str(folder), "result": result, "seconds": round(time.monotonic() - start, 2)}
