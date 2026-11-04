"""Page/1 catalog shapes and schema selection through the engine check command."""

import copy
import json
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[2] / "engine"
sys.path.insert(0, str(ENGINE))
import engine
import registry


def document(version="afkv2.page/1"):
    return {
        "schema": version,
        "session": {"id": "tips", "skill": "grill", "feature": "sample", "ticket": "sample",
                    "started": "2026-01-05T09:00:00Z"},
        "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                    "items": [{"id": "card", "kind": "info", "body": {
                        "type": "text", "props": {"text": "Parent"},
                        "children": [{"type": "text", "props": {"text": "A term"}}]}}]}],
    }


def check(tmp_path, capsys, doc):
    path = tmp_path / "page.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    status = engine.main(["check", str(path)])
    return status, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("tips", [None, {}, {"terms": []}, {"ids": []}, {"terms": [], "ids": []},
    {"terms": [{"term": "A" * 128, "definition": "D" * 1000}],
     "ids": [{"id": "card", "title": "T" * 1000}]}])
def test_optional_typed_catalogs_pass_the_engine_check(tmp_path, capsys, tips):
    doc = document()
    if tips is not None:
        doc["tips"] = tips
    status, answer = check(tmp_path, capsys, doc)
    assert status == 0, answer


@pytest.mark.parametrize("catalog,key,value", [("terms", "term", "definition"), ("ids", "id", "title")])
@pytest.mark.parametrize("field,invalid", [("key", ""), ("key", "x" * 129), ("value", ""),
    ("value", "x" * 1001), ("key", None), ("value", 7), ("key", "missing"),
    ("value", "missing"), ("extra", True)])
def test_catalog_fields_refuse_at_the_exact_path(tmp_path, capsys, catalog, key, value, field, invalid):
    entry = {key: "card", value: "Text"}
    name = {"key": key, "value": value, "extra": "extra"}[field]
    if invalid == "missing":
        del entry[name]
    else:
        entry[name] = invalid
    doc = document()
    doc["tips"] = {catalog: [entry]}
    status, answer = check(tmp_path, capsys, doc)
    assert status == 1
    assert answer["error"]["code"] == "schema"
    assert f"field tips.{catalog}[0].{name}:" in answer["error"]["reason"]


@pytest.mark.parametrize("tips,path", [(None, "tips"), ([], "tips"), ({"extra": 1}, "tips.extra"),
    ({"terms": None}, "tips.terms"), ({"ids": {}}, "tips.ids"),
    ({"terms": ["text"]}, "tips.terms[0]"), ({"ids": [None]}, "tips.ids[0]")])
def test_catalog_shapes_are_closed_and_typed(tmp_path, capsys, tips, path):
    doc = document()
    doc["tips"] = tips
    status, answer = check(tmp_path, capsys, doc)
    assert status == 1
    assert answer["error"]["code"] == "schema"
    assert f"field {path}:" in answer["error"]["reason"]


def test_readers_preserve_the_stored_version_and_source(tmp_path):
    for version in ("afkv2.page/0", "afkv2.page/1"):
        doc = document(version)
        path = tmp_path / "page.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        raw, read = engine.load_document(str(path))
        assert raw == read == doc
        assert json.loads(path.read_text("utf-8")) == doc


@pytest.mark.parametrize("version", ["afkv2.page/0", "afkv2.page/1"])
def test_engine_selects_the_document_schema_for_all_components(tmp_path, capsys, monkeypatch, version):
    doc = document(version)
    doc["maps"] = [{"type": "text", "props": {"text": "A map"}}]
    selected = []
    select = registry.component_schema_for

    def record(name):
        selected.append(name)
        return select(name)

    monkeypatch.setattr(registry, "component_schema_for", record)
    status, answer = check(tmp_path, capsys, doc)
    assert status == 0, answer
    assert selected and set(selected) == {version}


def test_nested_component_validation_keeps_the_selected_schema(monkeypatch):
    schema = copy.deepcopy(registry.component_schema_for("afkv2.page/1"))
    schema["$defs"]["component"]["properties"]["v1_only"] = {"type": "boolean"}
    monkeypatch.setattr(registry, "component_schema_for", lambda name: schema)
    part = {"type": "table", "props": {"columns": ["Name"], "rows": [[{
        "type": "text", "props": {"text": "Nested"}, "v1_only": True}]]}}
    assert registry.validate(part, schema_name="afkv2.page/1") == []


def test_page_zero_still_refuses_tips(tmp_path, capsys):
    doc = document("afkv2.page/0")
    doc["tips"] = {}
    status, answer = check(tmp_path, capsys, doc)
    assert status == 1 and "field tips:" in answer["error"]["reason"]


@pytest.mark.parametrize("name", ["v0-sdd-pass.json"])
def test_existing_page_zero_fixtures_keep_their_check_result(tmp_path, capsys, name):
    fixtures = Path(__file__).parent / "fixtures"
    doc = json.loads((fixtures / name).read_text("utf-8"))
    assert check(tmp_path, capsys, doc)[0] == 0
