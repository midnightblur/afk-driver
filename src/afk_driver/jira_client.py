"""Jira REST client for the AFK driver.

Encapsulates the operations the runner needs: JQL search, transition listing /
execution, parent-ticket field reads (the parent may be an Enhancement or a
Bug — they share the Target-Branch custom field but their workflows diverge
at Dev-Pending: Enhancement adds a Dev-Designing step, Bug skips it),
idempotent edits to the ``## Implementation Notes (auto-maintained)`` block
of a description, and markdown comment posting.

HTTP is driven through an injected ``HttpTransport`` so tests can substitute a
fake. The real transport (``UrllibTransport``) is in this module too but is
optional — callers can build their own (e.g. ``requests``-backed).
"""

from __future__ import annotations

import base64
import copy
import json as _json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol

from afk_driver import jira_section


_NOTES_HEADER_TEXT = "Implementation Notes (auto-maintained)"
_NOTES_MARKER_ID = "notes"

# Static map: transition name -> the workflow status that transition lands on.
# Used by ``JiraClient.transition`` to make repeat calls idempotent — if the
# named transition isn't in the current candidate list AND the issue is
# already at the expected target, the call is a no-op instead of an error.
# Confirmed against the Nakisa workflow as it appears on P2P (rm-release).
# Unknown transition names still raise — only entries here are auto-skipped.
_TRANSITION_TARGET_STATUS: Mapping[str, str] = {
    "Start Designing": "Dev-Designing",
    "Start Development": "Dev-Developing",
    "Request CR & Merge": "Dev-CR/Merge",
    "Request Development": "Dev-Pending",
}


class JiraError(RuntimeError):
    """Raised when the Jira API returns an unexpected response."""


@dataclass(frozen=True)
class Transition:
    id: str
    name: str
    to_status: str


@dataclass(frozen=True)
class IssueSummary:
    key: str
    summary: str
    status: str
    issuetype: str
    parent_key: Optional[str]
    labels: tuple[str, ...]
    fix_versions: tuple[str, ...]


@dataclass(frozen=True)
class JiraConfig:
    base_url: str
    email: str
    api_token: str
    parent_fields: Mapping[str, str] = field(
        default_factory=lambda: {
            "target_branch": "customfield_13706",
        }
    )


class HttpTransport(Protocol):
    def send(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict] = None,
        params: Optional[Mapping[str, str]] = None,
    ) -> dict: ...


class UrllibTransport:
    """stdlib urllib-backed transport. Builds Basic auth from email + API token."""

    def __init__(self, base_url: str, email: str, api_token: str):
        self._base = base_url.rstrip("/")
        creds = f"{email}:{api_token}".encode("utf-8")
        self._auth = b"Basic " + base64.b64encode(creds)

    def send(self, method, path, *, json_body=None, params=None):
        url = self._base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body_bytes = _json.dumps(json_body).encode("utf-8") if json_body is not None else None
        req = urllib.request.Request(url, data=body_bytes, method=method)
        req.add_header("Authorization", self._auth.decode("ascii"))
        req.add_header("Accept", "application/json")
        if body_bytes is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise JiraError(f"{method} {path} -> {e.code}: {e.read().decode('utf-8', 'replace')}") from e
        if not raw:
            return {}
        return _json.loads(raw.decode("utf-8"))


