# Digest contract — the dashboard's LLM-authored design layer

One home for the digest files under `{spec_dir}/plan/digests/`. Emitting side:
this skill's `build` mode. Parsing side: `scripts/mc/digests.py` (**lockstep**:
a schema/manifest change here is a same-commit change there, and vice versa).

Digests are **design synthesis, never status**. Status (progress, gates,
timeline, insights) is derived live by the renderer from the plan artifacts —
a digest that restates status would go stale and lie. Digests hold what only
reading the PRD/SDD/ADRs yields: architecture, flows, entities, decisions,
critical logic, vocabulary.

Digests are **committed to git** — built once per spec change, reused by every
render, teammate, and retro view.

## Layout

```
{spec_dir}/plan/digests/
  manifest.json        # freshness ledger — one entry per digest
  architecture.json
  flows.json
  entities.json
  adrs.json
  critical-logic.json
  legend.json
```

## Manifest grammar

```json
{
  "architecture": {
    "sources": [{"path": "SDD.md", "sha256": "<hex of file bytes>"}],
    "built_at": "YYYY-MM-DD HH:mm"
  }
}
```

- `path` — spec-dir-relative; list **every spec-dir file** the digest was
  synthesized from. A path outside the spec dir is treated as drifted by the
  renderer, so out-of-folder inputs (e.g. the plugin-root `GLOSSARY.md` behind
  the legend) are deliberately NOT listed — they version with the plugin, not
  the feature, and sit outside the freshness fence.
- `sha256` — of the source file's bytes at build time. The renderer re-hashes
  on every render; any mismatch (or missing source) marks the digest **stale**
  (amber banner naming the drifted sources; old content still shown).
- No manifest entry → the digest renders as stale with "freshness unknown".

Hash recipe: `python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <file>`.

## Authoring rules (all digests)

- **Traceable or absent.** Every claim comes from a named source file; if the
  sources are silent on a field, omit the field. Never pad, never invent.
- **Skip empty digests.** A digest whose sources give it nothing true to say
  (e.g. `entities` for a feature with no data layer) is **not built** — the
  renderer's "not built" hint is honest; an empty-but-present digest is not.
- **Write for a teammate who has NOT read the SDD.** One-line fields
  (`essence`, `responsibility`, `statement`, `definition`) ≤ 140 chars, plain
  words, no citation tags, no section numbers, term defined before used.
- Detail belongs in the optional long fields (`detail`, `decision`, `why`) —
  the shell hides them behind expanders (essentials first, depth on demand).
- IDs are stable handles: keep the source documents' own ids (module ids,
  ADR numbers, subtask ids) so live data joins onto them.

## Digest types

### architecture.json — modules, dependencies, seams

Sources: SDD topology/boundary/module sections (+ the plan's solution map for
subtask ownership). Shape:

```json
{
  "modules": [{
    "id": "…", "name": "…",
    "responsibility": "one plain sentence",          // required
    "layer": "…",                                    // optional grouping label
    "interface": "the public surface in one line",
    "depends_on": ["<module id>", "…"],              // must stay acyclic — rendered as a DAG
    "seams": ["<seam name>", "…"],
    "subtasks": ["NNNN-slug", "…"],                  // who builds/built it
    "detail": "longer prose, shown behind an expander"
  }],
  "seams": [{"id": "…", "boundary": "…", "failure": "what failure looks like + routing", "test": "how it's proven"}],
  "diagrams": [{"title": "…", "source": "<mermaid text>", "svg": "<svg…>"}]
}
```

Required per module: `id`, `name`, `responsibility`. Dependency direction is
dependent → dependency (the arrow the SDD draws).

`diagrams`: carry over the SDD's own mermaid blocks (`source` verbatim), and
**always attempt** to pre-render each to SVG and embed as `svg` — the page has
no mermaid engine, so a source-only diagram displays as raw text. Render via
`mmdc` if on PATH, else `npx -y @mermaid-js/mermaid-cli` (provisioned per
`skills/afk/setup/MANIFEST.md` N2), with `-b white` (the white plate keeps the
diagram legible in dark theme). The CLI emits every SVG with `id="my-svg"` —
rewrite that token to a unique id per diagram (e.g. `mc-arch-dg{N}`) before
embedding, or two inline SVGs cross-talk styles and marker refs. Render
failure → keep `source` only (the shell falls back to showing it). Never
reference external files.

### flows.json — journeys and processes, as steppable simulations

Sources: PRD user stories, `VERIFICATION-PLAN.md` UI journeys (user-facing
flows), SDD process/sequence sections (system flows). Shape:

