nakisainc/core/core-services@82c3db898ad82c86186989c1166547f05e060fb7 · partial · boundaries 11/14 · unverified 0 (load-bearing 0) · ledger: 11700-payable/specs/2026r2/P2P-2067/investigations/INV-008-run-artifact-retention/COVERAGE.json

## Verdict

AFK has two separate cleanup systems: session cleanup owns plugin-created worktrees, while `/afk:gc` owns a delivered feature's repository artifacts and optional worktree retirement. The lifecycle is understood, but the investigation is partial because two generic name forms were not enumerable and the Windows `gc-check` smoke suite failed its forge-fallback case.

## Before a forge change

`/afk:to-prd` writes `PRD.md` and requirement ADRs into the repository spec folder; publishing to a tracker is separate. A provisional slug is allowed before a ticket key exists. [skills/afk/to-prd/SKILL.md:10] [skills/afk/to-prd/SKILL.md:34] [skills/afk/to-prd/SKILL.md:37]

`/afk:to-subtasks` writes `plan/` beside the PRD, including `PLAN.md` and an append-only `JOURNAL.md`. It does not commit these files. [skills/afk/to-subtasks/SKILL.md:10] [skills/afk/to-subtasks/SKILL.md:79] [skills/afk/to-subtasks/SKILL.md:127]

`/afk:execute` keeps contracts, design, and progress under `plan/`; it then creates or reuses a Draft forge change and appends execution events to the journal. [skills/afk/execute/SKILL.md:12] [skills/afk/execute/SKILL.md:17] [skills/afk/execute/SKILL.md:37]

## Worktrees and local state

Plugin-created worktrees have owner records under the repository's git-common directory. SessionStart prunes dead-owner records; SessionEnd launches a detached waiter that removes only a clean, fully pushed, plugin-owned worktree. Unknown, dirty, unpushed, active, or move-in-flight worktrees are kept. [scripts/worktree_owner.py:224] [hooks/hooks.codex.json:34] [hooks/hooks.codex.json:133] [scripts/remove-worktree.py:321] [scripts/remove-worktree.py:425]

The keep decision is also local state: `<git-common>/afk-session/kept.json`. It is independent of feature delivery and `/afk:gc`. [scripts/remove-worktree.py:213]

## After delivery

`/afk:gc` is post-merge only. Its guard requires a complete feature header, merge proof, a clean spec folder, an interactive session, and that the current shell is not standing in the target worktree. [skills/afk/gc/scripts/gc-check.sh:101] [skills/afk/gc/scripts/gc-check.sh:151] [skills/afk/gc/SKILL.md:137]

The human approves spec compaction and worktree retirement separately. A dirty or unmerged worktree can be kept while spec compaction proceeds. [skills/afk/gc/SKILL.md:66] [skills/afk/gc/SKILL.md:95]

Compaction deletes only the known list: the whole `plan/` directory, `GRILL-LOG.md`, `TICKET.md`, and `*.adf.json`. It keeps evergreen documents and every unrecognized file. [skills/afk/gc/SKILL.md:49] [skills/afk/gc/SKILL.md:53] [skills/afk/gc/SKILL.md:60]

It updates `INDEX.md` with the archive ref and commits locally, but never pushes, deletes a remote branch, or updates the tracker. Deleted material remains recoverable through `git show` and available to retrospectives. [skills/afk/gc/SKILL.md:102] [skills/afk/gc/SKILL.md:109] [skills/afk/gc/SKILL.md:139]

## Design consequence

Investigations, `LAVISH-TIPS.md`, and Lavish JSON or HTML are outside the known delete list, so today's fail-safe rule retains them after delivery. [skills/afk/gc/SKILL.md:49] [LAVISH-KIT.md:30] [LAVISH.md:253]

Inference: a new glossary run artifact must either live under `plan/` or gain an explicit retention and cleanup rule. Otherwise `/afk:gc` will preserve it indefinitely. [skills/afk/gc/SKILL.md:49] [skills/afk/gc/SKILL.md:53]

## Verification

Worktree cleanup tests passed: `70 passed`. The `gc-check` smoke suite reported `25 passed, 3 failed`; all three failures were in the forge-fallback path, so that guard behavior remains unverified on this Windows snapshot.