class JiraClient:
    def __init__(self, config: JiraConfig, transport: HttpTransport):
        self._cfg = config
        self._http = transport
        # S4 — per-parent-key lock for ``update_implementation_notes``.
        # The splice is read-modify-write against the parent description;
        # without serialization, two SubTasks finishing concurrently could
        # both read the same baseline ADF, splice their bullets, and the
        # second PUT would clobber the first. The runner is currently
        # single-threaded (``one_pass`` processes parents and SubTasks
        # sequentially) so the race is latent in production, but locking
        # here unblocks future parallelization within a single runner
        # process. Cross-process races (two runners on different machines
        # writing to the same parent) remain — Jira's REST API has no
        # if-match for description fields, so a true CAS is impossible
        # against the server. Single-runner is the practical scope.
        self._notes_locks: dict[str, threading.Lock] = {}
        self._notes_locks_guard = threading.Lock()

    def _acquire_notes_lock(self, parent_key: str) -> threading.Lock:
        """Get-or-create the per-parent-key lock for description splices."""
        with self._notes_locks_guard:
            lock = self._notes_locks.get(parent_key)
            if lock is None:
                lock = threading.Lock()
                self._notes_locks[parent_key] = lock
            return lock

    def search(self, jql: str, *, max_results: int = 100) -> list[IssueSummary]:
        body = {
            "jql": jql,
            "maxResults": max_results,
            "fields": [
                "summary", "status", "issuetype", "parent", "labels", "fixVersions",
            ],
        }
        resp = self._http.send("POST", "/rest/api/3/search/jql", json_body=body)
        out: list[IssueSummary] = []
        for issue in resp.get("issues", []):
            f = issue.get("fields", {})
            parent = f.get("parent")
            out.append(IssueSummary(
                key=issue["key"],
                summary=f.get("summary", ""),
                status=(f.get("status") or {}).get("name", ""),
                issuetype=(f.get("issuetype") or {}).get("name", ""),
                parent_key=parent.get("key") if parent else None,
                labels=tuple(f.get("labels") or ()),
                fix_versions=tuple(v.get("name", "") for v in (f.get("fixVersions") or ())),
            ))
        return out

    def get_parent_fields(self, key: str) -> dict[str, Any]:
        """Return logical-name-keyed dict of the parent-ticket fields the runner
        cares about. Parent may be an Enhancement or a Bug — both share the
        same Nakisa workflow and Target-Branch custom field.

        Always includes 'status', 'issuetype', 'fix_versions', 'components',
        plus every entry in ``config.parent_fields`` (logical_name ->
        custom-field id).
        """
        wanted_ids = list(self._cfg.parent_fields.values())
        fields_csv = ",".join(
            ["summary", "status", "issuetype", "fixVersions", "components", *wanted_ids]
        )
        resp = self._http.send(
            "GET", f"/rest/api/3/issue/{key}", params={"fields": fields_csv}
        )
        f = resp.get("fields", {})
        out: dict[str, Any] = {
            "summary": f.get("summary", ""),
            "status": (f.get("status") or {}).get("name", ""),
            "issuetype": (f.get("issuetype") or {}).get("name", ""),
            "fix_versions": [v.get("name", "") for v in (f.get("fixVersions") or [])],
            "components": [c.get("name", "") for c in (f.get("components") or [])],
        }
        for logical, cf_id in self._cfg.parent_fields.items():
            out[logical] = f.get(cf_id)
        return out

    def list_transitions(self, key: str) -> list[Transition]:
        resp = self._http.send("GET", f"/rest/api/3/issue/{key}/transitions")
        out: list[Transition] = []
        for t in resp.get("transitions", []):
            out.append(Transition(
                id=str(t["id"]),
                name=t["name"],
                to_status=(t.get("to") or {}).get("name", ""),
            ))
        return out

    def transition(self, key: str, transition_name: str) -> bool:
        """Run the named transition on ``key``. Returns True if a transition
        actually fired, False if it was a no-op because the issue is already
        at the expected target status (idempotent skip).

        Idempotency rule: when ``transition_name`` is missing from the current
        candidate list, fetch the issue's status. If it matches
        ``_TRANSITION_TARGET_STATUS[transition_name]``, treat the call as
        already-done. This prevents a prior crashed pass (or a Jira workflow
        post-function that auto-advanced the issue) from blowing up the next
        run on a transition the issue has already completed.
        """
        candidates = self.list_transitions(key)
        match = next((t for t in candidates if t.name == transition_name), None)
        if match is None:
            expected = _TRANSITION_TARGET_STATUS.get(transition_name)
            if expected is not None:
                current = self._fetch_status(key)
                if current == expected:
                    return False
            available = ", ".join(t.name for t in candidates) or "(none)"
            raise JiraError(
                f"transition {transition_name!r} not available on {key}; available: {available}"
            )
        self._http.send(
            "POST",
            f"/rest/api/3/issue/{key}/transitions",
            json_body={"transition": {"id": match.id}},
        )
        return True

    def _fetch_status(self, key: str) -> str:
        resp = self._http.send(
            "GET", f"/rest/api/3/issue/{key}", params={"fields": "status"}
        )
        return ((resp.get("fields") or {}).get("status") or {}).get("name", "")

    def update_implementation_notes(
        self, parent_key: str, subtask_key: str, bullet_text: str
    ) -> None:
        """Idempotently insert/replace one ``(SUBTASK_KEY) ...`` bullet inside
        the auto-maintained Implementation Notes block on the parent issue's
        description.

        The block lives inside an ADF marker pair (``afk:notes:start`` /
        ``afk:notes:end`` — see ``CONTEXT.md``). The decorative
        ``## Implementation Notes (auto-maintained)`` heading lives *inside*
        the marker region, owned by this method's payload — not by the
        splicer. Body blocks above and below the marker region are
        preserved byte-identical via ``jira_section.splice_in_adf``.

        Migration: parents written by the pre-marker driver have a top-level
        ``## Implementation Notes (auto-maintained)`` heading + bulletList
        without markers. ``_strip_legacy_notes_heading_block`` detects that
        shape, lifts the existing bullets out, and removes the legacy nodes
        so the next splice creates the marker form fresh. After all live
        ``afk-agents`` parents have been written-through once, this fallback
        becomes dead code.

        Concurrency: serialized per ``parent_key`` via
        ``_acquire_notes_lock`` (S4 closure). Two concurrent calls for the
        same parent are guaranteed not to clobber each other; concurrent
        calls for *different* parents proceed in parallel. Cross-process
        races (multiple runner processes targeting the same parent) are
        not protected — Jira's REST API offers no if-match primitive on
        description fields, so a true CAS against the server is
        impossible. Single-runner-process is the supported scope.
        """
        with self._acquire_notes_lock(parent_key):
            resp = self._http.send(
                "GET", f"/rest/api/3/issue/{parent_key}", params={"fields": "description"}
            )
            adf = (resp.get("fields") or {}).get("description") or {
                "type": "doc",
                "version": 1,
                "content": [],
            }

            inside = jira_section.read_block_in_adf(adf, marker_id=_NOTES_MARKER_ID)
            if inside is not None:
                existing_items = _bullets_from_block_nodes(inside)
                adf_for_splice = adf
            else:
                existing_items, adf_for_splice = _strip_legacy_notes_heading_block(adf)

            new_items = _merge_notes_bullet(existing_items, subtask_key, bullet_text)
            block_nodes = [
                _make_heading2(_NOTES_HEADER_TEXT),
                *jira_section.render_bullets_adf(new_items),
            ]
            new_adf, changed = jira_section.splice_in_adf(
                adf_for_splice,
                block_nodes,
                marker_id=_NOTES_MARKER_ID,
                create_if_missing=True,
            )
            if not changed:
                return
            self._http.send(
                "PUT",
                f"/rest/api/3/issue/{parent_key}",
                json_body={"fields": {"description": new_adf}},
            )

    def set_fields(self, key: str, fields: Mapping[str, Any]) -> None:
        """Generic field write — used to attach the MR link to the parent
        ticket's ``customfield_*`` right after the Draft MR opens, etc."""
        if not fields:
            return
        self._http.send(
            "PUT",
            f"/rest/api/3/issue/{key}",
            json_body={"fields": dict(fields)},
        )

    def set_field_if_unset(self, key: str, field_id: str, value: Any) -> bool:
        """Conditionally write ``field_id`` on ``key`` — only if it's currently
        empty. Returns True if a write happened, False if the field was already
        set (treated as "user owns it, leave alone"). Empty = ``None``, empty
        string, or an empty list/dict.

        Used to default the parent ticket's "A+ Clarity" single-select to
        green 🟢 when the user hasn't picked anything yet, without overwriting
        a deliberate choice.
        """
        resp = self._http.send(
            "GET", f"/rest/api/3/issue/{key}", params={"fields": field_id}
        )
        current = (resp.get("fields") or {}).get(field_id)
        if current not in (None, "", [], {}):
            return False
        self._http.send(
            "PUT",
            f"/rest/api/3/issue/{key}",
            json_body={"fields": {field_id: value}},
        )
        return True

    def comment(self, key: str, markdown: str) -> None:
        self._http.send(
            "POST",
            f"/rest/api/3/issue/{key}/comment",
            json_body={"body": _text_to_adf(markdown)},
        )

    def get_status(self, key: str) -> str:
        """Return the current Jira status name of ``key``.

        Lean alternative to ``get_parent_fields`` when only the workflow
        position matters — used by the runner's ``contract_mismatch``
        routing to decide whether the producer SubTask is still mutable
        (Dev-Pending / Dev-Designing / Dev-Developing) or has already
        passed the lock point (Dev-CR/Merge and beyond), which changes
        the recovery framing posted to the human.
        """
        resp = self._http.send(
            "GET", f"/rest/api/3/issue/{key}", params={"fields": "status"}
        )
        f = resp.get("fields") or {}
        return (f.get("status") or {}).get("name", "")

    def get_my_account_id(self) -> str:
        """Return the authenticated user's Atlassian accountId.

        Required because the workflow validator on ``Start Development`` (and
        likely later transitions) demands the issue have an assignee, and we
        need a stable identifier to write into the ``assignee`` field.
        """
        resp = self._http.send("GET", "/rest/api/3/myself")
        return resp["accountId"]

    def assign(self, key: str, account_id: str) -> None:
        """Set the assignee on ``key`` to ``account_id``. Idempotent: writing the
        same accountId twice is a no-op for Jira."""
        self.set_fields(key, {"assignee": {"accountId": account_id}})

    def flip_acceptance_checkboxes(self, key: str) -> None:
        """Flip every ``[ ]`` to ``[x]`` inside the ``## Acceptance`` section of
        ``key``'s description, leaving every other section byte-identical.

        Idempotent: re-running on a fully-flipped section is a no-op (no PUT).
        Mixed lists with some items already ``[x]`` are preserved — only the
        unchecked bullets flip. If the description has no ``## Acceptance``
        heading or no description at all, this is a no-op.
        """
        resp = self._http.send(
            "GET", f"/rest/api/3/issue/{key}", params={"fields": "description"}
        )
        adf = (resp.get("fields") or {}).get("description")
        if not adf:
            return
        new_adf, changed = flip_acceptance_in_adf(adf)
        if not changed:
            return
        self._http.send(
            "PUT",
            f"/rest/api/3/issue/{key}",
            json_body={"fields": {"description": new_adf}},
        )

    def get_issue_description_markdown(self, key: str) -> str:
        """Fetch ``key``'s description and render the ADF tree as Markdown.

        Used by ``afk-go`` to feed ``subtask_template.parse(...)``. Handles
        heading / bulletList / orderedList / codeBlock / hardBreak / `code`
        marks — the shapes a SubTask description authored via the Jira UI uses.
        """
        resp = self._http.send(
            "GET", f"/rest/api/3/issue/{key}", params={"fields": "description"}
        )
        return _adf_to_markdown((resp.get("fields") or {}).get("description"))


