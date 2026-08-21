# LANGUAGE.md — every word the plugin produces

Binding on every surface that produces words — every skill, agent, hook,
script, template, and harness/steering file, current **and any added later**:
the conversation with the human (replies, questions, option lists, status
lines) and every artifact written to disk or published (specs, plans,
contracts, reports, steering notes, tickets, HTML pages, notifications),
whether a human or another agent reads it. Three rules: write **Simplified
Technical English** (§1), use the **vocabulary the glossaries own** (§2), keep
artifacts **compact** (§3). Root docs are not auto-loaded, so a producing
surface carries a one-line pointer here — never a restatement: every
`SKILL.md` and agent definition opens with one (gate:
`hooks/skill-registry-gate.sh` check D refuses a file without it — new files
included), and every artifact emitter/template carries a read-this-first
pointer.

## 1. Simplified Technical English (ASD-STE100 spirit) — which words

- Short sentences, one point each (aim ≤ 20 words); one instruction per sentence.
- Active voice, present tense: "run the build", not "the build should be run".
- One term, one meaning — and one meaning, one term. Never rotate synonyms for variety.
- Prefer the common word. Expand every abbreviation at first use, per report or artifact.
- No idioms, no metaphors, no filler, no rhetorical questions.
- Numbers, not adjectives: "3 of 9 subtasks parked", never "most subtasks parked".

## 2. Ubiquitous language — whose terms

- Workflow terms (stages, modes, states, verdicts, artifact names) come from `GLOSSARY.md` (plugin root), spelled as defined there.
- Domain terms come from the target repo's glossaries (start at its `GLOSSARY-MAP.md`).
- Never coin a synonym for a term a glossary owns; never redefine one inline — point at its home.
- A recurring domain term with no entry is a gap: name it once, consistently, and route it to the glossary steward (`/afk:glossary`).
- Jargon stays out of the reader-facing plain-terms sentence — that sentence must stand alone without any glossary (`REPORTING.md`).

## 3. Concision — how much

Applies to every markdown artifact a skill writes (PRD, SDD, ADRs, plan index
+ subtask contracts, verification/demo/brief docs, grill logs,
review/adversary/retro reports, steering notes, handoff docs):

- **Every sentence carries a fact the reader acts on.** No narration, motivation, meta-commentary, restated upstream context, or "unlike X" asides. Drop articles, fillers, hedges where meaning survives; fragments OK.
- **Complete over short.** Never drop a fact, constraint, citation, code anchor, or table row to save words — a shorter artifact that loses a fact failed. Cut words, not facts.
- **One fact, one home.** State each fact once at its owning spot; elsewhere point (path, section, stable ID). One-liner pointers beat explanations — reference the key location, let the reader open the code. Restate only what a format section explicitly requires (e.g. a contract's `Context excerpts`).
- **Tables beat prose for parallel structure** — reach for one at the third bullet of the same shape; enumerable sets get a catalog + reference-by-ID, never re-narration.
- **Directive subject + scope stated.** "Never run migrations against prod DB" ≠ "Never run migrations".
- **Formats are contracts.** Compactness changes the words inside a section, never the section set or grammar the owning format file defines.

### Steering notes (CLAUDE.md tree, role sidecars, `.claude/rules`) — additional rules

Read cold by future agents AND human teammates, and long-lived — unlike run artifacts, so also:

- **Stay generic — no volatile specifics.** State the rule, not the current value: version numbers, counts, dates, "current" dep lists go stale → wrong-but-authoritative. Volatile specifics live where they're authoritative (lockfile, code, registry). Caveat: identifiers (paths, commands, flags) are durable — keep them verbatim; versions/counts attached to them are not — drop or generalize. (Run artifacts — PRD/SDD/plan/reports — are dated snapshots; current values belong there.)
  - Bad: `pin foo-lib 1.60.0 (1.61.0 too young); 5 overrides`.
  - Good: `deps: exact pins + 30-day age floor; pin too-new transitives via overrides`.
- **Shape of a good line:** `<topic>: <non-obvious fact / pointer>. <gotcha if any>.` **One line is the default; earn every line past it** — a rule = that line + at most a gotcha/exception clause. A `Bad → Good` block is last resort, only when the one-liner is genuinely ambiguous in prose; propose the shortest form first — let the user ask for an example, never have to cut one.
  - Good: `Auth: token TTL checked in AuthFilter (uses <, off-by-one on expiry). Refresh path skips filter.`
  - Good: `Migrations: Flyway V{n}__ naming. Never edit applied migration — add new. Baseline V1 in db/migration.`
  - Bad (obvious → drop): `This project uses Spring Boot, a popular Java web framework.`
- **Leaf/subdir CLAUDE.md = directive only.** Emit the steering heading (`## …`) + body, nothing else — no file-title line, no `Scope:`/`Inherits` preamble: the dir path already scopes it and ancestors auto-load, so a banner adds tokens, not steering. Legacy leaf files carrying one are not the pattern to copy.
- **Match the target file's heading structure + density** — meaning density/heading depth, not replicating a redundant title/`Scope:` banner a legacy file happens to carry.
- **Block comments** `<!-- … -->` are stripped from agent context (free) but visible to humans in the raw file. Sparingly, for human-maintainer notes — never provenance (we don't track provenance).

## Scope, exceptions, specialized bars

- Prose only. Code, code comments, commit messages, and test names keep their own conventions.
- Verbatim identifiers — paths, commands, flags, field names, env vars, error strings — are never reworded or paraphrased to satisfy any rule here.
- A user-invoked compression mode overrides sentence shape while active; §2 and §3 still bind.
- Specialized bars own only their deltas: PRD catalog mechanics (`skills/afk/to-prd/PRD-TEMPLATE.md`), human-facing status lines (`REPORTING.md` — the `In plain terms:` sentence stays jargon-free prose, never compressed), glossary definitions (`skills/utils/glossary/SKILL.md` — definition depth is deliberate), Jira ticket bodies (`/afk:to-ticket` — narrative documentation prose, never fragments).
