"""Each round has its own colour, and every chip that names a round shows it: a card, a card's history and its
summary, the banner, the notes table, a section's change lines and a map box (shell/rounds.py). A muted chip keeps
the fill, an old round fades by saturation on an opaque chip, and the chip text stays readable on every round's fill
at every fade, so in both themes."""

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
import registry  # noqa: E402
from shell import page, rounds  # noqa: E402
from test_page_parts_v2 import document  # noqa: E402

CHIP_CLASS = "afkv2-round-chip"
CHIP = re.compile(r'<span class="' + CHIP_CLASS + r'([^"]*)"( style="[^"]*")?[^>]*>(?:R-|[Rr]ound )(\d+)</span>')
COLOUR = re.compile(r"--afkv2-round: ([^;\"]+)")
HSL = re.compile(r"hsl\(([0-9.]+), ([0-9.]+)%, ([0-9.]+)%\)")
CHIP_TEXT = "#111418"
AA_TEXT = 4.5
KIT = (ENGINE_DIR / "shell" / "kit.css").read_text("utf-8")
PAGE_FIXTURES = ["v0-page-with-notes.json", "v0-sdd-pass.json"]
HISTORY = re.compile(r'<details class="afkv2-history".*?</details>', re.S)
SUMMARY = re.compile(r'<details class="afkv2-history"[^>]*><summary>(.*?)</summary>', re.S)
CHANGES = re.compile(r'<ol class="afkv2-v2-changes">(.*?)</ol>', re.S)
PAST_RULE = re.compile(r"\.afkv2-round-chip--past \{([^}]*)\}")
BASE_RULE = re.compile(r"\.afkv2-round-chip \{([^}]*)\}")
CHANGE_RULE = re.compile(r"\.afkv2-v2-change-round \{([^}]*)\}")
FILL = "background: var(--afkv2-round"
# The card module as the registry loads it: its fade and fade constants.
CARD = registry.lookup("card").render.__globals__
MUTED_AND_MAP = {"afkv2-round-chip--past", "afkv2-node-round"}
# The CSS saturate() matrix (Filter Effects 1, "saturate"), applied to sRGB values as browsers do for the function.
SATURATE = ((0.213, 0.787, 0.715, -0.715, 0.072, -0.072), (0.213, -0.213, 0.715, 0.285, 0.072, -0.072),
            (0.213, -0.213, 0.715, -0.715, 0.072, 0.928))


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


def test_a_history_summary_names_each_round_with_its_chip():
    html = page.build(fixture("v0-page-with-notes.json"))
    found = [chip for summary in SUMMARY.findall(html) for chip in chips(summary)]
    assert found and all(colour == rounds.colour_of(n) for _, colour, n in found), found


def test_each_change_line_names_its_round_with_its_chip():
    html = page.build(document())
    lists = CHANGES.findall(html)
    assert lists
    for found in lists:
        lines = found.count("<li ")
        marked = chips(found)
        assert len(marked) == lines and all(colour == rounds.colour_of(n) for _, colour, n in marked), found
    rule = CHANGE_RULE.search(KIT).group(1)
    assert "background" not in rule and "color" not in rule and "border" not in rule


def test_a_muted_chip_keeps_the_fill_of_its_round():
    rule = PAST_RULE.search(KIT).group(1)
    assert "background" not in rule and "color" not in rule
    base = BASE_RULE.search(KIT).group(1)
    assert FILL in base and f"color: {CHIP_TEXT}" in base


def test_the_chip_colour_is_stable_and_differs_between_neighbouring_rounds():
    hues = [rounds.colour_of(n) for n in range(1, 13)]
    assert hues == [rounds.colour_of(n) for n in range(1, 13)] and len(set(hues)) == 12
    assert rounds.round_colour({"n": 3, "colour": "tomato"}) == "tomato"


def test_an_old_round_fades_by_saturation_never_by_opacity():
    fade = CARD["fade"]
    assert fade(0) == ""
    assert fade(1) == "filter: saturate(0.8)" and fade(9) == "filter: saturate(0.4)"


def _luminance(rgb):
    channel = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * channel[0] + 0.7152 * channel[1] + 0.0722 * channel[2]


def _contrast(a, b):
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _saturate(rgb, amount):
    return tuple(min(1.0, max(0.0, sum((row[2 * k] + row[2 * k + 1] * amount) * rgb[k] for k in range(3))))
                 for row in SATURATE)


def test_the_chip_text_is_readable_on_every_round_fill_at_every_fade():
    """The chip is opaque and its fill and text are fixed colours, so the contrast is the same in both themes."""
    text = tuple(int(CHIP_TEXT[i:i + 2], 16) / 255 for i in (1, 3, 5))
    for age in range(0, 6):
        amount = max(CARD["FADE_FLOOR"], 1 - CARD["FADE_STEP"] * age)
        for n in range(1, 101):
            hue, saturation, lightness = map(float, HSL.fullmatch(rounds.colour_of(n)).groups())
            fill = colorsys.hls_to_rgb(hue / 360, lightness / 100, saturation / 100)
            assert _contrast(_saturate(fill, amount), _saturate(text, amount)) >= AA_TEXT, (n, age)
