"""Diagram components: map, graph, sequence diagram and simulated-run strip.

The example props are the shapes session S2 documents for page authors in its visualize skill.
"""

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[2] / "engine"
sys.path.insert(0, str(ENGINE_DIR))

import engine  # noqa: E402
import registry  # noqa: E402
from shell import page  # noqa: E402

STYLES = (ENGINE_DIR / "shell" / "diagram.css").read_text(encoding="utf-8")
KIT = (ENGINE_DIR / "shell" / "kit.css").read_text(encoding="utf-8")
MODULES = {"map": "diagram_map.py", "graph": "diagram_graph.py", "sequence": "diagram_sequence.py",
           "run-strip": "diagram_run_strip.py"}

MAP = {"title": "Scope", "nodes": [
    {"id": "n-export", "label": "Export", "state": "settled", "round": 1},
    {"id": "n-format", "label": "File format", "state": "focus", "round": 1},
    {"id": "n-access", "label": "Who may export", "state": "open", "round": 1},
], "edges": [{"from": "n-export", "to": "n-format"}, {"from": "n-export", "to": "n-access"}]}
GRAPH = {"direction": "right", "groups": [{"id": "web", "label": "web module"}, {"id": "core", "label": "core module"}],
         "nodes": [{"id": "g-controller", "label": "export endpoint", "group": "web"},
                   {"id": "g-service", "label": "export service", "group": "core"},
                   {"id": "g-store", "label": "order store", "group": "core"}],
         "edges": [{"from": "g-controller", "to": "g-service", "label": "start export"},
                   {"from": "g-service", "to": "g-store", "label": "read orders"}]}
SEQUENCE = {"actors": [{"id": "user", "label": "User"}, {"id": "api", "label": "Export endpoint"},
                       {"id": "store", "label": "Order store"}],
            "messages": [{"from": "user", "to": "api", "text": "start export"},
                         {"from": "api", "to": "store", "text": "read orders"},
                         {"from": "store", "to": "api", "text": "orders"},
                         {"from": "api", "to": "user", "text": "file link"}]}
RUN = {"current": [{"label": "read orders"}, {"label": "write file"}, {"label": "email file", "tone": "removed"}],
       "proposed": [{"label": "read orders", "tone": "kept"}, {"label": "write file", "tone": "kept"},
                    {"label": "store file", "detail": "link valid 7 days", "tone": "new"}]}
EXAMPLES = {"map": MAP, "graph": GRAPH, "sequence": SEQUENCE, "run-strip": RUN}
NAMES = sorted(EXAMPLES)
CHIP = {"type": "chip", "id": "held-chip", "props": {"text": "inner", "tone": "new"}}

ELEMENT_ATTR = "data-afkv2-element"
ELEMENT = ELEMENT_ATTR + '="{}"'
ITEM_A = 'data-afkv2-item="i-a"'
DIAGRAM = "afkv2-diagram"
BOX = "afkv2-box"
TONE_CLASS = "afkv2-tone--"
ARROWHEAD = 'class="afkv2-arrowhead"'
BACK_EDGE = "afkv2-edge--back"
SEQ_LIFE = 'class="afkv2-seq-life"'
SEQ_SELF = "afkv2-seq-msg--self"
BOX_RECT = re.compile(r'class="afkv2-box[^"]*"[^>]*style="left:(\d+)px;top:(\d+)px;width:(\d+)px;height:(\d+)px"')
CANVAS = re.compile(r'class="afkv2-boxes" style="width:(\d+)px;height:(\d+)px"')
NODE_BOX = r'<div class="afkv2-box afkv2-node--{}"[^>]*data-afkv2-element="{}"[^>]*>(.*?)</div>'
STATE_RULE = r"\.afkv2-node--{} \{{[^}}]*border-{}: ([^;]+);"
EDGE_PATH = re.compile(r'<path class="afkv2-edge[^"]*" data-afkv2-edge="([^"]*)"')
GROUP_FRAME = re.compile(r'class="afkv2-group" style="left:(\d+)px;top:(\d+)px;width:(\d+)px;height:(\d+)px"[^>]*>'
                         r'<span class="afkv2-group-label">([^<]*)</span>')
