"""Contract tests for the deterministic lavish renderer.

They pin the two things the page kit exists to guarantee: the attribute
contract the send runtime composes from, and the split between a violation
that degrades and a violation that fails the render.

    python -m unittest scripts.tests.test_lavish_render
    python scripts/tests/test_lavish_render.py
"""

import copy
import io
import json
import os
import sys
import unittest
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)

import lavish_render  # noqa: E402
from lavish import page, schema  # noqa: E402

FIXTURE = os.path.join(HERE, "samples", "lavish-round.json")

VOID = {"meta", "link", "br", "hr", "img", "input", "source", "col"}


class Node(object):
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []

    def find(self, predicate, into=None):
        found = into if into is not None else []
        for child in self.children:
            if predicate(child):
                found.append(child)
            child.find(predicate, found)
        return found

    def has_ancestor(self, node):
        walker = self.parent
        while walker is not None:
            if walker is node:
                return True
            walker = walker.parent
        return False


class Tree(HTMLParser):
    """Enough of an HTML tree to assert containment, on the standard library."""

    def __init__(self, html):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.root = Node("#root", [], None)
        self._stack = [self.root]
        self._skip = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
            return
        if self._skip:
            return
        node = Node(tag, attrs, self._stack[-1])
        self._stack[-1].children.append(node)
        if tag not in VOID:
            self._stack.append(node)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def find(self, predicate):
        return self.root.find(predicate)


def has(attr):
    return lambda node: attr in node.attrs


def attr_is(attr, value):
    return lambda node: node.attrs.get(attr) == value


def load_fixture():
    with open(FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)


def render(doc):
    return page.build(schema.load(copy.deepcopy(doc)))


def body_of(html):
    """The rendered markup without the inlined stylesheet and runtime.

    Twice now an assertion about the page has matched a CSS comment or a class
    name in the stylesheet instead of an element. Any test asking whether
    something is *absent* asks it of this, not of the whole document.
    """
    return html.split("<body>", 1)[1].split("<script>", 1)[0]


def first_component(doc, component):
    """The first item of a component kind, for tests that break one field."""
    for rnd in doc["rounds"]:
        for item in rnd["items"]:
            if item.get("component") == component:
                return item
    raise AssertionError("fixture carries no %s" % component)


class RenderContract(unittest.TestCase):
    def setUp(self):
        self.doc = load_fixture()
        self.html = render(self.doc)
        self.tree = Tree(self.html)

    def test_deterministic(self):
        self.assertEqual(self.html, render(self.doc))

    def test_no_external_resources(self):
        for needle in ("http://", "https://", "<link", "src="):
            self.assertNotIn(needle, self.html, "%r would leave the page" % needle)

    def test_one_current_element_and_every_answer_inside_it(self):
        """The invariant the injected session rail and the send both rest on."""
        current = self.tree.find(attr_is("data-afk-state", "current"))
        self.assertEqual(len(current), 1)
        for node in self.tree.find(has("data-afk-input")):
            self.assertTrue(node.has_ancestor(current[0]),
                            "an answer control outside the current section is never sent")

    def test_one_choice_and_one_note_per_answerable_card(self):
        current = self.tree.find(attr_is("data-afk-state", "current"))[0]
        cards = current.find(has("data-afk-item"))
        self.assertTrue(cards)
        for card in cards:
            self.assertEqual(len(card.find(attr_is("data-afk-input", "choice"))), 1)
            self.assertEqual(len(card.find(attr_is("data-afk-input", "note"))), 1)

    def test_item_ids_unique_and_every_item_opens_with_its_label(self):
        """The injected rail labels and folds an item by its first child.

        A card opens with its heading -- h4 inside a group, h3 in a flat
        round, h2 for the round itself, so grouping moves the level and never
        the position. A table row opens with its Item cell instead: the same
        contract in the shape a `tr` can hold.
        """
        seen = set()
        for node in self.tree.find(has("data-afk-item")):
            item_id = node.attrs["data-afk-item"]
            self.assertNotIn(item_id, seen)
            seen.add(item_id)
            self.assertTrue(node.children, "%s has no label" % item_id)
            expected = ("td",) if node.tag == "tr" else ("h2", "h3", "h4")
            self.assertIn(node.children[0].tag, expected,
                          "%s must open with its label" % item_id)

    def test_carried_over_items_answer_nothing(self):
        current = self.tree.find(attr_is("data-afk-state", "current"))[0]
        carried = [n for n in self.tree.find(has("data-afk-item"))
                   if n is not current and not n.has_ancestor(current)]
        self.assertTrue(carried)
        for node in carried:
            self.assertEqual(node.find(has("data-afk-input")), [])

    def test_the_send_bar_offers_send_copy_and_a_jump(self):
        bar = self.tree.find(attr_is("id", "afk-send"))
        self.assertEqual(len(bar), 1)
        ids = [n.attrs.get("id") for n in bar[0].find(has("id"))]
        self.assertEqual(ids, ["afk-send-go", "afk-send-copy", "afk-send-jump"])
        jump = bar[0].find(attr_is("id", "afk-send-jump"))[0]
        self.assertIn("hidden", jump.attrs, "the jump stays out of the way until needed")

    def test_the_send_bar_sits_under_the_round_it_sends(self):
        """Not at the end of the document, where settled history buries it.

        A page whose settled history outgrows its current round strands a
        document-end bar below every settled card, and a host that sizes its
        frame to the content height defeats a fixed one too. The only
        placement that survives both is next to the cards it sends.
        """
        bar = self.html.index('id="afk-send"')
        round_end = self.html.index('data-afk-state="current"')
        settled = self.html.index('id="afk-settled"')
        self.assertLess(round_end, bar, "the bar follows its round")
        self.assertLess(bar, settled, "the bar precedes the settled history")
        self.assertNotIn("position: fixed", self.html,
                         "a fixed bar cannot be trusted inside a sized frame")

    def test_a_round_with_nothing_to_answer_offers_no_send(self):
        """A closing round is a record. A send control there would send nothing."""
        doc = load_fixture()
        current = [r for r in doc["rounds"] if r.get("state") == "current"][0]
        current["items"] = []
        html = render(doc)
        self.assertNotIn('id="afk-send"', html)
        self.assertIn("0 to answer", html)

    def test_settled_history_sits_below_the_current_round(self):
        order = [n.attrs.get("id") for n in self.tree.find(has("id"))
                 if n.attrs.get("id") in ("afk-open", "afk-settled")]
        self.assertEqual(order, ["afk-open", "afk-settled"])


