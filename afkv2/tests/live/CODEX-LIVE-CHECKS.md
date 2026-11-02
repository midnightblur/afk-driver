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
2. When Codex shows "Hooks need review", type `/hooks` and trust the three afkv2 handlers (`SessionStart`, `SubagentStart`, `Stop`).
3. Start a new session. Send: `Quote the last line of your context that starts with afkv2-core-behaviors end.`
4. Send: `Start one subagent. Ask it to quote the last line of its context that starts with afkv2-core-behaviors end, and report its answer.`
5. Look at `%LOCALAPPDATA%\afkv2\fired-codex.txt`. It must be newer than the time from "Before you start", step 5.

Pass: the session and the subagent both quote `afkv2-core-behaviors end <sha12>` with the expected `<sha12>`, and the fired record is new.

Also look for these problems:

- The answer holds a file path and a preview, not the text. Codex cut the text at its output limit (about 2,500 tokens). Record it; the owner decides on `additionalContextLimit`.
- The text has extra lines before the begin marker. Codex runs the command with `cmd /C` (inferred from v1 evidence), which also runs a cmd `AutoRun` registry command. Record the extra lines.

On fail: the hook does not run on Codex. The fallback is a Python hook (SDD §7, failure row ".cmd hook refused by a harness"). If Codex refuses `hooks.json` because of the Claude-only `args` field, move the Codex handlers to an inline `hooks` object in `afkv2/.codex-plugin/plugin.json`.

## Check 2 — Codex runs the hook again after a compaction

1. In the session from check 1, type `/compact`.
2. Send: `Quote the last line of your context that starts with afkv2-core-behaviors end.`

Pass: the answer is `afkv2-core-behaviors end <sha12>` with the expected `<sha12>`.

On fail: record it as a gap of PRD AC-012. The owner decides.

## Check 3 — a page answer sent after 10 minutes reaches the agent with no chat message

Run this check after lavish-axi 0.1.80 is the global install. `engine show` refuses any other version.

1. In the test repository, make `.afkv2\config.json` with a `spec_folder`, and a page document at `<spec folder>\<feature>\pages\grill-check3.json`. Copy `afkv2\tests\engine\fixtures\v0-sdd-pass.json` for the body, and set `session.id` to `check3` and `session.skill` to `grill`.
2. In a new Codex session, send: `Run: python <afkv2 source>\engine\engine.py show <page document path>. Then end your turn. Do not poll.`
3. Open the page in the browser. Look at the waiting record: `%LOCALAPPDATA%\afkv2\page-waiting-*.json`. The name after `page-waiting-` is the `CODEX_THREAD_ID` of the session.
4. Look at the Codex hook input, if your Codex version shows it. The `session_id` of the `Stop` event must equal that name. The docs do not state this equality; this check proves it. If they differ, the hook finds no record and returns nothing, and the check fails at step 7.
5. Wait for 10 minutes. Type nothing in Codex. While you wait, note whether you can still use the chat (PRD Further Notes, unverified premise).
6. Mark one card and click **Send my answers**. If the page shows "No mark on …", click it again.
7. Do not write in the chat. Watch Codex.

Pass: within one minute Codex continues by itself, and its next prompt is the raw response text, which starts with `[round R-`. The file `page-waiting-*.json` is gone.

On fail: the wait was refused or cut, or the hook found no record. The fallback is one chat message after Send, then the agent runs `engine.py poll`. Report the failure to the owner (SDD §9b, row "Codex Stop hook"; ADR-0006).

## Results

| Check | Date | Codex version | Result | Notes |
|-------|------|---------------|--------|-------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
