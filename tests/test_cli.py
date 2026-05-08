"""Unit tests for afk_driver.cli helpers (subprocess args, marker parsing
end-to-end, etc.).

The runner-closure tests below exercise the production seam: a spawned
``claude --print`` session writes its combined stdout+stderr into a log file
the closure opens, and the ``/afk:execute`` skill is required to emit a final
``<<<AFK_OUTCOME>>>{json}<<<END>>>`` marker block before exiting. The closure
parses that marker as the source of truth — subprocess exit code is only a
fallback when no marker was emitted (then the closure reports
``other`` with ``no AFK_OUTCOME marker emitted (...)`` so the loss is
audible). See ``test_cli_outcome_parser.py`` for the parser unit tests.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from afk_driver.cli import _WorktreeAdapter, _make_claude_runner


def _emit_marker(stdout_file, status: str, detail: str = "", producer_key=None) -> None:
    """Helper: write an AFK_OUTCOME marker into the spawned session's log
    file the same way the real `claude` subprocess would (its stdout is
    redirected to that file by the closure)."""
    import json as _json
    payload = {"status": status, "detail": detail, "producer_key": producer_key}
    stdout_file.write("\n<<<AFK_OUTCOME>>>\n")
    stdout_file.write(_json.dumps(payload))
    stdout_file.write("\n<<<END>>>\n")
    stdout_file.flush()


def test_real_claude_runner_invokes_claude_non_interactively(monkeypatch, tmp_path):
    """Without --print, `claude /afk:execute X` opens an interactive REPL after the
    slash command runs — subprocess.run blocks until cap_s. The driver must
    invoke claude in non-interactive --print mode.

    Discovered during the P2P-1226 smoke run: afk:execute session emitted final
    success but the parent driver hung for the full 1-hour cap because the
    REPL stayed open."""
    captured: dict = {}

    def fake_run(args, **kw):
        captured["args"] = list(args)
        captured["kw"] = kw
        # Simulate the spawned skill emitting its outcome marker into the log
        # file the closure is teeing into. Without this the runner now
        # correctly reports ``other`` with "no marker emitted" — which is
        # the very failure mode the marker contract exists to surface.
        _emit_marker(kw["stdout"], "success", "all green")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("afk_driver.cli.subprocess.run", fake_run)
    runner = _make_claude_runner(tmp_path / "logs")
    out = runner("P2P-1230", tmp_path, 60)
    assert out.status == "success"
    assert out.detail == "all green"

    args = captured["args"]
    assert args[0] == "claude"
    assert "--print" in args, "must run non-interactively or subprocess.run hangs"
    assert "--dangerously-skip-permissions" in args, "AFK lane is autonomous; tools must not prompt"
    assert f"/afk:execute P2P-1230" in args, "slash command + arg must be a single prompt token"
    assert captured["kw"]["cwd"] == str(tmp_path)
    assert captured["kw"]["timeout"] == 60


def test_real_claude_runner_returns_timeout_on_subprocess_timeout(monkeypatch, tmp_path):
    """When the wall-clock cap fires before the skill emits a marker, the
    runner reports ``timeout`` — not ``other`` — so the runner's retry/abort
    logic and digest writer can route accordingly."""
    def fake_run(args, **kw):
        raise subprocess.TimeoutExpired(cmd=args, timeout=kw.get("timeout"))

    monkeypatch.setattr("afk_driver.cli.subprocess.run", fake_run)
    runner = _make_claude_runner(tmp_path / "logs")
    out = runner("P2P-1230", tmp_path, 30)
    assert out.status == "timeout"
    assert "30s" in out.detail


def test_real_claude_runner_marker_wins_over_timeout(monkeypatch, tmp_path):
    """If the skill *did* manage to emit a marker before the wall-clock cap
    killed the process (rare race but possible — e.g. a final test run took
    too long after Step 13's marker print already flushed), trust the
    marker. The skill's narrative outcome beats the timeout signal."""
    def fake_run(args, **kw):
        _emit_marker(kw["stdout"], "test_fail", "one failure, retry")
        raise subprocess.TimeoutExpired(cmd=args, timeout=kw.get("timeout"))

    monkeypatch.setattr("afk_driver.cli.subprocess.run", fake_run)
    runner = _make_claude_runner(tmp_path / "logs")
    out = runner("P2P-1230", tmp_path, 30)
    assert out.status == "test_fail"
    assert out.detail == "one failure, retry"


def test_real_claude_runner_returns_other_with_no_marker_when_exit_zero(monkeypatch, tmp_path):
    """Pre-marker, exit 0 was demoted to ``success`` — silently masking
    every structured failure status. Now exit 0 with no marker is reported
    as ``other`` so the loss is audible in the digest comment."""
    def fake_run(args, **kw):
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr("afk_driver.cli.subprocess.run", fake_run)
    runner = _make_claude_runner(tmp_path / "logs")
    out = runner("P2P-1230", tmp_path, 60)
    assert out.status == "other"
    assert "no AFK_OUTCOME marker emitted" in out.detail
    assert "no_marker" in out.detail
    assert "exit 0" in out.detail
    assert "log:" in out.detail


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
    assert "no AFK_OUTCOME marker emitted" in out.detail


def test_real_claude_runner_marker_wins_over_nonzero_exit(monkeypatch, tmp_path):
    """The skill's structured marker is the source of truth — if it emitted
    ``contract_mismatch`` and then claude itself exited nonzero (e.g. an
    internal hiccup after Step 13), trust the marker. Routing depends on
    this: ``contract_mismatch`` triggers dual-comment routing the producer
    needs to see, while ``other`` would just abort silently."""
    def fake_run(args, **kw):
        _emit_marker(
            kw["stdout"],
            "contract_mismatch",
            "P2P-1199 src/foo.py#FooBarRegistry missing",
            producer_key="P2P-1199",
        )
        return subprocess.CompletedProcess(
            args=args, returncode=2, stdout="", stderr=""
        )

    monkeypatch.setattr("afk_driver.cli.subprocess.run", fake_run)
    runner = _make_claude_runner(tmp_path / "logs")
    out = runner("P2P-1230", tmp_path, 60)
    assert out.status == "contract_mismatch"
    assert out.producer_key == "P2P-1199"
    assert "FooBarRegistry" in out.detail


def test_real_claude_runner_full_marker_round_trip_for_every_status(monkeypatch, tmp_path):
    """Lock the full structured-status surface end-to-end through the
    closure — if any of these regress, the runner's no-retry / dual-comment
    logic for that status is fictional in production."""
    statuses = [
        ("success", None),
        ("test_fail", None),
        ("build_fail", None),
        ("design_conflict", None),
        ("contract_mismatch", "P2P-9999"),
        ("produces_drift", None),
        ("other", None),
    ]
    for i, (status, producer_key) in enumerate(statuses):
        def make_fake(status=status, producer_key=producer_key):
            def fake_run(args, **kw):
                _emit_marker(kw["stdout"], status, f"detail-{status}", producer_key=producer_key)
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            return fake_run

        monkeypatch.setattr("afk_driver.cli.subprocess.run", make_fake())
        runner = _make_claude_runner(tmp_path / f"logs-{i}")
        out = runner(f"P2P-{2000 + i}", tmp_path, 60)
        assert out.status == status, f"status {status!r} did not round-trip"
        assert out.detail == f"detail-{status}"
        assert out.producer_key == producer_key


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
