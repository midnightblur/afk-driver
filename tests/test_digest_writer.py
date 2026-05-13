"""Golden-ish test for digest_writer."""

from __future__ import annotations

from dataclasses import dataclass

from afk_driver.digest_writer import format_digest
from afk_driver.runner import ParentRun, RepoFailed, RunRecord, SubTaskRun


# Lightweight stand-in for ``cli.SweepWarning`` — the digest writer accepts
# the structural shape (issue_id / action / error) so we avoid the cli
# import here.
@dataclass(frozen=True)
class _Warn:
    issue_id: str
    action: str
    error: str = ""


def test_empty_digest():
    rec = RunRecord(started_iso="2026-05-05T03:00:00+00:00", ended_iso="2026-05-05T03:00:01+00:00")
    out = format_digest(rec)
    assert "# AFK morning digest" in out
    assert "No labelled SubTasks" in out


def test_full_digest_golden():
    enh = ParentRun(
        key="P2P-1220",
        summary="AFK bootstrap",
        target_branch="master",
        mr_url="https://example.com/mr/42",
        rebase="clean",
        duration_s=12.4,
        subtasks=[
            SubTaskRun(key="P2P-1221", summary="scaffold", status="success", attempts=1, duration_s=2.1),
            SubTaskRun(key="P2P-1222", summary="worktree", status="aborted", attempts=3, detail="test_fail x3", duration_s=8.5),
        ],
    )
    rec = RunRecord(
        started_iso="2026-05-05T03:00:00+00:00",
        ended_iso="2026-05-05T03:01:30+00:00",
        parents=[enh],
    )
    out = format_digest(rec)
    expected = (
        "# AFK morning digest\n"
        "\n"
        "_Run: 2026-05-05T03:00:00+00:00 → 2026-05-05T03:01:30+00:00_\n"
        "\n"
        "**Summary:** 1 parent(s), 1 SubTask(s) succeeded, 1 aborted, 0 parent(s) skipped.\n"
        "\n"
        "## P2P-1220 — AFK bootstrap\n"
        "- Target branch: `master`\n"
        "- MR: https://example.com/mr/42\n"
        "- Duration: 12.4s\n"
        "- Post-last-SubTask rebase: **clean**\n"
        "\n"
        "| SubTask | Status | Attempts | Detail |\n"
        "|---------|--------|----------|--------|\n"
        "| P2P-1221 | success | 1 |  |\n"
        "| P2P-1222 | aborted | 3 | test_fail x3 |\n"
    )
    assert out == expected


def test_flaky_suspect_surfaces_in_summary_and_row():
    """S1 — the digest must surface the flaky-suspect tag inline so the
    morning reader sees it without diffing two consecutive digests. Not
    failing the run is intentional: the SubTask succeeded, the digest
    just needs to flag investigation."""
    enh = ParentRun(
        key="P2P-1220",
        summary="AFK bootstrap",
        target_branch="master",
        mr_url="https://example.com/mr/42",
        rebase="clean",
        duration_s=10.0,
        subtasks=[
            SubTaskRun(
                key="P2P-1221", summary="flaky-on-retry", status="success",
                attempts=2, duration_s=4.5, flaky_suspect=True,
            ),
            SubTaskRun(
                key="P2P-1222", summary="clean", status="success",
                attempts=1, duration_s=2.0, flaky_suspect=False,
            ),
        ],
    )
    rec = RunRecord(
        started_iso="2026-05-05T03:00:00+00:00",
        ended_iso="2026-05-05T03:00:30+00:00",
        parents=[enh],
    )
    out = format_digest(rec)
    # Summary line carries the flaky count.
    assert "2 SubTask(s) succeeded, 1 flaky-suspect" in out
    # Row for P2P-1221 has the warning glyph; the clean row does not.
    assert "| P2P-1221 | success ⚠️ flaky-suspect | 2 |" in out
    assert "| P2P-1222 | success | 1 |" in out


def test_skipped_enhancement():
    rec = RunRecord(
        started_iso="2026-05-05T03:00:00+00:00",
        ended_iso="2026-05-05T03:00:01+00:00",
        parents=[
            ParentRun(
                key="P2P-9999",
                summary="bad parent",
                skip_reason="parent has no fixVersions",
            )
        ],
    )
    out = format_digest(rec)
    assert "_skipped: parent has no fixVersions_" in out
    assert "Target branch" not in out


# ---------------------------------------------------------------------------
# ST09 — GitHub-only golden file
# ---------------------------------------------------------------------------


