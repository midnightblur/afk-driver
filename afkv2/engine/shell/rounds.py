"""The colour of each round and the round chip, the one home of both. Every chip that names a round comes from
`round_chip`, so a chip shows the colour of its own round wherever it sits: a card, a card's history, the banner,
the notes table or a map box.

A round's colour is its own `colour`, else a hue a golden-angle step from its neighbours at a fixed saturation and
lightness. The chip text is near-black on that fill: its contrast is at least 4.5:1 for every hue, also at the
fade floor of an old round (a saturation fade on an opaque chip), so it is the same in both themes.
"""

from __future__ import annotations

from contextlib import contextmanager
from html import escape

GOLDEN_ANGLE = 137.5
CHIP_CLASS = "afkv2-round-chip"
_colours: dict[int, str] = {}


def round_colour(round_: dict) -> str:
    """The round's own colour; a hue step keeps every round number apart from its neighbours."""
    return round_.get("colour") or f"hsl({(round_['n'] * GOLDEN_ANGLE) % 360:.1f}, 72%, 70%)"


@contextmanager
def round_context(rounds: list[dict]):
    """The colour of each round of the page being built, so a chip that knows only its round number finds it."""
    global _colours
    previous, _colours = _colours, {r["n"]: round_colour(r) for r in rounds}
    try:
        yield
    finally:
        _colours = previous


def colour_of(n: int) -> str:
    """The colour of round `n` in the page being built; outside a build, the hue of its number."""
    return _colours.get(n) or round_colour({"n": n})


def round_chip(n: int, words: str, modifier: str = "", style: str = "", attrs: str = "",
               colour: str | None = None) -> str:
    """The chip of round `n` with `words`. `modifier` adds a class, `style` adds CSS declarations, such as the
    fade of an old round, `attrs` adds attributes, and `colour`, when the caller holds the round, is its colour."""
    css = f"{CHIP_CLASS} {modifier}" if modifier else CHIP_CLASS
    rules = f"--afkv2-round: {colour or colour_of(n)}" + (f"; {style}" if style else "")
    return f'<span class="{css}" style="{escape(rules)}"{attrs}>{escape(words)}</span>'
