"""``python -m afk_driver`` CLI: one drain pass and exit.

Composition root for the AFK driver. ST08 moved backend dispatch into this
module: ``main(argv)`` calls :func:`backend_select.resolve` BEFORE constructing
the :class:`Runner`, then runs per-backend pre-flight (Jira keeps the existing
env-var + tooling probes; GitHub adds ``gh auth status`` + ``claude mcp list``
+ a sub-issue REST round-trip + the crash-recovery sweeper from ADR-0005).

Pre-flight is fail-fast (SDD §7 use-case 1): ANY non-zero step raises
:class:`PreflightError` and we return ``2`` without ever instantiating the
runner. The sweeper produces :class:`SweepWarning` records that propagate
through ``one_pass`` into the morning digest (rendered by ST09 as a
``## Sweeper warnings`` section).

Wires the real clients (UrllibTransport for Jira, default subprocess for glab,
real worktree_manager) into a Runner, executes one pass, writes the digest.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from typing import Callable, Optional, Sequence, Union

from afk_driver import backend_select, repo_clone_manager, worktree_manager
from afk_driver.config import DriverConfig, GithubConfig, load
from afk_driver.digest_writer import format_digest
from afk_driver.github_issues_client import GitHubIssuesClient
from afk_driver.gitlab_client import GitLabClient, default_runner
from afk_driver.jira_client import HttpTransport, JiraClient, JiraConfig, UrllibTransport
from afk_driver.runner import (
    ClaudeOutcome,
    PreflightError,
    Runner,
    preflight,
)


# ---------------------------------------------------------------------------
# Sweeper warning record (ST08)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SweepWarning:
    """One sub-issue reset by the pre-flight sweeper.

    Returned from :func:`_run_sweeper` so ST09's digest writer can render
    a ``## Sweeper warnings`` bullet per record at the top of the morning
    digest (SDD §5 observability table row "Sweeper warning bullets in
    digest" + SDD §7 use-case 3 sequenceDiagram).

    Fields:

    * ``issue_id`` — the canonical sub-issue ref (e.g.
      ``"owner/repo#42"`` on GitHub, ``"P2P-1234"`` on Jira).
    * ``action`` — short human string describing what the sweeper did
      (``"reset to afk:pending"``, ``"comment failed: ..."``, etc.).
    * ``error`` — set when the per-issue reset OR comment raised; empty
      string on the happy path. The sweeper never aborts the whole
      pre-flight on a single per-issue failure (other issues may still
      reset cleanly); the field lets the digest highlight the partial
      failure.
    """

    issue_id: str
    action: str
    error: str = ""


# ---------------------------------------------------------------------------
# Pre-flight defaults (SDD §10 NFRs)
# ---------------------------------------------------------------------------

# SDD §10 NFRs row "`claude mcp list` probe time (s) | < 2".
_MCP_PROBE_TIMEOUT_S: float = 2.0
# SDD §10 NFRs row "Pre-flight total time (s) | < 5". Used by the gh auth /
# REST probes; the sweeper has its own slack budget (NFRs row
# "Sweeper time for ≤ 50 stuck issues (s) | < 10").
_GH_PROBE_TIMEOUT_S: float = 10.0


# Seam between the spawned `claude --print "/afk:execute SUBKEY"` session and
# the runner. The skill is required to emit one of these blocks as the LAST
# thing in its output (see the afk plugin's `skills/execute/SKILL.md` Step 13,
# shipped in this repo at `.claude-plugin/` + `skills/`). The substring
# between markers must be valid JSON: {"status": ..., "detail": ...,
# "producer_key": ... | null}. We regex-scan for the LAST occurrence so a
# session that retried internally and re-emitted wins. Without this, the
# runner only sees subprocess exit codes — and `claude --print` exits 0 on
# clean termination regardless of narrative outcome, collapsing every
# structured status (test_fail, contract_mismatch, design_conflict,
# produces_drift) into "success". The whole no-retry / dual-comment routing
# story for cited-mode contracts depends on this marker propagating.
_OUTCOME_MARKER_RE = re.compile(
    r"<<<AFK_OUTCOME>>>\s*(?P<json>\{.*?\})\s*<<<END>>>",
    re.DOTALL,
)
_VALID_OUTCOME_STATUSES = frozenset({
    "success",
    "test_fail",
    "build_fail",
    "timeout",
    "design_conflict",
    "contract_mismatch",
    "produces_drift",
    "other",
})


class _WorktreeAdapter:
    """Adapts the module-level worktree_manager functions into the object shape Runner expects."""

    @staticmethod
    def ensure(spec):
        return worktree_manager.ensure(spec)

    @staticmethod
    def publish_branch(spec):
        return worktree_manager.publish_branch(spec)

    @staticmethod
    def rebase_onto_target(spec):
        return worktree_manager.rebase_onto_target(spec)

    @staticmethod
    def validate_state(spec):
        return worktree_manager.validate_state(spec)

    @staticmethod
    def commit_dirty_changes(spec, message):
        return worktree_manager.commit_dirty_changes(spec, message)

    @staticmethod
    def head_sha(spec):
        return worktree_manager.head_sha(spec)

    @staticmethod
    def push_branch(spec):
        return worktree_manager.push_branch(spec)

    @staticmethod
    def reset_to_clean(spec):
        return worktree_manager.reset_to_clean(spec)

    @staticmethod
    def find_worktree_for_branch(repo_root, branch):
        return worktree_manager.find_worktree_for_branch(repo_root, branch)


def _parse_outcome_marker(log_path: Path) -> Union[ClaudeOutcome, str]:
    """Scan a spawned-claude log for the last AFK_OUTCOME marker and parse it.

    Returns a fully-populated ``ClaudeOutcome`` when the marker is present,
    well-formed JSON, and carries a known status. Otherwise returns a short
    reason string the caller maps into the runner-visible detail text:

      - ``"log_unreadable"`` — the log file does not exist or cannot be read
      - ``"no_marker"`` — the file is readable but has no marker
      - ``"marker_malformed_json"`` — last marker's payload is not valid JSON
      - ``"marker_unknown_status:<status>"`` — JSON parses but status is
        outside the ``ClaudeStatus`` literal set

    The string-vs-outcome split lets the caller surface *why* a fallback
    happened in the digest comment, instead of a silent demotion to
    ``other``.
    """
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "log_unreadable"

    matches = list(_OUTCOME_MARKER_RE.finditer(text))
    if not matches:
        return "no_marker"

    last_payload = matches[-1].group("json")
    try:
        payload = json.loads(last_payload)
    except json.JSONDecodeError:
        return "marker_malformed_json"

    if not isinstance(payload, dict):
        return "marker_malformed_json"

    status = payload.get("status")
    if status not in _VALID_OUTCOME_STATUSES:
        return f"marker_unknown_status:{status!r}"

    detail = payload.get("detail", "")
    if not isinstance(detail, str):
        detail = str(detail)

    producer_key = payload.get("producer_key")
    if producer_key is not None and not isinstance(producer_key, str):
        producer_key = None

    return ClaudeOutcome(status=status, detail=detail, producer_key=producer_key)


def _make_claude_runner(log_root: Path) -> "ClaudeRunner":
    """Build a claude_runner closure that tees the spawned session's combined
    stdout+stderr to a per-SubTask log file under ``log_root``. The path is
    surfaced in the ``ClaudeOutcome.detail`` so the digest writer and the live
    progress sink can point the user at the log when something goes wrong.
    """
    log_root.mkdir(parents=True, exist_ok=True)

    def _run(subtask_key: str, worktree_path: Path, cap_s: int) -> ClaudeOutcome:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log_path = log_root / f"{subtask_key}-{ts}.log"
        # --print: non-interactive — claude exits after the prompt completes
        # instead of dropping into the REPL (otherwise subprocess.run hangs
        # until the cap_s timeout because the slash command is consumed but
        # the session stays open for further user input).
        # --dangerously-skip-permissions: AFK lane is fully autonomous by
        # design; the spawned session must be able to edit/commit/push
        # without prompts.
        timed_out = False
        returncode: Optional[int] = None
        with log_path.open("w", encoding="utf-8") as f:
            f.write(f"# afk claude session log\n# subtask: {subtask_key}\n# cwd: {worktree_path}\n# started: {ts}\n# cap_s: {cap_s}\n\n")
            f.flush()
            try:
                proc = subprocess.run(
                    ["claude", "--print", "--dangerously-skip-permissions", f"/afk:execute {subtask_key}"],
                    cwd=str(worktree_path),
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=cap_s,
                )
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True

        # The skill's emitted AFK_OUTCOME marker is the source of truth — it
        # carries the structured status (test_fail, contract_mismatch,
        # produces_drift, ...). If parsed cleanly we trust it regardless of
        # exit code: claude --print exits 0 on clean termination and the
        # narrative outcome is what determines runner routing.
        parsed = _parse_outcome_marker(log_path)
        if isinstance(parsed, ClaudeOutcome):
            return parsed

        if timed_out:
            return ClaudeOutcome(
                status="timeout",
                detail=f"hit {cap_s}s wall-clock cap (log: {log_path})",
            )

        # No usable marker — surface the reason loudly. Pre-marker behaviour
        # demoted every nonzero exit to ``other`` and every zero exit to
        # ``success``; the latter silently masked structured failures, which
        # is exactly the bug this seam fixes.
        return ClaudeOutcome(
            status="other",
            detail=f"no AFK_OUTCOME marker emitted ({parsed}); exit {returncode} (log: {log_path})",
        )

    return _run


# ---------------------------------------------------------------------------
# Pre-flight (ST08) — per-backend dispatch
# ---------------------------------------------------------------------------


# Injectable subprocess runner for the pre-flight probes — tests stub this
# to assert ordering and halt-on-failure without spawning real ``gh`` /
# ``claude`` processes. Production calls ``subprocess.run``.
ProbeRunner = Callable[..., subprocess.CompletedProcess]


def _default_probe_runner(*args, **kwargs) -> subprocess.CompletedProcess:
    """Default probe runner — thin pass-through to ``subprocess.run``.

    Kept module-local (not imported from ``repo_clone_manager``) so the
    timeout/encoding policy can be tuned independently of the clone-side
    runner, which has very different latency tolerances.
    """
    return subprocess.run(
        *args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )


def _preflight_jira(
    config: DriverConfig,
    repo_root: Path,
    args: argparse.Namespace,
) -> None:
    """Existing Jira-backend pre-flight, unchanged from pre-ST08 behaviour.

    1. ``runner.preflight`` — tool presence (glab, mvn, node, claude, git),
       ``GITLAB_TOKEN`` env var, repo_root is a directory.
    2. ``JIRA_BASE_URL`` / ``JIRA_EMAIL`` / ``JIRA_API_TOKEN`` env vars (via
       the parsed args, which default to env).

    Raises :class:`PreflightError` on any failure so the GitHub-branch
    caller sees the same exception type.
    """
    preflight(config, repo_root=repo_root, env=os.environ)
    if not (args.jira_base and args.jira_email and args.jira_token):
        raise PreflightError(
            "jira: JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN required"
        )


def _preflight_github(
    tracker: GitHubIssuesClient,
    config: DriverConfig,
    *,
    probe_runner: ProbeRunner = _default_probe_runner,
) -> list[SweepWarning]:
    """GitHub-backend pre-flight: auth → MCP → REST probe → sweeper.

    Ordering matters (SDD §7 use-case 1 sequenceDiagram + ADR-0005
    flowchart). Each step raises :class:`PreflightError` on failure; the
    sweeper itself does not raise on per-issue failures (those become
    ``SweepWarning`` records with ``error`` set so the digest surfaces
    them without halting the whole pass).

    Returns the sweeper's warning list; an empty list means either no
    stuck issues or the sweeper found and recovered everything cleanly.
    """
    _probe_gh_auth(probe_runner)
    _probe_mcp_list(probe_runner)
    _probe_sub_issue_rest(tracker, probe_runner)
    return _run_sweeper(tracker)


def _probe_gh_auth(probe_runner: ProbeRunner) -> None:
    """Step 1 — ``gh auth status`` must exit 0 (SDD §7 use-case 1).

    ``gh`` writes auth status to stderr regardless of success; we only
    look at the exit code. Timeout caps at ``_GH_PROBE_TIMEOUT_S`` so a
    network-hung ``gh`` can't blow the SDD §10 NFR pre-flight budget.
    """
    try:
        proc = probe_runner(
            ["gh", "auth", "status"],
            timeout=_GH_PROBE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as e:
        raise PreflightError(
            f"gh auth status timed out after {_GH_PROBE_TIMEOUT_S}s"
        ) from e
    except FileNotFoundError as e:
        raise PreflightError("gh CLI not found on PATH") from e
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or "non-zero exit"
        raise PreflightError(f"gh auth status failed: {msg}")


def _probe_mcp_list(probe_runner: ProbeRunner) -> None:
    """Step 2 — ``claude mcp list`` output must contain ``github`` within
    ``_MCP_PROBE_TIMEOUT_S`` seconds (SDD §10 NFRs row "claude mcp list
    probe time (s) | < 2").

    A timeout halts with a diagnostic — the user typically needs to
    re-add the MCP server or restart the Claude daemon.
    """
    try:
        proc = probe_runner(
            ["claude", "mcp", "list"],
            timeout=_MCP_PROBE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as e:
        raise PreflightError(
            f"claude mcp list timed out after {_MCP_PROBE_TIMEOUT_S}s "
            f"(MCP daemon likely unresponsive)"
        ) from e
    except FileNotFoundError as e:
        raise PreflightError("claude CLI not found on PATH") from e
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or "non-zero exit"
        raise PreflightError(f"claude mcp list failed: {msg}")
    combined = (proc.stdout or "") + (proc.stderr or "")
    if "github" not in combined.lower():
        raise PreflightError(
            "claude mcp list output does not include 'github' — "
            "install/configure the GitHub MCP server before running"
        )


def _probe_sub_issue_rest(
    tracker: GitHubIssuesClient,
    probe_runner: ProbeRunner,
) -> None:
    """Step 3 — sub-issue REST endpoint must return 200 (SDD §7 use-case 1).

    We need a real ``owner/repo#N`` to probe against; the spec says
    ``{any_queued_owner}/{repo}/issues/{any_N}/sub_issues``. We call
    ``tracker.list_pickable()`` to discover one. If the queue is empty
    there is nothing in-flight to validate against — the probe is
    skipped with a progress note (no sub-issues means no risk of stale
    parents either; the run will exit cleanly via "no pickable tickets
    found").
    """
    try:
        queue = tracker.list_pickable()
    except Exception as e:  # noqa: BLE001 — surface as preflight failure
        raise PreflightError(f"sub-issue REST probe: list_pickable failed: {e}") from e
    if not queue:
        # Nothing queued — nothing to probe. SDD §10 budget allows this.
        return
    ref = queue[0]
    issue_id = ref.id
    # Parse owner/repo#N → REST path. We re-use the GitHub adapter's parser
    # via a defensive split (no public helper exposed).
    if "#" not in issue_id or "/" not in issue_id.split("#", 1)[0]:
        raise PreflightError(
            f"sub-issue REST probe: malformed queue entry id {issue_id!r}"
        )
    left, _, num_s = issue_id.rpartition("#")
    owner, _, repo = left.partition("/")
    try:
        proc = probe_runner(
            [
                "gh",
                "api",
                "-i",
                f"/repos/{owner}/{repo}/issues/{num_s}/sub_issues",
            ],
            timeout=_GH_PROBE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as e:
        raise PreflightError(
            f"sub-issue REST probe timed out after {_GH_PROBE_TIMEOUT_S}s "
            f"for {issue_id}"
        ) from e
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or "non-zero exit"
        raise PreflightError(
            f"sub-issue REST probe failed for {issue_id}: {msg}"
        )
    # ``gh api -i`` includes the status line as the first header. Anything
    # other than HTTP/2 200 / HTTP/1.1 200 indicates the sub-issue API is
    # not enabled for this repo / token.
    head = (proc.stdout or "").splitlines()[:1]
    status_line = head[0] if head else ""
    if "200" not in status_line:
        raise PreflightError(
            f"sub-issue REST probe for {issue_id} returned {status_line!r} "
            f"(expected 200)"
        )


def _run_sweeper(tracker) -> list[SweepWarning]:
    """Step 4 — reset crashed-mid-flight sub-issues to ``afk:pending``.

    Reuses the IssueTracker Protocol surface (ADR-0005 flowchart):
    ``list_stuck_subissues`` → for each: ``revert_to_pending`` + ``comment``.
    ADR-0004's verify-3x retry lives inside the tracker; this loop is
    presentation-layer only.

    Per-issue failures (label transition exhausts retries, comment post
    fails) are caught and folded into the returned warning list with
    ``error`` set, so sibling issues still get swept and the digest can
    flag the partial failure. Sweeper-level failures (e.g.
    ``list_stuck_subissues`` raises) propagate as :class:`PreflightError`
    since they imply the tracker is unreachable.
    """
    try:
        stuck = tracker.list_stuck_subissues()
    except Exception as e:  # noqa: BLE001 — sweeper input is mandatory
        raise PreflightError(f"sweeper: list_stuck_subissues failed: {e}") from e

    warnings: list[SweepWarning] = []
    comment_body = (
        "AFK: previous run did not complete; reset to afk:pending for re-pickup"
    )
    for ref in stuck:
        issue_id = ref.id
        try:
            tracker.revert_to_pending(issue_id)
        except Exception as e:  # noqa: BLE001 — fold into warning, continue
            warnings.append(SweepWarning(
                issue_id=issue_id,
                action="revert_to_pending failed",
                error=str(e),
            ))
            continue
        try:
            tracker.comment(issue_id, comment_body)
            warnings.append(SweepWarning(
                issue_id=issue_id,
                action="reset to afk:pending",
            ))
        except Exception as e:  # noqa: BLE001 — reset succeeded, comment did not
            warnings.append(SweepWarning(
                issue_id=issue_id,
                action="reset to afk:pending (comment post failed)",
                error=str(e),
            ))
    return warnings


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Factored out so tests can introspect / re-use the flag surface; the
    ``--github-all-repos`` / ``--cwd-only`` flags are mutually exclusive
    (one-shot overrides on ``[github] mode``).
    """
    parser = argparse.ArgumentParser(
        prog="python -m afk_driver",
        description="AFK driver — one drain pass.",
    )
    parser.add_argument("--repo-root", default=os.getcwd(), help="Path to the git repo to operate on")
    parser.add_argument("--label", default="afk-agents", help="Label that gates AFK eligibility (Jira: jira label; GitHub: issue label)")
    parser.add_argument("--project", default="P2P", help="Jira project key (Jira backend only)")
    parser.add_argument("--digest-out", default=None, help="Write digest to this path (default: stdout)")
    parser.add_argument("--jira-base", default=os.environ.get("JIRA_BASE_URL", ""), help="Jira base URL")
    parser.add_argument("--jira-email", default=os.environ.get("JIRA_EMAIL", ""), help="Jira email")
    parser.add_argument("--jira-token", default=os.environ.get("JIRA_API_TOKEN", ""), help="Jira API token")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--github-all-repos",
        action="store_true",
        help="One-shot override: set [github] mode = 'all-repos' for this run "
             "(queue is discovered via gh search across all owned repos; ADR-0003)",
    )
    mode_group.add_argument(
        "--cwd-only",
        action="store_true",
        help="One-shot override: set [github] mode = 'cwd' for this run "
             "(backend auto-detected from cwd's origin remote)",
    )
    return parser


def _apply_mode_override(config: DriverConfig, args: argparse.Namespace) -> DriverConfig:
    """Apply ``--github-all-repos`` / ``--cwd-only`` to the loaded config.

    Returns a new ``DriverConfig`` (frozen dataclass) with ``github.mode``
    swapped; no-op when neither flag is set so existing single-backend
    invocations are byte-identical to pre-ST08.
    """
    from dataclasses import replace

    if args.github_all_repos:
        return replace(config, github=replace(config.github, mode="all-repos"))
    if args.cwd_only:
        return replace(config, github=replace(config.github, mode="cwd"))
    return config


def main(
    argv: list[str] | None = None,
    *,
    transport_factory: Callable[..., HttpTransport] = UrllibTransport,
    glab_runner_factory: Callable[[], Callable] = lambda: default_runner,
    claude_runner_factory: Callable[..., "ClaudeRunner"] = _make_claude_runner,
    probe_runner: ProbeRunner = _default_probe_runner,
    backend_resolver: Callable[..., backend_select.Backend] = backend_select.resolve,
    github_tracker_factory: Callable[[], GitHubIssuesClient] = GitHubIssuesClient,
) -> int:
    """One drain pass and exit.

    Composition root: resolves the backend BEFORE constructing the Runner
    (SDD §8 row "cli (modified)"), runs per-backend pre-flight, then
    materialises the runner with the resolved ``tracker`` / ``scm`` /
    ``repo_clone_manager`` triple.

    Factory kwargs exist so the scenario harness can swap the seams below
    ``JiraClient`` / ``GitLabClient`` / the spawned ``claude`` subprocess
    / the pre-flight subprocess probes / the backend resolver itself
    while keeping every parsing / wiring layer in this module under test.
    Defaults reproduce production behaviour exactly.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    config = load()
    config = _apply_mode_override(config, args)
    repo_root = Path(args.repo_root).resolve()

    # ---- Backend dispatch (SDD §3 single dispatch point) -----------------
    try:
        backend = backend_resolver(repo_root, config)
    except backend_select.BackendResolutionError as e:
        print(f"backend-select: {e}", file=sys.stderr)
        return 2

    backend_name = backend.repo_coords.backend
    sweeper_warnings: list[SweepWarning] = []

    # ---- Per-backend pre-flight + runner construction --------------------
    if backend_name == "github":
        # ``backend_select`` returns a fresh ``GitHubIssuesClient`` in the
        # tracker slot; tests inject their own via ``github_tracker_factory``
        # so they can mock list_pickable / list_stuck_subissues without
        # patching subprocess. Production keeps the resolver's instance.
        tracker = backend.tracker
        if tracker is None:
            # ``mode=all-repos`` with force override could in principle hit
            # this path; defensive guard so we never construct a runner
            # with a None tracker.
            tracker = github_tracker_factory()
        try:
            sweeper_warnings = _preflight_github(
                tracker, config, probe_runner=probe_runner,
            )
        except PreflightError as e:
            print(f"preflight (github): {e}", file=sys.stderr)
            return 2

        runner = Runner(
            tracker=tracker,
            scm=backend.scm,
            worktrees=_WorktreeAdapter(),
            claude_runner=claude_runner_factory(config.log_root),
            config=config,
            repo_root=repo_root,
            label=args.label,
            project_key=args.project,
            repo_coords=backend.repo_coords,
            repo_clone_manager=repo_clone_manager.ensure_clone,
        )
    elif backend_name == "jira":
        try:
            _preflight_jira(config, repo_root, args)
        except PreflightError as e:
            print(f"preflight: {e}", file=sys.stderr)
            return 2

        jira = JiraClient(
            JiraConfig(
                base_url=args.jira_base,
                email=args.jira_email,
                api_token=args.jira_token,
            ),
            transport_factory(args.jira_base, args.jira_email, args.jira_token),
        )
        # Jira-side scm is always GitLab; ``backend_select`` may not have
        # populated tracker (per ADR / SDD §5 — secrets live in env), but
        # scm is fully bound.
        gitlab = backend.scm if isinstance(backend.scm, GitLabClient) else GitLabClient(
            runner=glab_runner_factory()
        )
        runner = Runner(
            tracker=jira,
            scm=gitlab,
            worktrees=_WorktreeAdapter(),
            claude_runner=claude_runner_factory(config.log_root),
            config=config,
            repo_root=repo_root,
            label=args.label,
            project_key=args.project,
            repo_coords=backend.repo_coords,
        )
    else:
        print(
            f"backend-select: unknown backend {backend_name!r}",
            file=sys.stderr,
        )
        return 2

    record = runner.one_pass()
    digest = _render_digest_with_sweep(record, sweeper_warnings)
    if args.digest_out:
        out = (config.digest_root / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md") if args.digest_out == "auto" else Path(args.digest_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(digest, encoding="utf-8")
        print(f"digest -> {out}")
    else:
        print(digest)
    return 0


def _render_digest_with_sweep(record, warnings: Sequence[SweepWarning]) -> str:
    """Thin alias kept for backwards-compatibility with the ST08 cli wiring
    and its tests. ST09 moved the sweeper-warnings block into
    ``digest_writer.format_digest``'s own signature; this shim just
    forwards. New callers should invoke ``format_digest`` directly.
    """
    return format_digest(record, warnings)


if __name__ == "__main__":
    raise SystemExit(main())
