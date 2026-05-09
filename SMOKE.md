# AFK driver — end-to-end smoke procedure

Manual one-shot test the user runs to prove the loop closes. The runner
spawns Claude Code sessions, opens a real Draft MR, and transitions real Jira
tickets, so the smoke is not automated; it's a checklist.

## Prerequisites

- `glab`, `mvn`, `node`, `claude`, `git`, `python` (≥3.11) all on PATH.
- `GITLAB_TOKEN` env set (`glab auth status` green).
- Jira API credentials in env: `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`.
- The `afk` Claude Code plugin installed and enabled. From inside Claude
  Code: `/plugin marketplace add <path-to-this-repo>` →
  `/plugin install afk@afk-marketplace` → confirm `/afk:execute`,
  `/afk:to-prd`, `/afk:to-subtasks` resolve. (Persisting via
  `enabledPlugins` in `~/.claude/settings.json` is recommended; see
  `README.md` § Skills.)
- The driver package importable: `pip install -e .` from this repo's
  root.

## Step 1 — fixture Enhancement + SubTask

In Jira, project P2P:

1. Create an Enhancement, summary `[AFK smoke] noop SubTask drain`.
   - `Target Branch` = `MASTER`.
   - `fixVersions` = whatever your active core sprint version is.
   - `components` = `payable` (or any).
   - Status: leave at `Creating`. Transition to `Dev-Pending` only when ready.

2. Under it, create one SubTask with:
   - Summary `[AFK smoke] echo hello`.
   - Label `afk-agents`.
   - Description (the structured contract — paste literally):

   ~~~markdown
   ## Goal
   Echo "hello" into a fixture file inside `tools/payable/afk-smoke/` so the driver
   can prove the loop closes without any real code change risk.

   ## Scope
   - tools/payable/afk-smoke/**

   ## Acceptance
   - [ ] `tools/payable/afk-smoke/output.txt` exists and contains the literal string `hello`
   - [ ] Tests pass via `python -c "assert open('tools/payable/afk-smoke/output.txt').read().strip() == 'hello'"`

   ## Test command
   ```
   python -c "assert open('tools/payable/afk-smoke/output.txt').read().strip() == 'hello'"
   ```

   ## Parent PRD
   `tools/payable/afk/PRD.md`

   ## Blocked by
   (none)

   ## Implementation Notes (auto-maintained)
   <!-- AFK appends one bullet per completed SubTask -->
   ~~~

3. Transition both Enhancement and SubTask to `Dev-Pending`.

## Step 2 — drive a one-shot pass

From the worktree root (not from this AFK bootstrap branch — the smoke wants
the driver to operate on a fresh branch off `master`):

```
python -m afk_driver --label afk-agents --project P2P --digest-out auto
```

This:
- runs preflight (must be green),
- searches Jira for `afk-agents`-labelled SubTasks in `Dev-Pending`,
- creates `~/.afk-driver/worktrees/{ENH-ID}/`,
- opens a Draft MR `[{ENH-ID}] [AFK smoke] noop SubTask drain` against `master`,
- transitions the parent Enhancement: `Dev-Pending → Dev-Designing → Dev-Developing`,
- spawns a fresh Claude Code session executing `/afk:execute {SUBTASK-KEY}`,
- the session writes `output.txt`, runs the Test command (green-bar),
- transitions the SubTask `Dev-Pending → Dev-Designing → Dev-Developing → Dev-CR/Merge`,
- updates the parent's `## Implementation Notes (auto-maintained)`,
- rebases the worktree against `master` (clean — nothing else moved),
- transitions the Enhancement to `Dev-CR/Merge`,
- writes the digest to `~/.afk-driver/digests/{YYYY-MM-DD}.md`.

## Step 3 — verify

- [ ] Jira: SubTask is in `Dev-CR/Merge`. Gate fields populated (MR link, SRED
  Eligibility = "SRED not eligible / Straightforward Implementation",
  Time = "Low: 10 and < 80 hours", Rationale present).
- [ ] Jira: Enhancement is in `Dev-CR/Merge`.
- [ ] Jira: Enhancement description has a new bullet under
  `## Implementation Notes (auto-maintained)` referencing the SubTask key.
- [ ] GitLab: Draft MR is open with the SubTasks checklist showing one ticked
  item; description preserves any human-edited content outside the
  `<!-- afk:subtasks:start -->` / `<!-- afk:subtasks:end -->` block.
- [ ] Local: `~/.afk-driver/digests/{today}.md` exists and lists this run.
- [ ] The MR commit is `[{SUBTASK-KEY}] ...`.

## Step 4 — capture

Attach a transcript or short screen recording to the MR description on
P2P-1226 so the close-out is auditable.

## Failure modes to watch for

- **Preflight hard-fail**: missing tool / missing `GITLAB_TOKEN` / PRD path
  wrong. Fix env, rerun.
- **Parent not Dev-Pending**: the runner skips the Enhancement. Transition
  parent to `Dev-Pending` before rerunning.
- **Rebase conflict**: shouldn't happen for a no-op fixture. If it does, the
  runner posts a comment on the Enhancement and exits clean — resolve the
  conflict manually.
- **Claude session timeout**: the wall-clock cap is 1 hour by default. The
  run is recorded as `timeout` in the digest; the SubTask returns to
  `Dev-Pending`.
