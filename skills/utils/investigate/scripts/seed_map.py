#!/usr/bin/env python3
"""Seed map: the deterministic pre-pass of a code investigation.

Enumerates the search space for one subject over the boundary classes
`INVESTIGATION.md` (plugin root) owns, so an agent spends tokens on judgment
and never on enumeration. It seeds an investigation; it never claims semantic
reachability, and it never writes into the repository it reads.

Usage:
  seed_map.py --repo ROOT --subject NAME [--subject NAME ...] --type Q1..Q5
              [--config auto|PATH] --out FILE.json

Boundary instances come from the `investigation:` block of the repository's
`.afk/config.yaml`, read through `scripts/afk-config.py` (the one reader).
Absent block: the generic defaults below run alone, and every class with
neither a default nor a declared instance is reported
`unverified(no enumeration method)` — never as an absence.

Subprocess budget: one `git ls-files`, one `git grep` for every name form, and
at most one `git grep` per boundary class that needs its own patterns. A spawn
costs 0.5-2s on this platform (`hooks/README.md` cost model), so patterns are
alternated into one expression per class and classified in Python.

Exit codes: 0 wrote the seed map, 2 usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[4]

# Generic default patterns, one entry per class that has one. Framework-shaped
# and product-free: a repository's own mechanisms belong in its `investigation:`
# block, never here. `{simple}` expands to the subject's simple name.
#
# `scoped` says how a class's hits are found:
#   "subject"  - the pattern already carries the subject's name
#   "registration" - the pattern finds a registration form, so the query is
#                    restricted to the files a name form already hit; a
#                    registration in a file that never names the subject is
#                    B2/B3 work for the tracer, not a textual hit
#   "filter"   - no query of its own; the name-form hits filtered to pathspecs
DEFAULTS: dict[str, dict] = {
    "B1": {"scoped": "names", "method": "every name form, whole repository"},
    "B2": {
        "scoped": "subject",
        "patterns": [r"(extends|implements)[^;{{]*\b{simple}\b", r"\(\s*{simple}\s+\w"],
        "method": "declaration and parameter forms carrying the name",
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

# How many hits a boundary row carries. The count above it stays exact.
HIT_SAMPLE = 200


def load_config(repo: Path, where: str) -> dict:
    """Read the `investigation:` block through the plugin's one config reader."""
    spec = importlib.util.spec_from_file_location(
        "afk_config", PLUGIN_ROOT / "scripts" / "afk-config.py"
    )
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if where == "auto":
        config = module.load(repo)
    else:
        path = Path(where)
        config = module.deep_merge(
            dict(module.DEFAULTS), module.parse(path.read_text(encoding="utf-8"), str(path))
        )
    block = config.get("investigation")
    return block if isinstance(block, dict) else {}


def name_forms(subject: str) -> list[dict]:
    """Every form the subject can be written in, each labelled.

    An import alias is repository-local and cannot be derived from the name
    alone, so it is recorded as not enumerated rather than assumed absent.
    """
    simple = subject.rsplit(".", 1)[-1]
    forms = [{"form": "simple", "value": simple, "enumerated": True}]
    if "." in subject:
        forms.append({"form": "qualified", "value": subject, "enumerated": True})
    forms.append({"form": "string-literal", "value": f'"{simple}"', "enumerated": True})
    forms.append(
        {
            "form": "import-alias",
            "value": None,
            "enumerated": False,
            "reason": "an alias is chosen at the importing site; not derivable from the name",
        }
    )
    return forms


def git(repo: Path, *args: str) -> tuple[int, str]:
    done = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        errors="replace",
    )
    return done.returncode, done.stdout


