# Per-subtask subagent prompt

Spawn one general-purpose subagent per subtask with this prompt, placeholders filled. The subagent does not need skill-invocation support — it reads the skill files by path and follows them. Spawn mechanics and the subagent's return contract follow `DELEGATION.md` (plugin root).

```
You are executing one subtask of a local plan, non-interactively.

Read {WORKFLOW_SKILLS_DIR}/afk/execute/SKILL.md and follow it exactly for
subtask {NNNN-slug}, in DRIVEN mode (see that file's "Driven mode" section).

Context:
- worktree (cwd): {WORKTREE_PATH} — already on branch {BRANCH}
- plan dir: {PLAN_DIR}
- live app for api/e2e/adversarial verification: {APP_BASE_URL}
  (already provisioned with your changes after you implement; if you need a
  reboot to pick up later changes:
  APP_START_KEEP=1 APP_START_PORT={PORT} [APP_START_SKIP_UI=false for UI slices]
  bash .claude/hooks/app-start-gate.sh {LEAF_MODULE})
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

The orchestrator parses only the trailing `OUTCOME:` line; anything else in the subagent's report (including its plain-terms sentence) is carried into the run report verbatim.
