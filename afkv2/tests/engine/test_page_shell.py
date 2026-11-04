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


# --- what changed this round: the banner list and the round marks

CHANGED_LIST = "afkv2-banner-changed"
FRESH = 'data-afkv2-fresh="{}"'


def table(table_id):
    return {"type": "table", "id": table_id, "props": {"columns": ["Cost"], "rows": [["low"]]}}


def changed_rounds():
    old = card("i-old", "decided", state="settled_by_mark", settled={"by": "mark", "round": 1, "signal": "accept"})
    new = {**card("i-new", title="The new card"), "body": table("d-cost")}
    return document(round_of(1, old, changed=["i-old"]), round_of(2, new, card("i-plain"), changed=["i-new", "d-cost"]))


def banner(html, n):
    start = html.index(f'data-afkv2-banner="{n}"')
    return html[start:html.index("</header>", start)]


def element_tag(html, element):
    start = html.index(f'data-afkv2-element="{element}"')
    return html[html.rindex("<", 0, start):html.index(">", start)]


def test_after_round_1_the_banner_lists_each_changed_element_with_a_link():
    html = build(changed_rounds())
    current = banner(html, 2)
    assert CHANGED_LIST in current and "What changed" in current
    assert '<a href="#i-new">The new card</a>' in current and '<a href="#d-cost">d-cost</a>' in current
    assert current.index("#i-new") < current.index("#d-cost")


def test_round_1_has_no_changed_list_and_a_round_with_none_says_nothing_changed():
    assert CHANGED_LIST not in build(document(round_of(1, card("i-a"), changed=["i-a"])))
    html = build(two_rounds())
    assert CHANGED_LIST in banner(html, 2) and "Nothing." in banner(html, 2)


def test_a_changed_element_of_this_round_has_a_round_mark_and_others_none():
    html = build(changed_rounds())
    assert FRESH.format(2) in element_tag(html, "i-new") and FRESH.format(2) in element_tag(html, "d-cost")
    assert "data-afkv2-fresh" not in element_tag(html, "i-plain")
    assert "data-afkv2-fresh" not in element_tag(html, "i-old")
    assert html.count("data-afkv2-fresh=") == 2


def test_the_round_mark_has_its_style_on_every_page():
    kit = (SHELL / "kit.css").read_text("utf-8")
    assert "[data-afkv2-fresh]" in kit and "[data-afkv2-fresh]" not in (SHELL / "tips.css").read_text("utf-8")


# --- text that names a card links to it

CARD_LINK = '<a class="afkv2-card-link" href="#{0}">{0}</a>'


def test_text_that_names_another_card_links_to_it():
    doc = two_rounds()
    doc["rounds"][1]["items"][0]["body"] = text("This follows i-old, and i-gone is no card.")
    doc["rounds"][1]["banner"]["settled"] = ["i-old accepted"]
    html = build(doc)
    assert CARD_LINK.format("i-old") in banner(html, 2)
    body = html[html.index('id="i-new"'):]
    assert "This follows " + CARD_LINK.format("i-old") in body
    assert CARD_LINK.format("i-gone") not in html


def test_a_card_id_of_letters_only_stays_a_plain_word():
    doc = two_rounds()
    doc["rounds"][0]["items"][0]["id"] = "export"
    doc["rounds"][1]["banner"]["settled"] = ["export accepted"]
    assert CARD_LINK.format("export") not in build(doc)


def test_a_card_heading_and_a_link_keep_their_text():
    html = build(two_rounds())
    start = html.index('id="i-new"')
    assert CARD_LINK.format("i-new") not in html[start:html.index("</h4>", start)]
    assert '<a class="afkv2-card-link"' not in html[html.index("<title>"):html.index("</title>")]
