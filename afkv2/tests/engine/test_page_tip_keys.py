"""Glossary keys of the tooltip layer: a `(token)` qualifier never becomes a key of its own."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
from shell import inject


@pytest.mark.parametrize("term, keys", [
    ("Order Queue", ["order queue"]),
    ("Queue", ["queue"]),
    ("Purchase Order (PO)", ["purchase order", "PO"]),
    ("Merge Requests (MRs)", ["merge requests", "MRs"]),
    ("Source of Truth (SoT)", ["source of truth", "SoT"]),
    ("Order file (`ORDERS.md`)", ["order file", "ORDERS.md"]),
    ("Pull request / PR", ["pull request", "PR"]),
    ("S1-S5 (order states)", ["S1-S5"]),
    ("Shipped Amount (order)", ["shipped amount"]),
    ("Display ID (SHOP)", ["display ID"]),
])
def test_an_alias_gives_a_key_and_a_qualifier_does_not(term, keys):
    assert inject.keys_for(term) == keys


@pytest.mark.parametrize("term", ["Retry (action)", "Open (basket)", "Currency (SHOP)", "Archive (page)"])
def test_a_qualified_common_word_gives_no_key(term):
    """A word such as `action` or `open` on a page rarely carries the meaning its qualifier narrows."""
    assert inject.keys_for(term) == []


def test_a_qualifier_does_not_take_the_tooltip_of_a_common_word(tmp_path):
    glossary = tmp_path / "GLOSSARY.md"
    glossary.write_text("**Retry (action)**:\nThe manual action that sends one order again.\n\n"
                        "**Currency (SHOP)**:\nThe shop's own currency.\n\n"
                        "**Purchase Order (PO)**:\nA buyer's order to a seller.\n", "utf-8")
    tips = inject.parse_glossary(glossary)
    assert "action" not in tips and "retry" not in tips
    assert "SHOP" not in tips and "currency" not in tips
    assert tips["PO"] == tips["purchase order"] == "A buyer's order to a seller."
