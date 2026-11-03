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


def _delete(folder):
    shutil.rmtree(folder, onexc=_make_writable_and_retry)


def _prune(repo):
    done = subprocess.run(["git", "worktree", "prune"], cwd=repo, capture_output=True, text=True, encoding="utf-8",
                          stdin=subprocess.DEVNULL, timeout=GIT_LIMIT)
    if done.returncode != 0:
        raise Refusal("git-failed", f"git worktree prune in {repo}: {done.stderr.strip()}")


REFUSED_RENAME = {
    32: ("in-use", "a process uses {folder} as its working folder; close it and run gc again"),
    5: ("in-use-or-no-right", "a process uses a file or subfolder of {folder}, or gc has no right to rename it; "
                              "close what uses it and run gc again"),
}


def _rename(folder, removing):
    """The rename that proves no process uses `folder`. A refused rename touched nothing; its Windows error names the cause."""
    try:
        os.rename(folder, removing)
    except OSError as error:
        known = REFUSED_RENAME.get(getattr(error, "winerror", None))
        if known is None:
            raise
        code, reason = known
        raise Refusal(code, reason.format(folder=folder) + "; nothing was touched", folder=str(folder),
                      winerror=error.winerror) from None


def remove_worktree_folder(repo, folder):
    """Rename `folder` to its name plus `.gc-removing`, delete it, and run `git worktree prune` in `repo`.

    Answer `{"folder", "result", "seconds"}`, `result` `removed`. Refuse `not-windows` elsewhere, before any touch."""
    if not WINDOWS:
        raise Refusal("not-windows", "gc deletes a worktree folder on Windows only; nothing was touched", folder=str(folder))
    start = time.monotonic()
    removing = Path(str(folder) + REMOVING_SUFFIX)
    _rename(folder, removing)
    _delete(removing)
    _prune(repo)
    return {"folder": str(folder), "result": "removed", "seconds": round(time.monotonic() - start, 2)}
