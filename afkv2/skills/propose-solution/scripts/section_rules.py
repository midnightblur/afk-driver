"""The section rules of a design page: catalog order, shape, caption and links (ADR-0001 design, SDD §6 I-1, I-2).

The section catalog, the pattern columns and the performance parts are tables of DRAFT.md, the one home of each.
`check_sections` answers each broken rule as 1 line `<code>: <reason>`; an empty list means every rule holds.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL.parent / "use-lavish" / "scripts"))

import round_document as rd  # noqa: E402
from grill_common import Refusal  # noqa: E402

DRAFT = SKILL / "DRAFT.md"
# A `diagram` is Mermaid text that the engine draws as a picture (engine/components/text_diagram.py).
PICTURES = rd.PICTURES | {"diagram"}
PICTURE_ROOT_KINDS = {"system", "critical", "level"}
CAPTION_LABEL = "What to see"
SUMMARY_LABEL = "Summary"
SUMMARY_LINES = 2
NO_PATTERN = "no pattern applied"
NO_RISK_LABEL = "No performance risk"
BUDGET_TONES = {"measured", "inferred", "estimated"}
INACTIVE = {"merged", "removed"}
CELL = re.compile(r"\s*\|\s*")


def _table(heading):
    """The body rows of the first table under the `### <heading>` of DRAFT.md, each a list of cells."""
    text = DRAFT.read_text("utf-8")
    start = text.index(f"### {heading}\n")
    rows = []
    for line in text[start:].splitlines()[1:]:
        if line.startswith("#"):
            break
        if line.startswith("|"):
            rows.append(CELL.split(line.strip())[1:-1])
        elif rows:
            break
    return [row for row in rows[1:] if not set("".join(row)) <= set("-")]


def catalog():
    """The section catalog rows of DRAFT.md in page order: {id, part, kind, opens_with}."""
    return [{"id": sid.strip("`"), "part": part, "kind": kind, "opens_with": opens}
            for sid, part, kind, opens in _table("Section catalog")]


def _row(section_id):
    for k, row in enumerate(catalog()):
        prefix, _, rest = row["id"].partition("<")
        if (section_id == row["id"] if not rest else
                section_id.startswith(prefix) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", section_id[len(prefix):])):
            return k, row
    raise Refusal("section-unknown", f"the section catalog of DRAFT.md names no section id {section_id!r}")


def order_key(section_id):
    """The place of a section id in the catalog order; every critical section shares 1 place."""
    return _row(section_id)[0]


def _kind(section_id):
    return _row(section_id)[1]["kind"]


def _components(component):
    """The component and every component inside it: its children and the component cells of a table."""
    yield component
    nested = list(component.get("children") or [])
    if component.get("type") == "table":
        nested += [cell for row in (component.get("props") or {}).get("rows") or [] for cell in row
                   if isinstance(cell, dict)]
    for child in nested:
        yield from _components(child)


def _props(component):
    return component.get("props") or {}


def _labelled(component, label):
    return component.get("type") == "text" and _props(component).get("label") == label


def _has_caption(picture):
    props = _props(picture)
    return bool(props.get("title") or props.get("caption")
                or any(_labelled(child, CAPTION_LABEL) for child in picture.get("children") or []))


def _level_shape(sid, body):
    children = body.get("children") or []
    summary = next((child for child in children if _labelled(child, SUMMARY_LABEL)), None)
    if summary is None:
        return [f"section-shape: {sid} holds no text labelled {SUMMARY_LABEL!r} under its picture"]
    lines = [line for line in str(_props(summary).get("text") or "").splitlines() if line.strip()]
    if len(lines) > SUMMARY_LINES:
        return [f"section-shape: the summary of {sid} has {len(lines)} lines; at most {SUMMARY_LINES}"]
    open_detail = [child for child in children if child is not summary and not _labelled(child, CAPTION_LABEL)
                   and not child.get("fold")]
    if open_detail:
        return [f"section-shape: {sid} shows {len(open_detail)} detail part(s) open; give each a fold"]
    return []


def _patterns_shape(sid, body):
    columns = [row[0].lower() for row in _table("Pattern columns")]
    for component in _components(body):
        if component.get("type") == "table" and [c.lower() for c in _props(component).get("columns") or []] == columns:
            return []
        if component.get("type") == "text" and str(_props(component).get("text") or "").strip().lower() == NO_PATTERN:
            return []
    return [f"section-shape: {sid} holds no table with the pattern columns of DRAFT.md and no line {NO_PATTERN!r}"]


def _performance_shape(sid, body):
    if _labelled(body, NO_RISK_LABEL):
        lines = [line for line in str(_props(body).get("text") or "").splitlines() if line.strip()]
        if len(lines) != 1 or body.get("children"):
            return [f"section-shape: the no-risk line of {sid} is 1 line with nothing under it"]
        return []
    parts = {}
    for component in _components(body):
        label = str(_props(component).get("label") or "") if component.get("type") == "text" else ""
        parts.setdefault(label.split(" ")[0], component)
    missing = [row[0] for row in _table("Performance parts") if row[0] not in parts]
    if missing:
        return [f"section-shape: {sid} holds no part {', '.join(missing)}; label each part 'PF-<n> <name>'"]
    tables = [c for c in _components(parts["PF-4"]) if c.get("type") == "table"]
    rows = [row for c in tables for row in _props(c).get("rows") or []]
    unmarked = [n for n, row in enumerate(rows, 1)
                if not any(cell.get("type") == "chip" and _props(cell).get("tone") in BUDGET_TONES
                           for cell in row if isinstance(cell, dict))]
    if not rows or unmarked:
        return [f"section-shape: each PF-4 budget row of {sid} needs a chip marked "
                f"{', '.join(sorted(BUDGET_TONES))}; rows without one: {unmarked or 'no budget table'}"]
    return []


SHAPES = {"level": _level_shape, "patterns": _patterns_shape, "performance": _performance_shape}


def _shape(sid, kind, body):
    if kind in PICTURE_ROOT_KINDS and body.get("type") not in PICTURES:
        return [f"section-shape: {sid} opens with a {body.get('type')!r}, not a picture"]
    failures = SHAPES[kind](sid, body) if kind in SHAPES else []
    if kind == "critical" and not any(c.get("type") == "chip" and str(_props(c).get("text") or "").lower()
                                      .startswith("critical") for c in _components(body)):
        failures.append(f"section-shape: {sid} holds no chip whose text starts 'critical'")
    return failures


def _captions(sid, body):
    return [f"section-caption: a {c['type']} picture{' ' + c['id'] if c.get('id') else ''} of {sid} has no caption "
            f"labelled {CAPTION_LABEL!r} and no title"
            for c in _components(body) if c.get("type") in PICTURES and not _has_caption(c)]


def _active(sections):
    return [entry for entry in sections if entry.get("state") not in INACTIVE]


def check_sections(doc_sections):
    """Each broken section rule, as `<code>: <reason>`: 1 unknown id per line, the first section out of order,
    then the shape and caption of each section."""
    failures, known, last, out_of_order = [], [], None, None
    for entry in _active(doc_sections):
        try:
            key = order_key(entry["id"])
        except Refusal as refusal:
            failures.append(f"{refusal.code}: {refusal.reason}")
            continue
        known.append(entry)
        if last is None or key >= last[0]:
            last = (key, entry["id"])
        elif out_of_order is None:
            out_of_order = (f"section-order: {entry['id']} stands after {last[1]}; the section catalog of DRAFT.md "
                            f"puts it before")
            failures.append(out_of_order)
    for entry in known:
        body = entry.get("body") or {}
        failures += _shape(entry["id"], _kind(entry["id"]), body) + _captions(entry["id"], body)
    return failures


def fill_links(sections):
    """A copy of the sections; each level section links to the next level section and to each critical section
    that names it in its links. Every link already there stays, and no link repeats."""
    filled = copy.deepcopy(sections)
    active = [entry for entry in _active(filled) if _row_or_none(entry["id"])]
    levels = [entry for entry in active if _kind(entry["id"]) == "level"]
    critical = [entry for entry in active if _kind(entry["id"]) == "critical"]
    for k, level in enumerate(levels):
        wanted = levels[k + 1:k + 2] + [crit for crit in critical if level["id"] in (crit.get("links") or [])]
        links = list(level.get("links") or [])
        links += [other["id"] for other in wanted if other["id"] not in links]
        if links:
            level["links"] = links
    return filled


def _row_or_none(section_id):
    try:
        return _row(section_id)
    except Refusal:
        return None
