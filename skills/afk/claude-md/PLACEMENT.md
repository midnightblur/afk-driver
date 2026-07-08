# Placement engine

Per candidate fact, route by scope + cohesion. First match wins.
After picking the directory (steps below), ALSO route by audience — see "Audience routing" at the bottom.

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

## Audience routing — CLAUDE.md vs role sidecars

A directory's `CLAUDE.md` auto-loads (whole file) for EVERY agent that reads any file under it —
planner, griller, reviewer, implementer alike. Content that only one activity needs pollutes all
the others. So within the chosen directory, route each fact by audience into a **closed set** of
files:

| File | Auto-loads? | Audience / read trigger | Content | Allowed level |
|---|---|---|---|---|
| `CLAUDE.md` | yes | everyone | invariants, landmines, architecture, placement contracts — anything that can change a plan/design/review decision | any |
| `IMPL.md` | no — read before editing source here | implementers | procedures, generated-code mechanics, rebuild sequences, hook/proxy mechanics, annotation recipes | any |
| `TESTING.md` | no — read before writing/fixing tests here | test authors | test harness, conventions, what's wired vs not, naming | module root |
| `DEBUG.md` | no — read when diagnosing runtime behavior | debuggers | run/attach, ports, logs, failure signatures | service root |

(`GLOSSARY.md` and `STAPLES.md` complete the set but have their own stewards/skills.)

**Litmus per fact:** "could this change a grill/plan/design/review decision?" → `CLAUDE.md`.
"Only matters while typing code / tests here?" → `IMPL.md` / `TESTING.md`. Unsure → `CLAUDE.md`
(under-loading an implementer is worse than over-loading a planner).

**Rules:**
- Closed nameset — never invent a new sidecar name; extending the set is a convention change, not a placement call.
- No empty placeholders — a sidecar exists only where content exists (an empty sidecar is an orphan).
- Every sidecar is announced by exactly one pointer line in the SAME directory's `CLAUDE.md`. Keep the tail `Read [<FILE>](<FILE>) first. Otherwise skip it.` verbatim (stable target for the read-before-edit hook); the leading trigger clause may match the sidecar's actual content:
  - `> **Editing code under this directory? Read [IMPL.md](IMPL.md) first. Otherwise skip it.**` (source dirs) — or `Building, testing, or running this service?` when the IMPL.md holds build/run commands (service root).
  - `> **Writing or fixing tests in this module? Read [TESTING.md](TESTING.md) first. Otherwise skip it.**`
  - `> **Diagnosing runtime behavior of this service? Read [DEBUG.md](DEBUG.md) first. Otherwise skip it.**`
- A sidecar inherits its directory scope — dedup vs ancestor sidecars exactly like CLAUDE.md (lowest common ancestor).
- HARVEST/AUDIT proposals must state the audience route alongside the placement rationale; AUDIT flags implementation-procedure content sitting in a `CLAUDE.md` as a move candidate (`CLAUDE.md → IMPL.md`).

## In-repo notes, not a shared layer
Cross-cutting principles live as **in-repo per-directory notes**, NOT an out-of-repo
`~/.claude/shared` `@import` layer. A note is written to the current checkout at the lowest common
ancestor of what it steers; branch/feature/module-specific guidance goes in that directory's local
`CLAUDE.md`. The write boundary is owned by SKILL.md's Safety section — don't restate it here.