class SilenceRule(unittest.TestCase):
    """Silence is never agreement: every answerable card needs an explicit mark."""

    def mark(self, **fields):
        item = {"component": "decided_card", "evidence": {"grade": "repo"}}
        item.update(fields)
        return schema.required_mark(item)

    def test_a_decided_card_needs_a_mark_at_either_evidence_grade(self):
        """The grade tells the reader how to judge it; it never buys a free pass."""
        self.assertTrue(self.mark(evidence={"grade": "repo"}))
        self.assertTrue(self.mark(evidence={"grade": "spec"}))

    def test_every_answerable_class_needs_a_mark(self):
        for component in ("debate_card", "confirm_row", "signoff_packet",
                          "decided_card"):
            self.assertTrue(schema.required_mark({"component": component}), component)

    def test_a_settled_card_asks_nothing(self):
        self.assertFalse(schema.required_mark({"component": "settled_card"}))

    def test_every_rendered_answer_surface_carries_the_required_flag(self):
        """The end-to-end guard: no answerable card renders without it."""
        tree = Tree(render(load_fixture()))
        current = tree.find(attr_is("data-afk-state", "current"))[0]
        answerable = [n for n in current.find(has("data-afk-item"))
                      if n.find(attr_is("data-afk-input", "choice"))]
        self.assertTrue(answerable, "the fixture must render answerable cards")
        for node in answerable:
            self.assertEqual(node.attrs.get("data-afk-required"), "1",
                             node.attrs.get("data-afk-item"))


class IndecisionIsStated(unittest.TestCase):
    """A debate card is a recorded indecision, so it owes its reason."""

    def test_a_debate_card_without_its_reason_is_refused(self):
        doc = load_fixture()
        card = first_component(doc, "debate_card")
        del card["undecided_because"]
        with self.assertRaises(schema.ContractError) as caught:
            render(doc)
        self.assertIn("undecided_because", str(caught.exception))

    def test_the_reason_precedes_the_options(self):
        """The tension beat comes before the comparison, never after it."""
        html = render(load_fixture())
        reason = html.index("Undecided because:")
        grid = html.index('<table class="afk-grid"')
        self.assertLess(reason, grid)

    def test_a_convention_cited_by_path_is_decidable(self):
        """`pattern` is a grade the doctrine admits, so it must not degrade."""
        doc = load_fixture()
        card = first_component(doc, "decided_card")
        card["evidence"]["grade"] = "pattern"
        before = render(load_fixture()).count("shown as a question")
        html = render(doc)
        self.assertIn("Evidence (pattern)", html)
        self.assertEqual(html.count("shown as a question"), before,
                         "a pattern-graded card must not become a question")


class DegradeNotFail(unittest.TestCase):
    """A decided card the human cannot audit is shown as a question, not dropped."""

    def decided(self, **drop):
        doc = load_fixture()
        for rnd in doc["rounds"]:
            for item in rnd["items"]:
                if item["id"] == "D-2":
                    item.update(drop)
        return doc

    def gaps_of(self, doc, item_id="D-2"):
        for rnd in schema.load(doc)["rounds"]:
            for item in rnd["items"]:
                if item["id"] == item_id:
                    return item
        raise AssertionError("%s vanished" % item_id)

    def test_each_missing_contract_field_degrades(self):
        for field in schema.DECIDED_CONTRACT:
            if field == "decision":
                continue
            item = self.gaps_of(self.decided(**{field: None}))
            self.assertEqual(item["component"], "confirm_row")
            self.assertIn(field, item["degraded_gaps"])

    def test_runner_up_naming_no_listed_alternative_degrades(self):
        item = self.gaps_of(self.decided(
            why_beat={"runner_up_id": "not-listed", "sentence": "it lost"}))
        self.assertEqual(item["component"], "confirm_row")
        self.assertIn("why_beat", item["degraded_gaps"])

    def test_a_degraded_card_says_so_on_the_page(self):
        html = render(self.decided(reverse=None))
        self.assertIn("afk-degraded", html)
        self.assertIn("reverse", html)

    def test_scope_depending_on_a_missing_id_degrades(self):
        item = self.gaps_of(self.decided(scope={"hl": "none", "depends_on": ["Q-404"]}))
        self.assertEqual(item["component"], "confirm_row")
        self.assertIn("scope", item["degraded_gaps"])

    def test_scope_may_depend_forward_on_a_later_card(self):
        item = self.gaps_of(self.decided(scope={"hl": "none", "depends_on": ["Q-2"]}))
        self.assertEqual(item["component"], "decided_card")

    def test_a_decided_card_with_no_decision_is_a_hard_failure(self):
        with self.assertRaises(schema.ContractError):
            schema.load(self.decided(decision=None))


