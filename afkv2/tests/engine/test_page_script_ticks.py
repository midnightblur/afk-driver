"""The page script on the questions for others (SDD §9b row "Ticks on a question for others", SDD §9 rows "Ticks"
and "Filter", ADR-0004 design): 1 queued answer per question, replaced on each change, and the role filter, which
sends nothing. The shipped runtime.js runs in Node against the rendered page in a small document stand-in; the
queued answers then go through the engine's own poll and ingest."""

import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
for folder in (PLUGIN / "scripts", ENGINE_DIR, Path(__file__).resolve().parent):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
from shell import page  # noqa: E402
from test_page_parts_v2 import document  # noqa: E402

RUNTIME = (ENGINE_DIR / "shell" / "runtime.js").read_text("utf-8")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
TICK_TAG = "afkv2-tick"
QUESTIONS = ["q-format", "q-size", "q-cols", "q-drop", "q-assume"]

# A document stand-in: the parts of the DOM that runtime.js calls, over the parsed page tree.
DRIVER = r"""
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const queued = [];
const copied = [];
function attrMatch(el, part) {
  const m = part.match(/^\[([\w-]+)(?:(\^?=)["']?(.*?)["']?)?\]$/);
  if (!el.attrs) return false;
  const value = el.getAttribute(m[1]);
  if (value === null) return false;
  if (!m[2]) return true;
  return m[2] === '=' ? value === m[3] : value.indexOf(m[3]) === 0;
}
function compound(el, sel) {
  if (!el.attrs) return false;
  const tag = sel.match(/^[a-zA-Z][\w-]*/);
  if (tag && el.tagName !== tag[0].toUpperCase()) return false;
  const parts = sel.slice(tag ? tag[0].length : 0).match(/#[\w-]+|\.[\w-]+|\[[^\]]+\]|:[\w-]+/g) || [];
  return parts.every(function (part) {
    if (part[0] === '#') return el.getAttribute('id') === part.slice(1);
    if (part[0] === '.') return (el.getAttribute('class') || '').split(/\s+/).indexOf(part.slice(1)) >= 0;
    if (part === ':checked') return !!el.checked;
    return attrMatch(el, part);
  });
}
function matches(el, selector) {
  const steps = selector.trim().split(/\s+/);
  if (!compound(el, steps[steps.length - 1])) return false;
  let at = el.parentElement, i = steps.length - 2;
  while (i >= 0 && at) { if (compound(at, steps[i])) i--; at = at.parentElement; }
  return i < 0;
}
function all(root, selector) {
  const out = [];
  (function walk(node) { node.children.forEach(function (c) { if (matches(c, selector)) out.push(c); walk(c); }); })(root);
  return out;
}
class Node {
  constructor(tag, attrs) {
    this.tagName = tag.toUpperCase(); this.attrs = Object.assign({}, attrs); this.children = []; this.parentElement = null;
    this.listeners = {}; this.text = ''; this.style = {}; this.open = false;
    this.checked = 'checked' in this.attrs; this.value = this.attrs.value || '';
    const self = this;
    this.classList = {
      add: function (c) { const s = (self.attrs['class'] || '').split(/\s+/).filter(Boolean); if (s.indexOf(c) < 0) s.push(c); self.attrs['class'] = s.join(' '); },
      remove: function (c) { self.attrs['class'] = (self.attrs['class'] || '').split(/\s+/).filter(function (x) { return x && x !== c; }).join(' '); },
      contains: function (c) { return (self.attrs['class'] || '').split(/\s+/).indexOf(c) >= 0; }
    };
  }
  get id() { return this.attrs.id || ''; }
  set id(v) { this.attrs.id = v; }
  get type() { return this.attrs.type || ''; }
  set type(v) { this.attrs.type = v; }
  get hidden() { return 'hidden' in this.attrs; }
  set hidden(v) { if (v) this.attrs.hidden = ''; else delete this.attrs.hidden; }
  get firstElementChild() { return this.children[0] || null; }
  get textContent() { return this.text + this.children.map(function (c) { return c.textContent; }).join(''); }
  set textContent(v) { this.text = String(v); this.children = []; }
  getAttribute(n) { return n in this.attrs ? this.attrs[n] : null; }
  setAttribute(n, v) { this.attrs[n] = String(v); }
  removeAttribute(n) { delete this.attrs[n]; }
  hasAttribute(n) { return n in this.attrs; }
  matches(s) { return s.split(',').some(function (one) { return matches(this, one); }, this); }
  closest(s) { for (let at = this; at && at.attrs; at = at.parentElement) if (at.matches(s)) return at; return null; }
  querySelectorAll(s) { return all(this, s); }
  querySelector(s) { return all(this, s)[0] || null; }
  appendChild(c) { c.parentElement = this; this.children.push(c); return c; }
  removeChild(c) { this.children = this.children.filter(function (x) { return x !== c; }); }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  getBoundingClientRect() { return { top: 0 }; }
  scrollIntoView() {}
  select() {}
}
function build(tree, parent) {
  const el = new Node(tree.tag, tree.attrs);
  el.text = tree.text || '';
  tree.children.forEach(function (c) { el.appendChild(build(c, el)); });
  return el;
}
const root = build(input.tree);
root.parentElement = null;
const docListeners = {};
const body = root.querySelector('body');
global.document = {
  body: body,
  querySelector: function (s) { return root.querySelector(s) || (root.matches(s) ? root : null); },
  querySelectorAll: function (s) { return root.querySelectorAll(s); },
  getElementById: function (id) { return root.querySelector('#' + id); },
  createElement: function (tag) { return new Node(tag, {}); },
  addEventListener: function (type, fn) { (docListeners[type] = docListeners[type] || []).push(fn); },
  execCommand: function () { return false; }
};
const store = Object.assign({}, input.storage);
global.localStorage = {
  get length() { return Object.keys(store).length; },
  key: function (i) { return Object.keys(store)[i]; },
  getItem: function (k) { return k in store ? store[k] : null; },
  setItem: function (k, v) { store[k] = String(v); },
  removeItem: function (k) { delete store[k]; }
};
global.window = { name: input.name, innerWidth: 800, scrollY: 0, scrollTo: function () {} };
if (input.lavish) window.lavish = { queuePrompt: function (prompt, options) {
  queued.push({ prompt: prompt, tag: options.tag, queueKey: options.queueKey, element: options.element && options.element.id });
} };
// Node has its own read-only navigator.
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { clipboard: { writeText: function (text) { copied.push(text); return { then: function (ok) { ok(); } }; } } } });
function fire(el, type) {
  const event = { target: el, type: type, preventDefault: function () {} };
  for (let at = el; at && at.attrs; at = at.parentElement) (at.listeners[type] || []).forEach(function (fn) { fn(event); });
  (docListeners[type] || []).forEach(function (fn) { fn(event); });
}
eval(input.script);
input.actions.forEach(function (a) {
  if (a.do === 'tick') {
    const box = root.querySelector('[data-afkv2-input="tick"][data-afkv2-question="' + a.question + '"] input[value="' + a.option + '"]');
    if (box.type === 'radio') all(box.parentElement.parentElement, 'input').forEach(function (r) { r.checked = false; });
    box.checked = a.on;
    fire(box, 'change');
  } else if (a.do === 'mark') {
    const radio = root.querySelector('input[name="choice:' + a.card + '"][value="' + a.token + '"]');
    radio.checked = true;
    fire(radio, 'change');
  } else if (a.do === 'filter') {
    const select = root.querySelector('#afkv2-who-filter');
    select.value = a.value;
    fire(select, 'change');
  } else if (a.do === 'copy') {
    fire(root.querySelector('#afkv2-copy-go'), 'click');
  }
});
const questions = root.querySelectorAll('article[data-afkv2-question]');
const ticked = {};
root.querySelectorAll('[data-afkv2-input="tick"]').forEach(function (group) {
  ticked[group.getAttribute('data-afkv2-question')] = group.querySelectorAll('input').filter(function (i) { return i.checked; }).map(function (i) { return i.value; });
});
console.log(JSON.stringify({
  queued: queued, copied: copied, ticked: ticked, name: window.name, storage: store,
  shown: questions.filter(function (q) { return !q.hidden; }).map(function (q) { return q.id; })
}));
"""


