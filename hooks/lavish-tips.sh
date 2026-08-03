#!/usr/bin/env bash
# lavish-tips.sh — PreToolUse hook (Bash/PowerShell): inject the page runtime
# into lavish-axi artifacts.
#
# Intercepts a `npx lavish-axi@<ver> <file>` RENDER command and embeds, into the
# artifact HTML on disk, (a) the merged tooltip dictionary, (b) a self-contained
# hover runtime that wraps every dictionary term in the page and serves a
# floating tooltip — it also promotes author-side `title=`/`data-tip` attributes
# (per-artifact item ids) into the same tooltip UI and propagates each authored
# id-tip to every later bare occurrence of the same id (LAVISH.md "Tooltips"
# rule 3), and (c) the floating "btw" side-question control (LAVISH.md
# "Side-questions"). Deterministic — no LLM at injection time; the authoring
# agent's only job is keeping the dictionary itself fed (LAVISH.md "Tooltips").
#
# Dictionary sources, merged in order (later wins):
#   1. seed     — lavish-tips.json next to this script (tooltip-only vocabulary
#                 with no glossary home; Lockstep-sanctioned copies, owning
#                 files win on conflict)
#   2. overlay  — <main-checkout>/.claude/lavish-tips.json in the gated repo
#                 (machine-local extras; legacy — committed glossaries below
#                 are the canonical stores and win on conflict)
#   3. workflow — ../GLOSSARY.md (committed workflow vocabulary), parsed from
#                 its canonical **Term**: entry grammar
#   4. feature  — {spec-dir}/GLOSSARY.md (committed feature vocabulary), where
#                 spec-dir comes from the artifact's
#                 <meta name="afk-spec-dir" content="<repo-relative path>">,
#                 resolved against the current worktree root
# Keys starting with "__" are metadata, ignored. A key with any uppercase
# letter matches case-sensitively; all-lowercase keys match case-insensitively;
# whole-word only (word chars and '-' bound the match). Glossary Title-Case
# words are lowered so page-case usage still matches; ALL-CAPS/mixed tokens
# (PRD, TICKET.md) stay case-sensitive.
#
# Re-injected (block replaced) on every render — the dictionary grows between
# renders and a resumed artifact must pick up new entries. Idempotent via
# start/end markers. Never blocks: always exits 0.

set -u

input=$(cat)

# Fast bail: virtually every command is not a lavish render.
case "$input" in
  *lavish-axi*) ;;
  *) exit 0 ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
seed="$script_dir/lavish-tips.json"
wf_glossary="$script_dir/../GLOSSARY.md"
overlay=""
if common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); then
  overlay="$(dirname "$common")/.claude/lavish-tips.json"
fi
toplevel=$(git rev-parse --show-toplevel 2>/dev/null || true)

LAVISH_TIPS_INPUT="$input" LAVISH_TIPS_SEED="$seed" LAVISH_TIPS_OVERLAY="$overlay" \
LAVISH_TIPS_WF_GLOSSARY="$wf_glossary" LAVISH_TIPS_TOPLEVEL="$toplevel" python - <<'PYEOF'
import json, os, re, sys

MARK_START = "<!-- afk-lavish-tips:start -->"
MARK_END = "<!-- afk-lavish-tips:end -->"

NON_RENDER = {"poll", "end", "stop", "playbook", "share", "setup", "update"}

try:
    command = json.loads(os.environ["LAVISH_TIPS_INPUT"]).get("tool_input", {}).get("command", "")
except Exception:
    sys.exit(0)

# Tokenize the tail after the lavish-axi package token; a render command's
# first non-flag token is the artifact file (non-render subcommands bail).
m = re.search(r"lavish-axi(?:@[\w.\-]+)?\s+(.*)", command, re.DOTALL)
if not m:
    sys.exit(0)
target = None
for tok in re.findall(r'"([^"]+)"|\'([^\']+)\'|(\S+)', m.group(1)):
    tok = next(t for t in tok if t)
    if tok.startswith("-") or tok in ("&&", "||", ";", "|"):
        continue
    if tok in NON_RENDER:
        sys.exit(0)
    target = tok
    break
if not target or not re.search(r"\.html?$", target, re.IGNORECASE):
    sys.exit(0)

try:
    with open(target, encoding="utf-8") as f:
        html = f.read()
except OSError:
    sys.exit(0)


