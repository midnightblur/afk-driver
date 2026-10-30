# Codex live checks

The plugin owner runs these steps. They need afkv2 enabled in the global Codex config, which is the owner's call. An agent does not run them.

Each check has a pass rule and an on-fail path. Write the result in the table at the end.

## Before you start

1. Use a test repository, not a repository with real work.
2. Get the expected hash. Open `afkv2\hooks\built\afkv2-core-behaviors.txt` in the afkv2 source. Its last line is `afkv2-core-behaviors end <sha12>`. Write down the `<sha12>`.
3. Check the install path. The repository Codex marketplace `.agents/plugins/marketplace.json` lists afkv2 with the path `./afkv2`. You add no entry.
4. Enable afkv2 in Codex from that marketplace. The exact Codex command is not verified here; use the Codex plugin documentation.
5. Write down the time. The hook writes `%LOCALAPPDATA%\afkv2\fired-codex.txt` each time it runs.

## Check 1 — Codex accepts the `.cmd` hook after the trust review

1. Start `codex` in the test repository. Do not use the full-bypass flag or `exec`: with them, Codex skips untrusted hooks and shows nothing.
2. When Codex shows "Hooks need review", type `/hooks` and trust the two afkv2 handlers (`SessionStart`, `SubagentStart`).
3. Start a new session. Send: `Quote the last line of your context that starts with afkv2-core-behaviors end.`
4. Send: `Start one subagent. Ask it to quote the last line of its context that starts with afkv2-core-behaviors end, and report its answer.`
5. Look at `%LOCALAPPDATA%\afkv2\fired-codex.txt`. It must be newer than the time from "Before you start", step 5.

Pass: the session and the subagent both quote `afkv2-core-behaviors end <sha12>` with the expected `<sha12>`, and the fired record is new.

Also look for these problems:

- The answer holds a file path and a preview, not the text. Codex cut the text at its output limit (about 2,500 tokens). Record it; the owner decides on `additionalContextLimit`.
- The text has extra lines before the begin marker. Codex runs the command with `cmd /C` (inferred from v1 evidence), which also runs a cmd `AutoRun` registry command. Record the extra lines.

On fail: the hook does not run on Codex. The fallback is a Python hook, and the 50 ms limit goes back to the owner (SDD §7, failure row ".cmd hook refused by a harness"). If Codex refuses `hooks.json` because of the Claude-only `args` field, move the Codex handlers to an inline `hooks` object in `afkv2/.codex-plugin/plugin.json`.

## Check 2 — Codex runs the hook again after a compaction

1. In the session from check 1, type `/compact`.
2. Send: `Quote the last line of your context that starts with afkv2-core-behaviors end.`

Pass: the answer is `afkv2-core-behaviors end <sha12>` with the expected `<sha12>`.

On fail: record it as a gap of PRD AC-012. The owner decides.

## Results

| Check | Date | Codex version | Result | Notes |
|-------|------|---------------|--------|-------|
| 1 | | | | |
| 2 | | | | |
