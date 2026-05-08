"""Unit tests for jira_client. HTTP is faked; no network."""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

import pytest

from afk_driver.jira_client import (
    JiraClient,
    JiraConfig,
    JiraError,
)
from afk_driver.section_splice import marker_id_text
from afk_driver.subtask_template import parse as parse_subtask


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Optional[dict], Optional[dict]]] = []
        self._handlers: list[tuple[str, str, Any]] = []

    def add(self, method: str, path_substring: str, response: Any) -> None:
        self._handlers.append((method, path_substring, response))

    def send(self, method, path, *, json_body=None, params=None):
        self.calls.append((method, path, json_body, dict(params) if params else None))
        for m, sub, r in self._handlers:
            if m == method and sub in path:
                return r(self.calls[-1]) if callable(r) else r
        raise AssertionError(f"FakeTransport: no handler for {method} {path}")


def _config() -> JiraConfig:
    return JiraConfig(
        base_url="https://x",
        email="a@b",
        api_token="t",
        parent_fields={"target_branch": "customfield_13706"},
    )


def test_search_parses_issues():
    t = FakeTransport()
    t.add("POST", "/search", {
        "issues": [
            {
                "key": "P2P-1",
                "fields": {
                    "summary": "thing",
                    "status": {"name": "Dev-Pending"},
                    "issuetype": {"name": "SubTask"},
                    "parent": {"key": "P2P-1220"},
                    "labels": ["afk-agents"],
                    "fixVersions": [{"name": "v1"}],
                },
            }
        ]
    })
    c = JiraClient(_config(), t)
    issues = c.search("project = P2P AND labels = afk-agents")
    assert len(issues) == 1
    i = issues[0]
    assert i.key == "P2P-1"
    assert i.summary == "thing"
    assert i.status == "Dev-Pending"
    assert i.issuetype == "SubTask"
    assert i.parent_key == "P2P-1220"
    assert i.labels == ("afk-agents",)
    assert i.fix_versions == ("v1",)


def test_get_parent_fields_returns_logical_keys_and_meta():
    t = FakeTransport()
    t.add("GET", "/issue/P2P-1220", {
        "fields": {
            "status": {"name": "Dev-Developing"},
            "issuetype": {"name": "Enhancement"},
            "fixVersions": [{"name": "core/1.2.0"}],
            "components": [{"name": "payable"}],
            "customfield_13706": {"value": "MASTER"},
        }
    })
    c = JiraClient(_config(), t)
    out = c.get_parent_fields("P2P-1220")
    assert out["status"] == "Dev-Developing"
    assert out["issuetype"] == "Enhancement"
    assert out["fix_versions"] == ["core/1.2.0"]
    assert out["components"] == ["payable"]
    assert out["target_branch"] == {"value": "MASTER"}


def test_get_parent_fields_handles_bug_issuetype():
    """Parent ticket may be a Bug, not just an Enhancement; both share workflow."""
    t = FakeTransport()
    t.add("GET", "/issue/P2P-9000", {
        "fields": {
            "status": {"name": "Dev-Pending"},
            "issuetype": {"name": "Bug"},
            "fixVersions": [{"name": "core/1.2.0"}],
            "components": [],
            "customfield_13706": {"value": "MASTER"},
        }
    })
    c = JiraClient(_config(), t)
    out = c.get_parent_fields("P2P-9000")
    assert out["issuetype"] == "Bug"
    assert out["target_branch"] == {"value": "MASTER"}


def test_list_transitions():
    t = FakeTransport()
    t.add("GET", "/transitions", {
        "transitions": [
            {"id": "11", "name": "Start Designing", "to": {"name": "Dev-Designing"}},
            {"id": "21", "name": "Start Development", "to": {"name": "Dev-Developing"}},
        ]
    })
    c = JiraClient(_config(), t)
    ts = c.list_transitions("P2P-1")
    assert [x.name for x in ts] == ["Start Designing", "Start Development"]
    assert ts[0].to_status == "Dev-Designing"


def test_transition_executes_named():
    t = FakeTransport()
    t.add("GET", "/transitions", {
        "transitions": [
            {"id": "21", "name": "Start Development", "to": {"name": "Dev-Developing"}},
        ]
    })
    t.add("POST", "/transitions", {})
    c = JiraClient(_config(), t)
    c.transition("P2P-1", "Start Development")
    post_calls = [c for c in t.calls if c[0] == "POST"]
    assert post_calls[-1][2] == {"transition": {"id": "21"}}


