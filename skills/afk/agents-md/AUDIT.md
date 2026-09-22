# AUDIT mode

Manual. Scan project's `AGENTS.md` tree / `.claude/rules` / shared layer; report + propose fixes (grouped, cherry-pickable).

## Discovery (safety-critical)
- Root = `git rev-parse --show-toplevel`, or cwd if not a repo.
- Find within root only: `AGENTS.md`, `.claude/AGENTS.md`, the root `CLAUDE.md` bridge and any
  unmigrated `CLAUDE.md` / `.claude/CLAUDE.md`, `CLAUDE.local.md`, `.claude/rules/**/*.md`,
  plus files referenced by `@import` (the root bridge's `@AGENTS.md`).
- Skip `node_modules`, `target`, `build`, `dist`, `.git`, vendor dirs.
- NEVER recurse from system roots (`C:\`, `C:\Windows`, `/`, `/c`). CrowdStrike guard.
  Use scoped tools (Glob under root, or Grep with an explicit path).

## Checks (run all)
1. **Duplication** — same guidance in 2+ files in a chain → resolve per [PLACEMENT.md](PLACEMENT.md)
   "Dedup direction" (lift to lowest common ancestor, or delete/push-down the child copy).
2. **Contradiction** — parent vs child/rule conflict (parent: X; child: not-X) → flag + propose resolution.
3. **Staleness** — verify referenced paths/commands/symbols still exist in code; flag dead hints.
   Flag volatile specifics (pinned versions, counts, dates, "current" dep lists) →
   generalize to the durable rule (`LANGUAGE.md` plugin root, "Stay generic").
4. **Mechanical** — run `scripts/mechanical_check.py <root>`. It reports (never fails; exit 0), one
   tagged line per finding; the steward acts per tag:
   - `[size > 200]` / `[bytes > 32768]` / `[chain > 32768]` — split the file, or rebalance the
     root→directory chain under the 32 KiB per-chain budget (`providers/HARNESS-MATRIX.md`).
   - `[import]` (in an `AGENTS.md`) — inline the target or make it a nested `AGENTS.md` (D2).
   - `[bridge]` — rewrite the root `CLAUDE.md` to exactly `@AGENTS.md`.
   - `[migrate]` — advisory; propose `git mv CLAUDE.md AGENTS.md` for each non-bridge `CLAUDE.md`.
   - `[override]` — propose removal (banned, D3).
   - `[tracked-local]` — untrack the file and add it to `.gitignore`.
   - `[rule-paths]` — add the `paths:` frontmatter key.
   - `[broken-import]` — fix or drop the `@import` in the `CLAUDE.md`.

   Orphan shared files + dead file-refs = agent judgment (unreliable to script across repos).
5. **Inclusion-bar sweep** — re-test each existing line vs the 4 gates; flag now-obvious / one-off /
   non-steering lines as removal candidates.

## Surgical vs --deep
- Default: flag exact dups + obvious mis-placements; propose minimal moves.
- `--deep`: propose ideal end-state tree (all lifts/splits/restructure). Large diff — explicit only.

## Output
Quality summary (files, sizes, issue counts) → grouped proposal per file
(diff · why · placement rationale · `src → dest` moves · blast-radius). Cherry-pickable.
