"""The commit gates' configuration test in `precommit-gates.sh`.

The code gates run in a repository that adopted the plugin: one the settings
reader calls set up (a committed file or a repository personal file), or one
with an `.afk` folder. The shell answers without Python; one test pins it to
the reader's answer.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASH = _load("afk_run_hook_for_config_gate", ROOT / "hooks" / "run-hook.py").find_bash()
cfg = _load("afk_config_for_config_gate", ROOT / "scripts" / "afk-config.py")
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")

COMMENT_GATE = 'gate_comment() { printf "comment\\n" >> "$GATE_LOG"; return 0; }\n'


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                          cwd=str(cwd), check=True, capture_output=True, text=True).stdout


@pytest.fixture(scope="module")
def plugin(tmp_path_factory):
    root = tmp_path_factory.mktemp("config-gate") / "plugin"
    root.mkdir()
    for part in ("hooks", "scripts", "adapters"):
        shutil.copytree(ROOT / part, root / part, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (root / "hooks" / "comment-gate.sh").write_text(COMMENT_GATE, encoding="utf-8", newline="\n")
    return root


def _layout(tmp_path: Path, layout: str) -> Path:
    """A repository in one adoption state; returns the checkout the commit runs in."""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    (main / "README").write_text("x\n", encoding="utf-8")
    _git(main, "add", "README")
    _git(main, "commit", "-q", "-m", "base")
    checkout = main
    if layout.startswith("worktree"):
        checkout = tmp_path / "linked"
        _git(main, "worktree", "add", "-q", "-b", "side", str(checkout))
    if layout in ("folder", "committed"):
        (checkout / ".afk").mkdir()
    if layout == "committed":
        (checkout / ".afk" / "config.yaml").write_text("schema: 1\n", encoding="utf-8")
    if layout in ("personal", "worktree-personal"):
        shared = main / ".git" / "afk" / "config.yaml"
        shared.parent.mkdir(parents=True)
        shared.write_text("forge: none\n", encoding="utf-8")
    (checkout / "A.java").write_text("class A {}\n", encoding="utf-8")
    _git(checkout, "add", "A.java")
    return checkout


def _commit_gates(plugin: Path, tmp_path: Path, checkout: Path) -> list[str]:
    log = tmp_path / "gates.log"
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    environ = {**os.environ, "AFK_PROVIDER": "claude", "AFK_PLUGIN_ROOT": plugin.as_posix(),
               "AFK_WORKTREE_OP": "1", "GATE_LOG": log.as_posix(), "GATE_CACHE_DISABLE": "1",
               "GATE_METRICS_DISABLE": "1", "HOME": home.as_posix(), "USERPROFILE": str(home)}
    for name in ("CLAUDE_PLUGIN_ROOT", "AFK_SKIP_PRECOMMIT_GATES", "AFK_CONFIG", "CLAUDE_PROJECT_DIR"):
        environ.pop(name, None)
    done = subprocess.run([str(BASH), (plugin / "hooks" / "precommit-gates.sh").as_posix()],
                          cwd=str(checkout), env=environ, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout + done.stderr
    return log.read_text(encoding="utf-8").split() if log.exists() else []


@pytest.mark.parametrize("layout", ["personal", "folder"])
def test_the_configuration_test_runs_with_only_a_personal_file_or_only_the_folder(
        plugin, tmp_path, layout):
    assert "comment" in _commit_gates(plugin, tmp_path, _layout(tmp_path, layout))


def test_a_repository_that_never_adopted_the_plugin_skips_the_code_gates(plugin, tmp_path):
    assert _commit_gates(plugin, tmp_path, _layout(tmp_path, "none")) == []


@pytest.mark.parametrize("layout", ["none", "folder", "committed", "personal", "worktree",
                                    "worktree-personal"])
def test_the_shell_answer_matches_the_reader(plugin, tmp_path, layout):
    checkout = _layout(tmp_path, layout)
    reader = cfg.is_set_up(checkout) or (checkout / ".afk").is_dir()
    assert ("comment" in _commit_gates(plugin, tmp_path, checkout)) is reader