class _Tree(HTMLParser):
    """The page as a tree of tags, attributes and text; script and style bodies are left out."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "html", "attrs": {}, "children": [], "text": ""}
        self.stack, self.skip = [self.root], 0

    def handle_starttag(self, tag, attrs):
        if tag == "html":
            self.root["attrs"] = {k: v or "" for k, v in attrs}
            return
        node = {"tag": tag, "attrs": {k: v or "" for k, v in attrs}, "children": [], "text": ""}
        self.stack[-1]["children"].append(node)
        if tag not in VOID:
            self.stack.append(node)
        self.skip += tag in ("script", "style")

    def handle_endtag(self, tag):
        self.skip -= tag in ("script", "style")
        if tag in VOID or tag == "html":
            return
        while len(self.stack) > 1:
            if self.stack.pop()["tag"] == tag:
                break

    def handle_data(self, data):
        if not self.skip:
            self.stack[-1]["text"] += data


def tree(doc):
    parser = _Tree()
    parser.feed(page.build(engine.READERS[doc["schema"]](doc)))
    return parser.root


def run(actions, lavish=True, held=None, doc=None):
    """Run runtime.js on the rendered page, apply `actions`, and answer what it queued, copied and shows.
    `held` is the `name` and `storage` of an earlier run: a reload of the same tab."""
    held = held or {"name": "", "storage": {}}
    payload = {"tree": tree(doc or document()), "script": RUNTIME, "actions": actions, "lavish": lavish, **held}
    result = subprocess.run(["node", "-e", DRIVER], input=json.dumps(payload), capture_output=True, text=True,
                            encoding="utf-8", check=True)
    return json.loads(result.stdout)


def tick(question, option, on=True):
    return {"do": "tick", "question": question, "option": option, "on": on}


def answers(queued):
    """The queued answers as the host keeps them: a new prompt replaces the unsent one of its queue key."""
    kept = {}
    for prompt in queued:
        kept.pop(prompt["queueKey"], None)
        kept[prompt["queueKey"]] = prompt
    return list(kept.values())


def raw_of(tmp_path, queued):
    """The raw response that the engine's poll makes of the queued answers."""
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(document()), encoding="utf-8")
    prompts = [{"uid": str(n), "prompt": p["prompt"], "selector": f"#{p['element']}", "tag": p["tag"], "text": ""}
               for n, p in enumerate(answers(queued))]
    return path, engine.poll_raw(str(path), prompts)


