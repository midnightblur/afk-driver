"""Each round has its own colour, and every chip that names a round shows it: a card, a card's history, the banner,
the notes table and a map box (shell/rounds.py). A muted chip keeps the fill, and the chip text stays readable on
every round's fill in both themes."""

import colorsys
import json
import re
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
for folder in (PLUGIN / "scripts", ENGINE_DIR, Path(__file__).resolve().parent):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
from shell import page, rounds  # noqa: E402
from test_page_parts_v2 import document  # noqa: E402

CHIP_CLASS = "afkv2-round-chip"
CHIP = re.compile(r'<span class="' + CHIP_CLASS + r'([^"]*)"( style="[^"]*")?[^>]*>(?:R-|Round )(\d+)</span>')
COLOUR = re.compile(r"--afkv2-round: ([^;\"]+)")
HSL = re.compile(r"hsl\(([0-9.]+), ([0-9.]+)%, ([0-9.]+)%\)")
CHIP_TEXT = "#111418"
AA_TEXT = 4.5
KIT = (ENGINE_DIR / "shell" / "kit.css").read_text("utf-8")
PAGE_FIXTURES = ["v0-page-with-notes.json", "v0-sdd-pass.json"]
HISTORY = re.compile(r'<details class="afkv2-history".*?</details>', re.S)
PAST_RULE = re.compile(r"\.afkv2-round-chip--past \{([^}]*)\}")
BASE_RULE = re.compile(r"\.afkv2-round-chip \{([^}]*)\}")
FILL = "background: var(--afkv2-round"
MUTED_AND_MAP = {"afkv2-round-chip--past", "afkv2-node-round"}


def fixture(name):
    raw = json.loads((FIXTURES / name).read_text("utf-8"))
    return engine.READERS[raw["schema"]](raw)


def chips(html):
    """(classes, colour or None, round number) of every round chip on the page."""
    found = []
    for classes, style, n in CHIP.findall(html):
        colour = COLOUR.search(style or "")
        found.append((classes.split(), colour and colour.group(1), int(n)))
    return found


@pytest.mark.parametrize("name", ["format 2", *PAGE_FIXTURES])
def test_every_round_chip_carries_the_colour_of_its_own_round(name):
    doc = document() if name == "format 2" else fixture(name)
    html = page.build(doc)
    colours = {r["n"]: page.round_colour(r) for r in doc["rounds"]}
    found = chips(html)
    assert len(found) == html.count(f'class="{CHIP_CLASS}'), "a chip the pattern cannot read"
    assert {n for _, _, n in found} == set(colours)
    wrong = [(n, colour) for _, colour, n in found if colour != colours[n]]
    assert not wrong, wrong


def test_muted_chips_and_map_labels_are_round_chips_too():
    classes = {word for found, _, _ in chips(page.build(fixture("v0-page-with-notes.json"))) for word in found}
    assert MUTED_AND_MAP <= classes


def test_an_earlier_card_in_a_later_cards_history_keeps_its_own_round_colour():
    html = page.build(fixture("v0-page-with-notes.json"))
    found = [chip for history in HISTORY.findall(html)
             for chip in chips(history)]
    assert found and all(colour == rounds.colour_of(n) for _, colour, n in found), found


def test_a_muted_chip_keeps_the_fill_of_its_round():
    rule = PAST_RULE.search(KIT).group(1)
    assert "background" not in rule and "color" not in rule
    base = BASE_RULE.search(KIT).group(1)
    assert FILL in base and f"color: {CHIP_TEXT}" in base


def test_the_chip_colour_is_stable_and_differs_between_neighbouring_rounds():
    hues = [rounds.colour_of(n) for n in range(1, 13)]
    assert hues == [rounds.colour_of(n) for n in range(1, 13)] and len(set(hues)) == 12
    assert rounds.round_colour({"n": 3, "colour": "tomato"}) == "tomato"


def _luminance(rgb):
    channel = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * channel[0] + 0.7152 * channel[1] + 0.0722 * channel[2]


def _contrast(a, b):
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_the_chip_text_is_readable_on_every_round_fill():
    """The fill and the text are fixed colours, so the contrast is the same in the light and the dark theme."""
    text = tuple(int(CHIP_TEXT[i:i + 2], 16) / 255 for i in (1, 3, 5))
    for n in range(1, 101):
        hue, saturation, lightness = map(float, HSL.fullmatch(rounds.colour_of(n)).groups())
        fill = colorsys.hls_to_rgb(hue / 360, lightness / 100, saturation / 100)
        assert _contrast(fill, text) >= AA_TEXT, n
