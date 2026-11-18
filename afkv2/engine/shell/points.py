"""Points of a page: a point is a lineage of cards linked by `carries` (SDD §4 rounds stay immutable).

A card that asks a returning point again carries the older card ids. The newest card of a lineage is the
point's head; the older cards are its history, newest first. A card is in one history only: when 2 newer
cards carry it, the newest one keeps it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from registry import walk

KIND_ORDER = ("debate", "confirm", "decided", "signoff", "info")
ASKING = {"decided", "confirm", "debate", "signoff"}
SETTLED = ("settled_by_mark", "settled_by_note")
LEGACY_CARRIES = "{}-carries"
WORD = re.compile(r"[\w-]+")
# The label of the text part that says why a point returns: the visualize guide, card.md. It is not content, so
# a returning card that adds only this part has not changed.
RETURN_LABEL = "Why it returns"


@dataclass
class Point:
    head: dict
    round: dict
    history: list = field(default_factory=list)


def carried(item: dict, earlier: set) -> list[str]:
    """The earlier cards that a card carries: its `carries` field, else the card ids that the text component
    `<id>-carries` names. A grill build wrote that text before the field existed."""
    if item.get("carries"):
        return [old for old in item["carries"] if old in earlier]
    for _, component in walk(item["body"]):
        if component.get("id") == LEGACY_CARRIES.format(item["id"]):
            words = WORD.findall((component.get("props") or {}).get("text") or "")
            return [word for word in words if word in earlier]
    return []


def _content(item: dict) -> str:
    """The kind, the title and the body of a card, without the parts that say why it returns and with its own id
    read as `@`: the content that a carried card compares."""
    def keep(component: dict) -> dict:
        if "children" not in component:
            return component
        return {**component, "children": [keep(child) for child in component["children"]
                                          if (child.get("props") or {}).get("label") != RETURN_LABEL]}
    found = {"kind": item["kind"], "title": item.get("title"), "body": keep(item["body"])}
    return json.dumps(found, sort_keys=True, ensure_ascii=False).replace(item["id"], "@")


def fresh_cards(doc: dict, n: int) -> set[str]:
    """The cards of round `n` whose content is new in it: a card that carries no earlier card, or whose kind,
    title or body (`_content`) differs from the newest card it carries."""
    earlier = {item["id"]: (round_["n"], item) for round_ in doc["rounds"] if round_["n"] < n
               for item in round_["items"]}
    found = set()
    for round_ in doc["rounds"]:
        if round_["n"] != n:
            continue
        for item in round_["items"]:
            older = carried(item, set(earlier))
            if not older:
                found.add(item["id"])
                continue
            newest = max(older, key=lambda card_id: earlier[card_id][0])
            if _content(item) != _content(earlier[newest][1]):
                found.add(item["id"])
    return found


def lineages(doc: dict) -> list[Point]:
    """Every point, its head in document order."""
    cards = [(round_, item) for round_ in doc["rounds"] for item in round_["items"]]
    place = {item["id"]: index for index, (_, item) in enumerate(cards)}
    round_of = {item["id"]: round_["n"] for round_, item in cards}
    owner: dict[str, str] = {}
    for round_, item in sorted(cards, key=lambda card: (-card[0]["n"], place[card[1]["id"]])):
        earlier = {other for other, n in round_of.items() if n < round_["n"]}
        for old in carried(item, earlier):
            owner.setdefault(old, item["id"])
    held: dict[str, list[str]] = {}
    for old, newer in owner.items():
        held.setdefault(newer, []).append(old)
    found = []
    for round_, item in cards:
        if item["id"] in owner:
            continue
        older, stack = [], list(held.get(item["id"], []))
        while stack:
            card_id = stack.pop()
            older.append(card_id)
            stack.extend(held.get(card_id, []))
        older.sort(key=lambda card_id: (-round_of[card_id], place[card_id]))
        found.append(Point(item, round_, [cards[place[card_id]][::-1] for card_id in older]))
    return found


def is_live(point: Point, current_n: int) -> bool:
    """A point of the current round, or an asking point that an earlier round left unsettled."""
    head = point.head
    return point.round["n"] == current_n or (head["kind"] in ASKING and head.get("state", "open") not in SETTLED)


def grouped(doc: dict) -> tuple[list[Point], list[Point]]:
    """(the live points by kind, debate first; the settled points, newest round first)."""
    current_n = next(r["n"] for r in doc["rounds"] if r["state"] == "current")
    points = lineages(doc)
    order = {id(point): index for index, point in enumerate(points)}
    live = [p for p in points if is_live(p, current_n)]
    live.sort(key=lambda p: (KIND_ORDER.index(p.head["kind"]), -p.round["n"], order[id(p)]))
    settled = [p for p in points if not is_live(p, current_n)]
    settled.sort(key=lambda p: (-p.round["n"], order[id(p)]))
    return live, settled
