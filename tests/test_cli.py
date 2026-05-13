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


# ===========================================================================
# ST08 — backend dispatch + per-backend pre-flight + sweeper
# ===========================================================================
#
# These tests cover the SubTask 08 acceptance matrix:
#
# 1. main() resolves backend via backend_select.resolve BEFORE constructing
#    the Runner (SDD §8 row "cli (modified)").
# 2. --github-all-repos / --cwd-only flip [github] mode for the run.
# 3. GitHub pre-flight ordering: gh-auth -> mcp-list -> sub-issue REST ->
#    sweeper. Any failure halts before Runner construction.
# 4. MCP probe absence halts (SDD §10 NFRs row "claude mcp list probe time").
# 5. Sub-issue REST 4xx halts.
# 6. Sweeper invocation: calls list_stuck_subissues + revert_to_pending +
#    comment per stuck issue.
# 7. Sweeper warnings propagate into the digest as `## Sweeper warnings`
#    bullets (SDD §5 observability table row).
# 8. Multi-repo flag wiring: --github-all-repos sets repo_clone_manager on
#    the Runner and config.github.mode = "all-repos".
# 9. Mutually-exclusive flags rejected by argparse.

import subprocess as _subprocess
from dataclasses import dataclass as _dataclass
from pathlib import Path as _Path
from typing import Optional as _Optional

import pytest

from afk_driver import backend_select as _backend_select
from afk_driver.backend_select import Backend as _Backend, RepoCoords as _RepoCoords
from afk_driver.cli import (
    SweepWarning,
    _preflight_github,
    _render_digest_with_sweep,
    _run_sweeper,
    main as cli_main,
)
from afk_driver.runner import PreflightError, RunRecord
from afk_driver.tracker_protocol import SubIssueRef


# ---- Fakes -----------------------------------------------------------------


class _FakeTracker:
    """Minimal IssueTracker fake covering the pre-flight + sweeper surface.

    Records every method call so tests can assert ordering and arguments.
    Each method's return value is configurable via the constructor so a
    single fake covers happy + error paths.
    """

    def __init__(
        self,
        *,
        pickable: _Optional[list[SubIssueRef]] = None,
        stuck: _Optional[list[SubIssueRef]] = None,
        revert_raises: _Optional[Exception] = None,
        comment_raises: _Optional[Exception] = None,
        list_stuck_raises: _Optional[Exception] = None,
        list_pickable_raises: _Optional[Exception] = None,
    ) -> None:
        self._pickable = pickable or []
        self._stuck = stuck or []
        self._revert_raises = revert_raises
        self._comment_raises = comment_raises
        self._list_stuck_raises = list_stuck_raises
        self._list_pickable_raises = list_pickable_raises
        self.calls: list[tuple] = []

    def list_pickable(self) -> list[SubIssueRef]:
        self.calls.append(("list_pickable",))
        if self._list_pickable_raises:
            raise self._list_pickable_raises
        return list(self._pickable)

    def list_stuck_subissues(self) -> list[SubIssueRef]:
        self.calls.append(("list_stuck_subissues",))
        if self._list_stuck_raises:
            raise self._list_stuck_raises
        return list(self._stuck)

    def revert_to_pending(self, child_id: str) -> None:
        self.calls.append(("revert_to_pending", child_id))
        if self._revert_raises:
            raise self._revert_raises

    def comment(self, child_id: str, body: str) -> None:
        self.calls.append(("comment", child_id, body))
        if self._comment_raises:
            raise self._comment_raises


@_dataclass
class _ProbeScript:
    """Records every probe-runner invocation and replays a scripted response.

    The script is a list of (predicate, response) pairs; the first matching
    predicate wins. Each predicate is called with the argv list and returns
    True on match. ``response`` may be a ``CompletedProcess`` or an
    ``Exception`` instance (raised at call time).
    """

    pairs: list
    calls: list = None

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), dict(kwargs)))
        for predicate, response in self.pairs:
            if predicate(args):
                if isinstance(response, Exception):
                    raise response
                return response
        # Default: succeed silently. Most tests pass a complete script.
        return _subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")


