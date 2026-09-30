"""`setup_secrets.py` resolves the repository the human ran it from.

The plugin is installed, not checked out beside the work, so its own root is
usually outside any repository. A resolution pinned to that root aborts on a
marketplace install and, on a clone of the plugin itself, silently answers with
the wrong repository. Both are caught here by asserting the *identity* of the
resolved path from a cwd unrelated to the plugin tree — a test asserting only
that the script did not abort would pass against the second failure.
"""
import os
import shutil
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


def test_no_repository_config_is_a_warning(repo):
    out = slashes(preflight(repo))
    assert "no .afk/config.yaml in this repository" in out
    assert "run /afk:setup step 0" in out


def test_a_repository_config_silences_the_warning(repo):
    (repo / ".afk").mkdir()
    (repo / ".afk" / "config.yaml").write_text("schema: 1\n", encoding="utf-8")
    assert "no .afk/config.yaml" not in slashes(preflight(repo))


MANIFEST = SCRIPT.parents[1] / "MANIFEST.md"


def bash_executable() -> str:
    """Git Bash on Windows: a bare `bash` resolves to the WSL stub in System32."""
    if os.name == "nt":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        git_bash = Path(program_files) / "Git" / "bin" / "bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    return shutil.which("bash") or "bash"


def h0_probe() -> str:
    """The backticked command on the H0 entry's Probe line, exactly as written."""
    import re
    text = MANIFEST.read_text(encoding="utf-8")
    entry = text.split("### H0 · ", 1)[1].split("\n### ", 1)[0]
    return re.search(r"\*\*Probe:\*\* `([^`]+)`", entry).group(1)


def test_the_h0_probe_fails_without_a_config_and_passes_with_one(repo):
    probe = h0_probe()
    run = lambda: subprocess.run([bash_executable(), "-c", probe], cwd=str(repo),
                                 capture_output=True, text=True).returncode
    assert run() == 1
    (repo / ".afk").mkdir()
    (repo / ".afk" / "config.yaml").write_text("schema: 1\n", encoding="utf-8")
    assert run() == 0


def test_no_manifest_row_calls_a_missing_config_file_n_a():
    text = MANIFEST.read_text(encoding="utf-8")
    outside_h0 = text.replace(text.split("### H0 · ", 1)[1].split("\n### ", 1)[0], "")
    assert "no `.afk/config.yaml`" not in outside_h0
