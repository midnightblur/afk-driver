"""The page shell (SDD §14 rows "Page title" and "Navigation", SDD §9 rows "What changed this round" and
"Back after a jump"): the stable title, the navigation, the back list, map box clicks, card links, the
banner's list of what changed, round marks and scope map groups. The browser half of each runs in
`afkv2/tests/live/test_page_live.md`."""

import re
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
SHELL = ENGINE_DIR / "shell"
for folder in (PLUGIN / "scripts", ENGINE_DIR):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
import registry  # noqa: E402
from shell import page  # noqa: E402

V0, V1 = "afkv2.page/0", "afkv2.page/1"
SEP = " · "
HEADING = '<h1 class="afkv2-title">'
BANNER = 'data-afkv2-banner="{}"'
ELEMENT = 'data-afkv2-element="{}"'
CHANGED_LIST = "afkv2-banner-changed"
FRESH_ATTR = "data-afkv2-fresh"
FRESH = FRESH_ATTR + '="{}"'
FRESH_RULE = f"[{FRESH_ATTR}]"
CARD_LINK = '<a class="afkv2-card-link" href="#{0}">{0}</a>'
CARD_LINK_START = '<a class="afkv2-card-link"'
CANVAS = 'class="afkv2-boxes"'
GROUPS = '<div class="afkv2-map-groups">'
NODE_N = 'data-afkv2-element="n-'
LISTS_RULE, CHANGED_RULE, GROUPS_RULE = ".afkv2-banner-lists", ".afkv2-banner-changed", ".afkv2-map-groups"
NOTES_WRAP = '<div class="afkv2-nr-scroll"><table'
NOTES_SCROLL_RULE, NOTES_TABLE_RULE = ".afkv2-nr-scroll, .afkv2-notes-replies", ".afkv2-nr-table"


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
    start = html.index(HEADING)
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


def test_a_step_that_repeats_the_name_shows_once():
    """Review finding f2: a format 0 skill with no step name took the feature as its step."""
    doc = two_rounds(skill="propose-verification")
    doc["schema"] = V0
    for key in ("short_title", "step"):
        doc["session"].pop(key)
    doc.pop("notes")
    assert page.stable_title(in_memory(doc)) == SEP.join(["PROJ-1", "export"])


def test_a_number_ticket_is_an_issue_reference_and_a_repeated_name_shows_once():
    doc = two_rounds(ticket="158", short_title=None, feature="158")
    assert page.stable_title(in_memory(doc)) == SEP.join(["#158", "Requirements grill"])


# --- what changed this round: the banner list and the round marks


def table(table_id):
    return {"type": "table", "id": table_id, "props": {"columns": ["Cost"], "rows": [["low"]]}}


def changed_rounds():
    old = card("i-old", "decided", state="settled_by_mark", settled={"by": "mark", "round": 1, "signal": "accept"})
    new = {**card("i-new", title="The new card"), "body": table("d-cost")}
    return document(round_of(1, old, changed=["i-old"]), round_of(2, new, card("i-plain"), changed=["i-new", "d-cost"]))


def banner(html, n):
    start = html.index(BANNER.format(n))
    return html[start:html.index("</header>", start)]


def element_tag(html, element):
    start = html.index(ELEMENT.format(element))
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
    assert FRESH_ATTR not in element_tag(html, "i-plain")
    assert FRESH_ATTR not in element_tag(html, "i-old")
    assert html.count(FRESH_ATTR + "=") == 2


def test_an_element_that_an_answer_changed_is_listed_and_marked_too():
    """Review finding f3, SDD §9 row "What changed this round": the round's list and its answers' lists."""
    doc = changed_rounds()
    doc["rounds"][1]["replies"] = [{"text": "Done.", "changed": ["i-plain", "i-new"]}]
    html = build(doc)
    current = banner(html, 2)
    assert current.count('href="#i-new"') == 1 and '<a href="#i-plain">i-plain</a>' in current
    assert current.index("#d-cost") < current.index("#i-plain")
    assert FRESH.format(2) in element_tag(html, "i-plain")
    assert html.count(FRESH_ATTR + "=") == 3


def test_the_round_mark_has_its_style_on_every_page():
    kit = (SHELL / "kit.css").read_text("utf-8")
    assert FRESH_RULE in kit and FRESH_RULE not in (SHELL / "tips.css").read_text("utf-8")


# --- text that names a card links to it


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
    assert CARD_LINK_START not in html[html.index("<title>"):html.index("</title>")]


# --- layout: the banner's 3 columns, scope map groups, the notes tables at phone width

