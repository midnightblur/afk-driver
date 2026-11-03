# Dogfood run

The run in progress for subtask `0016-dogfood-run`. One row for each step, then every failure with its owner.

## Steps

| Step | Provider | Tag | Result | Evidence |
|---|---|---|---|---|
| Install from the tag | Codex | `afkv2-2.0.0-beta.3` | pass | `codex plugin list`: afkv2 2.0.0-beta.3 and afk 1.16.1, both enabled |
| Live check 1, hook text in context | Codex 0.166 | beta.1, beta.2 | fail | hook exited 1; no marker; no fired record |
| Live check 1, hook text in context | Codex 0.166 | beta.3 | pass | session and subagent quote `afkv2-core-behaviors end 24a66b9e53ae`; new `fired-codex.txt` at 12:58 |
| Live check 2, after a compaction | Codex 0.166 | beta.3 | pass | same line after `/compact`; new session-start record at 13:00:16 |
| Setup, takeover | Codex | beta.3 | pass | v1 disabled, afkv2 enabled, backup of `config.toml`, lavish 0.1.80; a new session holds the marker, and the only `afk:behaviors` text is a comment in the interim block |
| Backup folder permissions (setup check 5) | Codex | beta.4 | pass, one part not checked | `backup` has one entry, the owner's account with `(OI)(CI)(F)`, no `(I)`. Per-file permissions not checked: switch-back had restored the values file. Check 5 step 5 no longer tests the sandbox account, because the rules run setup outside the sandbox |
| Switch-back, setup again (setup check 4) | Codex | beta.4 | pass | rules file removed, v1 on, afkv2 off, lavish 0.1.63, no conflict; after F-14, setup again: v1 off, afkv2 on, lavish 0.1.80, 32 scripts in the rules file |
| Live check 3, sandboxed | Codex | beta.3 | fail | F-6 |
| Live check 3, page answer after 10 minutes | Codex | beta.3, one approval, run outside the sandbox | not proved | the hook waited from 14:12:32; Codex restarted at 14:23:13 in a new pane and the turn was interrupted; on the next turn the hook handed the answer back with no chat message about it; see F-7, F-9 |
| Setup again, rules file | Codex | beta.4 | pass | v1 disabled, afkv2 enabled; `~/.codex/rules/afkv2.rules` holds 64 rules; see F-13 |
| Live check 3, page answer after 10 minutes | Codex | beta.4 | pass | `show` returned at 19:36:50 with no approval request in the session log; the answer came back as the next prompt at 20:08:41 (31 min 51 s), starting `[round R-5]`, with no chat message; the owner saw Codex continue immediately; the waiting record is gone |
| Publish on the test ticket P2P-2107, 56,000 characters | Codex | beta.4 | refused, as Jira's limit should | Jira answered 400 `CONTENT_LIMIT_EXCEEDED`; description unchanged, one picture left on the ticket; see F-15 |
| Publish on the test ticket P2P-2107, 17,000 characters | Codex | beta.4 | pass | owner's yes on the new preview; read back: before and after lines kept, v1 block replaced with `afkv2:prd`, AC and WE ids and one picture present; the picture left by the refused run deleted; `published-tickets.txt` holds the line. How Jira shows the long text is for the owner to check |
| Setup, takeover in the gc worktree | Claude | beta.5 | pass | hook proof passed; `afk` off and `afkv2` on in that project's `.claude/settings.local.json`; v1 git hooks moved aside in the shared `.git/hooks`; `install --scope local` enabled afkv2, so the enable command of F-14 still has no live run; see F-16 |
| `/afkv2:gc` part 1, GitHub #158 | Claude | beta.5 | running | started in the test pane; interim block removed by the owner first (F-8) |
| `/afkv2:gc` part 2, GitHub #159 | Codex | | not run | |

## Failures and findings

