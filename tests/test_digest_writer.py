"""Golden-ish test for digest_writer."""

from __future__ import annotations

from afk_driver.digest_writer import format_digest
from afk_driver.runner import ParentRun, RunRecord, SubTaskRun


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
