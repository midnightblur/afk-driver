"""Format 1 marks on the existing components: chip tones for state and certainty, the tone of a sequence
message, the YOU mark and the tip of a diagram part, and the colour of a value in its named set."""

import copy
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[2] / "engine"
sys.path.insert(0, str(ENGINE_DIR))

import registry  # noqa: E402

KIT = (ENGINE_DIR / "shell" / "kit.css").read_text(encoding="utf-8")
TIPS_JS = (ENGINE_DIR / "shell" / "tips.js").read_text(encoding="utf-8")
THEMES = (":root {", ':root[data-theme="light"] {')

STATE_TONES = ["open", "blocked", "settled", "measured", "inferred", "estimated", "unverified", "you"]
YOU = "afkv2-you"
TIP = "Who pushes the export button"
TIP_ATTR = 'data-afkv2-tip="{}"'

GRAPH = {"nodes": [{"id": "g-a", "label": "export endpoint"}, {"id": "g-b", "label": "store"}],
         "edges": [{"from": "g-a", "to": "g-b"}]}
MAP = {"nodes": [{"id": "n-a", "label": "Export", "state": "open", "round": 1},
                 {"id": "n-b", "label": "Format", "state": "settled", "round": 1}]}
RUN = {"current": [{"label": "read orders"}, {"label": "press export"}]}
SEQUENCE = {"actors": [{"id": "user", "label": "User"}, {"id": "api", "label": "Export endpoint"}],
            "messages": [{"from": "user", "to": "api", "text": "start export"},
                         {"from": "api", "to": "user", "text": "file link"}]}


def _base_chip():
    spec = importlib.util.spec_from_file_location("marks_base_chip", ENGINE_DIR / "components" / "base_chip.py")
    module = importlib.util.module_from_spec(spec)
    registry.load_components()
    original = registry.register_component
    registry.register_component = lambda *args, **kwargs: None
    try:
        spec.loader.exec_module(module)
    finally:
        registry.register_component = original
    return module


def chip(tone, text=None):
    return {"type": "chip", "props": {"text": text or tone, "tone": tone}}


def rule(selector):
    """The body of the first kit.css rule whose selector list holds `selector`."""
    found = re.search(r"(?:^|[},])\s*([^{}]*" + re.escape(selector) + r"(?![\w-])[^{}]*)\{([^}]*)\}", KIT, re.M)
    return found.group(2) if found else ""


def theme_block(start):
    block = KIT[KIT.index(start):]
    return block[:block.index("}")]


# --- chip tones for state and certainty (AC-022, PR-07) ---

@pytest.mark.parametrize("tone", STATE_TONES)
def test_a_chip_of_a_state_or_certainty_tone_is_valid_and_shows_its_word_and_mark(tone):
    assert registry.validate(chip(tone)) == []
    drawn = registry.render_component(chip(tone))
    assert f"afkv2-tone--{tone}" in drawn and f">{tone}<" in drawn
    mark = re.search(r'<span class="afkv2-chip-mark" aria-hidden="true">([^<]+)</span>', drawn)
    assert mark, f"a {tone} chip has no symbol beside its colour"


def test_each_state_and_certainty_tone_has_its_own_mark():
    marks = [re.search(r'afkv2-chip-mark" aria-hidden="true">([^<]+)<', registry.render_component(chip(tone))).group(1)
             for tone in STATE_TONES]
    assert len(set(marks)) == len(STATE_TONES)


@pytest.mark.parametrize("tone", STATE_TONES)
def test_each_tone_has_its_own_look_from_theme_tokens(tone):
    body = rule(f".afkv2-chip.afkv2-tone--{tone}")
    assert "var(--" in body and "#" not in body, f"the {tone} chip has no look from the theme tokens"


def test_the_you_colour_and_the_set_colours_exist_in_both_themes():
    for start in THEMES:
        block = theme_block(start)
        assert "--afkv2-you:" in block and "--afkv2-scale:" in block
        assert all(f"--afkv2-set-{n}:" in block for n in range(1, 9))


def test_a_text_keeps_its_4_tones():
    assert registry.validate({"type": "text", "props": {"text": "x", "tone": "open"}}) != []


# --- the tone of a sequence message (AC-023) ---

@pytest.mark.parametrize("tone", ["removed", "kept", "new"])
def test_a_sequence_message_shows_its_tone_and_its_word(tone):
    props = copy.deepcopy(SEQUENCE)
    props["messages"][0]["tone"] = tone
    component = {"type": "sequence", "props": props}
    assert registry.validate(component) == []
    drawn = registry.render_component(component)
    message = re.search(r'<div class="afkv2-seq-msg [^"]*afkv2-tone--' + tone + r'[^"]*"[^>]*>(.*?)</div></div>', drawn)
    assert message and f'<span class="afkv2-seq-tone">{tone}</span>' in message.group(1)


def test_a_sequence_message_refuses_another_tone():
    props = copy.deepcopy(SEQUENCE)
    props["messages"][0]["tone"] = "proposed"
    assert registry.validate({"type": "sequence", "props": props}) != []


# --- the YOU mark and the tip of a diagram part (AC-024, AC-025) ---

def _graph(**marks):
    props = copy.deepcopy(GRAPH)
    props["nodes"][0].update(marks)
    return {"type": "graph", "props": props}


def _map(**marks):
    props = copy.deepcopy(MAP)
    props["nodes"][0].update(marks)
    return {"type": "map", "props": props}