KIT = (SHELL / "kit.css").read_text("utf-8")
NOTES_CSS = (SHELL / "notes.css").read_text("utf-8")
DIAGRAM_CSS = (SHELL / "diagram.css").read_text("utf-8")


def rule(css, selector, media=None):
    """The declarations of `selector`, inside the `@media` block whose query is `media` when given."""
    if media:
        start = css.index("{", css.index(f"@media {media}")) + 1
        depth, end = 1, start
        while depth:
            depth += {"{": 1, "}": -1}.get(css[end], 0)
            end += 1
        css = css[start:end]
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, selector
    return match.group(1)


def test_the_banner_lists_stack_and_sit_side_by_side_in_3_columns_when_wide():
    assert "minmax(0, 1fr)" in rule(KIT, LISTS_RULE)
    assert "auto-fit" not in rule(KIT, LISTS_RULE)
    assert "repeat(3, minmax(0, 1fr))" in rule(KIT, LISTS_RULE, "(min-width: 48rem)")
    assert "grid-column: 1 / -1" in rule(KIT, CHANGED_RULE)


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
    assert html.index("web module") < html.index("core module") < html.index(ELEMENT.format("n-d"))
    assert html.count(NODE_N) == 4
    assert "flex-wrap: wrap" in rule(DIAGRAM_CSS, GROUPS_RULE)


ORDER = '<ul class="afkv2-map-order">'
EDGE = 'data-afkv2-edge="{} {}"'


def test_a_scope_map_with_an_arrow_between_groups_keeps_its_groups_side_by_side():
    """Review finding: the arrow between groups made one canvas that stacked its groups on a wide window.
    The arrow inside a group stays drawn; the arrow between groups becomes a line under the groups."""
    html = registry.render_component(scope_map([{"from": "n-a", "to": "n-b"}, {"from": "n-b", "to": "n-c"}]))
    assert html.count(GROUPS) == 1 and html.count(CANVAS) == 3
    assert EDGE.format("n-b", "n-c") in html and EDGE.format("n-a", "n-b") not in html
    order = html[html.index(ORDER):]
    assert "a" in order and "settles before" in order and html.index(GROUPS) < html.index(ORDER)


def test_the_notes_tables_scroll_in_their_own_box_at_phone_width():
    """Finding f4 of 0004: at 390 px the fixed and percent widths overflowed the page by about 29 px."""
    doc = two_rounds()
    doc["notes"] = [{"id": "N-2-i-new-1", "round": 2, "target": "i-new", "item": "i-new", "quote": None,
                     "text": "words", "deleted": False}]
    html = build(doc)
    card_start = html.index('id="i-new"')
    assert NOTES_WRAP in html[card_start:]
    assert "overflow-x: auto" in rule(NOTES_CSS, NOTES_SCROLL_RULE)
    assert "min-width: 40rem" in rule(NOTES_CSS, NOTES_TABLE_RULE)


# --- navigation, back after a jump and map box clicks; the live test drives them in a browser

import json  # noqa: E402

TIPS_JS = (SHELL / "tips.js").read_text("utf-8")
TIPS_CSS = (SHELL / "tips.css").read_text("utf-8")
RUNTIME = (SHELL / "runtime.js").read_text("utf-8")
NODE_CARDS = '<script type="application/json" id="afkv2-node-cards">'
NAV_RULE, JUMP_RULE, WITH_NAV_RULE = "#afkv2-nav", "#afkv2-jump", "body.afkv2-with-nav"
MIN_LIST_RULE = "#afkv2-nav.afkv2-min #afkv2-nav-list"
TOOLS_HOLD_JUMP = "nav.querySelector('#afkv2-nav-tools').appendChild(jump);"
NAV_KEY = "'afkv2-nav:' + session"
BACK_KEY = "'afkv2-back:' + holder.getAttribute('data-afkv2-session')"
NODE_CARDS_READ = "getElementById('afkv2-node-cards')"


def wide_query():
    return re.search(r"var WIDE = '([^']+)';", TIPS_JS).group(1)


def test_the_navigation_sits_in_the_left_margin_on_a_wide_window():
    wide = wide_query()
    assert "padding-left" in rule(TIPS_CSS, WITH_NAV_RULE, wide)
    assert "left:" in rule(TIPS_CSS, NAV_RULE, wide) and "right:" not in rule(TIPS_CSS, NAV_RULE)
    assert "matchMedia(WIDE)" in TIPS_JS