class HardFailures(unittest.TestCase):
    """Everything that is not an unauditable decided card stops the render."""

    def mutate(self, change):
        doc = load_fixture()
        change(doc)
        with self.assertRaises(schema.ContractError):
            schema.load(doc)

    def rounds(self, doc):
        return {r["round"]: r for r in doc["rounds"]}

    def test_an_unknown_key_on_the_document(self):
        self.mutate(lambda d: d.__setitem__("grill", "requirements"))

    def test_an_unknown_key_on_a_round(self):
        self.mutate(lambda d: self.rounds(d)[2].__setitem__("headr", {}))

    def test_an_unknown_key_on_a_round_header(self):
        self.mutate(lambda d: self.rounds(d)[2]["header"].__setitem__("tgt", 3))

    def test_a_header_may_carry_its_own_component_tag(self):
        """The contract calls it a component, so an author writes the tag."""
        doc = load_fixture()
        self.rounds(doc)[2]["header"]["component"] = "round_header"
        schema.load(doc)

    def test_a_header_tagged_as_another_component_is_refused(self):
        self.mutate(lambda d: self.rounds(d)[2]["header"]
                    .__setitem__("component", "debate_card"))

    def test_an_unknown_key_on_a_card(self):
        """A misspelt field is the common authoring error, and it renders nothing."""
        self.mutate(lambda d: self.rounds(d)[2]["items"][0].__setitem__("contex", "lost"))

    def test_the_finding_names_the_key(self):
        doc = load_fixture()
        self.rounds(doc)[2]["items"][0]["contex"] = "lost"
        with self.assertRaises(schema.ContractError) as caught:
            schema.load(doc)
        self.assertIn("contex", str(caught.exception))

    def test_unknown_component(self):
        self.mutate(lambda d: self.rounds(d)[2]["items"][0].__setitem__("component", "wat"))

    def test_duplicate_item_id(self):
        self.mutate(lambda d: self.rounds(d)[2]["items"][0].__setitem__("id", "C-9"))

    def test_two_current_rounds(self):
        self.mutate(lambda d: self.rounds(d)[1].__setitem__("state", "current"))

    def test_no_current_round(self):
        self.mutate(lambda d: self.rounds(d)[2].__setitem__("state", "settled"))

    def test_missing_field_on_another_component(self):
        self.mutate(lambda d: self.rounds(d)[2]["items"][0].__setitem__("question", ""))

    def test_recommendation_naming_no_option(self):
        self.mutate(lambda d: self.rounds(d)[2]["items"][0].__setitem__("recommended", "Z"))

    def test_settled_state_and_settled_card_travel_together(self):
        self.mutate(lambda d: self.rounds(d)[2]["items"][0].__setitem__("state", "settled"))

    def test_depends_on_naming_a_missing_id(self):
        self.mutate(lambda d: self.rounds(d)[2]["items"][0]
                    .__setitem__("depends_on", ["Q-404"]))

    def test_a_non_integer_target_is_refused(self):
        self.mutate(lambda d: self.rounds(d)[2]["header"].__setitem__("target", "a few"))


class NoCaps(unittest.TestCase):
    """Round size follows what is being decided. Nothing here bounds it."""

    def rounds(self, doc):
        return {r["round"]: r for r in doc["rounds"]}

    def test_a_round_needs_no_target_at_all(self):
        doc = load_fixture()
        del self.rounds(doc)[2]["header"]["target"]
        html = render(doc)
        self.assertIn("Round R-2 — ", html)
        # The heading itself, not everything above it: the inlined stylesheet
        # sits in that prefix and its prose is not under test.
        heading = html.split('<h2 class="afk-h">')[1].split("</h2>")[0]
        self.assertNotIn(" of ", heading)

    def test_a_round_past_its_stated_target_renders(self):
        doc = load_fixture()
        self.rounds(doc)[2]["header"]["target"] = 1
        self.assertIn("Round R-2 of 1", render(doc))

    def test_an_optional_size_note_reaches_the_page(self):
        doc = load_fixture()
        self.rounds(doc)[2]["header"]["size_note"] = "eight coupled decisions"
        self.assertIn("eight coupled decisions", render(doc))

    def test_a_debate_card_renders_its_prose_body_before_the_options(self):
        doc = load_fixture()
        current = self.rounds(doc)[2]
        current["items"][0]["context"] = ("First paragraph of the explanation."
                                          + chr(10) * 2
                                          + "Second paragraph of the explanation.")
        html = render(doc)
        self.assertIn("First paragraph of the explanation.", html)
        self.assertIn("Second paragraph of the explanation.", html)
        card = html.split('data-afk-item="Q-1"')[1]
        self.assertLess(card.index("First paragraph"), card.index("afk-grid"),
                        "the explanation must precede the option grid")

    def test_every_answerable_card_type_takes_a_prose_body(self):
        doc = load_fixture()
        current = self.rounds(doc)[2]
        takes = [i for i in current["items"]
                 if i["component"] in ("decided_card", "debate_card", "confirm_row")]
        self.assertTrue(takes)
        for item in takes:
            item["context"] = "Explanation for %s." % item["id"]
        html = render(doc)
        for item in takes:
            self.assertIn("Explanation for %s." % item["id"], html)

    def test_a_signoff_packet_may_not_carry_one(self):
        """The packet is its tables; prose beside them is a field nothing renders."""
        doc = load_fixture()
        for item in self.rounds(doc)[2]["items"]:
            if item["component"] == "signoff_packet":
                item["context"] = "Would render nowhere."
        with self.assertRaises(schema.ContractError):
            render(doc)

    def test_a_decided_card_keeps_c4_under_the_heading_above_its_context(self):
        doc = load_fixture()
        for item in self.rounds(doc)[2]["items"]:
            if item["id"] == "D-2":
                item["context"] = "Background a cold reader needs."
        card = render(doc).split('data-afk-item="D-2"')[1].split("</article>")[0]
        self.assertLess(card.index("afk-why-beat"), card.index("Background a cold reader"),
                        "C-4 stays pinned to the heading; context follows it")

    def test_a_degraded_card_keeps_its_explanation(self):
        doc = load_fixture()
        for item in self.rounds(doc)[2]["items"]:
            if item["id"] == "D-2":
                item["context"] = "Background that survives the degrade."
                item["reverse"] = None
        html = render(doc)
        self.assertIn("afk-degraded", html)
        self.assertIn("Background that survives the degrade.", html)

    def test_a_large_round_renders_every_card_whole(self):
        """No truncation, no pagination, no implicit ordering limit."""
        doc = load_fixture()
        current = self.rounds(doc)[2]
        template = dict(current["items"][3])          # a confirm_row
        for n in range(200):
            item = dict(template)
            item["id"] = "C-BULK-%03d" % n
            item["question"] = "Bulk question %d" % n
            current["items"].append(item)
        tree = Tree(render(doc))
        answered = tree.find(attr_is("data-afk-input", "note"))
        self.assertEqual(len(answered), 206)
        for n in range(200):
            self.assertTrue(tree.find(attr_is("data-afk-item", "C-BULK-%03d" % n)))


