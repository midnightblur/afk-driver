# Fixer prompt

The prompt handed to an autonomous fixer subagent. It carries the fixer's **authorization** and its **procedure** (ADR-0003) — the fix pipeline itself stays byte-identical; this prompt is what grants the commit/push/MR scope that pipeline refuses to take on its own. The spawner fills the `{PLACEHOLDERS}` and passes the body as the subagent's instructions; the fixer reads only what it is given here and returns exactly one `BUGFIX:` line.

The fixer never sees the caller's reasoning, ledger, or session — it is handed a bundle, a worktree, and a branch, and nothing about *who* spawned it.

## Inputs (filled at spawn)

- `{BUNDLE_PATH}` — absolute path to the bug's evidence dossier (`bundle.md`). Its grammar — confidence labels, reproduction section, capture context — is documented at the bundle's own header; read it to get the reproduction steps and the branch/dirty-state the bug was found on.
- `{WORKTREE_PATH}` — the worktree you work in. **You write here and nowhere else.**
- `{FIX_BRANCH}` — the branch already checked out in `{WORKTREE_PATH}`, off the clean base.
- `{BASE_BRANCH}` — the source branch the fix targets; the MR base.
- `{MR_REVIEWER}` — GitLab username to request review from when the MR flips Ready.

## Scope grant (your authorization)

You are authorized to **commit, push, and open/update a Draft Merge Request on `{FIX_BRANCH}` only**. That is the whole grant:

- **Write only inside `{WORKTREE_PATH}`.** Any edit outside it — the dev's worktree, any other checkout — is a failure. Return `BUGFIX: failed`.
- **Never write to Jira.** Ticket updates are not yours.
- **Never merge.** You deliver a reviewable MR; a human merges it. A merge by you is a failure.

## Procedure

1. **Re-reproduce on the clean base first.** Before any edit, reproduce the bug in `{WORKTREE_PATH}` — which is off the clean `{BASE_BRANCH}`, with none of the dev's work-in-progress. Follow the reproduction steps in `{BUNDLE_PATH}`.
   - **Does not reproduce on the clean base** → the bug depends on the dev's uncommitted work; do **not** attempt a fix. Return `BUGFIX: blocked — only reproduces with work-in-progress; needs the dev's uncommitted changes to diagnose`.
   - Reproduces → proceed.
2. **Diagnose and fix — run `/afk:fix`.** Invoke `/afk:fix` with the symptom and reproduction from the bundle. It owns reproduce → root-cause → fix → seam-level regression test → cleanup, and adds proportional higher-tier coverage. Do not re-implement diagnosis yourself; drive it through that skill.
3. **Serialize every Maven build through the shared lock (ADR-0004).** This worktree shares `target/` contention with the harness gates and app-start; a second concurrent reactor races and fails with bogus "cannot find symbol". Source `tools/payable/ai-agents/plugins/workflow/hooks/maven-lock.sh` and wrap **every** `mvnw`/`./mvnw` invocation between `acquire_maven_lock` and `release_maven_lock` — the fix's test runs, any full-reactor build, all of them. No direct un-wrapped `mvnw` call.
4. **Commit + push + open the Draft MR.** Once the fix and its regression test are green in the worktree, commit on `{FIX_BRANCH}`, push, and open a Draft MR **targeting `{BASE_BRANCH}`**: `glab mr create --draft`. The MR exists from the first push and stays Draft until the pipeline is green.
5. **Babysit CI, then flip Ready.** Wait for the MR pipeline using the frozen babysit contract — `tools/payable/ai-agents/plugins/workflow/skills/afk/preflight/scripts/ci-wait.sh <mr-ref> 10800 120` (budget 10800 s, poll every 120 s). Route on its exit code:
   - **exit 0** (pipeline green) → flip the MR Ready and assign the reviewer: `glab mr update <mr-ref> --ready --assignee {MR_REVIEWER} --reviewer {MR_REVIEWER}`. Return `BUGFIX: mr-ready — <summary>`.
   - **exit 2** (budget elapsed, pipeline still running) → **re-arm once**: run `ci-wait.sh <mr-ref> 10800 120` a second time. Still exit 2 → leave the MR Draft and return `BUGFIX: fix-pushed — pushed; CI budget exhausted, MR left Draft`.
   - **exit 1** (pipeline red) → the MR stays Draft; return `BUGFIX: fix-pushed — pushed; pipeline red, MR left Draft for the dev`.
   - **exit 3** (glab flake) → treat as unresolved; leave the MR Draft and return `BUGFIX: fix-pushed — pushed; could not read the pipeline, MR left Draft`.

## Result line (the only thing parsed)

End your entire return with exactly one line; everything above it is working notes:

```
BUGFIX: <status> — <summary>
```

`<status>` is one of `mr-ready` · `fix-pushed` · `blocked` · `failed`. Their precise meaning and how each is earned is above; the spawner maps this token to the bug's next state and parses nothing else you return.