EDGE_LABEL = re.compile(r'afkv2-edge-label" style="left:(\d+)px;top:(\d+)px')
EDGE_LABEL_BOX = re.compile(r'afkv2-edge-label" style="left:(\d+)px;top:(\d+)px;max-width:(\d+)px">([^<]*)</span>')
EDGE_D = re.compile(r'<path class="afkv2-edge[^"]*" data-afkv2-edge="([^"]*)" d="([^"]*)"')
EDGE_LABEL_RULE = re.compile(r"\.afkv2-edge-label \{[^}]*width: max-content;")
LABEL_CHAR, LABEL_LINE, LABEL_PAD = 7, 16, 8
SEQ_TEXT = re.compile(r'<span class="afkv2-seq-n">(\d+)\.</span> ?<span class="afkv2-seq-words">([^<]*)</span>')
SEQ_MSG = re.compile(r'class="afkv2-seq-msg afkv2-seq-msg--(\w+)" style="grid-column:(\d+) / (\d+);grid-row:(\d+)')
RUN_LANE = re.compile(r'<div class="afkv2-run-lane"><h5 class="afkv2-run-head">(\w+)</h5>'
                      r'<ol class="afkv2-run-steps">(.*?)</ol>', re.S)
REMOVED_STEP = re.compile(r'<li class="afkv2-run-step afkv2-tone--removed">.*?email file.*?removed', re.S)
NEW_STEP = re.compile(r'<li class="afkv2-run-step afkv2-tone--new">.*?store file.*?link valid 7 days', re.S)


def holds(text, *parts):
    return all(part in text for part in parts)


def state_rule(state, field):
    return re.search(STATE_RULE.format(state, field), STYLES).group(1)


def component(name, **extra):
    return {"type": name, "props": copy.deepcopy(EXAMPLES[name]), **extra}


def changed(name, change):
    props = copy.deepcopy(EXAMPLES[name])
    change(props)
    return {"type": name, "props": props}


def draw(name, **extra):
    return registry.render_component(component(name, **extra))


def fields(found):
    return [".".join(str(part) for part in path) for path, _ in found]


def document(*maps, body=None):
    return {"schema": "afkv2.page/0",
            "session": {"id": "s1", "skill": "grill", "feature": "f", "ticket": "T-1", "started": "2026-10-30T10:00:00Z"},
            "maps": list(maps),
            "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                        "items": [{"id": "i-a", "kind": "confirm",
                                   "body": body or {"type": "text", "props": {"text": "x"}}}]}]}


def check(tmp_path, capsys, doc):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    code = engine.main(["check", str(path)])
    return code, json.loads(capsys.readouterr().out)


def boxes(html):
    """Left, top, width and height of each drawn box, in page order."""
    return [tuple(map(int, match)) for match in BOX_RECT.findall(html)]


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def canvas(html):
    return tuple(map(int, CANVAS.search(html).groups()))


def kit_colours(block_start):
    block = KIT[KIT.index(block_start):]
    block = block[:block.index("}")]
    return dict(re.findall(r"--(\w+):\s*(#\w+)", block))


# --- every diagram


@pytest.mark.parametrize("name, module", sorted(MODULES.items()))
def test_each_diagram_is_one_registry_entry_in_its_own_module(name, module):
    assert (ENGINE_DIR / "components" / module).is_file()
    kind = registry.lookup(name)
    assert kind.name == name and kind.schema["type"] == "object" and kind.schema["additionalProperties"] is False


@pytest.mark.parametrize("name", NAMES)
def test_the_documented_example_passes_and_renders_the_same_bytes_twice(name):
    assert registry.validate(component(name)) == []
    assert draw(name) == draw(name)


