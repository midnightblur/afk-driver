"""`setup_secrets.py` resolves the repository the human ran it from.

The plugin is installed, not checked out beside the work, so its own root is
usually outside any repository. A resolution pinned to that root aborts on a
marketplace install and, on a clone of the plugin itself, silently answers with
the wrong repository. Both are caught here by asserting the *identity* of the
resolved path from a cwd unrelated to the plugin tree — a test asserting only
that the script did not abort would pass against the second failure.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parents[2]
          / "skills" / "afk" / "setup" / "scripts" / "setup_secrets.py")


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def slashes(p) -> str:
    return str(p).replace("\\", "/")


@pytest.fixture
def repo(tmp_path):
    """A checkout with no relation to the plugin tree."""
    r = tmp_path / "consuming-repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "T")
    (r / "README.md").write_text("x\n", encoding="utf-8")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "init")
    return r


def preflight(cwd) -> str:
    """Run the script far enough to print its preflight verdict.

    CLAUDECODE is dropped (the script refuses an agent shell) and HOME is
    redirected so the run cannot read or write the developer's harness config.
    stdin is closed, so the run ends at the first prompt after preflight.
    """
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "HOME", "USERPROFILE")}
    env["HOME"] = env["USERPROFILE"] = str(cwd)
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=str(cwd), env=env,
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120,
    ).stdout


def test_resolves_the_callers_repository(repo):
    out = slashes(preflight(repo))
    assert "not inside a git checkout" not in out
    assert f"repo {slashes(repo.resolve())}" in out


def test_aborts_when_the_caller_is_outside_any_repository(tmp_path):
    outside = tmp_path / "no-repo"
    outside.mkdir()
    assert "not inside a git checkout" in preflight(outside)
