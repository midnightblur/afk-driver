"""Unit tests for the ADF section splicer.

The splicer is format-only: it owns marker-finding + outside preservation.
Decoration (e.g. an H2 header for human navigation) lives inside the
caller's ``block_nodes`` payload, not in the splicer. Tests reflect that.
"""

from __future__ import annotations

import copy

import pytest

from afk_driver.jira_section import (
    read_block_in_adf,
    render_bullets_adf,
    splice_in_adf,
)
from afk_driver.section_splice import SectionMarkerMissing, marker_id_text


def _doc(content: list[dict]) -> dict:
    return {"type": "doc", "version": 1, "content": content}


def _heading2(text: str) -> dict:
    return {
        "type": "heading",
        "attrs": {"level": 2},
        "content": [{"type": "text", "text": text}],
    }


def _para(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _bullets(items: list[str]) -> dict:
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": s}],
                    }
                ],
            }
            for s in items
        ],
    }


def _marker_para(text: str) -> dict:
    return {
        "type": "paragraph",
        "content": [
            {"type": "text", "text": text, "marks": [{"type": "code"}]}
        ],
    }


def test_marker_id_text_format():
    assert marker_id_text("notes") == ("afk:notes:start", "afk:notes:end")
    assert marker_id_text("subtasks") == ("afk:subtasks:start", "afk:subtasks:end")


def test_render_bullets_adf_returns_one_bullet_list_node():
    nodes = render_bullets_adf(["a", "b"])
    assert len(nodes) == 1
    bl = nodes[0]
    assert bl["type"] == "bulletList"
    assert [
        li["content"][0]["content"][0]["text"] for li in bl["content"]
    ] == ["a", "b"]


def test_render_bullets_adf_empty_returns_empty_list():
    assert render_bullets_adf([]) == []


def test_splice_creates_block_when_markers_absent_and_create_if_missing():
    body = [_heading2("Goal"), _para("body prose")]
    block = [_heading2("Implementation Notes"), _bullets(["(P2P-1) one"])]
    new, changed = splice_in_adf(_doc(body), block, marker_id="notes", create_if_missing=True)
    assert changed is True
    # Body preserved verbatim.
    assert new["content"][:2] == body
    # Then start marker, payload, end marker — in order.
    start_t, end_t = marker_id_text("notes")
    assert new["content"][2] == _marker_para(start_t)
    assert new["content"][3] == _heading2("Implementation Notes")
    assert new["content"][4] == _bullets(["(P2P-1) one"])
    assert new["content"][5] == _marker_para(end_t)
    assert len(new["content"]) == 6


def test_splice_strict_raises_when_markers_absent():
    body = [_para("only this")]
    with pytest.raises(SectionMarkerMissing, match="absent"):
        splice_in_adf(_doc(body), [_para("x")], marker_id="notes")


def test_splice_replaces_content_between_existing_markers():
    start_t, end_t = marker_id_text("notes")
    body = [
        _heading2("Goal"),
        _marker_para(start_t),
        _heading2("OLD HEADING"),
        _bullets(["(P2P-1) old"]),
        _marker_para(end_t),
        _para("trailing human prose"),
    ]
    new_block = [_heading2("Implementation Notes (auto-maintained)"), _bullets(["(P2P-1) new", "(P2P-2) other"])]
    new, changed = splice_in_adf(_doc(body), new_block, marker_id="notes")
    assert changed is True
    # Outside markers preserved.
    assert new["content"][0] == _heading2("Goal")
    assert new["content"][-1] == _para("trailing human prose")
    # Markers in same positions (relative).
    assert new["content"][1] == _marker_para(start_t)
    assert new["content"][-2] == _marker_para(end_t)
    # Payload between markers is the new block (old heading + bullets gone).
    assert new["content"][2] == _heading2("Implementation Notes (auto-maintained)")
    assert new["content"][3] == _bullets(["(P2P-1) new", "(P2P-2) other"])
    assert len(new["content"]) == 6


def test_splice_idempotent_returns_same_object_when_unchanged():
    start_t, end_t = marker_id_text("notes")
    body = [
        _marker_para(start_t),
        _bullets(["(P2P-1) same"]),
        _marker_para(end_t),
    ]
    adf = _doc(body)
    new, changed = splice_in_adf(adf, [_bullets(["(P2P-1) same"])], marker_id="notes")
    assert changed is False
    assert new is adf  # identity preserved → caller skips PUT


