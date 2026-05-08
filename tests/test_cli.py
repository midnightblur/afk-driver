"""Unit tests for afk_driver.cli helpers (subprocess args, etc.)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from afk_driver.cli import _WorktreeAdapter, _make_claude_runner


def test_real_claude_runner_invokes_claude_non_interactively(monkeypatch, tmp_path):
    """Without --print, `claude /afk-go X` opens an interactive REPL after the
    slash command runs — subprocess.run blocks until cap_s. The driver must
    invoke claude in non-interactive --print mode.

    Discovered during the P2P-1226 smoke run: afk-go session emitted final
    success but the parent driver hung for the full 1-hour cap because the
    REPL stayed open."""
    captured: dict = {}

    def fake_run(args, **kw):
        captured["args"] = list(args)
        captured["kw"] = kw
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("afk_driver.cli.subprocess.run", fake_run)
    runner = _make_claude_runner(tmp_path / "logs")
    out = runner("P2P-1230", tmp_path, 60)
    assert out.status == "success"

    args = captured["args"]
    assert args[0] == "claude"
    assert "--print" in args, "must run non-interactively or subprocess.run hangs"
    assert "--dangerously-skip-permissions" in args, "AFK lane is autonomous; tools must not prompt"
    assert f"/afk-go P2P-1230" in args, "slash command + arg must be a single prompt token"
    assert captured["kw"]["cwd"] == str(tmp_path)
    assert captured["kw"]["timeout"] == 60


def test_real_claude_runner_returns_timeout_on_subprocess_timeout(monkeypatch, tmp_path):
    def fake_run(args, **kw):
        raise subprocess.TimeoutExpired(cmd=args, timeout=kw.get("timeout"))

    monkeypatch.setattr("afk_driver.cli.subprocess.run", fake_run)
    runner = _make_claude_runner(tmp_path / "logs")
    out = runner("P2P-1230", tmp_path, 30)
    assert out.status == "timeout"
    assert "30s" in out.detail


def test_real_claude_runner_returns_other_on_nonzero_exit(monkeypatch, tmp_path):
    def fake_run(args, **kw):
        return subprocess.CompletedProcess(
            args=args, returncode=2, stdout="", stderr=""
        )

    monkeypatch.setattr("afk_driver.cli.subprocess.run", fake_run)
    runner = _make_claude_runner(tmp_path / "logs")
    out = runner("P2P-1230", tmp_path, 60)
    assert out.status == "other"
    # New runner tees combined output to a per-SubTask log file rather than
    # capturing stdout into ClaudeOutcome.detail; detail now points at the log.
    assert "log:" in out.detail
    assert "exit 2" in out.detail


def test_worktree_adapter_exposes_every_method_runner_calls():
    """Runtime AttributeError caught in P2P-1218 smoke: runner.py calls
    self.worktrees.reset_to_clean(spec) but the cli adapter forgot to
    expose it. Lock the full surface so a missing method fails at unit
    time, not after the AFK driver has already opened a Draft MR and
    transitioned the parent."""
    required = {
        "ensure", "publish_branch", "rebase_onto_target", "validate_state",
        "commit_dirty_changes", "head_sha", "push_branch", "reset_to_clean",
    }
    adapter = _WorktreeAdapter()
    missing = [name for name in required if not hasattr(adapter, name)]
    assert not missing, f"_WorktreeAdapter missing: {missing}"
