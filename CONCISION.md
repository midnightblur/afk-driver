# CONCISION.md — artifacts are compact by default

Binding on every markdown artifact a skill writes (PRD, SDD, ADRs, plan index + subtask contracts, verification/demo/brief docs, grill logs, review/adversary/retro reports, steering notes, handoff docs). Root docs are not auto-loaded at invocation, so every emitter/template carries a read-this-first pointer to this file, never a restatement. This file governs **how much** to write; `LANGUAGE.md` (plugin root) governs **which words** — sentence shape and glossary terms — and binds replies as well as artifacts. Remaining specialized bars own only their deltas: PRD catalog mechanics (`skills/afk/to-prd/PRD-TEMPLATE.md`), human-facing status lines (`REPORTING.md` — the `In plain terms:` sentence stays jargon-free prose, never compressed), glossary definitions (`skills/utils/glossary/SKILL.md` — definition depth is deliberate), Jira ticket bodies (`/afk:to-ticket` — narrative documentation prose, never fragments).

## The bar — every artifact

- **Every sentence carries a fact the reader acts on.** No narration, motivation, meta-commentary, restated upstream context, or "unlike X" asides. Drop articles, fillers, hedges where meaning survives; fragments OK.
- **Complete over short.** Never drop a fact, constraint, citation, code anchor, or table row to save words — a shorter artifact that loses a fact failed. Cut words, not facts.
- **One fact, one home.** State each fact once at its owning spot; elsewhere point (path, section, stable ID). One-liner pointers beat explanations — reference the key location, let the reader open the code. Restate only what a format section explicitly requires (e.g. a contract's `Context excerpts`).
- **Tables beat prose for parallel structure** — reach for one at the third bullet of the same shape; enumerable sets get a catalog + reference-by-ID, never re-narration.
- **Identifiers verbatim.** File paths, commands, flags, field names, env vars, error strings are never paraphrased.
- **Directive subject + scope stated.** "Never run migrations against prod DB" ≠ "Never run migrations".
- **Formats are contracts.** Compactness changes the words inside a section, never the section set or grammar the owning format file defines.

## Steering notes (CLAUDE.md tree, role sidecars, `.claude/rules`) — additional rules

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
