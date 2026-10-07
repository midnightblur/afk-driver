"""`precommit-gates.sh` stops at the first block and runs cheap gates first."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_precommit", ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")

COMMENT_GATE = 'gate_comment() { printf "comment\\n" >> "$GATE_LOG"; return "${COMMENT_RC:-0}"; }\n'
MAVEN_GATES = """afk_bg_maven_discover() { printf 'maven-compile\\njava-format\\n'; }
afk_bg_maven_run() {
  printf '%s\\n' "$1" >> "$GATE_LOG"
  [ "$1" = "${BLOCK_GATE:-}" ] && return 2
  return 0
}
"""


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                          cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture(scope="module")
def plugin(tmp_path_factory):
    root = tmp_path_factory.mktemp("precommit") / "plugin"
    root.mkdir()
    for part in ("hooks", "scripts", "adapters"):
        shutil.copytree(ROOT / part, root / part, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (root / "hooks" / "comment-gate.sh").write_text(COMMENT_GATE, encoding="utf-8", newline="\n")
    (root / "adapters" / "build-gate" / "maven" / "gates.sh").write_text(MAVEN_GATES, encoding="utf-8",
                                                                         newline="\n")
    return root


def _run(plugin: Path, tmp_path: Path, **env: str):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / ".afk").mkdir()
    (repo / ".afk" / "config.yaml").write_text("schema: 1\nbuild-gates:\n  - maven\n", encoding="utf-8")
    (repo / "A.java").write_text("class A {}\n", encoding="utf-8")
    _git(repo, "add", "A.java")
    log = tmp_path / "gates.log"
    environ = {**os.environ, "AFK_PROVIDER": "claude", "AFK_PLUGIN_ROOT": plugin.as_posix(),
               "AFK_WORKTREE_OP": "1", "GATE_LOG": log.as_posix(), "GATE_CACHE_DISABLE": "1",
               "GATE_METRICS_DISABLE": "1", **env}
    for name in ("CLAUDE_PLUGIN_ROOT", "AFK_SKIP_PRECOMMIT_GATES"):
        environ.pop(name, None)
    done = subprocess.run([str(BASH), (plugin / "hooks" / "precommit-gates.sh").as_posix()], cwd=repo,
                          env=environ, capture_output=True, text=True, timeout=300)
    ran = log.read_text(encoding="utf-8").split() if log.exists() else []
    return done, ran


def test_a_comment_block_stops_before_any_build_gate(plugin, tmp_path):
    done, ran = _run(plugin, tmp_path, COMMENT_RC="2")
    assert done.returncode == 2, done.stderr
    assert ran == ["comment"], done.stderr


def test_a_cheap_build_gate_runs_before_compile_and_its_block_stops_the_run(plugin, tmp_path):
    done, ran = _run(plugin, tmp_path, BLOCK_GATE="java-format")
    assert done.returncode == 2, done.stderr
    assert ran == ["comment", "java-format"], done.stderr


def test_every_gate_runs_when_none_blocks(plugin, tmp_path):
    done, ran = _run(plugin, tmp_path)
    assert done.returncode == 0, done.stderr
    assert ran == ["comment", "java-format", "maven-compile"], done.stderr
