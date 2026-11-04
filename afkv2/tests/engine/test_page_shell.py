"""The page shell (SDD §14 rows "Page title" and "Navigation", SDD §9 rows "What changed this round" and
"Back after a jump"): the stable title, the navigation, the back list, map box clicks, card links, the
banner's list of what changed, round marks and scope map groups. The browser half of each runs in
`afkv2/tests/live/test_page_live.md`."""

import copy
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
SHELL = ENGINE_DIR / "shell"
for folder in (PLUGIN / "scripts", ENGINE_DIR):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
from shell import page  # noqa: E402

V0, V1 = "afkv2.page/0", "afkv2.page/1"
SEP = " · "


def text(value, **extra):
    return {"type": "text", "props": {"text": value}, **extra}


def card(item_id, kind="confirm", **extra):
    return {"id": item_id, "kind": kind, "body": text(f"Body of {item_id}", id=f"{item_id}-words"), **extra}


def round_of(n, *items, state="settled", **extra):
    return {"n": n, "state": state, "banner": {"settled": [], "unlocks": [], "parked": []}, "items": list(items),
            **extra}


def document(*rounds, maps=None, **session):
    rounds = list(rounds) or [round_of(1, card("i-a"))]
    rounds[-1]["state"] = "current"
    return {"schema": V1,
            "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                        "started": "2026-01-05T09:00:00Z", "short_title": "Export to a file",
                        "step": "Requirements grill", **session},
            "maps": maps or [], "notes": [], "rounds": rounds}


def two_rounds(**session):
    old = card("i-old", "decided", state="settled_by_mark", settled={"by": "mark", "round": 1, "signal": "accept"})
    return document(round_of(1, old), round_of(2, card("i-new")), **session)


def build(doc):
    return page.build(engine.READERS[doc["schema"]](doc))


def in_memory(doc):
    return engine.READERS[doc["schema"]](doc)


def heading(html):
    start = html.index('<h1 class="afkv2-title">')
    return html[start:html.index("</h1>", start)]


# --- the stable title


def test_the_heading_and_the_tab_read_ticket_short_title_and_step():
    html = build(two_rounds())
    want = SEP.join(["PROJ-1", "Export to a file", "Requirements grill"])
    assert page.stable_title(in_memory(two_rounds())) == want
    assert f"<title>{want}</title>" in html
    assert want in heading(html)


def test_the_title_is_the_same_every_round():
    first = document(round_of(1, card("i-a")))
    assert page.stable_title(in_memory(first)) == page.stable_title(in_memory(two_rounds()))
    assert "R-" not in page.stable_title(in_memory(two_rounds()))


def test_a_page_with_no_ticket_renders_its_title():
    """PR #171 finding f9 of 0003: a round build with no --ticket gave session.ticket null."""
    doc = two_rounds(ticket=None, skill="use-lavish", step="Cache sizes")
    want = SEP.join(["Export to a file", "Cache sizes"])
    assert page.stable_title(in_memory(doc)) == want
    html = build(doc)
    assert f"<title>{want}</title>" in html and "None" not in heading(html)


def test_an_upgraded_format_0_page_uses_its_feature_name():
    doc = two_rounds()
    doc["schema"] = V0
    for key in ("short_title", "step"):
        doc["session"].pop(key)
    doc.pop("notes")
    assert page.stable_title(in_memory(doc)) == SEP.join(["PROJ-1", "export", "Requirements grill"])


def test_a_number_ticket_is_an_issue_reference_and_a_repeated_name_shows_once():
    doc = two_rounds(ticket="158", short_title=None, feature="158")
    assert page.stable_title(in_memory(doc)) == SEP.join(["#158", "Requirements grill"])