| # | Finding | Status | Owner |
|---|---|---|---|
| F-1 | Codex runs a hook line in the session shell (`codex-rs/core/src/session/mod.rs`, `environment.shell`), not always `cmd /C`. A probe reported PowerShell 7.6.6 here. A line that starts with a quoted path and then an argument is a parse error there. The plan's premise, "Codex uses `cmd /C`, inferred from v1", was wrong. | fixed in beta.3; the test runs the line in each shell | afkv2 |
| F-2 | PowerShell does not expand `%PLUGIN_ROOT%`. Codex substitutes `${PLUGIN_ROOT}` in the command text. | fixed in beta.2 | afkv2 |
| F-3 | v1 hooks on Codex fail at each event with "plugin contents changed; hook approval required", also right after "Trust all". The v1 bundle hash moves after the trust (trusted `e96b741`, computed `d4baa18`). The v1 bundle root is the repository root and holds `.git`. What changes is not verified. | no fix, v1 is frozen; the takeover disables v1 on Codex, so the noise stops (inferred, not run) | v1, frozen |
| F-4 | The create-change-request skill says "base branch in the repository config", and the config reader has no such key. A run on `feat/afkv2` must state the target in the prompt. | open | afkv2 |
| F-5 | An isolated `CODEX_HOME` has no login, so a turn fails before SessionStart. It cannot test hooks. The real home with the normal trust review is the only live route. | recorded | afkv2 live checks |
| F-6 | A sandboxed Codex tool command cannot run the engine. `%LOCALAPPDATA%\afkv2` is read-only for the sandbox account (`WinError 5`), and with that folder writable the engine answers `lavish-axi is not on PATH`. No design document named the sandbox. | fix in beta.4: setup writes `~/.codex/rules/afkv2.rules`, so the plugin's scripts run outside the sandbox with no prompt. The owner chose to keep the file (2026-11-02). Passed live on beta.4 | afkv2 setup |
| F-7 | Run with an approval, the agent ended its turn at 19:10:28 while `show` still ran, and the waiting record appeared at 19:10:29. The Stop hook found no record and did not wait. Time on the approval prompt used up the tool's wait (inferred). | the rules file removes the prompt; no separate fix | afkv2 engine |
| F-9 | The owner restarted the Codex pane at 14:23:13 during the page wait, and it came back as a new pane on the same session. The waiting record survived, and the next turn's Stop hook delivered the answer, so an interrupted wait loses nothing. | recorded, not a defect; the beta.4 run repeats the wait | none |
| F-10 | The hook prompt reaches the agent as `<hook_prompt ...>` around the raw text, and the agent acts on it as work: it started a grill from `[round R-5]`. A free note before the marker means the text does not start with `[round R-`, as the live check expected. | the check's wording to correct; the behaviour is wanted | afkv2 live checks |
| F-11 | Removing and adding the marketplace turns v1 on again next to afkv2. Setup must run after each beta install. | recorded | afkv2 setup |
| F-12 | Card PIN-2 of the check page shows raw JSON (owner's note). The text comes from the fixture `v0-sdd-pass.json`, where a `signoff_packet` is stored as plain text. The renderer did what the document said. | fixture only, no fix needed for the run | afkv2 tests |
| F-13 | After a plugin update, the rules name the old folder, so the first `setup.py status` runs in the sandbox and answers `unreadable-input` (`WinError 5` on `backup`). The agent ran it again with an approval, and setup then wrote the new rules. | recorded: setup recovers with one approval | afkv2 setup |
| F-14 | Switch-back disables afkv2, so `/afkv2:setup` is gone, and nothing says how to return. Codex has no enable command: `codex plugin add afkv2@<marketplace>` enabled it. Setup then needs one more new session, because prepare writes a new install record. | fix on PR #161: the setup skill states the route. The Claude command is not run live (its `--help` lists `enable --scope local`) | afkv2 setup |
| F-15 | A PRD over Jira's length limit fails only after the developer's yes and after the picture upload. Atlassian states a cap of 32,767 characters for a description on Cloud; how it counts ADF is not documented in what I found. Seen here: 25,662 characters of ADF JSON passed, about 80,000 were refused. A real PRD can reach it: afkv2's own is 27,634 bytes (about 36,000 converted, inferred). | fix on the size branch: the preview answers `over_jira_limit` and the skill says so before the yes. The fix warns; it does not split a long PRD | afkv2 to-prd |
| F-16 | Setup on Claude asks for a Codex hook trust check "in this repository" although Codex already trusted these hooks. The fired record is one file per harness, not per repository, so setup cannot tell. Whether Codex's trust is per repository is not verified. | open | afkv2 setup |
| F-17 | The list "Your unsent notes" sits at the end of the page, above the Send bar, and scrolls with the page. "+ note" moves the reader to it, so the owner cannot write a note and see the content it is about (owner, round 1 of #158). The list is afkv2 code (`engine/shell/notes.js`, `notes.css`), not lavish. | fix: dock the list on the screen next to the content; the runtime reads it at the same place in the page, so only the layout moves. For beta.6; the page in use stays as it is | afkv2 engine |
| F-8 | The interim rule block stays in `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`, so a dogfood session holds it next to the afkv2 core behaviors. | Claude: the owner removed it on 2026-11-02 (auto mode refuses the agent this edit). Codex: open, remove it before its dogfood ticket | owner build setup |
