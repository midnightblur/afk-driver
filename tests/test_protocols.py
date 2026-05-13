"""Tests for the IssueTracker + Scm Protocol declarations (SubTask 01).

This SubTask only declares the Protocols. ST02 makes the legacy
``JiraClient`` and ``GitLabClient`` adapters conform; until then,
``isinstance`` against the Protocols must return False so the conformance
gap is visible in CI.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Protocol, get_type_hints

import pytest

from afk_driver.scm_protocol import PrRef, Scm
from afk_driver.tracker_protocol import (
    IssueTracker,
    ParentRef,
    SubIssueRef,
)


# ---------------------------------------------------------------------------
# Protocol shape — runtime_checkable + method names
# ---------------------------------------------------------------------------

# SDD §8 module table row "tracker_protocol" — binding contract.
TRACKER_METHODS = frozenset({
    "list_pickable",
    "get_parent",
    "start_designing",
    "start_developing",
    "request_cr_merge",
    "revert_to_pending",
    "close",
    "comment",
    "splice_notes_block",
    "get_target_branch",
    "list_stuck_subissues",
})

# SDD §8 module table row "scm_protocol" + §9 classDiagram — binding contract.
SCM_METHODS = frozenset({
    "find_open_pr_by_parent",
    "open_draft_pr",
    "update_pr_description",
    "splice_pr_block",
})


def test_issue_tracker_is_a_protocol():
    """The class must derive from typing.Protocol."""
    assert Protocol in IssueTracker.__mro__


def test_scm_is_a_protocol():
    assert Protocol in Scm.__mro__


def test_issue_tracker_is_runtime_checkable():
    """Per SDD §9 classDiagram + Acceptance — isinstance must work at runtime.

    A Protocol decorated with @runtime_checkable carries the
    _is_runtime_protocol marker; the isinstance() probe below also proves
    the check itself does not raise TypeError (which is what an
    undecorated Protocol would raise).
    """
    assert getattr(IssueTracker, "_is_runtime_protocol", False) is True
    # Sanity probe — must not raise. ``object()`` lacks every method, so
    # the answer is False, but the call itself proves runtime_checkable.
    assert isinstance(object(), IssueTracker) is False


def test_scm_is_runtime_checkable():
    assert getattr(Scm, "_is_runtime_protocol", False) is True
    assert isinstance(object(), Scm) is False


def test_issue_tracker_declares_eleven_methods():
    """Exactly the eleven names from SDD §8 row tracker_protocol."""
    declared = {
        name for name in vars(IssueTracker)
        if not name.startswith("_") and callable(vars(IssueTracker)[name])
    }
    assert declared == TRACKER_METHODS


def test_scm_declares_four_methods():
    """Exactly the four names from SDD §8 row scm_protocol + §9 classDiagram."""
    declared = {
        name for name in vars(Scm)
        if not name.startswith("_") and callable(vars(Scm)[name])
    }
    assert declared == SCM_METHODS


# ---------------------------------------------------------------------------
# Value-object shape — SDD §6 erDiagram
# ---------------------------------------------------------------------------


def test_sub_issue_ref_fields_match_child_work_unit():
    """SDD §6 erDiagram ChildWorkUnit: id, parent_id, scope_globs."""
    hints = get_type_hints(SubIssueRef)
    assert set(hints) == {"id", "parent_id", "scope_globs"}


def test_parent_ref_fields_match_parent_entity():
    """SDD §6 erDiagram Parent: id, backend, title."""
    hints = get_type_hints(ParentRef)
    assert set(hints) == {"id", "backend", "title"}


def test_pr_ref_fields_match_draft_pull_request_entity():
    """SDD §6 erDiagram DraftPullRequest: source_branch, target_branch, url."""
    hints = get_type_hints(PrRef)
    assert set(hints) == {"source_branch", "target_branch", "url"}


def test_value_objects_are_frozen():
    """Aggregate-root value objects are immutable — runner caches them."""
    ref = SubIssueRef(id="P2P-1", parent_id="P2P-0")
    with pytest.raises((AttributeError, TypeError)):
        ref.id = "P2P-99"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pure-type discipline — no I/O imports in either Protocol module
# ---------------------------------------------------------------------------

FORBIDDEN_IO_MODULES = frozenset({
    "subprocess",
    "urllib",
    "urllib.request",
    "urllib.parse",
    "urllib.error",
    "requests",
    "http",
    "http.client",
    "socket",
    "httpx",
})


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
                names.add(node.module.split(".")[0])
    return names


def test_tracker_protocol_has_no_io_imports():
    """SDD §8 dependency DAG — protocol modules sit in the domain ring and
    must not import I/O. Concrete adapters do the I/O.
    """
    from afk_driver import tracker_protocol
    path = Path(tracker_protocol.__file__)
    found = _imports_in(path) & FORBIDDEN_IO_MODULES
    assert not found, f"tracker_protocol.py imports forbidden I/O: {found}"


def test_scm_protocol_has_no_io_imports():
    from afk_driver import scm_protocol
    path = Path(scm_protocol.__file__)
    found = _imports_in(path) & FORBIDDEN_IO_MODULES
    assert not found, f"scm_protocol.py imports forbidden I/O: {found}"


# ---------------------------------------------------------------------------
# Legacy adapters do NOT yet conform — ST02 closes this gap
# ---------------------------------------------------------------------------


def _legacy_jira_client():
    """Build a JiraClient instance without touching the network."""
    from afk_driver.jira_client import JiraClient, JiraConfig

    class _NullTransport:
        def send(self, *a, **kw):  # pragma: no cover - never called
            raise AssertionError("transport must not be invoked in this test")

    cfg = JiraConfig(base_url="https://example.invalid", email="x@y", api_token="t")
    return JiraClient(cfg, _NullTransport())


def test_jira_client_does_not_yet_conform_to_issue_tracker():
    """ST01 only declares the Protocols. ST02 will rename / add methods on
    JiraClient so it conforms. Until then, isinstance must return False so
    a future accidental "looks like it conforms" regression is visible.
    """
    instance = _legacy_jira_client()
    assert not isinstance(instance, IssueTracker), (
        "JiraClient unexpectedly conforms to IssueTracker — ST02 should be "
        "the SubTask that makes this true, not ST01."
    )


def test_jira_client_is_missing_phase_semantic_methods():
    """Structural assertion of the same gap: the phase-semantic method
    names declared by the IssueTracker Protocol are NOT yet present on
    the legacy adapter (it still uses ``transition(key, name)``).
    """
    from afk_driver.jira_client import JiraClient
    phase_methods = {
        "list_pickable",
        "start_designing",
        "start_developing",
        "request_cr_merge",
        "revert_to_pending",
        "splice_notes_block",
        "get_target_branch",
        "list_stuck_subissues",
    }
    present = {m for m in phase_methods if hasattr(JiraClient, m)}
    assert not present, (
        f"JiraClient already has phase-semantic methods {present}; ST02 was "
        f"expected to introduce them, not ST01."
    )


def test_gitlab_client_does_not_yet_conform_to_scm():
    """Symmetric assertion for the SCM side — GitLabClient still exposes
    glab-CLI-shaped methods (``find_mr_by_branch``, ``open_draft_mr``,
    ``update_subtasks_checklist``), not the Protocol's PR-semantic names.
    """
    from afk_driver.gitlab_client import GitLabClient
    instance = GitLabClient(runner=lambda args: None)  # type: ignore[arg-type]
    assert not isinstance(instance, Scm), (
        "GitLabClient unexpectedly conforms to Scm — ST02 should close this "
        "gap, not ST01."
    )