def test_transition_unavailable_raises():
    t = FakeTransport()
    t.add("GET", "/transitions", {"transitions": [{"id": "1", "name": "Closed", "to": {"name": "Closed"}}]})
    # _fetch_status fallback fires for known transition names. Stub a status
    # that DOES NOT match the expected target so we still raise.
    t.add("GET", "/issue/P2P-1", {"fields": {"status": {"name": "Closed"}}})
    c = JiraClient(_config(), t)
    with pytest.raises(JiraError, match="not available"):
        c.transition("P2P-1", "Start Development")


def test_transition_idempotent_when_already_at_target():
    """Fix A: if 'Request CR & Merge' isn't in the candidate list AND the
    issue is already in Dev-CR/Merge, the call no-ops + returns False
    instead of raising. Repeats of the same logical transition (or a Jira
    workflow post-function that auto-advanced the issue) stop being fatal."""
    t = FakeTransport()
    # Available list is what Jira returns when the issue is already in
    # Dev-CR/Merge — none of these match "Request CR & Merge".
    t.add("GET", "/transitions", {"transitions": [
        {"id": "91", "name": "Re-Open / Testing Failed", "to": {"name": "Dev-Developing"}},
        {"id": "92", "name": "Merge To Target Branch", "to": {"name": "Closed"}},
    ]})
    t.add("GET", "/issue/P2P-1237", {"fields": {"status": {"name": "Dev-CR/Merge"}}})
    c = JiraClient(_config(), t)
    assert c.transition("P2P-1237", "Request CR & Merge") is False
    # No POST to /transitions — the no-op skips the actual transition call.
    assert all(call[0] != "POST" for call in t.calls)


def test_transition_returns_true_when_actually_fired():
    """Sanity: when the transition IS available, we POST and return True."""
    t = FakeTransport()
    t.add("GET", "/transitions", {
        "transitions": [
            {"id": "21", "name": "Start Development", "to": {"name": "Dev-Developing"}},
        ]
    })
    t.add("POST", "/transitions", {})
    c = JiraClient(_config(), t)
    assert c.transition("P2P-1", "Start Development") is True
    post_calls = [x for x in t.calls if x[0] == "POST"]
    assert len(post_calls) == 1


def test_transition_unknown_name_still_raises():
    """Idempotent skip only kicks in for transitions in
    _TRANSITION_TARGET_STATUS. An unknown name with no candidate match still
    raises so caller misuse stays loud."""
    t = FakeTransport()
    t.add("GET", "/transitions", {"transitions": []})
    c = JiraClient(_config(), t)
    with pytest.raises(JiraError, match="not available"):
        c.transition("P2P-1", "Some Made Up Transition")


def test_set_field_if_unset_writes_when_null():
    """A+ Clarity defaulting: when the customfield is null on the parent,
    the helper PUTs the green option payload."""
    t = FakeTransport()
    t.add("GET", "/issue/P2P-1220", {"fields": {"customfield_13894": None}})
    t.add("PUT", "/issue/P2P-1220", {})
    c = JiraClient(_config(), t)
    wrote = c.set_field_if_unset("P2P-1220", "customfield_13894", {"id": "13737"})
    assert wrote is True
    put_calls = [x for x in t.calls if x[0] == "PUT"]
    assert len(put_calls) == 1
    assert put_calls[0][2] == {"fields": {"customfield_13894": {"id": "13737"}}}


def test_set_field_if_unset_skips_when_already_set():
    """If the user (or someone) already picked a clarity option, the helper
    must NOT overwrite it. Returns False; no PUT issued."""
    t = FakeTransport()
    t.add("GET", "/issue/P2P-1220", {
        "fields": {"customfield_13894": {"id": "13740", "value": "🔴"}}
    })
    c = JiraClient(_config(), t)
    wrote = c.set_field_if_unset("P2P-1220", "customfield_13894", {"id": "13737"})
    assert wrote is False
    assert all(x[0] != "PUT" for x in t.calls)


def test_set_field_if_unset_treats_empty_collections_as_unset():
    """Jira can return ``[]`` or ``{}`` for unset multi-value fields; treat
    those as empty so the default still gets written."""
    for empty in ([], {}):
        t = FakeTransport()
        t.add("GET", "/issue/P2P-1", {"fields": {"customfield_13894": empty}})
        t.add("PUT", "/issue/P2P-1", {})
        c = JiraClient(_config(), t)
        assert c.set_field_if_unset("P2P-1", "customfield_13894", {"id": "13737"}) is True