def _ok(args, stdout="", stderr=""):
    return _subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr=stderr)


def _fail(args, stdout="", stderr="", code=1):
    return _subprocess.CompletedProcess(args=args, returncode=code, stdout=stdout, stderr=stderr)


# ---- _run_sweeper unit tests ----------------------------------------------


def test_run_sweeper_no_stuck_returns_empty_list():
    tracker = _FakeTracker(stuck=[])
    warnings = _run_sweeper(tracker)
    assert warnings == []
    assert tracker.calls == [("list_stuck_subissues",)]


def test_run_sweeper_resets_each_stuck_issue_and_comments():
    """ADR-0005 flowchart: for each stuck issue, revert_to_pending then
    post the canonical recovery comment. Verify-3x retry lives inside the
    tracker (ADR-0004) — the sweeper layer is presentation only."""
    stuck = [
        SubIssueRef(id="me/repo#1", parent_id=""),
        SubIssueRef(id="me/repo#2", parent_id=""),
    ]
    tracker = _FakeTracker(stuck=stuck)
    warnings = _run_sweeper(tracker)
    assert len(warnings) == 2
    assert all(w.action == "reset to afk:pending" for w in warnings)
    assert all(w.error == "" for w in warnings)
    # Ordering: list -> revert+comment per issue
    call_names = [c[0] for c in tracker.calls]
    assert call_names == [
        "list_stuck_subissues",
        "revert_to_pending", "comment",
        "revert_to_pending", "comment",
    ]
    # Comment body is the canonical ADR-0005 string
    comment_call = tracker.calls[2]
    assert "previous run did not complete" in comment_call[2]
    assert "afk:pending" in comment_call[2]


def test_run_sweeper_revert_failure_recorded_as_warning_continues_to_next():
    """Per-issue failures must not abort the sweeper — sibling issues still
    need their reset, and the digest gets the partial-failure record."""
    stuck = [
        SubIssueRef(id="me/repo#1", parent_id=""),
        SubIssueRef(id="me/repo#2", parent_id=""),
    ]
    fail_first = RuntimeError("verify-3x exhausted on #1")
    # Only first issue fails; we need a per-call switch. Build a tracker
    # whose revert raises only on the first call.
    class _PartialTracker(_FakeTracker):
        def __init__(self):
            super().__init__(stuck=stuck)
            self._revert_n = 0
        def revert_to_pending(self, child_id):
            self.calls.append(("revert_to_pending", child_id))
            self._revert_n += 1
            if self._revert_n == 1:
                raise fail_first
    tracker = _PartialTracker()
    warnings = _run_sweeper(tracker)
    assert len(warnings) == 2
    assert warnings[0].issue_id == "me/repo#1"
    assert "revert_to_pending failed" in warnings[0].action
    assert warnings[0].error == "verify-3x exhausted on #1"
    assert warnings[1].issue_id == "me/repo#2"
    assert warnings[1].error == ""
    # #2 still got comment'd after the revert succeeded
    assert ("comment", "me/repo#2",
            "AFK: previous run did not complete; reset to afk:pending for re-pickup",
            ) in tracker.calls


def test_run_sweeper_comment_failure_after_successful_reset_is_recorded():
    stuck = [SubIssueRef(id="me/repo#5", parent_id="")]
    tracker = _FakeTracker(stuck=stuck, comment_raises=RuntimeError("comment 500"))
    warnings = _run_sweeper(tracker)
    assert len(warnings) == 1
    assert "comment post failed" in warnings[0].action
    assert warnings[0].error == "comment 500"


def test_run_sweeper_list_stuck_failure_raises_preflight_error():
    """Tracker-unreachable failure is fatal — propagate as PreflightError so
    the cli halts before runner construction."""
    tracker = _FakeTracker(list_stuck_raises=RuntimeError("gh search 500"))
    with pytest.raises(PreflightError) as exc:
        _run_sweeper(tracker)
    assert "list_stuck_subissues failed" in str(exc.value)


# ---- _preflight_github ordering + halt-on-failure tests --------------------


