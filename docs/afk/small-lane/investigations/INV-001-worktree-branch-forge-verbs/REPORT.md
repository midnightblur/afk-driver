midnightblur/afk-driver@d346cfb5b395 · partial · boundaries 0/14 · unverified 6 (load-bearing 0) · ledger: docs/afk/small-lane/investigations/INV-001-worktree-branch-forge-verbs/COVERAGE.json

## Answer

| Question | Mechanism today | Sites |
|---|---|---|
| Worktree off base | `scripts/create-worktree`: `--branch/--dir` (new branch needs `--base`) or `--name` (branch from template; base = session HEAD, not `git.base-branch`) | scripts/create-worktree:16, :27, :389-398, :420-429 |
| Harness tool | claude `EnterWorktree` fires `WorktreeCreate` → `hooks/worktree-create.sh` → `create-worktree --name`; codex: guard + detached helper | hooks/hooks.json:80-85; hooks/worktree-create.sh:22-25; PROVIDERS.md:75-76 |
| Guard | agent writes only from an owned linked worktree on an unprotected branch; creating a new branch ref passes | SAFETY.md:25-38; hooks/git-backstop.py:9-11; scripts/create-worktree:75 |
| Branch name, no ticket | `--name` fills every non-`{user}` placeholder with the name; no placeholder → `worktree-<name>`; must match `git.branch-pattern` | scripts/create-worktree:203-218, :233-234; CONFIG.md:158-161 |
| Branch-name gate | agent-only `reference-transaction` hook; refuses new local branch off-pattern; skips remote-tracked | hooks/branch-name-gate.sh:38, :95-115, :76-77 |
| Open change | `change-create-draft` only (draft always; optional reviewer, assignee); no ready-create verb | ADAPTERS.md:63-66; adapters/forge/github/forge.sh:374-388; adapters/forge/gitlab/forge.sh:391-406 |
| Flip ready | `change-ready`; called by `/afk:preflight` PF-7 and the `/afk:bug` fixer | adapters/forge/github/forge.sh:390-397; skills/afk/preflight/SKILL.md:215 |
| Add reviewer | `change-reviewers`: github `--add-reviewer`, gitlab `glab mr update --reviewer`; only `/afk:bug` fixer calls it | adapters/forge/github/forge.sh:402; adapters/forge/gitlab/forge.sh:420; skills/afk/bug/FIXER-PROMPT.md:33 |
| Comment | `change-comment` (plain or inline); called by `forge_ledger.py` | ADAPTERS.md:80-86; skills/afk/review/scripts/forge_ledger.py:1018 |
| Change dependency | none: no verb, field or skill names one | counter-search q-c8a75df4 (0 lines), q-0c1b7b9f |
| Reviewer config | per-developer `developer.mrReviewer` (never committed; `none` = no reviewer) | CONFIG.md:136; skills/afk/bug/CONFIG.md:38 |
| Same commit, two branches | none: cherry-pick appears only as a guard-classified mutation | hooks/lib/shell_mutations.py:23; VERIFICATION.md:21 |

`/afk:execute`: opens Draft if absent (assignee = `mrAssignee`), updates checklist via `change-update-body`, stops before Ready (skills/afk/execute/SKILL.md:16-17, :63).

Inferences: glab `--reviewer` may replace, not add, reviewers (unchecked against glab docs). CONFIG.md:136 says `mrAssignee` goes on every opened change; forge_ledger.py:1901 opens a Draft with no assignee.

## Frontier

- B14: another repository, deployment manifest, or live consumer

## Unverified

- B3, B5, B6, B7, B10: no enumeration method (no `investigation:` block in `.afk/config.yaml`).
- B1 partial: name forms `import-alias` and `wire` not enumerated; B2, B4, B8, B9, B11, B12, B13 inherit that gap.
- Counter-search ran inline, not blind: the subagent limit refused tracer spawns.