def test_splice_preserves_outside_byte_identical():
    """Regression for P2P-1228 clobber: rich body blocks above must survive
    byte-identical when the splicer rewrites the marker region."""
    rich_body = [
        _heading2("Problem Statement"),
        _para("Long prose."),
        _bullets(["BS acc", "P&L acc"]),
        {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "Code"}]},
        {"type": "codeBlock", "attrs": {"language": "java"},
         "content": [{"type": "text", "text": "applyCostObjects(entry)"}]},
    ]
    snapshot = copy.deepcopy(rich_body)
    new, changed = splice_in_adf(
        _doc(rich_body), [_bullets(["(P2P-1) one"])], marker_id="notes", create_if_missing=True
    )
    assert changed is True
    assert new["content"][: len(rich_body)] == snapshot, (
        "every rich body block must be byte-identical after splice"
    )


def test_splice_raises_when_only_start_marker_present():
    """Corrupt state: one marker without its mate. Even with
    create_if_missing=True, do not auto-repair — would risk losing whatever
    the lone marker anchors. Manual intervention."""
    start_t, _ = marker_id_text("notes")
    body = [_para("hi"), _marker_para(start_t), _bullets(["x"])]
    with pytest.raises(SectionMarkerMissing, match="malformed"):
        splice_in_adf(_doc(body), [_para("y")], marker_id="notes", create_if_missing=True)


def test_splice_raises_when_only_end_marker_present():
    _, end_t = marker_id_text("notes")
    body = [_bullets(["x"]), _marker_para(end_t), _para("hi")]
    with pytest.raises(SectionMarkerMissing, match="malformed"):
        splice_in_adf(_doc(body), [_para("y")], marker_id="notes", create_if_missing=True)


def test_splice_raises_when_end_before_start():
    start_t, end_t = marker_id_text("notes")
    body = [_marker_para(end_t), _para("inner"), _marker_para(start_t)]
    with pytest.raises(SectionMarkerMissing, match="malformed"):
        splice_in_adf(_doc(body), [_para("y")], marker_id="notes", create_if_missing=True)


def test_find_marker_ignores_paragraphs_with_matching_text_but_no_code_mark():
    """Marker paragraphs are identified by exact shape (single text child +
    inline-code mark). A bare paragraph with the marker text is human prose,
    not a marker — splicer must not match it."""
    body = [
        _para("afk:notes:start"),  # bare text, no inline-code mark — NOT a marker
        _bullets(["x"]),
        _para("afk:notes:end"),
    ]
    # No real markers found → strict raises.
    with pytest.raises(SectionMarkerMissing, match="absent"):
        splice_in_adf(_doc(body), [_para("y")], marker_id="notes")


def test_read_block_returns_inside_nodes():
    start_t, end_t = marker_id_text("notes")
    body = [
        _para("before"),
        _marker_para(start_t),
        _heading2("hdr"),
        _bullets(["(P2P-1) one"]),
        _marker_para(end_t),
        _para("after"),
    ]
    inside = read_block_in_adf(_doc(body), marker_id="notes")
    assert inside == [_heading2("hdr"), _bullets(["(P2P-1) one"])]


def test_read_block_returns_none_when_markers_absent():
    body = [_heading2("Goal"), _para("nope")]
    assert read_block_in_adf(_doc(body), marker_id="notes") is None


def test_read_block_returns_none_when_only_one_marker_present():
    start_t, _ = marker_id_text("notes")
    body = [_marker_para(start_t), _bullets(["x"])]
    assert read_block_in_adf(_doc(body), marker_id="notes") is None


def test_read_block_deep_copies_so_caller_mutation_does_not_affect_source():
    start_t, end_t = marker_id_text("notes")
    bl = _bullets(["(P2P-1) one"])
    body = [_marker_para(start_t), bl, _marker_para(end_t)]
    inside = read_block_in_adf(_doc(body), marker_id="notes")
    inside[0]["content"][0]["content"][0]["content"][0]["text"] = "MUTATED"
    # Source unchanged.
    assert bl["content"][0]["content"][0]["content"][0]["text"] == "(P2P-1) one"


def test_splice_separate_marker_ids_do_not_interfere():
    """Two splice blocks (e.g. a hypothetical 'reviewers' block alongside
    'notes') must not collide; each marker_id is independent."""
    n_start, n_end = marker_id_text("notes")
    r_start, r_end = marker_id_text("reviewers")
    body = [
        _marker_para(n_start),
        _bullets(["(P2P-1) note"]),
        _marker_para(n_end),
        _para("between"),
        _marker_para(r_start),
        _bullets(["@alice"]),
        _marker_para(r_end),
    ]
    # Splice into 'notes' — 'reviewers' block must stay byte-identical.
    new, changed = splice_in_adf(_doc(body), [_bullets(["(P2P-1) note", "(P2P-2) two"])], marker_id="notes")
    assert changed is True
    # Reviewers region (last 3 blocks) untouched.
    assert new["content"][-3:] == body[-3:]
