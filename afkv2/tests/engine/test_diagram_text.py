"""Diagram text (ADR-0006 design, PRD AC-031 to AC-033, SDD §9b row "Diagram renderer"): each diagram text renders
once per text and theme through the renderer into the data folder's cache, each picture with its own SVG id, and
falls back to the text with 1 line of why. Every test uses a stub renderer: no test runs mermaid-cli."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
for folder in (PLUGIN / "scripts", ENGINE_DIR, PLUGIN / "skills" / "setup" / "scripts"):
    sys.path.insert(0, str(folder))

import diagrams  # noqa: E402
import engine  # noqa: E402
import registry  # noqa: E402
import tools  # noqa: E402
from shell import page  # noqa: E402

FLOW = "flowchart LR\n  a[Start] -->|go| b{Choice}\n  b --> c[End]"
STATES = "stateDiagram-v2\n  [*] --> open\n  open --> settled"
CAPTION = "An order moves from open to settled"
SVG_ROOT = re.compile(r'<svg id="([^"]+)"')
ID_ATTR = re.compile(r'\sid="([^"]+)"')


class StubRenderer:
    """mermaid-cli as an in-process stub: it writes a small SVG with the id, the theme and the text it was given,
    a marker and a gradient that the drawing names, ids that nothing names, and an id twice, as a mind map has."""

    def __init__(self, code=0, stderr="", timeout=False):
        self.calls, self.code, self.stderr, self.timeout = [], code, stderr, timeout

    def __call__(self, argv, timeout):
        self.calls.append({"argv": list(argv), "timeout": timeout})
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, timeout)
        value = dict(zip(argv[1::2], argv[2::2]))
        if self.code == 0:
            svg_id, theme, text = value["-I"], value["-t"], Path(value["-i"]).read_text("utf-8")
            Path(value["-o"]).write_text(
                f'<svg id="{svg_id}" xmlns="http://www.w3.org/2000/svg"><style>#{svg_id} .node{{fill:red}}</style>'
                f'<defs><marker id="{svg_id}_arrow"></marker><linearGradient id="shade"></linearGradient></defs>'
                f'<g id="flowchart-a-0" class="node"><rect fill="url(#shade)"></rect></g>'
                f'<g id="{svg_id}-node_1"></g><g id="{svg_id}-node_1"><use href="#{svg_id}-node_1"></use></g>'
                f'<g id="{svg_id}-lone"></g>'
                f'<path marker-end="url(#{svg_id}_arrow)"></path><text>{theme}: {len(text)}</text></svg>', "utf-8")
        return self.code, self.stderr


@pytest.fixture
def renderer(monkeypatch):
    """A renderer on the path and its browser config, as setup leaves them."""
    stub = StubRenderer()
    config = engine.data_folder() / diagrams.CONFIG_FILE
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("{}", "utf-8")
    monkeypatch.setattr(diagrams, "find_renderer", lambda: "mmdc")
    monkeypatch.setattr(diagrams, "call_renderer", stub)
    return stub


def diagram(text=FLOW, **extra):
    return {"type": "diagram", "props": {"caption": CAPTION, "text": text}, **extra}


def page_of(*bodies):
    items = [{"id": f"i-{k}", "kind": "info", "body": body} for k, body in enumerate(bodies)]
    return {"schema": "afkv2.page/1",
            "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                        "started": "2026-01-05T09:00:00Z", "step": "Requirements grill"},
            "maps": [], "notes": [],
            "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                        "items": items}]}


def built(doc):
    with diagrams.page_run() as counts:
        html = page.build(doc)
    return html, dict(counts)


# --- the picture (AC-031)

def test_a_diagram_shows_as_a_picture_in_each_theme_with_its_caption(renderer):
    component = diagram(id="d-flow")
    assert registry.validate(component) == []
    html = registry.render_component(component)
    assert SVG_ROOT.findall(html) == ["d-flow--dark", "d-flow--light"]
    assert 'class="afkv2-diagram-theme afkv2-diagram-theme--dark"' in html
    assert 'class="afkv2-diagram-theme afkv2-diagram-theme--light"' in html
    assert f"<figcaption" in html and CAPTION in html
    assert [call["argv"][call["argv"].index("-t") + 1] for call in renderer.calls] == ["dark", "default"]


def test_each_render_has_the_browser_config_a_transparent_background_and_60_s(renderer):
    registry.render_component(diagram())
    config = str(engine.data_folder() / diagrams.CONFIG_FILE)
    for call in renderer.calls:
        argv = call["argv"]
        assert argv[0] == "mmdc" and argv[argv.index("-p") + 1] == config
        assert argv[argv.index("-b") + 1] == "transparent" and call["timeout"] == 60


def test_the_page_css_shows_the_picture_of_the_theme_it_uses():
    css = (ENGINE_DIR / "shell" / "diagram.css").read_text("utf-8")
    assert re.search(r"\.afkv2-diagram-theme--light\s*\{\s*display:\s*none", css)
    assert re.search(r':root\[data-theme="light"\] \.afkv2-diagram-theme--light\s*\{\s*display:\s*block', css)
    assert re.search(r':root\[data-theme="light"\] \.afkv2-diagram-theme--dark\s*\{\s*display:\s*none', css)


@pytest.mark.parametrize("bad", [{"text": ""}, {"caption": ""}, {"caption": "c" * 161}, {"text": "x" * 20001},
                                 {"kind": "flowchart"}])
def test_a_diagram_refuses_props_outside_its_rules(bad):
    props = {"caption": CAPTION, "text": FLOW, **bad}
    assert registry.validate({"type": "diagram", "props": props}) != []


def test_a_diagram_without_a_caption_is_refused():
    assert registry.validate({"type": "diagram", "props": {"text": FLOW}}) != []


# --- distinct SVG ids (SDD §9b row "Diagram renderer")

def test_a_page_with_2_diagrams_holds_distinct_svg_ids_one_per_diagram_and_theme(renderer):
    html, _ = built(page_of(diagram(FLOW), diagram(STATES)))
    roots = SVG_ROOT.findall(html)
    assert len(roots) == 4 and len(set(roots)) == 4


def test_the_same_text_twice_on_a_page_still_holds_distinct_ids(renderer):
    html, _ = built(page_of(diagram(FLOW, id="d-one"), diagram(FLOW)))
    roots = SVG_ROOT.findall(html)
    assert len(roots) == 4 and len(set(roots)) == 4
    every = ID_ATTR.findall(html)
    assert len(every) == len(set(every)), [i for i in every if every.count(i) > 1]


def test_each_id_inside_a_picture_starts_with_its_svg_id_and_each_reference_follows(renderer):
    html = registry.render_component(diagram(id="d-flow"))
    dark = html[html.index('<svg id="d-flow--dark"'):html.index("</svg>")]
    assert all(found.startswith("d-flow--dark") for found in ID_ATTR.findall(dark))
    assert "url(#d-flow--dark_arrow)" in dark and "#d-flow--dark .node" in dark
    shade = re.search(r'<linearGradient id="([^"]+)"', dark).group(1)
    assert f"url(#{shade})" in dark
    assert "flowchart-a-0" not in dark and "lone" not in dark, "an id nothing names is dropped: a note lands on the diagram"
    assert dark.count('id="d-flow--dark-node_1"') == 1, "an id the renderer wrote twice is kept once"


def test_a_note_on_a_picture_lands_on_the_diagram():
    kind = registry.lookup("diagram")
    assert kind.targets({"id": "d-flow", **diagram()["props"]}) == {"d-flow--dark": "d-flow", "d-flow--light": "d-flow"}


def test_the_same_document_builds_the_same_bytes(renderer):
    doc = page_of(diagram(FLOW), diagram(FLOW))
    assert built(doc)[0] == built(doc)[0]


# --- the cache (AC-032, SDD §10 row "Diagram render")

def test_a_second_render_of_the_same_page_makes_0_renderer_calls(renderer):
    doc = page_of(diagram(FLOW), diagram(STATES))
    first, counts = built(doc)
    assert len(renderer.calls) == 4 and counts == {"rendered": 2, "cached": 0, "as_text": 0}
    second, counts = built(doc)
    assert len(renderer.calls) == 4 and counts == {"rendered": 0, "cached": 2, "as_text": 0}
    assert first == second


def test_a_picture_is_named_by_a_hash_of_the_text_the_theme_and_the_renderer_version(renderer):
    registry.render_component(diagram(FLOW))
    cache = engine.data_folder() / diagrams.CACHE_FOLDER
    names = sorted(path.name for path in cache.iterdir())
    wanted = sorted(hashlib.sha256("\0".join([diagrams.RENDERER_VERSION, theme, FLOW]).encode("utf-8")).hexdigest()
                    + ".svg" for theme in ("dark", "default"))
    assert names == wanted


def test_a_changed_text_renders_again(renderer):
    built(page_of(diagram(FLOW)))
    built(page_of(diagram(FLOW + "\n  c --> a")))
    assert len(renderer.calls) == 4


def test_the_renderer_version_is_the_setup_pin():
    assert diagrams.RENDERER_VERSION == tools.MERMAID_VERSION


# --- the text fallback (AC-033)

def _fallback(html):
    found = re.search(r'<pre class="afkv2-diagram-text"><code>(.*?)</code></pre><p class="afkv2-diagram-why">([^<]*)</p>',
                      html, re.S)
    assert found, html
    assert "<svg" not in html
    return found.group(1), found.group(2)


def test_no_renderer_on_the_path_shows_the_text_with_why(monkeypatch):
    monkeypatch.setattr(diagrams, "find_renderer", lambda: None)
    monkeypatch.setattr(diagrams, "call_renderer", lambda *a: pytest.fail("no renderer must be called"))
    html, counts = built(page_of(diagram("flowchart LR\n  a --> b & c")))
    text, why = _fallback(html)
    assert text == "flowchart LR\n  a --&gt; b &amp; c"
    assert "not on the path" in why and "/afkv2:setup" in why and "\n" not in why
    assert counts == {"rendered": 0, "cached": 0, "as_text": 1}


def test_no_browser_config_shows_the_text_with_why(monkeypatch):
    monkeypatch.setattr(diagrams, "find_renderer", lambda: "mmdc")
    monkeypatch.setattr(diagrams, "call_renderer", lambda *a: pytest.fail("no renderer must be called"))
    _, why = _fallback(registry.render_component(diagram()))
    assert diagrams.CONFIG_FILE in why and "/afkv2:setup" in why


def test_a_renderer_failure_shows_the_text_with_its_last_error_line(renderer):
    renderer.code, renderer.stderr = 1, "Error: Parse error on line 2:\n  a -->\nExpecting 'NODE', got 'EOF'\n"
    html, counts = built(page_of(diagram()))
    _, why = _fallback(html)
    assert "exit 1" in why and "Expecting &#x27;NODE&#x27;, got &#x27;EOF&#x27;" in why
    assert counts == {"rendered": 0, "cached": 0, "as_text": 1}
    assert not list((engine.data_folder() / diagrams.CACHE_FOLDER).glob("*.svg")), "a failure is not cached"


def test_a_renderer_timeout_shows_the_text_with_why(renderer):
    renderer.timeout = True
    _, why = _fallback(registry.render_component(diagram()))
    assert "60 s" in why


def test_a_failure_is_tried_again_at_the_next_render(renderer):
    renderer.code = 1
    built(page_of(diagram()))
    renderer.code = 0
    _, counts = built(page_of(diagram()))
    assert counts == {"rendered": 1, "cached": 0, "as_text": 0}


# --- the counts in the render answer (SDD §3 row "present")

def test_render_answers_the_diagram_counts(renderer, capsys, tmp_path):
    repo = tmp_path / "repo"
    (repo / ".afkv2").mkdir(parents=True)
    (repo / ".git").mkdir()
    (repo / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "specs"}), "utf-8")
    pages = repo / "specs" / "PROJ-1" / "pages"
    pages.mkdir(parents=True)
    path = pages / "grill-s1.json"
    path.write_text(json.dumps(page_of(diagram(FLOW), diagram(STATES))), "utf-8")
    assert engine.main(["render", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["diagrams"] == {"rendered": 2, "cached": 0, "as_text": 0}
    assert engine.main(["render", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["diagrams"] == {"rendered": 0, "cached": 2, "as_text": 0}
