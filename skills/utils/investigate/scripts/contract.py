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


# One search, one spelling: `CANONICAL` below is the grammar every git-grep
# query this format records is written in. Options are unbundled, short of a
# long form, and in that order; the mode is always -E. Chasing what a tool would
# make of every other spelling is a game with no end, so a command outside it is
# not a search this format reads. `LEDGER-FORMAT.md` § "Command families" states
# it for a reader; every emitter writes it through `build_command`.
CANONICAL = ("git grep -n -I -E [-i] [--untracked] [-w] (-e <expression>)+ "
             "[-- <path>+]")
FIXED = ("git", "grep", "-n", "-I", "-E")
OPTIONAL_FLAGS = ("-i", "--untracked", "-w")


def argv(command: str) -> list[str] | None:
    """The tokens a shell would hand the tool, or `None` for none it would.

    A command no shell can split is a command nobody can rerun; guessing at
    tokens would publish a search that never ran under a name that reads real.
    """
    try:
        return shlex.split(command or "")
    except ValueError:
        return None


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
    if parts is None or parts[:len(FIXED)] != list(FIXED):
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
        kept = [repo_path(item) for item in rest[1:]]
        if any(item is None for item in kept):
            return None
        paths = tuple(kept)
    # The one spelling is the one the builder writes: a command that does not
    # come back out of it carried something the grammar has no place for — a
    # token a shell would have expanded before git ever saw it, or quoting
    # nobody can reproduce.
    if command.strip() != build_command(expressions, list(paths), flags):
        return None
    return frozenset(flags), frozenset(expressions), paths


def is_search(command: str) -> bool:
    """Whether a command claims to be a search; the grammar judges the rest."""
    return (argv(command) or [])[:2] == ["git", "grep"]


class _AllFiles:
    """The whole repository: a universe, never a path a list could hold."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "the whole tree"


# A search naming no path ran over everything, which is not a path list and not
# an empty contribution to one. Out of band on purpose: any string here is a
# string some repository could name a file.
ALL_FILES = _AllFiles()


def searched_paths(command: str):
    """The paths a canonical search ran over, or `ALL_FILES` for the whole tree."""
    parsed = parse_canonical(command)
    if parsed is None:
        return ()
    return tuple(sorted(parsed[2])) or ALL_FILES


# Every command family this format records, each with the one shape it takes.
# A command outside all of them is a command no reader can place.
COMMAND_FAMILIES = (
    ("search", CANONICAL),
    ("built-output walk", "in-process walk of -- <path>+"),
    ("tracked listing", "git ls-files -- <path>+"),
    ("manifest parse", "parse -- <manifest>+"),
    ("sibling listing", "list the directories beside -- <manifest>+"),
)

PROSE_FAMILIES = (
    ("built-output walk", "in-process walk of --"),
    ("tracked listing", "git ls-files --"),
    ("manifest parse", "parse --"),
    ("sibling listing", "list the directories beside --"),
)


_FOLD = None


def repo_path(text: str) -> str | None:
    """One path, one spelling — or `None` for one no repository holds.

    The rule itself lives with the config reader (`scripts/afk-config.py`,
    `normalize_path`), which reads the paths a repository declares: two copies
    of it drift, and a path one accepts while the other refuses is a run that
    dies between them.
    """
    global _FOLD
    if _FOLD is None:
        _FOLD = _config_reader().normalize_path
    return _FOLD(text)


def _config_reader():
    """The one config reader, imported by path — it owns the path rule."""
    import importlib.util
    import os
    from pathlib import Path

    roots = []
    env = os.environ.get("AFK_PLUGIN_ROOT")
    if env:
        roots.append(Path(env))
    roots += list(Path(__file__).resolve().parents)
    for root in roots:
        target = root / "scripts" / "afk-config.py"
        if target.is_file():
            spec = importlib.util.spec_from_file_location("afk_config_paths", target)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise ImportError("cannot locate scripts/afk-config.py; set AFK_PLUGIN_ROOT")


def build_listing(name: str, paths) -> str:
    """One recorded listing, in its family's shape, paths as quoted tokens."""
    prefix = dict(PROSE_FAMILIES).get(name)
    if prefix is None:
        raise ValueError(f"{name}: no such command family")
    kept = [repo_path(path) for path in paths]
    if not kept or any(path is None for path in kept):
        raise ValueError(f"{name}: a path no repository holds")
    return " ".join([prefix, *(shlex.quote(path) for path in kept)])


