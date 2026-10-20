# INV-013 — CI wait and the ready flip

feat-small-lane@d346cfb · partial · ledger: COVERAGE.json (validator exit 0, 558 nodes, 38 claims)

## Answer

No helper waits for CI and then flips the change to ready. Two places chain the verbs, both in skill prose: preflight PF-6/PF-7 and the `/afk:bug` fixer. Every call goes through `afk_adapter forge <verb> <json>` (`hooks/lib/adapter.sh:73-113`).

| Verb | Sites | Answer |
|---|---|---|
| `ci-status` | github `forge.sh:357-362`; gitlab `:365-375` | `{status,url}`, one read |
| `ci-wait` | github `:681-721`; gitlab `:717-763` | payload `id`, `budget` (5400), `interval` (180). Exit 0 success; 1 failed or canceled; 2 running, budget spent; 3 unreadable (3 empty reads). Prints JSON on every exit |
| none | `none/forge.sh:9-11` | `unsupported`, exit 3 |

- **GitHub status.** Checks fold into one word (`:243-256`): failed, then canceled, then running, then success.
- **No CI configured.** It answers status `""`, so `ci-wait` exits 3 `unreadable` (`:247-248`, `:700-706`). It is not a separate state.
- **Ambiguous exit codes.** A dispatch failure also exits 2 (`adapter.sh:41-49`), so route on the stdout JSON.
- **Command timeout.** `AFK_FORGE_TIMEOUT` caps each gh/glab call at 60 s.
- **Preflight** (`preflight/SKILL.md:192-235`):
  - `ci-wait` runs as a tracked background task. The task's exit delivers the wake.
  - Exit 0 calls `change-ready`.
  - Exit 1: a mechanical red gets at most 2 fixes, then the run relaunches. A red seen only in CI parks `ci_test_red`.
  - Exit 2 parks `budget_exhausted`, and a resume reads `ci-status` first.
  - Exit 3 parks `forge_flake`.
- **Callers of `change-ready`.**
  - Preflight `:215`.
  - The bug fixer, `FIXER-PROMPT.md:33`. It calls the verb only when `ci-wait` exits 0 and a reviewer is set. It then calls `change-reviewers`, its only caller.
- **Bug fixer.**
  - Its `ci-wait` budget is 10800 with an interval of 120, and it re-arms once on exit 2.
  - Any other exit leaves the change Draft (`:32-36`).
  - It reads `mrReviewer` and `mrAssignee` (`bug/SKILL.md:68`; documented at `CONFIG.md:136` and `bug/CONFIG.md:38,41,70`).
  - `mrReviewer: none` comes back as the literal string; only the skill prose maps it to empty.
- **Error handling.** `change-ready` and `change-reviewers` exit 0 on error and print `{"error":true}` (github `:390-408`).
- **Reuse.** `forge_ledger.py` `Adapter.call` raises on any non-zero exit (`:740, 764-771`), so it cannot route `ci-wait`.

## Findings

- `GLOSSARY.md:334` describes a "flaky retry" in the CI wait; PF-7 has no retry.
- `preflight/SKILL.md:203-205` points the exit table at CONTRACT.md; the table is in `ADAPTERS.md:112-115`.
- `github/CONTRACT.md:71` claims a fork check that the code does not make.
- The `MANIFEST.md:413-430` callers list omits the fixer.
- Inferred: GitLab `skipped` or `manual` polls until the budget runs out.
- Inferred: the fixer's 10800 s foreground wait exceeds the harness's foreground limit.

## Unverified

- B3, B5, B6, B7, B10 had no method. B1 alias forms are not enumerated.
- Not checked live: `change-ready` on a change that is already ready, and whether `glab --reviewer` adds or replaces reviewers (load-bearing).
- No tests cover `ci-status`, `change-ready`, `change-reviewers`, the GitHub status fold, or the no-CI case.

## Frontier

B14: live gh/glab behaviour and other repositories.

Written by the orchestrator from the investigation's reply; the investigation's own REPORT.md write was refused.
