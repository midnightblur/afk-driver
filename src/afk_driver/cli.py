"""``python -m afk_driver`` CLI: one drain pass and exit.

Wires the real clients (UrllibTransport for Jira, default subprocess for glab,
real worktree_manager) into a Runner, executes one pass, writes the digest.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from typing import Callable

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
        with log_path.open("w", encoding="utf-8") as f:
            f.write(f"# afk claude session log\n# subtask: {subtask_key}\n# cwd: {worktree_path}\n# started: {ts}\n# cap_s: {cap_s}\n\n")
            f.flush()
            try:
                proc = subprocess.run(
                    ["claude", "--print", "--dangerously-skip-permissions", f"/afk-go {subtask_key}"],
                    cwd=str(worktree_path),
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=cap_s,
                )
            except subprocess.TimeoutExpired:
                return ClaudeOutcome(
                    status="timeout",
                    detail=f"hit {cap_s}s wall-clock cap (log: {log_path})",
                )
        if proc.returncode == 0:
            return ClaudeOutcome(status="success", detail=f"log: {log_path}")
        return ClaudeOutcome(
            status="other",
            detail=f"exit {proc.returncode} (log: {log_path})",
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
