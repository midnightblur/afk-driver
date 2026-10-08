"""`precommit-gates.sh` stops at the first block and runs cheap gates first."""
from __future__ import annotations

import importlib.util
import json
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
PLUGIN_SOURCE = 'printf "plugin-source %s\\n" "$*" >> "$GATE_LOG"; exit "${PSG_RC:-0}"\n'
REPO_RUNNER = 'printf "repo-runner\\n" >> "$GATE_LOG"; exit 0\n'


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
    (root / "hooks" / "plugin-source-gates.sh").write_text(PLUGIN_SOURCE, encoding="utf-8", newline="\n")
    return root


def _run(plugin: Path, tmp_path: Path, plugin_repo: bool = False, delete_only: bool = False,
         handlers: list[dict] | None = None, **env: str):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    _git(repo, "init", "-q")
    (repo / ".afk").mkdir()
    (repo / ".afk" / "config.yaml").write_text("schema: 1\nbuild-gates:\n  - maven\n", encoding="utf-8")
    if plugin_repo:
        (repo / ".claude-plugin").mkdir()
        (repo / ".claude-plugin" / "plugin.json").write_text('{"name": "afk"}\n', encoding="utf-8")
        (repo / "hooks").mkdir()
        (repo / "hooks" / "plugin-source-gates.sh").write_text(REPO_RUNNER, encoding="utf-8", newline="\n")
        _git(repo, "add", ".claude-plugin", "hooks")
    if handlers is not None:
        for entry in handlers:
            if "body" in entry:
                (repo / entry["script"]).write_text(entry.pop("body"), encoding="utf-8", newline="\n")
        (repo / ".afk" / "hooks.json").write_text(json.dumps(handlers), encoding="utf-8")
    (repo / "A.java").write_text("class A {}\n", encoding="utf-8")
    _git(repo, "add", "A.java")
    if delete_only:
        _git(repo, "commit", "-q", "-m", "base")
        _git(repo, "rm", "-q", "A.java")
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


def test_a_consuming_repository_never_runs_the_plugin_source_gates(plugin, tmp_path):
    done, ran = _run(plugin, tmp_path)
    assert "plugin-source" not in ran, done.stderr


def test_the_plugin_repository_is_judged_by_the_installed_runner_never_its_own(plugin, tmp_path):
    done, ran = _run(plugin, tmp_path, plugin_repo=True)
    assert done.returncode == 0, done.stderr
    assert ran == ["comment", "plugin-source", "--staged", "java-format", "maven-compile"], done.stderr


def test_the_plugin_repository_blocks_when_the_installed_runner_is_missing(plugin, tmp_path):
    bare = tmp_path / "plugin-without-runner"
    shutil.copytree(plugin, bare)
    (bare / "hooks" / "plugin-source-gates.sh").unlink()
    done, ran = _run(bare, tmp_path, plugin_repo=True)
    assert done.returncode == 2, done.stderr
    assert "repo-runner" not in ran and "java-format" not in ran, done.stderr


@pytest.mark.parametrize("rc", ["2", "1"])
def test_a_plugin_source_block_or_crash_blocks_the_commit(plugin, tmp_path, rc):
    done, ran = _run(plugin, tmp_path, plugin_repo=True, PSG_RC=rc)
    assert done.returncode == 2, done.stderr
    assert ran == ["comment", "plugin-source", "--staged"], done.stderr


def test_a_deletion_only_commit_still_reaches_the_plugin_source_gates(plugin, tmp_path):
    done, ran = _run(plugin, tmp_path, plugin_repo=True, delete_only=True)
    assert done.returncode == 0, done.stderr
    assert "plugin-source" in ran, done.stderr


def _handler(name: str, body: str = "", matcher: str = "*") -> dict:
    return {"event": "PreCommit", "matcher": matcher, "timeout": 60, "script": f"{name}.sh",
            "body": f'printf "{name}\\n" >> "$GATE_LOG"\n{body}exit "${{{name.upper()}_RC:-0}}"\n'}


def test_repository_precommit_handlers_run_last_in_declaration_order(plugin, tmp_path):
    done, ran = _run(plugin, tmp_path, handlers=[_handler("cheap"), _handler("costly")])
    assert done.returncode == 0, done.stderr
    assert ran == ["comment", "java-format", "maven-compile", "cheap", "costly"], done.stderr


@pytest.mark.parametrize("rc", ["2", "1"])
def test_the_first_refusing_handler_ends_the_run(plugin, tmp_path, rc):
    done, ran = _run(plugin, tmp_path, handlers=[_handler("cheap"), _handler("costly")], CHEAP_RC=rc)
    assert done.returncode == 2, done.stderr
    assert ran[-1] == "cheap", done.stderr
    assert "cheap.sh exited" in done.stderr


def test_a_build_gate_block_stops_before_any_handler(plugin, tmp_path):
    done, ran = _run(plugin, tmp_path, handlers=[_handler("cheap")], BLOCK_GATE="maven-compile")
    assert done.returncode == 2, done.stderr
    assert "cheap" not in ran, done.stderr


@pytest.mark.parametrize("broken", ["missing", "matcher"])
def test_a_handler_the_checkout_cannot_run_blocks(plugin, tmp_path, broken):
    if broken == "missing":
        handlers = [_handler("cheap"), {"event": "PreCommit", "matcher": "*", "timeout": 60, "script": "gone.sh"}]
    else:
        handlers = [_handler("cheap", matcher="Bash")]
    done, ran = _run(plugin, tmp_path, handlers=handlers)
    assert done.returncode == 2, done.stderr
    assert "PreCommit handler refused" in done.stderr


def test_the_gate_disabled_sentinel_skips_every_handler(plugin, tmp_path):
    (tmp_path / "repo" / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / "repo" / ".claude" / "hooks" / ".gate-disabled").write_text("reason\n", encoding="utf-8")
    done, ran = _run(plugin, tmp_path, handlers=[_handler("cheap", body="exit 2\n")])
    assert done.returncode == 0, done.stderr
    assert ran == [], done.stderr


def test_a_handler_reads_the_staged_tree_and_paths_and_each_run_is_metered(plugin, tmp_path):
    body = ('[ "$AFK_STAGED_TREE" = "$(git write-tree)" ] || exit 3\n'
            'grep -qx A.java "$AFK_STAGED_PATHS" || exit 4\n')
    metrics = tmp_path / "metrics.jsonl"
    done, ran = _run(plugin, tmp_path, handlers=[_handler("cheap", body=body), _handler("costly")],
                     GATE_METRICS_DISABLE="0", GATE_METRICS_FILE=metrics.as_posix())
    assert done.returncode == 0, done.stderr
    lines = [json.loads(line) for line in metrics.read_text(encoding="utf-8").splitlines()]
    handled = [(line["gate"], line["result"]) for line in lines if line.get("event") == "PreCommit"]
    assert handled == [("cheap.sh", "pass"), ("costly.sh", "pass")]