```json
{"flows": [{
  "id": "…", "title": "…", "summary": "one line",
  "kind": "linear | branching | concurrent",
  "steps":  [{"t": "1 · Short title", "who": "you|machine|gate", "d": "goal + observable result, 1-3 sentences", "n": "optional footnote"}],
  "nodes":  [{"id": "…", "t": "step|dec|end", "h": "heading", "d": "body",
              "next": "<node id>",
              "opts": [{"label": "…", "note": "one-line consequence", "next": "<node id>"}]}],
  "cols": 8, "unit": ["t1", "…"],
  "lanes": [{"label": "…", "bars": [{"start": 1, "end": 3, "text": "…", "cls": "a|b|c|d"}]}]
}]}
```

`kind` picks the widget and which fields are read: `linear` → `steps`
(slider), `branching` → `nodes` (choice simulator; first node is the start,
`dec` nodes fork on the reader's pick), `concurrent` → `cols`/`unit`/`lanes`
(lane chart; one `cls` letter per workstream). 4–9 steps per flow; every step
names an actor and an observable result. Cover: the primary user journey, the
main failure/park path (branching), and any genuinely concurrent
process — not every scenario in the verification plan.

### entities.json — data shapes, constraints, indexes

Sources: the SDD's data-architecture section. Shape:

```json
{"entities": [{
  "id": "…", "name": "…", "essence": "what it is, one line",
  "fields": [{"name": "…", "type": "…", "constraint": "unique/scoped/nullable/…", "essential": true}],
  "indexes": ["<index or key>", "…"],
  "relations": [{"to": "<entity id>", "kind": "1-n | n-1 | 1-1 | n-n", "label": "…"}],
  "retention": "…", "pii": "…"
}], "notes": "cross-entity constraints worth one line"}
```

Required: `id`, `name`, `essence`. Mark ≤ 7 design-carrying fields
`essential: true` (shown by default); the rest render behind an expander.
Constraints that protect an invariant (uniqueness, tenancy/scoping,
append-only) always make the essential cut.

### adrs.json — decision cards

Sources: every file under `adr/requirements/` and `adr/design/`. Shape:

```json
{"adrs": [{
  "id": "0001", "tier": "requirement | design", "title": "…",
  "essence": "the decision itself in one sentence — not the title restated",
  "status": "accepted | superseded | …",
  "decision": "…", "why": "…", "tradeoffs": "what was given up / rejected",
  "supersedes": "…", "superseded_by": "…",
  "path": "adr/design/0001-….md"
}]}
```

Required: `id`, `tier`, `title`, `essence`. One entry per ADR file, none
skipped — a superseded ADR is history worth seeing, marked by `superseded_by`.

### critical-logic.json — what must not break

Sources: SDD invariant/domain tables, budgets/caps (NFR numbers), conflict
procedures, landmine notes in seam/change-impact sections. Shape:

```json
{"items": [{
  "id": "…", "kind": "invariant | budget | gotcha",
  "title": "…", "statement": "the rule, one plain sentence",
  "why": "…", "enforced_at": "file/gate/test that holds the line",
  "breaks_if": "the concrete way it gets violated"
}]}
```

Required: `id`, `kind`, `title`, `statement`. 3–9 items — this is the
"do not break" shortlist, not an index of the SDD; if everything is critical,
nothing is.

### legend.json — the vocabulary behind the tooltips

Sources: the plugin-root `GLOSSARY.md` (workflow vocabulary the dashboard
displays: statuses, verdicts, tiers, modes, gate names), the feature's own
glossary/PRD terms, seam and module names. Shape:

```json
{"terms": [{
  "term": "…", "aliases": ["…"],
  "definition": "plain-terms, without using the term itself",
  "category": "workflow-state | gate | artifact | module | seam | domain"
}]}
```

Required: `term`, `definition`. Every ID-ed token a reader meets on the page
should resolve here — the shell wires these definitions into hover tooltips
everywhere, and renders the full list as the Legend section. Synthesize
definitions in your own plain words; do not paste glossary entries.

## Build protocol (the skill's `build` mode)

1. `python3 scripts/mission_control.py {spec_dir} --check-digests` — the
   freshness report. Only `stale`/`missing`/`invalid` digests are rebuilt;
   `ok` ones are never touched.
2. Fan out **one subagent per digest to rebuild**, in parallel, per
   `DELEGATION.md` — each reads only its digest type's sources plus this
   file's matching section, and returns the digest JSON (no file writes from
   subagents).
3. Validate + write: the orchestrator writes each returned digest and its
   manifest entry (all sources + hashes + `built_at`) together, then re-runs
   `--check-digests` — every rebuilt digest must now report `ok`; anything
   else bounces back to its subagent once, then surfaces to the human.
4. Report per `REPORTING.md`: which digests were rebuilt, which skipped
   (fresh or deliberately empty), and the live page/snapshot to look at.
