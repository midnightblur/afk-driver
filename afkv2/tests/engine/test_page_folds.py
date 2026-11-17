"""Folds on a version 2 page (steer of round 5): the Sections block, each section, each question for others, each
worked example, their blocks and the settled block fold to their heads by a button with aria-expanded. After round
1, an element that did not change starts closed. The page script keeps each fold per viewer, session and round,
and a page with no storage still folds. The shipped runtime.js runs in Node against the rendered page, in the
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
KEY = "afkv2-fold:s1"
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


def test_after_round_1_an_element_that_did_not_change_starts_closed_and_a_changed_one_open():
    found = starts(build(document()))
    assert {key for key, state in found.items() if state == "open"} == {
        "afkv2-sections", "afkv2-examples", "afkv2-questions", "afkv2-settled", "sec-scope", "sec-format", "ex-bad"}
    assert found["sec-later"] == found["q-size"] == found["ex-plain"] == "closed"


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
    assert folds["sec-later"] == {"shut": True, "expanded": "false"}
    assert folds["sec-scope"] == {"shut": False, "expanded": "true"}


def test_a_click_folds_and_opens_and_the_state_is_kept_for_the_round():
    first = run(clicks=["sec-scope", "sec-later"])
    assert first["folds"]["sec-scope"] == {"shut": True, "expanded": "false"}
    assert first["folds"]["sec-later"] == {"shut": False, "expanded": "true"}
    assert json.loads(first["storage"][KEY]) == {"round": "3", "open": {"sec-scope": 0, "sec-later": 1}}
    again = run(held={"name": first["name"], "storage": first["storage"]})["folds"]
    assert again["sec-scope"]["shut"] and not again["sec-later"]["shut"]


def test_a_new_round_starts_from_the_start_states():
    stored = {KEY: json.dumps({"round": "2", "open": {"sec-scope": 0}})}
    folds = run(held={"name": "", "storage": stored})["folds"]
    assert folds["sec-scope"] == {"shut": False, "expanded": "true"}


def test_a_page_with_no_storage_still_folds():
    folds = run(clicks=["sec-scope"], broken_storage=True)["folds"]
    assert folds["sec-scope"] == {"shut": True, "expanded": "false"}
