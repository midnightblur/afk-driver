"""Folds on a version 2 page (steer of round 5): the Sections block, each section, each question for others, each
worked example, their blocks and the settled block fold to their heads by a button with aria-expanded. Every fold
and every card, settled ones too, starts open on every round (steer of round 7). The page script keeps each fold per
viewer, session and round, and a page with no storage still folds. The shipped runtime.js runs in Node against the rendered page, in the
document stand-in of the tick tests."""

import json
import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
for folder in (PLUGIN / "scripts", ENGINE_DIR, Path(__file__).resolve().parent):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
from shell import page  # noqa: E402
from test_page_parts_v2 import document  # noqa: E402
from test_page_script_ticks import DRIVER, RUNTIME, tree  # noqa: E402

BUTTON = re.compile(r'<button type="button" class="afkv2-fold-btn" aria-expanded="true" aria-controls="([^"]+)" '
                    r'data-afkv2-fold-key="\1" data-lavish-action="afkv2-fold" aria-label="Fold or open: [^"]+">'
                    r'</button>')
START = re.compile(r'id="([^"]+)"[^>]*data-afkv2-foldable="\1" data-afkv2-start="(open|closed)"')
FOLDED = ["afkv2-sections", "sec-scope", "sec-format", "sec-later", "afkv2-examples", "ex-plain", "ex-big", "ex-bad",
          "afkv2-questions", "q-format", "q-size", "q-cols", "q-drop", "q-assume"]
SHUT_RULE = ".afkv2-shut > :not(.afkv2-fold-head) { display: none !important; }"
KEY = "afkv2-fold:v2:s1"
SETTLED_BLOCK = "afkv2-settled"
FOLDABLE = 'data-afkv2-foldable="{}"'
FOLDABLE_ANY = r'data-afkv2-foldable="[^"]*"'
# A storage that throws on every read and write, as a sandboxed frame with an opaque origin does.
STORAGE_OPEN = "global.localStorage = {"
STORAGE_CLOSE = "removeItem: function (k) { delete store[k]; }\n};"
# The run reports each fold: its classes hold afkv2-shut or not, and its button's aria-expanded.
REPORT = """
const folds = {};
const SHUT = 'afkv2-shut';
root.querySelectorAll('[data-afkv2-foldable]').forEach(function (el) {
  const button = root.querySelector('button[data-afkv2-fold-key="' + el.id + '"]');
  folds[el.id] = { shut: el.classList.contains(SHUT), expanded: button.getAttribute('aria-expanded') };
});
console.log(JSON.stringify({ folds: folds, storage: store, name: window.name }));
"""
CLICKS = """
function DENIED() { throw new Error('denied'); }
eval(input.script);
(input.clicks || []).forEach(function (key) { fire(root.querySelector('button[data-afkv2-fold-key="' + key + '"]'), 'click'); });
"""


def build(doc):
    return page.build(engine.READERS[doc["schema"]](doc))


def starts(html):
    return dict(START.findall(html))


def run(doc=None, clicks=(), held=None, broken_storage=False):
    """Run runtime.js on the rendered page, click the fold buttons of `clicks`, and answer each fold's state."""
    held = held or {"name": "", "storage": {}}
    driver = DRIVER.split("eval(input.script);")[0] + CLICKS + REPORT
    if broken_storage:
        assert STORAGE_OPEN in driver and STORAGE_CLOSE in driver
        driver = driver.replace(STORAGE_OPEN, STORAGE_OPEN + " getItem: DENIED, setItem: DENIED, _shadowed: {")
        driver = driver.replace(STORAGE_CLOSE, STORAGE_CLOSE[:-1] + " };")
    payload = {"tree": tree(doc or document()), "script": RUNTIME, "actions": [], "lavish": True, "preset": {},
               "clicks": list(clicks), **held}
    result = subprocess.run(["node", "-e", driver], input=json.dumps(payload), capture_output=True, text=True,
                            encoding="utf-8", check=True)
    return json.loads(result.stdout)


# --- the markup


def test_each_block_section_question_and_example_has_a_fold_button_that_names_its_element():
    html = build(document())
    assert sorted(BUTTON.findall(html)) == sorted([*FOLDED, SETTLED_BLOCK])


def test_a_merged_or_removed_section_stays_1_line_with_no_fold():
    html = build(document())
    assert not {FOLDABLE.format(section) for section in ("sec-old", "sec-gone")} & set(re.findall(FOLDABLE_ANY, html))


def test_after_round_1_every_element_starts_open_changed_or_not():
    assert set(starts(build(document())).values()) == {"open"}


def test_on_round_1_every_element_starts_open():
    doc = document()
    doc["rounds"] = [{**doc["rounds"][0], "state": "current"}]
    for kind in ("sections", "examples", "questions"):
        for entry in doc[kind]:
            entry["changes"] = [line for line in entry["changes"] if line["round"] == 1]
    assert set(starts(build(doc)).values()) == {"open"}


def test_the_folded_state_hides_all_but_the_head():
    css = (ENGINE_DIR / "shell" / "kit.css").read_text("utf-8")
    assert SHUT_RULE in css.splitlines()


