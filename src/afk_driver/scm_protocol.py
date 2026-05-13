"""Strategy interface for SCM / PR providers (GitLab, GitHub).

Pure type module — no I/O, no subprocess, no urllib, no requests, no ``gh``
or ``glab``. Concrete adapters (``gitlab_client.GitLabClient``,
``github_pr_client``) live in the adapter ring and depend inward on this
Protocol; ``runner.py`` depends only on the Protocol. See SDD §3 (L2
service boundaries — Strategy seam) and §8 (L7 module table row
``scm_protocol``).

The Protocol is ``runtime_checkable`` so tests can assert conformance via
``isinstance(client, Scm)`` — see SDD §9 Strategy classDiagram.

``PrRef`` materialises the SDD §6 erDiagram entity ``DraftPullRequest`` as a
transport-agnostic record the runner consumes (a GitLab MR and a GitHub PR
collapse to the same shape at this boundary).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PrRef:
    """Backend-agnostic reference to a Draft MR / PR.

    Mirrors SDD §6 erDiagram ``DraftPullRequest``: ``source_branch``,
    ``target_branch``, and ``url`` (the canonical web URL — GitLab
    ``web_url`` or GitHub ``html_url``).
    """

    source_branch: str
    target_branch: str
    url: str


@runtime_checkable
class Scm(Protocol):
    """Strategy interface for SCM / PR providers.

    Four methods named in SDD §8 module table row ``scm_protocol`` and the
    SDD §9 Strategy classDiagram. Method names are PR-semantic so the same
    Protocol fits both ``glab mr ...`` and ``gh pr ...`` adapters.
    """

    def find_open_pr_by_parent(self, parent_id: str) -> PrRef | None:
        """Return the single open MR/PR referencing ``parent_id`` (by title
        prefix convention — ``[KEY]`` for Jira, ``[#N]`` for GitHub), or
        ``None`` if no open MR/PR exists. Raises on >1 match (ambiguous —
        SDD §5 idempotency table).
        """
        ...

    def open_draft_pr(self, spec: object) -> PrRef:
        """Open a Draft MR/PR. ``spec`` is an adapter-specific request
        record (e.g. ``OpenDraftPrSpec`` declared by each concrete client);
        accepting ``object`` keeps this Protocol module free of adapter
        details while still pinning the return shape. Idempotent: if an
        open MR/PR already exists for the given source branch the adapter
        returns it instead of creating a duplicate (SDD §5 idempotency
        table — ``(repo, source_branch)``).
        """
        ...

    def update_pr_description(self, branch: str, body: str) -> None:
        """Replace the MR/PR description for ``branch`` with ``body`` in
        full. Used by the runner to write the rendered subtasks-checklist
        block on first MR open.
        """
        ...

    def splice_pr_block(self, branch: str, body: str) -> None:
        """Idempotently replace the auto-maintained block in the MR/PR
        description (between ``afk:subtasks:start`` / ``...:end`` markers)
        with ``body``. Outside-marker content is preserved byte-identical
        (SDD §5 idempotency table).
        """
        ...
