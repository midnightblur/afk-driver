"""The shared round builder: `after` on a section and the "Driven by" block of a decided card (SDD §14 rows
"shared section merge" and "decided card fields"; ADR-0001 and ADR-0004 design)."""

import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
for _folder in (PLUGIN / "skills" / "use-lavish" / "scripts", PLUGIN / "scripts", PLUGIN / "engine"):
    sys.path.insert(0, str(_folder))

import round_document as rd  # noqa: E402

SESSION = {"id": "s-1", "skill": "grill", "feature": "PROJ-1", "ticket": "PROJ-1"}
DECIDED = {"decision": "Use a csv file.", "alternatives": ["An xls file"], "evidence": "The export reads csv.",
           "grade": "repo", "why": "It is the format of today.", "reverse": "Write xls instead."}


def decided_card(item_id="i-a", **extra):
    return {"id": item_id, "kind": "decided", "body": {"type": "text", "id": f"{item_id}-body", "props": {"text": "x"}},
            "decided": {**DECIDED, **extra}}


def build(path, *items):
    return rd.build_round_document(path, SESSION, {"banner": {"settled": [], "unlocks": [], "parked": []},
                                                   "items": list(items)})


def components(path):
    doc = rd.read_json(path)
    return list(rd._components(doc["rounds"][-1]["items"][-1]["body"]))


