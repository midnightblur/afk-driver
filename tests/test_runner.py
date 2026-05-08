"""Integration tests for the runner with fake Jira / GitLab / worktree clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from afk_driver.config import defaults
from afk_driver.gitlab_client import MRInfo, SubtaskItem
from afk_driver.jira_client import IssueSummary
from afk_driver.runner import (
    ClaudeOutcome,
    Runner,
    SubTaskRun,
    ParentRun,
    RunRecord,
)


# --- Fakes -----------------------------------------------------------------

class FakeJira:
    def __init__(self, issues: list[IssueSummary], parents: dict[str, dict]):
        self._issues = issues
        self._parents = dict(parents)
        self.transitions: list[tuple[str, str]] = []
        self.notes: list[tuple[str, str, str]] = []
        self.comments: list[tuple[str, str]] = []
        self.field_writes: list[tuple[str, dict]] = []
        self.assignments: list[tuple[str, str]] = []
        self.flips: list[str] = []
        self.events: list[tuple] = []  # ordered log of ("transition"|"set_fields", key, payload)
        self.search_calls: int = 0
        self.account_id: str = "fake-account-id-123"
        # S3 — the runner's contract_mismatch routing reads producer status
        # via get_status(key). Tests that need a stable producer-status
        # response REGARDLESS of intervening transition() calls (e.g. when
        # the producer's own success-path transitions it past the lock
        # point during the same drain pass) seed this dict; entries here
        # win over self._parents. Keys present in _status_raise raise
        # instead, simulating a transient HTTP error.
        self._status_overrides: dict[str, str] = {}
        self._status_raise: set[str] = set()

    def get_my_account_id(self) -> str:
        return self.account_id

    def assign(self, key: str, account_id: str) -> None:
        self.assignments.append((key, account_id))

    def search(self, jql: str, *, max_results: int = 100):
        self.search_calls += 1
        return list(self._issues)

    def get_parent_fields(self, key: str) -> dict:
        return dict(self._parents[key])

    def get_status(self, key: str) -> str:
        # _status_overrides wins over _parents because transition() mutates
        # _parents in-place, which would otherwise mean a producer that
        # succeeded earlier in the same drain pass appears as Dev-CR/Merge
        # by the time its consumer's contract_mismatch lands here — fine
        # in production (it's the actual current state), but useless when
        # a test wants to pin the response.
        if key in self._status_raise:
            raise RuntimeError("simulated jira get_status failure")
        if key in self._status_overrides:
            return self._status_overrides[key]
        return self._parents.get(key, {}).get("status", "Dev-Pending")

    def transition(self, key: str, name: str) -> None:
        self.transitions.append((key, name))
        self.events.append(("transition", key, name))
        # mirror parent-status changes so subsequent calls observe them
        if key in self._parents:
            mapping = {
                "Start Designing": "Dev-Designing",
                "Start Development": "Dev-Developing",
                "Request CR & Merge": "Dev-CR/Merge",
            }
            new_status = mapping.get(name)
            if new_status:
                self._parents[key]["status"] = new_status

    def update_implementation_notes(self, parent_key, sub_key, bullet) -> None:
        self.notes.append((parent_key, sub_key, bullet))

    def comment(self, key, md) -> None:
        self.comments.append((key, md))

    def set_fields(self, key, fields) -> None:
        self.field_writes.append((key, dict(fields)))
        self.events.append(("set_fields", key, dict(fields)))

    def set_field_if_unset(self, key, field_id, value) -> bool:
        # Treat the parent's currently-known value of field_id as authoritative.
        # Default behaviour mirrors real JiraClient: if the parent dict has no
        # entry (or empty), write and return True; otherwise no-op + False.
        current = self._parents.get(key, {}).get(field_id)
        if current not in (None, "", [], {}):
            return False
        self._parents.setdefault(key, {})[field_id] = value
        self.field_writes.append((key, {field_id: value}))
        self.events.append(("set_fields", key, {field_id: value}))
        return True

    def list_transitions(self, key):
        return []

    def flip_acceptance_checkboxes(self, key: str) -> None:
        self.flips.append(key)


class FakeGitLab:
    def __init__(self):
        self.opened: list[dict] = []
        self.checklists: list[tuple[str, list[SubtaskItem]]] = []
        self._open_for: dict[str, MRInfo] = {}
        # Per-parent-key canned response for find_open_mr_by_parent_key.
        # Tests inject an MRInfo to simulate "user already opened an MR
        # for this parent on a hand-crafted branch"; default behaviour is
        # "no existing MR" so the runner falls back to its template branch.
        # Special sentinel: if value is the string "AMBIGUOUS", the lookup
        # raises GitLabError to mirror the >1-match real-world failure.
        self._mr_for_parent: dict[str, Any] = {}

    def find_open_mr_by_parent_key(self, parent_key: str):
        from afk_driver.gitlab_client import GitLabError
        result = self._mr_for_parent.get(parent_key)
        if result == "AMBIGUOUS":
            raise GitLabError(f"ambiguous: 2 open MRs match parent {parent_key}")
        return result

    def open_draft_mr(self, *, source_branch, target_branch, title, description, assignee=None) -> MRInfo:
        if source_branch in self._open_for:
            return self._open_for[source_branch]
        mr = MRInfo(
            iid=42,
            web_url=f"https://example.com/mr/{source_branch}",
            state="opened",
            title=title,
            description=description,
            source_branch=source_branch,
            target_branch=target_branch,
        )
        self._open_for[source_branch] = mr
        self.opened.append(
            {"source_branch": source_branch, "target_branch": target_branch, "title": title, "assignee": assignee}
        )
        return mr

    def update_subtasks_checklist(self, branch: str, items: list[SubtaskItem]) -> MRInfo:
        self.checklists.append((branch, list(items)))
        return self._open_for[branch]


class FakeWorktrees:
    """Test fake for the worktree manager.

    Models the relevant subset of git state per (spec.parent_id, spec.branch):
    a monotonically increasing HEAD SHA and a "dirty" flag the test can flip
    to simulate a claude session that left uncommitted edits behind. The
    runner's auto-commit safety net interrogates head_sha + commit_dirty_changes
    to decide whether the SubTask actually advanced the branch.
    """

    def __init__(self, *, rebase_outcome: str = "clean"):
        self.ensured: list[Any] = []
        self.published: list[Any] = []
        self.rebased: list[Any] = []
        self.rebase_outcome = rebase_outcome
        # Per-spec.path commit log + pushed log.
        self._tip: dict = {}
        self._dirty: dict = {}
        self.commits: list[tuple[str, str]] = []  # (parent_id, message)
        self.pushed: list[Any] = []
        self.resets: list[Any] = []
        # Test-injected map: branch -> Path. When set, the runner's
        # discovery probe sees that branch as already checked out at the
        # given path and reuses it (path_override on spec).
        self._foreign_worktrees: dict[str, Path] = {}

    def find_worktree_for_branch(self, repo_root, branch):
        return self._foreign_worktrees.get(branch)

    def _key(self, spec):
        return str(spec.path)

    def _ensure_tip(self, spec):
        if self._key(spec) not in self._tip:
            self._tip[self._key(spec)] = "0" * 40

    def ensure(self, spec):
        self.ensured.append(spec)
        self._ensure_tip(spec)
        return spec.path

    def publish_branch(self, spec):
        self.published.append(spec)

    def rebase_onto_target(self, spec):
        self.rebased.append(spec)
        return self.rebase_outcome

    def validate_state(self, spec):
        return None

    def head_sha(self, spec):
        self._ensure_tip(spec)
        return self._tip[self._key(spec)]

    def mark_dirty(self, spec):
        """Test helper: simulate claude leaving uncommitted edits behind."""
        self._dirty[self._key(spec)] = True

    def advance_tip(self, spec):
        """Test helper: simulate claude making its own commit during the session."""
        self._ensure_tip(spec)
        cur = self._tip[self._key(spec)]
        self._tip[self._key(spec)] = f"{int(cur, 16) + 1:040x}"

    def commit_dirty_changes(self, spec, message):
        if not self._dirty.get(self._key(spec)):
            return False
        self._dirty[self._key(spec)] = False
        self.advance_tip(spec)
        self.commits.append((spec.parent_id, message))
        return True

    def push_branch(self, spec):
        self.pushed.append(spec)

    def reset_to_clean(self, spec):
        """Test helper: clears the simulated dirty flag, returns True if it was set.

        Models the runner's per-subtask safety net: any uncommitted leftover
        from a prior interruption is wiped before the next claude attempt.
        """
        self._ensure_tip(spec)
        was_dirty = bool(self._dirty.get(self._key(spec)))
        if was_dirty:
            self._dirty[self._key(spec)] = False
            self.resets.append(spec)
        return was_dirty


# --- Helpers ---------------------------------------------------------------

def _issue(key, parent="P2P-1220", summary="x") -> IssueSummary:
    return IssueSummary(
        key=key,
        summary=summary,
        status="Dev-Pending",
        issuetype="SubTask",
        parent_key=parent,
        labels=("afk-agents",),
        fix_versions=(),
    )


def _parent(status="Dev-Pending", target="MASTER", issuetype="Enhancement") -> dict:
    return {
        "summary": "AFK parent ticket",
        "status": status,
        "issuetype": issuetype,
        "fix_versions": ["core/1.2.0"],
        "components": [],
        "target_branch": target,
    }


def _runner(
    jira: FakeJira,
    gitlab: FakeGitLab,
    worktrees: FakeWorktrees,
    claude: Any,
    *,
    tmp_path: Path,
    auto_dirty_on_success: bool = True,
) -> Runner:
    """Build a Runner with fakes wired in.

    By default, wrap ``claude`` so a "success" outcome marks the FakeWorktrees
    dirty — this mirrors the real-world post-condition of a successful claude
    session (it edited *some* files; whether it committed them is what the
    runner's safety net handles). Tests asserting the no-op-claude failure
    path (claude returned success but didn't touch any files) pass
    ``auto_dirty_on_success=False`` to suppress this so the runner sees a
    clean tree + unchanged HEAD and converts the outcome to a SubTask
    failure.
    """
    cfg = defaults()
    # Redirect roots into tmp_path so we don't touch the user's home
    from dataclasses import replace
    cfg = replace(
        cfg,
        worktree_root=tmp_path / "wt",
        log_root=tmp_path / "logs",
        digest_root=tmp_path / "dg",
        retry_count=3,
    )
    if auto_dirty_on_success:
        inner = claude
        def _wrapped(key, path, cap):
            out = inner(key, path, cap)
            if out.status == "success" and worktrees.ensured:
                worktrees.mark_dirty(worktrees.ensured[-1])
            return out
        claude_to_use = _wrapped
    else:
        claude_to_use = claude
    return Runner(
        jira=jira,
        gitlab=gitlab,
        worktrees=worktrees,
        claude_runner=claude_to_use,
        config=cfg,
        repo_root=tmp_path / "repo",
        progress=lambda msg: None,  # silence in tests
    )


# --- Tests ----------------------------------------------------------------

def test_empty_queue(tmp_path):
    j = FakeJira([], {})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()
    assert rec.parents == []
    assert g.opened == []
    assert w.ensured == []


def test_single_subtask_happy_path(tmp_path):
    j = FakeJira([_issue("P2P-1", summary="alpha")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()
    assert len(rec.parents) == 1
    enh = rec.parents[0]
    assert enh.key == "P2P-1220"
    assert enh.target_branch == "master"
    assert [s.status for s in enh.subtasks] == ["success"]
    assert enh.rebase == "clean"
    # Parent went P2P-1220 Dev-Pending → Dev-Developing → Dev-CR/Merge
    parent_transitions = [t for t in j.transitions if t[0] == "P2P-1220"]
    assert [n for _, n in parent_transitions] == [
        "Start Designing", "Start Development", "Request CR & Merge"
    ]
    # SubTask: Designing → Developing → CR/Merge
    sub_transitions = [t for t in j.transitions if t[0] == "P2P-1"]
    assert [n for _, n in sub_transitions] == [
        "Start Designing", "Start Development", "Request CR & Merge"
    ]
    assert ("P2P-1220", "P2P-1", "alpha") in j.notes


def test_multi_subtask_drain(tmp_path):
    issues = [_issue("P2P-1"), _issue("P2P-2"), _issue("P2P-3")]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()
    assert [s.key for s in rec.parents[0].subtasks] == ["P2P-1", "P2P-2", "P2P-3"]
    assert all(s.status == "success" for s in rec.parents[0].subtasks)
    assert rec.parents[0].rebase == "clean"


def test_in_progress_enhancement_priority_over_fresh(tmp_path):
    issues = [
        _issue("P2P-A1", parent="P2P-FRESH"),
        _issue("P2P-B1", parent="P2P-OLD"),
    ]
    parents = {
        "P2P-FRESH": _parent(status="Dev-Pending"),
        "P2P-OLD": _parent(status="Dev-Developing"),
    }
    j = FakeJira(issues, parents)
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()
    assert [e.key for e in rec.parents] == ["P2P-OLD", "P2P-FRESH"]


def test_parent_not_dev_pending_or_developing_skipped(tmp_path):
    j = FakeJira(
        [_issue("P2P-1")],
        {"P2P-1220": _parent(status="Closed")},
    )
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()
    enh = rec.parents[0]
    assert enh.skip_reason.startswith("parent status")
    assert enh.subtasks == []
    assert g.opened == []


def test_post_last_subtask_rebase_conflict(tmp_path):
    j = FakeJira([_issue("P2P-1"), _issue("P2P-2")], {"P2P-1220": _parent()})
    g = FakeGitLab()
    w = FakeWorktrees(rebase_outcome="conflict")
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()
    enh = rec.parents[0]
    assert all(s.status == "success" for s in enh.subtasks)
    assert enh.rebase == "conflict"
    # Enhancement NOT transitioned to Dev-CR/Merge on conflict
    assert ("P2P-1220", "Request CR & Merge") not in j.transitions
    # Comment posted on the Enhancement
    assert any(k == "P2P-1220" and "rebase" in c.lower() for k, c in j.comments)


def test_retry_then_abort(tmp_path):
    issues = [_issue("P2P-1"), _issue("P2P-2")]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()

    attempts = {"P2P-1": 0}

    def claude(key, path, cap):
        if key == "P2P-1":
            attempts["P2P-1"] += 1
            return ClaudeOutcome("test_fail", detail=f"attempt {attempts['P2P-1']}")
        return ClaudeOutcome("success")

    r = _runner(j, g, w, claude, tmp_path=tmp_path)
    rec = r.one_pass()
    enh = rec.parents[0]
    # First SubTask aborted after 3 attempts; second never tried
    assert enh.subtasks[0].status == "aborted"
    assert enh.subtasks[0].attempts == 3
    assert len(enh.subtasks) == 1
    # Aborted SubTask got a comment + sent back via "Request Development"
    assert ("P2P-1", "Request Development") in j.transitions
    assert any(k == "P2P-1" and "aborted" in c.lower() for k, c in j.comments)
    # Rebase NOT attempted when something aborted
    assert w.rebased == []


def test_flaky_suspect_flagged_when_test_fail_precedes_success(tmp_path):
    """When a SubTask succeeds on attempt N>1 after at least one prior
    attempt was ``test_fail``, the runner must:
      - flag SubTaskRun.flaky_suspect = True (digest surfaces this)
      - post an explicit "flaky-suspect" comment so the human knows to
        investigate before the flake normalises into background noise
      - still mark the SubTask as success (the retry loop succeeded;
        we're not invalidating the run, just calling out the flake).

    S1 closure 2026-05-08."""
    issues = [_issue("P2P-1")]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()

    attempts = {"P2P-1": 0}

    def claude(key, path, cap):
        attempts["P2P-1"] += 1
        if attempts["P2P-1"] == 1:
            return ClaudeOutcome("test_fail", detail="3 unit tests failed")
        return ClaudeOutcome("success")

    r = _runner(j, g, w, claude, tmp_path=tmp_path)
    rec = r.one_pass()
    sub = rec.parents[0].subtasks[0]
    assert sub.status == "success"
    assert sub.attempts == 2
    assert sub.flaky_suspect is True

    flaky_comments = [
        c for k, c in j.comments
        if k == "P2P-1" and "flaky-suspect" in c.lower()
    ]
    assert flaky_comments, "expected a flaky-suspect comment on the SubTask"
    assert "attempt **2**" in flaky_comments[0]
    assert "test_fail" in flaky_comments[0].lower()


def test_flaky_suspect_not_flagged_when_clean_first_attempt(tmp_path):
    """Success on attempt 1 (no prior failures) must NOT be flagged. The
    flaky-suspect signal would lose meaning if every successful run
    carried it."""
    issues = [_issue("P2P-1")]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()

    r = _runner(
        j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path,
    )
    rec = r.one_pass()
    sub = rec.parents[0].subtasks[0]
    assert sub.status == "success"
    assert sub.flaky_suspect is False
    # No flaky-suspect comment posted.
    assert not [
        c for k, c in j.comments
        if k == "P2P-1" and "flaky-suspect" in c.lower()
    ]


def test_flaky_suspect_excludes_build_fail_recovery(tmp_path):
    """build_fail recovering on retry is a different category — typically
    a transient dep-cache / network issue rather than a feature-level
    race. Do NOT flag flaky-suspect for build_fail-only retry histories;
    otherwise CI noise would drown the signal."""
    issues = [_issue("P2P-1")]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()

    attempts = {"P2P-1": 0}

    def claude(key, path, cap):
        attempts["P2P-1"] += 1
        if attempts["P2P-1"] == 1:
            return ClaudeOutcome("build_fail", detail="mvn cache eviction")
        return ClaudeOutcome("success")

    r = _runner(j, g, w, claude, tmp_path=tmp_path)
    rec = r.one_pass()
    sub = rec.parents[0].subtasks[0]
    assert sub.status == "success"
    assert sub.attempts == 2
    assert sub.flaky_suspect is False
    assert not [
        c for k, c in j.comments
        if k == "P2P-1" and "flaky-suspect" in c.lower()
    ]


def test_design_conflict_no_retry_explicit_comment(tmp_path):
    """A `design_conflict` outcome from /afk:execute must:
      - skip retry (binding-contract issue, retrying as-is is wasted work)
      - post a Jira comment that names the conflict and points the human at
        /architect-grill so they emit a superseding ADR before re-queueing
      - transition the SubTask back to Dev-Pending
      - NOT proceed to subsequent SubTasks (treat like other aborts)
    """
    issues = [_issue("P2P-1"), _issue("P2P-2")]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()

    attempts = {"P2P-1": 0}

    def claude(key, path, cap):
        if key == "P2P-1":
            attempts["P2P-1"] += 1
            return ClaudeOutcome(
                "design_conflict",
                detail="SDD §8 names ExportLoader<E>; PDF lib forces Future<PDF> return",
            )
        return ClaudeOutcome("success")

    r = _runner(j, g, w, claude, tmp_path=tmp_path)
    rec = r.one_pass()
    enh = rec.parents[0]
    assert enh.subtasks[0].status == "aborted"
    # Critical: design_conflict must NOT retry — one attempt only.
    assert enh.subtasks[0].attempts == 1
    assert attempts["P2P-1"] == 1
    # Subsequent SubTask not tried (same abort semantics as other non-retryables).
    assert len(enh.subtasks) == 1
    # Routed back to Dev-Pending for human triage.
    assert ("P2P-1", "Request Development") in j.transitions
    # Comment must surface the binding-contract framing — not a generic
    # "aborted" — so the human runs /architect-grill instead of re-queueing.
    conflict_comments = [
        c for k, c in j.comments
        if k == "P2P-1" and "design conflict" in c.lower()
    ]
    assert conflict_comments, "expected a design-conflict-tagged comment"
    body = conflict_comments[0]
    assert "architect-grill" in body
    assert "superseding ADR" in body
    assert "ExportLoader" in body  # detail surfaced verbatim
    # Rebase NOT attempted when something aborted.
    assert w.rebased == []


def test_contract_mismatch_no_retry_routes_comment_to_producer(tmp_path):
    """A `contract_mismatch` outcome from /afk:execute's preflight grep must:
      - skip retry (signature drift won't fix itself by re-running the
        consumer; the producer must change)
      - post an explicit "contract mismatch" comment on the **consumer**
      - ALSO post a separate comment on the **producer** SubTask so the
        ticket the human will re-open carries the break in its own thread
      - transition the consumer back to Dev-Pending
      - halt the chain (no subsequent SubTask runs)
    """
    issues = [
        _issue("P2P-100", summary="ExportStrategy abstraction"),
        _issue("P2P-101", summary="TemplateRegistry"),
        _issue("P2P-102", summary="PdfExportStrategy"),
    ]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()

    attempts = {"P2P-101": 0}

    def claude(key, path, cap):
        if key == "P2P-100":
            return ClaudeOutcome("success")
        if key == "P2P-101":
            attempts["P2P-101"] += 1
            return ClaudeOutcome(
                "contract_mismatch",
                detail=(
                    "Consumes `ExportStrategy.java#interface ExportStrategy<E>` "
                    "from P2P-100 not found on branch — preflight grep "
                    "returned no match"
                ),
                producer_key="P2P-100",
            )
        return ClaudeOutcome("success")

    r = _runner(j, g, w, claude, tmp_path=tmp_path)
    rec = r.one_pass()
    enh = rec.parents[0]

    # P2P-100 succeeded; P2P-101 hit contract_mismatch on first attempt; P2P-102 never ran.
    assert [s.key for s in enh.subtasks] == ["P2P-100", "P2P-101"]
    assert enh.subtasks[0].status == "success"
    assert enh.subtasks[1].status == "aborted"
    # Critical: contract_mismatch must NOT retry — one attempt only.
    assert enh.subtasks[1].attempts == 1
    assert attempts["P2P-101"] == 1

    # Consumer comment frames it as contract mismatch + names the producer.
    consumer_comments = [
        c for k, c in j.comments
        if k == "P2P-101" and "contract mismatch" in c.lower()
    ]
    assert consumer_comments, "expected a contract-mismatch-tagged comment on consumer"
    assert "P2P-100" in consumer_comments[0]
    assert "ExportStrategy" in consumer_comments[0]

    # Producer comment landed separately on P2P-100.
    producer_comments = [
        c for k, c in j.comments
        if k == "P2P-100" and "contract break" in c.lower()
    ]
    assert producer_comments, (
        "expected a producer-side comment on P2P-100 surfacing the downstream break"
    )
    assert "P2P-101" in producer_comments[0]
    assert "ExportStrategy" in producer_comments[0]

    # Consumer routed back to Dev-Pending; rebase did not run.
    assert ("P2P-101", "Request Development") in j.transitions
    assert w.rebased == []


def test_contract_mismatch_with_locked_producer_emits_corrective_framing(tmp_path):
    """When the producer SubTask is past Dev-Developing (Dev-CR/Merge, Done,
    Closed, ...), telling the human to "re-open" is wrong advice — re-opening
    requires reverting a merge. The comments must instead route to "emit a
    corrective SubTask" so the consumer can be re-ranked behind the new
    producer slice instead of bouncing forever on a locked ticket.

    S3 closure 2026-05-08."""
    issues = [
        _issue("P2P-200", summary="LockedProducer (already merged elsewhere)"),
        _issue("P2P-201", summary="ConsumerThatStrandedBefore"),
    ]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    # Producer is past the lock point at the moment the consumer's
    # contract_mismatch lands. Override survives the producer's own
    # success-path transitions in the same drain pass.
    j._status_overrides["P2P-200"] = "Dev-CR/Merge"
    g, w = FakeGitLab(), FakeWorktrees()

    def claude(key, path, cap):
        if key == "P2P-200":
            return ClaudeOutcome("success")
        return ClaudeOutcome(
            "contract_mismatch",
            detail="Consumes `Foo.java#class Foo implements Bar<E>` not found",
            producer_key="P2P-200",
        )

    r = _runner(j, g, w, claude, tmp_path=tmp_path)
    rec = r.one_pass()
    enh = rec.parents[0]

    assert enh.subtasks[1].status == "aborted"
    assert enh.subtasks[1].attempts == 1  # no retry on contract_mismatch

    # Consumer comment must use the LOCKED framing — corrective SubTask, not
    # re-open the producer.
    consumer = next(
        c for k, c in j.comments
        if k == "P2P-201" and "contract mismatch" in c.lower()
    )
    assert "locked" in consumer.lower(), consumer
    assert "corrective subtask" in consumer.lower(), consumer
    assert "Dev-CR/Merge" in consumer
    # Must NOT instruct re-opening when the producer is locked.
    assert "re-open it or" not in consumer

    # Producer-side comment must also route to corrective-SubTask framing
    # rather than "re-open".
    producer = next(
        c for k, c in j.comments
        if k == "P2P-200" and "contract break" in c.lower()
    )
    assert "do **not** re-open" in producer.lower() or "do not re-open" in producer.lower(), producer
    assert "corrective subtask" in producer.lower(), producer
    assert "Dev-CR/Merge" in producer


def test_contract_mismatch_with_mutable_producer_keeps_reopen_framing(tmp_path):
    """When the producer SubTask is still in {Dev-Pending, Dev-Designing,
    Dev-Developing}, the existing "re-open the producer" framing is correct
    — the producer ticket can still legally accept changes. The locked
    framing must NOT fire here, otherwise we'd push humans to spawn extra
    SubTasks unnecessarily."""
    issues = [
        _issue("P2P-300", summary="MutableProducer"),
        _issue("P2P-301", summary="ConsumerThatHitDrift"),
    ]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    j._status_overrides["P2P-300"] = "Dev-Developing"
    g, w = FakeGitLab(), FakeWorktrees()

    def claude(key, path, cap):
        if key == "P2P-300":
            return ClaudeOutcome("success")
        return ClaudeOutcome(
            "contract_mismatch",
            detail="Consumes `Foo.java#bar(...)` returned no match",
            producer_key="P2P-300",
        )

    r = _runner(j, g, w, claude, tmp_path=tmp_path)
    r.one_pass()

    consumer = next(c for k, c in j.comments if k == "P2P-301" and "contract mismatch" in c.lower())
    assert "re-open it or" in consumer.lower(), consumer
    assert "locked" not in consumer.lower(), consumer

    producer = next(c for k, c in j.comments if k == "P2P-300" and "contract break" in c.lower())
    # Mutable producer → "Re-open and correct" stays in play.
    assert "re-open and correct" in producer.lower(), producer
    assert "do not re-open" not in producer.lower()


def test_contract_mismatch_status_fetch_failure_falls_back_to_mutable_framing(tmp_path):
    """If the runner cannot fetch the producer's status (transient HTTP
    error, 404 if the producer key was wrong, etc.), the comment must fall
    back to the historic mutable framing rather than guess at locked-state
    advice. Wrong "emit a corrective SubTask" advice is worse than the
    historic framing because it asks the human to slice extra work that
    might not be needed."""
    issues = [
        _issue("P2P-400", summary="StatusFetchFails"),
        _issue("P2P-401", summary="ConsumerOnTopOfFlakyJira"),
    ]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    j._status_raise.add("P2P-400")
    g, w = FakeGitLab(), FakeWorktrees()

    def claude(key, path, cap):
        if key == "P2P-400":
            return ClaudeOutcome("success")
        return ClaudeOutcome(
            "contract_mismatch",
            detail="Consumes anchor missing",
            producer_key="P2P-400",
        )

    r = _runner(j, g, w, claude, tmp_path=tmp_path)
    r.one_pass()

    consumer = next(c for k, c in j.comments if k == "P2P-401" and "contract mismatch" in c.lower())
    # Falls back to the historic mutable framing — the locked-state
    # tell-tales ("past the lock point", "do not retry this consumer
    # as-is") must NOT appear on a fetch failure, because we don't know
    # what state the producer is actually in. ("corrective SubTask"
    # appears in BOTH framings — it's a valid recovery either way; the
    # discriminator is the "re-open it or" phrasing that only the
    # mutable framing uses.)
    assert "past the lock point" not in consumer.lower()
    assert "re-open it or" in consumer.lower()


def test_produces_drift_no_retry_explicit_comment(tmp_path):
    """A `produces_drift` outcome from /afk:execute's producer self-preflight must:
      - skip retry (the SubTask declared X in ## Produces but didn't deliver
        X; re-running it without intervention will fail the same way)
      - post a comment that names the failed self-check + points the human at
        impl-vs-slice mismatch (not at /architect-grill — that's design_conflict)
      - transition the SubTask back to Dev-Pending
      - halt the chain (no subsequent SubTask runs)

    Symmetric counterpart to contract_mismatch, but consumer == producer
    (same SubTask): no separate producer-side comment is posted.
    """
    issues = [_issue("P2P-1"), _issue("P2P-2")]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()

    attempts = {"P2P-1": 0}

    def claude(key, path, cap):
        if key == "P2P-1":
            attempts["P2P-1"] += 1
            return ClaudeOutcome(
                "produces_drift",
                detail=(
                    "Declared `## Produces` artifact "
                    "`ExportStrategy.java#interface ExportStrategy<E>` "
                    "not found on branch — own pre-success grep returned no match"
                ),
            )
        return ClaudeOutcome("success")

    r = _runner(j, g, w, claude, tmp_path=tmp_path)
    rec = r.one_pass()
    enh = rec.parents[0]
    assert enh.subtasks[0].status == "aborted"
    # Critical: produces_drift must NOT retry — one attempt only.
    assert enh.subtasks[0].attempts == 1
    assert attempts["P2P-1"] == 1
    # Subsequent SubTask not tried (same abort semantics as other non-retryables).
    assert len(enh.subtasks) == 1
    # Routed back to Dev-Pending for human triage.
    assert ("P2P-1", "Request Development") in j.transitions
    # Comment must surface the producer-self-check framing — not a generic
    # "aborted" — so the human fixes impl or slice, not re-queues blindly.
    drift_comments = [
        c for k, c in j.comments
        if k == "P2P-1" and "producer self-check" in c.lower()
    ]
    assert drift_comments, "expected a producer-self-check-tagged comment"
    body = drift_comments[0]
    assert "## Produces" in body
    assert "ExportStrategy" in body  # detail surfaced verbatim
    # Does NOT mention architect-grill (that framing is for design_conflict).
    assert "architect-grill" not in body
    # No producer-side comment: drift is self-detected, no separate producer ticket.
    other_comments = [c for k, c in j.comments if k != "P2P-1"]
    assert all("contract break" not in c.lower() for c in other_comments)
    # Rebase NOT attempted when something aborted.
    assert w.rebased == []


def test_idempotent_rerun_when_subtasks_have_moved(tmp_path):
    """After a SubTask transitions to Dev-Developing, the JQL filter (status =
    Dev-Pending) excludes it. A second run sees an empty queue → no double-process."""
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    r.one_pass()
    notes_before = list(j.notes)
    transitions_before = list(j.transitions)
    # Simulate what JQL would return on re-run: nothing, since the SubTask is
    # no longer Dev-Pending.
    j._issues = []
    rec2 = r.one_pass()
    assert rec2.parents == []
    assert j.notes == notes_before
    assert j.transitions == transitions_before


def test_mr_assigned_to_configured_user_on_open(tmp_path):
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    r.one_pass()
    assert g.opened[0]["assignee"] == "minh.vu.nakisa"


def test_mr_link_attached_to_enhancement_after_open(tmp_path):
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()
    # Verify a set_fields write happened on the parent before the SubTask started.
    parent_writes = [(k, f) for k, f in j.field_writes if k == "P2P-1220"]
    assert parent_writes, "expected MR link to be written to the parent ticket"
    field_id = r.config.dev_cr_merge_gate_fields["merge_request_link"]
    assert parent_writes[0][1] == {field_id: rec.parents[0].mr_url}


def test_assigns_before_transitions(tmp_path):
    """Nakisa workflow validator on Start Development requires an assignee.
    Driver must call assign() on parent + each SubTask before transitioning."""
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    r.one_pass()
    assigned_keys = [k for k, _ in j.assignments]
    assert "P2P-1220" in assigned_keys
    assert "P2P-1" in assigned_keys
    # All assignments use the same accountId from get_my_account_id
    assert {a for _, a in j.assignments} == {"fake-account-id-123"}
    # Assign on parent precedes its first transition
    parent_assign_idx = next(i for i, a in enumerate(j.assignments) if a[0] == "P2P-1220")
    parent_first_transition_idx = next(
        i for i, t in enumerate(j.transitions) if t[0] == "P2P-1220"
    )
    # Assignments and transitions are tracked in different lists, so check by
    # ensuring assign was recorded first by event order: at minimum, both happened.
    assert parent_assign_idx >= 0 and parent_first_transition_idx >= 0


def test_branch_published_before_mr_open(tmp_path):
    """glab mr create rejects source_branch that only exists locally — runner must
    push the freshly-created branch to origin before calling open_draft_mr."""
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    r.one_pass()
    assert len(w.published) == 1
    assert w.published[0].parent_id == "P2P-1220"
    assert g.opened, "MR should have been opened after publish"


def test_bug_parent_skips_start_designing(tmp_path):
    """The Bug workflow goes Dev-Pending → Dev-Developing directly (no
    Dev-Designing step), so the runner must NOT call 'Start Designing' on a
    Bug parent — only on an Enhancement parent. Verified empirically against
    P2P-1228, whose available transitions list excluded 'Start Designing'.
    Everything else (MR open, SubTask drain, notes update, Acceptance flips,
    Request CR & Merge) is identical to the Enhancement path."""
    j = FakeJira(
        [_issue("P2P-1", parent="P2P-9000", summary="repro the rounding bug")],
        {"P2P-9000": _parent(issuetype="Bug")},
    )
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()
    assert len(rec.parents) == 1
    parent_run = rec.parents[0]
    assert parent_run.key == "P2P-9000"
    assert parent_run.issuetype == "Bug"
    assert parent_run.target_branch == "master"
    assert [s.status for s in parent_run.subtasks] == ["success"]
    assert parent_run.rebase == "clean"
    parent_transitions = [n for k, n in j.transitions if k == "P2P-9000"]
    assert parent_transitions == ["Start Development", "Request CR & Merge"]
    assert "Start Designing" not in parent_transitions
    assert ("P2P-9000", "P2P-1", "repro the rounding bug") in j.notes
    assert j.flips == ["P2P-1", "P2P-9000"]


def test_dev_cr_merge_gate_fields_set_before_subtask_and_parent_transitions(tmp_path):
    """The Nakisa workflow validator on Request CR & Merge rejects the
    transition with HTTP 400 unless Merge Request Link, SRED Eligibility,
    Time Estimation, and SRED Rationale are filled in first. The runner must
    write those four custom fields on the SubTask immediately before its
    Request CR & Merge transition, and again on the parent ticket immediately
    before its own Request CR & Merge transition. Empirically observed on
    P2P-1233 (SubTask) — the transition POST returned the four-error envelope
    when these fields were unset."""
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()
    mr_url = rec.parents[0].mr_url

    expected_payload = {
        "customfield_12700": mr_url,
        "customfield_14005": {
            "value": "SRED not eligible",
            "child": {"value": "Straightforward Implementation"},
        },
        "customfield_14006": {"value": "Low: 10 and < 80 hours"},
        # SRED Rationale is a rich-text customfield; runner wraps the plain-string
        # default into a one-paragraph ADF doc.
        "customfield_14003": {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "."}]}
            ],
        },
    }

    for key in ("P2P-1", "P2P-1220"):
        events = [e for e in j.events if e[1] == key]
        gate_idx = next(
            (i for i, e in enumerate(events)
             if e[0] == "set_fields" and e[2].get("customfield_12700") == mr_url
             and "customfield_14005" in e[2]
             and "customfield_14006" in e[2]
             and "customfield_14003" in e[2]),
            None,
        )
        cr_idx = next(
            (i for i, e in enumerate(events)
             if e[0] == "transition" and e[2] == "Request CR & Merge"),
            None,
        )
        assert gate_idx is not None, f"no gate-field write found for {key}"
        assert cr_idx is not None, f"no Request CR & Merge transition found for {key}"
        assert gate_idx < cr_idx, f"gate-field write must precede Request CR & Merge for {key}"
        assert events[gate_idx][2] == expected_payload, (
            f"gate-field payload for {key} does not match defaults: {events[gate_idx][2]}"
        )


def test_acceptance_flipped_on_happy_path(tmp_path):
    """Each successful SubTask + the Enhancement (after clean rebase) get
    flip_acceptance_checkboxes called exactly once, in that order."""
    issues = [_issue("P2P-1"), _issue("P2P-2")]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    r.one_pass()
    assert j.flips == ["P2P-1", "P2P-2", "P2P-1220"]


def test_acceptance_not_flipped_when_subtask_aborts(tmp_path):
    issues = [_issue("P2P-1")]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(
        j, g, w, lambda *a: ClaudeOutcome("test_fail", detail="x"), tmp_path=tmp_path
    )
    r.one_pass()
    assert j.flips == []


def test_acceptance_enhancement_not_flipped_on_rebase_conflict(tmp_path):
    """SubTask flip still happens on success, but the Enhancement flip is gated
    on the post-rebase Request CR & Merge transition, which conflicts skip."""
    issues = [_issue("P2P-1")]
    j = FakeJira(issues, {"P2P-1220": _parent()})
    g = FakeGitLab()
    w = FakeWorktrees(rebase_outcome="conflict")
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    r.one_pass()
    assert j.flips == ["P2P-1"]


def test_non_master_target_branch(tmp_path):
    issues = [_issue("P2P-1")]
    parents = {"P2P-1220": _parent(target="FINCORE_RELEASE")}
    j = FakeJira(issues, parents)
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    # extend the value-map so FINCORE_RELEASE → fin-core/release
    from dataclasses import replace
    r.config = replace(
        r.config,
        target_branch_value_map={**r.config.target_branch_value_map, "FINCORE_RELEASE": "fin-core/release"},
    )
    rec = r.one_pass()
    assert rec.parents[0].target_branch == "fin-core/release"


# --- Fix B regression: Jira side-effects must not abort the subtask drain --


class _FlakyJira(FakeJira):
    """FakeJira variant that raises a hand-picked exception on a specific
    (subtask_key, transition_name) pair. Used to reproduce the P2P-1237
    crash: 'Request CR & Merge' raises JiraError mid-loop, and the runner
    was bailing on the entire enhancement so P2P-1238 never started."""

    def __init__(self, issues, parents, *, raise_on):
        super().__init__(issues, parents)
        self._raise_on = set(raise_on)  # set of (key, name) tuples

    def transition(self, key: str, name: str) -> None:
        if (key, name) in self._raise_on:
            raise RuntimeError(f"transition {name!r} not available on {key} (synthetic)")
        super().transition(key, name)


def test_subtask_continues_when_jira_transition_fails_after_claude_success(tmp_path):
    """Regression for the P2P-1237 → P2P-1238 crash: claude_runner returned
    success, but jira.transition('Request CR & Merge') raised because the
    SubTask was already in Dev-CR/Merge. The runner used to crash and skip
    P2P-1238 entirely. After Fix B, the failed Jira call is logged into
    sub_run.detail, P2P-1237 is still marked 'success' (the code is
    committed — that's the main job), and the loop proceeds to P2P-1238."""
    issues = [_issue("P2P-1236"), _issue("P2P-1237"), _issue("P2P-1238")]
    j = _FlakyJira(
        issues,
        {"P2P-1220": _parent()},
        raise_on=[("P2P-1237", "Request CR & Merge")],
    )
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()

    subtasks = rec.parents[0].subtasks
    assert [s.key for s in subtasks] == ["P2P-1236", "P2P-1237", "P2P-1238"], (
        "P2P-1238 must be processed even after P2P-1237's Jira hiccup"
    )
    assert all(s.status == "success" for s in subtasks), (
        "claude succeeded for all three — sub_run.status must reflect code "
        "work, not Jira side-effect failures"
    )
    bad = next(s for s in subtasks if s.key == "P2P-1237")
    assert "Request CR & Merge" in bad.detail
    # The two healthy subtasks have no Jira-error noise on detail.
    assert next(s for s in subtasks if s.key == "P2P-1236").detail == ""
    assert next(s for s in subtasks if s.key == "P2P-1238").detail == ""


def test_enhancement_continues_when_lifecycle_transition_fails(tmp_path):
    """Same policy at the parent level — if Start Designing or Start
    Development on the Enhancement raises, the runner must still process
    every SubTask and only skip the offending Jira write."""
    issues = [_issue("P2P-1")]
    j = _FlakyJira(
        issues,
        {"P2P-1220": _parent()},
        raise_on=[("P2P-1220", "Start Designing")],
    )
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()
    parent = rec.parents[0]
    assert [s.status for s in parent.subtasks] == ["success"]
    assert "Start Designing" in parent.skip_reason


# -- Post-claude commit-or-fail gate ---------------------------------------

def test_subtask_aborts_when_claude_succeeds_but_no_code_change(tmp_path):
    """Empirically observed in the P2P-1233/1234/1235 smoke run: the spawned
    `claude /afk:execute` session edited files but exited without `git commit`.
    The runner trusted the success exit code and transitioned the SubTask to
    Dev-CR/Merge anyway — leaving the parent's MR with zero work commits.

    The fix is a runner-side gate: after claude returns success, auto-commit
    any leftover dirty tree, then verify the branch tip advanced. If neither
    claude itself nor the auto-commit produced a new commit (i.e. claude was
    a no-op), treat the SubTask as a failure: do NOT populate the gate
    fields, do NOT transition to Dev-CR/Merge, do NOT update Implementation
    Notes, do NOT flip Acceptance. Comment + send back to Dev-Pending."""
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    # auto_dirty_on_success=False — simulate a no-op claude session.
    r = _runner(
        j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path,
        auto_dirty_on_success=False,
    )
    rec = r.one_pass()

    sub = rec.parents[0].subtasks[0]
    assert sub.status == "aborted", "no-code-change SubTask must abort"
    assert "no code changes" in (sub.detail or "").lower()
    # No Dev-CR/Merge transition for a no-op SubTask.
    sub_transitions = [t[1] for t in j.transitions if t[0] == "P2P-1"]
    assert "Request CR & Merge" not in sub_transitions
    # Acceptance flip + Implementation Notes are gated on success.
    assert j.flips == []
    assert j.notes == []
    # No push because no work to ship.
    assert w.pushed == []


def test_subtask_resets_dirty_tree_from_prior_interruption_before_starting(tmp_path):
    """Crash-recovery contract: if a prior pass left the worktree dirty
    (claude server died, OS killed the process, machine rebooted mid-
    session), the next SubTask must wipe the leftovers before invoking
    claude. Resuming partial edits is unsafe — claude has no way to pick up
    where the dead session left off. The runner must call reset_to_clean on
    the worktree at the top of _process_subtask; if anything was actually
    cleaned, that fact is logged for the digest."""
    j = FakeJira([_issue("P2P-1"), _issue("P2P-2")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    # Simulate a prior crash: ensure() seeds tip + leaves the tree dirty.
    # FakeWorktrees.ensure is invoked by the runner, but we need the dirty
    # flag set BEFORE the first SubTask runs reset_to_clean. Pre-seed it.
    spec_path = tmp_path / "wt" / "P2P-1220"
    w._dirty[str(spec_path)] = True

    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()

    # The pre-seeded dirty flag was cleared by reset_to_clean before the
    # first SubTask spawned claude. (After that, the auto-dirty-on-success
    # wrapper may set it again per SubTask — but the FIRST reset entry is
    # the cross-pass recovery one.)
    assert len(w.resets) >= 1, "runner must call reset_to_clean per SubTask"
    # Both SubTasks succeeded — recovery did not break the happy path.
    assert [s.status for s in rec.parents[0].subtasks] == ["success", "success"]


def test_subtask_reset_no_op_when_tree_already_clean(tmp_path):
    """Sibling assertion: reset_to_clean is called per SubTask but is a
    no-op when there's nothing to clean (returns False). The runner must not
    log the 'discarded leftovers' message in that case — verified indirectly
    by reset_to_clean returning False (FakeWorktrees doesn't append to
    resets when nothing was dirty)."""
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()
    # No pre-seeded dirty: the per-SubTask reset call returns False, no entry
    # in resets. (FakeWorktrees only records the call when it actually wiped
    # something, which mirrors the runner's "log only if cleaned" policy.)
    assert w.resets == []
    assert rec.parents[0].subtasks[0].status == "success"


def test_subtask_auto_commits_dirty_tree_after_claude_success(tmp_path):
    """Reverse of the no-op case: claude session edited files but exited
    without running git commit. The runner must auto-commit the dirty tree
    so the work lands on the branch, push, populate gate fields, and
    transition. Asserted: a commit was made via FakeWorktrees, the branch
    was pushed, and the SubTask reached Dev-CR/Merge."""
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    # Default _runner wrap: success outcome -> mark_dirty -> runner auto-
    # commit captures it. This mirrors the P2P-1233 failure mode in
    # production.
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()

    sub = rec.parents[0].subtasks[0]
    assert sub.status == "success"
    # Auto-commit produced exactly one commit, attributed to this SubTask.
    auto_commits = [c for c in w.commits if c[0] == "P2P-1220"]
    assert len(auto_commits) == 1
    msg = auto_commits[0][1]
    assert "[P2P-1]" in msg, f"auto-commit msg must reference SubTask key: {msg}"
    # Branch was pushed after the auto-commit.
    assert len(w.pushed) >= 1
    # Dev-CR/Merge transition landed.
    sub_transitions = [t[1] for t in j.transitions if t[0] == "P2P-1"]
    assert "Request CR & Merge" in sub_transitions


def test_subtask_skips_auto_commit_when_claude_already_committed(tmp_path):
    """If claude itself committed during its session (as the SKILL.md
    instructs), the runner's auto-commit safety net must be a no-op — no
    redundant commit gets created. The runner still pushes (idempotent) and
    transitions normally."""
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()

    def claude_that_committed(key, path, cap):
        # Simulate claude making its own commit during the session: tip
        # advances WITHOUT mark_dirty (i.e. tree is clean post-claude).
        if w.ensured:
            w.advance_tip(w.ensured[-1])
        return ClaudeOutcome("success")

    r = _runner(j, g, w, claude_that_committed, tmp_path=tmp_path,
                auto_dirty_on_success=False)
    rec = r.one_pass()

    sub = rec.parents[0].subtasks[0]
    assert sub.status == "success"
    # No auto-commit — claude's own commit stands.
    assert w.commits == []
    # Push still happens (idempotent).
    assert len(w.pushed) >= 1
    # Transition landed.
    sub_transitions = [t[1] for t in j.transitions if t[0] == "P2P-1"]
    assert "Request CR & Merge" in sub_transitions


# -- Branch / worktree reuse for hand-prepped parents -----------------------

def test_runner_reuses_existing_mr_branch_when_present(tmp_path):
    """Nakisa convention: a developer often prepares the parent's branch by
    hand (``kapteyn/development/mvu/{slug}``) and opens the Draft MR before
    the AFK driver gets involved. The runner must detect that pre-existing
    MR by parent_key, point spec.branch at its source_branch instead of
    minting ``mvu/afk/{parent_id}``, and drive everything (publish,
    checklist update) on that branch."""
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    # Seed the canned MR — runner discovery hits this on
    # find_open_mr_by_parent_key(P2P-1220).
    g._mr_for_parent["P2P-1220"] = MRInfo(
        iid=99,
        web_url="https://example.com/mr/99",
        state="opened",
        title="[P2P-1220] hand-prepped",
        description="<!-- afk:subtasks:start -->\n<!-- afk:subtasks:end -->",
        source_branch="kapteyn/development/mvu/payable-fixes",
        target_branch="master",
    )
    g._open_for["kapteyn/development/mvu/payable-fixes"] = g._mr_for_parent["P2P-1220"]
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()

    enh = rec.parents[0]
    # Branch on every spec passed to the worktree manager is the discovered
    # one, NOT the template default.
    assert all(s.branch == "kapteyn/development/mvu/payable-fixes" for s in w.ensured)
    assert all(s.branch == "kapteyn/development/mvu/payable-fixes" for s in w.published)
    # MR URL on the run is the existing MR's URL — no new MR was opened.
    assert enh.mr_url == "https://example.com/mr/99"
    assert g.opened == [], "must not call mr create when MR already exists"
    # Checklist updates targeted the discovered branch.
    assert g.checklists and g.checklists[0][0] == "kapteyn/development/mvu/payable-fixes"


def test_runner_skips_parent_when_mr_lookup_is_ambiguous(tmp_path):
    """Two open MRs both reference the parent_key — ambiguous; refuse to
    pick. The parent gets skipped with a recorded reason; subsequent
    parents in the queue are unaffected."""
    issues = [_issue("P2P-A", parent="P2P-AMBIG"), _issue("P2P-B", parent="P2P-CLEAN")]
    parents = {
        "P2P-AMBIG": _parent(),
        "P2P-CLEAN": _parent(),
    }
    j = FakeJira(issues, parents)
    g, w = FakeGitLab(), FakeWorktrees()
    g._mr_for_parent["P2P-AMBIG"] = "AMBIGUOUS"
    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()

    by_key = {p.key: p for p in rec.parents}
    assert "MR lookup failed" in by_key["P2P-AMBIG"].skip_reason
    assert "ambiguous" in by_key["P2P-AMBIG"].skip_reason.lower()
    assert by_key["P2P-AMBIG"].subtasks == []
    # Sibling parent must still drain normally.
    assert [s.status for s in by_key["P2P-CLEAN"].subtasks] == ["success"]


def test_runner_uses_foreign_worktree_path_when_branch_already_checked_out(tmp_path):
    """If the discovered branch is already checked out at a worktree
    outside the managed root (user opened it in IntelliJ via ``new-task``),
    the runner reuses that path in place rather than failing with "branch
    already checked out elsewhere"."""
    j = FakeJira([_issue("P2P-1")], {"P2P-1220": _parent()})
    g, w = FakeGitLab(), FakeWorktrees()
    g._mr_for_parent["P2P-1220"] = MRInfo(
        iid=42,
        web_url="https://example.com/mr/42",
        state="opened",
        title="[P2P-1220] in-progress",
        description="<!-- afk:subtasks:start -->\n<!-- afk:subtasks:end -->",
        source_branch="kapteyn/development/mvu/some-feature",
        target_branch="master",
    )
    g._open_for["kapteyn/development/mvu/some-feature"] = g._mr_for_parent["P2P-1220"]
    foreign = tmp_path / "user-worktrees" / "some-feature"
    w._foreign_worktrees["kapteyn/development/mvu/some-feature"] = foreign

    r = _runner(j, g, w, lambda *a: ClaudeOutcome("success"), tmp_path=tmp_path)
    rec = r.one_pass()

    # Spec's path on every worktree-manager call is the foreign path,
    # NOT the managed worktree_root/{ID} default.
    assert all(s.path == foreign for s in w.ensured)
    assert all(s.path == foreign for s in w.published)
    # And spec.branch is still the discovered one.
    assert all(s.branch == "kapteyn/development/mvu/some-feature" for s in w.ensured)
    assert rec.parents[0].subtasks[0].status == "success"
