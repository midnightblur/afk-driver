# Placement engine

Per candidate fact, route by scope + cohesion. First match wins.

## Decision order
1. Personal/uncommitted (sandbox URL, local creds)? → `CLAUDE.local.md` (gitignored).
2. Applies to ALL your projects (personal pref)? → `~/.claude/CLAUDE.md`. (rare; flag — outside project scope)
3. Cross-cutting working principle for this repo? → write it as an **in-repo per-directory note**
   at the lowest common ancestor of the current checkout. Do NOT route it out to `~/.claude/shared`.
4. About a *kind-of-file* regardless of location (every `*.repository.ts`, every migration, every
   `*.form.vue`)? → `.claude/rules/<topic>.md` with `paths:` glob.
5. About one module/dir subtree? → that subdir's `CLAUDE.md`.
6. Project-wide, no tighter home? → root `CLAUDE.md` (`./CLAUDE.md` or `./.claude/CLAUDE.md`).
7. Fails inclusion bar / obvious / one-off? → DROP.

## Cohesion test (the 4-vs-5 tie-break)
Ask: "what is this guidance ABOUT?"
- a **place** (this module/dir does X, this service's quirk) → subdir `CLAUDE.md`
- a **kind-of-file** anywhere (how to write any X) → `.claude/rules/`+`paths:`
Pick by the natural unit of the knowledge, NOT by counting files.

| paths glob | matches |
|---|---|
| `**/*.repository.ts` | every repository file |
| `src/main/resources/db/migration/**` | every migration |
| `**/*.form.vue` | every form component |

`.claude/rules/` files MUST declare `paths:`. Always-on cross-cutting topics live in an in-repo
per-directory note (decision #3), not in `rules/`.

## Dedup vs specialization
Before adding to a child, read full root→child ancestor chain + applicable rules.
- **Dup** (child repeats parent) → don't add; in AUDIT, delete the child copy.
- **Specialization** (child refines/overrides parent for this scope) → keep, phrase as **delta**:
  "Unlike root default, here X because Y." Not a dup.

## Dedup direction (AUDIT)
Shared content lives at the **lowest common ancestor** covering all consumers.
- Two+ siblings repeat it → lift to nearest common parent (or root).
- Only one subtree needs it → push down, strip from parent.

## In-repo notes, not a shared layer
Cross-cutting principles live as **in-repo per-directory notes**, NOT an out-of-repo
`~/.claude/shared` `@import` layer. A note is written to the current checkout at the lowest common
ancestor of what it steers; branch/feature/module-specific guidance goes in that directory's local
`CLAUDE.md`. The write boundary is owned by SKILL.md's Safety section — don't restate it here.
