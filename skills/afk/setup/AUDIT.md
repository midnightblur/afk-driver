# AUDIT.md — the drift audit (`/afk:setup audit`)

Hunts staleness between the plugin's artifacts and reality. Read-only — returns
findings routed to the file that must change. The sweeps are repo-wide grep/read
work: delegate to fresh subagents per `DELEGATION.md` (plugin root), keep only
the digests.

Run all six checks; report even when clean.

## 1 · Structural consistency

Four surfaces that enumerate skills must agree:
`.claude-plugin/plugin.json` (`skills` array) ↔ skill dirs on disk
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
- Known CLIs: `glab|mmdc|npx |npm |node |python|mvnw|envctl|bash `
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
- **External anchors:** paths into the core-services tree the skills lean on —
  at minimum `11700-payable/verification/{ui-e2e,api}/AUTHORING.md`,
  `tools/payable/envstack/envctl.py` (`hooks/app-start-gate.sh` ships in-plugin
  — first scope).

Route: the citing file (fix the pointer) — unless the target genuinely moved,
then the finding names both sides.

## 4 · Registry compliance

For each `FRESHNESS.md` registry row: the artifact exists, its steward file
exists, the update-trigger surfaces it names still exist. For each lockstep
pair/triple named in `CLAUDE.md` "Lockstep": the sections the pair binds
(emitter grammar ↔ parser expectation) are both still present. Route:
`FRESHNESS.md` for dead rows; the drifted member for broken pairs.

## 5 · Generated-layer sync (Codex mirror)

Run `python tools/payable/ai-agents/codex-sync/generate.py --check` from the
repo root. Any drift → finding (route: rerun the generator and commit — the
listed canonical source changed without regeneration). Provider-independent:
runs whether or not Codex CLI is installed; it audits repo artifacts, not the
machine. Also spot-check that `hooks/lib/provider.sh` and the harness plugin's
synced copy are byte-identical (the same `--check` covers it).

## 6 · Glossary term usage

Every `**Term**:` heading in the plugin-root `GLOSSARY.md` must have ≥1 consumer
file using the term (grep the plugin); a zero-hit term → finding (route: `GLOSSARY.md`).

## Report

Ranked findings (staleness that misleads an agent first, cosmetic last), each:
`[check#] what drifted → file to fix`. Close per `REPORTING.md` — one
plain-terms sentence: is the plugin's documentation trustworthy now, and if not,
which file misleads. Clean run ⇒ say so explicitly; silence is not a verdict.
