from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from glossary_lifecycle.markdown import (  # noqa: E402
    AliasCollisionError,
    DuplicateTermIdError,
    GlossaryMarkdownCodec,
    MissingIdentityError,
    ReplacementCycleError,
    UnresolvedReplacementError,
)
from lavish import inject  # noqa: E402


ADOPTED = """\
# Payable glossary

**Invoice** (vendor invoice / supplier invoice):
Money owed to a supplier after delivery.
_ID_: payable.invoice
_Owner_: payable-team
_Also_: invoice document
_Replaces_: legacy.invoice
_Code_: Invoice
_Related_: Purchase order
_Avoid_: bill

**Legacy invoice**:
The former invoice concept.
_ID_: legacy.invoice
_Owner_: payable-team
"""


def test_adopted_markdown_round_trips_stable_identity_and_aliases() -> None:
    codec = GlossaryMarkdownCodec()
    parsed = codec.parse(ADOPTED)

    invoice = parsed.by_id["payable.invoice"]
    assert invoice.canonical_term == "Invoice"
    assert invoice.aliases == ("vendor invoice", "supplier invoice", "invoice document")
    assert invoice.replaces == ("legacy.invoice",)
    assert invoice.owner == "payable-team"
    assert invoice.code == "Invoice"
    assert invoice.related == ("Purchase order",)
    assert invoice.avoid == ("bill",)
    assert codec.parse(codec.serialize(parsed)) == parsed


def test_adopted_tooltip_dictionary_matches_explicit_corpus() -> None:
    codec = GlossaryMarkdownCodec()

    expected = {
        "invoice": "Money owed to a supplier after delivery.",
        "vendor invoice": "Money owed to a supplier after delivery.",
        "supplier invoice": "Money owed to a supplier after delivery.",
        "invoice document": "Money owed to a supplier after delivery.",
        "legacy invoice": "The former invoice concept.",
    }
    assert codec.tooltip_dictionary(ADOPTED) == expected


def test_aliases_with_slash_and_comma_survive_round_trip() -> None:
    text = ADOPTED.replace(
        "_Also_: invoice document",
        '_Also_: invoice document, read/write, "amount, net"',
    )
    codec = GlossaryMarkdownCodec()
    parsed = codec.parse(text)
    assert "read/write" in parsed.by_id["payable.invoice"].aliases
    assert "amount, net" in parsed.by_id["payable.invoice"].aliases
    assert codec.parse(codec.serialize(parsed)) == parsed


def test_legacy_tooltip_corpus_matches_the_existing_parser(tmp_path: Path) -> None:
    legacy = """\
**Gate**:
A check that blocks unsafe progress.
_Avoid_: pipeline

**Plan (delivery plan)**:
An ordered delivery contract.

**AFK / Full path — mode**:
A [workflow](https://example.invalid) with `code`.
"""
    path = tmp_path / "GLOSSARY.md"
    path.write_text(legacy, encoding="utf-8")

    assert GlossaryMarkdownCodec().tooltip_dictionary(legacy) == inject.parse_glossary(path)


@pytest.mark.parametrize(
    ("text", "error"),
    [
        (ADOPTED.replace("legacy.invoice\n_Owner_", "payable.invoice\n_Owner_"), DuplicateTermIdError),
        (ADOPTED.replace("_Replaces_: legacy.invoice", "_Replaces_: missing.invoice"), UnresolvedReplacementError),
        (ADOPTED.replace("**Legacy invoice**", "**Legacy invoice** (invoice)"), AliasCollisionError),
        (ADOPTED.replace("_ID_: payable.invoice\n", ""), MissingIdentityError),
        (
            ADOPTED.replace(
                "_ID_: legacy.invoice\n_Owner_: payable-team",
                "_ID_: legacy.invoice\n_Owner_: payable-team\n_Replaces_: payable.invoice",
            ),
            ReplacementCycleError,
        ),
    ],
)
def test_invalid_identity_and_alias_relationships_are_rejected(text: str, error: type[ValueError]) -> None:
    with pytest.raises(error):
        GlossaryMarkdownCodec().parse(text)
