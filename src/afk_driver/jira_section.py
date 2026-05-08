"""ADF section-splice implementation for the Jira parent description.

The splicer is format-only: it identifies the marker pair, replaces the
nodes between them with the caller-supplied ``block_nodes``, and preserves
everything outside byte-identical via ``copy.deepcopy``. Decoration that
should be visible to humans (e.g. an H2 header) lives inside ``block_nodes``,
not in the splicer.

ADF has no comment node, so markers are paragraph nodes containing the bare
identifier text (e.g. ``afk:notes:start``) with an ``inline-code`` text mark.
This renders as visible monospaced text in the Jira UI — the deliberate
visual trade-off for marker-based identification (see ``CONTEXT.md`` §
"Marker pair"). Humans learn to leave them alone; strict mode catches
accidental deletion.
"""

from __future__ import annotations

import copy

from afk_driver.section_splice import SectionMarkerMissing, marker_id_text


def splice_in_adf(
    adf: dict,
    block_nodes: list[dict],
    *,
    marker_id: str,
    create_if_missing: bool = False,
) -> tuple[dict, bool]:
    """Replace the content between the marker pair ``marker_id`` with
    ``block_nodes``. Return ``(new_adf, changed)``; callers skip the PUT when
    not changed.

    Behaviour:
    - **Both markers present, in order**: deep-copy nodes before the start
      marker, then start marker, then ``block_nodes``, then end marker, then
      deep-copy nodes after the end marker.
    - **Both markers absent**: if ``create_if_missing=True``, append
      ``[start_marker, *block_nodes, end_marker]`` to the doc content.
      Otherwise raise ``SectionMarkerMissing``.
    - **One marker present (without its mate), or end before start**: raise
      ``SectionMarkerMissing`` even when ``create_if_missing=True``. This is
      a corrupt state; auto-repair would risk losing whatever block the
      survivor anchors. Manual intervention.

    Idempotent: replaying with the same ``(adf, block_nodes, marker_id)``
    that yielded ``changed=False`` returns the original ``adf`` object
    identity unchanged.
    """
    start_text, end_text = marker_id_text(marker_id)
    blocks = list(adf.get("content", []) or [])
    start_idx = _find_marker_index(blocks, start_text)
    end_idx = _find_marker_index(blocks, end_text)

    if start_idx is None and end_idx is None:
        if not create_if_missing:
            raise SectionMarkerMissing(
                f"marker pair {marker_id!r} absent (create_if_missing=False)"
            )
        new_blocks = (
            [copy.deepcopy(b) for b in blocks]
            + [_make_marker_paragraph(start_text)]
            + [copy.deepcopy(n) for n in block_nodes]
            + [_make_marker_paragraph(end_text)]
        )
    elif start_idx is not None and end_idx is not None and start_idx < end_idx:
        new_blocks = (
            [copy.deepcopy(b) for b in blocks[: start_idx + 1]]
            + [copy.deepcopy(n) for n in block_nodes]
            + [copy.deepcopy(b) for b in blocks[end_idx:]]
        )
    else:
        raise SectionMarkerMissing(
            f"marker pair {marker_id!r} malformed "
            f"(start_idx={start_idx} end_idx={end_idx})"
        )

    new_adf = {"type": "doc", "version": 1, "content": new_blocks}
    if new_adf == adf:
        return adf, False
    return new_adf, True


def read_block_in_adf(adf: dict, *, marker_id: str) -> list[dict] | None:
    """Return deep-copied nodes strictly between the marker pair, or ``None``
    if the marker pair is absent or malformed. Used by callers that need to
    read the existing block content (e.g. to merge new bullets with old).
    """
    start_text, end_text = marker_id_text(marker_id)
    blocks = adf.get("content", []) or []
    start_idx = _find_marker_index(blocks, start_text)
    end_idx = _find_marker_index(blocks, end_text)
    if start_idx is None or end_idx is None or start_idx >= end_idx:
        return None
    return [copy.deepcopy(b) for b in blocks[start_idx + 1 : end_idx]]


def render_bullets_adf(items: list[str]) -> list[dict]:
    """Render flat strings as a single ``bulletList`` ADF node. Empty input
    returns an empty list (caller can splice-in nothing-but-decoration if
    they want).
    """
    if not items:
        return []
    return [
        {
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
    ]


def _find_marker_index(blocks: list[dict], marker_text: str) -> int | None:
    """Find the top-level paragraph node whose only text child is ``marker_text``
    bearing an ``inline-code`` mark. Marker paragraphs may be authored only by
    the splicer; the precise shape match (single text child + code mark + exact
    text) is intentional — bare-text matches risk colliding with human prose
    that happens to mention the identifier.
    """
    for i, b in enumerate(blocks):
        if b.get("type") != "paragraph":
            continue
        content = b.get("content") or []
        if len(content) != 1:
            continue
        node = content[0]
        if node.get("type") != "text":
            continue
        if node.get("text") != marker_text:
            continue
        marks = node.get("marks") or ()
        if any(m.get("type") == "code" for m in marks):
            return i
    return None


def _make_marker_paragraph(text: str) -> dict:
    """Build a marker paragraph: a paragraph whose only child is a text node
    with the literal ``text`` and an ``inline-code`` mark. The shape mirrors
    what ``_find_marker_index`` looks for — round-trip stable.
    """
    return {
        "type": "paragraph",
        "content": [
            {"type": "text", "text": text, "marks": [{"type": "code"}]}
        ],
    }
