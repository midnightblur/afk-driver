"""Pins the sixteen headings that the pre-1.0.6 glossary check reported as unused.

Every one of them was consumed at the time it was reported. The check compared a
heading's exact case, its trailing parenthetical qualifier and its slash-joined
term list against a tree where nobody writes it that way, so it reported
false positives and would have reported more as the glossary grew. These are
fixtures, not a snapshot of GLOSSARY.md: they must keep passing even after the
glossary is rewritten, because what they pin is the normalization, not the terms.

Where prose legitimately writes a shorter spelling than the heading, the entry
declares it under `_Also_:` and the check accepts it. `_Avoid_:` is the opposite
and never counts — see the two tests under "declared shorter spellings".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import glossary_usage as gu  # noqa: E402


def report(glossary_text, files):
    """Run the check over an in-memory glossary and consumer corpus."""
    headings = gu.parse(glossary_text)
    alternatives = gu.parse_alternatives(glossary_text)
    corpus = "\n".join(files).casefold()
    unused = {}
    for heading, parts in headings.items():
        alts = alternatives.get(heading, [])
        if alts and any(a in corpus for a in alts):
            continue
        missing = [t for t in parts if t not in corpus]
        if missing:
            unused[heading] = missing
    return unused


# ---------------------------------------------------------------- case folding

CASE_FIXTURES = [
    ("**Sign-off**:", "the reviewer records a sign-off on the ticket"),
    ("**Stranded**:", "a stranded subtask is one nobody can pick up"),
    ("**Decision point**:", "at each decision point the ledger gains a row"),
    ("**Decision ledger**:", "written to the decision ledger"),
    ("**Evidence bundle**:", "attach the evidence bundle"),
    ("**Adversary gate**:", "the adversary gate refused the claim"),
    ("**Grep-anchor**:", "leave a grep-anchor at the seam"),
    ("**Freshness registry**:", "the freshness registry names each owner"),
    ("**Tooltip dictionary**:", "the tooltip dictionary is rendered once"),
    ("**Feature terms file**:", "read the feature terms file first"),
    ("**Parked by inheritance**:", "the subtask is parked by inheritance"),
]


def test_a_term_used_in_lower_case_prose_is_not_reported():
    for heading, prose in CASE_FIXTURES:
        assert report(heading + "\nDefinition.\n", [prose]) == {}, heading


def test_case_folding_does_not_hide_a_genuinely_absent_term():
    assert report("**Sign-off**:\nDefinition.\n", ["nothing relevant here"])


# ------------------------------------------------- trailing qualifier stripped

def test_trailing_parenthetical_qualifier_is_not_part_of_the_term():
    g = "**Review policy (lean / full)**:\nDefinition.\n"
    assert report(g, ["the review policy for this repo is lean"]) == {}


def test_qualifier_words_alone_do_not_satisfy_the_term():
    g = "**Review policy (lean / full)**:\nDefinition.\n"
    assert report(g, ["lean and full are both fine"])


# ------------------------------------------------- multi-term heading is split

def test_a_heading_defining_two_terms_needs_a_consumer_for_each():
    g = "**Cited mode / uncited mode**:\nDefinition.\n"
    assert report(g, ["cited mode is the default", "uncited mode is rare"]) == {}
    half = report(g, ["cited mode is the default"])
    assert half and half["Cited mode / uncited mode"] == ["uncited mode"]


def test_slash_inside_a_qualifier_does_not_split_the_term():
    g = "**Grill-question triage (debate / confirm)**:\nDefinition.\n"
    assert report(g, ["grill-question triage runs first"]) == {}


# ------------------------------------------------- declared shorter spellings

def test_a_declared_shorter_spelling_satisfies_the_term():
    """Prose often writes a term's distinctive part and lets the sentence carry
    the rest: `one-live-fixer` inside a list of invariants. That is correct
    usage, so the entry declares it and the check accepts it."""
    g = ("**One-live-fixer invariant**:\n"
         "Definition.\n"
         "_Also_: one-live-fixer (prose names it inside a list of invariants)\n")
    prose = "Invariants 1-3 (capture-before-external, one-live-fixer, single-writer) hold"
    assert report(g, [prose]) == {}


def test_an_alternative_is_never_an_extra_requirement():
    """Declaring a spelling must not make the entry harder to satisfy."""
    g = "**Sign-off**:\nDefinition.\n_Also_: signoff\n"
    assert report(g, ["the reviewer records a sign-off"]) == {}
    assert report(g, ["the reviewer records a signoff"]) == {}
    assert report(g, ["nothing relevant"])


def test_a_parenthetical_on_the_also_line_is_not_part_of_the_spelling():
    g = "**Grep-anchor**:\nDefinition.\n_Also_: anchor (the short form, in seam prose)\n"
    assert gu.also_forms(g) == ["anchor"]
    assert report(g, ["leave an anchor at the seam"]) == {}


def test_avoid_lines_are_not_alternatives():
    """`_Avoid_:` lists the spellings nobody should use; counting one as a
    consumer would let a term be satisfied by the very drift it warns against."""
    g = "**Artifact registry**:\nDefinition.\n_Avoid_: freshness registry\n"
    assert gu.also_forms("Definition.\n_Avoid_: freshness registry\n") == []
    assert report(g, ["the freshness registry says"])


# --------------------------------------------------------------- parsing shape

def test_files_that_talk_about_the_check_are_not_consumers():
    """A term named in a release note or in this file is being discussed, not used.

    Counting them makes the check blind to exactly the terms it most recently
    reported: name one in a fixture, and it has a consumer forever after. That
    happened to `One-live-fixer invariant` the day the check shipped — this file
    and the 1.0.6 changelog entry both name it, and the check went quiet.
    """
    assert "scripts/tests/test_glossary_usage.py" in gu.NOT_A_CONSUMER
    assert "CHANGELOG.md" in gu.NOT_A_CONSUMER


def test_the_exclusion_is_by_exact_relative_path():
    """Never a suffix or basename match: a repository's own `CHANGELOG.md`
    under some other directory is ordinary prose and must still count."""
    for entry in gu.NOT_A_CONSUMER:
        assert not entry.startswith("*") and not entry.startswith("/"), entry
        assert "\\" not in entry, entry


def test_backticked_heading_is_read_as_its_term():
    assert gu.parse("**`pattern-debt`** (pattern debt):\nDefinition.\n") == {
        "pattern-debt": ["pattern-debt"]
    }


def test_terms_of_folds_case_and_drops_the_qualifier():
    assert gu.terms_of("Review policy (lean / full)") == ["review policy"]
    assert gu.terms_of("Cited mode / uncited mode") == ["cited mode", "uncited mode"]


# ------------------------------------------------------------- the live pin

def test_the_shipped_glossary_has_no_unconsumed_term():
    """The check must report zero against the tree it ships in.

    Unlike every fixture above, this one reads the real `GLOSSARY.md`, so it
    fails when a new entry lands with no consumer — which is the point. A
    failure here is not necessarily a bug in the check: read the reported term
    first, and if prose legitimately writes it shorter, declare that under
    `_Also_:` rather than loosening the rule.
    """
    root = Path(__file__).resolve().parents[2]
    glossary = root / "GLOSSARY.md"
    text = glossary.read_text(encoding="utf-8")
    headings = gu.parse(text)
    alternatives = gu.parse_alternatives(text)
    files = gu.consumers(root, glossary)

    unused = []
    for heading, parts in headings.items():
        alts = alternatives.get(heading, [])
        if alts and any(gu.used(a, files) for a in alts):
            continue
        if [t for t in parts if not gu.used(t, files)]:
            unused.append(heading)

    assert unused == [], "no consumer found for: %s" % ", ".join(unused)