def clean(text):
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links -> label
    text = text.replace("`", "")
    text = re.sub(r"(\*\*|\*|__)", "", text)
    text = re.sub(r"(?<![\w])_|_(?![\w])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def keys_for(term):
    # "Full path / Lean path" -> both; "Ticket description (`TICKET.md`)" ->
    # base name + the parenthetical token. Title-Case words lower so page-case
    # usage matches; ALL-CAPS/mixed-case words stay case-sensitive.
    raw = term.replace("`", "").strip()
    out = set()
    base = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    for part in re.split(r"\s*/\s*", base):
        part = part.strip()
        if part:
            out.add(" ".join(
                w.lower() if len(w) > 1 and w[1:].islower() else w
                for w in part.split()))
    for m in re.finditer(r"\(([^)]*)\)", raw):
        inner = m.group(1).strip()
        if re.fullmatch(r"[\w.\-]+", inner):
            out.add(inner)
    return out


def parse_glossary(path):
    # Canonical glossary entry grammar (GLOSSARY-FORMAT.md): "**Term**:" then
    # definition lines until a blank line; "_Avoid_"/heading lines excluded.
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
        m = re.match(r"\*\*(.+?)\*\*\s*:\s*(.*)$", stripped)
        if m:
            flush()
            term, buf = m.group(1), ([m.group(2)] if m.group(2) else [])
            continue
        if not stripped or stripped.startswith("#") or stripped.startswith("_Avoid_"):
            flush()
            term, buf = None, []
            continue
        if term is not None:
            buf.append(stripped)
    flush()
    return entries


tips = {}
for path in (os.environ.get("LAVISH_TIPS_SEED"), os.environ.get("LAVISH_TIPS_OVERLAY")):
    if not path:
        continue
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            tips.update({k: v for k, v in data.items()
                         if not k.startswith("__") and isinstance(v, str) and v.strip()})
    except Exception:
        pass  # a broken overlay must never break a render

# Committed glossaries are canonical: workflow-wide, then the feature's own
# (declared by the artifact's afk-spec-dir meta), most specific wins.
tips.update(parse_glossary(os.environ.get("LAVISH_TIPS_WF_GLOSSARY", "")))
toplevel = os.environ.get("LAVISH_TIPS_TOPLEVEL", "")
m = re.search(
    r"<meta\s+(?:name=\"afk-spec-dir\"\s+content=\"([^\"]+)\"|content=\"([^\"]+)\"\s+name=\"afk-spec-dir\")",
    html, re.IGNORECASE)
if m and toplevel:
    spec_dir = (m.group(1) or m.group(2)).replace("\\", "/").strip("/")
    tips.update(parse_glossary(os.path.join(toplevel, spec_dir, "GLOSSARY.md")))

if not tips:
    sys.exit(0)

# </script> inside a value would end our JSON script tag early.
dict_json = json.dumps(tips, ensure_ascii=False).replace("</", "<\\/")

block = MARK_START + """
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
    re = new RegExp('(?<![\\\\w-])(?:' + keys.map(esc).join('|') + ')(?![\\\\w-])', 'gi');
  }
  rebuild();

  function tipFor(matched) {
    if (Object.prototype.hasOwnProperty.call(dict, matched)) return dict[matched];
    var lower = matched.toLowerCase();
    return Object.prototype.hasOwnProperty.call(ciMap, lower) ? ciMap[lower] : null;
  }

  function wrap(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (!n.nodeValue || n.nodeValue.length > 50000 || !re.test(n.nodeValue)) return NodeFilter.FILTER_REJECT;
        re.lastIndex = 0;
        var p = n.parentElement;
        if (!p || p.closest('script,style,noscript,textarea,.afk-tip,#afk-tip-box,#afk-btw')) return NodeFilter.FILTER_REJECT;
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
      if (elx.closest('#afk-btw,#afk-tip-box')) return;
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

  function start() {
    var pending;
    mo = new MutationObserver(function (recs) {
      var ours = recs.every(function (r) {
        return (box && (r.target === box || box.contains(r.target))) ||
               (r.target && r.target.closest && r.target.closest('#afk-btw'));
      });
      if (ours) return;
      clearTimeout(pending); pending = setTimeout(scan, 300);
    });
    btw();
    scan();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
</script>
""" + MARK_END

# Dictionary text is UTF-8-heavy (—, →, ≥): a charset-less artifact would
# garble it (browser default windows-1252). Declare one if absent.
if not re.search(r"<meta[^>]+charset", html, re.IGNORECASE):
    html = re.sub(r"(<head\b[^>]*>)", r'\1<meta charset="utf-8">',
                  html, count=1, flags=re.IGNORECASE) \
        if re.search(r"<head\b", html, re.IGNORECASE) \
        else '<meta charset="utf-8">\n' + html

# Replace a prior block (dictionary grows between renders), else inject fresh.
pattern = re.compile(re.escape(MARK_START) + r".*?" + re.escape(MARK_END), re.DOTALL)
if pattern.search(html):
    html = pattern.sub(lambda _: block, html, count=1)
else:
    m = re.search(r"</body\s*>", html, re.IGNORECASE)
    html = html[: m.start()] + block + "\n" + html[m.start() :] if m else html + "\n" + block
try:
    with open(target, "w", encoding="utf-8") as f:
        f.write(html)
except OSError:
    pass
sys.exit(0)
PYEOF
exit 0