def _is_gh_auth(args): return args[:3] == ["gh", "auth", "status"]
def _is_mcp_list(args): return args[:3] == ["claude", "mcp", "list"]
def _is_gh_api_subissues(args): return args[:3] == ["gh", "api", "-i"]


def test_preflight_github_runs_steps_in_order_gh_auth_then_mcp_then_rest_then_sweep():
    """Pin the ordering required by SDD §7 use-case 1 sequenceDiagram and
    ADR-0005 flowchart."""
    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _ok([])),
        (_is_mcp_list, _ok([], stdout="github\nfoo\n")),
        (_is_gh_api_subissues, _ok([], stdout="HTTP/2 200\n[]\n")),
    ])
    tracker = _FakeTracker(
        pickable=[SubIssueRef(id="me/repo#7", parent_id="")],
        stuck=[],
    )
    config = _make_config()
    warnings = _preflight_github(tracker, config, probe_runner=probe)
    assert warnings == []
    # Subprocess calls happen in this exact order:
    call_argvs = [c[0] for c in probe.calls]
    assert call_argvs[0][:3] == ["gh", "auth", "status"]
    assert call_argvs[1][:3] == ["claude", "mcp", "list"]
    assert call_argvs[2][:3] == ["gh", "api", "-i"]
    # Tracker calls: list_pickable (for REST probe), then list_stuck_subissues
    tracker_call_names = [c[0] for c in tracker.calls]
    assert tracker_call_names == ["list_pickable", "list_stuck_subissues"]


def test_preflight_github_gh_auth_failure_halts_before_mcp_probe():
    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _fail([], stderr="not logged in")),
        # If mcp_list ever gets called we want to see it in the probe log.
    ])
    tracker = _FakeTracker(pickable=[], stuck=[])
    with pytest.raises(PreflightError) as exc:
        _preflight_github(tracker, _make_config(), probe_runner=probe)
    assert "gh auth status failed" in str(exc.value)
    # MCP probe never ran
    assert all(c[0][:3] != ["claude", "mcp", "list"] for c in probe.calls)
    # Tracker never queried
    assert tracker.calls == []


def test_preflight_github_mcp_list_missing_github_substring_halts():
    """SDD §10 NFRs: `claude mcp list | grep github`. Absent -> halt with
    diagnostic; sub-issue REST probe never runs."""
    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _ok([])),
        (_is_mcp_list, _ok([], stdout="nakisa-jira\nlean-ctx\n")),
    ])
    tracker = _FakeTracker(pickable=[], stuck=[])
    with pytest.raises(PreflightError) as exc:
        _preflight_github(tracker, _make_config(), probe_runner=probe)
    assert "github" in str(exc.value).lower()
    assert "mcp list" in str(exc.value).lower()
    # REST probe and tracker never reached
    assert not any(_is_gh_api_subissues(c[0]) for c in probe.calls)
    assert tracker.calls == []


def test_preflight_github_mcp_list_timeout_halts():
    """Per SDD §10 the MCP probe budget is 2 s; timeout -> halt with
    diagnostic. Simulated by raising TimeoutExpired."""
    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _ok([])),
        (_is_mcp_list, _subprocess.TimeoutExpired(cmd=["claude", "mcp", "list"], timeout=2.0)),
    ])
    tracker = _FakeTracker(pickable=[], stuck=[])
    with pytest.raises(PreflightError) as exc:
        _preflight_github(tracker, _make_config(), probe_runner=probe)
    assert "timed out" in str(exc.value)
    assert "mcp" in str(exc.value).lower()


def test_preflight_github_sub_issue_rest_non_200_halts():
    """REST probe must return 200; 404 (sub-issue API not enabled for this
    repo/token) halts pre-flight, so the runner never starts a doomed run."""
    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _ok([])),
        (_is_mcp_list, _ok([], stdout="github\n")),
        (_is_gh_api_subissues, _ok([], stdout="HTTP/2 404\n{}\n")),
    ])
    tracker = _FakeTracker(
        pickable=[SubIssueRef(id="me/repo#7", parent_id="")],
        stuck=[],
    )
    with pytest.raises(PreflightError) as exc:
        _preflight_github(tracker, _make_config(), probe_runner=probe)
    assert "404" in str(exc.value)
    # Sweeper never invoked
    assert "list_stuck_subissues" not in [c[0] for c in tracker.calls]