def _heading2(text):
    return {"type": "heading", "attrs": {"level": 2},
            "content": [{"type": "text", "text": text}]}


def _bullet(items):
    return {"type": "bulletList", "content": [
        {"type": "listItem", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": s}]}
        ]} for s in items
    ]}


def _marker_para(text):
    """Mirror jira_section's marker shape: paragraph w/ single inline-code
    text node. Tests use this to construct fixtures and to assert the
    splicer's output structure."""
    return {"type": "paragraph",
            "content": [{"type": "text", "text": text,
                         "marks": [{"type": "code"}]}]}


def _items_inside_notes_markers(adf):
    """Extract the (P2P-N) bullet texts from the bulletList between the
    afk:notes:start / afk:notes:end marker pair. Asserts the marker pair is
    present + a bulletList sits between them."""
    start_t, end_t = marker_id_text("notes")
    blocks = adf["content"]
    start_idx = next(
        i for i, b in enumerate(blocks)
        if b.get("type") == "paragraph"
        and (b.get("content") or [{}])[0].get("text") == start_t
    )
    end_idx = next(
        i for i, b in enumerate(blocks)
        if b.get("type") == "paragraph"
        and (b.get("content") or [{}])[0].get("text") == end_t
    )
    assert start_idx < end_idx, "marker pair out of order"
    inside = blocks[start_idx + 1: end_idx]
    bl = next(b for b in inside if b.get("type") == "bulletList")
    return [li["content"][0]["content"][0]["text"] for li in bl["content"]]


def test_implementation_notes_insert_when_block_missing():
    """No marker pair, no legacy heading: body survives byte-identical;
    helper appends a fresh ``afk:notes:start`` … ``afk:notes:end`` block
    at the end with the decorative H2 + bulletList inside."""
    body_blocks = [
        _heading2("Summary"),
        {"type": "paragraph", "content": [{"type": "text", "text": "blah"}]},
    ]
    t = FakeTransport()
    t.add("GET", "/issue/P2P-1220", {
        "fields": {"description": {"type": "doc", "version": 1, "content": body_blocks}}
    })
    t.add("PUT", "/issue/P2P-1220", {})
    c = JiraClient(_config(), t)
    c.update_implementation_notes("P2P-1220", "P2P-1222", "did the thing")
    put = [x for x in t.calls if x[0] == "PUT"][-1]
    new_adf = put[2]["fields"]["description"]
    blocks = new_adf["content"]
    assert blocks[:2] == body_blocks, "user body must be byte-identical"
    start_t, end_t = marker_id_text("notes")
    assert blocks[2] == _marker_para(start_t)
    assert blocks[3] == _heading2("Implementation Notes (auto-maintained)")
    assert blocks[4] == _bullet(["(P2P-1222) did the thing"])
    assert blocks[5] == _marker_para(end_t)
    assert _items_inside_notes_markers(new_adf) == ["(P2P-1222) did the thing"]


def test_implementation_notes_replaces_existing_bullet_in_marker_form():
    """When the marker pair already exists, replaying with the same key
    replaces that bullet's text; other bullets and body blocks are preserved
    verbatim. Decorative H2 inside the markers is rebuilt identically."""
    start_t, end_t = marker_id_text("notes")
    body_blocks = [
        _heading2("Summary"),
        {"type": "paragraph", "content": [{"type": "text", "text": "body"}]},
    ]
    notes_blocks = [
        _marker_para(start_t),
        _heading2("Implementation Notes (auto-maintained)"),
        _bullet(["(P2P-1222) old text", "(P2P-1223) other"]),
        _marker_para(end_t),
    ]
    t = FakeTransport()
    t.add("GET", "/issue/P2P-1220", {
        "fields": {"description": {"type": "doc", "version": 1, "content": body_blocks + notes_blocks}}
    })
    t.add("PUT", "/issue/P2P-1220", {})
    c = JiraClient(_config(), t)
    c.update_implementation_notes("P2P-1220", "P2P-1222", "new text")
    put = [x for x in t.calls if x[0] == "PUT"][-1]
    new_adf = put[2]["fields"]["description"]
    assert new_adf["content"][:2] == body_blocks
    assert _items_inside_notes_markers(new_adf) == [
        "(P2P-1222) new text",
        "(P2P-1223) other",
    ]


