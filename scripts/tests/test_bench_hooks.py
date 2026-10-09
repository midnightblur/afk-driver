"""`hooks/tests/bench-hooks.py` picks the handlers the harness would run and reports per event."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "hooks" / "tests" / "bench-hooks.py"


def _bench():
    spec = importlib.util.spec_from_file_location("afk_bench_hooks", BENCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_handlers_follow_the_manifest_matchers():
    bench = _bench()
    manifest = {"hooks": {"PreToolUse": [
        {"matcher": "Bash|PowerShell", "hooks": [{"type": "command", "command": "x run-hook.py plugin shell-only.sh"}]},
        {"matcher": "*", "hooks": [{"type": "command", "command": "x protected-branch-guard.py"}]}]}}
    bash = [h["command"] for h in bench.handlers(manifest, "PreToolUse", "Bash")]
    read = [h["command"] for h in bench.handlers(manifest, "PreToolUse", "Read")]
    assert bash == ["x run-hook.py plugin shell-only.sh", "x protected-branch-guard.py"]
    assert read == ["x protected-branch-guard.py"]
    shipped = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert "protected-branch-guard.py" in [bench.label_of(h["command"])
                                           for h in bench.handlers(shipped, "PreToolUse", "Bash")]


@pytest.mark.parametrize("name", ["hooks.json", "hooks.codex.json"])
def test_every_manifest_command_has_a_scenario(name):
    bench = _bench()
    manifest = json.loads((ROOT / "hooks" / name).read_text(encoding="utf-8"))
    assert bench.uncovered(manifest) == []


def test_a_stray_command_is_reported_uncovered():
    bench = _bench()
    manifest = {"hooks": {"Notification": [{"hooks": [{"type": "command", "command": "python x.py"}]}]}}
    assert bench.uncovered(manifest) == ["Notification: python x.py"]


@pytest.mark.parametrize("name, provider, own, foreign", [
    ("hooks.json", "claude", "CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT"),
    ("hooks.codex.json", "codex", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"),
])
def test_the_environment_carries_only_the_selected_harness(monkeypatch, tmp_path, name, provider, own, foreign):
    bench = _bench()
    for var in ("AFK_PROVIDER", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "CLAUDECODE", "PROJECT_DIR", "CLAUDE_PID"):
        monkeypatch.setenv(var, "stale")
    env = bench.harness_env(name, tmp_path, tmp_path / "data")
    assert env["AFK_PROVIDER"] == provider and env[own] == str(bench.PLUGIN_ROOT)
    assert foreign not in env and "CLAUDE_PID" not in env
    assert ("CLAUDECODE" in env) == (provider == "claude")


def test_percentile_is_nearest_rank():
    bench = _bench()
    assert bench.percentile([5.0, 1.0, 3.0, 2.0, 4.0], 0.5) == 3.0
    assert bench.percentile([5.0, 1.0, 3.0, 2.0, 4.0], 0.95) == 5.0


def test_one_run_reports_the_event_and_each_handler(tmp_path):
    done = subprocess.run([sys.executable, str(BENCH), "--runs", "1", "--only", "read"], cwd=ROOT,
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    assert "read (PreToolUse)" in done.stdout and "protected-branch-guard.py" in done.stdout


def _worktrees() -> set[str]:
    listing = subprocess.run(["git", "-C", str(ROOT), "worktree", "list", "--porcelain"], capture_output=True,
                             text=True).stdout
    return {line for line in listing.splitlines() if line.startswith("worktree ")}


def test_worktree_lifecycle_runs_in_a_disposable_clone():
    before = _worktrees()
    done = subprocess.run([sys.executable, str(BENCH), "--runs", "1", "--only", "worktree-create", "worktree-remove"],
                          cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr
    assert "worktree-create (WorktreeCreate)" in done.stdout and "worktree-remove (WorktreeRemove)" in done.stdout
    rows = [line.split() for line in done.stdout.splitlines() if line.startswith("  plugin worktree-")]
    assert rows and all(row[-1] == "0" for row in rows), done.stdout
    assert not [w for w in _worktrees() - before if "bench-new-" in w or "bench-old-" in w]


def test_every_budget_names_a_handler_its_scenario_reaches():
    bench = _bench()
    table = bench.scenarios(Path("."), Path("."))
    for (name, scenario, label), ceiling in bench.BUDGET_MS.items():
        manifest = json.loads((ROOT / "hooks" / name).read_text(encoding="utf-8"))
        reached = [bench.label_of(h["command"])
                   for h in bench.handlers(manifest, table[scenario].event, table[scenario].subject)]
        assert label in reached, (name, scenario, label)
        assert ceiling > 0
