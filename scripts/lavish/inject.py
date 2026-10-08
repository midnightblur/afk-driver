"""Inject the lavish page runtime into an artifact before it is shown or polled.

    inject_file(path, cwd=None) -> bool   # True when the file changed

Owns the tooltip dictionary (seed `tips.json`, then the plugin `GLOSSARY.md`, then
the artifact's repository glossaries with its own service last, then the feature's
`LAVISH-TIPS.md`; later wins), the hover/side-question/session-nav runtime, the
`<title>` and charset backfill, and the dark-mode override. Every block sits between
start/end markers and is replaced whole, so unchanged inputs give unchanged bytes and
the file is rewritten only when its bytes differ. Doctrine: `LAVISH.md`.

Standard library only; no network, no subprocess.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parents[1]
SEED = HERE / "tips.json"
WORKFLOW_GLOSSARY = PLUGIN_ROOT / "GLOSSARY.md"

MARK_START = "<!-- afk-lavish-tips:start -->"
MARK_END = "<!-- afk-lavish-tips:end -->"
DARK_START = "<!-- afk-lavish-dark:start -->"
DARK_END = "<!-- afk-lavish-dark:end -->"
TIPS_BLOCK = re.compile(re.escape(MARK_START) + r".*?" + re.escape(MARK_END) + r"(?:\r?\n)?", re.DOTALL)
DARK_BLOCK = re.compile(re.escape(DARK_START) + r".*?" + re.escape(DARK_END) + r"(?:\r?\n)?", re.DOTALL)
# The single-marker dark injection older releases wrote: marker, one style, optional script.
LEGACY_DARK = re.compile(r"<!-- afk-lavish-dark -->\s*<style>.*?</style>\s*(?:<script>.*?</script>\s*)?",
                         re.DOTALL)
DAISY_DARK = "\n<style>html{color-scheme:dark}</style>\n"


class InjectError(Exception):
    """The artifact cannot be read or written as UTF-8 HTML."""


def clean(text):
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links -> label
    text = text.replace("`", "")
    text = re.sub(r"(\*\*|\*|__)", "", text)
    text = re.sub(r"(?<![\w])_|_(?![\w])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def keys_for(term):
    """Dictionary keys of a term: each `a / b` part, its bare pre-dash head, a `(token)` inside it.

    Title-Case words lower so page-case usage matches; ALL-CAPS and mixed-case words stay case-sensitive.
    """
    raw = term.replace("`", "").strip()
    out = {}  # insertion-ordered: the dictionary bytes must not follow the process hash seed

    def add(part):
        part = part.strip()
        if part:
            out.setdefault(" ".join(
                w.lower() if len(w) > 1 and w[1:].islower() else w
                for w in part.split()))

    base = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    for part in re.split(r"\s*/\s*", base):
        add(part)
        head = re.split(r"\s+—\s+", part)[0]
        if head.strip() != part.strip():
            add(head)
    for m in re.finditer(r"\(([^)]*)\)", raw):
        inner = m.group(1).strip()
        if re.fullmatch(r"[\w.\-]+", inner):
            out.setdefault(inner)
    return list(out)


# Entry line: optional list bullet, bold term, optional italic parenthetical
# qualifier ("**State** *(user-facing: "Status")*:"), then the definition.
ENTRY_RE = re.compile(r"(?:[-*+]\s+)?\*\*(.+?)\*\*\s*(?:\*\([^)]*\)\*\s*)?:\s*(.*)$")
# Trailing metadata lines the glossary grammar allows — never tooltip text.
META_LINE_RE = re.compile(r"[`_]*(Avoid|Code|Related)[`_]*\s*:")


def parse_glossary(path):
    """Entries of the canonical glossary grammar (GLOSSARY-FORMAT.md): `**Term**:` then lines to a blank one."""
    entries = {}
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return entries
    term, buf = None, []

    def flush():
        if term and buf:
            definition = clean(" ".join(buf))
            if definition:
                for k in keys_for(term):
                    entries[k] = definition

    for line in lines:
        stripped = line.strip()
        m = ENTRY_RE.match(stripped)
        if m:
            flush()
            term, buf = m.group(1), ([m.group(2)] if m.group(2) else [])
            continue
        if not stripped or stripped.startswith("#") or META_LINE_RE.match(stripped):
            flush()
            term, buf = None, []
            continue
        if term is not None:
            buf.append(stripped)
    flush()
    return entries


# The luminance-gated invert override for a page that is not DaisyUI.
DARK_INVERT = """
<style>
  html { color-scheme: dark; }
  html.afk-lavish-invert { filter: invert(1) hue-rotate(180deg); background: #111 !important; }
  html.afk-lavish-invert img,
  html.afk-lavish-invert video,
  html.afk-lavish-invert canvas,
  html.afk-lavish-invert iframe { filter: invert(1) hue-rotate(180deg); }
</style>
<script>
(function () {
  function lum(c) {
    var m = c && c.match(/[\\d.]+/g);
    if (!m || m.length < 3) return null;
    if (m.length >= 4 && parseFloat(m[3]) === 0) return null; /* transparent */
    return (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255;
  }
  function apply() {
    var l = lum(getComputedStyle(document.body).backgroundColor);
    if (l === null) l = lum(getComputedStyle(document.documentElement).backgroundColor);
    if (l === null) l = 1; /* nothing painted = browser-default white */
    if (l > 0.5) document.documentElement.classList.add('afk-lavish-invert');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', apply);
  else apply();
})();
</script>
"""


def tips_block(dict_json: str) -> str:
    """The tooltip dictionary, hover runtime, btw control and session-nav chrome, between markers."""
    return MARK_START + """
<style>
  .afk-tip { border-bottom: 1px dotted currentColor; cursor: help; }
  #afk-tip-box {
    position: fixed; z-index: 2147483647; max-width: 340px; padding: 8px 10px;
    background: #111827; color: #f3f4f6; border: 1px solid rgba(255,255,255,.18);
    border-radius: 6px; font: 12.5px/1.45 system-ui, sans-serif; text-align: left;
    box-shadow: 0 4px 14px rgba(0,0,0,.35); pointer-events: none;
    opacity: 0; transition: opacity .12s; white-space: normal;
  }
  #afk-btw {
    position: fixed; right: 14px; bottom: 14px; z-index: 2147483646;
    font: 12.5px/1.4 system-ui, sans-serif; text-align: right;
  }
  #afk-btw button {
    background: #111827; color: #f3f4f6; border: 1px solid rgba(255,255,255,.25);
    border-radius: 6px; padding: 5px 10px; cursor: pointer; font: inherit;
  }
  #afk-btw button:hover { border-color: rgba(255,255,255,.5); }
  #afk-btw-panel {
    position: absolute; bottom: calc(100% + 6px); right: 0; width: 300px;
    background: #111827; border: 1px solid rgba(255,255,255,.25); border-radius: 8px;
    padding: 8px; box-shadow: 0 4px 14px rgba(0,0,0,.35); text-align: left;
  }
  #afk-btw-q {
    width: 100%; min-height: 64px; box-sizing: border-box; resize: vertical;
    background: #0b0f19; color: #f3f4f6; border: 1px solid rgba(255,255,255,.2);
    border-radius: 6px; padding: 6px; font: inherit;
  }
  #afk-btw-panel > div { display: flex; gap: 6px; justify-content: flex-end; margin-top: 6px; }
  #afk-nav {
    position: fixed; top: 14px; right: 14px; z-index: 2147483645; width: 236px;
    background: #111827; color: #f3f4f6; border: 1px solid rgba(255,255,255,.25);
    border-radius: 8px; font: 12.5px/1.45 system-ui, sans-serif; text-align: left;
    box-shadow: 0 4px 14px rgba(0,0,0,.35);
  }
  #afk-nav-head { display: flex; align-items: center; gap: 6px; padding: 7px 10px; cursor: pointer; user-select: none; }
  #afk-nav-head b { flex: 1; font-weight: 600; }
  #afk-nav-list { max-height: 62vh; overflow-y: auto; padding: 0 6px 6px; }
  #afk-nav.afk-min { width: auto; }
  #afk-nav.afk-min #afk-nav-list { display: none; }
  .afk-nav-g { margin: 4px 0 2px; padding: 2px 4px; font-weight: 600; opacity: .75; cursor: pointer; user-select: none; }
  .afk-nav-row { display: block; padding: 3px 4px 3px 10px; border-radius: 5px; cursor: pointer;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .afk-nav-row:hover { background: rgba(255,255,255,.08); }
  .afk-nav-row.afk-cur { background: rgba(59,130,246,.25); }
  .afk-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #f59e0b; margin-right: 5px; vertical-align: 1px; }
  #afk-jump {
    position: fixed; left: 14px; bottom: 14px; z-index: 2147483645; display: none;
    background: #111827; color: #f3f4f6; border: 1px solid rgba(255,255,255,.25);
    border-radius: 6px; padding: 5px 10px; cursor: pointer; font: 12.5px/1.4 system-ui, sans-serif;
  }
  #afk-jump:hover { border-color: rgba(255,255,255,.5); }
  .afk-collapsed > *:not(:first-child) { display: none !important; }
  .afk-caret { cursor: pointer; }
  .afk-caret::after { content: "▸"; margin-left: 6px; opacity: .55; }
  .afk-caret.afk-open::after { content: "▾"; }
  [data-afk-fresh] { box-shadow: -3px 0 0 0 #f59e0b; }
  [data-afk-item] { scroll-margin-top: 10px; }
  .afk-flash { outline: 2px solid #f59e0b; outline-offset: 2px; }
</style>
<script id="afk-tips-dict" type="application/json">""" + dict_json + """</script>
<script>
(function () {
  var el = document.getElementById('afk-tips-dict');
  var dict; try { dict = JSON.parse(el.textContent); } catch (e) { return; }
  if (!Object.keys(dict).length) return;
  var ciMap = {}, keys, re;
  var esc = function (s) { return s.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'); };
  function rebuild() {
    keys = Object.keys(dict).sort(function (a, b) { return b.length - a.length; });
    keys.forEach(function (k) { if (k === k.toLowerCase()) ciMap[k] = dict[k]; });
    re = new RegExp('(?<![\\\\w-])(?:' + keys.map(esc).join('|') + ')(?:e?s)?(?!\\\\w)', 'gi');
  }
  rebuild();

  function lookup(s) {
    if (Object.prototype.hasOwnProperty.call(dict, s)) return dict[s];
    var lower = s.toLowerCase();
    return Object.prototype.hasOwnProperty.call(ciMap, lower) ? ciMap[lower] : null;
  }
  // The wrap regex admits a plural tail; resolve "MRs"/"classes" to their
  // singular key under the same case rules.
  function tipFor(matched) {
    var tip = lookup(matched);
    if (tip === null && matched.length > 2 && /s$/i.test(matched)) {
      tip = lookup(matched.slice(0, -1));
      if (tip === null && /es$/i.test(matched)) tip = lookup(matched.slice(0, -2));
    }
    return tip;
  }

  function wrap(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (!n.nodeValue || n.nodeValue.length > 50000 || !re.test(n.nodeValue)) return NodeFilter.FILTER_REJECT;
        re.lastIndex = 0;
        var p = n.parentElement;
        if (!p || p.closest('script,style,noscript,textarea,.afk-tip,#afk-tip-box,#afk-btw,#afk-nav,#afk-jump')) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var nodes = [], n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(function (node) {
      var text = node.nodeValue, frag = document.createDocumentFragment(), last = 0, m;
      re.lastIndex = 0;
      while ((m = re.exec(text))) {
        var tip = tipFor(m[0]);
        if (tip === null) continue;
        frag.appendChild(document.createTextNode(text.slice(last, m.index)));
        var span = document.createElement('span');
        span.className = 'afk-tip';
        span.setAttribute('data-afk-tip', tip);
        span.textContent = m[0];
        frag.appendChild(span);
        last = m.index + m[0].length;
      }
      if (last === 0) return;
      frag.appendChild(document.createTextNode(text.slice(last)));
      node.parentNode.replaceChild(frag, node);
    });
  }

  // Author-side tooltips (item ids etc.): promote title=/data-tip into the same UI.
  function promote(root) {
    root.querySelectorAll('[title],[data-tip]').forEach(function (elx) {
      if (elx.id === 'afk-tip-box') return;
      var t = elx.getAttribute('data-tip') || elx.getAttribute('title');
      if (!t) return;
      elx.setAttribute('data-afk-tip', t);
      elx.removeAttribute('title');
      if (!elx.hasAttribute('data-lavish-action')) elx.classList.add('afk-tip');
    });
  }

  // Id-tip propagation (LAVISH.md Tooltips rule 3): an id tipped once serves
  // every later bare occurrence — harvest single-token authored tips into the
  // dictionary so wrap() covers the rest of the page.
  function harvest(root) {
    var dirty = false;
    root.querySelectorAll('[data-afk-tip]').forEach(function (elx) {
      if (elx.closest('#afk-btw,#afk-tip-box,#afk-nav')) return;
      var token = (elx.textContent || '').trim();
      if (!/^[A-Za-z][\\w.-]{0,23}$/.test(token)) return;
      if (Object.prototype.hasOwnProperty.call(dict, token)) return;
      dict[token] = elx.getAttribute('data-afk-tip');
      dirty = true;
    });
    if (dirty) rebuild();
  }

  var box;
  function ensureBox() {
    if (!box) { box = document.createElement('div'); box.id = 'afk-tip-box'; document.body.appendChild(box); }
    return box;
  }
  document.addEventListener('mouseover', function (e) {
    var t = e.target && e.target.closest && e.target.closest('[data-afk-tip]');
    if (!t) { if (box) box.style.opacity = '0'; return; }
    var b = ensureBox();
    b.textContent = t.getAttribute('data-afk-tip');
    var r = t.getBoundingClientRect(), bw = b.offsetWidth, bh = b.offsetHeight;
    var x = Math.max(6, Math.min(r.left, window.innerWidth - bw - 6));
    var y = r.top - bh - 8;
    if (y < 6) y = r.bottom + 8;
    b.style.left = x + 'px'; b.style.top = y + 'px'; b.style.opacity = '1';
  });
  window.addEventListener('scroll', function () { if (box) box.style.opacity = '0'; }, true);

  var mo;
  function scan() {
    if (mo) mo.disconnect();
    if (navRefresh) navRefresh();
    promote(document.body);
    harvest(document.body);
    wrap(document.body);
    if (mo) mo.observe(document.body, { childList: true, subtree: true });
  }

  // Side-question control (LAVISH.md "Side-questions"): rides the normal
  // queue with a [btw] / [btw:subagent] prefix; absent when the artifact is
  // opened standalone (no window.lavish, nobody listening).
  var btwTries = 0;
  function btw() {
    if (document.getElementById('afk-btw')) return;
    if (!window.lavish || !document.body) { if (btwTries++ < 20) setTimeout(btw, 250); return; }
    var host = document.createElement('div');
    host.id = 'afk-btw';
    host.setAttribute('data-lavish-ui', 'afk-btw');
    host.setAttribute('data-lavish-action', 'btw');
    host.innerHTML =
      '<div id="afk-btw-panel" hidden><textarea id="afk-btw-q" data-lavish-action="btw"' +
      ' placeholder="Quick question about this page..."></textarea>' +
      '<div><button type="button" id="afk-btw-here" data-lavish-action="btw"' +
      ' title="Answered by the reviewing agent in this session">Ask here</button>' +
      '<button type="button" id="afk-btw-side" data-lavish-action="btw"' +
      ' title="A fresh background agent answers - cheaper, main review keeps going">Ask side agent</button></div></div>' +
      '<button type="button" id="afk-btw-open" data-lavish-action="btw"' +
      ' title="Side-question: answered without derailing the review">btw?</button>';
    document.body.appendChild(host);
    var panel = host.querySelector('#afk-btw-panel');
    var q = host.querySelector('#afk-btw-q');
    host.querySelector('#afk-btw-open').addEventListener('click', function () {
      panel.hidden = !panel.hidden;
      if (!panel.hidden) q.focus();
    });
    function ask(prefix) {
      var text = q.value.trim();
      if (!text || !window.lavish) return;
      window.lavish.queuePrompt(prefix + ' ' + text, { tag: 'btw' });
      window.lavish.sendQueuedPrompts();
      q.value = '';
      panel.hidden = true;
    }
    host.querySelector('#afk-btw-here').addEventListener('click', function () { ask('[btw]'); });
    host.querySelector('#afk-btw-side').addEventListener('click', function () { ask('[btw:subagent]'); });
  }

  // Session-nav chrome (LAVISH.md "Page anatomy"): a sticky section rail with
  // per-state counts, settled cards collapsed to their heading, and a floating
  // jump-to-current control — built from the authored data-afk-item /
  // data-afk-state / data-afk-fresh grammar. A page without that markup gets
  // no chrome.
  var navRefresh = null;
  function navChrome() {
    if (document.getElementById('afk-nav')) return;
    if (!document.querySelector('[data-afk-item]')) return;
    var LS = 'afk-nav:' + location.pathname;
    var store = {};
    try { store = JSON.parse(localStorage.getItem(LS) || '{}') || {}; } catch (e) {}
    function save() { try { localStorage.setItem(LS, JSON.stringify(store)); } catch (e) {} }
    function items() { return [].slice.call(document.querySelectorAll('[data-afk-item]')); }
    function st(el) {
      var s = el.getAttribute('data-afk-state');
      return s === 'current' || s === 'settled' || s === 'blocked' ? s : 'open';
    }
    function label(el) {
      var h = el.firstElementChild;
      var t = ((h && h.textContent) || el.getAttribute('data-afk-item') || '').replace(/\\s+/g, ' ').trim();
      return t.length > 64 ? t.slice(0, 61) + '…' : t;
    }
    function setCollapsed(el, on) {
      if (st(el) === 'current') on = false;
      el.classList.toggle('afk-collapsed', on);
      var h = el.firstElementChild;
      if (h && st(el) !== 'current') { h.classList.add('afk-caret'); h.classList.toggle('afk-open', !on); }
    }
    function applyDefaults() {
      items().forEach(function (el) {
        // A table row is already its own summary. Folding one would hide
        // every cell but the id and leave a one-cell row in a five-column
        // table. Rows still list in the rail and still take goTo(); they
        // just never fold.
        if (el.tagName === 'TR') return;
        var id = el.getAttribute('data-afk-item'), s = st(el);
        if (s === 'current') { setCollapsed(el, false); return; }
        if (el.hasAttribute('data-afk-nav-done')) return;
        el.setAttribute('data-afk-nav-done', '1');
        var expanded = Object.prototype.hasOwnProperty.call(store, id) ? !!store[id] : s !== 'settled';
        setCollapsed(el, !expanded);
        var h = el.firstElementChild;
        if (h) {
          h.setAttribute('data-lavish-action', 'afk-collapse');
          h.addEventListener('click', function () {
            var wasCollapsed = el.classList.contains('afk-collapsed');
            setCollapsed(el, !wasCollapsed);
            store[id] = wasCollapsed ? 1 : 0; save();
          });
        }
      });
    }
    function goTo(el) {
      setCollapsed(el, false);
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      el.classList.add('afk-flash');
      setTimeout(function () { el.classList.remove('afk-flash'); }, 1600);
    }
    var nav = document.createElement('div');
    nav.id = 'afk-nav';
    nav.setAttribute('data-lavish-ui', 'afk-nav');
    nav.setAttribute('data-lavish-action', 'afk-nav');
    nav.innerHTML = '<div id="afk-nav-head" role="button" tabindex="0"><b>On this page</b><span>–</span></div><div id="afk-nav-list"></div>';
    document.body.appendChild(nav);
    nav.addEventListener('keydown', function (e) {
      if ((e.key === 'Enter' || e.key === ' ') && e.target && e.target.click) { e.preventDefault(); e.target.click(); }
    });
    if (store['__min']) nav.classList.add('afk-min');
    nav.querySelector('#afk-nav-head').addEventListener('click', function () {
      nav.classList.toggle('afk-min');
      store['__min'] = nav.classList.contains('afk-min') ? 1 : 0; save();
    });
    var GROUPS = [['current', 'Now'], ['open', 'Open'], ['blocked', 'Blocked'], ['settled', 'Settled']];
    // Rebuild replaces the rail's nodes, so unforced refreshes (mutation-driven
    // rescans) skip when the item set is unchanged — unrelated page mutations
    // must not churn the rail a user is about to click.
    var navSig = null;
    function rebuildNav(force) {
      var els = items();
      var sig = els.map(function (el) {
        return el.getAttribute('data-afk-item') + '|' + st(el) + '|' +
          (el.hasAttribute('data-afk-fresh') ? 1 : 0) + '|' + label(el);
      }).join(';');
      if (!force && sig === navSig) return;
      navSig = sig;
      applyDefaults();
      var list = nav.querySelector('#afk-nav-list');
      list.textContent = '';
      GROUPS.forEach(function (g) {
        var members = els.filter(function (el) { return st(el) === g[0]; });
        if (!members.length) return;
        var gk = '__g:' + g[0];
        var open = Object.prototype.hasOwnProperty.call(store, gk) ? !!store[gk] : g[0] !== 'settled';
        var head = document.createElement('div');
        head.className = 'afk-nav-g';
        head.textContent = (open ? '▾ ' : '▸ ') + g[1] + (g[0] === 'current' ? '' : ' (' + members.length + ')');
        head.setAttribute('data-lavish-action', 'afk-nav');
        head.setAttribute('role', 'button');
        head.setAttribute('tabindex', '0');
        head.addEventListener('click', function () { store[gk] = open ? 0 : 1; save(); rebuildNav(true); });
        list.appendChild(head);
        if (!open) return;
        members.forEach(function (el) {
          var row = document.createElement('div');
          row.className = 'afk-nav-row' + (g[0] === 'current' ? ' afk-cur' : '');
          row.setAttribute('data-lavish-action', 'afk-nav');
          row.setAttribute('role', 'button');
          row.setAttribute('tabindex', '0');
          if (el.hasAttribute('data-afk-fresh')) {
            var dot = document.createElement('span');
            dot.className = 'afk-dot';
            dot.setAttribute('data-afk-tip', 'Changed in the round just applied');
            row.appendChild(dot);
          }
          row.appendChild(document.createTextNode(label(el)));
          row.addEventListener('click', function () { goTo(el); });
          list.appendChild(row);
        });
      });
    }
    function currentAnswerSurface() {
      var current = document.querySelector('[data-afk-state="current"]');
      if (!current) return null;
      return current.closest('[data-afk-answer-form="1"]') || current;
    }
    var jump = document.createElement('button');
    jump.type = 'button';
    jump.id = 'afk-jump';
    jump.setAttribute('data-lavish-action', 'afk-nav');
    jump.textContent = '↑ Current question';
    jump.addEventListener('click', function () {
      var cur = currentAnswerSurface();
      if (cur) goTo(cur);
    });
    document.body.appendChild(jump);
    var cur = currentAnswerSurface();
    if (cur && 'IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        jump.style.display = entries[0].isIntersecting ? 'none' : 'block';
      }).observe(cur);
    }
    rebuildNav(true);
    navRefresh = function () { rebuildNav(false); };
  }

  function start() {
    var pending;
    mo = new MutationObserver(function (recs) {
      var ours = recs.every(function (r) {
        return (box && (r.target === box || box.contains(r.target))) ||
               (r.target && r.target.closest && r.target.closest('#afk-btw,#afk-nav,#afk-jump'));
      });
      if (ours) return;
      clearTimeout(pending); pending = setTimeout(scan, 300);
    });
    btw();
    navChrome();
    scan();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
</script>
""" + MARK_END


def repo_root(start: Path) -> Path | None:
    """The nearest folder at or above `start` holding a `.git` entry, or None."""
    walk = start if start.is_dir() else start.parent
    while True:
        if (walk / ".git").exists():
            return walk
        if walk.parent == walk:
            return None
        walk = walk.parent


def _under(child: str, parent: str) -> bool:
    return os.path.normcase(child).startswith(os.path.normcase(parent) + os.sep)


def _seed(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}  # a broken seed must never break a render
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if not k.startswith("__") and isinstance(v, str) and v.strip()}


def spec_dir_of(html: str, target: Path, top: str) -> str:
    """The feature folder: the `afk-spec-dir` meta, else the nearest `LAVISH-TIPS.md` above the artifact."""
    m = re.search(
        r"<meta\s+(?:name=\"afk-spec-dir\"\s+content=\"([^\"]+)\"|content=\"([^\"]+)\"\s+name=\"afk-spec-dir\")",
        html, re.IGNORECASE)
    if m:
        return (m.group(1) or m.group(2)).replace("\\", "/").strip("/")
    if not top or not _under(str(target), top):
        return ""
    d = os.path.dirname(str(target))
    while True:
        if os.path.isfile(os.path.join(d, "LAVISH-TIPS.md")):
            rel = os.path.relpath(d, top).replace("\\", "/")
            return "" if rel == "." else rel
        if os.path.normcase(d) == os.path.normcase(top):
            return ""
        parent = os.path.dirname(d)
        if parent == d:
            return ""
        d = parent


def load_dictionary(target: Path, html: str, toplevel: Path | None,
                    seed: Path = SEED, workflow: Path = WORKFLOW_GLOSSARY) -> tuple[dict, str]:
    """(merged term -> tip dictionary, spec-dir) for one artifact; later sources win."""
    tips = _seed(seed)
    tips.update(parse_glossary(str(workflow)))
    top = os.path.abspath(toplevel) if toplevel else ""
    abs_target = os.path.abspath(target)
    if top:
        own = ""
        if _under(abs_target, top):
            own = os.path.relpath(abs_target, top).replace("\\", "/").split("/", 1)[0]
        glossaries = []
        if os.path.isfile(os.path.join(top, "GLOSSARY.md")):
            glossaries.append(os.path.join(top, "GLOSSARY.md"))
        try:
            names = sorted(os.listdir(top))
        except OSError:
            names = []
        for name in names:
            g = os.path.join(top, name, "GLOSSARY.md")
            if name != own and os.path.isfile(g):
                glossaries.append(g)
        if own and os.path.isfile(os.path.join(top, own, "GLOSSARY.md")):
            glossaries.append(os.path.join(top, own, "GLOSSARY.md"))
        for g in glossaries:
            tips.update(parse_glossary(g))
    spec_dir = spec_dir_of(html, Path(abs_target), top)
    if spec_dir and top:
        tips.update(parse_glossary(os.path.join(top, spec_dir, "LAVISH-TIPS.md")))
    return tips, spec_dir


def _strip(html: str) -> str:
    return LEGACY_DARK.sub("", DARK_BLOCK.sub("", TIPS_BLOCK.sub("", html)))


def inject(html: str, target: Path, tips: dict, spec_dir: str) -> str:
    """`html` with every runtime block replaced; a pure function of its arguments."""
    nl = "\r\n" if "\r\n" in html else "\n"
    html = _strip(html)
    titled = False
    if not re.search(r"<title[\s>]", html, re.IGNORECASE):
        stem = os.path.splitext(os.path.basename(str(target)))[0]
        tail = spec_dir.rsplit("/", 1)[-1] if spec_dir else ""
        tag = "<title>" + (stem + " — " + tail if tail and tail != stem else stem) + "</title>"
        if re.search(r"<head\b", html, re.IGNORECASE):
            html = re.sub(r"(<head\b[^>]*>)", lambda mh: mh.group(1) + tag, html, count=1, flags=re.IGNORECASE)
        else:
            html = tag + nl + html
        titled = True
    # Dictionary text and the backfilled title are UTF-8-heavy; a charset-less page reads as windows-1252.
    if (tips or titled) and not re.search(r"<meta[^>]+charset", html, re.IGNORECASE):
        if re.search(r"<head\b", html, re.IGNORECASE):
            html = re.sub(r"(<head\b[^>]*>)", r'\1<meta charset="utf-8">', html, count=1, flags=re.IGNORECASE)
        else:
            html = '<meta charset="utf-8">' + nl + html
    if re.search(r"daisyui", html, re.IGNORECASE):
        def darken(tag):
            t = tag.group(0)
            if re.search(r"data-theme\s*=", t, re.IGNORECASE):
                return re.sub(r"data-theme\s*=\s*([\"']).*?\1", 'data-theme="dark"', t, flags=re.IGNORECASE)
            return t[:-1] + ' data-theme="dark">'

        html = re.sub(r"<html\b[^>]*>", darken, html, count=1, flags=re.IGNORECASE)
        dark = DARK_START + DAISY_DARK + DARK_END
    else:
        dark = DARK_START + DARK_INVERT + DARK_END
    blocks = ""
    if tips:
        # </script> inside a value would end the JSON script tag early.
        blocks += tips_block(json.dumps(tips, ensure_ascii=False).replace("</", "<\\/")) + "\n"
    blocks = (blocks + dark + "\n").replace("\n", nl)
    m = re.search(r"</body\s*>", html, re.IGNORECASE)
    if m:
        return html[: m.start()] + blocks + html[m.start():]
    return html + ("" if html.endswith("\n") else nl) + blocks


def write_if_changed(path: Path, data: bytes) -> bool:
    """Atomically replace `path` with `data` only when its bytes differ; True when written."""
    try:
        if path.read_bytes() == data:
            return False
    except OSError:
        pass
    fd, temp = tempfile.mkstemp(prefix=".afk-lavish-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        try:
            os.chmod(temp, path.stat().st_mode & 0o7777)
        except OSError:
            pass
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    return True


def inject_file(path: str | Path, cwd: str | Path | None = None,
                seed: Path = SEED, workflow: Path = WORKFLOW_GLOSSARY) -> bool:
    """Inject the runtime into the artifact at `path`; True when its bytes changed.

    The repository is the one holding the artifact, else the one holding `cwd`.
    """
    target = Path(os.path.abspath(path))
    try:
        raw = target.read_bytes()
        html = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as problem:
        raise InjectError(f"cannot read {target} as UTF-8: {problem}") from problem
    toplevel = repo_root(target) or (repo_root(Path(os.path.abspath(cwd))) if cwd else None)
    tips, spec_dir = load_dictionary(target, _strip(html), toplevel, seed, workflow)
    try:
        return write_if_changed(target, inject(html, target, tips, spec_dir).encode("utf-8"))
    except OSError as problem:
        raise InjectError(f"cannot write {target}: {problem}") from problem
