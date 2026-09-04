"""Pins the sixteen headings that the pre-1.0.6 glossary check reported as unused.

Every one of them was consumed at the time it was reported. The check compared a
heading's exact case, its trailing parenthetical qualifier and its slash-joined
term list against a tree where nobody writes it that way, so it reported
false positives and would have reported more as the glossary grew. These are
fixtures, not a snapshot of GLOSSARY.md: they must keep passing even after the
glossary is rewritten, because what they pin is the normalization, not the terms.

One of the sixteen is still reported, deliberately. See `test_trailing_category
_noun_is_still_reported` for what that costs and why it is not worked around.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import glossary_usage as gu  # noqa: E402


def report(glossary_text, files):
    """Run the check over an in-memory glossary and consumer corpus."""
    headings = gu.parse(glossary_text)
    corpus = "\n".join(files).casefold()
    unused = {}
    for heading, parts in headings.items():
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


# ------------------------------------------------------ the one still reported

def test_trailing_category_noun_is_still_reported():
    """`One-live-fixer invariant` is used as `one-live-fixer` in a list of
    invariants, the category noun factored out into the sentence. The check
    reports it.

    It is left reported on purpose. A rule that strips a trailing category noun
    would have to know which nouns are categories, and would then hide a term
    that really is unused whenever it ends in one of them. The check's own
    output says a zero-hit is a prompt to look rather than a verdict, and this
    is what looking is for. Fixing it in the glossary is not available either:
    the entry is correct as written.
    """
    g = "**One-live-fixer invariant**:\nDefinition.\n"
    prose = "Invariants 1-3 (capture-before-external, one-live-fixer, single-writer) hold"
    assert report(g, [prose]) == {"One-live-fixer invariant": ["one-live-fixer invariant"]}


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