def test_implementation_notes_no_change_skips_put():
    """Idempotent: replaying same key + text against marker-form input → no PUT."""
    start_t, end_t = marker_id_text("notes")
    initial = {"type": "doc", "version": 1, "content": [
        _marker_para(start_t),
        _heading2("Implementation Notes (auto-maintained)"),
        _bullet(["(P2P-1222) same"]),
        _marker_para(end_t),
    ]}
    t = FakeTransport()
    t.add("GET", "/issue/P2P-1220", {"fields": {"description": initial}})
    c = JiraClient(_config(), t)
    c.update_implementation_notes("P2P-1220", "P2P-1222", "same")
    assert all(x[0] != "PUT" for x in t.calls)


def test_implementation_notes_migrates_legacy_heading_block_to_marker_form():
    """One-time migration: a parent written by the pre-marker driver has a
    top-level ``## Implementation Notes (auto-maintained)`` heading + bulletList
    with no markers. First write: lift existing bullets, strip legacy heading +
    list, splicer creates marker form. Body above the legacy heading is
    preserved verbatim."""
    body_blocks = [
        _heading2("Goal"),
        {"type": "paragraph", "content": [{"type": "text", "text": "real prose"}]},
    ]
    legacy_blocks = [
        _heading2("Implementation Notes (auto-maintained)"),
        _bullet(["(P2P-1222) old", "(P2P-1223) keep"]),
    ]
    t = FakeTransport()
    t.add("GET", "/issue/P2P-1220", {
        "fields": {"description": {"type": "doc", "version": 1, "content": body_blocks + legacy_blocks}}
    })
    t.add("PUT", "/issue/P2P-1220", {})
    c = JiraClient(_config(), t)
    c.update_implementation_notes("P2P-1220", "P2P-1222", "migrated text")
    put = [x for x in t.calls if x[0] == "PUT"][-1]
    new_adf = put[2]["fields"]["description"]
    blocks = new_adf["content"]
    # Body above legacy preserved.
    assert blocks[:2] == body_blocks
    # Legacy heading-block stripped — no top-level Implementation Notes heading
    # remains outside the markers.
    top_level_headings = [
        b for b in blocks
        if b.get("type") == "heading"
        and (b.get("content") or [{}])[0].get("text") == "Implementation Notes (auto-maintained)"
    ]
    # Exactly one — and it must be inside the marker region.
    assert len(top_level_headings) == 1
    start_t, end_t = marker_id_text("notes")
    start_idx = next(i for i, b in enumerate(blocks) if b == _marker_para(start_t))
    end_idx = next(i for i, b in enumerate(blocks) if b == _marker_para(end_t))
    assert start_idx < blocks.index(top_level_headings[0]) < end_idx
    # Items: replaced bullet for P2P-1222, other preserved in order.
    assert _items_inside_notes_markers(new_adf) == [
        "(P2P-1222) migrated text",
        "(P2P-1223) keep",
    ]


def test_implementation_notes_preserves_rich_body_blocks():
    """Regression for the P2P-1228 clobber: a description with multiple
    headings, paragraphs, bulletLists, and codeBlocks must survive an
    update_implementation_notes call with every body block byte-identical.
    Body blocks above the marker region are deep-copied unchanged."""
    rich_body = [
        _heading2("Problem Statement"),
        {"type": "paragraph", "content": [{"type": "text", "text": "Long prose."}]},
        _bullet(["BS acc: do not send", "P&L acc: do send"]),
        {"type": "heading", "attrs": {"level": 3},
         "content": [{"type": "text", "text": "Code"}]},
        {"type": "codeBlock", "attrs": {"language": "java"},
         "content": [{"type": "text", "text": "applyCostObjects(entry)"}]},
    ]
    t = FakeTransport()
    t.add("GET", "/issue/P2P-1228", {
        "fields": {"description": {"type": "doc", "version": 1, "content": rich_body}}
    })
    t.add("PUT", "/issue/P2P-1228", {})
    c = JiraClient(_config(), t)
    c.update_implementation_notes("P2P-1228", "P2P-1233", "[AFK] Plumb flag")
    put = [x for x in t.calls if x[0] == "PUT"][-1]
    new_adf = put[2]["fields"]["description"]
    assert new_adf["content"][: len(rich_body)] == rich_body, (
        "every rich body block must be byte-identical after the splice"
    )
    start_t, _ = marker_id_text("notes")
    assert new_adf["content"][len(rich_body)] == _marker_para(start_t)
    assert _items_inside_notes_markers(new_adf) == ["(P2P-1233) [AFK] Plumb flag"]