def grep(repo: Path, patterns: list[str], pathspecs: list[str] | None) -> list[dict]:
    """One `git grep` for a whole class. Exit 1 means no match, not failure."""
    if not patterns:
        return []
    args = ["grep", "-n", "-I", "-E", "--no-color"]
    for pattern in patterns:
        args += ["-e", pattern]
    if pathspecs:
        args += ["--", *pathspecs]
    code, out = git(repo, *args)
    if code not in (0, 1):
        return []
    hits = []
    for line in out.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3 or not parts[1].isdigit():
            continue
        hits.append({"file": parts[0], "line": int(parts[1]), "text": parts[2].strip()[:200]})
    return hits


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
    reported rather than dropped.
    """
    declared: list[str] = []
    commented: list[str] = []
    missing: list[str] = []
    for pom in poms:
        target = repo / pom
        if not target.is_file():
            missing.append(pom)
            continue
        text = target.read_text(encoding="utf-8", errors="replace")
        for comment in re.findall(r"<!--(.*?)-->", text, re.S):
            commented += [m.strip() for m in re.findall(r"<module>(.*?)</module>", comment, re.S)]
        stripped = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        try:
            root = ElementTree.fromstring(stripped)
        except ElementTree.ParseError:
            declared += [m.strip() for m in re.findall(r"<module>(.*?)</module>", stripped, re.S)]
            continue
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] == "module" and node.text:
                declared.append(node.text.strip())
    return {"declared": declared, "commented_out": commented, "missing_manifests": missing}


def build_class_map(block: dict) -> dict[str, list[dict]]:
    """Declared instances, grouped by the class each names."""
    grouped: dict[str, list[dict]] = {}
    for entry in block.get("boundaries") or []:
        if isinstance(entry, dict) and entry.get("class"):
            grouped.setdefault(entry["class"], []).append(entry)
    return grouped


def seed(repo: Path, subjects: list[str], qtype: str, block: dict) -> dict:
    forms = {subject: name_forms(subject) for subject in subjects}
    searchable = [
        form["value"]
        for subject_forms in forms.values()
        for form in subject_forms
        if form["enumerated"] and form["value"]
    ]
    simple_names = [subject.rsplit(".", 1)[-1] for subject in subjects]

    code, listing = git(repo, "ls-files")
    inventory = listing.splitlines()
    inventory_hash = hashlib.sha256(listing.encode("utf-8", "replace")).hexdigest()

    queries: list[dict] = []
    declared = build_class_map(block)

    # B1 first: its hit set is the file universe every registration-form query
    # is restricted to, so the whole pass costs one extra spawn, not one per class.
    name_patterns = [re.escape(value) for value in searchable]
    b1_hits = grep(repo, name_patterns, None)
    queries.append(
        {
            "command": "git grep -n -I -E <name forms>",
            "universe": "tracked files",
            "count": len(b1_hits),
            "evidence": None,
        }
    )
    named_files = sorted({hit["file"] for hit in b1_hits})

    # Which hits only a non-primary name form found: the free counter-check.
    primary = re.compile("|".join(re.escape(name) for name in simple_names)) if simple_names else None
    secondary_only = [
        hit for hit in b1_hits if primary is not None and not primary.search(hit["text"])
    ]

    boundaries: dict[str, dict] = {}

    def record(klass: str, status: str, method: str, hits: list[dict], **extra) -> None:
        # The count is the fact; the hit list is the sample an agent starts from.
        # A mechanism-wide pattern can return thousands, and a ledger nobody can
        # open is a ledger nobody reads — so the count stays exact and the list
        # is capped, saying so.
        row = {
            "class": klass,
            "status": status,
            "method": method,
            "count": len(hits),
            "truncated": len(hits) > HIT_SAMPLE,
            "hits": hits[:HIT_SAMPLE],
        }
        row.update(extra)
        boundaries[klass] = row

    for klass in ALL_CLASSES:
        instances = declared.get(klass, [])
        default = DEFAULTS.get(klass)

        judgment_sites = [i["site"] for i in instances if i.get("judgment-only") and i.get("site")]
        patterns = [i["pattern"] for i in instances if i.get("pattern")]
        paths = [p for i in instances for p in (i.get("paths") or [])]
        mechanism = ", ".join(i.get("name", "?") for i in instances) or "default"

        if klass == "B1":
            record(
                "B1",
                "closed",
                default["method"],
                b1_hits,
                mechanism=mechanism,
                name_forms={s: forms[s] for s in subjects},
            )
            continue

        if klass == "B6":
            generated = block.get("generated") or []
            if not generated:
                record("B6", "unverified", "no generated paths declared", [],
                       mechanism=mechanism, reason="no enumeration method")
                continue
            absent = [g for g in generated if not (repo / g).exists()]
            if absent:
                record("B6", "frontier", "declared generated paths", [], mechanism=mechanism,
                       reason=f"unbuilt: {', '.join(absent)}")
                continue
            hits = grep(repo, name_patterns, generated)
            queries.append({"command": "git grep -n -I -E <name forms> -- <generated>",
                            "universe": "declared generated output", "count": len(hits),
                            "evidence": None})
            record("B6", "closed", "name forms in built generated output", hits, mechanism=mechanism)
            continue

        if klass == "B7":
            poms = block.get("reactor") or []
            if not poms:
                record("B7", "unverified", "no reactor manifests declared", [],
                       mechanism=mechanism, reason="no enumeration method")
                continue
            modules = reactor_modules(repo, poms)
            record("B7", "closed", "declared aggregator manifests parsed", [],
                   mechanism=mechanism, modules=modules)
            continue

        if klass == "B14":
            record("B14", "frontier", "outside this repository", [], mechanism=mechanism,
                   reason="another repository, deployment manifest, or live consumer")
            continue

        if judgment_sites and not patterns:
            record(klass, "judgment-only", "a site an agent reads", [], mechanism=mechanism,
                   sites=judgment_sites)
            continue

        if default and default["scoped"] == "filter" and not patterns:
            specs = paths or default["paths"]
            hits = [hit for hit in b1_hits if matches_any(hit["file"], specs)]
            record(klass, "closed", default["method"], hits,
                   mechanism=mechanism, pathspecs=specs)
            continue

        expressions: list[str] = list(patterns)
        restrict = paths or None
        if default and not patterns:
            expressions = [
                pattern.format(simple="|".join(re.escape(n) for n in simple_names))
                if "{simple}" in pattern
                else pattern
                for pattern in default["patterns"]
            ]
            if default["scoped"] == "registration":
                restrict = named_files or ["nothing-matched"]
        elif patterns and default and default["scoped"] == "registration":
            restrict = restrict or named_files or ["nothing-matched"]

        if not expressions:
            record(klass, "unverified", "no default and no declared instance", [],
                   mechanism=mechanism, reason="no enumeration method")
            continue

        hits = grep(repo, expressions, restrict)
        universe = ("files that name the subject" if restrict is named_files
                    else "declared paths" if restrict else "tracked files")
        queries.append({"command": f"git grep -n -I -E <{klass} patterns>",
                        "universe": universe, "count": len(hits), "evidence": None})
        method = default["method"] if (default and not patterns) else "declared instance patterns"
        record(klass, "closed", method, hits, mechanism=mechanism, universe=universe,
               sites=judgment_sites or None)

    return {
        "run": {
            "repository": str(repo),
            "roots": subjects,
            "type": qtype,
            "aliases": {s: forms[s] for s in subjects},
            "inventory_hash": inventory_hash,
            "inventory_count": len(inventory),
            "config": "declared" if block else "defaults only",
        },
        "boundaries": [boundaries[klass] for klass in ALL_CLASSES],
        "queries": queries,
        "counter_checks": [
            {
                "method": "second name form",
                "targeted_claims": [],
                "new_nodes": [f"{h['file']}:{h['line']}" for h in secondary_only],
                "state": "complete",
            }
        ],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True, description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--subject", action="append", required=True)
    parser.add_argument("--type", required=True, choices=[f"Q{n}" for n in range(1, 6)])
    parser.add_argument("--config", default="auto")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        sys.stderr.write(f"seed_map: {repo} is not a git repository\n")
        return 2

    try:
        block = load_config(repo, args.config)
    except Exception as problem:  # a broken config must not read as "no boundaries"
        sys.stderr.write(f"seed_map: could not read the investigation block: {problem}\n")
        return 2

    result = seed(repo, args.subject, args.type, block)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    closed = sum(1 for row in result["boundaries"] if row["status"] == "closed")
    unverified = sum(1 for row in result["boundaries"] if row["status"] == "unverified")
    sys.stdout.write(
        f"seed_map: {closed}/14 classes enumerated, {unverified} without a method, "
        f"{sum(row['count'] for row in result['boundaries'])} hits -> {out}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
