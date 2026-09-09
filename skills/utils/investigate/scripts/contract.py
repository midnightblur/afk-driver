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
import shlex

# A boundary row carries every hit it found: the node table is the denominator
# a count is checked against, so a sampled list would hide the rest of a class.
# This is the ceiling on a whole class instead — past it the subject is too
# generic to answer anything, and the run says so rather than publishing noise.
HIT_LIMIT = 20000

ALL_CLASSES = tuple(f"B{n}" for n in range(1, 15))

# Worst status wins wherever two answers meet — a merge, or one row carrying a
# gap from two directions. Left is worse than right.
STATUS_ORDER = ("unverified", "judgment-only", "partial", "frontier", "n/a", "closed")


def stable_id(prefix: str, text: str) -> str:
    """A key stable across partitions — an ordinal collides when fragments merge.

    What goes in `text` per table is `LEDGER-FORMAT.md` § "Stable keys".
    """
    return prefix + "-" + hashlib.sha1(text.encode("utf-8", "surrogateescape")).hexdigest()[:8]


# One option, one spelling. A command is compared by what it runs, so the long
# form of an option is the short one; every option the emitter writes is here,
# with the long forms a hand-written command may reach for.
OPTION_SPELLINGS = {
    "--ignore-case": "-i",
    "--line-number": "-n",
    "--extended-regexp": "-E",
    "--basic-regexp": "-G",
    "--fixed-strings": "-F",
    "--perl-regexp": "-P",
    "--regexp": "-e",
    "--word-regexp": "-w",
    "--invert-match": "-v",
    "--files-with-matches": "-l",
    "--name-only": "-l",
    "--count": "-c",
    "--text": "-a",
    "--recursive": "-r",
}

# The terms of a Boolean search, whose order is the search: `A --and --not B`
# and `B --and --not A` ask two different questions.
BOOLEAN_TOKENS = ("--and", "--or", "--not", "(", ")")


def argv(command: str) -> list[str]:
    """The tokens a shell would hand the tool."""
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def pathspecs(command: str) -> tuple[str, ...]:
    """The paths a command ran over — everything past `--`."""
    parts = argv(command)
    if "--" not in parts:
        return ()
    return tuple(sorted(parts[parts.index("--") + 1:]))


def normalized(command: str) -> str:
    """One search, one spelling.

    Two searches differ by what they run, not by how the string was typed:
    spacing, quoting, the long or short form of an option and the order of the
    fixed flags all say nothing. The Boolean terms keep their order, because
    that order is the question. Paths are left out: the same search over fewer
    files is the same method, narrowed.
    """
    parts = argv(command)
    if "--" in parts:
        parts = parts[:parts.index("--")]
    flags: list[str] = []
    expression: list[str] = []
    index = 0
    while index < len(parts):
        token = parts[index]
        option = OPTION_SPELLINGS.get(token, token)
        if option == "-e" and index + 1 < len(parts):
            expression.append(f"-e {parts[index + 1]}")
            index += 2
        elif option in BOOLEAN_TOKENS:
            expression.append(option)
            index += 1
        elif token.startswith("-") and token != "--":
            flags.append(option)
            index += 1
        else:
            expression.append(token)
            index += 1
    return " ".join(sorted(flags) + expression)


# Who ran a query: the deterministic pre-pass, or a tracer widening past it.
# Only a `seed` query can be run again by a later pre-pass.
QUERY_ORIGINS = ("seed", "tracer")

# The shape of a `line_hash`: what the emitter writes and the validator pins.
LINE_HASH_CHARS = 12


def line_hash(text: str) -> str:
    """The identity of a matched line, so a node survives an edit above it.

    A node id carries a line number, which every insertion shifts. Comparing
    two runs on ids alone reports drift the code never had; comparing on this
    reports the drift it did.

    Over the exact bytes of the line, its own trailing newline aside. Whitespace
    carries meaning in enough languages that folding it hides real edits.
    """
    digest = hashlib.sha1(text.encode("utf-8", "surrogateescape")).hexdigest()
    return digest[:LINE_HASH_CHARS]


def worst(*statuses: str) -> str:
    """The status a row may claim when several apply to it at once."""
    known = [status for status in statuses if status in STATUS_ORDER]
    if not known:
        return statuses[0] if statuses else "unverified"
    return min(known, key=STATUS_ORDER.index)