def test_preflight_github_sub_issue_rest_subprocess_nonzero_halts():
    """gh api itself exits non-zero (e.g. token lacks scope)."""
    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _ok([])),
        (_is_mcp_list, _ok([], stdout="github\n")),
        (_is_gh_api_subissues, _fail([], stderr="HTTP 401: Bad credentials")),
    ])
    tracker = _FakeTracker(
        pickable=[SubIssueRef(id="me/repo#7", parent_id="")],
        stuck=[],
    )
    with pytest.raises(PreflightError) as exc:
        _preflight_github(tracker, _make_config(), probe_runner=probe)
    assert "Bad credentials" in str(exc.value) or "401" in str(exc.value)


def test_preflight_github_skips_rest_probe_when_queue_empty():
    """Empty queue = nothing to probe against; pre-flight passes through to
    sweeper. SDD §10 budget allows this."""
    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _ok([])),
        (_is_mcp_list, _ok([], stdout="github\n")),
        # No gh api -i pair — if it's called, the default-_ok kicks in,
        # but we assert below it was NEVER called.
    ])
    tracker = _FakeTracker(pickable=[], stuck=[])
    _preflight_github(tracker, _make_config(), probe_runner=probe)
    assert not any(_is_gh_api_subissues(c[0]) for c in probe.calls)
    # Sweeper still ran
    assert "list_stuck_subissues" in [c[0] for c in tracker.calls]


def test_preflight_github_sweeper_warnings_propagate():
    """Sweeper warnings returned from _preflight_github so main() can fold
    them into the morning digest's `## Sweeper warnings` section."""
    stuck = [SubIssueRef(id="me/repo#9", parent_id="")]
    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _ok([])),
        (_is_mcp_list, _ok([], stdout="github\n")),
    ])
    tracker = _FakeTracker(pickable=[], stuck=stuck)
    warnings = _preflight_github(tracker, _make_config(), probe_runner=probe)
    assert len(warnings) == 1
    assert warnings[0].issue_id == "me/repo#9"


# ---- Digest rendering ------------------------------------------------------


def test_render_digest_with_sweep_no_warnings_passthrough():
    record = RunRecord(started_iso="t0", ended_iso="t1")
    out = _render_digest_with_sweep(record, [])
    assert "Sweeper warnings" not in out


def test_render_digest_with_sweep_renders_section_at_top():
    record = RunRecord(started_iso="t0", ended_iso="t1")
    warnings = [
        SweepWarning(issue_id="me/repo#1", action="reset to afk:pending"),
        SweepWarning(
            issue_id="me/repo#2",
            action="reset to afk:pending (comment post failed)",
            error="gh api 500",
        ),
    ]
    out = _render_digest_with_sweep(record, warnings)
    # Section appears before the standard digest header
    assert out.startswith("## Sweeper warnings")
    assert "me/repo#1" in out
    assert "me/repo#2" in out
    assert "gh api 500" in out
    # Body still present
    assert "# AFK morning digest" in out


# ---- main() backend dispatch wiring ---------------------------------------


def _make_config():
    """Minimal config for unit tests — avoids hitting the user's real TOML."""
    from afk_driver.config import defaults
    return defaults()


def _make_resolver(backend: _Backend):
    """Build a backend_resolver kwarg that returns ``backend`` for any cwd."""
    def _resolve(_cwd, _cfg, **_kw):
        return backend
    return _resolve


def test_main_resolves_backend_before_constructing_runner(monkeypatch, tmp_path):
    """SDD §8 row 'cli (modified)': main(argv) must call backend_select.resolve
    BEFORE Runner construction. We catch this by injecting a resolver that
    raises BackendResolutionError; main must exit 2 without touching JiraClient
    / GitHubIssuesClient construction."""
    constructed: list[str] = []

    def boom_resolve(cwd, cfg, **kw):
        constructed.append("resolve-called")
        raise _backend_select.BackendResolutionError("no origin remote")

    # Make JiraClient construction crash so we'd notice if it ran
    def boom_jira(*a, **kw):
        constructed.append("jira-constructed")
        raise AssertionError("Jira constructed before backend resolved")

    monkeypatch.setattr("afk_driver.cli.JiraClient", boom_jira)
    rc = cli_main(
        ["--repo-root", str(tmp_path)],
        backend_resolver=boom_resolve,
    )
    assert rc == 2
    assert constructed == ["resolve-called"]


