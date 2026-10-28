"""`afk-config.py resolve worktreeRoot`: the root the worktree creator reads, checked on every read.

A temporary home holds the machine file; the developer's own `~/.afk` is never read.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CONFIG = PLUGIN_ROOT / "scripts" / "afk-config.py"
SCRUB = ("AFK_", "CLAUDE", "CODEX", "PLUGIN_ROOT", "GIT_")


@pytest.fixture
def home(tmp_path):
    folder = tmp_path / "home"
    (folder / ".afk").mkdir(parents=True)
    return folder


def machine(home: Path, text: str) -> None:
    (home / ".afk" / "config.yaml").write_text(text, encoding="utf-8")


def resolve(home: Path, key: str = "worktreeRoot", cwd: Path | None = None):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(SCRUB)}
    env.update(HOME=str(home), USERPROFILE=str(home))
    return subprocess.run([sys.executable, str(CONFIG), "resolve", key], capture_output=True, text=True,
                          cwd=cwd or home, env=env, timeout=120)


def same(a, b) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def test_a_confirmed_root_prints_with_no_note(tmp_path, home):
    root = tmp_path / "root"
    root.mkdir()
    machine(home, f"developer:\n  worktreeRoot: '{root.as_posix()}'\n")
    done = resolve(home)
    assert done.returncode == 0 and same(done.stdout.strip().strip("'"), root), done.stderr
    assert done.stderr == ""


def test_the_suggestion_prints_with_a_note_when_nothing_is_confirmed(home):
    (home / "repo-worktrees").mkdir()
    done = resolve(home)
    assert done.returncode == 0 and same(done.stdout.strip().strip("'"), home / "repo-worktrees"), done.stderr
    assert "worktreeRoot is not confirmed" in done.stderr and "comes from suggestion" in done.stderr
    assert "run /afk:setup" in done.stderr


def test_a_passing_old_base_value_prints_with_a_note_naming_it(tmp_path, home):
    base = tmp_path / "old"
    base.mkdir()
    machine(home, f"developer:\n  worktreeBasePath: '{base.as_posix()}'\n")
    done = resolve(home)
    assert done.returncode == 0 and same(done.stdout.strip().strip("'"), base), done.stderr
    assert "comes from developer.worktreeBasePath" in done.stderr


@pytest.mark.parametrize(("text", "rule"), [
    ("developer:\n  worktreeRoot: relative/root\n", "R-01"),
    ("developer:\n  worktreeRoot: '~/trees'\n", "R-01"),
    ("", "R-03"),
])
def test_a_root_that_fails_a_rule_exits_1_naming_the_rule(home, text, rule):
    machine(home, text)
    done = resolve(home)
    assert done.returncode == 1 and done.stdout == ""
    assert done.stderr.startswith(f"afk-config: worktreeRoot: {rule} ") and "run /afk:setup" in done.stderr


def test_a_root_inside_a_repository_exits_1_with_r02(tmp_path, home):
    repo = tmp_path / "repo"
    (repo / "inside").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    machine(home, f"developer:\n  worktreeRoot: '{(repo / 'inside').as_posix()}'\n")
    done = resolve(home)
    assert done.returncode == 1 and "worktreeRoot: R-02 " in done.stderr


def test_a_space_in_the_root_passes_with_the_r04_warning(tmp_path, home):
    root = tmp_path / "my root"
    root.mkdir()
    machine(home, f"developer:\n  worktreeRoot: '{root.as_posix()}'\n")
    done = resolve(home)
    assert done.returncode == 0 and "warning: worktreeRoot: R-04 " in done.stderr


def test_an_unreadable_machine_file_exits_2(home):
    machine(home, "developer: text\n")
    done = resolve(home)
    assert done.returncode == 2 and done.stderr.startswith("afk-config: worktreeRoot: ")


def test_resolve_worktree_base_path_is_gone(home):
    done = resolve(home, "worktreeBasePath")
    assert done.returncode == 2 and "resolve worktreeRoot" in done.stderr and done.stdout == ""


def test_an_unknown_key_is_not_offered_the_removed_key(home):
    done = resolve(home, "noSuchKey")
    assert done.returncode == 2 and "expected one of " in done.stderr and "worktreeRoot" in done.stderr
    assert "worktreeBasePath" not in done.stderr