@pytest.mark.parametrize("name", NAMES)
def test_each_diagram_takes_the_open_style_an_id_and_children(name):
    html = draw(name, id="d-1", style='font-family: "Segoe UI"', children=[CHIP])
    assert 'style="font-family: &quot;Segoe UI&quot;"' in html
    assert holds(html, ELEMENT.format("d-1"), "inner")


@pytest.mark.parametrize("name", NAMES)
def test_each_diagram_owns_its_styling(name):
    classes = {word for value in re.findall(r'class="([^"]*)"', draw(name)) for word in value.split()}
    drawn = {word for word in classes if not word.startswith(TONE_CLASS)}
    assert drawn and not [word for word in drawn if f".{word}" not in STYLES]


def test_the_page_inlines_the_diagram_styling():
    assert STYLES in page.build(document(component("map", id="m-1")))


@pytest.mark.parametrize("name", NAMES)
def test_text_is_escaped_in_every_diagram(name):
    props = copy.deepcopy(EXAMPLES[name])
    props["title"] = "<i>raw</i>"
    if name == "run-strip":
        props["current"][0]["label"] = "<b>raw</b>"
        props["current"][0]["detail"] = "<u>raw</u>"
    elif name == "sequence":
        props["actors"][0]["label"] = "<b>raw</b>"
        props["messages"][0]["text"] = "<u>raw</u>"
    else:
        props["nodes"][0]["label"] = "<b>raw</b>"
        props["edges"][0]["label"] = "<u>raw</u>"
    html = registry.render_component({"type": name, "props": props})
    assert not re.search(r"<[biu]>raw", html)
    assert all(f"&lt;{tag}&gt;raw" in html for tag in "biu")


# --- refusals name the item and the field


BAD_PROPS = [
    ("map", lambda p: p.pop("nodes"), "props.nodes", "is required"),
    ("map", lambda p: p.update(nodes=[]), "props.nodes", "at least 1"),
    ("map", lambda p: p.update(extra=1), "props.extra", "not a field"),
    ("map", lambda p: p["nodes"][0].pop("state"), "props.nodes.0.state", "is required"),
    ("map", lambda p: p["nodes"][0].update(state="loud"), "props.nodes.0.state", "loud"),
    ("map", lambda p: p["nodes"][0].pop("round"), "props.nodes.0.round", "is required"),
    ("map", lambda p: p["nodes"][0].update(label=5), "props.nodes.0.label", "allowed shapes"),
    ("map", lambda p: p["nodes"][1].update(id="n-export"), "props.nodes.1.id", "n-export"),
    ("map", lambda p: p["edges"][0].update(to="n-gone"), "props.edges.0.to", "n-gone"),
    ("map", lambda p: p["edges"][0].update(**{"from": "n-gone"}), "props.edges.0.from", "n-gone"),
    ("map", lambda p: p["nodes"][0].update(label={"type": "nope"}), "props.nodes.0.label.type", "nope"),
    ("graph", lambda p: p.pop("nodes"), "props.nodes", "is required"),
    ("graph", lambda p: p.update(direction="up"), "props.direction", "up"),
    ("graph", lambda p: p["nodes"][0].update(group="gone"), "props.nodes.0.group", "gone"),
    ("graph", lambda p: p["groups"][1].update(id="web"), "props.groups.1.id", "web"),
    ("graph", lambda p: p["groups"][0].pop("label"), "props.groups.0.label", "is required"),
    ("graph", lambda p: p["edges"][1].update(to="gone"), "props.edges.1.to", "gone"),
    ("graph", lambda p: p["edges"][1].update(extra=1), "props.edges.1.extra", "not a field"),
    ("graph", lambda p: p["nodes"][0].update(state="open"), "props.nodes.0.state", "not a field"),
    ("sequence", lambda p: p.pop("actors"), "props.actors", "is required"),
    ("sequence", lambda p: p.update(messages=[]), "props.messages", "at least 1"),
    ("sequence", lambda p: p["actors"][1].update(id="user"), "props.actors.1.id", "user"),
    ("sequence", lambda p: p["messages"][2].update(to="gone"), "props.messages.2.to", "gone"),
    ("sequence", lambda p: p["messages"][2].update(**{"from": "gone"}), "props.messages.2.from", "gone"),
    ("sequence", lambda p: p["messages"][0].pop("text"), "props.messages.0.text", "is required"),
    ("sequence", lambda p: p["actors"][0].update(label={"type": "nope"}), "props.actors.0.label.type", "nope"),
    ("run-strip", lambda p: (p.pop("current"), p.pop("proposed")), "props.current", "at least one"),
    ("run-strip", lambda p: p.update(current=[], proposed=[]), "props.current", "at least one"),
    ("run-strip", lambda p: p["current"][0].pop("label"), "props.current.0.label", "is required"),
    ("run-strip", lambda p: p["proposed"][0].update(tone="loud"), "props.proposed.0.tone", "loud"),
    ("run-strip", lambda p: p["proposed"][0].update(label={"type": "nope"}), "props.proposed.0.label.type", "nope"),
]