def _run(**marks):
    props = copy.deepcopy(RUN)
    props["current"][1].update(marks)
    return {"type": "run-strip", "props": props}


def _sequence(**marks):
    props = copy.deepcopy(SEQUENCE)
    props["messages"][0].update(marks)
    return {"type": "sequence", "props": props}


PARTS = {"graph node": _graph, "map node": _map, "run-strip step": _run, "sequence message": _sequence}
MARKED = {
    "graph node": r'<div class="afkv2-box(?: [^"]*)?"[^>]*>(?:(?!</div>).)*export endpoint',
    "map node": r'<div class="afkv2-box(?: [^"]*)?"[^>]*data-afkv2-element="n-a"[^>]*>',
    "run-strip step": r'<li class="afkv2-run-step[^"]*"[^>]*>(?:(?!</li>).)*press export',
    "sequence message": r'<div class="afkv2-seq-msg[^"]*"[^>]*>(?:(?!afkv2-seq-line).)*start export',
}


def _part(name, html):
    found = re.search(MARKED[name], html, re.S)
    assert found, f"no {name} drawn"
    return found.group(0)


@pytest.mark.parametrize("name", PARTS)
def test_a_part_marked_you_shows_the_you_mark(name):
    component = PARTS[name](you=True)
    assert registry.validate(component) == []
    head = _part(name, registry.render_component(component))
    assert YOU in head.split(">", 1)[0]
    other = registry.render_component(PARTS[name]())
    assert YOU not in other and YOU not in registry.render_component(PARTS[name](you=False))


def test_the_you_mark_reads_you_in_the_kit():
    assert 'content: "YOU"' in rule(f".{YOU}::before")


@pytest.mark.parametrize("name", PARTS)
def test_a_part_with_a_tip_carries_its_text_for_the_hover(name):
    component = PARTS[name](tip=TIP + ' & "more"')
    assert registry.validate(component) == []
    head = _part(name, registry.render_component(component))
    assert TIP_ATTR.format(TIP + " &amp; &quot;more&quot;") in head.split(">", 1)[0]
    assert "data-afkv2-tip" not in registry.render_component(PARTS[name]())


@pytest.mark.parametrize("name", PARTS)
def test_a_part_refuses_a_tip_over_300_characters_and_a_you_that_is_no_flag(name):
    assert registry.validate(PARTS[name](tip="t" * 301)) != []
    assert registry.validate(PARTS[name](you="yes")) != []


def test_an_authored_tip_shows_on_a_page_with_no_dictionary():
    """The hover handler and the harvest of authored tips run when the dictionary is empty."""
    assert "if (!Object.keys(dict).length) return;" not in TIPS_JS
    assert "if (!keys.length) return;" in TIPS_JS


# --- the colour of a value in its named set (AC-028, SDD §9 row "Value colours") ---

def test_a_value_takes_its_colour_by_its_position_in_its_set():
    value_colour = _base_chip().value_colour
    values = ["web", "core", "store"]
    colours = [value_colour(values, value, False) for value in values]
    assert colours == ["var(--afkv2-set-1)", "var(--afkv2-set-2)", "var(--afkv2-set-3)"]
    assert value_colour(values, "core", False) == value_colour(list(values), "core", False)


def test_an_unordered_set_longer_than_the_palette_starts_the_palette_again():
    value_colour = _base_chip().value_colour
    values = [f"v{n}" for n in range(10)]
    assert value_colour(values, "v8", False) == "var(--afkv2-set-1)"


def test_an_ordered_set_runs_strong_to_faint():
    value_colour = _base_chip().value_colour
    values = ["high", "medium", "low"]
    strengths = [int(re.search(r"var\(--afkv2-scale\) (\d+)%", value_colour(values, value, True)).group(1))
                 for value in values]
    assert strengths[0] == 100 and strengths == sorted(strengths, reverse=True) and len(set(strengths)) == 3


def test_you_has_one_fixed_strong_colour_in_every_set():
    value_colour = _base_chip().value_colour
    assert value_colour(["YOU", "agent"], "YOU", False) == "var(--afkv2-you)"
    assert value_colour(["agent", "reviewer", "you"], "you", True) == "var(--afkv2-you)"


def test_a_value_outside_its_set_has_no_colour():
    assert _base_chip().value_colour(["low", "high"], "medium", True) is None


# --- the tip of any component (AC-025) ---

@pytest.mark.parametrize("component", [
    {"type": "chip", "props": {"text": "SLA", "tone": "new"}},
    {"type": "text", "props": {"text": "The export runs nightly."}},
    {"type": "chip", "id": "c-sla", "style": "margin: 0", "props": {"text": "SLA", "tone": "new"}},
], ids=["chip", "text", "chip with id and style"])
def test_a_component_with_a_tip_carries_its_text_on_its_wrapper(component):
    component = {**component, "tip": TIP + ' & "more"'}
    assert registry.validate(component) == []
    drawn = registry.render_component(component)
    head = drawn.split(">", 1)[0]
    assert TIP_ATTR.format(TIP + " &amp; &quot;more&quot;") in head
    assert head.startswith("<span" if component["type"] == "chip" else "<div")
    bare = {k: v for k, v in component.items() if k != "tip"}
    assert "data-afkv2-tip" not in registry.render_component(bare)


def test_a_component_refuses_a_tip_over_300_characters():
    assert registry.validate({"type": "chip", "tip": "t" * 301, "props": {"text": "x", "tone": "new"}}) != []
