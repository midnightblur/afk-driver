"""A pane agent's two names: the spaced four-part pane label and the herdr agent name.

The parts are goal, role, model and effort. The goal is the feature's leading ticket key, else the feature
identifier cut to 16 characters. The agent name joins the parts with '-', each made legal by one rule
(lowercase; each character herdr refuses becomes '-'; g- before a first character that is not a lowercase
letter), at most 32 characters with any -N suffix; the goal part is cut first. The model part drops a vendor
prefix, is made legal, then is cut to 8 characters, and the pane label carries that same model part.
"""
from __future__ import annotations

import re
import string
from typing import Iterable

LIMIT = 32
GOAL_ROOM = 16
MODEL_ROOM = 8
VENDOR_PREFIXES = ("claude-", "gpt-")
EFFORTS = ("lo", "med", "hi", "max")
_TICKET = re.compile(r"[A-Z][A-Z0-9]*-[0-9]+")
_REFUSED = re.compile(r"[^a-z0-9_-]")


class NameRefused(ValueError):
    """No legal agent name fits; the message names the name."""


def goal_of(feature: str) -> str:
    """The goal part: the feature's leading ticket key, else the feature identifier cut to 16 characters."""
    key = _TICKET.match(feature)
    return key.group(0) if key else feature[:GOAL_ROOM]


def _needs_prefix(text: str) -> bool:
    return not text or text[0] not in string.ascii_lowercase


def legal(part: str) -> str:
    """One part made legal for a herdr agent name."""
    text = _REFUSED.sub("-", part.lower())
    return f"g-{text}" if _needs_prefix(text) else text


def model_part(cell: str) -> str:
    """The model cell with its vendor prefix dropped, made legal, then cut to 8 characters."""
    bare = next((cell[len(p):] for p in VENDOR_PREFIXES if cell.lower().startswith(p)), cell)
    return legal(bare)[:MODEL_ROOM]


def build_agent_name(feature: str, role: str, model_cell: str, effort: str,
                     taken: Iterable[str] = ()) -> tuple[str, str]:
    """(pane label, agent name) for one agent; `taken` holds the labels and names already in the manifest.

    Raises NameRefused naming the name when role, model, effort and suffix leave no room for 1 goal
    character, or for g- and 1 character when the goal needs g-, the 3 joining '-' counted.
    """
    if effort not in EFFORTS:
        raise ValueError(f"effort {effort!r} is not one of {', '.join(EFFORTS)}")
    goal, model = goal_of(feature), model_part(model_cell)
    parts = (legal(role), model, legal(effort))
    goal_slug = legal(goal)
    need = 3 if _needs_prefix(_REFUSED.sub("-", goal.lower())) else 1
    taken = set(taken)
    number = 1
    while True:
        suffix = "" if number == 1 else f"-{number}"
        room = LIMIT - 3 - sum(len(p) for p in parts) - len(suffix)
        name = "-".join((goal_slug[:max(room, 0)], *parts)) + suffix
        if room < need:
            raise NameRefused(f"agent name {name!r} leaves no room for the goal part "
                              f"({room} characters, {need} needed); shorten the role name")
        label = " ".join((goal, role, model, effort)) + ("" if number == 1 else f" #{number}")
        if name not in taken and label not in taken:
            return label, name
        number += 1
