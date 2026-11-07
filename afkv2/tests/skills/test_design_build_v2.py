"""Tests for the design build on a page format 2 document: sections, decisions, banner, ticket card, fork credits.

Each build runs in process against the real page engine (SDD §3 row S-1).
"""

import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / "skills" / "propose-solution" / "scripts"))

import design_round as dr  # noqa: E402
import page_round  # noqa: E402
import round_document as rd  # noqa: E402
from grill_common import Refusal  # noqa: E402

SESSION = {"id": "s-1", "skill": "propose-solution", "feature": "PROJ-1", "ticket": "PROJ-1"}


def text(words, label=None, fold=None, children=None):
    props = {"text": words, **({"label": label} if label else {})}
    return {"type": "text", "props": props, **({"fold": fold} if fold else {}),
            **({"children": children} if children else {})}


def picture(children=()):
    return {"type": "graph", "props": {"nodes": [{"id": "n1", "label": "A"}]},
            "children": [text("what passes", label="What to see"), *children]}


def level_body():
    return picture([text("the summary", label="Summary"), text("detail", fold="Detail")])


def critical_body():
    return picture([{"type": "chip", "props": {"text": "critical", "tone": "proposed"}}])


def section(sid, body=None, **extra):
    return {"id": sid, "title": sid, "state": "current", "body": body or level_body(),
            "change": {"cause": "finding", "text": "drafted"}, **extra}


def confirm(item_id):
    return {"id": item_id, "kind": "confirm", "body": text("A reading.") | {"id": f"{item_id}-text"}}


def round_of(*items, **extra):
    return {"banner": {"settled": [], "unlocks": [], "parked": []}, "items": list(items), **extra}


def doc_path(tmp_path):
    path = tmp_path / "PROJ-1" / "pages" / "s-1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def answer_current_round(path):
    """Accept every card of the current round, unless the round holds an answer already."""
    current = rd.current_round(rd.read_json(path))
    if not current.get("responses"):
        raw = path.with_name("raw.txt")
        lines = [f"{item['id']} accept" for item in current["items"] if item["kind"] != "info"]
        raw.write_text("\n".join([f"[round R-{current['n']}]", *lines]), "utf-8")
        page_round.ingest(path, raw)


def build(tmp_path, round_input, **kwargs):
    """Build the next round; answer the round before it first. A round with no card gets 1 confirm card."""
    path = doc_path(tmp_path)
    if path.exists():
        answer_current_round(path)
    if not round_input.get("items"):
        n = len(rd.read_json(path)["rounds"]) + 1 if path.exists() else 1
        round_input = {**round_input, "items": [confirm(f"c-{n}")]}
    return dr.build_design_round(path, SESSION, round_input, **kwargs)


def stored(tmp_path):
    return json.loads(doc_path(tmp_path).read_text("utf-8"))


def refused(tmp_path, round_input, **kwargs):
    with pytest.raises(Refusal) as refusal:
        build(tmp_path, round_input, **kwargs)
    return refusal.value


# --- sections: order, shape, links (SDD §6 I-1, I-2; PRD AC-005, AC-006)

def test_a_section_out_of_catalog_order_is_refused_before_any_write(tmp_path):
    refusal = refused(tmp_path, round_of(sections=[section("sec-l2"), section("sec-l1")]))
    assert refusal.code == "section-order" and "sec-l1" in refusal.reason
    assert not doc_path(tmp_path).exists()


def test_a_level_section_without_its_summary_is_refused(tmp_path):
    refusal = refused(tmp_path, round_of(sections=[section("sec-l1", picture())]))
    assert refusal.code == "section-shape"
    assert not doc_path(tmp_path).exists()


def test_a_section_placed_with_after_is_checked_in_its_merged_place(tmp_path):
    build(tmp_path, round_of(sections=[section("sec-l1"), section("sec-l3")]))
    refusal = refused(tmp_path, round_of(sections=[section("sec-l4", after="sec-l1")]))
    assert refusal.code == "section-order"
    answer = build(tmp_path, round_of(sections=[section("sec-l2", after="sec-l1")]))
    assert answer["section_order"] == ["sec-l1", "sec-l2", "sec-l3"]


def test_a_built_page_links_each_level_to_the_next_level_and_its_critical_sections(tmp_path):
    build(tmp_path, round_of(sections=[section("sec-crit-keys", critical_body(), links=["sec-l3"]),
                                       section("sec-l1"), section("sec-l3")]))
    links = {entry["id"]: entry.get("links") for entry in stored(tmp_path)["sections"]}
    assert links["sec-l1"] == ["sec-l3"]
    assert links["sec-l3"] == ["sec-crit-keys"]
    assert links["sec-crit-keys"] == ["sec-l3"]


def test_a_stored_level_section_gets_the_link_to_a_later_level_with_a_change_line(tmp_path):
    build(tmp_path, round_of(sections=[section("sec-l1")]))
    build(tmp_path, round_of(sections=[section("sec-l2")]))
    level = next(entry for entry in stored(tmp_path)["sections"] if entry["id"] == "sec-l1")
    assert level["links"] == ["sec-l2"]
    assert [line["round"] for line in level["changes"]] == [1, 2]