@pytest.mark.parametrize("name, change, field, why", BAD_PROPS)
def test_bad_props_are_refused_by_field(name, change, field, why):
    found = registry.validate(changed(name, change))
    assert field in fields(found), found
    assert any(why in reason for _, reason in found), found


def test_the_engine_names_the_item_and_the_field_of_a_bad_diagram(tmp_path, capsys):
    body = changed("sequence", lambda p: p["messages"][0].update(to="gone"))
    code, answer = check(tmp_path, capsys, document(body=body))
    assert code == 1
    assert "item i-a, field body.props.messages[0].to" in answer["error"]["reason"]
    assert "gone" in answer["error"]["reason"]


def test_the_engine_names_the_map_and_the_node_of_a_bad_map(tmp_path, capsys):
    doc = document(changed("map", lambda p: p["nodes"][0].update(state="loud")) | {"id": "m-1"})
    code, answer = check(tmp_path, capsys, doc)
    assert code == 1 and "map m-1, field props.nodes[0].state" in answer["error"]["reason"]


# --- map


def test_a_map_shows_each_state_in_its_own_colour_and_word():
    html = draw("map")
    for node_id, state, word in (("n-export", "settled", "settled"), ("n-format", "focus", "current focus"),
                                 ("n-access", "open", "open")):
        match = re.search(NODE_BOX.format(state, node_id), html, re.S)
        assert match and word in match.group(1) and "R-1" in match.group(1)
    rules = {state: state_rule(state, "color") for state in ("settled", "open", "focus")}
    assert rules == {state: f"var(--{state})" for state in rules}
    for theme in (":root {", ':root[data-theme="light"] {'):
        colours = kit_colours(theme)
        assert len({colours[state] for state in rules}) == 3


def test_the_three_node_states_also_differ_in_shape():
    assert len({state_rule(state, "style") for state in ("settled", "open", "focus")}) == 3


def test_a_page_may_hold_any_number_of_maps(tmp_path, capsys):
    maps = []
    for m in range(5):
        chart = component("map", id=f"m-{m}")
        for node in chart["props"]["nodes"]:
            node["id"] += f"-{m}"
        for edge in chart["props"]["edges"]:
            edge["from"] += f"-{m}"
            edge["to"] += f"-{m}"
        maps.append(chart)
    doc = document(*maps)
    assert check(tmp_path, capsys, doc)[0] == 0
    html = page.build(doc)
    assert holds(html, *[ELEMENT.format(f"m-{m}") for m in range(5)])
    assert holds(html, *[ELEMENT.format(f"n-export-{m}") for m in range(5)])


def test_a_card_links_to_a_node_of_a_real_map(tmp_path, capsys):
    doc = document(component("map", id="m-1"))
    doc["rounds"][0]["items"][0]["node"] = "n-format"
    assert check(tmp_path, capsys, doc)[0] == 0
    doc["rounds"][0]["items"][0]["node"] = "n-gone"
    code, answer = check(tmp_path, capsys, doc)
    assert code == 1 and "n-gone" in answer["error"]["reason"]


