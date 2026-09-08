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
    """A key stable across partitions — an ordinal collides when fragments merge."""
    return prefix + "-" + hashlib.sha1(text.encode("utf-8", "surrogateescape")).hexdigest()[:8]


def worst(*statuses: str) -> str:
    """The status a row may claim when several apply to it at once."""
    known = [status for status in statuses if status in STATUS_ORDER]
    if not known:
        return statuses[0] if statuses else "unverified"
    return min(known, key=STATUS_ORDER.index)
