"""The gc target: one JSON file per feature branch in git's common folder, its file-name key, its atomic write, the lock of one run per target, and the receipt of a list."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN / "ports"))

from tracker.envelope import Refusal  # noqa: E402

sys.path.insert(0, str(PLUGIN / "skills" / "autopilot" / "scripts"))
from start_gate import RUN_SUFFIX  # noqa: E402

FOLDER = "afkv2-gc"
SCHEMA = "afkv2.gc/0"
FIELDS = ("schema", "feature_branch", "feature_worktree", "run_branch", "run_worktree", "remote",
          "change", "tips", "receipt", "state", "left", "listed_at")
GIT_LIMIT = 60
UNSAFE = frozenset('\\/:*?"<>|%')
ENCODED = re.compile(r"%([0-9A-F]{2})")


def encode_branch(branch):
    """The file-name stem of a branch: each of `\\ / : * ? " < > |`, `%` and each control character becomes `%XX`."""
    return "".join(f"%{ord(char):02X}" if char in UNSAFE or ord(char) < 0x20 or ord(char) == 0x7F else char
                   for char in branch)


def decode_branch(stem):
    return ENCODED.sub(lambda match: chr(int(match.group(1), 16)), stem)


def common_dir(repo):
    """Git's common folder: the same for the main checkout and every linked worktree."""
    done = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=repo,
                          capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=GIT_LIMIT)
    if done.returncode != 0:
        raise Refusal("git-failed", f"{repo} is not in a git repository: {done.stderr.strip()}")
    return Path(done.stdout.strip())


def target_path(repo, branch):
    return common_dir(repo) / FOLDER / f"{encode_branch(branch)}.json"


def new_target(feature_branch, feature_worktree, change, tips, receipt, **fields):
    """A target with every field; `fields` overrides a default (run_branch, run_worktree, remote, state, left, listed_at)."""
    target = {"schema": SCHEMA, "feature_branch": feature_branch, "feature_worktree": str(feature_worktree),
              "run_branch": feature_branch + RUN_SUFFIX, "run_worktree": str(feature_worktree) + RUN_SUFFIX,
              "remote": "origin", "change": change, "tips": tips, "receipt": receipt, "state": "listed", "left": [],
              "listed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    unknown = sorted(set(fields) - set(FIELDS))
    if unknown:
        raise ValueError(f"a target has no field {', '.join(unknown)}")
    target.update(fields)
    return target


def read_target(repo, branch):
    """The stored target of `branch`, or None when there is none."""
    path = target_path(repo, branch)
    try:
        target = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise Refusal("bad-target", f"cannot read {path}: {error}; list again") from None
    if not isinstance(target, dict) or target.get("schema") != SCHEMA:
        found = target.get("schema") if isinstance(target, dict) else None
        raise Refusal("bad-target", f"{path} has schema {found!r}, not {SCHEMA}; list again")
    missing = [field for field in FIELDS if field not in target]
    if missing:
        raise Refusal("bad-target", f"{path} lacks {', '.join(missing)}; list again")
    return target


def write_target(repo, target):
    """Write to a temporary file beside the target, then replace the target in one step. Answer the target path."""
    path = target_path(repo, target["feature_branch"])
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.stem + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(target, stream, indent=1, ensure_ascii=False)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path


def lock_path(repo, branch):
    return target_path(repo, branch).with_suffix(".lock")


if os.name == "nt":
    import msvcrt

    def _lock(handle):
        os.lseek(handle, 0, os.SEEK_SET)
        msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)

    def _unlock(handle):
        os.lseek(handle, 0, os.SEEK_SET)
        msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock(handle):
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(handle):
        fcntl.flock(handle, fcntl.LOCK_UN)


class Lock:
    """A held lock on one target. The system frees it when the process ends, a crash included."""

    def __init__(self, path, handle):
        self.path, self._handle = path, handle

    def release(self):
        if self._handle is None:
            return
        try:
            _unlock(self._handle)
        finally:
            os.close(self._handle)
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.release()


def take_lock(repo, branch):
    """Lock byte 0 of the target's lock file; a lock another handle holds refuses `locked`."""
    path = lock_path(repo, branch)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_RDWR | os.O_CREAT)
    try:
        _lock(handle)
    except OSError:
        os.close(handle)
        raise Refusal("locked", f"another gc run holds the target of {branch}; run gc again when it ends") from None
    return Lock(path, handle)
