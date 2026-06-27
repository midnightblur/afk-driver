## Relationship to the rest of the chain

- **vs. the per-subtask `api` / `e2e/browser` tiers** (`/afk:execute` Step 8):
  those prove one slice — its endpoint contract or its UI — in a dev worktree as
  the slice lands. This proves the **integrated** feature against a running app,
  after everything has landed. Both exist on purpose; neither replaces the other.
- **vs. `/afk:grill-verification` + `/afk:to-verification-plan` + the terminal
  `NNNN-smoke-e2e` / `NNNN-smoke-api` subtasks**: `grill-verification` *designs*
  the scenarios and `to-verification-plan` *writes* `VERIFICATION-PLAN.md`; the
  build subtasks *implement* them — UI journeys as
  `Scenario`s in the `11700-payable/verification/ui-e2e` Gherkin catalog, API
  scenarios as `node:test` `*.test.mjs` in `11700-payable/verification/api`
  (reuse-first), resolve them offline (`cucumber-js --dry-run` / `node --check`,
  their `static` tiers), and run them locally (`npm run smoke` / `node --test`,
  their `e2e` / `api` tiers) to prove they pass in dev. This skill *runs the
  already-built suites* against the real target as the gate. The local redundancy
  is intentional — "specs pass in dev" ≠ "feature works in the env with all
  subtasks integrated." If the gate hits an undefined/ambiguous step or an
  import/parse error, the build subtask skipped its dry-run — fix it there, not
  here.
- **Reuse**: the built specs are permanent residents of
  `11700-payable/verification` (`ui-e2e` + `api`). CI pipelines and scheduled jobs
  run the same suite commands directly; a human can run this skill (or the raw
  commands) any time to re-check system sanity. The gate is one consumer of the
  suites, not their owner.
