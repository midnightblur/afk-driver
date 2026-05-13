"""Strategy interface for issue trackers (Jira, GitHub).

Pure type module — no I/O, no subprocess, no urllib, no requests, no ``gh``.
Concrete adapters (``jira_client.JiraClient``, ``github_issues_client``) live
in the adapter ring and depend inward on this Protocol; ``runner.py`` depends
only on the Protocol, not on any concrete client. See SDD §3 (L2 service
boundaries — Strategy seam) and §8 (L7 module table row ``tracker_protocol``).

The Protocol is ``runtime_checkable`` so tests can assert conformance via
``isinstance(client, IssueTracker)`` — see SDD §9 Strategy classDiagram.

Value objects (``SubIssueRef``, ``ParentRef``) materialise the SDD §6
erDiagram entities ``ChildWorkUnit`` and ``Parent`` as transport-agnostic
records the runner consumes. Return-type shapes for IDs / labels / statuses
intentionally use plain ``str`` so a Jira ``ENH-1234`` key and a GitHub
``owner/repo#42`` reference both fit the same surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SubIssueRef:
    """Backend-agnostic reference to a sub-issue / SubTask.

    Mirrors SDD §6 erDiagram ``ChildWorkUnit``: ``id`` is the Jira SUBKEY
    (``P2P-1234``) or GitHub coordinate (``owner/repo#42``); ``parent_id``
    is the owning ``Parent``'s id; ``scope_globs`` is the parsed
    ``## Scope:`` glob list from the SubTask body (empty tuple if absent).
    """

    id: str
    parent_id: str
    scope_globs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParentRef:
    """Backend-agnostic reference to a parent (Enhancement / Bug / Issue).

    Mirrors SDD §6 erDiagram ``Parent``: ``id`` is the Jira ENH-ID or GitHub
    ``owner/repo#N``; ``backend`` is the discriminator (``"jira"`` or
    ``"github"``); ``title`` is the human-readable summary line.
    """

    id: str
    backend: str
    title: str


@runtime_checkable
class IssueTracker(Protocol):
    """Strategy interface for issue trackers.

    Eleven methods named in SDD §8 module table row ``tracker_protocol``.
    Method names are phase-semantic (``start_designing`` etc.) rather than
    tracker-specific transition labels so the same Protocol fits both the
    Jira ``Start Designing`` workflow transition and the GitHub
    ``afk:designing`` mutually-exclusive label flip (SDD §6 phase-label
    state machine, ADR-0002).
    """

    def list_pickable(self) -> list[SubIssueRef]:
        """Return all AFK-eligible sub-issues currently in the pending phase
        (Jira ``Dev-Pending`` + ``afk-agents`` label; GitHub ``afk:pending``
        + ``afk-agents`` labels, assignee = me).
        """
        ...

    def get_parent(self, child_id: str) -> ParentRef:
        """Resolve the parent reference for a sub-issue."""
        ...

    def start_designing(self, child_id: str) -> None:
        """Advance the sub-issue from pending to the designing phase."""
        ...

    def start_developing(self, child_id: str) -> None:
        """Advance the sub-issue from designing to the developing phase."""
        ...

    def request_cr_merge(self, child_id: str) -> None:
        """Advance the sub-issue from developing to the cr-merge phase."""
        ...

    def revert_to_pending(self, child_id: str) -> None:
        """Move the sub-issue back to the pending phase (abort path, or
        sweeper recovery for a crashed-mid-flight run — SDD §7 use-case 3).
        """
        ...

    def close(self, child_id: str, reason: str) -> None:
        """Close the sub-issue terminally (``reason`` distinguishes
        ``completed`` from ``not_planned``).
        """
        ...

    def comment(self, child_id: str, body: str) -> None:
        """Post a Markdown comment on the sub-issue."""
        ...

    def splice_notes_block(self, parent_id: str, body: str) -> None:
        """Idempotently replace the parent's auto-maintained Implementation
        Notes block. Splicer guarantees byte-identical preservation of body
        outside the marker pair (SDD §5 idempotency table).
        """
        ...

    def get_target_branch(self, parent_id: str) -> str:
        """Return the resolved target branch for a parent. Cached by the
        runner on first read; immutable mid-flight (SDD §6 invariants).
        """
        ...

    def list_stuck_subissues(self) -> list[SubIssueRef]:
        """Pre-flight sweeper input — sub-issues whose phase label is one of
        ``{designing, developing, cr-merge}`` from a prior crashed run
        (SDD §7 use-case 3, ADR-0005).
        """
        ...
