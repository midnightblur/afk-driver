"""Skip marks for tests that need a minimum git version (floor: skills/afk/setup/MANIFEST.md C2b)."""
from __future__ import annotations

import re
import subprocess

import pytest


def git_version() -> tuple[int, int]:
    out = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout
    found = re.search(r"(\d+)\.(\d+)", out)
    return (int(found[1]), int(found[2])) if found else (0, 0)


NEEDS_HEAD_SWITCH_HOOK = pytest.mark.skipif(
    git_version() < (2, 46),
    reason="git < 2.46 sends no HEAD switch to the reference-transaction hook, so the backstop cannot refuse it",
)
