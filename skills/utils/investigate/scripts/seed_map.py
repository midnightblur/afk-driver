#!/usr/bin/env python3
"""Seed map: the deterministic pre-pass of a code investigation.

Enumerates the search space for one subject over the boundary classes
`INVESTIGATION.md` (plugin root) owns, so an agent spends tokens on judgment
and never on enumeration. It seeds an investigation; it never claims semantic
reachability, and it never writes into the repository it reads.

Usage:
  seed_map.py --repo ROOT --subject NAME [--subject NAME ...]
              --type Q1..Q5 [--type ...] [--question TEXT]
              [--alias FORM=VALUE ...] [--config auto|PATH] [--design-phase]
              --out FILE.json

Output is a ledger-shaped document (`LEDGER-FORMAT.md` beside this script):
the same six tables, every node it found carrying `unverified` until a tracer
dispositions it. Boundary instances come from the `investigation:` block of the
repository's `.afk/config.yaml`, read and validated through
`scripts/afk-config.py` (the one reader). Absent block: the generic defaults
run alone, and every class with neither a default nor a declared instance is
reported `unverified(no enumeration method)` — never as an absence.

A class is `closed` only over a set this script actually reached: a class
searching another class's hits inherits that class's gap, a walk that skipped a
file says so, and a declared site that is gone is a gap, never evidence.

Subprocess budget: one `git ls-files`, one `git rev-parse`, one `git grep` per
name-form pass, and per boundary class two `git grep` per distinct path scope —
the search, and the case-blind counter-search that tries to break it.
A spawn costs 0.5-2s on this platform (`hooks/README.md` cost model), so
classification runs in Python.

Exit codes: 0 wrote the seed map, 2 usage, configuration, or git error.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contract import ALL_CLASSES, HIT_LIMIT, line_hash, stable_id, worst  # noqa: E402

JVM = (".java", ".kt", ".kts", ".scala", ".groovy")
CURLY = JVM + (".ts", ".tsx", ".js", ".jsx", ".php", ".cs")
ANNOTATED = JVM + (".ts", ".py")

# Generic default patterns, one entry per class that has one. Framework-shaped
# and product-free: a repository's own mechanisms belong in its `investigation:`
# block, never here. `{simple}` expands to the subject's simple names, already
# grouped — a pattern embeds it as written. The expansion is every simple name
# plus every declared alias, so a pattern class searches the forms B1 searched.
#
# `scoped` says how a class's hits are found:
#   "names"        - the name-form passes themselves
#   "subject"      - the pattern carries the subject's name forms, so it is
#                    as complete as the enumeration of those forms
#   "registration" - the pattern finds a registration form; hits are kept only
#                    in files a name form already hit, intersected in-process
#   "filter"       - no query of its own; the name-form hits filtered to paths
#
# Every class but "names" depends on B1's name-form enumeration — by searching
# its hit set, or by interpolating its forms — so none can be more complete
# than B1 is.
#
# `languages` names the file kinds a default pattern can match in. A repository
# holding none of them gets `unverified(pattern cannot match)`, never closed(0).
DEFAULTS: dict[str, dict] = {
    "B1": {"scoped": "names", "method": "every name form, whole repository"},
    "B2": {
        "scoped": "subject",
        "patterns": [r"(extends|implements)[^;{]*{bounded}", r"\(\s*{simple}\s+\w"],
        "method": "declaration and parameter forms carrying the name",
        "languages": CURLY,
        "language_label": "class-declaration",
    },
    "B4": {
        "scoped": "subject",
        "patterns": [r"[\"']{simple}[\"']"],
        "method": "the name as a string literal",
    },
    "B8": {
        "scoped": "filter",
        "paths": ["*.yml", "*.yaml", "*.properties", "*.conf", "*.ini", "*.env"],
        "method": "name forms filtered to configuration files",
    },
    "B9": {
        "scoped": "filter",
        "paths": ["*.sql", "*migration*", "*schema*"],
        "method": "name forms filtered to schema and migration sources",
    },
    "B11": {
        "scoped": "registration",
        "patterns": [r"@\w*Listener\b", r"@Scheduled\b", r"@\w*Handler\b"],
        "method": "registration forms in files that name the subject",
        "languages": ANNOTATED,
        "language_label": "annotation-carrying",
    },
    "B12": {
        "scoped": "filter",
        "paths": ["*test*", "*Test*", "*spec*"],
        "method": "name forms filtered to test sources",
    },
    "B13": {
        "scoped": "filter",
        "paths": ["*.md", "*.adoc", "*.txt"],
        "method": "name forms filtered to documents",
    },
}

# A word boundary POSIX extended regular expressions can express, so a short
# alias never matches inside a longer identifier. `\b` cannot do this job: an
# alias whose first or last character is not a word character has no boundary
# there, and the pattern then matches nothing at all.
LEFT = "(^|[^[:alnum:]_])"
RIGHT = "($|[^[:alnum:]_])"
PY_LEFT = "(?:^|[^0-9A-Za-z_])"
PY_RIGHT = "(?:$|[^0-9A-Za-z_])"

# How much of a matching line is stored as evidence. Matching happens on the
# whole line; only storage is capped.
EVIDENCE_CHARS = 200

# A generated file larger than this is output, not source, and is not read.
MAX_WALK_BYTES = 2 * 1024 * 1024

# Bytes of pathspec argv one executed search may carry. Well under the shell
# limits of every supported platform, so a path list past it runs as several
# commands rather than as one command nobody can rerun.
PATHSPEC_BUDGET = 8000

# How many skipped or missing paths a reason names before it says "and N more".
REASON_SAMPLE = 5

# The build-graph class parses aggregator manifests. Only XML is supported;
# anything else is reported, never guessed at (`CONFIG.md` § Investigation).
REACTOR_SUFFIXES = (".xml",)

# Both spellings git accepts for a case-blind pass.
CASE_BLIND = {"-i", "--ignore-case"}


class GitError(RuntimeError):
    """A git invocation failed for a reason that is not `no match`."""


class ConfigError(RuntimeError):
    """The effective configuration did not validate, or could not be read."""


class SeedTooWide(RuntimeError):
    """One class returned more than a ledger can carry as whole nodes."""


def sample(items: list[str]) -> str:
    """Name a few of them, and say how many were not named."""
    shown = ", ".join(items[:REASON_SAMPLE])
    rest = len(items) - REASON_SAMPLE
    return shown + (f", and {rest} more" if rest > 0 else "")


def plugin_root() -> Path:
    """The installed plugin root, checked rather than counted to."""
    candidates = []
    env = os.environ.get("AFK_PLUGIN_ROOT")
    if env:
        candidates.append(Path(env))
    candidates += list(Path(__file__).resolve().parents)
    for candidate in candidates:
        if (candidate / "scripts" / "afk-config.py").is_file():
            return candidate
    raise ConfigError("cannot locate the plugin root; set AFK_PLUGIN_ROOT")


def outside_brackets(pattern: str) -> str:
    """The pattern with its escapes and its bracket expressions removed.

    What is left is the text whose case the expression actually pins. A
    bracket expression states the cases it accepts, and an escaped character
    is one character, never a class.
    """
    kept: list[str] = []
    index = 0
    inside = False
    while index < len(pattern):
        character = pattern[index]
        if character == "\\":
            index += 2
            continue
        if inside and character != "]":
            # A range like `a-z` is widened by a case-blind pass, so its
            # letters count; `[Ww]` spells its cases and does not.
            if (character == "-" and kept is not None and index + 1 < len(pattern)
                    and pattern[index - 1].isascii() and pattern[index - 1].isalpha()
                    and pattern[index + 1].isascii() and pattern[index + 1].isalpha()):
                kept.append(pattern[index + 1])
            index += 1
            continue
        if not inside:
            if character == "[":
                inside = True
                index += 1
                # A `^` opens a negation, and a `]` in first position is a
                # literal `]`, not the close.
                if index < len(pattern) and pattern[index] == "^":
                    index += 1
                if index < len(pattern) and pattern[index] == "]":
                    index += 1
                continue
            kept.append(character)
        elif character == "]":
            inside = False
        index += 1
    return "".join(kept)


def discriminating(patterns: list[str], primary_extra: list[str] | None) -> bool:
    """Whether a case-blind rerun can return what the primary could not.

    It cannot when the primary already ran case-blind, and it cannot when the
    expressions pin no letter — a digit class matches the same text either
    way. Both are the same pass twice.
    """
    if set(primary_extra or []) & CASE_BLIND:
        return False
    return any(character.isascii() and character.isalpha()
               for pattern in patterns
               for character in outside_brackets(pattern))


def block_warnings(block: dict) -> list[str]:
    """Declared instances that will run, but not the way the declarer expects.

    Not a defect: the pattern is legal and the run proceeds. It is said once,
    on the way in, because the row it produces looks like closure.
    """
    warnings = []
    for entry in block.get("boundaries") or []:
        if not isinstance(entry, dict):
            continue
        pattern = entry.get("pattern") or ""
        if not pattern or entry.get("paths"):
            continue
        if "{simple}" in pattern or "{bounded}" in pattern:
            continue
        warnings.append(
            f"{entry.get('name', '?')} ({entry.get('class', '?')}): the pattern names "
            "no subject placeholder and no paths, so it matches every occurrence in "
            "the repository — add `{simple}` or narrow it with `paths`"
        )
    return warnings


def load_config(repo: Path, where: str) -> tuple[dict, dict]:
    """Read and validate the effective config through the one config reader.

    Returns the investigation block and its stamp, so a ledger says which
    configuration produced it. The stamp hashes the resolved block, not the
    bytes it was written in: two files that resolve to one block are one
    search, and a comment is not a different investigation.
    """
    root = plugin_root()
    spec = importlib.util.spec_from_file_location(
        "afk_config", root / "scripts" / "afk-config.py"
    )
    if spec is None or spec.loader is None:
        raise ConfigError(f"cannot import {root / 'scripts' / 'afk-config.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if where == "auto":
        config = module.load(repo)
        found = next((repo / name for name in (".afk/config.yaml", ".afk/config.yml")
                      if (repo / name).is_file()), None)
        source = str(found.relative_to(repo).as_posix()) if found else "defaults"
    else:
        path = Path(where)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as problem:
            raise ConfigError(f"cannot read {path}: {problem}") from problem
        config = module.deep_merge(dict(module.DEFAULTS), module.parse(text, str(path)))
        source = str(path)
    problems = module.validate(config, repo)
    if problems:
        raise ConfigError("; ".join(problems))
    block = config.get("investigation")
    block = block if isinstance(block, dict) else {}
    resolved = json.dumps(block, sort_keys=True, separators=(",", ":")).encode("utf-8")
    stamp = {"path": source, "sha256": hashlib.sha256(resolved).hexdigest()}
    return block, stamp


def name_forms(subject: str, aliases: list[tuple[str, str]]) -> list[dict]:
    """Every form the subject can be written in, each labelled enumerated or not.

    A form nobody enumerated keeps B1 short of closed: an alias and a wire name
    are chosen at the site, not derivable from the symbol, so they are searched
    only when the caller passes them as `--alias FORM=VALUE`.
    """
    simple = subject.rsplit(".", 1)[-1]
    forms = [{"form": "simple", "value": simple, "enumerated": True}]
    if "." in subject:
        forms.append({"form": "qualified", "value": subject, "enumerated": True})
    forms.append({"form": "string-literal", "value": f'"{simple}"', "enumerated": True})
    declared = {form for form, _ in aliases}
    for form, value in aliases:
        forms.append({"form": form, "value": value, "enumerated": True, "source": "declared"})
    for form in ("import-alias", "wire"):
        if form not in declared:
            forms.append(
                {
                    "form": form,
                    "value": None,
                    "enumerated": False,
                    "reason": f"a {form} name is chosen at the site; pass --alias {form}=VALUE",
                }
            )
    return forms


def git(repo: Path, *args: str, allowed: tuple[int, ...] = (0,)) -> str:
    """Run git with paths verbatim. A return code outside `allowed` is an error."""
    done = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=str(repo),
        capture_output=True,
        encoding="utf-8",
        errors="surrogateescape",
    )
    if done.returncode not in allowed:
        raise GitError(
            f"git {' '.join(args[:2])} exited {done.returncode}: "
            f"{(done.stderr or '').strip()[:300]}"
        )
    return done.stdout or ""


def parse_hits(out: str) -> list[dict]:
    """Whole matching lines, byte for byte: an indent is part of the line."""
    hits = []
    for line in out.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3 or not parts[1].isdigit():
            continue
        hits.append({"file": parts[0], "line": int(parts[1]), "text": parts[2]})
    return hits


def grep(repo: Path, patterns: list[str], pathspecs: list[str] | None,
         extra: list[str] | None = None) -> list[dict]:
    """One `git grep` for a whole class. Exit 1 means no match, not failure."""
    if not patterns:
        return []
    args = ["grep", "-n", "-I", "-E", "--no-color", *(extra or [])]
    for pattern in patterns:
        args += ["-e", pattern]
    if pathspecs:
        args += ["--", *pathspecs]
    return parse_hits(git(repo, *args, allowed=(0, 1)))


def chunk_pathspecs(paths: list[str]) -> list[list[str]]:
    """The path list, split into runs one command can carry.

    Sorted paths and a fixed budget, so two runs over one file set chunk the
    same way and the recorded commands compare.
    """
    chunks: list[list[str]] = []
    current: list[str] = []
    size = 0
    for path in sorted(set(paths)):
        cost = len(shlex.quote(path)) + 1
        if current and size + cost > PATHSPEC_BUDGET:
            chunks.append(current)
            current, size = [], 0
        current.append(path)
        size += cost
    if current:
        chunks.append(current)
    return chunks


def walk_grep(repo: Path, roots: list[str], expression: str) -> tuple[list[dict], list[str]]:
    """Search paths git does not track — built output is untracked by design.

    Returns the hits and the paths it could not read: a file too large or not
    text is a file nobody searched, and the caller says so.
    """
    compiled = re.compile(expression)
    hits: list[dict] = []
    unread: list[str] = []
    for root in roots:
        target = repo / root
        files = [target] if target.is_file() else sorted(
            path for path in target.rglob("*") if path.is_file()
        )
        for path in files:
            rel = path.relative_to(repo).as_posix()
            try:
                if path.stat().st_size > MAX_WALK_BYTES:
                    unread.append(rel)
                    continue
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                unread.append(rel)
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if compiled.search(line):
                    hits.append({"file": rel, "line": number, "text": line})
    return hits, unread


def matches_any(path: str, pathspecs: list[str]) -> bool:
    from fnmatch import fnmatch

    for spec in pathspecs:
        if fnmatch(path, spec) or fnmatch(Path(path).name, spec):
            return True
        if "/" not in spec and "*" not in spec and spec in path.split("/"):
            return True
        if spec.endswith("/") and path.startswith(spec):
            return True
    return False


def reactor_modules(repo: Path, poms: list[str]) -> dict:
    """B7: the declared module list, and the modules commented out of it.

    A commented-out module still deploys from an earlier build, so it is
    reported rather than dropped. A manifest that is missing, of an unsupported
    kind, or that will not parse is named — never guessed at.
    """
    declared: list[str] = []
    commented: list[str] = []
    missing: list[str] = []
    unsupported: list[str] = []
    unparsable: list[str] = []
    for pom in poms:
        target = repo / pom
        if not target.is_file():
            missing.append(pom)
            continue
        if target.suffix.lower() not in REACTOR_SUFFIXES:
            unsupported.append(pom)
            continue
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unparsable.append(pom)
            continue
        for comment in re.findall(r"<!--(.*?)-->", text, re.S):
            commented += [m.strip() for m in re.findall(r"<module>(.*?)</module>", comment, re.S)]
        stripped = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        try:
            root = ElementTree.fromstring(stripped)
        except ElementTree.ParseError:
            unparsable.append(pom)
            continue
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] == "module" and node.text:
                declared.append(node.text.strip())
    return {
        "declared": declared,
        "commented_out": commented,
        "missing_manifests": missing,
        "unsupported_manifests": unsupported,
        "unparsable_manifests": unparsable,
    }


def sibling_modules(repo: Path, poms: list[str]) -> list[str]:
    """The module directories the tree holds beside each declared manifest.

    The build graph's counter-method: the parse reads what a manifest says,
    this reads what the tree carries. A directory holding a manifest of its
    own that the parse never named is a module the declared list left out.
    """
    found: list[str] = []
    for pom in poms:
        target = repo / pom
        if not target.is_file():
            continue
        for child in sorted(path for path in target.parent.iterdir() if path.is_dir()):
            if (child / target.name).is_file() and child.name not in found:
                found.append(child.name)
    return found


def build_class_map(block: dict) -> dict[str, list[dict]]:
    """Declared instances, grouped by the class each names."""
    grouped: dict[str, list[dict]] = {}
    for entry in block.get("boundaries") or []:
        if isinstance(entry, dict) and entry.get("class"):
            grouped.setdefault(entry["class"], []).append(entry)
    return grouped


def group(names: list[str]) -> str:
    """One alternation, always parenthesized — a bare `A|B` splits the pattern.

    A plain group, not a non-capturing one: `git grep -E` speaks POSIX extended
    regular expressions, where `(?:` is a syntax error.
    """
    return "(" + "|".join(re.escape(name) for name in names) + ")"


def is_word(char: str) -> bool:
    return bool(char) and (char.isalnum() or char == "_")


def bounded(name: str, left: str, right: str) -> str:
    """One name that cannot match inside a longer identifier.

    The boundary is added only on a side where the name itself ends in a word
    character. `W` needs both; `$Alias` needs only the right one, and asking
    for a left boundary there would make the pattern match nothing.
    """
    escaped = re.escape(name)
    return ((left if is_word(name[:1]) else "")
            + escaped
            + (right if is_word(name[-1:]) else ""))


def bounded_group(names: list[str], flavour: str = "ere") -> str:
    """The alternation, each alternative bounded. `flavour`: `ere` or `py`."""
    left, right = (LEFT, RIGHT) if flavour == "ere" else (PY_LEFT, PY_RIGHT)
    return "(" + "|".join(bounded(name, left, right) for name in names) + ")"


def form_pattern(form: dict, flavour: str = "ere") -> str:
    """The search expression for one name form.

    A declared alias is bounded: it is chosen at the site and is often short,
    so an unbounded pass returns every longer identifier that contains it, and
    every class deriving from that pass inherits the inflation. A derived form
    is the symbol itself and stays verbatim.
    """
    if form.get("source") != "declared":
        return re.escape(form["value"])
    left, right = (LEFT, RIGHT) if flavour == "ere" else (PY_LEFT, PY_RIGHT)
    return bounded(form["value"], left, right)


def expand(pattern: str, simple: str, bounded_terms: str) -> str:
    """Fill a default pattern's placeholders.

    A literal replacement, not `str.format`: a search expression carries braces
    of its own (`{2,3}` is a quantifier), and formatting one would fail on them.
    """
    return pattern.replace("{simple}", simple).replace("{bounded}", bounded_terms)


def site_present(repo: Path, inventory: set[str], site: str) -> bool:
    """A judgment-only site is evidence only while it exists on this snapshot."""
    normalized = site.strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.rstrip("/")
    if normalized in inventory:
        return True
    if any(path.startswith(normalized + "/") for path in inventory):
        return True
    return (repo / normalized).exists()


class Ledger:
    """The node table, and the ids the boundary rows point at."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}

    @staticmethod
    def tag(hits: list[dict], query_id: str) -> list[dict]:
        """Stamp each hit with the query that returned it; a node keeps it."""
        for hit in hits:
            hit["query_id"] = query_id
        return hits

    def add(self, klass: str, hits: list[dict], reason: str,
            query_id: str | None = None) -> list[str]:
        ids = []
        for hit in hits:
            node_id = f"{klass}:{hit['file']}:{hit['line']}"
            ids.append(node_id)
            self.nodes.setdefault(
                node_id,
                {
                    "id": node_id,
                    "class": klass,
                    "site": f"{hit['file']}:{hit['line']}",
                    "disposition": "unverified",
                    "reason": reason,
                    "evidence": hit["text"].strip()[:EVIDENCE_CHARS],
                    "line_hash": line_hash(hit["text"]),
                    "parent": None,
                    "query_id": hit.get("query_id") or query_id,
                },
            )
        return ids

    def rows(self) -> list[dict]:
        return [self.nodes[key] for key in sorted(self.nodes)]


