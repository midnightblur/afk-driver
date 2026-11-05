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
TIP_NAME = "data-afkv2-tip"
TONE_CLASS = "afkv2-tone--{}"
TONE_SELECTOR = r"\.afkv2-tone--"
CHIP_MARK = re.compile(r'<span class="afkv2-chip-mark" aria-hidden="true">([^<]+)</span>')
STRENGTH = re.compile(r"var\(--afkv2-scale\) (\d+)%")
VALUE_VAR = "--afkv2-value"
SET_TOKEN = "--afkv2-set-{}:"
THEME_TOKENS = ["--afkv2-you:", "--afkv2-scale:", *map(SET_TOKEN.format, range(1, 9))]
SEQ_TONE = '<span class="afkv2-seq-tone">{}</span>'
SEQ_MSG = r'<div class="afkv2-seq-msg [^"]*afkv2-tone--'

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
    assert TONE_CLASS.format(tone) in drawn and f">{tone}<" in drawn
    mark = CHIP_MARK.search(drawn)
    assert mark, f"a {tone} chip has no symbol beside its colour"


def test_each_state_and_certainty_tone_has_its_own_mark():
    marks = [CHIP_MARK.search(registry.render_component(chip(tone))).group(1)
             for tone in STATE_TONES]
    assert len(set(marks)) == len(STATE_TONES)


@pytest.mark.parametrize("tone", STATE_TONES)
def test_each_tone_has_its_own_look_from_theme_tokens(tone):
    body = rule(f".afkv2-chip.afkv2-tone--{tone}")
    assert "var(--" in body and "#" not in body, f"the {tone} chip has no look from the theme tokens"


def test_the_you_colour_and_the_set_colours_exist_in_both_themes():
    for start in THEMES:
        block = theme_block(start)
        assert all(token in block for token in THEME_TOKENS)


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
    message = re.search(SEQ_MSG + tone + r'[^"]*"[^>]*>(.*?)</div></div>', drawn)
    assert message and SEQ_TONE.format(tone) in message.group(1)


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
    assert TIP_NAME not in registry.render_component(PARTS[name]())


@pytest.mark.parametrize("name", PARTS)
def test_a_part_refuses_a_tip_over_300_characters_and_a_you_that_is_no_flag(name):
    assert registry.validate(PARTS[name](tip="t" * 301)) != []
    assert registry.validate(PARTS[name](you="yes")) != []


def test_an_authored_tip_shows_on_a_page_with_no_dictionary():
    """The hover handler and the harvest of authored tips run when the dictionary is empty."""
    assert "if (!Object.keys(dict).length) return;" not in TIPS_JS
    assert "if (!re) return;" in TIPS_JS  # re is null when no catalog holds a key


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
    strengths = [int(STRENGTH.search(value_colour(values, value, True)).group(1))
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
    assert TIP_NAME not in registry.render_component(bare)


def test_a_component_refuses_a_tip_over_300_characters():
    assert registry.validate({"type": "chip", "tip": "t" * 301, "props": {"text": "x", "tone": "new"}}) != []


def test_a_component_refuses_an_empty_tip():
    """Ruling D-47: a component tip holds 1 to 300 characters, as a diagram part's tip does."""
    assert registry.validate({"type": "chip", "tip": "", "props": {"text": "x", "tone": "new"}}) != []
    assert registry.validate({"type": "chip", "tip": "t", "props": {"text": "x", "tone": "new"}}) == []


# --- a value chip: its word and its colour from the document's named set (AC-028, PR-07) ---

RISK = {"values": ["high", "medium", "low"], "ordered": True}
OWNER = {"values": ["agent", "reviewer", "YOU"], "ordered": False}
VALUE_SETS = {"risk": RISK, "owner": OWNER}
VALUE_STYLE = re.compile(r'<span class="afkv2-chip afkv2-value" style="--afkv2-value: ([^"]+)">([^<]+)</span>')


def value_chip(value, set_name):
    return {"type": "chip", "props": {"text": value, "set": set_name}}


def test_a_chip_takes_a_tone_or_a_set_and_never_both_or_neither():
    assert registry.validate(value_chip("high", "risk")) == []
    assert registry.validate({"type": "chip", "props": {"text": "high"}}) != []
    assert registry.validate({"type": "chip", "props": {"text": "high", "set": "risk", "tone": "new"}}) != []


@pytest.mark.parametrize("value, set_name", [("high", "risk"), ("low", "risk"), ("reviewer", "owner"), ("YOU", "owner")])
def test_a_value_chip_shows_its_word_and_the_colour_of_its_value(value, set_name):
    value_colour = _base_chip().value_colour
    with registry.page_context(VALUE_SETS):
        drawn = registry.render_component(value_chip(value, set_name))
    found = VALUE_STYLE.search(drawn)
    assert found, drawn
    expected = value_colour(VALUE_SETS[set_name]["values"], value, VALUE_SETS[set_name]["ordered"])
    assert found.groups() == (expected, value)


def test_the_page_context_ends_with_its_page():
    with registry.page_context(VALUE_SETS):
        pass
    assert VALUE_VAR not in registry.render_component(value_chip("high", "risk"))


def test_the_value_colour_rule_reads_the_value_colour():
    body = rule(".afkv2-chip.afkv2-value")
    assert f"var({VALUE_VAR}" in body and "#" not in body


def test_the_same_value_has_the_same_colour_on_the_whole_page():
    sys.path.insert(0, str(ENGINE_DIR.parent / "scripts"))
    import engine  # noqa: E402
    from shell import page  # noqa: E402

    def table(table_id, values):
        return {"type": "table", "id": table_id, "props": {"columns": ["Risk"],
                                                           "rows": [[value_chip(v, "risk")] for v in values]}}

    doc = {"schema": "afkv2.page/1",
           "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                       "started": "2026-01-05T09:00:00Z", "step": "Requirements grill"},
           "maps": [], "notes": [], "value_sets": {"risk": RISK},
           "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                       "items": [{"id": "i-a", "kind": "info", "body": table("t-a", ["high", "low"])},
                                 {"id": "i-b", "kind": "info", "body": table("t-b", ["low", "medium", "high"])}]}]}
    html = page.build(engine.READERS[doc["schema"]](doc))
    colours = {}
    for colour, value in VALUE_STYLE.findall(html):
        colours.setdefault(value, set()).add(colour)
    assert set(colours) == {"high", "medium", "low"}
    assert all(len(found) == 1 for found in colours.values()), colours


