"""The shared writer's schema boundary, through the producer commands: every write is page/1 (#163 design
ADR-0002), and the document keeps its tips catalog until a round input replaces it."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
PRODUCERS = ["use-lavish/scripts/round_document.py", "propose-solution/scripts/design_round.py"]
TIPS = {"terms": [{"term": "batch", "definition": "A group of records."}],
        "ids": [{"id": "t-export", "title": "Export the selected records."}]}


def run_build(tmp_path, producer, content, replace=False):
    source = tmp_path / "round.json"
    source.write_text(json.dumps(content), "utf-8")
    args = [sys.executable, str(PLUGIN / "skills" / producer), "build",
            "--doc", str(tmp_path / "page.json"), "--session", "s-test", "--ticket", "1",
            "--round-input", str(source)]
    result = subprocess.run(args + (["--replace"] if replace else []), capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout)


def round_input():
    return {
        "banner": {"settled": [], "unlocks": [], "parked": []},
        "items": [{
            "id": "i-export",
            "kind": "confirm",
            "body": {"type": "text", "id": "t-export", "props": {"text": "REQ-1 exports one batch."}},
        }],
    }


def check(path):
    result = subprocess.run([sys.executable, str(PLUGIN / "engine/engine.py"), "check", str(path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def as_format_0(path):
    """Rewrite the built page/1 file as the page/0 file of the same session: no notes, no tips, no format 1
    session fields. Return its bytes."""
    doc = json.loads(path.read_text("utf-8"))
    session = {key: doc["session"][key] for key in ("id", "skill", "feature", "ticket", "started", "links")}
    path.write_text(json.dumps({"schema": "afkv2.page/0", "session": session, "maps": doc["maps"],
                                "rounds": doc["rounds"]}), "utf-8")
    return path.read_bytes()


def test_authoring_examples_are_page_one_and_one_owns_tips():
    examples = PLUGIN / "skills/visualize/examples"
    for name in ("all-components.json", "page-owned-tips.json"):
        path = examples / name
        doc = json.loads(path.read_text("utf-8"))
        assert doc["schema"] == "afkv2.page/1"
        if name == "page-owned-tips.json":
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
def test_resume_of_page_one_keeps_its_tips(tmp_path, producer):
    assert run_build(tmp_path, producer, {**round_input(), "tips": TIPS})[0] == 0
    path = tmp_path / "page.json"
    assert run_build(tmp_path, producer, round_input(), replace=True)[0] == 0
    resumed = json.loads(path.read_text("utf-8"))
    assert resumed["schema"] == "afkv2.page/1"
    assert resumed["tips"] == TIPS
    check(path)


@pytest.mark.parametrize("producer", PRODUCERS)
def test_page_zero_opens_unchanged_and_its_next_round_writes_page_one(tmp_path, producer):
    assert run_build(tmp_path, producer, round_input())[0] == 0
    path = tmp_path / "page.json"
    before = as_format_0(path)
    check(path)
    assert path.read_bytes() == before
    assert run_build(tmp_path, producer, round_input(), replace=True)[0] == 0
    resumed = json.loads(path.read_text("utf-8"))
    assert resumed["schema"] == "afkv2.page/1"
    assert "tips" not in resumed
    check(path)


@pytest.mark.parametrize("schema", ["afkv2.page/0", "afkv2.page/1"])
def test_tip_update_replaces_the_document_dictionary(tmp_path, schema):
    producer = PRODUCERS[0]
    assert run_build(tmp_path, producer, round_input())[0] == 0
    path = tmp_path / "page.json"
    if schema.endswith("/0"):
        as_format_0(path)
    assert run_build(tmp_path, producer, {**round_input(), "tips": TIPS}, replace=True)[0] == 0
    doc = json.loads(path.read_text("utf-8"))
    assert doc["schema"] == "afkv2.page/1" and doc["tips"] == TIPS
    assert run_build(tmp_path, producer, {**round_input(), "tips": {}}, replace=True)[0] == 0
    assert json.loads(path.read_text("utf-8"))["tips"] == {}
    check(path)
