"""Exercise the shipped resolver with rendered payloads; live DOM proof lives in tests/live."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
from shell import inject


def resolve(text, ids=None, terms=None, shared=None, broken=False):
    html = inject.tips_block(shared or {}, ids or {}, terms or {})
    blocks = dict(re.findall(r'<script id="([^"]+)" type="application/json">(.*?)</script>', html, re.S))
    if broken:
        blocks["afkv2-tips-payload"] = "{"
    # Run the actual initialization and resolver, stopping before DOM scanning.
    script = inject._asset("tips.js").split("  function wrap(root)")[0]
    driver = "const document={getElementById:id=>blocks[id]===undefined?null:{textContent:blocks[id]}};"
    driver += script + "\n console.log(JSON.stringify({tip:tipFor(input)}));})();"
    program = "const blocks=" + json.dumps(blocks) + ";const input=" + json.dumps(text) + ";" + driver
    result = subprocess.run(["node", "-e", program], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)["tip"]


def test_page_id_precedence():
    assert resolve("card", {"card": "ID"}, {"card": "Term"}, {"card": "Shared"}) == "ID"
    assert resolve("queue", terms={"queue": "Page"}, shared={"queue": "Shared"}) == "Page"
    assert resolve("queue", shared={"queue": "Shared"}) == "Shared"


@pytest.mark.parametrize("text,expected", [("CARD-1", "ID"), ("card-1", None), ("CARD-1s", None), ("CARD-1es", None)])
def test_page_ids_are_exact(text, expected):
    assert resolve(text, {"CARD-1": "ID"}) == expected


@pytest.mark.parametrize("text", ["queue", "Queue", "QUEUE", "queues", "Queues"])
def test_page_term_case_plural_and_shared_precedence(text):
    assert resolve(text, terms={"queue": "Page"}, shared={"queues": "Shared plural"}) == "Page"


def test_legacy_case_plural_and_unknown():
    assert resolve("MRs", shared={"MR": "Merge request"}) == "Merge request"
    assert resolve("mrs", shared={"MR": "Merge request"}) is None
    assert resolve("classes", shared={"class": "Class"}) == "Class"
    assert resolve("unknown", shared={"class": "Class"}) is None


def test_literal_values_and_prototype_names():
    literal = '<img src=x onerror="alert(1)"><a href="https://example.invalid">x</a>'
    assert resolve("queue", terms={"queue": literal}) == literal
    assert resolve("constructor", terms={"constructor": "Literal key"}) == "Literal key"


def test_bad_payload_keeps_shared_resolver():
    assert resolve("queue", {"queue": "Page"}, shared={"queue": "Shared"}, broken=True) == "Shared"
