"""The note rules that the invariants, ingest and the page share: note ids and the round target.

One lavish annotation is one note. A note on a card has the id `N-<round>-<item>-<k>`, a steer
`N-<round>-<target>-<k>`, with k = 1, 2, 3 in annotation order. An older document keeps the old form
`N-<round>-<item>` or `N-<round>-<target>`: one note that merged every annotation of its card or target.
"""

from __future__ import annotations

import re

COUNT = re.compile(r"[1-9][0-9]*")


def round_target(n: int) -> str:
    """The element id of the banner of round n. A note on it is a steer on the round."""
    return f"R-{n}"


def old_note_id(n: int, owner: str) -> str:
    return f"N-{n}-{owner}"


def is_new_id(note_id: str, n: int, owner: str) -> bool:
    prefix = old_note_id(n, owner) + "-"
    return note_id.startswith(prefix) and COUNT.fullmatch(note_id[len(prefix):]) is not None


def next_note_id(notes: list[dict], n: int, owner: str) -> str:
    """The id of the next annotation on `owner` in round n, after the new-form ids in `notes`."""
    prefix = old_note_id(n, owner) + "-"
    taken = [int(note["id"][len(prefix):]) for note in notes if is_new_id(note["id"], n, owner)]
    return f"{prefix}{max(taken, default=0) + 1}"
