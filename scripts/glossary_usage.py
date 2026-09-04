#!/usr/bin/env python3
"""Report glossary terms that no file in the plugin uses.

A heading is written for a reader, not for a grep. Readers write `sign-off` in a
sentence and `Sign-off` in a heading; one heading often heads several terms, and
a trailing parenthetical says which variants the entry covers rather than naming
part of the term. So the heading string is normalized into the terms a consumer
would actually type, and every one of them must appear somewhere.

A zero-hit term means no file in the plugin uses that word. It does not mean the
term is wrong, or that the entry should go: an entry a reader needs and no file
happens to mention is fine. It is a prompt to look, not a verdict.

Exit status is 0 whether or not terms are unused; this reports, it does not gate.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^\*\*(`?)([^*`]+?)\1\*\*(?:\s*\(([^)]*)\))?\s*:", re.M)
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".ico", ".woff", ".woff2"}

# Files that name a term in order to talk about this check, rather than using
# the vocabulary. Counting them makes the check blind to exactly the terms it
# most recently reported: name one in a test fixture or a release note, and it
# has a consumer forever after. Both of these did that to `One-live-fixer
# invariant` the day the check shipped.
NOT_A_CONSUMER = {"CHANGELOG.md", "scripts/tests/test_glossary_usage.py"}


def terms_of(heading: str, qualifier: str | None = None) -> list[str]:
    """The terms a consumer would type, given a glossary heading.

    Splits a heading that heads several terms, drops a trailing parenthetical
    qualifier, and folds case. A qualifier that is itself a term list (`lean /
    full`) contributes nothing on its own: those words are modifiers, not terms.
    """
    bare = re.sub(r"\s*\([^)]*\)\s*", " ", heading).strip()
    out = []
    for part in bare.split("/"):
        part = part.strip()
        if part:
            out.append(part.casefold())
    return list(dict.fromkeys(out))


def parse(glossary: str) -> dict[str, list[str]]:
    """Map each heading to the terms it defines, in file order."""
    found: dict[str, list[str]] = {}
    for m in HEADING.finditer(glossary):
        heading = m.group(2).strip()
        found.setdefault(heading, terms_of(heading, m.group(3)))
    return found


def used(term: str, files: list[Path]) -> bool:
    needle = term.casefold()
    for f in files:
        try:
            if needle in f.read_text(encoding="utf-8", errors="ignore").casefold():
                return True
        except OSError:
            continue
    return False


def consumers(root: Path, glossary: Path) -> list[Path]:
    out = []
    for p in root.rglob("*"):
        if not p.is_file() or p == glossary:
            continue
        if p.suffix.lower() in SKIP_SUFFIXES:
            continue
        rel = p.relative_to(root)
        if SKIP_DIRS.intersection(rel.parts):
            continue
        if rel.as_posix() in NOT_A_CONSUMER:
            continue
        out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".", help="plugin root (default: .)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    glossary = root / "GLOSSARY.md"
    if not glossary.is_file():
        print("no GLOSSARY.md under %s" % root, file=sys.stderr)
        return 2

    headings = parse(glossary.read_text(encoding="utf-8"))
    files = consumers(root, glossary)

    unused = []
    for heading, parts in headings.items():
        missing = [t for t in parts if not used(t, files)]
        if missing:
            unused.append((heading, missing))

    print("%d headings, %d terms, %d file(s) searched"
          % (len(headings), sum(len(v) for v in headings.values()), len(files)))
    if not unused:
        print("every term has at least one consumer")
        return 0
    print("\nno consumer found for:")
    for heading, missing in unused:
        print("  %s -> %s" % (heading, ", ".join(missing)))
    print("\nA zero-hit term is a prompt to look, not a verdict: check whether the "
          "term is spelled differently in prose before changing GLOSSARY.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