class Navigability(unittest.TestCase):
    """Rules 1-3: shape before content, groups in dependency order, detail on demand."""

    def rounds(self, doc):
        return {r["round"]: r for r in doc["rounds"]}

    def current(self, doc):
        return self.rounds(doc)[2]

    def ungroup(self, doc):
        """The same round with grouping removed — a small round may skip it."""
        del self.current(doc)["header"]["groups"]
        for item in self.current(doc)["items"]:
            item.pop("group", None)
        return doc

    # --- rule 1: shape before content ------------------------------------

    def test_the_shape_line_counts_cards_and_groups(self):
        html = render(load_fixture())
        shape = html.split('class="afk-shape"')[1].split("</p>")[0]
        self.assertIn("6 cards in 3 groups", shape)

    def test_the_shape_line_names_the_independent_groups_itself(self):
        """Derived, never authored: a stale independence claim misroutes the human."""
        doc = load_fixture()
        titles = [g["title"] for g in self.current(doc)["header"]["groups"]]
        shape = render(doc).split('class="afk-shape"')[1].split("</p>")[0]
        self.assertIn(titles[0], shape)
        self.assertIn(titles[1], shape)
        self.assertIn("after %s" % titles[0], shape)

    def test_an_ungrouped_round_says_so_rather_than_claiming_groups(self):
        shape = render(self.ungroup(load_fixture())).split('class="afk-shape"')[1]
        self.assertIn("ungrouped", shape.split("</p>")[0])

    # --- rule 2: groups in dependency order ------------------------------

    def test_groups_render_in_their_declared_order(self):
        html = render(load_fixture())
        order = [chunk.split('"')[0]
                 for chunk in html.split('<section class="afk-group" id="afk-g-')[1:]]
        self.assertEqual(order, ["shape", "access", "wiring"])

    def test_a_group_listed_before_its_parent_is_refused(self):
        doc = load_fixture()
        groups = self.current(doc)["header"]["groups"]
        groups[0], groups[2] = groups[2], groups[0]
        with self.assertRaises(schema.ContractError):
            schema.load(doc)

    def test_a_card_in_an_undeclared_group_is_refused(self):
        doc = load_fixture()
        self.current(doc)["items"][0]["group"] = "nowhere"
        with self.assertRaises(schema.ContractError):
            schema.load(doc)

    def test_a_grouped_round_leaves_no_card_ungrouped(self):
        doc = load_fixture()
        del self.current(doc)["items"][0]["group"]
        with self.assertRaises(schema.ContractError):
            schema.load(doc)

    def test_a_group_on_a_card_in_an_ungrouped_round_is_refused(self):
        doc = self.ungroup(load_fixture())
        self.current(doc)["items"][0]["group"] = "shape"
        with self.assertRaises(schema.ContractError):
            schema.load(doc)

    def test_a_degrading_card_keeps_its_group_and_stays_on_the_page(self):
        """The defect this test exists for: a degrade that dropped the group
        removed the card from every group section, so the weaker question
        disappeared at the moment it needed asking."""
        doc = load_fixture()
        card = first_component(doc, "decided_card")
        card["reverse"] = None
        html = render(doc)
        self.assertIn("afk-degraded", html)
        placed = html.split('data-afk-item="%s"' % card["id"])[0]
        self.assertIn('id="afk-g-%s"' % card["group"], placed)
        self.assertNotIn("afk-g-unplaced", html)

    def test_a_card_no_group_claims_is_still_rendered(self):
        """The guard, not the contract: the schema already refuses this, so
        reaching it means a later transform dropped the field."""
        doc = schema.load(load_fixture())
        for rnd in doc["rounds"]:
            if rnd["state"] == "current":
                rnd["items"][0].pop("group")
        html = page.build(doc)
        self.assertIn("afk-g-unplaced", html)
        self.assertIn('data-afk-item="%s"' % "Q-1", html)

    # --- rule 3: heading and lede visible, detail on demand --------------

    def card(self, html, item_id):
        return html.split('data-afk-item="%s"' % item_id)[1].split("</article>")[0]

    def test_every_answerable_card_keeps_its_answer_outside_the_disclosure(self):
        """A closed card is still markable: scanning and answering are one pass."""
        tree = Tree(render(load_fixture())).root
        current = tree.find(attr_is("data-afk-state", "current"))[0]
        cards = [n for n in current.find(has("data-afk-required"))]
        self.assertTrue(cards)
        for card in cards:
            details = card.find(lambda n: n.tag == "details")
            self.assertTrue(details, "%s discloses nothing" % card.attrs["data-afk-item"])
            for control in card.find(has("data-afk-input")):
                for block in details:
                    self.assertFalse(
                        control.has_ancestor(block),
                        "%s hides an answer control behind its disclosure"
                        % card.attrs["data-afk-item"])

    def test_no_stylesheet_rule_styles_a_heading_by_its_level(self):
        """A card heading is h3 in a flat round and h4 inside a group. A bare
        `h4 {}` rule written for small labels styled every grouped card's
        decision sentence as a dim uppercase caption — caught in a browser,
        invisible to every markup assertion. Headings are styled by class."""
        css = io.open(os.path.join(SCRIPTS, "lavish", "assets", "kit.css"),
                      encoding="utf-8").read()
        for line in css.splitlines():
            stripped = line.strip()
            for level in ("h2", "h3", "h4"):
                self.assertFalse(
                    stripped.startswith(level + " {") or stripped.startswith(level + "{"),
                    "%r styles a heading by its level" % stripped)

    def test_a_debate_cards_recommendation_and_reason_precede_the_disclosure(self):
        html = render(load_fixture())
        card = self.card(html, "Q-1")
        self.assertLess(card.index("afk-rec-line"), card.index("<details"))
        self.assertLess(card.index("afk-undecided"), card.index("<details"))

    def test_the_option_grid_sits_behind_the_disclosure(self):
        card = self.card(render(load_fixture()), "Q-1")
        self.assertLess(card.index("<details"), card.index('<table class="afk-grid"'))

    def test_a_decided_cards_evidence_grade_reads_without_opening_it(self):
        html = render(load_fixture())
        card = self.card(html, "D-2")
        lede = card.split("<details")[0]
        self.assertIn("afk-why-beat", lede)
        self.assertIn("Evidence (", lede)

    def test_a_degrade_banner_never_hides_behind_the_disclosure(self):
        doc = load_fixture()
        card = first_component(doc, "decided_card")
        card["reverse"] = None
        rendered = self.card(render(doc), card["id"])
        self.assertLess(rendered.index("afk-degraded"), rendered.index("<details"))

    def test_every_disclosure_says_what_it_holds(self):
        """A summary that names nothing is a reason not to click, which turns
        rule 3 into hidden explanation."""
        html = render(load_fixture())
        labels = [chunk.split("</summary>")[0]
                  for chunk in html.split("<summary>")[1:]]
        self.assertTrue(labels)
        for label in labels:
            self.assertGreater(len(label.strip()), 8, "an unlabelled disclosure")

    # --- W-5: dependency chips -------------------------------------------

    def test_a_dependent_card_chips_its_parent_and_reads_provisional(self):
        doc = load_fixture()
        self.current(doc)["items"][0]["depends_on"] = ["Q-2"]
        card = self.card(render(doc), "Q-1")
        self.assertIn('href="#afk-i-Q-2"', card)
        self.assertIn("provisional", card)

    def test_a_dependency_already_settled_carries_no_provisional_badge(self):
        doc = load_fixture()
        self.current(doc)["items"][0]["depends_on"] = ["D-1"]
        card = self.card(render(doc), "Q-1")
        self.assertIn('href="#afk-i-D-1"', card)
        self.assertIn("afk-chip--settled", card)
        self.assertNotIn("provisional", card)

    def test_a_chip_points_at_an_element_that_exists(self):
        doc = load_fixture()
        self.current(doc)["items"][0]["depends_on"] = ["Q-2"]
        html = render(doc)
        self.assertIn('id="afk-i-Q-2"', html)


