"""The gc target: one JSON file per feature branch in git's common folder, its file-name key, its atomic write, the lock of one run per target, and the receipt of a list."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN / "ports"))

from tracker.envelope import Refusal  # noqa: E402

FOLDER = "afkv2-gc"
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