def ingest(path, raw):
    raw_file = path.parent / "raw.txt"
    raw_file.write_text(raw, encoding="utf-8")
    out, original = [], print
    try:
        engine.print = out.append
        code = engine.main(["ingest", str(path), "--raw-file", str(raw_file)])
    finally:
        engine.print = original
    return code, json.loads(out[0])


# --- 1 queued answer per question for others (SDD §9b, ADR-0004 design)


def test_ticking_2_choices_then_unticking_1_leaves_1_queued_answer_with_the_remaining_choice(tmp_path):
    out = run([tick("q-cols", "opt-name"), tick("q-cols", "opt-sum"), tick("q-cols", "opt-name", on=False)])
    [answer] = answers(out["queued"])
    assert answer["prompt"] == "q-cols tick opt-sum" and answer["tag"] == TICK_TAG and answer["element"] == "q-cols"
    path, raw = raw_of(tmp_path, out["queued"])
    assert raw.splitlines() == ["[round R-3]", "q-cols tick opt-sum"]
    code, result = ingest(path, raw)
    assert code == 0, result
    [signal] = result["questions_to_read"]
    assert signal["target"] == "q-cols" and signal["choices"] == ["opt-sum"]


def test_each_change_queues_on_the_same_key_of_its_question():
    out = run([tick("q-cols", "opt-name"), tick("q-cols", "opt-sum"), tick("q-size", "opt-k")])
    keys = [prompt["queueKey"] for prompt in out["queued"]]
    assert keys[0] == keys[1] != keys[2]
    assert "s1" in keys[0] and "3" in keys[0] and "q-cols" in keys[0] and "q-size" in keys[2]


