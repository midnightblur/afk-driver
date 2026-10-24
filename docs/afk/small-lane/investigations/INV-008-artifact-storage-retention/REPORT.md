# INV-008 — artifact storage and retention

feat-small-lane@d346cfb · partial · boundaries 0/14 · unverified 3 (load-bearing 2) · ledger: COVERAGE.json

## Answer

1. **Spec folder.** Every notes kind renders `repo-files.spec-dir` from a JSON payload; the default is `docs/afk/{workId}` (`scripts/afk-config.py:138`, `.afk/config.yaml:22`, `adapters/notes/common.sh:116-127`). The root is the git top-level for repo-files (`repo-files/notes.sh:16`) or `obsidian.vault` (`obsidian/notes.sh:13`); notion delegates to repo-files (`notion/NOTES.md:18,25`). `resolve` creates nothing. `workId` falls back to `ticket` and back (`common.sh:64-65`), so a slug alone fills both. An empty payload renders `docs/afk/`. The provisional-slug rename is prose only (`to-prd/SKILL.md:37`); no verb or script renames a folder.
2. **/afk:bug evidence.** `<main checkout>/.claude/bugs/{ticket}/`: starts under a slug, renamed to the key on publish, moved to `done/` at S9, deleted only by `purge` (`bug/LEDGER-FORMAT.md:7,24-39`). "Gitignored" is a doc claim; no plugin code writes the ignore rule; this repo ignores it via `.gitignore:59`.
3. **/afk:gc.** Human-run only (no hook or workflow entry). `gc-check.sh` requires plan complete (`:108`), branch merged (`:134-136`), clean spec folder (`:146`), `AFK_DRIVEN` unset (`:151`), session off the feature branch (`:156`). Deletes `plan/`, `GRILL-LOG.md`, `TICKET.md`, `*.adf.json`; keeps the rest (`gc/SKILL.md:53-63`). Removes the worktree without `--force`, `branch -d`, one commit, no push (`:76-109`).
4. **Committed vs untracked.** Committed: slice code by /afk:execute (`execute/SKILL.md:61`); `plan/` by a human (`to-subtasks/SKILL.md:75`); `plan/SHIP-SNAPSHOT.html` by preflight (`preflight/SKILL.md:177-178`); `plan/digests/` (`DIGEST-FORMAT.md:13`). Never committed: `.claude/bugs/`, lessons ledger (`lessons/LEDGER-FORMAT.md:22`), `plan/mission-control/` (`mission-control/SKILL.md:70-71`), `.afk/config.local.yaml` (`CONFIG.md:32-33`). PRD/SDD/ADRs/investigations have no commit step in any skill (inferred: a human commits them; gc's clean-tree guard assumes it).

## Findings

- `ADAPTERS.md:131` documents positional `resolve <workId>`; the code parses JSON (`common.sh:109`).
- `mission-control/SKILL.md:26` names `spec/{slug}/`, which no template produces.
- `gc/SKILL.md:29,44` say `origin/master`; the script reads `git.base-branch` (`gc-check.sh:16`).
- Plugin defect: `merge_fragments.py:108-135` treats the seed's untriaged `unverified` nodes as conflicts; merged against a staging copy without them.

## Unverified

- Whether consuming repos ignore `.claude/bugs/`, `.claude/lessons/`, `plan/mission-control/` — load-bearing.
- Whether /afk:execute commits its final PLAN.md status edit (`plan-status.sh … done` runs after the last commit, `execute/SKILL.md:106`) — load-bearing.
- B3, B5, B6, B7, B10 have no enumeration method; import-alias and wire name forms undeclared.

## Frontier

B14: consuming repos' `.gitignore` files; live forge state.

Written by the orchestrator from the investigation's reply; the investigation's own REPORT.md write was refused.
