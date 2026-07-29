#!/usr/bin/env bash
# lavish-tips.sh — PreToolUse hook (Bash/PowerShell): inject the persistent
# tooltip dictionary into lavish-axi artifacts.
#
# Intercepts a `npx lavish-axi@<ver> <file>` RENDER command and embeds, into the
# artifact HTML on disk, (a) the merged tooltip dictionary and (b) a
# self-contained hover runtime that wraps every dictionary term in the page and
# serves a floating tooltip; it also promotes author-side `title=`/`data-tip`
# attributes (per-artifact item ids) into the same tooltip UI. Deterministic —
# no LLM at injection time; the authoring agent's only job is keeping the
# dictionary itself fed (LAVISH.md "Tooltips").
#
# Dictionary sources, merged in order (later wins):
#   1. seed    — lavish-tips.json next to this script (workflow vocabulary;
#                Lockstep-sanctioned copies, owning files win on conflict)
#   2. overlay — <main-checkout>/.claude/lavish-tips.json in the gated repo
#                (domain/ticket vocabulary; grows over time, shared across
#                worktrees via the git common dir, like the lesson ledger)
# Keys starting with "__" are metadata, ignored. A key with any uppercase
# letter matches case-sensitively; all-lowercase keys match case-insensitively;
# whole-word only (word chars and '-' bound the match).
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

seed="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lavish-tips.json"
overlay=""
if common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); then
  overlay="$(dirname "$common")/.claude/lavish-tips.json"
fi

LAVISH_TIPS_INPUT="$input" LAVISH_TIPS_SEED="$seed" LAVISH_TIPS_OVERLAY="$overlay" python - <<'PYEOF'
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
if not tips:
    sys.exit(0)

try:
    with open(target, encoding="utf-8") as f:
        html = f.read()
except OSError:
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
</style>
<script id="afk-tips-dict" type="application/json">""" + dict_json + """</script>
<script>
(function () {
  var el = document.getElementById('afk-tips-dict');
  var dict; try { dict = JSON.parse(el.textContent); } catch (e) { return; }
  var keys = Object.keys(dict).sort(function (a, b) { return b.length - a.length; });
  if (!keys.length) return;
  var ciMap = {};
  keys.forEach(function (k) { if (k === k.toLowerCase()) ciMap[k] = dict[k]; });
  var esc = function (s) { return s.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'); };
  var re = new RegExp('(?<![\\\\w-])(?:' + keys.map(esc).join('|') + ')(?![\\\\w-])', 'gi');

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
        if (!p || p.closest('script,style,noscript,textarea,.afk-tip,#afk-tip-box')) return NodeFilter.FILTER_REJECT;
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
    wrap(document.body);
    if (mo) mo.observe(document.body, { childList: true, subtree: true });
  }
  function start() {
    var pending;
    mo = new MutationObserver(function (recs) {
      var ours = recs.every(function (r) { return box && (r.target === box || box.contains(r.target)); });
      if (ours) return;
      clearTimeout(pending); pending = setTimeout(scan, 300);
    });
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
