"""Durable page-tip source through the engine's render entry point."""

import copy
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
import engine
from shell import inject, page


class SourceParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.sources = []
        self.tags = []
        self.active = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        self.active = tag == "script" and dict(attrs).get("id") == "afkv2-page-tip-source"
        if self.active:
            assert dict(attrs)["type"] == "application/json"
            self.sources.append("")

    def handle_data(self, data):
        if self.active:
            self.sources[-1] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False


def source(html):
    parsed = SourceParser(html)
    assert len(parsed.sources) == 1
    return json.loads(parsed.sources[0])


@pytest.fixture
def render_case(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    root = tmp_path / "repo"
    (root / ".afkv2").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "specs"}), "utf-8")
    path = root / "specs" / "pages" / "grill-tips.json"
    path.parent.mkdir(parents=True)
    doc = {
        "schema": "afkv2.page/1",
        "session": {"id": "tips", "skill": "grill", "feature": "sample", "ticket": "sample",
                    "started": "2026-01-05T09:00:00Z"},
        "tips": {"terms": [{"term": "queue", "definition": "Waiting work"}],
                 "ids": [{"id": "card", "title": "Decision"}]},
        "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                    "items": [{"id": "card", "kind": "info", "body": {
                        "type": "text", "props": {"text": "Queue"}}}]}],
    }
    return path, doc


def render(path, doc, capsys):
    path.write_text(json.dumps(doc), "utf-8")
    status = engine.main(["render", str(path)])
    answer = json.loads(capsys.readouterr().out)
    return status, answer


@pytest.mark.parametrize("unsafe", [
    '</ScRiPt><img id="injected" src=x onerror=alert(1)>',
    '<!--<script>nested</script></body><!-- afkv2-page-tips:start -->removed<!-- afkv2-page-tips:end -->',
    'Literal **bold**, `code`, <b>tag</b>, &amp;, "quotes"\n\u96ea \U0001f680 \u2028 \u2029',
    '\ud800',
])
def test_page_tip_source_round_trip(render_case, capsys, unsafe):
    path, doc = render_case
    doc["tips"]["terms"][0]["definition"] = unsafe
    doc["tips"]["ids"][0]["title"] = unsafe
    before = copy.deepcopy(doc)
    status, answer = render(path, doc, capsys)
    assert status == 0, answer
    html = path.with_suffix(".html").read_text("utf-8")
    assert source(html) == doc["tips"]
    assert doc == before
    assert not any(attrs.get("id") == "injected" for _, attrs in SourceParser(html).tags)
    assert source(inject.TIPS_BLOCK.sub("", html)) == doc["tips"]
    assert source(inject.inject(html, {"shared": "Definition"})) == doc["tips"]
    first = path.with_suffix(".html").read_bytes()
    assert render(path, doc, capsys)[0] == 0
    assert path.with_suffix(".html").read_bytes() == first


@pytest.mark.parametrize("tips", [None, {}, {"terms": []}, {"ids": []}])
def test_empty_page_one_still_identifies_its_source(render_case, capsys, tips):
    path, doc = render_case
    doc.pop("tips")
    if tips is not None:
        doc["tips"] = tips
    assert render(path, doc, capsys)[0] == 0
    assert source(path.with_suffix(".html").read_text("utf-8")) == {"terms": [], "ids": []}


def test_page_zero_has_no_source_block(render_case, capsys):
    path, doc = render_case
    doc["schema"] = "afkv2.page/0"
    doc.pop("tips")
    assert render(path, doc, capsys)[0] == 0
    assert not SourceParser(path.with_suffix(".html").read_text("utf-8")).sources


def test_new_round_replaces_page_meaning(render_case, capsys):
    path, doc = render_case
    assert render(path, doc, capsys)[0] == 0
    doc["rounds"][0]["state"] = "settled"
    doc["rounds"].append({"n": 2, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                          "items": [{"id": "next", "kind": "info", "body": {
                              "type": "text", "props": {"text": "Next round"}}}]})
    doc["tips"]["terms"][0]["definition"] = "Changed meaning"
    doc["tips"]["ids"][0]["title"] = "Changed title"
    status, answer = render(path, doc, capsys)
    assert status == 0, answer
    assert source(path.with_suffix(".html").read_text("utf-8")) == doc["tips"]


@pytest.mark.parametrize("invalid", ["collision", "stale-id", "shape"])
def test_invalid_tips_preserve_previous_render(render_case, capsys, invalid):
    path, doc = render_case
    assert render(path, doc, capsys)[0] == 0
    previous = path.with_suffix(".html").read_bytes()
    if invalid == "collision":
        doc["tips"]["terms"].append({"term": "queues", "definition": "Duplicate"})
    elif invalid == "stale-id":
        doc["tips"]["ids"][0]["id"] = "missing"
    else:
        doc["tips"]["terms"][0]["definition"] = 1
    status, answer = render(path, doc, capsys)
    assert status == 1, answer
    assert answer["error"]["code"] in {"schema", "invariant"}
    assert path.with_suffix(".html").read_bytes() == previous


def test_source_serialization_failure_preserves_previous_render(render_case, capsys, monkeypatch):
    path, doc = render_case
    assert render(path, doc, capsys)[0] == 0
    previous = path.with_suffix(".html").read_bytes()
    path.write_text(json.dumps(doc), "utf-8")

    def failed_dumps(*args, **kwargs):
        raise ValueError("source serialization failed")

    monkeypatch.setattr(page.json, "dumps", failed_dumps)
    with pytest.raises(ValueError, match="source serialization failed"):
        engine.main(["render", str(path)])
    assert path.with_suffix(".html").read_bytes() == previous
