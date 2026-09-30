"""The H6 probe in `MANIFEST.md` must not report a repository nobody configured as healthy.

The probe block is lifted from the manifest and run, so the test binds the text
a human or agent executes, not a copy of it.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "skills" / "afk" / "setup" / "MANIFEST.md"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="needs a POSIX shell")


def probe_block() -> str:
    text = MANIFEST.read_text(encoding="utf-8")
    section = text.split("### H6 ", 1)[1].split("\n### ", 1)[0]
    return re.search(r"```\n(.*?)```", section, re.S).group(1)


def run(repo: Path, home: Path):
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
           "AFK_PLUGIN_ROOT": str(ROOT).replace("\\", "/"),
           "CLAUDE_PROJECT_DIR": str(repo)}
    env.pop("AFK_CONFIG", None)
    return subprocess.run([BASH, "-c", probe_block()], cwd=repo, env=env,
                          capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "-C", str(r), "init", "-q", "-b", "main"], check=True)
    (tmp_path / "home").mkdir()
    return r


def test_no_config_anywhere_needs_human(repo, tmp_path):
    out = run(repo, tmp_path / "home")
    assert out.returncode != 0
    assert out.stdout.strip() == "needs-human: see H0"
    assert "ok" not in out.stdout.split()


def test_repo_config_none_is_ok(repo, tmp_path):
    (repo / ".afk").mkdir()
    (repo / ".afk" / "config.yaml").write_text("schema: 1\ntracker: none\nforge: none\n",
                                               encoding="utf-8")
    out = run(repo, tmp_path / "home")
    assert out.returncode == 0, out.stdout + out.stderr
    assert out.stdout.strip() == "ok"


def test_machine_layer_none_is_ok(repo, tmp_path):
    home = tmp_path / "home"
    (home / ".afk").mkdir()
    (home / ".afk" / "config.yaml").write_text("schema: 1\ntracker: none\nforge: none\n",
                                               encoding="utf-8")
    out = run(repo, home)
    assert out.returncode == 0, out.stdout + out.stderr
