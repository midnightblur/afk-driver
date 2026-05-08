"""``python -m afk_driver`` CLI: one drain pass and exit.

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
from datetime import datetime, timezone
from pathlib import Path

from typing import Callable, Optional, Union

from afk_driver.config import load
from afk_driver.digest_writer import format_digest
from afk_driver.gitlab_client import GitLabClient, default_runner
from afk_driver.jira_client import HttpTransport, JiraClient, JiraConfig, UrllibTransport
from afk_driver.runner import (
    ClaudeOutcome,
    PreflightError,
    Runner,
    preflight,
)
from afk_driver import worktree_manager


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


def main(
    argv: list[str] | None = None,
    *,
    transport_factory: Callable[..., HttpTransport] = UrllibTransport,
    glab_runner_factory: Callable[[], Callable] = lambda: default_runner,
    claude_runner_factory: Callable[..., "ClaudeRunner"] = _make_claude_runner,
) -> int:
    """One drain pass and exit.

    Factory kwargs exist so the scenario harness can swap the seams below
    ``JiraClient`` / ``GitLabClient`` / the spawned ``claude`` subprocess
    while keeping every parsing / wiring layer in this module under test.
    Defaults reproduce production behaviour exactly.
    """
    parser = argparse.ArgumentParser(prog="python -m afk_driver", description="AFK driver — one drain pass.")
    parser.add_argument("--repo-root", default=os.getcwd(), help="Path to the git repo to operate on")
    parser.add_argument("--label", default="afk-agents", help="Jira label that gates AFK eligibility")
    parser.add_argument("--project", default="P2P", help="Jira project key")
    parser.add_argument("--digest-out", default=None, help="Write digest to this path (default: stdout)")
    parser.add_argument("--jira-base", default=os.environ.get("JIRA_BASE_URL", ""), help="Jira base URL")
    parser.add_argument("--jira-email", default=os.environ.get("JIRA_EMAIL", ""), help="Jira email")
    parser.add_argument("--jira-token", default=os.environ.get("JIRA_API_TOKEN", ""), help="Jira API token")
    args = parser.parse_args(argv)

    config = load()
    repo_root = Path(args.repo_root).resolve()

    try:
        preflight(config, repo_root=repo_root, env=os.environ)
    except PreflightError as e:
        print(f"preflight: {e}", file=sys.stderr)
        return 2

    if not (args.jira_base and args.jira_email and args.jira_token):
        print("jira: JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN required", file=sys.stderr)
        return 2

    jira = JiraClient(
        JiraConfig(base_url=args.jira_base, email=args.jira_email, api_token=args.jira_token),
        transport_factory(args.jira_base, args.jira_email, args.jira_token),
    )
    gitlab = GitLabClient(runner=glab_runner_factory())
    runner = Runner(
        jira=jira,
        gitlab=gitlab,
        worktrees=_WorktreeAdapter(),
        claude_runner=claude_runner_factory(config.log_root),
        config=config,
        repo_root=repo_root,
        label=args.label,
        project_key=args.project,
    )

    record = runner.one_pass()
    digest = format_digest(record)
    if args.digest_out:
        out = (config.digest_root / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md") if args.digest_out == "auto" else Path(args.digest_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(digest, encoding="utf-8")
        print(f"digest -> {out}")
    else:
        print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