class TheTwoStrips(unittest.TestCase):
    """W-1 and W-2: where the session sits, and where this round sits in it."""

    def test_the_process_rail_lights_the_document_stage(self):
        html = render(load_fixture())
        rail = html.split('class="afk-rail"')[1].split("</nav>")[0]
        self.assertIn('afk-step--current" aria-current="step">design', rail)
        self.assertIn("afk-step--done", rail)
        self.assertIn("afk-step--upcoming", rail)

    def test_done_and_upcoming_are_derived_from_the_stage_order(self):
        """Nobody authors them, so nobody can author them wrongly."""
        doc = load_fixture()
        doc["stage"] = schema.STAGES[0]
        rail = render(doc).split('class="afk-rail"')[1].split("</nav>")[0]
        self.assertNotIn("afk-step--done", rail)
        doc["stage"] = schema.STAGES[-1]
        rail = render(doc).split('class="afk-rail"')[1].split("</nav>")[0]
        self.assertNotIn("afk-step--upcoming", rail)

    def test_a_document_with_no_stage_gets_no_rail(self):
        doc = load_fixture()
        del doc["stage"]
        self.assertNotIn("afk-rail", body_of(render(doc)))

    def test_a_stage_outside_the_chain_is_refused(self):
        doc = load_fixture()
        doc["stage"] = "brainstorm"
        with self.assertRaises(schema.ContractError):
            schema.load(doc)

    def test_one_notch_per_round_carrying_what_it_holds(self):
        html = render(load_fixture())
        strip = html.split('class="afk-strip"')[1].split("</nav>")[0]
        self.assertEqual(strip.count("<li"), 2)
        self.assertIn("afk-notch--settled", strip)
        self.assertIn("afk-notch--current", strip)
        self.assertIn("6 cards", strip)
        self.assertIn("3 groups", strip)
        self.assertIn("6 to answer", strip)

    def test_every_notch_lands_on_an_element_that_exists(self):
        """A strip is navigation; a notch pointing at nothing is worse than none."""
        html = render(load_fixture())
        strip = html.split('class="afk-strip"')[1].split("</nav>")[0]
        targets = [chunk.split('"')[0] for chunk in strip.split('href="#')[1:]]
        self.assertTrue(targets)
        for target in targets:
            self.assertIn('id="%s"' % target, html)

    def test_settled_history_is_sectioned_by_round_newest_first(self):
        doc = load_fixture()
        # A second settled round, so "newest first" has something to order.
        doc["rounds"].insert(1, {"round": 2, "state": "settled",
                                 "items": [{"component": "settled_card", "id": "D-9",
                                            "decision": "An earlier call",
                                            "round": 2, "by": "human",
                                            "evidence": "the human's own words"}]})
        for rnd in doc["rounds"]:
            if rnd["state"] == "current":
                rnd["round"] = 3
                rnd["header"]["round"] = 3
        html = render(doc)
        self.assertLess(html.index('id="afk-r-2"'), html.index('id="afk-r-1"'),
                        "settled rounds read newest first")


