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
| Switch-back, setup again | Codex | | not run | |
| Live check 3, sandboxed | Codex | beta.3 | fail | F-6 |
| Live check 3, page answer after 10 minutes | Codex | beta.3, one approval, run outside the sandbox | in progress | Stop hook waiting since 14:12:32; see F-7 |
| Publish on the test ticket P2P-2107 | Claude | | not run | |
| `/afkv2:gc` part 1, GitHub #158 | Claude | | not run | |
| `/afkv2:gc` part 2, GitHub #159 | Codex | | not run | |

## Failures and findings

| # | Finding | Status | Owner |
|---|---|---|---|
| F-1 | Codex runs a hook line in the session shell (`codex-rs/core/src/session/mod.rs`, `environment.shell`), not always `cmd /C`. A probe reported PowerShell 7.6.6 here. A line that starts with a quoted path and then an argument is a parse error there. The plan's premise, "Codex uses `cmd /C`, inferred from v1", was wrong. | fixed in beta.3; the test runs the line in each shell | afkv2 |
| F-2 | PowerShell does not expand `%PLUGIN_ROOT%`. Codex substitutes `${PLUGIN_ROOT}` in the command text. | fixed in beta.2 | afkv2 |
| F-3 | v1 hooks on Codex fail at each event with "plugin contents changed; hook approval required", also right after "Trust all". The v1 bundle hash moves after the trust (trusted `e96b741`, computed `d4baa18`). The v1 bundle root is the repository root and holds `.git`. What changes is not verified. | no fix, v1 is frozen; the takeover disables v1 on Codex, so the noise stops (inferred, not run) | v1, frozen |
| F-4 | The create-change-request skill says "base branch in the repository config", and the config reader has no such key. A run on `feat/afkv2` must state the target in the prompt. | open | afkv2 |
| F-5 | An isolated `CODEX_HOME` has no login, so a turn fails before SessionStart. It cannot test hooks. The real home with the normal trust review is the only live route. | recorded | afkv2 live checks |
| F-6 | A sandboxed Codex tool command cannot run the engine. `%LOCALAPPDATA%\afkv2` is read-only for the sandbox account (`WinError 5`), and with that folder writable the engine answers `lavish-axi is not on PATH`. No design document named the sandbox. | fix in beta.4: setup writes `~/.codex/rules/afkv2.rules`; live run pending | afkv2 setup |
| F-7 | Run with an approval, the agent ended its turn at 19:10:28 while `show` still ran, and the waiting record appeared at 19:10:29. The Stop hook found no record and did not wait. Time on the approval prompt used up the tool's wait (inferred). | the rules file removes the prompt; no separate fix | afkv2 engine |
| F-8 | The interim rule block stays in `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`, so a dogfood session holds it next to the afkv2 core behaviors. | open: remove it from the file for that harness before its dogfood ticket | owner build setup |
