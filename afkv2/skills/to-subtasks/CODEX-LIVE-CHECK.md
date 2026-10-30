# Codex live check of to-subtasks

The owner runs this check (plan decision D-S-8). It needs afkv2 enabled in the global Codex config, the page engine merged, and a feature branch with `PRD.md` and `SDD.md` in its spec folder.

1. In that repository, open a Codex session on the feature branch and run `/afkv2:to-subtasks <ticket key>`.
2. Expected: the plan is committed on `<feature branch>-run`, the agent shows the division page, and it ends its turn. It runs no `page_round.py wait`.
3. Mark the division card with `Sign`. Send the round. Send no chat message.
4. Expected: the agent starts a new turn by itself and runs `page_round.py ingest`, then `plan_files.py approve`.
5. Expected: `PLAN.md` on the run branch has the line `> Division: approved <today>`, in a commit of the run branch. `git log <feature branch>` holds no file of `plan/`.

A failure at step 4 means the fallback in the skill's step 8, one chat message after Send. Report it to the owner of the plan.