def test_a_map_node_round_past_the_last_round_is_refused(tmp_path, capsys):
    doc = document(changed("map", lambda p: p["nodes"][0].update(round=9)))
    code, answer = check(tmp_path, capsys, doc)
    assert code == 1 and "props.nodes[0].round" in answer["error"]["reason"]


def test_a_map_needs_no_title_and_no_edges():
    chart = {"type": "map", "props": {"nodes": [{"id": "n", "label": "x", "state": "open", "round": 1}]}}
    assert registry.validate(chart) == []
    assert BOX in registry.render_component(chart)


# --- graph


def arrows(html):
    return EDGE_PATH.findall(html)


def test_a_graph_draws_nodes_and_one_arrow_per_edge():
    html = draw("graph")
    assert all(node["label"] in html for node in GRAPH["nodes"])
    assert arrows(html) == ["g-controller g-service", "g-service g-store"]
    assert html.count(ARROWHEAD) == 2
    assert "start export" in html and "read orders" in html


def test_a_graph_node_is_not_a_note_target_of_its_own():
    assert ELEMENT_ATTR not in draw("graph")


def test_a_group_draws_as_a_labelled_box_around_its_nodes():
    html = draw("graph")
    groups = GROUP_FRAME.findall(html)
    assert [group[4] for group in groups] == ["web module", "core module"]
    frames = [tuple(map(int, group[:4])) for group in groups]
    assert not overlap(*frames)
    nodes = boxes(html)
    inside = lambda n, f: f[0] <= n[0] and n[0] + n[2] <= f[0] + f[2] and f[1] <= n[1] and n[1] + n[3] <= f[1] + f[3]
    assert inside(nodes[0], frames[0]) and inside(nodes[1], frames[1]) and inside(nodes[2], frames[1])
    assert not inside(nodes[0], frames[1])


@pytest.mark.parametrize("direction", ["right", "down"])
def test_boxes_never_overlap_and_fit_the_canvas(direction):
    props = {"direction": direction, "groups": [{"id": "g", "label": "a long group name " * 4}], "nodes": [
        {"id": str(i), "label": "a long node label " * (i % 4 + 1), "group": "g" if i % 3 == 0 else None}
        for i in range(12)]}
    for node in props["nodes"]:
        if node["group"] is None:
            del node["group"]
    props["edges"] = [{"from": str(i), "to": str((i * 2 + 1) % 12), "label": "edge " * 8} for i in range(12)]
    html = registry.render_component({"type": "graph", "props": props})
    drawn = boxes(html)
    width, height = canvas(html)
    assert len(drawn) == 12
    for i, box in enumerate(drawn):
        assert box[0] + box[2] <= width and box[1] + box[3] <= height
        assert not any(overlap(box, other) for other in drawn[i + 1:])


def test_direction_turns_the_layout():
    props = {"nodes": [{"id": "a", "label": "a"}, {"id": "b", "label": "b"}], "edges": [{"from": "a", "to": "b"}]}
    right = boxes(registry.render_component({"type": "graph", "props": {**props, "direction": "right"}}))
    down = boxes(registry.render_component({"type": "graph", "props": {**props, "direction": "down"}}))
    default = boxes(registry.render_component({"type": "graph", "props": props}))
    assert right == default
    assert right[0][0] < right[1][0] and right[0][1] == right[1][1]
    assert down[0][1] < down[1][1] and down[0][0] == down[1][0]


@pytest.mark.parametrize("direction", ["right", "down"])
def test_a_loop_and_a_self_arrow_draw_and_end(direction):
    props = {"direction": direction, "nodes": [{"id": n, "label": n} for n in "abc"], "edges": [
        {"from": "a", "to": "b"}, {"from": "b", "to": "c"}, {"from": "c", "to": "a", "label": "retry"},
        {"from": "b", "to": "b", "label": "again"}]}
    html = registry.render_component({"type": "graph", "props": props})
    assert len(arrows(html)) == 4 and html.count(BACK_EDGE) == 2
    assert "retry" in html and "again" in html
    assert len(set(boxes(html))) == 3


