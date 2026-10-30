"""Boxes and arrows for the map and the graph, in a computed layout with no browser script.

Boxes stand in ranks along the arrows. Each group is one band across the ranks, so a group frame
never holds a box of another group. An arrow that would run against the rank order is a back arrow.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import ceil
from typing import Callable, Iterable

from shell.diagram_parts import LABEL, TEXT, TITLE, held_in, label_html, repeated_ids, unknown_ends

NODE_WIDTH, HELD_WIDTH, HELD_HEIGHT = 176, 264, 136
LINE, BOX_PADDING, CHARS_PER_LINE = 20, 16, 21
GROUP_LINE, GROUP_CHARS_PER_LINE = 18, 24
EDGE_LINE, EDGE_CHAR, EDGE_CHARS_PER_LINE = 16, 7, 24
RANK_GAP, CROSS_GAP, BAND_GAP, FRAME, START = 64, 20, 28, 12, 24
BACK_ARC, BACK_OFFSET, HEAD, HEAD_WIDTH = 56, 12, 8, 4


def boxes_schema(node_fields: dict, node_required: list[str]) -> dict:
    return {
        "type": "object", "additionalProperties": False, "required": ["nodes"],
        "properties": {
            "title": TITLE,
            "direction": {"enum": ["right", "down"]},
            "nodes": {"type": "array", "minItems": 1, "items": {
                "type": "object", "additionalProperties": False, "required": ["id", "label", *node_required],
                "properties": {"id": TEXT, "label": LABEL, "group": TEXT, **node_fields}}},
            "edges": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["from", "to"],
                "properties": {"from": TEXT, "to": TEXT, "label": {"type": "string"}}}},
            "groups": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["id", "label"],
                "properties": {"id": TEXT, "label": TEXT}}},
        },
    }


def nested_labels(props: dict) -> list[tuple]:
    return held_in(props["nodes"], "nodes")


def check_boxes(props: dict) -> Iterable[tuple]:
    nodes, groups = props["nodes"], props.get("groups") or []
    yield from repeated_ids(nodes, "nodes")
    yield from repeated_ids(groups, "groups")
    known_groups = {group["id"] for group in groups}
    for i, node in enumerate(nodes):
        if "group" in node and node["group"] not in known_groups:
            yield ("nodes", i, "group"), f"{node['group']!r} names no group of this diagram"
    yield from unknown_ends(props.get("edges") or [], "edges", {node["id"] for node in nodes}, "node")


def _ranks(ids: list[str], edges: list[dict]) -> tuple[dict[str, int], set[int]]:
    """The rank of each node, and the index of each back arrow. Iterative: a chain may be long."""
    after: dict[str, list[tuple[int, str]]] = {identifier: [] for identifier in ids}
    for index, edge in enumerate(edges):
        after[edge["from"]].append((index, edge["to"]))
    open_nodes, done, back, finished = set(), set(), set(), []
    for root in ids:
        if root in done:
            continue
        open_nodes.add(root)
        stack = [(root, iter(after[root]))]
        while stack:
            node, rest = stack[-1]
            for index, target in rest:
                if target in open_nodes:
                    back.add(index)
                elif target not in done:
                    open_nodes.add(target)
                    stack.append((target, iter(after[target])))
                    break
            else:
                stack.pop()
                open_nodes.discard(node)
                done.add(node)
                finished.append(node)
    ranks = dict.fromkeys(ids, 0)
    for node in reversed(finished):
        for index, target in after[node]:
            if index not in back:
                ranks[target] = max(ranks[target], ranks[node] + 1)
    return ranks, back


def _size(node: dict, head: int) -> tuple[int, int]:
    label = node["label"]
    if not isinstance(label, str):
        return HELD_WIDTH, HELD_HEIGHT + head
    return NODE_WIDTH, BOX_PADDING + head + LINE * ceil(len(label) / CHARS_PER_LINE)


def _gap(edges: list[dict], right: bool) -> int:
    longest = max((len(edge.get("label") or "") for edge in edges), default=0)
    if right:
        return min(max(RANK_GAP, longest * EDGE_CHAR + 3 * HEAD), NODE_WIDTH)
    return max(RANK_GAP, 3 * HEAD + EDGE_LINE * ceil(longest / EDGE_CHARS_PER_LINE))


@dataclass(frozen=True)
class _Place:
    """A box by its start and length along the ranks (main) and across them (cross)."""
    main: int
    cross: int
    main_size: int
    cross_size: int


@dataclass(frozen=True)
class _Layout:
    right: bool
    gap: int
    places: dict[str, _Place]
    frames: list[tuple[str, tuple[int, int, int, int]]]
    back: set[int]
    width: int
    height: int

    def rect(self, place: _Place) -> tuple[int, int, int, int]:
        if self.right:
            return place.main, place.cross, place.main_size, place.cross_size
        return place.cross, place.main, place.cross_size, place.main_size

    def point(self, main: int, cross: int) -> str:
        return f"{main} {cross}" if self.right else f"{cross} {main}"

    def label_left_top(self, main: int, cross: int) -> tuple[int, int]:
        return (main, cross) if self.right else (cross, main)

    @property
    def label_width(self) -> int:
        return self.gap - HEAD if self.right else NODE_WIDTH


def _layout(props: dict, head: int) -> _Layout:
    nodes, edges = props["nodes"], props.get("edges") or []
    right = props.get("direction", "right") == "right"
    ranks, back = _ranks([node["id"] for node in nodes], edges)
    sizes = {node["id"]: _size(node, head) for node in nodes}
    titles = {group["id"]: group["label"] for group in props.get("groups") or []}
    heads = {group: GROUP_LINE * ceil(len(titles[group]) / GROUP_CHARS_PER_LINE) + FRAME
             for group in {node.get("group") for node in nodes} - {None}}
    head_room = 0 if right else max(heads.values(), default=0)
    gap = _gap(edges, right)

    extent: dict[int, int] = {}
    for identifier, rank in ranks.items():
        extent[rank] = max(extent.get(rank, 0), sizes[identifier][0 if right else 1])
    starts, cursor = {}, START + head_room
    for rank in sorted(extent):
        starts[rank] = cursor
        cursor += extent[rank] + gap + head_room
    main_end = cursor - gap - head_room + START

    bands: dict[str | None, list[dict]] = {}
    for node in nodes:
        bands.setdefault(node.get("group"), []).append(node)
    groups_of = {node["id"]: node.get("group") for node in nodes}
    arc_bands = {groups_of[edges[index][end]] for index in back for end in ("from", "to")}
    places, frames, cross = {}, [], START
    for group, members in bands.items():
        first = cross if group is None else cross + (heads[group] if right else FRAME)
        stacks: dict[int, int] = {}
        for node in members:
            width, height = sizes[node["id"]]
            main_size, cross_size = (width, height) if right else (height, width)
            rank = ranks[node["id"]]
            at = stacks.get(rank, first)
            places[node["id"]] = _Place(starts[rank], at, main_size, cross_size)
            stacks[rank] = at + cross_size + CROSS_GAP
        last = max(stacks.values()) - CROSS_GAP
        if group is not None:
            last += FRAME
            held = [places[node["id"]] for node in members]
            low = min(place.main for place in held)
            high = max(place.main + place.main_size for place in held)
            length = high - low + 2 * FRAME
            rect = ((low - FRAME, cross, length, last - cross) if right
                    else (cross, low - FRAME - heads[group], last - cross, length + heads[group]))
            frames.append((titles[group], rect))
        cross = last + BAND_GAP + (BACK_ARC if group in arc_bands else 0)
    cross_end = cross - BAND_GAP + START
    width, height = (main_end, cross_end) if right else (cross_end, main_end)
    return _Layout(right, gap, places, frames, back, width, height)


def _forward(layout: _Layout, start: _Place, target: _Place) -> tuple[str, str, tuple[int, int]]:
    from_main, from_cross = start.main + start.main_size, start.cross + start.cross_size // 2
    tip_main, tip_cross = target.main, target.cross + target.cross_size // 2
    end, middle = tip_main - HEAD, (from_main + tip_main - HEAD) // 2
    at = layout.point
    curve = (f"M{at(from_main, from_cross)} C{at(middle, from_cross)} {at(middle, tip_cross)} {at(end, tip_cross)}")
    tip = (f"M{at(tip_main, tip_cross)} L{at(end, tip_cross - HEAD_WIDTH)} L{at(end, tip_cross + HEAD_WIDTH)} Z")
    run = tip_main - from_main
    label_main = from_main + min(layout.gap, run) // 2
    label_cross = from_cross + (tip_cross - from_cross) * (label_main - from_main) // run
    return curve, tip, layout.label_left_top(label_main, label_cross)


def _backward(layout: _Layout, start: _Place, target: _Place) -> tuple[str, str, tuple[int, int]]:
    from_main, from_cross = start.main + start.main_size // 2 + BACK_OFFSET, start.cross + start.cross_size
    tip_main, tip_cross = target.main + target.main_size // 2 - BACK_OFFSET, target.cross + target.cross_size
    end, far = tip_cross + HEAD, max(from_cross, tip_cross) + BACK_ARC
    at = layout.point
    curve = f"M{at(from_main, from_cross)} C{at(from_main, far)} {at(tip_main, far)} {at(tip_main, end)}"
    tip = f"M{at(tip_main, tip_cross)} L{at(tip_main - HEAD_WIDTH, end)} L{at(tip_main + HEAD_WIDTH, end)} Z"
    label = layout.label_left_top((from_main + tip_main) // 2, far - BACK_ARC // 4)
    return curve, tip, label


def _rect_style(rect: tuple[int, int, int, int]) -> str:
    return f"left:{rect[0]}px;top:{rect[1]}px;width:{rect[2]}px;height:{rect[3]}px"


def _arrows(layout: _Layout, edges: list[dict]) -> tuple[str, str]:
    paths, labels = [], []
    for index, edge in enumerate(edges):
        is_back = index in layout.back
        draw = _backward if is_back else _forward
        curve, tip, (left, top) = draw(layout, layout.places[edge["from"]], layout.places[edge["to"]])
        css = "afkv2-edge afkv2-edge--back" if is_back else "afkv2-edge"
        paths.append(f'<path class="{css}" data-afkv2-edge="{escape(edge["from"])} {escape(edge["to"])}" d="{curve}"/>'
                     f'<path class="afkv2-arrowhead" d="{tip}"/>')
        if edge.get("label"):
            labels.append(f'<span class="afkv2-edge-label" style="left:{left}px;top:{top}px;'
                          f'max-width:{layout.label_width}px">{escape(edge["label"])}</span>')
    svg = (f'<svg class="afkv2-edges" width="{layout.width}" height="{layout.height}" aria-hidden="true">'
           f'{"".join(paths)}</svg>')
    return svg, "".join(labels)


def _frame(title: str, rect: tuple[int, int, int, int]) -> str:
    return (f'<div class="afkv2-group" style="{_rect_style(rect)}">'
            f'<span class="afkv2-group-label">{escape(title)}</span></div>')


def _plain(node: dict) -> tuple[str, str, str]:
    return "", "", ""


def draw_boxes(props: dict, head: int = 0, parts: Callable[[dict], tuple[str, str, str]] = _plain) -> str:
    """`parts(node)` gives a box's extra class, its extra attributes and the HTML above its label."""
    layout = _layout(props, head)
    frames = "".join(_frame(title, rect) for title, rect in layout.frames)
    svg, labels = _arrows(layout, props.get("edges") or [])
    drawn = []
    for node in props["nodes"]:
        extra_class, attrs, above = parts(node)
        css = f"afkv2-box {extra_class}" if extra_class else "afkv2-box"
        drawn.append(f'<div class="{css}"{attrs} style="{_rect_style(layout.rect(layout.places[node["id"]]))}">'
                     f'{above}{label_html(node["label"], "afkv2-box-label")}</div>')
    return (f'<div class="afkv2-diagram-scroll"><div class="afkv2-boxes" style="width:{layout.width}px;'
            f'height:{layout.height}px">{frames}{svg}{"".join(drawn)}{labels}</div></div>')