class ReAuditAndLedger(unittest.TestCase):
    """W-8 and W-6: what came back unmarked, and everything already settled."""

    def current(self, doc):
        for rnd in doc["rounds"]:
            if rnd["state"] == "current":
                return rnd
        raise AssertionError("fixture has no current round")

    def flag(self, doc, ids):
        self.current(doc)["header"]["re_audit"] = ids
        return doc

    # --- the re-audit strip ----------------------------------------------

    def test_an_unmarked_decision_opens_the_round(self):
        html = body_of(render(self.flag(load_fixture(), ["D-2"])))
        strip = html.split("afk-reaudit")[1]
        self.assertIn('href="#afk-i-D-2"', strip)
        round_section = html.split('<section class="afk-round"')[1]
        self.assertLess(round_section.index("afk-reaudit"),
                        round_section.index("afk-round-header"),
                        "the strip reads before the round's own header")

    def test_the_line_carries_the_decision_and_its_citation_from_the_card(self):
        """Ids are authored; the words come off the card the round presents."""
        doc = self.flag(load_fixture(), ["D-2"])
        card = first_component(doc, "decided_card")
        line = body_of(render(doc)).split("afk-reaudit")[1].split("</ul>")[0]
        self.assertIn(card["decision"], line)
        self.assertIn(card["evidence"]["cite"], line)

    def test_no_flag_no_strip(self):
        self.assertNotIn("afk-reaudit", body_of(render(load_fixture())))

    def test_only_the_unanswered_are_listed(self):
        """One trigger: the strip is a fact about unmarked decisions, not a
        second place to put warnings."""
        line = body_of(render(self.flag(load_fixture(), ["D-2"]))).split("afk-reaudit")[1]
        self.assertEqual(line.split("</ul>")[0].count("<li>"), 1)

    def test_a_flag_naming_a_settled_card_is_refused(self):
        doc = load_fixture()
        settled = [i for r in doc["rounds"] for i in r["items"]
                   if i["component"] == "settled_card"]
        self.current(doc)["items"].append(dict(settled[0], id="D-7"))
        self.flag(doc, ["D-7"])
        with self.assertRaises(schema.ContractError):
            schema.load(doc)

    def test_a_flag_naming_a_card_this_round_does_not_present_is_refused(self):
        """An unmarked card is re-asked, not merely reported."""
        with self.assertRaises(schema.ContractError):
            schema.load(self.flag(load_fixture(), ["D-1"]))
        with self.assertRaises(schema.ContractError):
            schema.load(self.flag(load_fixture(), ["D-404"]))

    # --- the decision ledger ---------------------------------------------

    def test_the_ledger_carries_one_row_per_settled_decision(self):
        html = body_of(render(load_fixture()))
        ledger = html.split('<details class="afk-ledger"')[1]
        self.assertEqual(ledger.split("</tbody>")[0].count("<tr>"), 2)  # header + 1
        self.assertIn("1 settled", ledger)

    def test_a_ledger_row_links_to_its_card_rather_than_restating_it(self):
        """The card is the record. A ledger holding a copy of the evidence
        would be a second home for it, and the two would drift."""
        html = body_of(render(load_fixture()))
        ledger = html.split('<details class="afk-ledger"')[1]
        self.assertIn('href="#afk-i-D-1"', ledger)
        settled_card = html.split('data-afk-item="D-1"')[1].split("</article>")[0]
        sentence = "explicit"
        self.assertIn(sentence, settled_card)
        self.assertNotIn("What settled it", ledger)

    def test_the_ledger_sits_at_the_bottom_and_starts_closed(self):
        html = body_of(render(load_fixture()))
        self.assertGreater(html.index("afk-ledger"), html.index("afk-settled"))
        opening = html.split('<details class="afk-ledger"')[1].split(">")[0]
        self.assertNotIn("open", opening)

    def test_a_session_with_nothing_settled_has_no_ledger(self):
        doc = load_fixture()
        doc["rounds"] = [r for r in doc["rounds"] if r["state"] == "current"]
        doc["rounds"][0]["header"]["settled_last_round"] = []
        self.assertNotIn("afk-ledger", body_of(render(doc)))


