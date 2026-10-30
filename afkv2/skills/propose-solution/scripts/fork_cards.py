"""Fork cards: a `debate` item whose body shows the options side by side (SDD §4).

One table column per option, and one cell per option with the id `<item id>-opt-<letter>`. The page
offers one option mark per such cell, labelled with its column heading.
"""

from __future__ import annotations

import copy
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "grill" / "scripts"))

from grill_common import Refusal  # noqa: E402

LETTERS = string.ascii_lowercase
FORK_FIELDS = {"question", "options", "why_open", "recommended", "picture"}


def _text(component_id, value):
    return {"type": "text", "id": component_id, "props": {"text": value}}


def _check(item_id, question, options, why_open, recommended, picture):
    where = f"fork {item_id}"
    if not question or not why_open:
        raise Refusal("bad-fork", f"{where}: question and why_open are required")
    if not isinstance(options, list) or not 2 <= len(options) <= len(LETTERS):
        raise Refusal("bad-fork", f"{where}: a fork has 2 to {len(LETTERS)} options")
    names = [option.get("name") if isinstance(option, dict) else None for option in options]
    if not all(names) or not all(isinstance(option, dict) and option.get("text") for option in options):
        raise Refusal("bad-fork", f"{where}: each option has a name and a text")
    if len(set(names)) != len(names):
        raise Refusal("bad-fork", f"{where}: 2 options have the same name")
    if recommended is not None and recommended not in LETTERS[:len(options)]:
        raise Refusal("bad-fork", f"{where}: recommended {recommended!r} names no option")
    if picture is not None and not (isinstance(picture, dict) and picture.get("type")):
        raise Refusal("bad-fork", f"{where}: picture must be one component")


def build_fork_card(item_id, question, options, why_open, recommended=None, picture=None, node=None, state="open"):
    """A debate item: the question, the options as table columns, and why the agent did not decide it.

    With `picture`, the picture of the current state is the body root, above the question.
    """
    _check(item_id, question, options, why_open, recommended, picture)
    choice = f"Recommended: {recommended.upper()}." if recommended else "No recommendation."
    asked = _text(f"{item_id}-question", f"{question} {choice}")
    table = {"type": "table", "id": f"{item_id}-options", "props": {
        "columns": [f"{letter.upper()} — {option['name']}" for letter, option in zip(LETTERS, options)],
        "rows": [[_text(f"{item_id}-opt-{letter}", option["text"]) for letter, option in zip(LETTERS, options)]]}}
    why = _text(f"{item_id}-why-open", why_open)
    if picture is None:
        body = {**asked, "children": [table, why]}
    else:
        body = copy.deepcopy(picture)
        body["children"] = [*(body.get("children") or []), asked, table, why]
    item = {"id": item_id, "kind": "debate", "state": state, "body": body}
    if node:
        item["node"] = node
    return item


def expand_fork(raw):
    """Turn a round-input item with a `fork` field into a debate item, and keep its other input fields."""
    fork = raw.get("fork")
    if not isinstance(fork, dict) or set(fork) - FORK_FIELDS:
        raise Refusal("bad-fork", f"fork {raw.get('id')}: one object with {sorted(FORK_FIELDS)}")
    if "body" in raw or raw.get("kind", "debate") != "debate":
        raise Refusal("bad-fork", f"fork {raw.get('id')}: the card is built from its fork; give no body and no other kind")
    item = build_fork_card(raw.get("id"), fork.get("question"), fork.get("options"), fork.get("why_open"),
                           fork.get("recommended"), fork.get("picture"), raw.get("node"), raw.get("state", "open"))
    kept = {field: value for field, value in raw.items() if field not in ("fork", "kind", "body", "node", "state")}
    return {**kept, **item}
