"""The H6 probe in `MANIFEST.md` must not call an unconfigured repository ok.

The probe block is lifted from the manifest and run, so the test binds the
text a human or agent executes, not a copy of it.
"""
import os
import re
import subprocess
from pathlib import Path

import pytest

from test_setup_secrets_repo_root import bash_executable

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "skills" / "afk" / "setup" / "MANIFEST.md"
BASH = bash_executable()
NONE = "schema: 1\ntracker: none\nforge: none\n"
DEV = "developer:\n  trackerAssignee: me\n  mrReviewer: you\n"


def probe_block() -> str:
    text = MANIFEST.read_text(encoding="utf-8")
    section = text.split("### H6 ", 1)[1].split("\n### ", 1)[0]
    return re.search(r"```\n(.*?)```", section, re.S).group(1)


def h0_notes() -> str:
    text = MANIFEST.read_text(encoding="utf-8")
    section = text.split("### H0 ", 1)[1].split("\n### ", 1)[0]
    return " ".join(section.split("**Notes:**", 1)[1].split())


def run(cwd: Path, home: Path, **extra):
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
           "AFK_PLUGIN_ROOT": str(ROOT).replace("\\", "/"), **extra}
    env.pop("AFK_CONFIG", None)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.update(extra)
    return subprocess.run([BASH, "-c", probe_block()], cwd=cwd, env=env,
                          capture_output=True, text=True)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "-C", str(r), "init", "-q", "-b", "main"], check=True)
    return r


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


def test_no_config_anywhere_needs_human(repo, home):
    out = run(repo, home)
    assert out.returncode == 1
    assert out.stdout.splitlines() == [
        "resolved: tracker=none forge=none",
        "needs-human: see H0 (trackerAssignee mrReviewer)"]


def test_developer_only_machine_file_still_needs_human(repo, home):
    write(home / ".afk" / "config.yaml", DEV)
    out = run(repo, home)
    assert out.returncode == 1
    assert "needs-human: see H0" in out.stdout


def test_unset_forge_is_reported_when_tracker_says_none(repo, home):
    write(home / ".afk" / "config.yaml", "tracker: none\n" + DEV)
    out = run(repo, home)
    assert out.returncode == 1
    assert out.stdout.splitlines()[-1] == "needs-human: see H0 (mrReviewer)"


def test_repo_file_with_key_left_unset_needs_human(repo, home):
    write(repo / ".afk" / "config.yaml", "schema: 1\n# tracker: jira  # TODO\n")
    out = run(repo, home)
    assert out.returncode == 1
    assert out.stdout.splitlines()[-1] == (
        "needs-human: see H0 (trackerAssignee mrReviewer)")


def test_present_file_naming_no_forge_points_at_a_working_fix(repo, home):
    """Step 0 skips a present file, so H0 Notes carry the fix themselves."""
    write(repo / ".afk" / "config.yaml",
          "schema: 1\ntracker: jira\njira:\n  project: XX\n")
    write(home / ".afk" / "config.yaml", DEV)
    out = run(repo, home)
    assert out.returncode == 1
    assert "needs-human: see H0 (mrReviewer)" in out.stdout.splitlines()
    notes = h0_notes()
    assert "set `tracker:` and `forge:` in `.afk/config.yaml`" in notes
    assert "`CONFIG.md`" in notes and "re-probe" in notes


def test_a_quoted_none_counts_as_saying_none(repo, home):
    write(repo / ".afk" / "config.yaml",
          "schema: 1\ntracker: \"none\"\nforge: 'none'\n")
    out = run(repo, home)
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.strip() == "ok"


def test_repo_config_none_is_ok(repo, home):
    write(repo / ".afk" / "config.yaml", NONE)
    out = run(repo, home)
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.strip() == "ok"


def test_machine_layer_none_is_ok(repo, home):
    write(home / ".afk" / "config.yaml", NONE)
    out = run(repo, home)
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.strip() == "ok"


def test_a_machine_only_person_is_confirmed_per_repository(repo, home):
    write(repo / ".afk" / "config.yaml", "schema: 1\ntracker: jira\nforge: none\n")
    write(home / ".afk" / "config.yaml", DEV)
    out = run(repo, home)
    assert out.returncode == 1
    assert out.stdout.splitlines()[-1] == "inherited from the machine file, confirm: trackerAssignee"

    write(repo / ".git" / "afk" / "config.yaml", "developer:\n  trackerAssignee: me\n")
    out = run(repo, home)
    assert out.returncode == 0, out.stdout + out.stderr


def test_a_neighbouring_checkout_missing_values_fails_the_probe(tmp_path, repo, home):
    write(repo / ".afk" / "config.yaml", NONE)
    other = tmp_path / "other"
    write(other / ".afk" / "config.yaml", "schema: 1\ntracker: none\nforge: github\n")
    subprocess.run(["git", "-C", str(other), "init", "-q", "-b", "main"], check=True)
    out = run(repo, home)
    assert out.returncode == 1
    assert out.stdout.splitlines()[-1] == (
        f"other checkouts need values: {other.resolve().as_posix()}")

    write(other / ".git" / "afk" / "config.yaml", "developer:\n  mrReviewer: you\n")
    out = run(repo, home)
    assert out.returncode == 0, out.stdout + out.stderr


def test_shared_overlay_none_is_ok(repo, home):
    write(repo / ".git" / "afk" / "config.yaml", NONE.replace("schema: 1\n", ""))
    out = run(repo, home)
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.strip() == "ok"


def test_worktree_base_failure_still_reported_beside_h0(tmp_path, home):
    bare = tmp_path / "not-a-repo"
    bare.mkdir()
    out = run(bare, home)
    assert out.returncode == 1
    assert "needs-human: see H0" in out.stdout
    assert "unresolved: worktreeBasePath" in out.stdout


def test_root_is_the_working_directorys_git_root(tmp_path, repo, home):
    """CLAUDE_PROJECT_DIR is ignored: `get` reads the working directory too."""
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(["git", "-C", str(other), "init", "-q"], check=True)
    write(other / ".afk" / "config.yaml", NONE)
    out = run(repo, home, CLAUDE_PROJECT_DIR=str(other))
    assert out.returncode == 1
    assert "needs-human: see H0" in out.stdout