class TableLayoutGroups(unittest.TestCase):
    """A group may lay its members out as rows instead of cards.

    Two upstream pages ask dozens of one-mark questions, where a card stack
    buries the list. The items stay flat — a row carries the same anatomy as a
    card — so anchors, the ledger, the re-audit strip, the chips, persistence
    and the send read either layout without knowing which one drew the item.
    """

    def current(self, doc):
        for rnd in doc["rounds"]:
            if rnd["state"] == "current":
                return rnd
        raise AssertionError("fixture has no current round")

    def table_doc(self, rows=3, layout="table"):
        """The fixture plus one more group holding `rows` confirm rows.

        `layout=None` drops the field, which is how every document written
        before it existed reads.
        """
        doc = load_fixture()
        current = self.current(doc)
        group = {"id": "bulk", "title": "One mark each"}
        if layout is not None:
            group["layout"] = layout
        current["header"]["groups"].append(group)
        template = next(i for i in current["items"]
                        if i["component"] == "confirm_row")
        for n in range(rows):
            item = copy.deepcopy(template)
            item.update(id="T-%d" % n, question="Row question %d" % n,
                        group="bulk")
            current["items"].append(item)
        return doc

    def group_section(self, html, group_id="bulk"):
        return body_of(html).split('id="afk-g-%s"' % group_id)[1].split("</section>")[0]

    def rows_of(self, html, group_id="bulk"):
        tree = Tree(self.group_section(html, group_id))
        return [n for n in tree.find(has("data-afk-item")) if n.tag == "tr"]

    # --- the shape --------------------------------------------------------

    def test_a_table_group_renders_one_row_per_item(self):
        """One `<tr>` per item, and the items themselves stay flat: nothing is
        nested inside a container item, so every walk over `[data-afk-item]`
        still finds one element per question."""
        html = render(self.table_doc(rows=4))
        rows = self.rows_of(html)
        self.assertEqual(len(rows), 4)
        self.assertEqual([r.attrs["data-afk-item"] for r in rows],
                         ["T-0", "T-1", "T-2", "T-3"])
        self.assertNotIn("afk-card--confirm", self.group_section(html))

    def test_every_row_carries_the_item_anatomy(self):
        """The anchor is what the decision ledger and the re-audit strip link
        to, so it must land on the row rather than on a wrapper."""
        html = render(self.table_doc())
        for row in self.rows_of(html):
            item_id = row.attrs["data-afk-item"]
            self.assertEqual(row.attrs.get("id"), "afk-i-%s" % item_id)
            self.assertEqual(row.attrs.get("data-afk-state"), "open")

    def test_every_row_anchor_resolves_to_an_element_that_exists(self):
        html = render(self.table_doc())
        for row in self.rows_of(html):
            self.assertIn('id="%s"' % row.attrs["id"], html)

    def test_every_row_mark_is_required_and_sits_in_the_row(self):
        """Silence is not agreement in either layout: one choice control and
        one note field per row, both inside the row the send walks."""
        html = render(self.table_doc())
        for row in self.rows_of(html):
            self.assertEqual(row.attrs.get("data-afk-required"), "1",
                             row.attrs["data-afk-item"])
            self.assertEqual(len(row.find(attr_is("data-afk-input", "choice"))), 1)
            self.assertEqual(len(row.find(attr_is("data-afk-input", "note"))), 1)

    def test_a_rows_answer_grammar_is_the_confirm_grammar(self):
        """One home for the answer grammar: the row offers exactly the tokens
        a confirm card offers, so the composed response cannot depend on the
        frame that drew the question."""
        html = render(self.table_doc(rows=1))
        row = self.rows_of(html)[0]
        values = [n.attrs.get("value") for n in row.find(attr_is("type", "radio"))]
        self.assertEqual(values, ["accept", "raise", "write-in"])

    def test_a_row_hides_no_answer_control_behind_its_disclosure(self):
        """Scanning and answering stay one pass, exactly as on a card."""
        html = render(self.table_doc())
        for row in self.rows_of(html):
            details = row.find(lambda n: n.tag == "details")
            self.assertTrue(details, "%s discloses nothing" % row.attrs["data-afk-item"])
            for control in row.find(has("data-afk-input")):
                for block in details:
                    self.assertFalse(control.has_ancestor(block))

    def test_the_row_disclosure_holds_the_argument_and_the_citation(self):
        """The cells carry the scannable facts; `why`, `cite`, `context` and
        each alternative's reason open on demand, so the group keeps one row
        per item at any width."""
        doc = self.table_doc(rows=1)
        for item in self.current(doc)["items"]:
            if item["id"] == "T-0":
                item["context"] = "Background a cold reader needs."
        row = self.group_section(render(doc))
        detail = row.split("<details")[1]
        for needle in ("Background a cold reader needs.",
                       "Nothing in this round changes the failure profile.",
                       "example/other.ext:88", "hides slow failures"):
            self.assertIn(needle, detail, needle)
        self.assertIn("Row question 0", row.split("<details")[0])

    def test_wide_rows_scroll_inside_the_shared_wrapper(self):
        """The same wrapper the decision ledger uses — one home for the
        horizontal-scroll behaviour, not a second one for this table."""
        section = self.group_section(render(self.table_doc()))
        self.assertIn("afk-grid-wrap", section)

    # --- what may sit in a table group ------------------------------------

    def test_a_non_confirm_row_in_a_table_group_is_refused(self):
        """Every other component carries more than a row can hold — a decided
        card's six-field contract and its narrative body would be truncated
        into a cell or make the row unreadable."""
        for component in ("debate_card", "decided_card", "signoff_packet"):
            doc = self.table_doc()
            first_component(doc, component)["group"] = "bulk"
            with self.assertRaises(schema.ContractError, msg=component):
                schema.load(doc)

    def test_the_refusal_names_the_item_and_its_component(self):
        doc = self.table_doc()
        card = first_component(doc, "debate_card")
        card["group"] = "bulk"
        with self.assertRaises(schema.ContractError) as caught:
            schema.load(doc)
        self.assertIn(card["id"], str(caught.exception))
        self.assertIn("debate_card", str(caught.exception))

    def test_a_settled_card_in_a_table_group_is_left_alone(self):
        """A settled card renders in the history section, never in the group,
        so the row-shape rule has nothing to say about it."""
        doc = self.table_doc()
        settled = [i for r in doc["rounds"] for i in r["items"]
                   if i["component"] == "settled_card"][0]
        self.current(doc)["items"].append(
            dict(settled, id="D-8", group="bulk", state="settled"))
        self.assertEqual(len(self.rows_of(render(doc))), 3)

    def test_a_degraded_decided_card_renders_as_a_row_with_its_banner(self):
        """The degrade path lands in the table: the card is a confirm_row by
        the time it is placed, and its banner is a warning, so it shows in the
        row rather than behind the disclosure."""
        doc = self.table_doc()
        card = first_component(doc, "decided_card")
        card["group"] = "bulk"
        card["reverse"] = None
        html = render(doc)
        ids = [r.attrs["data-afk-item"] for r in self.rows_of(html)]
        self.assertIn(card["id"], ids)
        row = self.group_section(html).split('data-afk-item="%s"' % card["id"])[1]
        row = row.split("</tr>")[0]
        self.assertIn("afk-degraded", row)
        self.assertIn("reverse", row)
        self.assertLess(row.index("afk-degraded"), row.index("<details"))

    # --- the layout field itself ------------------------------------------

    def test_an_unknown_layout_value_is_refused(self):
        """A layout the renderer does not know would silently fall back to
        cards, which is the class of failure nobody is told about."""
        for value in ("rows", "grid", "", "Table", "cards "):
            doc = self.table_doc()
            self.current(doc)["header"]["groups"][-1]["layout"] = value
            with self.assertRaises(schema.ContractError, msg=repr(value)):
                schema.load(doc)

    def test_cards_layout_and_an_absent_layout_render_the_same_page(self):
        """The default is the behaviour every document written before the field
        existed already had, byte for byte."""
        declared = render(self.table_doc(layout="cards"))
        absent = render(self.table_doc(layout=None))
        self.assertEqual(declared, absent)
        self.assertNotIn("afk-rows", body_of(absent))
        self.assertEqual(len(self.rows_of(absent)), 0)

    def test_the_shipped_sample_is_untouched_by_the_new_field(self):
        html = render(load_fixture())
        self.assertNotIn("afk-rows", body_of(html))
        self.assertEqual(schema.group_layout({"id": "x", "title": "y"}), "cards")

    def test_a_table_group_and_a_card_group_coexist_in_one_round(self):
        """One round, both layouts: the shape line still counts every group and
        every card, and each group renders in its declared order."""
        html = render(self.table_doc(rows=2))
        body = body_of(html)
        order = [chunk.split('"')[0]
                 for chunk in body.split('<section class="afk-group" id="afk-g-')[1:]]
        self.assertEqual(order, ["shape", "access", "wiring", "bulk"])
        self.assertIn("8 cards in 4 groups", body.split('class="afk-shape"')[1])
        self.assertIn("afk-card--debate", self.group_section(html, "shape"))
        self.assertEqual(len(self.rows_of(html)), 2)
        # Every item in the round is still one element the send walks.
        tree = Tree(html)
        current = tree.find(attr_is("data-afk-state", "current"))[0]
        answerable = [n for n in current.find(has("data-afk-item"))
                      if n.find(attr_is("data-afk-input", "choice"))]
        self.assertEqual(len(answerable), 8)


