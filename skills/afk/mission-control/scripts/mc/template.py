"""Composes parsed panels into one self-contained `index.html` (ADR-0007,
ADR-0006). Absent panels render as an empty-state card.

Deliberately a pure function of its `panels` argument only — no wall-clock,
no environment lookups — so the page stays a pure function of the source
artifacts end to end (requirement ADR-0005) and re-rendering an unchanged
fixture is byte-identical (SDD §5 idempotency table).
"""
from __future__ import annotations

import html

from .vm import Absent

_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Mission Control</title>
<style>
{css}
</style>
</head>
<body>
<header><h1>Mission Control</h1></header>
<main class="mc-grid">
{cards}
</main>
{script}
</body>
</html>
"""

_CSS = """
body { font-family: -apple-system, "Segoe UI", Arial, sans-serif; margin: 0; background: #0b0e14; color: #e6e6e6; }
header { padding: 1rem 1.5rem; border-bottom: 1px solid #22262f; }
header h1 { margin: 0; font-size: 1.25rem; }
.mc-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; padding: 1.5rem; }
.mc-card { background: #12151c; border: 1px solid #22262f; border-radius: 8px; padding: 1rem; }
.mc-card h2 { margin-top: 0; font-size: 1rem; }
.mc-empty-state { color: #888; font-style: italic; }
.mc-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.mc-table th, .mc-table td { text-align: left; padding: 0.25rem 0.5rem; border-bottom: 1px solid #22262f; }
.mc-empty-sub { color: #888; font-size: 0.8rem; padding: 0.25rem 0; }
.mc-gate-group { margin-bottom: 0.75rem; }
.mc-gate-group h3 { margin: 0.25rem 0; font-size: 0.9rem; color: #aab; }
"""

# Live-reload polling only — a GET-only fetch loop, no mutating control
# (AC-012). Never injected into --once output, which must stay fully inert.
_RELOAD_SCRIPT = """<script>
(function () {
  var lastToken = null;
  setInterval(function () {
    fetch("/__mc_token").then(function (r) { return r.text(); }).then(function (t) {
      if (lastToken !== null && t !== lastToken) { location.reload(); }
      lastToken = t;
    }).catch(function () {});
  }, 1500);
})();
</script>"""


def render_page(panels: list, live_reload: bool) -> str:
    cards = "\n".join(_render_card(panel) for panel in panels)
    script = _RELOAD_SCRIPT if live_reload else ""
    return _PAGE_TEMPLATE.format(css=_CSS, cards=cards, script=script)


def _render_card(panel) -> str:
    if isinstance(panel, Absent):
        title = html.escape(panel.panel_id.replace("_", " ").title())
        return (
            f'<section class="mc-card mc-card-absent" data-panel="{html.escape(panel.panel_id)}">'
            f"<h2>{title}</h2>"
            f'<div class="mc-empty-state">Absent &mdash; {html.escape(panel.reason)}</div>'
            "</section>"
        )
    return (
        f'<section class="mc-card" data-panel="{html.escape(panel.panel_id)}">'
        f"<h2>{html.escape(panel.title)}</h2>"
        f"{panel.html}"
        "</section>"
    )
