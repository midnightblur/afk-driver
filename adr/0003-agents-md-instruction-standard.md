# ADR-0003 — `AGENTS.md` is the instruction-file standard, with a root `CLAUDE.md` bridge

> Status: Accepted
> Date: 2026-09-22

## Context

A repository's per-directory steering has lived in `CLAUDE.md` files. Harnesses have since converged on `AGENTS.md` as the cross-tool instruction file, but they disagree on when they read it, how they walk the tree, whether nested files load lazily, and what size a chain may reach — the per-harness facts are catalogued in `providers/HARNESS-MATRIX.md`. One harness reads `AGENTS.md` only when no `CLAUDE.md` shadows it, and only from the session after an upgrade. A repository that keeps both files, or that names steering inconsistently across directories, gets a different instruction set per tool and per session — silently.

The plugin needs one reusable answer any consuming repository can adopt, so the steward (`skills/afk/agents-md`) teaches one tree shape rather than a per-harness patchwork.

## Decision

`AGENTS.md` is the source of per-directory steering in every directory. Exactly one `CLAUDE.md` remains in a repository: the root file, holding only `@AGENTS.md`. That bridge is the floor for any session that cannot read `AGENTS.md` natively, including the first session after a harness upgrade.

- No `@path` imports inside any `AGENTS.md`; the root bridge's `@AGENTS.md` is the one allowed import. Shared content becomes a nested `AGENTS.md` at its natural directory, or is inlined where it passes the inclusion bar.
- `AGENTS.override.md` is banned in a repository (gitignored `**/AGENTS.override.md`).
- Per-developer and plugin steering live in the user-global steering files, never committed. Repo-scoped personal preference goes in `CLAUDE.local.md`, gitignored `**/CLAUDE.local.md`.
- `.claude/rules/*.md` keep their full bodies; one line in each service `AGENTS.md` names the rules directory for tools without the plugin.

Nested steering reaching a harness that does not load it natively is a separate capability (`nested_steering`), degraded per `CAPABILITIES.md`; this ADR fixes only the tree shape.

## Alternatives Considered

| Alternative | Pros | Cons | Reason rejected |
|-------------|------|------|-----------------|
| Repo-local `AGENTS.local.md` for shared steering | one filename family | undocumented or ignored on most harnesses (`providers/HARNESS-MATRIX.md`); not a portable source | never reliably read |
| Generated `AGENTS.override.md` committed per directory | overrides load cleanly where supported | replaces rather than layers, ignored elsewhere, and a committed override is a generated activation surface the distribution law forbids | wrong layering, not portable |
| A pointer index (one file listing every steering file) | one place to read | an extra always-loaded file that duplicates the tree and goes stale; the harness still must open each target | adds context load, drifts |
| Zero-`CLAUDE.md` tree (drop the bridge entirely) | one filename, no duplication | a session that reads only `CLAUDE.md`, and the first session after an upgrade, then gets no steering at all | loses the floor |
| A settings-file detector to decide whether to inject nested steering | avoids double-loading when native reading is on | the setting can arrive from managed settings, an override flag, or a moved config directory, so a detector guesses wrong and double-loads | the injector keys on capability, not a guessed setting |

## Consequences

- **Positive** — every supported harness, and every session, reads the same steering from `AGENTS.md`, with the bridge as a guaranteed floor. The tree shape is machine-checkable (one `CLAUDE.md`, no `AGENTS.md` imports, no tracked override/local files).
- **Positive** — the standard is harness-agnostic: adding a harness updates `providers/HARNESS-MATRIX.md`, not the tree shape.
- **Negative** — the root keeps two instruction files (`AGENTS.md` plus its `CLAUDE.md` bridge), so a reader must know the bridge is not steering.
- **Negative** — migrating a repository is a bulk rename with by-hand merges wherever a directory held both files, and consuming repositories migrate on their own schedule; until then, tree walkers must read both `AGENTS.md` and `CLAUDE.md`.
- **Follow-ups** — the nested-steering injector and the mechanical tree check are their own work; the first-session-after-upgrade limitation is re-checked per harness release.
