# Content style — dense but parseable

CLAUDE.md read by future agents cold AND human teammates (committed). Compress like caveman; stay readable.

## Compress
- Drop articles (a/the), fillers (just/really/basically), hedges.
- Fragments OK. Arrows for causality (X -> Y). One word when enough.
- One-liner pointers > explanations. Reference key locations; let agent read the code.
- Tables/bullets when 3+ parallel items.

## Keep verbatim (NEVER paraphrase)
File paths, commands, flag names, field names, env vars, error strings.

## Stay generic — no volatile specifics
State the rule, not the current value. Version numbers, counts, dates, "current" dep lists go
stale → wrong-but-authoritative. Keep CLAUDE.md to the durable principle; let volatile specifics
live where they're authoritative (`package.json`/lockfile, code, memory).
- Bad: `pin foo-lib 1.60.0 (1.61.0 too young); 5 overrides`.
- Good: `deps: exact pins + 30-day age floor; pin too-new transitives via overrides`.
- Caveat to "Keep verbatim" above: identifiers (paths, commands, flags, fields, env vars)
  are durable — keep them. Version numbers / counts attached to them are NOT — drop or generalize.

## Keep precise
- Directive subject + scope. "Never run migrations against prod DB" ≠ "Never run migrations".
- Match target file's existing heading structure + density — meaning *density / heading depth*,
  NOT replicating a redundant title / `Scope:` banner some legacy file happens to carry.

## Leaf/subdir CLAUDE.md = directive only
Emit the steering heading (`## …`) + body, nothing else. NO file-title line (`# CLAUDE.md — <dir>`),
NO `Scope:` / `Inherits` preamble — the dir path already scopes it (progressive disclosure) and
ancestors auto-load, so a title/Scope banner adds tokens, not steering (fails inclusion bar #3).
Legacy leaf files carrying that banner are NOT the pattern to copy.

## Shape of a good line
`<topic>: <non-obvious fact / pointer>. <gotcha if any>.`

**One line is the default; earn every line past it.** A rule = that line + at most a gotcha/exception
clause. A `Bad → Good` block is last resort — only when the one-liner is genuinely ambiguous in prose;
most rules ship without one. Propose the shortest form first — let the user ask for an example, never
have to cut one.

Good:
- `Auth: token TTL checked in AuthFilter (uses <, off-by-one on expiry). Refresh path skips filter.`
- `Migrations: Flyway V{n}__ naming. Never edit applied migration — add new. Baseline V1 in db/migration.`
- `Forms: *.form.vue use useFormGuard() for dirty-check; skip it -> nav guard breaks.`

Bad (obvious / verbose → drop):
- `This project uses Spring Boot, a popular Java web framework.`

## Block comments
`<!-- ... -->` stripped from agent context (free) but visible to humans in raw file.
Use sparingly for human-maintainer notes. NOT for provenance (we don't track provenance).
