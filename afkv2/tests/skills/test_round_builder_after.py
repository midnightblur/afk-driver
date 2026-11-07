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
    assert "AC-009" in block["props"]["text"] and "ADR-0004" in block["props"]["text"]


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