def test_the_ticked_option_ids_go_in_tick_order():
    out = run([tick("q-cols", "opt-sum"), tick("q-cols", "opt-name")])
    assert answers(out["queued"])[-1]["prompt"] == "q-cols tick opt-sum opt-name"


def test_a_question_that_takes_1_choice_queues_the_last_radio_only():
    out = run([tick("q-size", "opt-k"), tick("q-size", "opt-m")])
    assert [a["prompt"] for a in answers(out["queued"])] == ["q-size tick opt-m"]


def test_unticking_every_choice_queues_an_answer_that_sends_no_tick(tmp_path):
    out = run([tick("q-cols", "opt-date"), tick("q-cols", "opt-date", on=False)])
    assert [a["prompt"] for a in answers(out["queued"])] == ["q-cols tick"]
    assert raw_of(tmp_path, out["queued"])[1].splitlines() == ["[round R-3]"]


def test_a_reload_of_the_tab_shows_the_ticks_again_and_keeps_their_order():
    first = run([tick("q-cols", "opt-sum"), tick("q-cols", "opt-name"), tick("q-size", "opt-m")])
    held = {"name": first["name"], "storage": first["storage"]}
    again = run([], held=held)
    assert again["ticked"]["q-cols"] == ["opt-name", "opt-sum"] and again["ticked"]["q-size"] == ["opt-m"]
    assert again["queued"] == []
    later = run([tick("q-cols", "opt-date")], held=held)
    assert answers(later["queued"])[-1]["prompt"] == "q-cols tick opt-sum opt-name opt-date"


def test_a_reload_without_local_storage_keeps_the_ticks_in_the_tab_name():
    first = run([tick("q-cols", "opt-sum")])
    assert run([], held={"name": first["name"], "storage": {}})["ticked"]["q-cols"] == ["opt-sum"]


def test_copy_the_response_holds_the_tick_line_beside_the_marks():
    out = run([{"do": "mark", "card": "i-closed", "token": "accept"}, tick("q-cols", "opt-date")], lavish=False)
    out = run([{"do": "copy"}], lavish=False, held={"name": out["name"], "storage": out["storage"]})
    assert out["copied"] == ["[round R-3]\ni-closed accept\nq-cols tick opt-date"]


def test_a_mark_still_queues_its_card_beside_the_ticks():
    out = run([{"do": "mark", "card": "i-closed", "token": "accept"}, tick("q-cols", "opt-date")])
    assert [(a["prompt"], a["tag"]) for a in answers(out["queued"])] == [
        ("i-closed accept", "afkv2-mark"), ("q-cols tick opt-date", TICK_TAG)]


# --- the role filter (PRD AC-033, SDD §9 row "Filter")


def test_the_filter_shows_every_question_before_a_role_is_set():
    assert run([])["shown"] == QUESTIONS


def test_a_role_shows_that_role_s_questions_and_the_questions_for_everyone_in_the_same_order():
    assert run([{"do": "filter", "value": "tester"}])["shown"] == ["q-size", "q-drop"]
    assert run([{"do": "filter", "value": "product owner"}])["shown"] == ["q-format", "q-size", "q-cols"]
    assert run([{"do": "filter", "value": "developer lead"}])["shown"] == ["q-size", "q-assume"]


def test_every_role_again_shows_every_question():
    assert run([{"do": "filter", "value": "tester"}, {"do": "filter", "value": ""}])["shown"] == QUESTIONS


def test_setting_the_filter_queues_nothing():
    out = run([{"do": "filter", "value": "tester"}, {"do": "filter", "value": "product owner"}])
    assert out["queued"] == []
    assert run([tick("q-cols", "opt-sum"), {"do": "filter", "value": "tester"}])["queued"] == run(
        [tick("q-cols", "opt-sum")])["queued"]