def _merge_notes_bullet(
    existing: list[str], subtask_key: str, bullet_text: str
) -> list[str]:
    """Replace the existing ``(SUBTASK_KEY) ...`` bullet for ``subtask_key`` with
    the new text, or append if no entry for that key yet. Other bullets are
    preserved in original order. Idempotent: replaying with the same arguments
    yields a list byte-identical to the previous result.
    """
    bullet_line = f"({subtask_key}) {bullet_text.lstrip('-').lstrip()}"
    needle = re.compile(rf"^\s*\(?\s*{re.escape(subtask_key)}\b")
    out: list[str] = []
    replaced = False
    for item in existing:
        if needle.match(item):
            if not replaced:
                out.append(bullet_line)
                replaced = True
            continue
        out.append(item)
    if not replaced:
        out.append(bullet_line)
    return out


def _bullets_from_block_nodes(nodes: list[dict]) -> list[str]:
    """Pull the flat text of each ``listItem`` from the first ``bulletList`` in
    a sequence of marker-region nodes. Other node types (e.g. the decorative
    H2 header) are skipped. Returns ``[]`` if no bulletList is present.
    """
    for b in nodes:
        if b.get("type") != "bulletList":
            continue
        items: list[str] = []
        for li in b.get("content", []):
            text_parts: list[str] = []
            for child in li.get("content", []):
                if child.get("type") == "paragraph":
                    text_parts.append(_render_inlines(child.get("content", [])))
            items.append("".join(text_parts))
        return items
    return []


