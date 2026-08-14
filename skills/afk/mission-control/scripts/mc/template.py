"""Injects the composed MC_DATA into the static app-shell asset
(`mc/assets/shell.html`). All artifact *parsing* stays in the tested Python
view-model; the shell's JS only renders that data to DOM (two-layer design
ADR — parsing server-side, presentation client-side).

Deliberately a pure function of its arguments — no wall-clock, no
environment lookups — so re-rendering an unchanged fixture is byte-identical
(requirement ADR-0005; SDD §5 idempotency table).
"""
from __future__ import annotations

import json
from pathlib import Path

_SHELL_PATH = Path(__file__).resolve().parent / "assets" / "shell.html"

# Injection slots in the shell asset (lockstep with mc/assets/shell.html):
#   <script id="mc-data" type="application/json">null</script>  — MC_DATA JSON
#   <!--MC_RELOAD-->                                            — reload script
_DATA_SLOT = '<script id="mc-data" type="application/json">null</script>'
_RELOAD_SLOT = "<!--MC_RELOAD-->"

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


def render_page(mc_data: dict, live_reload: bool) -> str:
    shell = _SHELL_PATH.read_text(encoding="utf-8")
    payload = json.dumps(mc_data, ensure_ascii=True)
    # `</` only occurs inside JSON strings; `<\/` is a legal JSON escape and
    # keeps a literal `</script` in the data from terminating the element.
    payload = payload.replace("</", "<\\/")
    page = shell.replace(
        _DATA_SLOT,
        f'<script id="mc-data" type="application/json">{payload}</script>',
        1,
    )
    return page.replace(_RELOAD_SLOT, _RELOAD_SCRIPT if live_reload else "", 1)
