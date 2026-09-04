# AUDIT.md — the drift audit (`/afk:setup audit`)

Hunts staleness between the plugin's artifacts and reality. Read-only — returns
findings routed to the file that must change. The sweeps are repo-wide grep/read
work: delegate to fresh subagents per `DELEGATION.md` (plugin root), keep only
the digests.

Run all six checks; report even when clean.

## 1 · Structural consistency

Five surfaces that enumerate skills must agree:
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` (`skills` arrays) ↔ skill dirs on disk
(`skills/*/*/SKILL.md`) ↔ `README.md` §10 skill reference ↔ `CLAUDE.md`
"The skills". A skill on one surface, absent from another → finding (route: the
surface missing it — or `plugin.json` if the dir itself is the stray). Also:
both `.claude-plugin/*.json` descriptions still describe the chain's current
shape.

## 2 · Dependency drift

Grep `skills/`, `hooks/`, `agents/` for dependency-shaped references. Named
patterns are a **floor, not the definition** — an unfamiliar tool name is what
this check exists to catch, so the generic shapes are mandatory:

- MCP tools: `mcp__[a-z_]+`
- Known CLIs: `glab|gh|mmdc|npx |npm |node |python|mvnw|bash `
- **Generic command shapes:** any backticked invocation carrying flags
  (`` [a-z][a-z0-9_-]+ --[a-z-]+ ``) and any `scripts/*.{py,sh,mjs,cmd}`
  execution — a hit whose leading token is not a known CLI above is a candidate,
  *especially* if unfamiliar
- Env vars: `[A-Z][A-Z_]{3,}` — every hit is a candidate unless it matches a
  MANIFEST `E`-table var, an `S`-entry secret, or an obvious non-var (Markdown
  heading, acronym in prose)

Diff the hit-set against `MANIFEST.md` entries. A dependency a skill references
but registered nowhere → finding (route: `MANIFEST.md`); a manifest entry no
skill references anymore → finding too (route: delete or annotate).

## 3 · Pointer integrity

Every relative file path cited in the plugin's `.md` files must resolve on
disk — a dead pointer is a stale doc. Sweep two scopes:

- **In-plugin:** paths under the plugin root (sibling `.md`s, `skills/...`,
  `hooks/...`, `agents/...`, `scripts/...`).
- **External anchors:** paths into the consuming repository the skills lean on
  — every one of them comes from `.afk/config.yaml` (a `verification.tiers`
  command, a `verification.env` command, a `setup.extra` file), so the check is
  that the configured path exists, not that a named path does.

Route: the citing file (fix the pointer) — unless the target genuinely moved,
then the finding names both sides.

## 4 · Registry compliance

For each `FRESHNESS.md` registry row: the artifact exists, its steward file
exists, the update-trigger surfaces it names still exist. For each lockstep
pair/triple named in `CLAUDE.md` "Lockstep": the sections the pair binds
(emitter grammar ↔ parser expectation) are both still present. Route:
`FRESHNESS.md` for dead rows; the drifted member for broken pairs.

## 5 · Native harness contract

Run `bash "$AFK_PLUGIN_ROOT/hooks/native-contract-gate.sh"`
from the repo root. A failure routes to the named surface. Then run each
installed harness's setup probes from `MANIFEST.md`: plugin enablement, native
skill catalog, hooks, shared MCP, agent definitions, and local activation
cleanup. Record live conformance gaps in `providers/CONFORMANCE.md`.

## 6 · Glossary term usage

`python "$AFK_PLUGIN_ROOT/scripts/glossary_usage.py" "$AFK_PLUGIN_ROOT"` — every
`**Term**:` heading in the plugin-root `GLOSSARY.md` must have ≥1 consumer file
using the term.

Do not grep the heading string. A heading is written for a reader: prose writes
`sign-off` where the heading writes `Sign-off`, one heading can head several
terms, and a trailing parenthetical names the variants the entry covers rather
than part of the term. The script case-folds, drops that qualifier, and splits a
multi-term heading, then requires a consumer for each part.

A zero-hit term means no file uses that word. It is a prompt to look, not a
verdict, and never on its own a reason to delete an entry: check first whether
prose spells the term differently. Where prose legitimately writes it shorter,
the fix is an `_Also_:` line on that entry (`skills/utils/glossary/GLOSSARY-FORMAT.md`),
not a looser check. Report it as a finding (route: `GLOSSARY.md`) only once you
have looked and the term really is unused.

`scripts/tests/test_glossary_usage.py` pins that normalization against the
sixteen headings an earlier, exact-match check reported as unused while every
one of them was in use.

## Report

Ranked findings (staleness that misleads an agent first, cosmetic last), each:
`[check#] what drifted → file to fix`. Close per `REPORTING.md` — one
plain-terms sentence: is the plugin's documentation trustworthy now, and if not,
which file misleads. Clean run ⇒ say so explicitly; silence is not a verdict.