def _strip_legacy_notes_heading_block(adf: dict) -> tuple[list[str], dict]:
    """One-time migration: detect the pre-marker shape (top-level
    ``## Implementation Notes (auto-maintained)`` heading + immediately
    following bulletList), extract the existing bullets, return ``(items,
    adf_with_legacy_removed)``.

    If no legacy heading is found, returns ``([], adf)`` unchanged. The
    caller's next splice will create the marker form via ``create_if_missing``.

    Once all live ``afk-agents`` parents have been written-through once, this
    fallback becomes dead code (search for ``_NOTES_HEADER_TEXT`` at the top
    level on each live parent; zero hits = safe to delete).
    """
    blocks = list(adf.get("content", []) or [])
    notes_idx = -1
    for i, b in enumerate(blocks):
        if (
            b.get("type") == "heading"
            and _heading_text(b).strip() == _NOTES_HEADER_TEXT
        ):
            notes_idx = i
            break
    if notes_idx == -1:
        return [], adf

    items = _bullets_from_block_nodes(blocks[notes_idx + 1 :])
    new_blocks = list(blocks[:notes_idx])
    skipped_first_list = False
    for b in blocks[notes_idx + 1 :]:
        if not skipped_first_list and b.get("type") == "bulletList":
            skipped_first_list = True
            continue
        new_blocks.append(b)
    return items, {"type": "doc", "version": 1, "content": new_blocks}


