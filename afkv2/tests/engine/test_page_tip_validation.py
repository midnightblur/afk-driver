"""Semantic page-tip checks through the public engine commands."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
import engine


def document():
    return {
        "schema": "afkv2.page/1",
        "session": {"id": "tips", "skill": "grill", "feature": "sample", "ticket": "sample",
                    "started": "2026-01-05T09:00:00Z"},
        "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                    "items": [{"id": "card", "kind": "info", "body": {
                        "type": "text", "id": "body", "props": {"text": "Terms"}}}]}],
    }


def check(tmp_path, capsys, doc, verb="check"):
    path = tmp_path / "page.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    status = engine.main([verb, str(path)])
    return status, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("catalog,keys", [
    ("terms", ["queue", "queue"]), ("terms", ["queue", "QUEUE"]),
    ("terms", ["queue", "queues"]), ("terms", ["class", "classes"]),
    ("terms", ["MR", "MRs"]), ("terms", ["MR", "MRES"]), ("terms", ["MR", "mr"]),
    ("terms", ["Queue", "queue"]), ("terms", ["a", "aes"]),
    ("ids", ["card", "card"]),
])
def test_page_tip_collision_paths(tmp_path, capsys, catalog, keys):
    key, value = ("term", "definition") if catalog == "terms" else ("id", "title")
    doc = document()
    doc["tips"] = {catalog: [{key: token, value: "Meaning"} for token in keys]}
    before = copy.deepcopy(doc)
    status, answer = check(tmp_path, capsys, doc)
    assert status == 1, answer
    assert answer["error"]["code"] == "invariant"
    for index in (0, 1):
        assert f"tips.{catalog}[{index}].{key}" in answer["error"]["reason"]
    assert doc == before
    assert json.loads((tmp_path / "page.json").read_text("utf-8")) == before


@pytest.mark.parametrize("keys", [["Mr", "MR"], ["Queue", "QUEUE"], ["a", "as"],
                                   ["a.b", "axb"], ["queue", "queueing"]])
def test_distinct_term_matches_pass(tmp_path, capsys, keys):
    doc = document()
    doc["tips"] = {"terms": [{"term": key, "definition": "Meaning"} for key in keys]}
    status, answer = check(tmp_path, capsys, doc)
    assert status == 0, answer


@pytest.mark.parametrize("identifier", ["missing", "CARD", "R-1"])
def test_stale_reference_names_repair_path(tmp_path, capsys, identifier):
    doc = document()
    doc["tips"] = {"ids": [{"id": "card", "title": "Card"}, {"id": identifier, "title": "Stale"}]}
    status, answer = check(tmp_path, capsys, doc)
    assert status == 1, answer
    assert answer["error"]["code"] == "invariant"
    assert "tips.ids[1].id" in answer["error"]["reason"]
    assert identifier in answer["error"]["reason"]


def test_card_component_nested_component_and_map_node_references_pass(tmp_path, capsys):
    doc = document()
    doc["maps"] = [{"type": "map", "id": "map", "props": {
        "nodes": [{"id": "node", "label": "Node", "state": "open", "round": 1}], "edges": []}}]
    doc["rounds"][0]["items"][0]["body"] = {
        "type": "table", "id": "body", "props": {"columns": ["Part"], "rows": [[{
            "type": "text", "id": "nested", "props": {"text": "Nested"}}]]}}
    doc["tips"] = {"ids": [{"id": key, "title": "Title"} for key in ("card", "body", "map", "node", "nested")],
                   "terms": [{"term": "card", "definition": "A term"}]}
    status, answer = check(tmp_path, capsys, doc)
    assert status == 0, answer


def test_invalid_tips_leave_last_render_unchanged(tmp_path, capsys):
    doc = document()
    doc["tips"] = {"terms": [{"term": "queue", "definition": "One"},
                             {"term": "queues", "definition": "Two"}]}
    html = tmp_path / "page.html"
    html.write_text("Last valid page", encoding="utf-8")
    status, answer = check(tmp_path, capsys, doc, "render")
    assert status == 1 and answer["error"]["code"] == "invariant", answer
    assert html.read_text("utf-8") == "Last valid page"



def test_supplementary_unicode_plural_collision_paths(tmp_path, capsys):
    doc = document()
    doc["tips"] = {"terms": [{"term": "\U0001f680", "definition": "One"},
                             {"term": "\U0001f680s", "definition": "Two"}]}
    status, answer = check(tmp_path, capsys, doc)
    assert status == 1, answer
    assert answer["error"]["code"] == "invariant"
    assert "tips.terms[0].term" in answer["error"]["reason"]
    assert "tips.terms[1].term" in answer["error"]["reason"]


@pytest.mark.parametrize("keys", [["\u03bf\u03c2", "\u039f\u03a3s"], ["\u039f\u03a3s", "\u03bf\u03c2"],
                                   ["\u03bf\u03c2", "\u03bf\u03c3s"], ["\u03bf\u03c3s", "\u03bf\u03c2"],
                                   ["\u03bf\u03c3 \u03bf\u03c2", "\u03bf\u03c3 \u03bf\u03c3s"]])
def test_contextual_lowercase_plural_collision_paths(tmp_path, capsys, keys):
    doc = document()
    doc["tips"] = {"terms": [{"term": key, "definition": "Meaning"} for key in keys]}
    status, answer = check(tmp_path, capsys, doc)
    assert status == 1, answer
    assert "tips.terms[0].term" in answer["error"]["reason"]
    assert "tips.terms[1].term" in answer["error"]["reason"]


def test_distinct_sigma_terms_pass(tmp_path, capsys):
    doc = document()
    doc["tips"] = {"terms": [{"term": key, "definition": "Meaning"} for key in ("\u03bf\u03c2", "\u03bf\u03c3")]}
    status, answer = check(tmp_path, capsys, doc)
    assert status == 0, answer