# --- the page script


def test_the_script_applies_the_start_state_and_aria_expanded():
    folds = run()["folds"]
    assert set(folds) == {*FOLDED, SETTLED_BLOCK}
    assert all(state == {"shut": False, "expanded": "true"} for state in folds.values())


def test_a_click_folds_and_opens_and_the_state_is_kept_for_the_round():
    first = run(clicks=["sec-scope", "sec-later", "sec-later"])
    assert first["folds"]["sec-scope"] == {"shut": True, "expanded": "false"}
    assert first["folds"]["sec-later"] == {"shut": False, "expanded": "true"}
    assert json.loads(first["storage"][KEY]) == {"round": "3", "open": {"sec-scope": 0, "sec-later": 1}}
    again = run(held={"name": first["name"], "storage": first["storage"]})["folds"]
    assert again["sec-scope"]["shut"] and not again["sec-later"]["shut"]


def test_a_store_from_before_the_open_default_shuts_nothing():
    stale = json.dumps({"round": "3", "open": {"sec-scope": 0}})
    folds = run(held={"name": "", "storage": {"afkv2-fold:s1": stale}})["folds"]
    assert not any(state["shut"] for state in folds.values())


def test_a_new_round_starts_from_the_start_states():
    stored = {KEY: json.dumps({"round": "2", "open": {"sec-scope": 0}})}
    folds = run(held={"name": "", "storage": stored})["folds"]
    assert folds["sec-scope"] == {"shut": False, "expanded": "true"}


def test_a_page_with_no_storage_still_folds():
    folds = run(clicks=["sec-scope"], broken_storage=True)["folds"]
    assert folds["sec-scope"] == {"shut": True, "expanded": "false"}


# --- the cards: tips.js folds each card by its heading; a fresh render folds none, settled cards included

TIPS = (ENGINE_DIR / "shell" / "tips.js").read_text("utf-8")
TIPS_CUT = "  function start() {"
OLD_NAV_KEY = "afkv2-nav:s1"
# The stand-in parses no HTML: the rail's innerHTML gives the 3 children the rail script reads.
CARDS = """
Node.prototype.insertBefore = function (c, ref) {
  c.parentElement = this; const i = this.children.indexOf(ref); this.children.splice(i < 0 ? 0 : i, 0, c); return c; };
Node.prototype.cloneNode = function () {
  const copy = new Node(this.tagName, this.attrs);
  copy.text = this.text;
  this.children.forEach(function (c) { copy.appendChild(c.cloneNode()); });
  return copy;
};
Node.prototype.remove = function () { if (this.parentElement) this.parentElement.removeChild(this); };
Object.defineProperty(Node.prototype, 'innerHTML', { set: function () {
  const self = this;
  self.children = [];
  ['afkv2-nav-head', 'afkv2-nav-tools', 'afkv2-nav-list'].forEach(function (id) { self.appendChild(new Node('div', { id: id })); });
  withToggle(self);
} });
function withToggle(el) {
  if (el.classList && !el.classList.toggle) el.classList.toggle = function (c, on) {
    if (on === undefined) on = !el.classList.contains(c);
    if (on) el.classList.add(c); else el.classList.remove(c);
  };
  el.children.forEach(withToggle);
}
withToggle(root);
const createElement = document.createElement;
document.createElement = function (tag) { const el = createElement(tag); withToggle(el); return el; };
document.createTextNode = function (text) { const el = createElement('span'); el.text = String(text); return el; };
window.addEventListener = function () {};
eval(input.tips.split(input.cut)[0] + 'navChrome();})();');
const cards = root.querySelectorAll('[data-afkv2-item]').filter(function (el) { return el.tagName !== 'TR'; });
const FOLDED_CARD = 'afkv2-collapsed';
console.log(JSON.stringify({ cards: cards.map(function (el) {
  return { id: el.getAttribute('data-afkv2-item'), state: el.getAttribute('data-afkv2-state'),
           collapsed: el.classList.contains(FOLDED_CARD) };
}) }));
"""


def run_cards(storage=None):
    """Run the card fold defaults of the shipped tips.js on the rendered page, and answer each card's state."""
    assert TIPS_CUT in TIPS
    driver = DRIVER.split("eval(input.script);")[0] + CARDS
    payload = {"tree": tree(document()), "script": "", "actions": [], "lavish": True, "preset": {},
               "name": "", "storage": storage or {}, "tips": TIPS, "cut": TIPS_CUT}
    result = subprocess.run(["node", "-e", driver], input=json.dumps(payload), capture_output=True, text=True,
                            encoding="utf-8", check=True)
    return json.loads(result.stdout)["cards"]


def test_a_fresh_render_folds_no_card_settled_or_open():
    cards = run_cards()
    assert {card["state"] for card in cards} >= {"settled", "open"}
    assert [card["id"] for card in cards if card["collapsed"]] == []


def test_a_card_store_from_before_the_open_default_folds_no_card():
    stale = json.dumps({"i-closed": 0, "i-format": 0, "i-scope": 0})
    assert [card["id"] for card in run_cards({OLD_NAV_KEY: stale}) if card["collapsed"]] == []
