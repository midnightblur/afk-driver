#!/usr/bin/env bash
# lavish-dark.sh — PreToolUse hook (Bash/PowerShell): force dark mode on lavish-axi artifacts.
#
# Intercepts a `npx lavish-axi@<ver> <file>` RENDER command and injects a
# self-contained dark-mode override into the artifact HTML on disk before the
# render runs. Deterministic enforcement — no skill instruction involved; the
# authoring agent stays unaware.
#
# Mechanism (lavish-axi itself has no theme param — theming is artifact-side):
# - DaisyUI artifact (the lavish-recommended design system): force
#   `data-theme="dark"` on the <html> tag — native dark palette.
# - Anything else: injected script measures the painted background luminance at
#   load; a light page gets the invert+hue-rotate treatment (images/video/
#   canvas counter-inverted), an already-dark page is left untouched.
# Idempotent via marker comment. Never blocks: always exits 0.

set -u

input=$(cat)

# Fast bail: virtually every command is not a lavish render.
case "$input" in
  *lavish-axi*) ;;
  *) exit 0 ;;
esac

LAVISH_HOOK_INPUT="$input" python - <<'PYEOF'
import json, os, re, sys

MARKER = "<!-- afk-lavish-dark -->"
SNIPPET = MARKER + """
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

NON_RENDER = {"poll", "end", "stop", "playbook", "share", "setup", "update"}

try:
    command = json.loads(os.environ["LAVISH_HOOK_INPUT"]).get("tool_input", {}).get("command", "")
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
if MARKER in html:
    sys.exit(0)

if re.search(r"daisyui", html, re.IGNORECASE):
    # Native theming: force the page-level DaisyUI theme to dark.
    def darken(tag):
        t = tag.group(0)
        if re.search(r"data-theme\s*=", t, re.IGNORECASE):
            return re.sub(r"data-theme\s*=\s*([\"']).*?\1", 'data-theme="dark"', t, flags=re.IGNORECASE)
        return t[:-1] + ' data-theme="dark">'

    html = re.sub(r"<html\b[^>]*>", darken, html, count=1, flags=re.IGNORECASE)
    inject = MARKER + "\n<style>html{color-scheme:dark}</style>\n"
else:
    inject = SNIPPET

m = re.search(r"</body\s*>", html, re.IGNORECASE)
html = html[: m.start()] + inject + html[m.start() :] if m else html + inject
try:
    with open(target, "w", encoding="utf-8") as f:
        f.write(html)
except OSError:
    pass
sys.exit(0)
PYEOF
exit 0