def _make_heading2(text: str) -> dict:
    return {
        "type": "heading",
        "attrs": {"level": 2},
        "content": [{"type": "text", "text": text}],
    }


_UNCHECKED_PREFIX = re.compile(r"^(\s*)\[ \]")


def flip_acceptance_in_adf(adf: dict) -> tuple[dict, bool]:
    """Return (new_adf, changed) where every ``[ ]`` inside the first-level
    ``## Acceptance`` heading's following bulletList items is flipped to ``[x]``.

    Walk only top-level ``content`` blocks. A heading whose flattened text is
    exactly ``Acceptance`` opens the section; the next heading at any level
    closes it. Within an open section, mutate each ``bulletList`` ``listItem``'s
    first text node (the conventional position of the ``[ ]`` token in
    Jira-authored task lists). Other text nodes are left alone so embedded
    ``[ ]`` literals inside criterion prose are not corrupted.
    """
    new_adf = copy.deepcopy(adf)
    changed = False
    in_section = False
    for block in new_adf.get("content", []):
        t = block.get("type")
        if t == "heading":
            in_section = _heading_text(block).strip() == "Acceptance"
            continue
        if not in_section:
            continue
        if t == "bulletList":
            for item in block.get("content", []):
                if _flip_listitem(item):
                    changed = True
    return new_adf, changed


def _heading_text(block: dict) -> str:
    return "".join(
        n.get("text", "") for n in block.get("content", []) if n.get("type") == "text"
    )


def _flip_listitem(item: dict) -> bool:
    """Flip the leading ``[ ]`` of the listItem's first text node in its first
    paragraph. Return True if something changed."""
    for inner in item.get("content", []):
        if inner.get("type") != "paragraph":
            continue
        for node in inner.get("content", []):
            if node.get("type") != "text":
                continue
            text = node.get("text", "")
            new_text, n = _UNCHECKED_PREFIX.subn(r"\1[x]", text, count=1)
            if n:
                node["text"] = new_text
                return True
            return False
    return False


def _adf_to_markdown(adf: Optional[dict]) -> str:
    """Render an ADF doc as Markdown the SubTask-template parser understands.

    Kept distinct from ``_adf_to_text`` (which is paragraph-only and round-trips
    the splice-block writes verbatim). This renderer covers the additional
    block kinds a human-authored Jira description uses: heading, bulletList,
    orderedList, codeBlock, hardBreak, ``code`` text-mark.
    """
    if not adf:
        return ""
    return _render_blocks(adf.get("content", []))


def _render_blocks(blocks: list[dict]) -> str:
    out: list[str] = []
    for block in blocks:
        t = block.get("type")
        if t == "paragraph":
            out.append(_render_inlines(block.get("content", [])))
        elif t == "heading":
            level = (block.get("attrs") or {}).get("level", 1)
            out.append("#" * level + " " + _render_inlines(block.get("content", [])))
        elif t == "bulletList":
            for item in block.get("content", []):
                inner = _render_blocks(item.get("content", []))
                lines = inner.splitlines() or [""]
                out.append("- " + lines[0])
                for ln in lines[1:]:
                    out.append("  " + ln)
        elif t == "orderedList":
            for i, item in enumerate(block.get("content", []), 1):
                inner = _render_blocks(item.get("content", []))
                lines = inner.splitlines() or [""]
                out.append(f"{i}. " + lines[0])
                for ln in lines[1:]:
                    out.append("   " + ln)
        elif t == "codeBlock":
            lang = (block.get("attrs") or {}).get("language", "") or ""
            text = "".join(
                n.get("text", "")
                for n in block.get("content", [])
                if n.get("type") == "text"
            )
            out.append(f"```{lang}\n{text}\n```")
        elif t == "rule":
            out.append("---")
    return "\n\n".join(out)


def _render_inlines(nodes: list[dict]) -> str:
    parts: list[str] = []
    for node in nodes:
        t = node.get("type")
        if t == "text":
            text = node.get("text", "")
            for mark in node.get("marks") or ():
                if mark.get("type") == "code":
                    text = f"`{text}`"
            parts.append(text)
        elif t == "hardBreak":
            parts.append("\n")
    return "".join(parts)


def _text_to_adf(text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }
