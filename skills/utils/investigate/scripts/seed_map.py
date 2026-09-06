#!/usr/bin/env python3
"""Seed map: the deterministic pre-pass of a code investigation.

Enumerates the search space for one subject over the boundary classes
`INVESTIGATION.md` (plugin root) owns, so an agent spends tokens on judgment
and never on enumeration. It seeds an investigation; it never claims semantic
reachability, and it never writes into the repository it reads.

Usage:
  seed_map.py --repo ROOT --subject NAME [--subject NAME ...]
              --type Q1..Q5 [--type ...] [--question TEXT]
              [--alias FORM=VALUE ...] [--config auto|PATH] --out FILE.json

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
name-form pass, and per boundary class one `git grep` per distinct path scope.
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
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timezone
from pathlib import Path

JVM = (".java", ".kt", ".kts", ".scala", ".groovy")
CURLY = JVM + (".ts", ".tsx", ".js", ".jsx", ".php", ".cs")
ANNOTATED = JVM + (".ts", ".py")

# Generic default patterns, one entry per class that has one. Framework-shaped
# and product-free: a repository's own mechanisms belong in its `investigation:`
# block, never here. `{simple}` expands to the subject's simple names, already
# grouped — a pattern embeds it as written.
#
# `scoped` says how a class's hits are found:
#   "names"        - the name-form passes themselves
#   "subject"      - the pattern already carries the subject's name
#   "registration" - the pattern finds a registration form; hits are kept only
#                    in files a name form already hit, intersected in-process
#   "filter"       - no query of its own; the name-form hits filtered to paths
#
# A "filter" or "registration" class searches B1's hit set, so it can be no more
# complete than B1 is.
#
# `languages` names the file kinds a default pattern can match in. A repository
# holding none of them gets `unverified(pattern cannot match)`, never closed(0).
DEFAULTS: dict[str, dict] = {
    "B1": {"scoped": "names", "method": "every name form, whole repository"},
    "B2": {
        "scoped": "subject",
        "patterns": [r"(extends|implements)[^;{{]*\b{simple}\b", r"\(\s*{simple}\s+\w"],
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

ALL_CLASSES = tuple(f"B{n}" for n in range(1, 15))

# How many nodes a boundary row carries. The count above it stays exact.
HIT_SAMPLE = 200

# How much of a matching line is stored as evidence. Matching happens on the
# whole line; only storage is capped.
EVIDENCE_CHARS = 200

# A generated file larger than this is output, not source, and is not read.
MAX_WALK_BYTES = 2 * 1024 * 1024

# How many skipped or missing paths a reason names before it says "and N more".
REASON_SAMPLE = 5

# The build-graph class parses aggregator manifests. Only XML is supported;
# anything else is reported, never guessed at (`CONFIG.md` § Investigation).
REACTOR_SUFFIXES = (".xml",)


class GitError(RuntimeError):
    """A git invocation failed for a reason that is not `no match`."""


class ConfigError(RuntimeError):
    """The effective configuration did not validate, or could not be read."""


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


def load_config(repo: Path, where: str) -> dict:
    """Read and validate the effective config through the one config reader."""
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
    else:
        path = Path(where)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as problem:
            raise ConfigError(f"cannot read {path}: {problem}") from problem
        config = module.deep_merge(dict(module.DEFAULTS), module.parse(text, str(path)))
    problems = module.validate(config, repo)
    if problems:
        raise ConfigError("; ".join(problems))
    block = config.get("investigation")
    return block if isinstance(block, dict) else {}


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
    """Whole matching lines. Comparison happens on the line, storage caps it."""
    hits = []
    for line in out.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3 or not parts[1].isdigit():
            continue
        hits.append({"file": parts[0], "line": int(parts[1]), "text": parts[2].strip()})
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
                    hits.append({"file": rel, "line": number, "text": line.strip()})
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


def site_present(repo: Path, inventory: set[str], site: str) -> bool:
    """A judgment-only site is evidence only while it exists on this snapshot."""
    normalized = site.strip().lstrip("./").rstrip("/")
    if normalized in inventory:
        return True
    if any(path.startswith(normalized + "/") for path in inventory):
        return True
    return (repo / normalized).exists()


def digest(prefix: str, text: str) -> str:
    """A key stable across partitions — an ordinal collides when fragments merge."""
    return prefix + "-" + hashlib.sha1(text.encode("utf-8", "surrogateescape")).hexdigest()[:8]


class Ledger:
    """The node table, and the ids the boundary rows point at."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}

    def add(self, klass: str, hits: list[dict], reason: str) -> list[str]:
        ids = []
        for hit in hits[:HIT_SAMPLE]:
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
                    "evidence": hit["text"][:EVIDENCE_CHARS],
                    "parent": None,
                },
            )
        return ids

    def rows(self) -> list[dict]:
        return [self.nodes[key] for key in sorted(self.nodes)]


def seed(repo: Path, subjects: list[str], qtypes: list[str], question: str,
         aliases: list[tuple[str, str]], block: dict) -> dict:
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

    def note(command: str, universe: str, count: int) -> None:
        row = {"id": digest("q", command + universe), "command": command,
               "universe": universe, "count": count, "evidence": None}
        queries.setdefault(row["id"], row)

    def carries_simple(value: str) -> bool:
        # Case-sensitive, because the primary pass is: a form the exact search
        # already returns is not a form the counter-search can learn from.
        return any(name in value for name in simple_names)

    every_form = [
        form for subject_forms in forms.values() for form in subject_forms
        if form["enumerated"] and form["value"]
    ]
    primary_values = [form["value"] for form in every_form if carries_simple(form["value"])]
    counter_values = [form["value"] for form in every_form if not carries_simple(form["value"])]
    declared_aliases = [form for form in every_form if form.get("source") == "declared"]
    unenumerated = sorted(
        {
            form["form"]
            for subject_forms in forms.values()
            for form in subject_forms
            if not form["enumerated"]
        }
    )

    # B1 first: its hit set is the universe every filter and registration class
    # searches, so those classes can be no more complete than it is. One call
    # covers both universes — the wide one (case-blind, untracked files
    # included) is split from the exact one in-process, so the second universe
    # costs no second walk of a large working tree.
    wide = grep(repo, [re.escape(value) for value in primary_values], None,
                extra=["-i", "--untracked"])
    exact = re.compile("|".join(re.escape(value) for value in primary_values))
    b1_hits = [hit for hit in wide
               if hit["file"] in inventory_set and exact.search(hit["text"])]
    kept = {(hit["file"], hit["line"]) for hit in b1_hits}
    wider_only = [hit for hit in wide if (hit["file"], hit["line"]) not in kept]
    note("git grep -n -I -E -i --untracked <primary name forms>",
         "tracked and untracked text files, not ignored, binary excluded, case-blind",
         len(wide))
    seen = set(kept)

    # Counter-search one: a name form that does not carry the simple name — a
    # form the primary pass provably cannot return.
    counter_checks: list[dict] = []
    claim_text = ("the hit set holds every reference to "
                  + ", ".join(subjects) + " over the name forms this pass searched")
    claim_id = digest("c", claim_text)
    if counter_values:
        form_hits = grep(repo, [re.escape(value) for value in counter_values], None)
        note("git grep -n -I -E <declared wire or alias forms>", "tracked files", len(form_hits))
        new = [hit for hit in form_hits if (hit["file"], hit["line"]) not in seen]
        b1_hits += new
        seen |= {(hit["file"], hit["line"]) for hit in new}
        counter_checks.append({
            "method": f"name forms carrying no simple name: {', '.join(counter_values)}",
            "kind": "deterministic", "targeted_claims": [claim_id],
            "new_nodes": ledger.add("B1", new, seed_reason), "state": "complete",
        })
    else:
        reason = ("alias contains simple name; the primary pass already covers it"
                  if declared_aliases
                  else "no wire or alias form declared; pass --alias FORM=VALUE")
        counter_checks.append({
            "method": "name form carrying no simple name",
            "kind": "deterministic", "targeted_claims": [claim_id], "new_nodes": [],
            "state": "pending", "reason": reason,
        })

    # Counter-search two: the second universe — case-blind, and including the
    # untracked files a tracked pass cannot see. Already searched above; what
    # the exact tracked pass could not have returned is its result.
    new = [hit for hit in wider_only if (hit["file"], hit["line"]) not in seen]
    b1_hits += new
    seen |= {(hit["file"], hit["line"]) for hit in new}
    counter_checks.append({
        "method": "case-blind pass over tracked and untracked files, not ignored",
        "kind": "deterministic", "targeted_claims": [claim_id],
        "new_nodes": ledger.add("B1", new, seed_reason), "state": "complete",
    })

    named_files = {hit["file"] for hit in b1_hits}
    b1_gap = (f"name forms not enumerated: {', '.join(unenumerated)}") if unenumerated else None
    boundaries: dict[str, dict] = {}

    def record(klass: str, status: str, method: str, hits: list[dict],
               reasons: list[str] | None = None, **extra) -> None:
        # The count is the fact; the node list is the sample an agent starts
        # from. A mechanism-wide pattern can return thousands, and a ledger
        # nobody can open is a ledger nobody reads — so the count stays exact
        # and the node list is capped, saying so.
        unique: list[dict] = []
        placed = set()
        for hit in hits:
            key = (hit["file"], hit["line"])
            if key not in placed:
                placed.add(key)
                unique.append(hit)
        row = {
            "class": klass,
            "status": status,
            "method": method,
            "hits": len(unique),
            "truncated": len(unique) > HIT_SAMPLE,
            "hit_ids": ledger.add(klass, unique, seed_reason),
        }
        reasons = [item for item in (reasons or []) if item]
        if reasons:
            row["reason"] = "; ".join(reasons)
        row.update(extra)
        boundaries[klass] = row

    def declared_searches(klass: str, instances: list[dict],
                          restrict_to_named: bool) -> tuple[list[dict], list[str]]:
        """Every declared pattern, each inside its own path scope.

        Patterns sharing a scope share one call, so a scope costs one spawn.
        """
        by_scope: dict[tuple[str, ...], list[str]] = {}
        for instance in instances:
            if instance.get("pattern"):
                by_scope.setdefault(tuple(instance.get("paths") or []), []).append(
                    instance["pattern"])
        hits: list[dict] = []
        universes: list[str] = []
        for scope, patterns in by_scope.items():
            found = grep(repo, patterns, list(scope) or None)
            if restrict_to_named:
                found = [hit for hit in found if hit["file"] in named_files]
            universe = f"declared paths {', '.join(scope)}" if scope else "tracked files"
            note(f"git grep -n -I -E <{klass} declared patterns>", universe, len(found))
            hits += found
            universes.append(universe)
        return hits, universes

    for klass in ALL_CLASSES:
        instances = declared.get(klass, [])
        default = DEFAULTS.get(klass)
        mechanism = ", ".join(instance.get("name", "?") for instance in instances) or "default"
        sites = [i["site"] for i in instances if i.get("judgment-only") and i.get("site")]
        missing_sites = [site for site in sites if not site_present(repo, inventory_set, site)]
        live_sites = [site for site in sites if site not in missing_sites]
        site_gap = f"site missing: {sample(missing_sites)}" if missing_sites else None
        scoped = (default or {}).get("scoped")
        inherits_b1 = scoped in ("filter", "registration")

        # A declared pattern runs beside whatever the class does on its own.
        extra_hits, extra_universes = declared_searches(
            klass, instances, restrict_to_named=(scoped == "registration"))
        extra_method = ["declared instance patterns"] if extra_hits or extra_universes else []

        if klass == "B1":
            record("B1", "partial" if b1_gap else "closed",
                   " + ".join([default["method"], *extra_method]), b1_hits + extra_hits,
                   reasons=[b1_gap, site_gap], mechanism=mechanism,
                   name_forms={s: forms[s] for s in subjects},
                   sites=live_sites or None,
                   universe="tracked text files (binary excluded), and the second universe")
            continue

        if klass == "B6":
            generated = block.get("generated") or []
            if not generated and not extra_hits:
                record("B6", "unverified", "no generated paths declared", extra_hits,
                       reasons=["no enumeration method", site_gap], mechanism=mechanism)
                continue
            absent = [path for path in generated if not (repo / path).exists()]
            present = [path for path in generated if (repo / path).exists()]
            searched = [form["value"] for form in every_form]
            hits, unread = walk_grep(repo, present, group(searched)) if present else ([], [])
            if present:
                note("in-process walk of the declared generated paths",
                     "built output, tracked or not", len(hits))
            unread_gap = f"{len(unread)} files unread: size or encoding — {sample(unread)}" \
                if unread else None
            if absent:
                status, reason = "frontier", f"unbuilt: {sample(absent)}"
            elif unread_gap or site_gap:
                status, reason = "partial", None
            else:
                status, reason = "closed", None
            record("B6", status,
                   " + ".join(["every name form in built generated output", *extra_method]),
                   hits + extra_hits, reasons=[reason, unread_gap, site_gap],
                   mechanism=mechanism, sites=live_sites or None)
            continue

        if klass == "B7":
            poms = block.get("reactor") or []
            if not poms and not extra_hits:
                record("B7", "unverified", "no reactor manifests declared", extra_hits,
                       reasons=["no enumeration method", site_gap], mechanism=mechanism)
                continue
            modules = reactor_modules(repo, poms)
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
            record("B7", "unverified" if gaps else "closed",
                   " + ".join(["declared aggregator manifests parsed", *extra_method]),
                   extra_hits, reasons=[*gaps, site_gap], mechanism=mechanism,
                   modules=modules, sites=live_sites or None)
            continue

        if klass == "B14":
            # A submodule is its own checkout; the inventory never descends into it.
            submodules = ("; submodules are separate checkouts and were not searched"
                          if (repo / ".gitmodules").exists() else "")
            record("B14", "frontier",
                   " + ".join(["outside this repository", *extra_method]), extra_hits,
                   reasons=["another repository, deployment manifest, or live consumer"
                            + submodules, site_gap],
                   mechanism=mechanism, sites=live_sites or None)
            continue

        hits: list[dict] = list(extra_hits)
        methods: list[str] = list(extra_method)
        universes: list[str] = list(extra_universes)
        language_gap = None

        if default and scoped == "filter":
            specs = default["paths"]
            hits += [hit for hit in b1_hits if matches_any(hit["file"], specs)]
            methods.append(default["method"])
            universes.append("name-form hits filtered to paths")
        elif default and default.get("patterns"):
            wanted = default.get("languages")
            if wanted and not (suffixes & set(wanted)):
                language_gap = (f"pattern cannot match: no {default['language_label']} files "
                                f"({', '.join(wanted[:4])})")
            else:
                expressions = [
                    pattern.format(simple=group(simple_names)) if "{simple}" in pattern else pattern
                    for pattern in default["patterns"]
                ]
                found = grep(repo, expressions, None)
                if scoped == "registration":
                    found = [hit for hit in found if hit["file"] in named_files]
                universe = ("files that name the subject" if scoped == "registration"
                            else "tracked files")
                note(f"git grep -n -I -E <{klass} default patterns>", universe, len(found))
                hits += found
                methods.append(default["method"])
                universes.append(universe)

        inherited = (f"universe inherits B1: {b1_gap}") if (inherits_b1 and b1_gap) else None
        common = {"mechanism": mechanism, "universe": ", ".join(universes) or None,
                  "sites": live_sites or None}
        method = " + ".join(methods) or "none"

        if live_sites:
            record(klass, "judgment-only", method, hits,
                   reasons=[f"a site an agent reads: {', '.join(live_sites)}",
                            site_gap, inherited], **common)
        elif not methods and language_gap:
            record(klass, "unverified", "default pattern only", hits,
                   reasons=[language_gap, site_gap], **common)
        elif not methods:
            record(klass, "unverified", "no default and no declared instance", hits,
                   reasons=["no enumeration method", site_gap], **common)
        elif site_gap or inherited:
            record(klass, "partial", method, hits, reasons=[site_gap, inherited], **common)
        else:
            record(klass, "closed", method, hits, **common)

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
            "config": "declared" if block else "defaults only",
            "started": started,
            "finished": datetime.now(timezone.utc).isoformat(),
        },
        "boundaries": [boundaries[klass] for klass in ALL_CLASSES],
        "nodes": ledger.rows(),
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
        block = load_config(repo, args.config)
        result = seed(repo, args.subject, args.type, question, args.alias, block)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except ConfigError as problem:
        sys.stderr.write(f"seed_map: the effective configuration is not valid: {problem}\n")
        return 2
    except GitError as problem:
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
