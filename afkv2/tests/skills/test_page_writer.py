"""The shared writer's schema boundary, through the producer commands."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
PRODUCERS = ["grill/scripts/round_document.py", "propose-solution/scripts/design_round.py"]
TIPS = {"terms": [{"term": "batch", "definition": "A group of records."}],
        "ids": [{"id": "REQ-1", "title": "Export the selected records."}]}


def run_build(tmp_path, producer, content, replace=False):
    source = tmp_path / "round.json"
    source.write_text(json.dumps(content), "utf-8")
    args = [sys.executable, str(PLUGIN / "skills" / producer), "build",
            "--doc", str(tmp_path / "page.json"), "--session", "s-test", "--ticket", "1",
            "--round-input", str(source)]
    result = subprocess.run(args + (["--replace"] if replace else []), capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout)


def round_input():
    return {"banner": {"settled": [], "unlocks": [], "parked": []}, "items": []}


def check(path):
    result = subprocess.run([sys.executable, str(PLUGIN / "engine/engine.py"), "check", str(path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_authoring_examples_cover_both_schema_versions():
    examples = PLUGIN / "skills/visualize/examples"
    for name, schema in [("all-components.json", "afkv2.page/0"), ("page-owned-tips.json", "afkv2.page/1")]:
        path = examples / name
        doc = json.loads(path.read_text("utf-8"))
        assert doc["schema"] == schema
        if schema.endswith("/1"):
            assert doc["tips"]["terms"] and doc["tips"]["ids"]
        check(path)


@pytest.mark.parametrize("producer", PRODUCERS)
def test_new_producer_session_uses_page_one_and_document_tips(tmp_path, producer):
    assert run_build(tmp_path, producer, {**round_input(), "tips": TIPS})[0] == 0
    path = tmp_path / "page.json"
    doc = json.loads(path.read_text("utf-8"))
    assert doc["schema"] == "afkv2.page/1"
    assert doc["tips"] == TIPS
    check(path)


@pytest.mark.parametrize("producer", PRODUCERS)
@pytest.mark.parametrize("schema", ["afkv2.page/0", "afkv2.page/1"])
def test_resume_preserves_schema_and_existing_tips(tmp_path, producer, schema):
    assert run_build(tmp_path, producer, round_input())[0] == 0
    path = tmp_path / "page.json"
    doc = json.loads(path.read_text("utf-8"))
    doc["schema"] = schema
    if schema.endswith("/1"):
        doc["tips"] = TIPS
    path.write_text(json.dumps(doc), "utf-8")
    assert run_build(tmp_path, producer, round_input(), replace=True)[0] == 0
    resumed = json.loads(path.read_text("utf-8"))
    assert resumed["schema"] == schema
    assert resumed.get("tips") == doc.get("tips")
    check(path)


@pytest.mark.parametrize("schema", ["afkv2.page/0", "afkv2.page/1"])
def test_tip_update_replaces_the_document_dictionary_only_when_supported(tmp_path, schema):
    producer = PRODUCERS[0]
    assert run_build(tmp_path, producer, round_input())[0] == 0
    path = tmp_path / "page.json"
    doc = json.loads(path.read_text("utf-8"))
    doc["schema"] = schema
    path.write_text(json.dumps(doc), "utf-8")
    before = path.read_bytes()
    code, answer = run_build(tmp_path, producer, {**round_input(), "tips": TIPS}, replace=True)
    if schema.endswith("/0"):
        assert code == 1 and answer["error"]["code"] == "bad-schema"
        assert path.read_bytes() == before
    else:
        assert code == 0
        assert json.loads(path.read_text("utf-8"))["tips"] == TIPS
        assert run_build(tmp_path, producer, {**round_input(), "tips": {}}, replace=True)[0] == 0
        assert json.loads(path.read_text("utf-8"))["tips"] == {}
        check(path)
