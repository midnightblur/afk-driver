# LAVISH-SESSIONS.md — the opt-in grilling-session render default

One home for the block `MANIFEST.md · H8` installs into the user-global
steering file(s) — targets + copy command live in that entry. Everything
between the sentinel lines lands verbatim; edit here.

<!-- afk:lavish-sessions:start -->
## Grilling sessions: render through lavish

A grilling session is an interactive stretch of rounds: the agent explains or
asks, the human answers, picks an option, or gives feedback — requirement
interviews, design reviews, option picks, plan critiques.

Scope: only inside a repository whose session has the afk-toolkit plugin
enabled, so that `${AFK_PLUGIN_ROOT}/LAVISH.md` resolves. Elsewhere this
section is inert.

In scope, every grilling session is a session-default render point, RP-10:
read that `LAVISH.md` and follow it — warm-up, one artifact file per session,
re-render each round, tooltips, queue discipline, fallback. A round asks the
human per item, so RP-10 takes that file's **kit path**: author the round JSON
per `${AFK_PLUGIN_ROOT}/LAVISH-KIT.md` and render it with
`python ${AFK_PLUGIN_ROOT}/scripts/lavish_render.py <round.json>` — never write
the markup. A skill carrying its own render point keeps its own weave; this
section covers the grilling sessions no skill weave reaches.
<!-- afk:lavish-sessions:end -->