def test_github_only_digest_golden():
    """GitHub-only run: ``Backend`` / ``Repo`` columns rendered, sub-issue
    rows use ``owner/repo#N``, PR link is clickable Markdown
    (PRD §"Observability" — User Stories 39-41)."""
    enh = ParentRun(
        key="acme/widget#7",
        summary="GitHub bootstrap",
        target_branch="main",
        mr_url="https://github.com/acme/widget/pull/42",
        rebase="clean",
        duration_s=9.0,
        subtasks=[
            SubTaskRun(key="acme/widget#8", summary="impl", status="success", attempts=1, duration_s=3.0),
            SubTaskRun(key="acme/widget#9", summary="docs", status="success", attempts=1, duration_s=1.5),
        ],
    )
    rec = RunRecord(
        started_iso="2026-05-05T03:00:00+00:00",
        ended_iso="2026-05-05T03:00:09+00:00",
        backend="github",
        parents=[enh],
    )
    out = format_digest(rec)
    expected = (
        "# AFK morning digest\n"
        "\n"
        "_Run: 2026-05-05T03:00:00+00:00 → 2026-05-05T03:00:09+00:00_\n"
        "\n"
        "**Summary:** 1 parent(s), 2 SubTask(s) succeeded, 0 aborted, 0 parent(s) skipped.\n"
        "\n"
        "## acme/widget#7 — GitHub bootstrap\n"
        "- Backend: `github`\n"
        "- Repo: `acme/widget`\n"
        "- Target branch: `main`\n"
        "- MR: [#42](https://github.com/acme/widget/pull/42)\n"
        "- Duration: 9.0s\n"
        "- Post-last-SubTask rebase: **clean**\n"
        "\n"
        "| SubTask | Status | Attempts | Detail |\n"
        "|---------|--------|----------|--------|\n"
        "| acme/widget#8 | success | 1 |  |\n"
        "| acme/widget#9 | success | 1 |  |\n"
    )
    assert out == expected


def test_mixed_jira_and_github_in_one_digest():
    """One file across both backends (PRD §"Observability" — User Story 39
    "single file"). Once any parent is GitHub-shaped, every parent row
    gains the Backend/Repo columns so the table stays uniform."""
    jira_parent = ParentRun(
        key="P2P-1300",
        summary="Jira side",
        target_branch="master",
        mr_url="https://gitlab.com/grp/proj/-/merge_requests/55",
        duration_s=4.0,
        subtasks=[
            SubTaskRun(key="P2P-1301", summary="t", status="success", attempts=1),
        ],
    )
    gh_parent = ParentRun(
        key="acme/widget#7",
        summary="GitHub side",
        target_branch="main",
        mr_url="https://github.com/acme/widget/pull/42",
        duration_s=5.0,
        subtasks=[
            SubTaskRun(key="acme/widget#8", summary="t", status="success", attempts=1),
        ],
    )
    rec = RunRecord(
        started_iso="t0",
        ended_iso="t1",
        backend="github",
        parents=[jira_parent, gh_parent],
    )
    out = format_digest(rec)

    # Single file -- both parents present in one rendering.
    assert "## P2P-1300 — Jira side" in out
    assert "## acme/widget#7 — GitHub side" in out

    # Per-parent backend / repo columns rendered for BOTH parents.
    assert "- Backend: `jira`\n- Repo: `P2P`\n" in out
    assert "- Backend: `github`\n- Repo: `acme/widget`\n" in out

    # PR / MR links clickable.
    assert "- MR: [!55](https://gitlab.com/grp/proj/-/merge_requests/55)" in out
    assert "- MR: [#42](https://github.com/acme/widget/pull/42)" in out

    # Sub-issue ids verbatim — copy-paste-able.
    assert "| P2P-1301 |" in out
    assert "| acme/widget#8 |" in out


