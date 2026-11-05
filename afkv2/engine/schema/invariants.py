"""Page document rules a schema cannot state (SDD §4, §6), on the format 1 form that a reader gives.
The document already fits the schema of its format.

A problem is `(path, why)`, with `path` from the document root.
"""

from __future__ import annotations

import hashlib
import json

import registry
from schema import note_rules

STAMP_SALT = "afkv2 ingest stamp v0"
SETTLED_BY = {"settled_by_mark": "mark", "settled_by_note": "note"}
# Every element id is also an HTML id. The page shell and the lavish host name their own elements so.
RESERVED_PREFIXES = ("afkv2-", "lavish-")


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def ingest_stamp(session_id: str, round_n: int, received: str, raw: str, signal: dict) -> str:
    """The stamp only ingest writes on a signal. It marks the writer; it is not a secret."""
    unstamped = {key: value for key, value in signal.items() if key != "stamp"}
    text = canonical([STAMP_SALT, session_id, round_n, received, raw, unstamped])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def settled_rounds(doc: dict) -> dict[int, str]:
    return {r["n"]: canonical(r) for r in doc["rounds"] if r["state"] == "settled"}


def _format_1_round(text: str) -> str:
    """A saved round in the format 1 form: a copy saved from a format 0 round still holds its notes, which the
    format 0 reader moves into the session list."""
    round_ = json.loads(text)
    if "notes" not in round_ and not any("notes" in item for item in round_.get("items") or []):
        return text
    round_.pop("notes", None)
    for item in round_.get("items") or []:
        item.pop("notes", None)
    return canonical(round_)


def check_rewrite(doc: dict, saved: dict[int, str]) -> list[tuple]:
    """A settled round in the last saved copy must come back the same, byte for byte, in the format 1 form."""
    now = settled_rounds(doc)
    index = {r["n"]: i for i, r in enumerate(doc["rounds"])}
    found = []
    for n, text in saved.items():
        if n not in index:
            found.append((("rounds",), f"settled round {n} was removed; a settled round is never rewritten"))
        elif now.get(n) != text and now.get(n) != _format_1_round(text):
            found.append((("rounds", index[n]), "a settled round is never rewritten; it differs from the last saved copy"))
    return found


def check_invariants(doc: dict, ids: dict[str, tuple], nodes: dict[str, tuple]) -> list[tuple]:
    """`ids` holds every item, component and map node id with its path; `nodes` only the map nodes."""
    rounds = doc["rounds"]
    last = len(rounds)
    found = _round_order(rounds)
    found += [((*path, "id"), f"id {identifier!r} starts with a prefix the page and its host keep: "
                              f"{', '.join(RESERVED_PREFIXES)}")
              for identifier, path in ids.items() if identifier.startswith(RESERVED_PREFIXES)]
    note_ids: dict[str, tuple] = {}
    card_round = {item["id"]: round_["n"] for round_ in rounds for item in round_["items"]}
    notes = doc.get("notes") or []
    for k, note in enumerate(notes):
        found += _note(("notes", k), note, ids, nodes, card_round, last, note_ids)
    for r, round_ in enumerate(rounds):
        where = ("rounds", r)
        found += _responses(doc["session"]["id"], round_, where)
        for i, item in enumerate(round_["items"]):
            found += _item((*where, "items", i), item, notes, nodes, last)
            found += [((*where, "items", i, "carries", c), f"{old!r} is no card of an earlier round")
                      for c, old in enumerate(item.get("carries") or [])
                      if card_round.get(old, round_["n"]) >= round_["n"]]
    found += _value_chips(doc)
    answer_ids: dict[str, tuple] = {}
    for r, round_ in enumerate(rounds):
        for p, answer in enumerate(round_.get("replies") or []):
            where = ("rounds", r, "replies", p, "id")
            if answer.get("id") in answer_ids:
                found.append((where, f"answer id {answer['id']!r} is not unique"))
            elif answer.get("id"):
                answer_ids[answer["id"]] = where
    return found


def check_links(doc: dict, ids: dict[str, tuple]) -> list[tuple]:
    """The links of the answers and the rounds (SDD §6), refused as `bad-link`: an answer's note ids, changed
    ids and, on format 0 pages, `about` ids, and a round's changed ids must name a real note or element."""
    note_ids = {note["id"] for note in doc.get("notes") or []}
    found = []

    def names_nothing(where: tuple, values, known, what: str) -> None:
        found.extend(((*where, k), f"{value!r} names no {what}") for k, value in enumerate(values or [])
                     if value not in known)

    for r, round_ in enumerate(doc["rounds"]):
        names_nothing(("rounds", r, "changed"), round_.get("changed"), ids, "element")
        for p, answer in enumerate(round_.get("replies") or []):
            where = ("rounds", r, "replies", p)
            names_nothing((*where, "notes"), answer.get("notes"), note_ids, "note")
            names_nothing((*where, "changed"), answer.get("changed"), ids, "element")
            for a, target in enumerate(answer.get("about") or []):
                if target not in ids and target not in note_ids:
                    found.append(((*where, "about", a), f"{target!r} resolves to no element and no note"))
    return found