# --- check refuses a value chip that resolves to no set or no value of its set (ruling D-44) ---

def _checked(capsys, tmp_path, cell, value_sets):
    sys.path.insert(0, str(ENGINE_DIR.parent / "scripts"))
    import json
    import engine  # noqa: E402

    body = {"type": "text", "props": {"text": "Risks"},
            "children": [{"type": "table", "props": {"columns": ["Risk"], "rows": [[cell]]}}]}
    doc = {"schema": "afkv2.page/1",
           "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                       "started": "2026-01-05T09:00:00Z", "step": "Requirements grill"},
           "maps": [], "notes": [], "value_sets": value_sets,
           "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                       "items": [{"id": "i-a", "kind": "info", "body": body}]}]}
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(doc), "utf-8")
    code = engine.main(["check", str(path)])
    return code, json.loads(capsys.readouterr().out)


def test_check_accepts_a_value_chip_of_its_set(capsys, tmp_path):
    assert _checked(capsys, tmp_path, value_chip("low", "risk"), {"risk": RISK})[0] == 0


@pytest.mark.parametrize("cell, value_sets, why", [
    (value_chip("low", "size"), {"risk": RISK}, "'size' names no value set of the document"),
    (value_chip("low", "risk"), None, "'risk' names no value set of the document"),
    (value_chip("severe", "risk"), {"risk": RISK}, "'severe' is no value of the set 'risk'"),
], ids=["unknown set", "no sets", "value outside its set"])
def test_check_refuses_a_value_chip_that_does_not_resolve(capsys, tmp_path, cell, value_sets, why):
    code, answer = _checked(capsys, tmp_path, cell, value_sets)
    assert code == 1
    reason = answer["error"]["reason"]
    assert why in reason and "body.children[0].props.rows[0][0].props" in reason, reason


# --- every chip tone has a cue beside its colour (PR-07) ---

SHAPE_CUES = {"removed": ("text-decoration", "line-through"), "proposed": ("border-style", "dashed")}


@pytest.mark.parametrize("tone", ["removed", "kept", "new", "proposed", *STATE_TONES])
def test_every_chip_tone_has_a_cue_beside_its_colour(tone):
    drawn = registry.render_component(chip(tone, "export"))
    mark = re.search(CHIP_MARK.pattern + 'export', drawn)
    if tone in SHAPE_CUES:
        prop, value = SHAPE_CUES[tone]
        body = " ".join(re.findall(TONE_SELECTOR + tone + r"(?![\w-])[^{]*\{([^}]*)\}", KIT))
        assert re.search(re.escape(prop) + r"\s*:[^;]*" + value, body) or mark, tone
    else:
        assert mark, f"a {tone} chip shows its meaning by colour alone"


def test_the_you_badge_of_a_map_box_leaves_room_for_its_round_label():
    """Review f2/f10 of 0008: the badge sits at the top right of the box, where the head line ends with R-n."""
    room = rule(".afkv2-box.afkv2-you .afkv2-node-head")
    assert re.search(r"padding-right:\s*2\.\d+rem", room), room


def test_a_sequence_message_marked_you_draws_its_line_and_arrowhead_in_the_you_colour():
    """Review f3/f11 of 0008: sequence.md says the message's line is in the YOU colour."""
    colour = "var(--afkv2-you)"
    line, new_line = ".afkv2-seq-msg.afkv2-you .afkv2-seq-line", ".afkv2-seq-msg.afkv2-tone--new .afkv2-seq-line"
    right_head = ".afkv2-seq-msg--right.afkv2-you .afkv2-seq-line::after"
    left_head = ".afkv2-seq-msg--left.afkv2-you .afkv2-seq-line::after"
    self_line = ".afkv2-seq-msg--self.afkv2-you .afkv2-seq-line"
    assert f"border-top-color: {colour}" in rule(line)
    assert f"border-left-color: {colour}" in rule(right_head)
    assert f"border-right-color: {colour}" in rule(left_head)
    assert f"border-color: {colour}" in rule(self_line)
    assert KIT.index(line) > KIT.index(new_line), "the YOU colour wins over a tone colour"