@pytest.mark.parametrize("direction", ["right", "down"])
def test_a_back_arrow_label_stays_clear_of_the_next_band(direction):
    props = {"direction": direction, "groups": [{"id": "g", "label": "group"}], "nodes": [
        {"id": "a", "label": "a", "group": "g"}, {"id": "b", "label": "b"}],
        "edges": [{"from": "a", "to": "a", "label": "again"}]}
    html = registry.render_component({"type": "graph", "props": props})
    left, top = map(int, EDGE_LABEL.search(html).groups())
    assert not any(box[0] <= left <= box[0] + box[2] and box[1] <= top <= box[1] + box[3] for box in boxes(html))
    assert left < canvas(html)[0] and top < canvas(html)[1]


def edge_paths(html):
    return dict(EDGE_D.findall(html))


def turns(curve):
    """The corners of a straight-line path, as (x, y)."""
    numbers = [int(number) for number in re.findall(r"\d+", curve)]
    return list(zip(numbers[::2], numbers[1::2]))


def crosses(start, end, box):
    left, top, width, height = box
    low_x, high_x = sorted((start[0], end[0]))
    low_y, high_y = sorted((start[1], end[1]))
    return low_x < left + width and left < high_x and low_y < top + height and top < high_y


def label_boxes(html):
    """Each arrow label's box as (left, top, width, height), from the size its text needs."""
    found = []
    for left, top, limit, words in EDGE_LABEL_BOX.findall(html):
        length = len(words) * LABEL_CHAR
        width = min(length + LABEL_PAD, int(limit))
        height = LABEL_LINE * -(-length // (int(limit) - LABEL_PAD))
        found.append((int(left) - width // 2, int(top) - height // 2, width, height))
    return found


def skip_graph(direction):
    """Node order a, c, b, with one arrow from a to b that skips c."""
    return {"direction": direction, "nodes": [{"id": n, "label": n} for n in "acb"], "edges": [
        {"from": "a", "to": "c"}, {"from": "c", "to": "b"}, {"from": "a", "to": "b", "label": "skips a step"}]}


@pytest.mark.parametrize("direction", ["right", "down"])
def test_an_arrow_that_skips_a_rank_goes_round_the_box_between(direction):
    html = registry.render_component({"type": "graph", "props": skip_graph(direction)})
    drawn = dict(zip("acb", boxes(html)))
    corners = turns(edge_paths(html)["a b"])
    assert not any(crosses(start, end, drawn["c"]) for start, end in zip(corners, corners[1:]))
    source, target = drawn["a"], drawn["b"]
    if direction == "right":
        assert corners[0] == (source[0] + source[2], source[1] + source[3] // 2)
        assert corners[-1][1] == target[1] + target[3] // 2 and corners[-1][0] < target[0]
    else:
        assert corners[0] == (source[0] + source[2] // 2, source[1] + source[3])
        assert corners[-1][0] == target[0] + target[2] // 2 and corners[-1][1] < target[1]
    width, height = canvas(html)
    assert all(0 <= x <= width and 0 <= y <= height for x, y in corners)


@pytest.mark.parametrize("direction", ["right", "down"])
def test_arrows_that_skip_the_same_box_take_separate_lanes(direction):
    props = skip_graph(direction)
    props["edges"].append({"from": "a", "to": "b"})
    html = registry.render_component({"type": "graph", "props": props})
    between = boxes(html)[1]
    routes = [turns(curve) for name, curve in EDGE_D.findall(html) if name == "a b"]
    assert len(routes) == 2 and routes[0][2] != routes[1][2]
    for corners in routes:
        assert not any(crosses(start, end, between) for start, end in zip(corners, corners[1:]))


def test_an_arrow_that_skips_a_rank_stays_a_curve_when_no_box_is_in_its_way():
    props = {"nodes": [{"id": n, "label": n} for n in ("p", "a", "m", "u", "t")], "edges": [
        {"from": "p", "to": "m"}, {"from": "m", "to": "u"}, {"from": "m", "to": "t"}, {"from": "a", "to": "t"}]}
    html = registry.render_component({"type": "graph", "props": props})
    assert " C" in edge_paths(html)["a t"]


@pytest.mark.parametrize("direction", ["right", "down"])
@pytest.mark.parametrize("edges, count", [
    ([("a", "b", "read"), ("a", "b", "write")], 2),
    ([("a", "b", "reads the order table"), ("a", "c", "writes the audit row")], 2),
    ([("a", "b", "first long label that takes more than one line"),
      ("a", "c", "second long label that takes more than one line"),
      ("a", "d", "third long label that takes more than one line")], 3),
])
def test_arrow_labels_never_land_on_each_other(direction, edges, count):
    props = {"direction": direction, "nodes": [{"id": n, "label": n} for n in "abcd"],
             "edges": [{"from": start, "to": end, "label": words} for start, end, words in edges]}
    html = registry.render_component({"type": "graph", "props": props})
    labels = label_boxes(html)
    assert len(labels) == count
    for i, label in enumerate(labels):
        assert not any(overlap(label, other) for other in labels[i + 1:])
        assert not any(overlap(label, box) for box in boxes(html))


@pytest.mark.parametrize("direction", ["right", "down"])
def test_a_long_arrow_label_stays_on_the_canvas(direction):
    props = {"direction": direction, "nodes": [{"id": "a", "label": "a"}, {"id": "b", "label": "b"}],
             "edges": [{"from": "a", "to": "b", "label": "a long label " * 20}]}
    html = registry.render_component({"type": "graph", "props": props})
    width, height = canvas(html)
    (left, top, label_width, label_height), = label_boxes(html)
    assert left >= 0 and top >= 0
    assert left + label_width <= width and top + label_height <= height


def test_an_arrow_label_takes_its_own_width_at_the_canvas_edge():
    assert EDGE_LABEL_RULE.search(STYLES)


@pytest.mark.parametrize("direction", ["right", "down"])
def test_arrow_labels_stay_clear_of_boxes_and_labels_in_a_crowded_graph(direction):
    props = {"direction": direction, "nodes": [{"id": str(i), "label": "a node label " * (i % 3 + 1)} for i in range(12)],
             "edges": [{"from": str(i), "to": str((i * 2 + 1) % 12), "label": "edge " * 8} for i in range(12)]}
    html = registry.render_component({"type": "graph", "props": props})
    drawn, labels = boxes(html), label_boxes(html)
    width, height = canvas(html)
    assert len(labels) == 12
    for i, label in enumerate(labels):
        assert label[0] >= 0 and label[1] >= 0 and label[0] + label[2] <= width and label[1] + label[3] <= height
        assert not any(overlap(label, other) for other in labels[i + 1:])
        assert not any(overlap(label, box) for box in drawn)


def test_a_long_chain_draws_without_a_recursion_failure():
    count = 3000
    props = {"nodes": [{"id": str(i), "label": "x"} for i in range(count)],
             "edges": [{"from": str(i), "to": str(i + 1)} for i in range(count - 1)]}
    assert len(boxes(registry.render_component({"type": "graph", "props": props}))) == count


# --- sequence diagram


def test_a_sequence_draws_actors_and_numbered_messages_in_order():
    html = draw("sequence")
    assert all(actor["label"] in html for actor in SEQUENCE["actors"])
    texts = [message["text"] for message in SEQUENCE["messages"]]
    found = SEQ_TEXT.findall(html)
    assert found == [(str(n + 1), text) for n, text in enumerate(texts)]
    assert html.count(SEQ_LIFE) == 3


def test_each_message_runs_between_its_actors_in_its_direction():
    html = draw("sequence")
    found = SEQ_MSG.findall(html)
    assert found == [("right", "1", "3", "2"), ("right", "2", "4", "3"), ("left", "2", "4", "4"), ("left", "1", "3", "5")]


def test_an_actor_may_message_itself():
    props = {"actors": [{"id": "a", "label": "A"}], "messages": [{"from": "a", "to": "a", "text": "think"}]}
    assert registry.validate({"type": "sequence", "props": props}) == []
    assert SEQ_SELF in registry.render_component({"type": "sequence", "props": props})


# --- simulated-run strip


def lanes(html):
    return RUN_LANE.findall(html)


def test_a_strip_draws_each_lane_in_time_order():
    drawn = lanes(draw("run-strip"))
    assert [name for name, _ in drawn] == ["Current", "Proposed"]
    current = drawn[0][1]
    positions = [current.index(step["label"]) for step in RUN["current"]]
    assert positions == sorted(positions) and current.count("<li") == 3


def test_a_step_shows_its_tone_and_its_detail():
    html = draw("run-strip")
    assert REMOVED_STEP.search(html) and NEW_STEP.search(html)


@pytest.mark.parametrize("lane, shown", [("current", "Current"), ("proposed", "Proposed")])
def test_a_strip_may_hold_one_lane(lane, shown):
    strip = {"type": "run-strip", "props": {lane: [{"label": "step"}]}}
    assert registry.validate(strip) == []
    assert [name for name, _ in lanes(registry.render_component(strip))] == [shown]


# --- nesting


@pytest.mark.parametrize("name", NAMES)
def test_a_diagram_renders_inside_a_card(tmp_path, capsys, name):
    doc = document(body=component(name, id="d-1"))
    assert check(tmp_path, capsys, doc)[0] == 0
    html = page.build(doc)
    card = html[html.index(ITEM_A):]
    assert holds(card, ELEMENT.format("d-1"), DIAGRAM)


@pytest.mark.parametrize("name", NAMES)
def test_a_diagram_renders_inside_a_table_cell(tmp_path, capsys, name):
    table = {"type": "table", "props": {"columns": ["A"], "rows": [[component(name, id="d-1")]]}}
    assert check(tmp_path, capsys, document(body=table))[0] == 0
    cell = re.search(r"<td>(.*)</td>", registry.render_component(table), re.S).group(1)
    assert holds(cell, ELEMENT.format("d-1"), DIAGRAM)


LABEL_SLOTS = [
    ("map", lambda p, held: p["nodes"][0].update(label=held), ("nodes", 0, "label")),
    ("graph", lambda p, held: p["nodes"][0].update(label=held), ("nodes", 0, "label")),
    ("sequence", lambda p, held: p["actors"][0].update(label=held), ("actors", 0, "label")),
    ("sequence", lambda p, held: p["messages"][0].update(text=held), ("messages", 0, "text")),
    ("run-strip", lambda p, held: p["current"][0].update(label=held), ("current", 0, "label")),
]


@pytest.mark.parametrize("name, put, path", LABEL_SLOTS)
def test_any_component_renders_inside_a_label(name, put, path):
    diagram = changed(name, lambda p: put(p, copy.deepcopy(CHIP)))
    assert registry.validate(diagram) == []
    assert ELEMENT.format("held-chip") in registry.render_component(diagram)
    assert (("props", *path), CHIP) in [(sub, part) for sub, part in registry.walk(diagram)]


@pytest.mark.parametrize("name, put, path", LABEL_SLOTS)
def test_a_diagram_renders_inside_a_diagram_label(name, put, path):
    inner = component("graph", id="d-inner")
    diagram = changed(name, lambda p: put(p, inner))
    assert registry.validate(diagram) == []
    assert ELEMENT.format("d-inner") in registry.render_component(diagram)


def test_a_component_id_in_a_label_counts_for_uniqueness(tmp_path, capsys):
    chart = changed("map", lambda p: p["nodes"][0].update(label=copy.deepcopy(CHIP)))
    body = {"type": "chip", "id": "held-chip", "props": {"text": "again", "tone": "new"}}
    code, answer = check(tmp_path, capsys, document(chart, body=body))
    assert code == 1 and "held-chip" in answer["error"]["reason"]