@pytest.fixture
def path(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return tmp_path / "pages" / "grill-s-1.json"


# ---- the "Driven by" block (ADR-0004 design; PRD AC-009)


def test_a_decided_card_that_sends_driven_by_shows_a_driven_by_block_with_each_id(path):
    answer = build(path, decided_card(driven_by=["AC-009", "ADR-0004"]))
    assert answer["degraded"] == []
    block = next(c for c in components(path) if c.get("id") == "i-a-driven-by")
    assert block["props"]["label"] == rd.DRIVEN_BY_LABEL == "Driven by"
    assert block["props"]["text"] == "AC-009, ADR-0004"


@pytest.mark.parametrize("driven_by", ["AC-009", 5, ["AC-009", ""], ["AC-009", 7], {"AC-009": 1}])
def test_a_driven_by_that_is_not_a_list_of_id_strings_is_refused(path, driven_by):
    with pytest.raises(rd.Refusal) as refused:
        build(path, decided_card(driven_by=driven_by))
    assert refused.value.code == "bad-item" and "driven_by" in refused.value.reason
    assert not path.exists()


def test_the_driven_by_block_follows_the_decision(path):
    build(path, decided_card(driven_by=["AC-009"]))
    ids = [c.get("id") for c in components(path)]
    assert ids.index("i-a-driven-by") == ids.index("i-a-decision") + 1


def test_a_decided_card_without_driven_by_renders_exactly_as_before(path, tmp_path):
    fields, whole = rd._decided_fields("i-a", DECIDED, set())
    assert whole and not any(field["props"]["label"] == "Driven by" for field in fields)
    assert [field["id"] for field in fields] == ["i-a-decision", "i-a-why", "i-a-alternatives", "i-a-evidence",
                                                 "i-a-reverse", "i-a-scope"]
    build(path, decided_card())
    assert "i-a-driven-by" not in [c.get("id") for c in components(path)]


def test_an_empty_driven_by_adds_no_block(path):
    build(path, decided_card(driven_by=[]))
    assert "i-a-driven-by" not in [c.get("id") for c in components(path)]


# ---- `after` on a section (ADR-0001 design; SDD §14 row "shared section merge")

import page_round  # noqa: E402
from grill_common import Refusal  # noqa: E402

CHANGE = {"cause": "finding", "text": "Wrote the part."}


def section(section_id, **extra):
    return {"id": section_id, "title": f"Title of {section_id}", "state": "current", "change": CHANGE,
            "body": {"type": "text", "id": f"{section_id}-text", "props": {"text": "Text."}}, **extra}


def answer_current_round(path):
    """Accept the first card of the current round, unless the round holds an answer already."""
    current = rd.current_round(rd.read_json(path))
    if not current.get("responses"):
        raw = path.with_name("raw.txt")
        raw.write_text(f"[round R-{current['n']}]\n{current['items'][0]['id']} accept", "utf-8")
        page_round.ingest(path, raw)


def build_sections(path, item_id, *sections):
    """Build the next round with 1 card and the given sections; answer the round before it first."""
    if path.exists():
        answer_current_round(path)
    return rd.build_round_document(path, SESSION, {"banner": {"settled": [], "unlocks": [], "parked": []},
                                                   "items": [decided_card(item_id)], "sections": list(sections)})


def section_ids(path):
    return [entry["id"] for entry in rd.read_json(path)["sections"]]


def test_a_section_with_after_a_same_round_section_is_placed_right_after_it(path):
    build_sections(path, "i-a", section("sec-l1"), section("sec-l3"), section("sec-l2", after="sec-l1"))
    assert section_ids(path) == ["sec-l1", "sec-l2", "sec-l3"]


def test_a_section_with_after_a_stored_section_is_placed_right_after_it(path):
    build_sections(path, "i-a", section("sec-system"), section("sec-l1"))
    build_sections(path, "i-b", section("sec-crit-auth", after="sec-system"))
    assert section_ids(path) == ["sec-system", "sec-crit-auth", "sec-l1"]


def test_the_stored_section_holds_no_after_field(path):
    build_sections(path, "i-a", section("sec-l1"), section("sec-l2", after="sec-l1"))
    assert all("after" not in entry for entry in rd.read_json(path)["sections"])


@pytest.mark.parametrize("after", ["sec-none", "sec-l2"])
def test_a_section_with_after_that_names_no_other_section_is_refused_and_nothing_is_written(path, after):
    build_sections(path, "i-a", section("sec-l1"))
    answer_current_round(path)
    before = path.read_bytes()
    with pytest.raises(Refusal) as refused:
        build_sections(path, "i-b", section("sec-l2", after=after))
    assert refused.value.code == "bad-entry" and "names no other section" in refused.value.reason
    assert path.read_bytes() == before


def test_a_round_without_after_builds_the_same_section_order_as_before(path):
    build_sections(path, "i-a", section("sec-l1"), section("sec-l2"))
    build_sections(path, "i-b", section("sec-l0"))
    assert section_ids(path) == ["sec-l1", "sec-l2", "sec-l0"]


def test_a_section_with_after_a_section_sent_later_in_the_same_round_is_refused(path):
    """Order matters: `after` resolves against stored sections and the sections sent before it."""
    with pytest.raises(Refusal) as refused:
        build_sections(path, "i-a", section("sec-l2", after="sec-l1"), section("sec-l1"))
    assert refused.value.code == "bad-entry" and "sent before this one" in refused.value.reason
    assert not path.exists()


def test_a_stored_section_with_after_that_names_itself_is_refused(path):
    build_sections(path, "i-a", section("sec-l1"), section("sec-l2"))
    answer_current_round(path)
    before = path.read_bytes()
    changed = section("sec-l2", after="sec-l2")
    changed["title"] = "New title"
    with pytest.raises(Refusal) as refused:
        build_sections(path, "i-b", changed)
    assert refused.value.code == "bad-entry" and "names no other section" in refused.value.reason
    assert path.read_bytes() == before


def test_a_stored_section_resent_with_after_moves_to_its_new_place(path):
    build_sections(path, "i-a", section("sec-l1"), section("sec-l2"), section("sec-l3"))
    build_sections(path, "i-b", section("sec-l3", after="sec-l1"))
    assert section_ids(path) == ["sec-l1", "sec-l3", "sec-l2"]


def test_a_new_section_with_after_null_is_placed_first(path):
    build_sections(path, "i-a", section("sec-l1"), section("sec-l2"))
    build_sections(path, "i-b", section("sec-asks", after=None))
    assert section_ids(path) == ["sec-asks", "sec-l1", "sec-l2"]
    assert all("after" not in entry for entry in rd.read_json(path)["sections"])


def test_a_stored_section_resent_with_after_null_moves_first(path):
    build_sections(path, "i-a", section("sec-l1"), section("sec-l2"), section("sec-l3"))
    build_sections(path, "i-b", section("sec-l3", after=None))
    assert section_ids(path) == ["sec-l3", "sec-l1", "sec-l2"]


def test_a_first_section_resent_with_after_null_and_no_other_change_is_refused(path):
    build_sections(path, "i-a", section("sec-l1"), section("sec-l2"))
    answer_current_round(path)
    with pytest.raises(Refusal) as refused:
        build_sections(path, "i-b", section("sec-l1", after=None))
    assert refused.value.code == "unchanged-entry"


def test_a_section_with_after_null_in_round_1_goes_before_the_sections_sent_before_it(path):
    build_sections(path, "i-a", section("sec-l1"), section("sec-asks", after=None))
    assert section_ids(path) == ["sec-asks", "sec-l1"]