class DeadLinks(unittest.TestCase):
    """A dead relative href is the one page failure only the human meets."""

    def warn(self, href, artifact_dir):
        """The count, with the warning itself kept out of the suite's output."""
        doc = {"rounds": [{"round": 2, "header": {"links": [{"href": href}]}}]}
        held, sys.stderr = sys.stderr, io.StringIO()
        try:
            return lavish_render.warn_dead_links(doc, artifact_dir)
        finally:
            sys.stderr = held

    def test_a_missing_relative_target_warns(self):
        self.assertEqual(self.warn("no/such/file.md", HERE), 1)

    def test_a_resolvable_relative_target_is_quiet(self):
        self.assertEqual(self.warn("samples/lavish-round.json", HERE), 0)
        self.assertEqual(self.warn("samples/lavish-round.json#anchor", HERE), 0)

    def test_absolute_and_in_page_targets_are_left_alone(self):
        for href in ("https://example.invalid/x", "mailto:someone@example.invalid",
                     "//example.invalid/x", "/absolute/path.md", "#section"):
            self.assertEqual(self.warn(href, HERE), 0, href)

    def test_the_shipped_example_links_at_nothing_dead(self):
        """The example every author copies must never print a warning.

        A sample that warns on every run teaches that warnings from this tool
        are background noise, which costs more than the demonstration is worth.
        """
        self.assertEqual(lavish_render.warn_dead_links(
            load_fixture(), os.path.join(HERE, "samples")), 0)

    def test_a_dead_link_never_blocks_the_render(self):
        out = os.path.join(HERE, "samples", "does-not-matter.html")
        code = lavish_render.main([FIXTURE, "--check", "-o", out])
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(out), "--check writes nothing")


if __name__ == "__main__":
    unittest.main()
