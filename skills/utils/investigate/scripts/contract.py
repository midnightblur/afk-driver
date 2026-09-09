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


# One search, one spelling. Every git-grep query this format records is written
# in this grammar and no other:
#
#   git grep -n -I -E [-i] [--untracked] [-w] (-e <expression>)+ [-- <path>+]
#
# Options are unbundled, short of a long form, and in that order; the mode is
# always -E. Chasing what a tool would make of every other spelling is a game
# with no end, so a command outside the grammar is not a search this format
# reads. `LEDGER-FORMAT.md` states it, and every emitter writes it through
# `build_command`.
CANONICAL = ("git grep -n -I -E [-i] [--untracked] [-w] (-e <expression>)+ "
             "[-- <path>+]")
FIXED = ("git", "grep", "-n", "-I", "-E")
OPTIONAL_FLAGS = ("-i", "--untracked", "-w")


def argv(command: str) -> list[str]:
    """The tokens a shell would hand the tool."""
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def build_command(expressions, paths=None, flags=()) -> str:
    """One recorded search, in the grammar, quoted so it runs again verbatim."""
    outside = [flag for flag in flags if flag not in OPTIONAL_FLAGS]
    if outside:
        raise ValueError(f"{', '.join(outside)}: outside the canonical grammar")
    if not expressions:
        raise ValueError("a search carries at least one expression")
    parts = list(FIXED)
    parts += [flag for flag in OPTIONAL_FLAGS if flag in flags]
    for expression in expressions:
        parts += ["-e", shlex.quote(expression)]
    if paths:
        parts += ["--", *(shlex.quote(path) for path in paths)]
    return " ".join(parts)


def parse_canonical(command: str):
    """What a canonical command runs, or `None` where it is not one.

    Returns the flags it carried, the expressions it searched for as a set —
    their order says nothing — and the paths it ran over, in order.
    """
    parts = argv(command)
    if parts[:len(FIXED)] != list(FIXED):
        return None
    rest = parts[len(FIXED):]
    flags: list[str] = []
    while rest and rest[0] in OPTIONAL_FLAGS:
        flags.append(rest.pop(0))
    if len(set(flags)) != len(flags):
        return None
    if flags != [flag for flag in OPTIONAL_FLAGS if flag in flags]:
        return None
    expressions: list[str] = []
    while len(rest) >= 2 and rest[0] == "-e":
        expressions.append(rest[1])
        rest = rest[2:]
    if not expressions:
        return None
    paths: tuple[str, ...] = ()
    if rest:
        if rest[0] != "--" or len(rest) < 2:
            return None
        paths = tuple(rest[1:])
    return frozenset(flags), frozenset(expressions), paths


def is_search(command: str) -> bool:
    """Whether a command claims to be a search; the grammar judges the rest."""
    return argv(command)[:2] == ["git", "grep"]


def search_key(command: str):
    """What two commands compare on: the search, never the files it narrowed to."""
    parsed = parse_canonical(command)
    if parsed is None:
        return ("outside the grammar", command.strip())
    flags, expressions, _ = parsed
    return (flags, expressions)


# A search naming no path ran over the whole repository, which is not the same
# as contributing nothing to a union of paths.
ALL_FILES = ("<every tracked file>",)


def searched_paths(command: str) -> tuple[str, ...]:
    """The paths a canonical search ran over, or the whole tree."""
    parsed = parse_canonical(command)
    if parsed is None:
        return ()
    return tuple(sorted(parsed[2])) or ALL_FILES


# Every command family this format records, each with the one shape it takes.
# A command outside all of them is a command no reader can place.
COMMAND_FAMILIES = (
    ("search", CANONICAL),
    ("built-output walk", "in-process walk of <path>[, <path>]*"),
    ("tracked listing", "git ls-files -- <path>[, <path>]*"),
    ("manifest parse", "parse <manifest>[, <manifest>]*"),
    ("sibling listing", "list the directories beside <manifest>[, <manifest>]*"),
)

PROSE_FAMILIES = (
    ("built-output walk", "in-process walk of "),
    ("tracked listing", "git ls-files -- "),
    ("manifest parse", "parse "),
    ("sibling listing", "list the directories beside "),
)


def family(command: str) -> str | None:
    """The family a recorded command belongs to, or `None` for none of them."""
    text = (command or "").strip()
    if is_search(text):
        return "search" if parse_canonical(text) else None
    for name, prefix in PROSE_FAMILIES:
        if text.startswith(prefix) and text[len(prefix):].strip():
            return name
    return None


def respell(command: str) -> str | None:
    """The same search, written in the grammar — a mechanical fix, or `None`.

    Reads what a command outside the grammar was asking for: options bundled,
    spelled long, or in another order, and the expressions they carried.
    """
    parts = argv(command)
    if parts[:2] != ["git", "grep"]:
        return None
    long_forms = {"--ignore-case": "-i", "--word-regexp": "-w",
                  "--regexp": "-e", "--untracked": "--untracked"}
    flags: list[str] = []
    expressions: list[str] = []
    index = 2
    while index < len(parts):
        token, joined = parts[index], None
        if token.startswith("--") and "=" in token:
            token, _, joined = token.partition("=")
        token = long_forms.get(token, token)
        if token == "-e" and joined is not None:
            expressions.append(joined)
            index += 1
            continue
        if token == "--":
            break
        if token == "-e" and index + 1 < len(parts):
            expressions.append(parts[index + 1])
            index += 2
            continue
        if token.startswith("--"):
            if token in OPTIONAL_FLAGS:
                flags.append(token)
            index += 1
            continue
        if token.startswith("-"):
            for letter in token[1:]:
                if f"-{letter}" in OPTIONAL_FLAGS:
                    flags.append(f"-{letter}")
            index += 1
            continue
        expressions.append(token)
        index += 1
    paths = parts[index + 1:] if index < len(parts) else []
    if not expressions:
        return None
    return build_command(expressions, paths, sorted(set(flags)))


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
