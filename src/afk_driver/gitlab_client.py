"""GitLab Draft MR client via the ``glab`` CLI.

All operations are subprocess calls; no direct REST. The ``GlabRunner``
callable is injected so tests can stub command outputs.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

from afk_driver.scm_protocol import PrRef, Scm
from afk_driver.section_splice import SectionMarkerMissing, marker_id_text


_SUBTASKS_MARKER_ID = "subtasks"


class GitLabError(RuntimeError):
    """Raised when ``glab`` exits non-zero or returns unparseable output."""


@dataclass(frozen=True)
class MRInfo:
    iid: int
    web_url: str
    state: str
    title: str
    description: str
    source_branch: str
    target_branch: str


@dataclass(frozen=True)
class SubtaskItem:
    key: str
    summary: str
    done: bool


@dataclass(frozen=True)
class OpenDraftPrSpec:
    """Adapter-specific request record consumed by ``Scm.open_draft_pr``
    (SDD §9 Strategy classDiagram). Keeps the cross-backend Protocol module
    free of GitLab-specific fields while pinning the inputs ``GitLabClient``
    needs to call ``glab mr create``.
    """

    source_branch: str
    target_branch: str
    title: str
    description: str
    assignee: Optional[str] = None


GlabRunner = Callable[[list[str]], subprocess.CompletedProcess]


def default_runner(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["glab", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


class GitLabClient(Scm):
    # ST02: explicit Protocol nominal subtype — see SDD §8 row "gitlab_client",
    # §9 Strategy classDiagram. The four Protocol methods below delegate to
    # the existing glab-CLI operations and return ``PrRef`` shapes instead of
    # ``MRInfo``. Legacy methods stay for back-compat — runner.py keeps
    # calling them until ST07's refactor.

    def __init__(self, runner: GlabRunner = default_runner):
        self._run = runner

    def find_mr_by_branch(self, branch: str) -> Optional[MRInfo]:
        proc = self._run(["mr", "view", branch, "--output", "json"])
        if proc.returncode != 0:
            stderr = proc.stderr.lower()
            if "not found" in stderr or "no open merge request" in stderr or "404" in stderr:
                return None
            raise GitLabError(f"glab mr view {branch} failed: {proc.stderr.strip()}")
        return _parse_mr(proc.stdout)

    def find_open_mr_by_parent_key(self, parent_key: str) -> Optional[MRInfo]:
        """Look up the open MR whose title references ``parent_key`` (e.g.
        ``[P2P-1229]``). Used by the runner for branch discovery when the
        user opened the MR by hand against a non-template branch name (the
        Nakisa convention is ``kapteyn/development/mvu/{slug}``).

        ``--search`` matches both title and description, so the title-contains
        filter is re-applied client-side to avoid false positives from
        descriptions that merely mention the key. ``-A`` includes any state;
        only ``opened`` MRs (which covers Draft) are kept.

        Returns ``None`` for zero matches. Raises ``GitLabError`` for >1 to
        force the runner to skip the parent rather than guess.
        """
        proc = self._run(
            ["mr", "list", "--search", parent_key, "-A", "-F", "json", "--per-page", "100"]
        )
        if proc.returncode != 0:
            raise GitLabError(
                f"glab mr list --search {parent_key} failed: {proc.stderr.strip()}"
            )
        try:
            items = json.loads(proc.stdout) if proc.stdout.strip() else []
        except json.JSONDecodeError as e:
            raise GitLabError(
                f"glab mr list returned non-JSON: {proc.stdout[:200]}"
            ) from e
        if not isinstance(items, list):
            raise GitLabError(
                f"glab mr list expected JSON array, got {type(items).__name__}"
            )
        matches = [
            mr for mr in items
            if str(mr.get("state", "")).lower() == "opened"
            and parent_key in str(mr.get("title", ""))
        ]
        if not matches:
            return None
        if len(matches) > 1:
            iids = sorted(int(m.get("iid", 0)) for m in matches)
            raise GitLabError(
                f"ambiguous: {len(matches)} open MRs match parent {parent_key} "
                f"(iids={iids}); refusing to pick one"
            )
        return _parse_mr(json.dumps(matches[0]))

    def open_draft_mr(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        assignee: Optional[str] = None,
    ) -> MRInfo:
        existing = self.find_mr_by_branch(source_branch)
        if existing is not None:
            return existing
        args = [
            "mr", "create",
            "--draft",
            "--source-branch", source_branch,
            "--target-branch", target_branch,
            "--title", title,
            "--description", description,
            "--yes",
        ]
        if assignee:
            args.extend(["--assignee", assignee])
        proc = self._run(args)
        if proc.returncode != 0:
            raise GitLabError(f"glab mr create failed: {proc.stderr.strip()}")
        # Re-query: glab mr create's stdout shape varies; canonical view is via mr view.
        mr = self.find_mr_by_branch(source_branch)
        if mr is None:
            raise GitLabError(f"glab mr create succeeded but mr view {source_branch} returned None")
        return mr

    def update_description(self, branch: str, new_description: str) -> None:
        proc = self._run(["mr", "update", branch, "--description", new_description])
        if proc.returncode != 0:
            raise GitLabError(f"glab mr update {branch} failed: {proc.stderr.strip()}")

    # ------------------------------------------------------------------
    # Scm Protocol conformance (ST02 — typing/shape only)
    # ------------------------------------------------------------------
    # Method shapes from src/afk_driver/scm_protocol.py. ``PrRef`` is the
    # cross-backend reduction of ``MRInfo`` (source_branch / target_branch /
    # url). Legacy methods (``find_mr_by_branch``, ``open_draft_mr``,
    # ``update_description``, ``update_subtasks_checklist``) stay — runner.py
    # keeps calling them until ST07's refactor.

    def find_open_pr_by_parent(self, parent_id: str) -> PrRef | None:
        """Protocol alias for ``find_open_mr_by_parent_key`` — returns the
        cross-backend ``PrRef`` shape (or ``None``).
        """
        mr = self.find_open_mr_by_parent_key(parent_id)
        return _pr_ref_from_mr(mr) if mr is not None else None

    def open_draft_pr(self, spec: object) -> PrRef:
        """Open a Draft MR. ``spec`` must be an ``OpenDraftPrSpec`` (declared
        in this module) with ``source_branch`` / ``target_branch`` / ``title``
        / ``description`` / optional ``assignee``. Delegates to the existing
        ``open_draft_mr`` kwargs path; reduces the returned ``MRInfo`` to
        ``PrRef``.
        """
        if not isinstance(spec, OpenDraftPrSpec):
            raise TypeError(
                "GitLabClient.open_draft_pr requires an OpenDraftPrSpec; "
                f"got {type(spec).__name__}"
            )
        mr = self.open_draft_mr(
            source_branch=spec.source_branch,
            target_branch=spec.target_branch,
            title=spec.title,
            description=spec.description,
            assignee=spec.assignee,
        )
        return _pr_ref_from_mr(mr)

    def update_pr_description(self, branch: str, body: str) -> None:
        """Protocol alias for ``update_description`` — replaces the MR
        description for ``branch`` with ``body`` in full.
        """
        self.update_description(branch, body)

    def splice_pr_block(self, branch: str, body: str) -> None:
        """Idempotently replace the auto-maintained ``afk:subtasks`` block in
        the MR description with ``body`` (pre-rendered). The legacy
        ``update_subtasks_checklist`` takes a list of ``SubtaskItem`` and
        renders inside; this Protocol method takes the rendered string so the
        rendering layer is backend-agnostic in ST07's runner. Behaviour is
        otherwise identical — splice via ``splice_marker_block``, only PUT if
        the description changed.
        """
        existing = self.find_mr_by_branch(branch)
        if existing is None:
            raise GitLabError(f"no MR open for branch {branch}")
        new_desc = splice_marker_block(
            existing.description,
            body,
            marker_id=_SUBTASKS_MARKER_ID,
            create_if_missing=True,
        )
        if new_desc != existing.description:
            self.update_description(branch, new_desc)

    def update_subtasks_checklist(self, branch: str, items: list[SubtaskItem]) -> MRInfo:
        existing = self.find_mr_by_branch(branch)
        if existing is None:
            raise GitLabError(f"no MR open for branch {branch}")
        block_body = _render_subtasks_block(items)
        # ``create_if_missing=True``: ``open_draft_mr`` does not yet inject the
        # marker pair into a fresh MR's description, so the very first
        # checklist update after MR creation must be permissive. After that
        # call, the markers are in place and subsequent updates are
        # effectively strict (``find_mr_by_branch`` would surface any drift
        # via missing markers, but the splicer would just re-create them).
        new_desc = splice_marker_block(
            existing.description,
            block_body,
            marker_id=_SUBTASKS_MARKER_ID,
            create_if_missing=True,
        )
        if new_desc != existing.description:
            self.update_description(branch, new_desc)
        return MRInfo(
            iid=existing.iid,
            web_url=existing.web_url,
            state=existing.state,
            title=existing.title,
            description=new_desc,
            source_branch=existing.source_branch,
            target_branch=existing.target_branch,
        )


def _pr_ref_from_mr(mr: MRInfo) -> PrRef:
    """Reduce an ``MRInfo`` to the cross-backend ``PrRef`` shape (SDD §6
    erDiagram ``DraftPullRequest``)."""
    return PrRef(
        source_branch=mr.source_branch,
        target_branch=mr.target_branch,
        url=mr.web_url,
    )


def _render_subtasks_block(items: list[SubtaskItem]) -> str:
    """Render SubtaskItem list as the bullet body that lives between markers.
    Empty list → empty string (splicer will emit ``start\\nend`` with nothing
    in between)."""
    return "\n".join(
        f"- [{'x' if i.done else ' '}] {i.key} {i.summary}".rstrip() for i in items
    )


def splice_marker_block(
    description: str,
    block_body: str,
    *,
    marker_id: str,
    create_if_missing: bool = False,
) -> str:
    """Replace the content between the ``afk:{marker_id}:start`` /
    ``afk:{marker_id}:end`` HTML-comment markers with ``block_body``.

    Behaviour:
    - Both markers present, in order: returns ``before + new_block + after``
      with ``before`` and ``after`` (everything outside the markers) preserved
      byte-identical.
    - Both markers absent: if ``create_if_missing=True``, appends a fresh
      marker block at the end of the description (separated by a blank line if
      the existing description doesn't already end with ``\\n\\n``).
      Otherwise raises ``SectionMarkerMissing``.
    - One marker present without its mate, or end before start: raises
      ``SectionMarkerMissing`` even when ``create_if_missing=True``. Corrupt
      state — auto-repair would risk losing whatever the survivor anchors.
    """
    start_id, end_id = marker_id_text(marker_id)
    start_marker = f"<!-- {start_id} -->"
    end_marker = f"<!-- {end_id} -->"
    new_block = (
        f"{start_marker}\n{block_body}\n{end_marker}"
        if block_body
        else f"{start_marker}\n{end_marker}"
    )
    start = description.find(start_marker)
    end = description.find(end_marker)
    if start == -1 and end == -1:
        if not create_if_missing:
            raise SectionMarkerMissing(
                f"marker pair {marker_id!r} absent (create_if_missing=False)"
            )
        sep = "\n\n" if description and not description.endswith("\n\n") else ""
        return description + sep + new_block + "\n"
    if start == -1 or end == -1 or end < start:
        raise SectionMarkerMissing(
            f"marker pair {marker_id!r} malformed "
            f"(start={start} end={end})"
        )
    end_full = end + len(end_marker)
    return description[:start] + new_block + description[end_full:]


def _parse_mr(stdout: str) -> MRInfo:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise GitLabError(f"glab returned non-JSON: {stdout[:200]}") from e
    return MRInfo(
        iid=int(data.get("iid", 0)),
        web_url=str(data.get("web_url", "")),
        state=str(data.get("state", "")),
        title=str(data.get("title", "")),
        description=str(data.get("description", "")),
        source_branch=str(data.get("source_branch", "")),
        target_branch=str(data.get("target_branch", "")),
    )
