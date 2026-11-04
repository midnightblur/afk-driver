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
    assert CHANGED_LIST not in banner(build(document(round_of(1, card("i-a"), changed=["i-a"]))), 1)
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


# --- layout: the banner's 3 columns, scope map groups, the notes tables at phone width

import re  # noqa: E402

import registry  # noqa: E402

KIT = (SHELL / "kit.css").read_text("utf-8")
NOTES_CSS = (SHELL / "notes.css").read_text("utf-8")
DIAGRAM_CSS = (SHELL / "diagram.css").read_text("utf-8")
CANVAS = 'class="afkv2-boxes"'
GROUPS = '<div class="afkv2-map-groups">'


def rule(css, selector, media=None):
    """The declarations of `selector`, inside the `@media` block whose query is `media` when given."""
    if media:
        start = css.index(f"@media {media}")
        css = css[start:css.index("\n}", start)]
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, selector
    return match.group(1)


def test_the_banner_lists_stack_and_sit_side_by_side_in_3_columns_when_wide():
    assert "minmax(0, 1fr)" in rule(KIT, ".afkv2-banner-lists")
    assert "auto-fit" not in rule(KIT, ".afkv2-banner-lists")
    assert "repeat(3, minmax(0, 1fr))" in rule(KIT, ".afkv2-banner-lists", "(min-width: 48rem)")
    assert "grid-column: 1 / -1" in rule(KIT, ".afkv2-banner-changed")


def scope_map(edges=()):
    return {"type": "map", "id": "m-scope", "props": {
        "groups": [{"id": "web", "label": "web module"}, {"id": "core", "label": "core module"}],
        "nodes": [{"id": "n-a", "label": "a", "state": "open", "round": 1, "group": "web"},
                  {"id": "n-b", "label": "b", "state": "open", "round": 1, "group": "core"},
                  {"id": "n-c", "label": "c", "state": "settled", "round": 1, "group": "core"},
                  {"id": "n-d", "label": "d", "state": "settled", "round": 1}],
        "edges": list(edges)}}


def test_a_scope_map_draws_each_group_on_its_own_canvas_that_wraps():
    html = registry.render_component(scope_map([{"from": "n-b", "to": "n-c"}]))
    assert html.count(GROUPS) == 1 and html.count(CANVAS) == 3
    assert html.index("web module") < html.index("core module") < html.index('data-afkv2-element="n-d"')
    assert html.count('data-afkv2-element="n-') == 4
    assert "flex-wrap: wrap" in rule(DIAGRAM_CSS, ".afkv2-map-groups")


def test_a_map_with_an_arrow_between_groups_stays_one_canvas():
    html = registry.render_component(scope_map([{"from": "n-a", "to": "n-b"}]))
    assert GROUPS not in html and html.count(CANVAS) == 1


def test_the_notes_tables_scroll_in_their_own_box_at_phone_width():
    """Finding f4 of 0004: at 390 px the fixed and percent widths overflowed the page by about 29 px."""
    doc = two_rounds()
    doc["notes"] = [{"id": "N-2-i-new-1", "round": 2, "target": "i-new", "item": "i-new", "quote": None,
                     "text": "words", "deleted": False}]
    html = build(doc)
    card_start = html.index('id="i-new"')
    assert '<div class="afkv2-nr-scroll"><table' in html[card_start:]
    assert "overflow-x: auto" in rule(NOTES_CSS, ".afkv2-nr-scroll, .afkv2-notes-replies")
    assert "min-width: 40rem" in rule(NOTES_CSS, ".afkv2-nr-table")