def seed(repo: Path, subjects: list[str], qtypes: list[str], question: str,
         aliases: list[tuple[str, str]], block: dict, config_stamp: dict,
         design_phase: bool = False) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    forms = {subject: name_forms(subject, aliases) for subject in subjects}
    simple_names = [subject.rsplit(".", 1)[-1] for subject in subjects]

    listing = git(repo, "ls-files")
    inventory = listing.splitlines()
    inventory_set = set(inventory)
    suffixes = {Path(path).suffix.lower() for path in inventory}
    inventory_hash = hashlib.sha256(listing.encode("utf-8", "surrogateescape")).hexdigest()
    head = git(repo, "rev-parse", "HEAD").strip()

    ledger = Ledger()
    queries: dict[str, dict] = {}
    declared = build_class_map(block)
    seed_reason = "seed map hit, not yet triaged"

    def note(command: str, universe: str, lines: int) -> str:
        """Record the query and hand back its id, so a row can point at it.

        `command` is the literal thing that ran, expressions included — the id
        is its digest, so a label like `<default patterns>` would collide two
        different searches into one row and lose one of them on a merge.
        `lines` is what the search returned; `count` is the nodes citing it,
        and the finalization pass reads that off the nodes table.
        """
        row = {"id": stable_id("q", command + universe), "command": command,
               "universe": universe, "count": 0, "lines": lines, "evidence": None,
               "origin": "seed"}
        queries.setdefault(row["id"], row)
        return row["id"]

    def grep_command(patterns: list[str], pathspecs: list[str] | None,
                     extra: list[str] | None = None) -> str:
        """The invocation, written out — what `note` digests into a query id."""
        parts = ["git grep -n -I -E", *(extra or [])]
        parts += [f"-e {shlex.quote(pattern)}" for pattern in patterns]
        if pathspecs:
            parts += ["--", *(shlex.quote(spec) for spec in pathspecs)]
        return " ".join(parts)

    def search(patterns: list[str], files: list[str] | None, universe: str,
               extra: list[str] | None = None) -> tuple[list[dict], list[str]]:
        """Run the search the ledger records, pathspecs and all.

        A class that searches only the files another class named passes those
        files as pathspecs, so the recorded command returns what the row
        counted; a list past the argv budget runs as several commands, each its
        own query row, and every hit cites the one that returned it.
        """
        if files is None:
            found = grep(repo, patterns, None, extra=extra)
            query_id = note(grep_command(patterns, None, extra), universe, len(found))
            return ledger.tag(found, query_id), [query_id]
        hits: list[dict] = []
        ids: list[str] = []
        for chunk in chunk_pathspecs(files):
            found = grep(repo, patterns, chunk, extra=extra)
            query_id = note(grep_command(patterns, chunk, extra), universe, len(found))
            hits += ledger.tag(found, query_id)
            ids.append(query_id)
        return hits, ids

    def carries_simple(value: str) -> bool:
        # Case-sensitive, because the primary pass is: a form the exact search
        # already returns is not a form the counter-search can learn from.
        return any(name in value for name in simple_names)

    every_form = [
        form for subject_forms in forms.values() for form in subject_forms
        if form["enumerated"] and form["value"]
    ]
    primary_forms = [form for form in every_form if carries_simple(form["value"])]
    counter_forms = [form for form in every_form if not carries_simple(form["value"])]
    counter_values = [form["value"] for form in counter_forms]
    declared_aliases = [form for form in every_form if form.get("source") == "declared"]
    # What a `{simple}` pattern expands to. A declared alias is a name the
    # subject is written in, so a pattern searching for the name searches for
    # it too — otherwise every pattern class closes over the simple form alone.
    subject_terms = simple_names + [form["value"] for form in declared_aliases]
    unenumerated = sorted(
        {
            form["form"]
            for subject_forms in forms.values()
            for form in subject_forms
            if not form["enumerated"]
        }
    )

    # B1 first: its hit set is the universe every filter and registration class
    # searches, so those classes can be no more complete than it is. Two
    # universes, two calls: the class's own exact tracked pass, and the wider
    # case-blind pass over untracked files the counter-search runs. Each
    # recorded command is the one that ran, so a reader reruns either verbatim.
    primary_patterns = [form_pattern(form) for form in primary_forms]
    b1_hits = grep(repo, primary_patterns, None)
    kept = {(hit["file"], hit["line"]) for hit in b1_hits}
    wide = grep(repo, primary_patterns, None, extra=["-i", "--untracked"])
    second_universe = "case-blind pass over tracked and untracked files, not ignored"
    wider_only = [hit for hit in wide if (hit["file"], hit["line"]) not in kept]
    # The name-form queries; every class searching B1's hit set points at them.
    name_query_ids = [note(grep_command(primary_patterns, None),
                           "tracked text files, binary excluded", len(b1_hits))]
    ledger.tag(b1_hits, name_query_ids[0])
    seen = set(kept)
    second_universe_id = note(grep_command(primary_patterns, None, ["-i", "--untracked"]),
                              second_universe, len(wide))
    ledger.tag(wider_only, second_universe_id)

    # Counter-search one: a name form that does not carry the simple name — a
    # form the primary pass provably cannot return.
    counter_checks: list[dict] = []
    # The checks whose hits reach every class that searches B1's hit set.
    inherited_checks: list[dict] = []
    claim_text = ("the hit set holds every reference to "
                  + ", ".join(subjects) + " over the name forms this pass searched")
    claim_id = stable_id("c", claim_text)
    if counter_values:
        # The same universe the simple pass searched: a wire name lives in
        # untracked built output as readily as in a tracked source file.
        counter_patterns = [form_pattern(form) for form in counter_forms]
        form_hits = grep(repo, counter_patterns, None, extra=["--untracked"])
        form_query = note(grep_command(counter_patterns, None, ["--untracked"]),
                          "tracked and untracked text files, not ignored", len(form_hits))
        ledger.tag(form_hits, form_query)
        tracked = [hit for hit in form_hits if hit["file"] in inventory_set]
        wider_only += [hit for hit in form_hits if hit["file"] not in inventory_set]
        new = [hit for hit in tracked if (hit["file"], hit["line"]) not in seen]
        b1_hits += new
        seen |= {(hit["file"], hit["line"]) for hit in new}
        # `classes` is filled with the derived classes once the loop knows
        # them: they inherit this search's hits through B1's set.
        form_check = {
            "method": f"name forms carrying no simple name: {', '.join(counter_values)}",
            "kind": "deterministic", "targeted_claims": [claim_id],
            "new_nodes": ledger.add("B1", new, seed_reason, form_query),
            "state": "complete", "classes": ["B1"], "query_ids": [form_query],
        }
        inherited_checks.append(form_check)
        counter_checks.append(form_check)
    elif declared_aliases:
        # No declared form discriminates from the simple name, so the second
        # universe is what the primary pass provably could not return.
        counter_checks.append({
            "method": "name form carrying no simple name: none declared discriminates, "
                      f"so the {second_universe} stands in",
            "kind": "deterministic", "targeted_claims": [claim_id], "new_nodes": [],
            "state": "complete", "classes": ["B1"], "query_ids": [second_universe_id],
        })
    else:
        counter_checks.append({
            "method": "name form carrying no simple name",
            "kind": "deterministic", "targeted_claims": [claim_id], "new_nodes": [],
            "state": "pending", "classes": ["B1"],
            "reason": "no wire or alias form declared; pass --alias FORM=VALUE",
        })

    # Counter-search two: the second universe — case-blind, and including the
    # untracked files a tracked pass cannot see. Already searched above; what
    # the exact tracked pass could not have returned is its result.
    new = [hit for hit in wider_only if (hit["file"], hit["line"]) not in seen]
    b1_hits += new
    seen |= {(hit["file"], hit["line"]) for hit in new}
    # `classes` is filled once the loop knows which classes searched B1's hit
    # set rather than running a pattern of their own.
    second_check = {
        "method": second_universe,
        "kind": "deterministic", "targeted_claims": [claim_id],
        "new_nodes": ledger.add("B1", new, seed_reason, second_universe_id),
        "state": "complete", "classes": ["B1"], "query_ids": [second_universe_id],
    }
    inherited_checks.append(second_check)
    counter_checks.append(second_check)

    def counter_pass(klass: str, patterns: list[str], pathspecs: list[str] | None,
                     seen_keys: set, keep: set | None = None,
                     primary_extra: list[str] | None = None
                     ) -> tuple[list[dict], str | None]:
        """The class's own expressions over the second universe.

        A class enumerated by its own pattern is not counter-searched by B1's
        pass: nothing there ran that pattern. Running it case-blind is a method
        the case-sensitive primary provably cannot repeat, over the same
        universe the primary searched — so the pass changes the method without
        widening the claim. Untracked files stay B1's wide pass and B6's walk;
        adding `--untracked` here triples the cost of every class.
        """
        if not discriminating(patterns, primary_extra):
            counter_checks.append({
                "method": "case-blind pass over the class's own expressions",
                "kind": "deterministic", "targeted_claims": [claim_id], "new_nodes": [],
                "state": "pending", "classes": [klass],
                "reason": "method not discriminating: a case-blind rerun of these "
                          "expressions returns what the primary pass already returned",
            })
            return [], None
        scope = sorted(keep) if keep is not None else pathspecs
        universe = ("files that name the subject, case-blind" if keep is not None
                    else "tracked files, case-blind")
        found, ids = search(patterns, scope, universe, ["-i"])
        new = [hit for hit in found if (hit["file"], hit["line"]) not in seen_keys]
        counter_checks.append({
            "method": "case-blind pass over the class's own expressions",
            "kind": "deterministic", "targeted_claims": [claim_id],
            "new_nodes": ledger.add(klass, new, seed_reason),
            "state": "complete", "classes": [klass], "query_ids": ids,
        })
        return new, ids

    declared_done: dict[str, tuple] = {}
    named_files: set[str] = set()
    b1_derived: list[str] = []
    # Set once per class, read by `record`. Holding it here rather than passing
    # it to every call is what makes the rule unskippable.
    site_state: dict[str, list[str]] = {"statuses": []}
    b1_gap =(f"name forms not enumerated: {', '.join(unenumerated)}") if unenumerated else None
    boundaries: dict[str, dict] = {}

    def record(klass: str, status: str, method: str, hits: list[dict],
               reasons: list[str] | None = None, **extra) -> None:
        # The count is the fact and the node list carries it: every hit becomes
        # a node, so `hits`, `hit_ids` and the node table say the same thing. A
        # class past the limit is a subject too generic to answer, and the run
        # stops instead of publishing a sample that reads like a class.
        unique: list[dict] = []
        placed = set()
        for hit in hits:
            key = (hit["file"], hit["line"])
            if key not in placed:
                placed.add(key)
                unique.append(hit)
        # Every row is finalized here, so the site rule cannot be skipped on
        # one exit: a site an agent still has to read is not closure, and a
        # site that is gone is a method that did not run. Worst status wins.
        if len(unique) > HIT_LIMIT:
            raise SeedTooWide(
                f"{klass}: {len(unique)} hits, past the {HIT_LIMIT} a class may "
                "carry — the subject is too generic to answer; narrow it with "
                "--alias or with paths on the boundary instance"
            )
        row = {
            "class": klass,
            "status": worst(status, *site_state["statuses"]),
            "method": method,
            "hits": len(unique),
            "hit_ids": ledger.add(klass, unique, seed_reason),
        }
        reasons = [item for item in (reasons or []) if item]
        if reasons:
            row["reason"] = "; ".join(reasons)
        row.update(extra)
        boundaries[klass] = row

    def declared_searches(klass: str,
                          instances: list[dict]) -> tuple[list[dict], list[str], list[str]]:
        """Every declared pattern, each inside its own path scope.

        Patterns sharing a scope share one call, so a scope costs one spawn.
        A declared pattern is never narrowed to the files a name form hit: the
        repository already stated its scope, and a registration naming only a
        wire form lives in a file no name form returns.
        """
        if klass in declared_done:
            return declared_done[klass]
        by_scope: dict[tuple[str, ...], list[str]] = {}
        for instance in instances:
            if instance.get("pattern"):
                by_scope.setdefault(tuple(instance.get("paths") or []), []).append(
                    expand(instance["pattern"], group(subject_terms),
                           bounded_group(subject_terms)))
        hits: list[dict] = []
        universes: list[str] = []
        qids: list[str] = []
        for scope, patterns in by_scope.items():
            primary_extra: list[str] = []
            universe = f"declared paths {', '.join(scope)}" if scope else "tracked files"
            found, scope_ids = search(patterns, list(scope) or None, universe,
                                      primary_extra)
            qids += scope_ids
            hits += found
            universes.append(universe)
            # The counter-search's own query stays out of `qids`: the class
            # row names the method that enumerated it, and the check names the
            # method that tried to break it.
            extra, _ = counter_pass(
                klass, patterns, list(scope) or None,
                {(hit["file"], hit["line"]) for hit in found},
                primary_extra=primary_extra)
            hits += extra
        declared_done[klass] = (hits, universes, qids)
        return declared_done[klass]

    # B1's declared patterns widen the set every derived class searches, so
    # they run before that set is frozen.
    b1_declared_hits, _, b1_declared_qids = declared_searches("B1", declared.get("B1", []))
    b1_hits += b1_declared_hits
    named_files.update(hit["file"] for hit in b1_hits)
    b1_query_ids = name_query_ids + b1_declared_qids

    for klass in ALL_CLASSES:
        instances = declared.get(klass, [])
        default = DEFAULTS.get(klass)
        mechanism = ", ".join(instance.get("name", "?") for instance in instances) or "default"
        sites = [i["site"] for i in instances if i.get("judgment-only") and i.get("site")]
        missing_sites = [site for site in sites if not site_present(repo, inventory_set, site)]
        live_sites = [site for site in sites if site not in missing_sites]
        site_gap = f"site missing: {sample(missing_sites)}" if missing_sites else None
        scoped = (default or {}).get("scoped")
        # A pattern class interpolates the name forms, so it is as complete as
        # the enumeration of those forms — same dependence as a filter class.
        inherits_b1 = scoped in ("filter", "registration", "subject")

        site_state["statuses"] = ([] + (["judgment-only"] if live_sites else [])
                                  + (["partial"] if site_gap else []))

        # A declared pattern runs beside whatever the class does on its own.
        extra_hits, extra_universes, extra_qids = declared_searches(klass, instances)
        extra_method = ["declared instance patterns"] if extra_universes else []

        if klass == "B1":
            record("B1", "partial" if b1_gap else "closed",
                   " + ".join([default["method"], *extra_method]), b1_hits + extra_hits,
                   reasons=[b1_gap, site_gap], mechanism=mechanism,
                   name_forms={s: forms[s] for s in subjects},
                   sites=live_sites or None,
                   query_ids=name_query_ids + extra_qids,
                   universe="tracked text files (binary excluded), and the second universe")
            continue

        if klass == "B6":
            generated = block.get("generated") or []
            if not generated and not extra_universes:
                record("B6", "unverified", "no generated paths declared", extra_hits,
                       reasons=["no enumeration method", site_gap], mechanism=mechanism,
                       universe="no generated paths declared", query_ids=extra_qids)
                continue
            absent = [path for path in generated if not (repo / path).exists()]
            present = [path for path in generated if (repo / path).exists()]
            searched = [form["value"] for form in every_form]
            hits, unread = walk_grep(repo, present, group(searched)) if present else ([], [])
            walk_qids = list(extra_qids)
            if present:
                walk_query = note(f"in-process walk of {', '.join(present)}",
                                  "built output, tracked or not", len(hits))
                walk_qids.append(walk_query)
                ledger.tag(hits, walk_query)
            unread_gap = f"{len(unread)} files unread: size or encoding — {sample(unread)}" \
                if unread else None
            unbuilt_gap = None
            if present:
                # The counter-method: the index says what belongs under these
                # paths, the walk says what is there to read. A tracked file
                # the walk never saw is one nobody searched.
                listed = [line for line in
                          git(repo, "ls-files", "--", *present).splitlines() if line]
                gone = [name for name in listed if not (repo / name).exists()]
                list_query = note(f"git ls-files -- {', '.join(present)}",
                                  "tracked files under the declared generated paths",
                                  len(listed))
                counter_checks.append({
                    "method": "the tracked file list of the generated paths, "
                              "against the walk that read them",
                    "kind": "deterministic", "targeted_claims": [claim_id],
                    "new_nodes": [], "state": "complete", "classes": ["B6"],
                    "query_ids": [list_query],
                })
                if gone:
                    unbuilt_gap = f"tracked but not on disk: {sample(gone)}"
            if absent:
                status, reason = "frontier", f"unbuilt: {sample(absent)}"
            elif unread_gap or site_gap or unbuilt_gap:
                status, reason = "partial", None
            else:
                status, reason = "closed", None
            record("B6", status,
                   " + ".join(["every name form in built generated output", *extra_method]),
                   hits + extra_hits, reasons=[reason, unread_gap, unbuilt_gap, site_gap],
                   mechanism=mechanism, sites=live_sites or None, query_ids=walk_qids,
                   universe=", ".join(["declared generated paths, read in process",
                                       *extra_universes]))
            continue

        if klass == "B7":
            poms = block.get("reactor") or []
            if not poms and not extra_universes:
                record("B7", "unverified", "no reactor manifests declared", extra_hits,
                       reasons=["no enumeration method", site_gap], mechanism=mechanism,
                       universe="no aggregator manifests declared", query_ids=extra_qids)
                continue
            modules = reactor_modules(repo, poms)
            parse_query = note(f"parse {', '.join(poms)}",
                               "declared aggregator manifests",
                               len(modules["declared"]))
            gaps = []
            if modules["missing_manifests"]:
                gaps.append(f"reactor manifest missing: {sample(modules['missing_manifests'])}")
            if modules["unparsable_manifests"]:
                gaps.append(
                    f"reactor manifest unparsable: {sample(modules['unparsable_manifests'])}")
            if modules["unsupported_manifests"]:
                gaps.append(
                    "reactor manifest of an unsupported kind: "
                    f"{sample(modules['unsupported_manifests'])}")
            # The counter-method: what the tree holds beside each manifest,
            # against what the manifest declares.
            siblings = sibling_modules(repo, poms)
            tree_query = note(f"list the directories beside {', '.join(poms)}",
                              "directories holding a manifest of their own",
                              len(siblings))
            # A listing that returned nothing tried nothing: there was no
            # second reading of the tree to disagree with the parse.
            counter_checks.append({
                "method": "the module directories the tree holds beside the manifests",
                "kind": "deterministic", "targeted_claims": [claim_id], "new_nodes": [],
                "state": "complete" if siblings else "pending",
                "classes": ["B7"], "query_ids": [tree_query],
                **({} if siblings else
                   {"reason": "no module directory sits beside a declared manifest, so the "
                              "listing had nothing to weigh against the parse"}),
            })
            undeclared = [name for name in siblings if name not in modules["declared"]]
            undeclared_gap = (f"module directories no manifest declares: {sample(undeclared)}"
                              if undeclared else None)
            record("B7", "unverified" if gaps else ("partial" if undeclared_gap else "closed"),
                   " + ".join(["declared aggregator manifests parsed",
                               "the module directories beside them", *extra_method]),
                   extra_hits, reasons=[*gaps, undeclared_gap, site_gap], mechanism=mechanism,
                   modules=modules, sites=live_sites or None,
                   query_ids=[parse_query, *extra_qids],
                   universe=", ".join(["declared aggregator manifests", *extra_universes]))
            continue

        if klass == "B14":
            # A submodule is its own checkout; the inventory never descends into it.
            submodules = ("; submodules are separate checkouts and were not searched"
                          if (repo / ".gitmodules").exists() else "")
            record("B14", "frontier",
                   " + ".join(["outside this repository", *extra_method]), extra_hits,
                   reasons=["another repository, deployment manifest, or live consumer"
                            + submodules, site_gap],
                   mechanism=mechanism, sites=live_sites or None, query_ids=extra_qids,
                   universe=", ".join(["nothing in this repository", *extra_universes]))
            continue

        hits: list[dict] = list(extra_hits)
        methods: list[str] = list(extra_method)
        universes: list[str] = list(extra_universes)
        qids: list[str] = list(extra_qids)
        language_gap = None

        if default and scoped == "filter":
            specs = default["paths"]
            hits += [hit for hit in b1_hits if matches_any(hit["file"], specs)]
            methods.append(default["method"])
            universes.append("name-form hits filtered to paths")
            qids += b1_query_ids
            b1_derived.append(klass)
        elif default and default.get("patterns"):
            wanted = default.get("languages")
            if wanted and not (suffixes & set(wanted)):
                language_gap = (f"pattern cannot match: no {default['language_label']} files "
                                f"({', '.join(wanted[:4])})")
            else:
                expressions = [expand(pattern, group(subject_terms),
                                      bounded_group(subject_terms))
                               for pattern in default["patterns"]]
                keep = named_files if scoped == "registration" else None
                primary_extra = []
                universe = ("files that name the subject" if scoped == "registration"
                            else "tracked files")
                if keep is not None and not keep:
                    # No file names the subject, so this class searches an empty
                    # universe: what B1 ran is the proof it is empty, and B1's
                    # counter-search covers the classes that inherit its set.
                    qids += b1_query_ids
                    b1_derived.append(klass)
                    methods.append(default["method"])
                    universes.append("no file names the subject")
                else:
                    found, class_ids = search(
                        expressions, sorted(keep) if keep is not None else None,
                        universe, primary_extra)
                    qids += class_ids
                    hits += found
                    if scoped == "registration":
                        qids += b1_query_ids
                    extra, _ = counter_pass(
                        klass, expressions, None,
                        {(hit["file"], hit["line"]) for hit in found}, keep,
                        primary_extra=primary_extra)
                    hits += extra
                    methods.append(default["method"])
                    universes.append(universe)

        inherited = (f"universe inherits B1: {b1_gap}") if (inherits_b1 and b1_gap) else None
        common = {"mechanism": mechanism,
                  "universe": ", ".join(universes) or "no method ran",
                  "query_ids": qids, "sites": live_sites or None}
        method = " + ".join(methods) or "none"

        # A live site is a method too, so a class carrying only one is not an
        # absence. `record` folds the site statuses in; this picks the base.
        if not methods and not live_sites and language_gap:
            record(klass, "unverified", "default pattern only", hits,
                   reasons=[language_gap, site_gap], **common)
        elif not methods and not live_sites:
            record(klass, "unverified", "no default and no declared instance", hits,
                   reasons=["no enumeration method", site_gap], **common)
        else:
            # A default pattern that cannot match any file kind here is a
            # method that did not run, even where a declared one did.
            record(klass, "partial" if (inherited or language_gap) else "closed",
                   method, hits,
                   reasons=[f"a site an agent reads: {', '.join(live_sites)}"
                            if live_sites else None,
                            site_gap, inherited, language_gap], **common)

    for check in inherited_checks:
        check["classes"] = ["B1", *b1_derived]

    # A query's count is what it put in the nodes table. A raw hit that no class
    # kept is not a node, and a count above the nodes citing it would be a row
    # nobody can check against the table.
    node_rows = ledger.rows()
    produced: dict[str, int] = {}
    for node in node_rows:
        if isinstance(node.get("query_id"), str):
            produced[node["query_id"]] = produced.get(node["query_id"], 0) + 1
    for key, row in queries.items():
        row["count"] = produced.get(key, 0)

    return {
        "run": {
            "repository": str(repo),
            "head": head,
            "question": question,
            "type": qtypes,
            "roots": subjects,
            "aliases": {subject: forms[subject] for subject in subjects},
            "inventory_hash": inventory_hash,
            "inventory_count": len(inventory),
            "config": config_stamp,
            "design_phase": design_phase,
            "started": started,
            "finished": datetime.now(timezone.utc).isoformat(),
        },
        "boundaries": [boundaries[klass] for klass in ALL_CLASSES],
        "nodes": node_rows,
        "queries": [queries[key] for key in queries],
        "claims": [{
            "id": claim_id,
            "text": claim_text,
            "kind": "unverified",
            "load_bearing": False,
            "supporting_nodes": [],
            "citations": [],
        }],
        "counter_checks": counter_checks,
    }