def family(command: str) -> str | None:
    """The family a recorded command belongs to, or `None` for none of them.

    Membership is the builder's own answer: a command is of a family when
    rebuilding it from the parts it parses to returns the same bytes. Anything
    else — a path spelled another way, a token a shell would have eaten, a
    prefix glued to its first path — is a command nobody can rerun as written.
    """
    text = (command or "").strip()
    if argv(text) is None:
        return None
    if is_search(text):
        return "search" if parse_canonical(text) else None
    for name, prefix in PROSE_FAMILIES:
        if not text.startswith(prefix + " "):
            continue
        paths = parsed_paths(text, prefix)
        if not paths:
            continue
        try:
            if build_listing(name, paths) == text:
                return name
        except ValueError:
            continue
    return None


def parsed_paths(command: str, prefix: str) -> tuple[str, ...]:
    """The paths a prose family lists, in the command's own order.

    Empty where the command lists none, or one no repository holds: a path is
    a token a shell would hand over, so a comma inside one is part of it.
    """
    rest = command.strip()[len(prefix):]
    if chr(92) in rest:
        # A shell reads it as an escape; a repository path never carries one.
        return ()
    parts = argv(rest)
    if not parts:
        return ()
    kept = [repo_path(part) for part in parts]
    if any(path is None for path in kept):
        return ()
    return tuple(kept)


def listed(command: str, prefix: str) -> tuple[str, ...]:
    """What a prose family read, as a set — relisting is the same method."""
    return tuple(sorted(set(parsed_paths(command, prefix))))


def command_key(command: str):
    """The one key a command of any family compares on.

    A search is its flags and its expressions, the paths left out — the same
    search over fewer files is that search narrowed. Every other family is what
    it read, as a set: relisting the same paths is the same method.
    """
    text = (command or "").strip()
    name = family(text)
    if name is None:
        return ("outside the grammar", text)
    if name == "search":
        flags, expressions, _ = parse_canonical(text)
        return (name, flags, expressions)
    prefix = dict(PROSE_FAMILIES)[name]
    return (name, listed(text, prefix))


def respell(command: str) -> str | None:
    """The same search, written in the grammar — a mechanical fix, or `None`.

    Reads what a command outside the grammar asked for: options bundled,
    spelled long, joined to their value, or in another order. An option the
    grammar has no place for — another mode, an inversion, another output —
    changes what the search means, so no hint is offered at all: a hint that
    runs a different search is worse than none.
    """
    parts = argv(command)
    if parts is None or parts[:2] != ["git", "grep"]:
        return None
    known = {"--ignore-case": "-i", "--word-regexp": "-w", "--regexp": "-e",
             "--untracked": "--untracked", "-i": "-i", "-w": "-w", "-e": "-e",
             "-n": "-n", "-I": "-I", "-E": "-E",
             "--line-number": "-n", "--extended-regexp": "-E"}
    flags: list[str] = []
    expressions: list[str] = []
    index = 2
    while index < len(parts):
        token, joined = parts[index], None
        if token.startswith("--") and "=" in token:
            token, _, joined = token.partition("=")
        if token == "--":
            break
        if token.startswith("--"):
            option = known.get(token)
            if option is None:
                return None
            if option == "-e":
                if joined is None:
                    if index + 1 >= len(parts):
                        return None
                    joined = parts[index + 1]
                    index += 1
                expressions.append(joined)
            elif option in OPTIONAL_FLAGS:
                flags.append(option)
            index += 1
            continue
        if token.startswith("-"):
            for letter in token[1:]:
                option = known.get(f"-{letter}")
                if option is None:
                    return None
                if option == "-e":
                    if index + 1 >= len(parts):
                        return None
                    expressions.append(parts[index + 1])
                    index += 1
                elif option in OPTIONAL_FLAGS:
                    flags.append(option)
            index += 1
            continue
        expressions.append(token)
        index += 1
    paths = parts[index + 1:] if index < len(parts) else []
    kept = [repo_path(path) for path in paths]
    if any(path is None for path in kept):
        return None
    if not expressions:
        return None
    return build_command(expressions, kept, sorted(set(flags)))


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
