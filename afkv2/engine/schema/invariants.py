"""Page document v0 rules a schema cannot state (SDD §4, §6). The document already fits its schema.

A problem is `(path, why)`, with `path` from the document root.
"""

from __future__ import annotations

import hashlib
import json

STAMP_SALT = "afkv2 ingest stamp v0"
SETTLED_BY = {"settled_by_mark": "mark", "settled_by_note": "note"}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def ingest_stamp(session_id: str, round_n: int, received: str, raw: str, signal: dict) -> str:
    """The stamp only ingest writes on a signal. It marks the writer; it is not a secret."""
    unstamped = {key: value for key, value in signal.items() if key != "stamp"}
    text = canonical([STAMP_SALT, session_id, round_n, received, raw, unstamped])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def settled_rounds(doc: dict) -> dict[int, str]:
    return {r["n"]: canonical(r) for r in doc["rounds"] if r["state"] == "settled"}


def check_rewrite(doc: dict, saved: dict[int, str]) -> list[tuple]:
    """A settled round in the last saved copy must come back the same, byte for byte."""
    now = settled_rounds(doc)
    index = {r["n"]: i for i, r in enumerate(doc["rounds"])}
    found = []
    for n, text in saved.items():
        if n not in index:
            found.append((("rounds",), f"settled round {n} was removed; a settled round is never rewritten"))
        elif now.get(n) != text:
            found.append((("rounds", index[n]), "a settled round is never rewritten; it differs from the last saved copy"))
    return found


def check_invariants(doc: dict, ids: dict[str, tuple], nodes: dict[str, tuple]) -> list[tuple]:
    """`ids` holds every item, component and map node id with its path; `nodes` only the map nodes."""
    rounds = doc["rounds"]
    last = len(rounds)
    found = _round_order(rounds)
    note_ids: set[str] = set()
    for r, round_ in enumerate(rounds):
        where = ("rounds", r)
        found += _responses(doc["session"]["id"], round_, where)
        for p, reply in enumerate(round_.get("replies") or []):
            for a, target in enumerate(reply.get("about") or []):
                if target not in ids:
                    found.append(((*where, "replies", p, "about", a), f"{target!r} resolves to no element"))
        for i, item in enumerate(round_["items"]):
            found += _item((*where, "items", i), item, ids, nodes, last, note_ids)
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


def _item(where: tuple, item: dict, ids: dict, nodes: dict, last: int, note_ids: set) -> list[tuple]:
    found = []
    node = item.get("node")
    if node is not None and node not in nodes:
        found.append(((*where, "node"), f"{node!r} resolves to no map node"))
    notes = item.get("notes") or []
    for n, note in enumerate(notes):
        found += _note((*where, "notes", n), item, note, ids, last, note_ids)
    return found + _settled(where, item, notes, nodes, last)


def _note(where: tuple, item: dict, note: dict, ids: dict, last: int, note_ids: set) -> list[tuple]:
    found = []
    expected = f"N-{note['round']}-{item['id']}"
    if note["id"] != expected:
        found.append(((*where, "id"), f"must be {expected}, found {note['id']!r}"))
    if note["id"] in note_ids:
        found.append(((*where, "id"), f"note id {note['id']!r} is not unique"))
    note_ids.add(note["id"])
    if note["round"] > last:
        found.append(((*where, "round"), f"round {note['round']} does not exist"))
    if note["target"] not in ids:
        found.append(((*where, "target"), f"{note['target']!r} resolves to no element"))
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
