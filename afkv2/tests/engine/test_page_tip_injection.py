"""Typed tooltip reconstruction through render and launcher reopen."""

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
import engine
import launcher
from shell import inject


class Scripts(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.blocks = {}
        self.active = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = dict(attrs).get("id")
            if self.active:
                assert self.active not in self.blocks
                self.blocks[self.active] = ""

    def handle_data(self, data):
        if self.active:
            self.blocks[self.active] += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = None


def payload(html):
    return json.loads(Scripts(html).blocks["afkv2-tips-payload"])


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.delenv("LAVISH_AXI_HOST", raising=False)
    root = tmp_path / "repo"
    (root / ".afkv2").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".afkv2" / "config.json").write_text('{"spec_folder": "specs"}', "utf-8")
    (root / "GLOSSARY.md").write_text("**Queue**: Shared queue.\n\n**Worker**: Shared worker.\n", "utf-8")
    path = root / "specs" / "pages" / "grill-tips.json"
    path.parent.mkdir(parents=True)
    (path.parent.parent / "PAGE-TIPS.md").write_text("**Legacy**: Legacy only.\n", "utf-8")
    seed = tmp_path / "seed.json"
    seed.write_text("{}", "utf-8")
    monkeypatch.setattr(inject, "SEED", seed)
    monkeypatch.setattr(inject, "PLUGIN_GLOSSARY", tmp_path / "none.md")
    # Execute launcher.run, substituting only the external host process.
    monkeypatch.setattr(launcher, "upstream", lambda args: [sys.executable, "-c", "print('opened')"])
    doc = {
        "schema": "afkv2.page/1",
        "session": {"id": "tips", "skill": "grill", "feature": "sample", "ticket": "sample",
                    "started": "2026-01-05T09:00:00Z"},
        "tips": {"terms": [{"term": "queue", "definition": "Page queue."}],
                 "ids": [{"id": "card", "title": "Page card."}]},
        "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                    "items": [{"id": "card", "kind": "info", "body": {
                        "type": "text", "props": {"text": "Queue worker card"}}}]}],
    }
    return path, doc


@pytest.mark.parametrize("kind", ["page/0", "page/1", "arbitrary"])
def test_page_tip_reopen_contract(case, capsys, kind):
    path, doc = case
    html_path = path.with_suffix(".html")
    if kind == "arbitrary":
        html_path.write_text('<html><body><p>Queue worker</p><button title="Help">Go</button></body></html>', "utf-8")
        assert launcher.run(["open", str(html_path), "--no-open"])[0] == 0
    else:
        doc["schema"] = "afkv2." + kind
        if kind == "page/0":
            doc.pop("tips")
        path.write_text(json.dumps(doc), "utf-8")
        assert engine.main(["render", str(path)]) == 0, capsys.readouterr().out
    first = html_path.read_bytes()
    maps = payload(first.decode("utf-8"))
    assert maps["shared_terms"]["queue"] == "Shared queue."
    assert maps["shared_terms"]["worker"] == "Shared worker."
    assert ("legacy" in maps["shared_terms"]) == (kind != "page/1")
    assert maps["page_ids"] == ({"card": "Page card."} if kind == "page/1" else {})
    assert maps["page_terms"] == ({"queue": "Page queue."} if kind == "page/1" else {})
    source = Scripts(first.decode("utf-8")).blocks.get("afkv2-page-tip-source")
    for _ in range(2):
        assert launcher.run(["open", str(html_path), "--reopen"])[0] == 0
        assert html_path.read_bytes() == first
    assert not inject.inject_file(html_path)
    if kind == "arbitrary":
        assert '<button title="Help">Go</button>' in first.decode("utf-8")
    # A changed glossary rebuilds derived data without altering durable data.
    (path.parents[2] / "GLOSSARY.md").write_text("**Queue**: Updated shared queue.\n", "utf-8")
    assert launcher.run(["open", str(html_path), "--reopen"])[0] == 0
    updated = html_path.read_text("utf-8")
    assert payload(updated)["shared_terms"]["queue"] == "Updated shared queue."
    assert Scripts(updated).blocks.get("afkv2-page-tip-source") == source


def test_page_owned_only_tips_and_safe_literal_payload():
    literal = '</ScRiPt><img src=x onerror=alert(1)><!-- afkv2-page-tips:start -->\ud800'
    source = json.dumps({"ids": [{"id": "lower", "title": literal}],
                         "terms": [{"term": "queue", "definition": literal}]}).replace("<", "\\u003c")
    html = '<body><script id="afkv2-page-tip-source" type="application/json">' + source + '</script></body>'
    result = inject.inject(html, {})
    assert payload(result) == {"page_ids": {"lower": literal}, "page_terms": {"queue": literal}, "shared_terms": {}}
    assert Scripts(result).blocks["afkv2-page-tip-source"] == source
    assert '<img' not in result
    assert result == inject.inject(result, {})
    result.encode("utf-8")


@pytest.mark.parametrize("broken", ['{', 'null', '{"terms": 1}', '{"ids": [{"id": 1, "title": "x"}]}'])
def test_bad_source_keeps_shared_layer(case, broken):
    path, _ = case
    html = '<body><p>Queue</p><script id="afkv2-page-tip-source" type="application/json">' + broken + '</script></body>'
    html_path = path.with_suffix(".html")
    html_path.write_text(html, "utf-8")
    assert launcher.run(["open", str(html_path), "--reopen"])[0] == 0
    maps = payload(html_path.read_text("utf-8"))
    assert maps == {"page_ids": {}, "page_terms": {}, "shared_terms": {"queue": "Shared queue.", "worker": "Shared worker."}}


def test_empty_page_one_ignores_sidecar(case, capsys):
    path, doc = case
    doc.pop("tips")
    path.write_text(json.dumps(doc), "utf-8")
    assert engine.main(["render", str(path)]) == 0, capsys.readouterr().out
    assert "legacy" not in payload(path.with_suffix(".html").read_text("utf-8"))["shared_terms"]
