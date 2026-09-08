#!/usr/bin/env python3
"""The parts of the ledger contract the emitter and the validator must share.

`LEDGER-FORMAT.md` beside this file is the grammar; this module is the half a
program has to agree on literally — the node cap, the class list, and the way a
stable key is computed. Two copies of a constant drift; one does not.

Imported by `seed_map.py` (emitter) and `validate_coverage.py` (checker). Both
put this directory on `sys.path` before importing, because both run as scripts.
"""

from __future__ import annotations

import hashlib

# How many node ids a boundary row carries. The count above it stays exact, and
# a row that reached the cap says `truncated: true`.
HIT_CAP = 200

ALL_CLASSES = tuple(f"B{n}" for n in range(1, 15))

# Worst status wins wherever two answers meet — a merge, or one row carrying a
# gap from two directions. Left is worse than right.
STATUS_ORDER = ("unverified", "judgment-only", "partial", "frontier", "n/a", "closed")


def stable_id(prefix: str, text: str) -> str:
    """A key stable across partitions — an ordinal collides when fragments merge.

    What goes in `text` per table is `LEDGER-FORMAT.md` § "Stable keys".
    """
    return prefix + "-" + hashlib.sha1(text.encode("utf-8", "surrogateescape")).hexdigest()[:8]


# The shape of a `line_hash`: what the emitter writes and the validator pins.
LINE_HASH_CHARS = 12


def line_hash(text: str) -> str:
    """The identity of a matched line, so a node survives an edit above it.

    A node id carries a line number, which every insertion shifts. Comparing
    two runs on ids alone reports drift the code never had; comparing on this
    reports the drift it did.
    """
    digest = hashlib.sha1(text.strip().encode("utf-8", "surrogateescape")).hexdigest()
    return digest[:LINE_HASH_CHARS]


def worst(*statuses: str) -> str:
    """The status a row may claim when several apply to it at once."""
    known = [status for status in statuses if status in STATUS_ORDER]
    if not known:
        return statuses[0] if statuses else "unverified"
    return min(known, key=STATUS_ORDER.index)