def _value_chips(doc: dict) -> list[tuple]:
    """A chip's `set` names a value set of the document, and its text is a value of that set (SDD §4: chip ->
    value set, many to 1)."""
    sets = doc.get("value_sets") or {}
    trees = [(("maps", m), tree) for m, tree in enumerate(doc.get("maps") or [])]
    trees += [(("rounds", r, "items", i, "body"), item["body"])
              for r, round_ in enumerate(doc["rounds"]) for i, item in enumerate(round_["items"])]
    found = []
    for root, tree in trees:
        for path, part in registry.walk(tree):
            props = part.get("props") or {}
            if part["type"] != "chip" or "set" not in props:
                continue
            named = sets.get(props["set"])
            if named is None:
                found.append(((*root, *path, "props", "set"), f"{props['set']!r} names no value set of the document"))
            elif props["text"] not in named["values"]:
                found.append(((*root, *path, "props", "text"),
                              f"{props['text']!r} is no value of the set {props['set']!r}"))
    return found


def _round_order(rounds: list[dict]) -> list[tuple]:
    found = []
    numbers = [r["n"] for r in rounds]
    if numbers != list(range(1, len(rounds) + 1)):
        found.append((("rounds",), f"n must count 1, 2, 3 in order, found {numbers}"))
    current = sum(r["state"] == "current" for r in rounds)
    if current != 1:
        found.append((("rounds",), f"exactly one round is current, found {current}"))
    return found


def _responses(session_id: str, round_: dict, where: tuple) -> list[tuple]:
    found = []
    for a, response in enumerate(round_.get("responses") or []):
        for s, signal in enumerate(response["signals"]):
            stamp = ingest_stamp(session_id, round_["n"], response["received"], response["raw"], signal)
            if signal["stamp"] != stamp:
                found.append(((*where, "responses", a, "signals", s, "stamp"),
                              "only ingest writes responses and signals; this stamp is not ingest's"))
    return found


def _item(where: tuple, item: dict, notes: list[dict], nodes: dict, last: int) -> list[tuple]:
    found = []
    node = item.get("node")
    if node is not None and node not in nodes:
        found.append(((*where, "node"), f"{node!r} resolves to no map node"))
    return found + _settled(where, item, [note for note in notes if note.get("item") == item["id"]], nodes, last)


def _note_id(where: tuple, note_id: str, n: int, owner: str, note_ids: dict) -> list[tuple]:
    """The id is `N-<n>-<owner>-<k>`, k = 1, 2, 3, or the older `N-<n>-<owner>`; and it is unique."""
    found = []
    old = note_rules.old_note_id(n, owner)
    if note_id != old and not note_rules.is_new_id(note_id, n, owner):
        found.append(((*where, "id"), f"must be {old}-<k>, k = 1, 2, 3, found {note_id!r}"))
    if note_id in note_ids:
        found.append(((*where, "id"), f"note id {note_id!r} is not unique"))
    note_ids[note_id] = where
    return found


def _note(where: tuple, note: dict, ids: dict, nodes: dict, card_round: dict, last: int, note_ids: dict) -> list[tuple]:
    """A note of the session list. A card note names its card in `item`: its id is `N-<round>-<card>-<k>`.
    A steer names no card, and sits on a map node, a round banner, or another element that no card holds:
    its id is `N-<round>-<target>-<k>`."""
    target, item = note["target"], note.get("item")
    found = _note_id(where, note["id"], note["round"], item or target, note_ids)
    if note["round"] > last:
        found.append(((*where, "round"), f"round {note['round']} does not exist"))
    if target not in ids:
        found.append(((*where, "target"), f"{target!r} resolves to no element"))
    elif item is None and target not in nodes and ids[target][2:3] == ("items",):
        found.append(((*where, "item"), f"{target!r} is part of a card; a note on it names that card"))
    if item is not None and item not in card_round:
        found.append(((*where, "item"), f"{item!r} is no card"))
    return found


def _settled(where: tuple, item: dict, notes: list[dict], nodes: dict, last: int) -> list[tuple]:
    state = item.get("state", "open")
    settled = item.get("settled")
    by = SETTLED_BY.get(state)
    if by is None:
        return [((*where, "settled"), f"only a settled point has this field; the state is {state}")] if settled else []
    if not settled:
        return [((*where, "settled"), f"is required when the state is {state}")]
    found = []
    if settled["by"] != by:
        found.append(((*where, "settled", "by"), f"must be {by} when the state is {state}"))
    if settled["round"] > last:
        found.append(((*where, "settled", "round"), f"round {settled['round']} does not exist"))
    if by == "note":
        if not settled.get("reading"):
            found.append(((*where, "settled", "reading"), "is required when by = note"))
        live = {n["id"] for n in notes if not n["deleted"] and n["target"] not in nodes}
        if settled["signal"] not in live:
            found.append(((*where, "settled", "signal"),
                          f"{settled['signal']!r} must be the id of a live note on this item"))
    return found