def test_main_github_backend_runs_full_preflight_then_constructs_runner(
    monkeypatch, tmp_path,
):
    """End-to-end: GitHub backend resolved -> pre-flight runs (auth, mcp, rest,
    sweeper) -> Runner constructed with tracker, scm, repo_clone_manager."""
    tracker = _FakeTracker(
        pickable=[SubIssueRef(id="me/repo#7", parent_id="")],
        stuck=[],
    )
    scm = object()  # opaque — we just verify it's threaded through
    backend = _Backend(
        tracker=tracker,
        scm=scm,
        repo_coords=_RepoCoords(backend="github", host="github.com"),
    )
    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _ok([])),
        (_is_mcp_list, _ok([], stdout="github\n")),
        (_is_gh_api_subissues, _ok([], stdout="HTTP/2 200\n[]\n")),
    ])

    runner_kwargs: dict = {}

    class _FakeRunner:
        def __init__(self, **kw):
            runner_kwargs.update(kw)
        def one_pass(self):
            return RunRecord(started_iso="t0", ended_iso="t1")

    monkeypatch.setattr("afk_driver.cli.Runner", _FakeRunner)

    rc = cli_main(
        ["--repo-root", str(tmp_path)],
        backend_resolver=_make_resolver(backend),
        probe_runner=probe,
        claude_runner_factory=lambda _root: (lambda *a, **kw: None),
    )
    assert rc == 0
    # Runner got the resolver's tracker + scm
    assert runner_kwargs["tracker"] is tracker
    assert runner_kwargs["scm"] is scm
    # And the multi-repo primitive is wired so the runner can fan out when
    # config.github.mode == "all-repos" (current run is "cwd" by default —
    # presence of repo_clone_manager is what matters)
    from afk_driver import repo_clone_manager
    assert runner_kwargs["repo_clone_manager"] is repo_clone_manager.ensure_clone
    assert runner_kwargs["repo_coords"].backend == "github"


def test_main_github_preflight_failure_returns_2_without_constructing_runner(
    monkeypatch, tmp_path,
):
    """Halt-on-failure: gh auth missing -> exit 2, Runner never built."""
    tracker = _FakeTracker(pickable=[], stuck=[])
    backend = _Backend(
        tracker=tracker, scm=object(),
        repo_coords=_RepoCoords(backend="github", host="github.com"),
    )
    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _fail([], stderr="You are not logged into GitHub")),
    ])

    def boom_runner(**kw):
        raise AssertionError("Runner constructed despite pre-flight halt")

    monkeypatch.setattr("afk_driver.cli.Runner", boom_runner)
    rc = cli_main(
        ["--repo-root", str(tmp_path)],
        backend_resolver=_make_resolver(backend),
        probe_runner=probe,
        claude_runner_factory=lambda _root: (lambda *a, **kw: None),
    )
    assert rc == 2


def test_main_github_all_repos_flag_sets_mode_for_run(monkeypatch, tmp_path):
    """--github-all-repos must flip config.github.mode to 'all-repos' before
    backend_select runs (so the resolver short-circuits cwd inspection per
    ADR-0003)."""
    seen_modes: list[str] = []

    def capture_resolve(cwd, cfg, **kw):
        seen_modes.append(cfg.github.mode)
        return _Backend(
            tracker=_FakeTracker(pickable=[], stuck=[]),
            scm=object(),
            repo_coords=_RepoCoords(backend="github", host="github.com"),
        )

    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _ok([])),
        (_is_mcp_list, _ok([], stdout="github\n")),
    ])

    class _FakeRunner:
        def __init__(self, **kw): pass
        def one_pass(self): return RunRecord(started_iso="t0", ended_iso="t1")
    monkeypatch.setattr("afk_driver.cli.Runner", _FakeRunner)

    rc = cli_main(
        ["--repo-root", str(tmp_path), "--github-all-repos"],
        backend_resolver=capture_resolve,
        probe_runner=probe,
        claude_runner_factory=lambda _root: (lambda *a, **kw: None),
    )
    assert rc == 0
    assert seen_modes == ["all-repos"]


