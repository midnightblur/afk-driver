# Per-subtask subagent prompt

Spawn one subagent per subtask with this prompt, placeholders filled — agent type per the sizing rule in `SKILL.md` (implementation tier travels as the `afk-implementor` type, which carries the pinned model). The subagent needs no skill-invocation support — it reads the skill files by path and follows them. Spawn mechanics + the subagent's return contract follow `DELEGATION.md` (plugin root).

`{WORKFLOW_SKILLS_DIR}` = `<main-checkout>/tools/payable/ai-agents/plugins/workflow/skills`; `{WORKFLOW_HOOKS_DIR}` = the sibling `…/workflow/hooks`. `<main-checkout>` is the first entry of `git worktree list` (fill absolute paths). **Always the main checkout — never the worktree's own copy**: the worktree carries the plugin as of the feature's branch point, so a worktree-resolved path would run stale plugin files (`GLOSSARY.md` "Main checkout").

```
You are executing one subtask of a local plan, non-interactively.

Read {WORKFLOW_SKILLS_DIR}/afk/execute/SKILL.md and follow it exactly for
subtask {NNNN-slug}, in DRIVEN mode (see that file's "Driven mode" section).

Context:
- worktree (cwd): {WORKTREE_PATH} — already on branch {BRANCH}
- plan dir: {PLAN_DIR}
- live app base URL for api/e2e/adversarial verification: {APP_BASE_URL}
  (the port is reserved and the baseline was booted before the run — YOU
  provision the instance AFTER implementing, so it serves your changes;
  re-run the same command to pick up later changes:
  APP_START_KEEP=1 APP_START_PORT={PORT} [APP_START_SKIP_UI=false for UI slices]
  bash {WORKFLOW_HOOKS_DIR}/app-start-gate.sh {LEAF_MODULE}
  The gate kills any prior subtask's instance on the port itself. If YOUR
  changes touched nothing the app loads — no file under a Maven module's
  src/, and no UI file when the instance serves the UI — add
  APP_START_REUSE=1 to reuse the running instance without a rebuild.
  When your slice finishes, LEAVE the instance running: it is per-run;
  the orchestrator stops it at run end.)
- commit + push on {BRANCH} and Draft-MR checklist updates are authorized
  for this run; merging, other branches, and Jira are not.

Non-negotiable: apply that file's "Driven mode" rules strictly — no waiting
for input, no waivers, adversarial gate included.

End your final message with the execute contract's report block — the
plain-terms + pointer lines, then the structured outcome line LAST:
In plain terms: <one jargon-free sentence>
Journal: plan/JOURNAL.md · Contract: plan/{NNNN-slug}.md
OUTCOME: <status> — <one-line summary> [producer: <PRODUCER-ID|none>]
```

The orchestrator parses only the trailing `OUTCOME:` line; anything else in the subagent's report (including its plain-terms sentence) is carried into the run report verbatim. The report-block grammar above is owned by `/afk:execute` (Step 13) — lockstep copy here because the orchestrator parses it; update both in the same commit.