class _StatefulNotesTransport:
    """Fake transport that maintains a single issue's description across
    calls, the way a real Jira backend would. Each GET returns the
    current description; each PUT replaces it. Used to exercise
    concurrency on ``update_implementation_notes``: two threads that
    each splice one bullet must both end up in the final description,
    NOT clobber each other.

    Includes a configurable per-call delay between GET and PUT so the
    test can amplify any window where the lock would have to hold.
    """

    def __init__(self, initial_adf: dict, *, delay_s: float = 0.0):
        self.adf = initial_adf
        self.delay_s = delay_s
        self._state_lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []

    def send(self, method, path, *, json_body=None, params=None):
        self.calls.append((method, path))
        if method == "GET" and "/issue/" in path:
            with self._state_lock:
                snapshot = {"fields": {"description": _deepcopy(self.adf)}}
            # Simulate latency between GET and PUT to widen the race
            # window. Without the per-key lock under test, the two
            # threads' GETs would both see the same baseline and the
            # second PUT would clobber the first.
            time.sleep(self.delay_s)
            return snapshot
        if method == "PUT" and "/issue/" in path:
            new_desc = (json_body or {}).get("fields", {}).get("description")
            with self._state_lock:
                if new_desc is not None:
                    self.adf = _deepcopy(new_desc)
            return {}
        raise AssertionError(f"_StatefulNotesTransport: unhandled {method} {path}")


def _deepcopy(obj):
    import copy as _copy
    return _copy.deepcopy(obj)


def test_implementation_notes_serializes_concurrent_writes_per_parent():
    """Two threads splicing different bullets into the same parent must
    NOT clobber each other. Both bullets must end up in the final
    description.

    S4 closure 2026-05-08. Pre-fix, two concurrent calls would each
    GET the baseline description (no marker block, or the same set of
    bullets), splice their own bullet locally, and the second PUT
    would overwrite the first — losing one bullet per race.

    The fix: ``JiraClient`` holds a per-parent-key lock, so the two
    threads' read-modify-write splices serialize. After the test, the
    description has BOTH bullets in the marker block.
    """
    initial = {"type": "doc", "version": 1, "content": []}
    transport = _StatefulNotesTransport(initial, delay_s=0.05)
    client = JiraClient(_config(), transport)

    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def worker(subkey: str, text: str) -> None:
        try:
            barrier.wait()  # release both threads as close to simultaneously as possible
            client.update_implementation_notes("P2P-1220", subkey, text)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    t1 = threading.Thread(target=worker, args=("P2P-1221", "first"))
    t2 = threading.Thread(target=worker, args=("P2P-1222", "second"))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert not errors, errors
    final_items = _items_inside_notes_markers(transport.adf)
    # Both bullets must be present (order is whichever thread won the
    # lock first; we only assert containment, not order).
    assert "(P2P-1221) first" in final_items
    assert "(P2P-1222) second" in final_items
    assert len(final_items) == 2


def test_implementation_notes_different_parents_proceed_in_parallel():
    """Locking is per-parent-key. Two writes targeting *different* parents
    must NOT serialize against each other — that would defeat the
    parallelization the per-key locking was added to enable. We verify
    by giving each parent its own transport (so the locks don't share
    state across them) and asserting both calls complete inside a
    bounded window."""
    t1 = _StatefulNotesTransport(
        {"type": "doc", "version": 1, "content": []}, delay_s=0.1,
    )
    t2 = _StatefulNotesTransport(
        {"type": "doc", "version": 1, "content": []}, delay_s=0.1,
    )
    c1 = JiraClient(_config(), t1)
    c2 = JiraClient(_config(), t2)

    start = time.monotonic()
    th1 = threading.Thread(
        target=lambda: c1.update_implementation_notes("P2P-A", "P2P-A1", "x")
    )
    th2 = threading.Thread(
        target=lambda: c2.update_implementation_notes("P2P-B", "P2P-B1", "y")
    )
    th1.start(); th2.start()
    th1.join(); th2.join()
    elapsed = time.monotonic() - start

    # Each call sleeps 0.1s in the GET delay. If they ran serialized
    # they'd take ~0.2s; in parallel they should take ~0.1s. Allow
    # generous slack for thread-start overhead but reject obvious
    # serial behaviour (>0.18s would mean serialization).
    assert elapsed < 0.18, (
        f"different parents serialized: elapsed={elapsed:.3f}s "
        f"(expected ~0.1s for parallel, ~0.2s for serial)"
    )