def test_main_cwd_only_flag_sets_mode_for_run(monkeypatch, tmp_path):
    """--cwd-only must flip config.github.mode to 'cwd' (overrides any TOML
    default of 'all-repos' for a single invocation)."""
    seen_modes: list[str] = []

    def capture_resolve(cwd, cfg, **kw):
        seen_modes.append(cfg.github.mode)
        return _Backend(
            tracker=_FakeTracker(pickable=[], stuck=[]),
            scm=object(),
            repo_coords=_RepoCoords(backend="github", host="github.com"),
        )

    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _ok([])),
        (_is_mcp_list, _ok([], stdout="github\n")),
    ])

    class _FakeRunner:
        def __init__(self, **kw): pass
        def one_pass(self): return RunRecord(started_iso="t0", ended_iso="t1")
    monkeypatch.setattr("afk_driver.cli.Runner", _FakeRunner)

    rc = cli_main(
        ["--repo-root", str(tmp_path), "--cwd-only"],
        backend_resolver=capture_resolve,
        probe_runner=probe,
        claude_runner_factory=lambda _root: (lambda *a, **kw: None),
    )
    assert rc == 0
    assert seen_modes == ["cwd"]


def test_main_mode_flags_are_mutually_exclusive():
    """argparse must reject --github-all-repos + --cwd-only together."""
    with pytest.raises(SystemExit):
        cli_main(["--github-all-repos", "--cwd-only"])


def test_main_sweeper_warnings_flow_into_digest_output(
    monkeypatch, tmp_path, capsys,
):
    """End-to-end: sweeper finds stuck issues -> warnings appear in the
    printed digest's `## Sweeper warnings` section."""
    stuck = [SubIssueRef(id="me/repo#42", parent_id="")]
    tracker = _FakeTracker(pickable=[], stuck=stuck)
    backend = _Backend(
        tracker=tracker, scm=object(),
        repo_coords=_RepoCoords(backend="github", host="github.com"),
    )
    probe = _ProbeScript(pairs=[
        (_is_gh_auth, _ok([])),
        (_is_mcp_list, _ok([], stdout="github\n")),
    ])

    class _FakeRunner:
        def __init__(self, **kw): pass
        def one_pass(self): return RunRecord(started_iso="t0", ended_iso="t1")
    monkeypatch.setattr("afk_driver.cli.Runner", _FakeRunner)

    rc = cli_main(
        ["--repo-root", str(tmp_path)],
        backend_resolver=_make_resolver(backend),
        probe_runner=probe,
        claude_runner_factory=lambda _root: (lambda *a, **kw: None),
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Sweeper warnings" in out
    assert "me/repo#42" in out
    assert "reset to afk:pending" in out


def test_main_jira_backend_path_runs_existing_preflight_unchanged(
    monkeypatch, tmp_path,
):
    """Jira branch must keep its existing pre-flight (tool presence +
    JIRA_API_TOKEN / JIRA_EMAIL / JIRA_BASE_URL env vars). We assert that
    when those env vars are missing, main exits 2 with the legacy message."""
    backend = _Backend(
        tracker=None,
        scm=object(),
        repo_coords=_RepoCoords(backend="jira", host="gitlab.example.com"),
    )
    # Make the pre-flight tool check pass — focus on the env-var check.
    monkeypatch.setattr(
        "afk_driver.cli.preflight",
        lambda *a, **kw: None,
    )

    rc = cli_main(
        [
            "--repo-root", str(tmp_path),
            "--jira-base", "",  # explicitly clear
            "--jira-email", "",
            "--jira-token", "",
        ],
        backend_resolver=_make_resolver(backend),
        claude_runner_factory=lambda _root: (lambda *a, **kw: None),
    )
    assert rc == 2