def parse_alias(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            "an alias is written FORM=VALUE, for example wire=order-created")
    form, value = raw.split("=", 1)
    if not form.strip() or not value.strip():
        raise argparse.ArgumentTypeError("an alias needs both a form and a value")
    return form.strip(), value.strip()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True, description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--subject", action="append", required=True)
    parser.add_argument("--type", action="append", required=True,
                        choices=[f"Q{n}" for n in range(1, 6)])
    parser.add_argument("--question")
    parser.add_argument("--alias", action="append", type=parse_alias, default=[])
    parser.add_argument("--config", default="auto")
    parser.add_argument("--design-phase", action="store_true",
                        help="this run feeds a design decision, not a report")
    parser.add_argument("--out", required=True)
    parser.add_argument("--traceback", action="store_true",
                        help="print the traceback of an unexpected failure")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        sys.stderr.write(f"seed_map: {repo} is not a git repository\n")
        return 2

    question = args.question or "seed map for " + ", ".join(args.subject)
    try:
        block, config_stamp = load_config(repo, args.config)
        warnings = block_warnings(block)
        for warning in warnings:
            sys.stderr.write(f"seed_map: {warning}\n")
        result = seed(repo, args.subject, args.type, question, args.alias, block,
                      config_stamp, args.design_phase)
        # A pattern that matches everything returns hits that are not about the
        # subject; the record says so, so a reader can triage them last.
        if warnings:
            result["run"]["config_warnings"] = warnings
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except ConfigError as problem:
        sys.stderr.write(f"seed_map: the effective configuration is not valid: {problem}\n")
        return 2
    except GitError as problem:
        sys.stderr.write(f"seed_map: {problem}\n")
        return 2
    except SeedTooWide as problem:
        sys.stderr.write(f"seed_map: {problem}\n")
        return 2
    except Exception as problem:  # an unexpected failure is an error, never a half-run
        if args.traceback:
            traceback.print_exc()
        sys.stderr.write(f"seed_map: error: {type(problem).__name__}: {problem}\n")
        return 2

    rows = result["boundaries"]
    closed = sum(1 for row in rows if row["status"] == "closed")
    unverified = sum(1 for row in rows if row["status"] == "unverified")
    sys.stdout.write(
        f"seed_map: {closed}/14 classes enumerated, {unverified} without a method, "
        f"{sum(row['hits'] for row in rows)} hits, {len(result['nodes'])} nodes -> {out}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