def test_multi_repo_github_digest_three_repos():
    """ADR-0003 multi-repo: three GitHub parents from three repos render
    in a single digest with per-row Repo coordinates."""
    parents = [
        ParentRun(
            key="acme/alpha#1",
            summary="alpha", target_branch="main",
            mr_url="https://github.com/acme/alpha/pull/10",
            duration_s=1.0,
            subtasks=[SubTaskRun(key="acme/alpha#2", summary="x", status="success", attempts=1)],
        ),
        ParentRun(
            key="acme/beta#3",
            summary="beta", target_branch="main",
            mr_url="https://github.com/acme/beta/pull/11",
            duration_s=2.0,
            subtasks=[SubTaskRun(key="acme/beta#4", summary="y", status="success", attempts=1)],
        ),
        ParentRun(
            key="acme/gamma#5",
            summary="gamma", target_branch="main",
            mr_url="https://github.com/acme/gamma/pull/12",
            duration_s=3.0,
            subtasks=[SubTaskRun(key="acme/gamma#6", summary="z", status="success", attempts=1)],
        ),
    ]
    rec = RunRecord(
        started_iso="t0", ended_iso="t1", backend="github", parents=parents,
        repo_failures=[
            RepoFailed(backend="github", owner="acme", repo="delta", reason="clone failed: auth"),
        ],
    )
    out = format_digest(rec)

    # All three repos surfaced row-by-row in the per-parent rollup.
    for repo in ("acme/alpha", "acme/beta", "acme/gamma"):
        assert f"- Repo: `{repo}`\n" in out

    # Three clickable PR links (one per repo).
    assert "[#10](https://github.com/acme/alpha/pull/10)" in out
    assert "[#11](https://github.com/acme/beta/pull/11)" in out
    assert "[#12](https://github.com/acme/gamma/pull/12)" in out

    # Skipped-repo block surfaces the per-repo failure (ADR-0003 ``skip_repo``).
    assert "## Skipped repos" in out
    assert "- `acme/delta` — clone failed: auth" in out


# ---------------------------------------------------------------------------
# ST09 — Sweeper warnings block (moved from cli.py shim into digest_writer)
# ---------------------------------------------------------------------------


def test_sweeper_warnings_omitted_when_empty():
    """Empty sweeper list → block entirely absent (no empty section)."""
    rec = RunRecord(started_iso="t0", ended_iso="t1")
    out = format_digest(rec, [])
    assert "## Sweeper warnings" not in out


def test_sweeper_warnings_prepended_above_per_parent_rollup():
    """Block lives ABOVE the per-parent rollup (and above the digest H1)
    so the human sees it before any ticket-level detail."""
    parent = ParentRun(
        key="acme/widget#7", summary="x", target_branch="main",
        mr_url="https://github.com/acme/widget/pull/42",
        duration_s=1.0,
        subtasks=[SubTaskRun(key="acme/widget#8", summary="t", status="success", attempts=1)],
    )
    rec = RunRecord(started_iso="t0", ended_iso="t1", backend="github", parents=[parent])
    warnings = [
        _Warn(issue_id="acme/widget#9", action="reset to afk:pending"),
        _Warn(issue_id="acme/widget#11", action="reset to afk:pending (comment post failed)", error="gh api 500"),
    ]
    out = format_digest(rec, warnings)

    # Block at the very top.
    assert out.startswith("## Sweeper warnings\n")
    # Both bullets present, error annotated in parens.
    assert "- `acme/widget#9` — reset to afk:pending" in out
    assert "- `acme/widget#11` — reset to afk:pending (comment post failed) (gh api 500)" in out
    # Per-parent rollup follows the block.
    sw_idx = out.index("## Sweeper warnings")
    h1_idx = out.index("# AFK morning digest")
    parent_idx = out.index("## acme/widget#7")
    assert sw_idx < h1_idx < parent_idx


def test_clickable_pr_link_falls_back_to_raw_for_unknown_url():
    """Unknown SCM URL → raw URL kept (no garbage Markdown). Forward-compat
    for whatever new backend lands next."""
    parent = ParentRun(
        key="P2P-1", summary="x", target_branch="main",
        mr_url="https://random.host/path/to/thing",
        duration_s=1.0,
        subtasks=[SubTaskRun(key="P2P-2", summary="t", status="success", attempts=1)],
    )
    rec = RunRecord(started_iso="t0", ended_iso="t1", parents=[parent])
    out = format_digest(rec)
    assert "- MR: https://random.host/path/to/thing" in out


def test_github_sub_issue_id_appears_verbatim():
    """User Story 41 — sub-issue id is copy-paste-able as
    ``owner/repo#N`` (not wrapped, not escaped)."""
    parent = ParentRun(
        key="acme/widget#7", summary="x", target_branch="main",
        mr_url="https://github.com/acme/widget/pull/42",
        duration_s=1.0,
        subtasks=[SubTaskRun(key="acme/widget#8", summary="t", status="success", attempts=1)],
    )
    rec = RunRecord(started_iso="t0", ended_iso="t1", backend="github", parents=[parent])
    out = format_digest(rec)
    assert "| acme/widget#8 | success | 1 |" in out