def test_comment_posts_adf():
    t = FakeTransport()
    t.add("POST", "/comment", {})
    c = JiraClient(_config(), t)
    c.comment("P2P-1", "hello world")
    body = t.calls[-1][2]
    assert body["body"]["content"][0]["content"][0]["text"] == "hello world"


def test_get_issue_description_markdown_round_trips_through_subtask_parser():
    """End-to-end: Jira-authored ADF -> markdown -> subtask_template.parse OK."""
    adf = {
        "type": "doc", "version": 1, "content": [
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Goal"}]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Echo "},
                {"type": "text", "text": "hello", "marks": [{"type": "code"}]},
                {"type": "text", "text": " into "},
                {"type": "text", "text": "tools/payable/afk-smoke/", "marks": [{"type": "code"}]},
                {"type": "hardBreak"},
                {"type": "text", "text": "to prove the loop closes."},
            ]},
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Scope"}]},
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "tools/payable/afk-smoke/**"}]},
                ]},
            ]},
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Acceptance"}]},
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [
                    {"type": "paragraph", "content": [
                        {"type": "text", "text": "[ ] "},
                        {"type": "text", "text": "tools/payable/afk-smoke/output.txt", "marks": [{"type": "code"}]},
                        {"type": "text", "text": " contains "},
                        {"type": "text", "text": "hello", "marks": [{"type": "code"}]},
                    ]},
                ]},
                {"type": "listItem", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "[ ] Tests pass"}]},
                ]},
            ]},
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Test command"}]},
            {"type": "codeBlock", "attrs": {"language": "bash"}, "content": [
                {"type": "text", "text": "python -c \"assert open('out.txt').read() == 'hello'\""},
            ]},
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Parent PRD"}]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "tools/payable/afk/PRD.md", "marks": [{"type": "code"}]},
            ]},
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Blocked by"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "(none)"}]},
            {"type": "heading", "attrs": {"level": 2}, "content": [
                {"type": "text", "text": "Implementation Notes (auto-maintained)"},
            ]},
            {"type": "paragraph", "content": [{"type": "text", "text": "<!-- AFK appends -->"}]},
        ]
    }
    t = FakeTransport()
    t.add("GET", "/issue/P2P-1230", {"fields": {"description": adf}})
    c = JiraClient(_config(), t)

    md = c.get_issue_description_markdown("P2P-1230")
    assert md.startswith("## Goal\n")
    assert "## Test command\n\n```bash\n" in md
    assert "- tools/payable/afk-smoke/**" in md
    assert "- [ ] `tools/payable/afk-smoke/output.txt` contains `hello`" in md

    parsed = parse_subtask(md)
    assert parsed.scope == ("tools/payable/afk-smoke/**",)
    assert len(parsed.acceptance) == 2
    assert parsed.test_command == "python -c \"assert open('out.txt').read() == 'hello'\""
    assert parsed.parent_prd == "`tools/payable/afk/PRD.md`"
    assert parsed.blocked_by == "(none)"


def test_get_my_account_id_returns_authenticated_user():
    t = FakeTransport()
    t.add("GET", "/myself", {"accountId": "abc-123", "displayName": "Minh Vu"})
    c = JiraClient(_config(), t)
    assert c.get_my_account_id() == "abc-123"


def test_assign_writes_assignee_with_account_id():
    t = FakeTransport()
    t.add("PUT", "/issue/P2P-1230", {})
    c = JiraClient(_config(), t)
    c.assign("P2P-1230", "abc-123")
    put = [x for x in t.calls if x[0] == "PUT"][-1]
    assert put[2] == {"fields": {"assignee": {"accountId": "abc-123"}}}


def test_get_issue_description_markdown_empty_when_no_description():
    t = FakeTransport()
    t.add("GET", "/issue/P2P-X", {"fields": {"description": None}})
    c = JiraClient(_config(), t)
    assert c.get_issue_description_markdown("P2P-X") == ""
