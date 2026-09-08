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

    def test_item_ids_unique_and_headings_come_first(self):
        seen = set()
        for node in self.tree.find(has("data-afk-item")):
            item_id = node.attrs["data-afk-item"]
            self.assertNotIn(item_id, seen)
            seen.add(item_id)
            self.assertTrue(node.children, "%s has no heading" % item_id)
            self.assertIn(node.children[0].tag, ("h2", "h3"),
                          "%s must open with its one-line heading" % item_id)

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

    def test_settled_history_sits_below_the_current_round(self):
        order = [n.attrs.get("id") for n in self.tree.find(has("id"))
                 if n.attrs.get("id") in ("afk-open", "afk-settled")]
        self.assertEqual(order, ["afk-open", "afk-settled"])


class SilenceRule(unittest.TestCase):
    """The per-grill rule the runtime applies from the card's required flag."""

    def mark(self, **fields):
        item = {"component": "decided_card", "evidence": {"grade": "repo"}}
        item.update(fields)
        return schema.required_mark(item)

    def test_requirements_grill_always_needs_a_mark(self):
        self.assertTrue(self.mark(grill="requirements"))
        self.assertTrue(self.mark(grill="requirements", evidence={"grade": "spec"}))

    def test_elsewhere_only_spec_graded_needs_a_mark(self):
        self.assertFalse(self.mark(grill="solution"))
        self.assertFalse(self.mark(grill="verification"))
        self.assertTrue(self.mark(grill="solution", evidence={"grade": "spec"}))

    def test_every_other_answerable_class_always_needs_a_mark(self):
        for component in ("debate_card", "confirm_row", "signoff_packet"):
            self.assertTrue(schema.required_mark({"component": component}))


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

    def test_unknown_grill(self):
        self.mutate(lambda d: d.__setitem__("grill", "guessing"))

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
        self.assertNotIn(" of ", html.split("</h2>")[0])

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
        for item in current["items"]:
            item["context"] = "Explanation for %s." % item["id"]
        html = render(doc)
        for item in current["items"]:
            if item["component"] == "signoff_packet":
                continue
            self.assertIn("Explanation for %s." % item["id"], html)

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
            json.load(open(FIXTURE, encoding="utf-8")),
            os.path.join(HERE, "samples")), 0)

    def test_a_dead_link_never_blocks_the_render(self):
        out = os.path.join(HERE, "samples", "does-not-matter.html")
        code = lavish_render.main([FIXTURE, "--check", "-o", out])
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(out), "--check writes nothing")


if __name__ == "__main__":
    unittest.main()