def test_on_a_narrow_window_the_navigation_is_a_button_whose_list_closes_after_a_jump():
    assert "if (!wide.matches) nav.classList.add(MINIMIZED);" in TIPS_JS
    assert "display: none" in rule(TIPS_CSS, MIN_LIST_RULE)


def test_the_navigation_no_longer_shares_the_bottom_left_corner_with_btw():
    assert "bottom:" not in rule(TIPS_CSS, JUMP_RULE) and "bottom:" not in rule(TIPS_CSS, NAV_RULE)
    assert TOOLS_HOLD_JUMP in TIPS_JS


BTW_CSS = (SHELL / "btw.css").read_text("utf-8")
BTW_RULE, BTW_BUTTON_PX = "#afkv2-btw", 32


def test_a_full_navigation_on_a_wide_window_ends_above_the_btw_button():
    """Finding f1 of the review: a long rail reached 14 px above the window bottom, under the btw? button."""
    top = int(re.search(r"top: (\d+)px", rule(TIPS_CSS, NAV_RULE, wide_query())).group(1))
    reserved = int(re.search(r"max-height: calc\(100vh - (\d+)px\)", rule(TIPS_CSS, NAV_RULE, wide_query())).group(1))
    btw_bottom = int(re.search(r"bottom: (\d+)px", rule(BTW_CSS, BTW_RULE)).group(1))
    assert reserved - top >= btw_bottom + BTW_BUTTON_PX


def test_the_collapsed_navigation_is_kept_per_session_where_a_sandboxed_frame_can_write():
    assert NAV_KEY in TIPS_JS and "window.name" in TIPS_JS
    assert "location.pathname" not in TIPS_JS


def test_the_page_keeps_its_last_20_places_across_a_reload():
    assert "var afkv2BackList = read();" in RUNTIME and "var BACK_LIMIT = 20;" in RUNTIME
    assert BACK_KEY in RUNTIME
    assert "window.name" in RUNTIME and "window.afkv2Jump = jump;" in RUNTIME
    assert "window.afkv2Jump" in TIPS_JS


def test_an_in_page_link_and_a_map_box_jump_and_the_back_button_returns():
    assert "var IN_PAGE_LINK = 'a[href^=\"#\"]';" in RUNTIME and "closest(IN_PAGE_LINK)" in RUNTIME
    assert NODE_CARDS_READ in RUNTIME and "box.addEventListener('click'" in RUNTIME
    assert "back.addEventListener('click', goBack);" in RUNTIME


def node_card_rounds():
    map_ = {"type": "map", "id": "m-1", "props": {"nodes": [
        {"id": "n-1", "label": "one", "state": "open", "round": 1},
        {"id": "n-2", "label": "two", "state": "open", "round": 1}]}}
    first = card("i-a", node="n-1", state="settled_by_mark", settled={"by": "mark", "round": 1, "signal": "accept"})
    later = card("i-b", node="n-1", carries=["i-a"])
    return document(round_of(1, first), round_of(2, card("i-x")), round_of(3, later, changed=[]),
                    maps=[map_])


def node_cards(html):
    start = html.index(NODE_CARDS) + len(NODE_CARDS)
    return json.loads(html[start:html.index("</script>", start)])


def test_each_map_box_names_its_newest_card_and_the_round_of_its_last_change():
    doc = node_card_rounds()
    assert node_cards(build(doc)) == {"n-1": ["i-b", 3]}
    doc["rounds"][2]["items"][0].pop("node")
    doc["rounds"][1]["changed"] = ["n-1"]
    assert node_cards(build(doc)) == {"n-1": ["i-a", 2]}


def test_an_answer_that_changed_the_card_sets_the_round_of_the_box():
    """Review finding: the hover round read the round's own list only, not its answers' lists."""
    doc = node_card_rounds()
    doc["rounds"][2]["items"][0].pop("node")
    doc["rounds"][1]["replies"] = [{"text": "Done.", "changed": ["i-a"]}]
    assert node_cards(build(doc)) == {"n-1": ["i-a", 2]}


BOX_SKIPS_LINK = "if (event.target.closest && event.target.closest(IN_PAGE_LINK)) return;"


def test_a_card_link_in_a_box_label_jumps_once_and_an_odd_id_still_jumps():
    """Review findings: a link in a box label pushed 2 places; a bare % in an id threw before the jump."""
    assert BOX_SKIPS_LINK in RUNTIME
    assert "decodeURIComponent" not in RUNTIME


def test_a_page_with_no_map_box_of_a_card_has_no_node_list():
    assert NODE_CARDS not in build(two_rounds())
