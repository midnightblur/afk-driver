---
name: setup
description: /afkv2:setup — installs afkv2 for Claude and Codex in one run, proves its hook, then takes over from v1 with a backup for every write; `switch-back` returns to v1. Use after installing afkv2, in any repository, or to go back to v1.
---

# /afkv2:setup

One run serves Claude and Codex, in any repository, the main checkout included.
Every step is a verb of `scripts/setup.py` in this skill's folder; each verb
answers one JSON object and exits 0 (ok), 1 (refused or failed) or 2 (bad input).
Run it with `python` (on Windows `py -3` when `python` is missing), from the
repository root. Show the developer each answer's outcome in one plain sentence.

Ask the developer only for what a step below names. Values that are not secret
you ask in this session; the Jira token never passes through you.

## Steps

1. **Status.** `setup.py status`. Read it once; the steps below act on its fields.
2. **Prepare.** `setup.py prepare` — checks Python 3 on the path, installs rg
   and puts it on the path of every shell, writes the install record. A red
   `rg.shells` entry: tell the developer to open a new terminal and harness, then
   run setup again.
3. **Jira values.** `jira.complete` false: ask the developer to run
   `python <this skill's folder>/scripts/setup.py secrets` in their own terminal
   (it asks for `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` and stores them
   where v1 keeps them), then run `status` again. Report each key's source, never
   a value.
4. **v1 config.** `v1_config.v1_config` true and `v1_config.done` false: show the
   developer `v1_config.keys` and offer one copy into `.afkv2`. On yes,
   `setup.py copy-config`. The v1 file stays as it is.
5. **Ownership.** `ownership` is `missing`: ask once which paths the developer's
   team owns and which it shares. Answer given: `setup.py ownership --own <globs>
   --shared <globs>`. Skipped: `setup.py ownership --skip`.
6. **Codex hook trust review.** The developer uses Codex (a `codex_plugins` entry,
   or a block in `v1_blocks.codex`): ask them to start a new Codex session in this
   repository, trust the afkv2 hooks in Codex's hook review, and end that session.
   Codex skips an untrusted hook without a message.
7. **Proof and takeover.** Find the line `afkv2-core-behaviors end <sha12>` in
   your own context — the session-start hook put it there. Run
   `setup.py takeover --provider <claude|codex> --end-marker "<that full line>"`
   (`--end-marker ""` when the line is absent). The script proves the hook, then
   removes the v1 rule block from both instruction files, moves the v1 git hook
   stubs aside, switches the plugins (Claude: this project's
   `.claude/settings.local.json`, kept out of git by a line in `.git/info/exclude`
   when git does not already ignore it; Codex: the global config) and installs
   lavish host 0.1.80 — each with a backup.
   - `proof.proved` false: the v1 block stays and its backup is kept. Tell the
     developer each line of `proof.reasons`, then to start a new session and run
     `/afkv2:setup` again.
   - Another step failed: report its `error`; a re-run continues where it stopped.
8. **Report.** One line per step: done, already done, or why not.

## Switch back to v1

`/afkv2:setup switch-back`: run `setup.py switch-back`. It restores the v1 block,
the git hook stubs, the plugin settings and the lavish host version from the
backups, and leaves only v1 on. A file the harness changed since keeps those
changes (`merged`); a deleted repository is skipped (`repo-missing`). A
`.claude/settings.local.json` that holds the off value stays, with its ignore
line. Report each restored item, each `conflict` or `failed` with its `backup` path
(`codex_config` has `backup_dir`, file `codex/config.toml`), and the
`published_tickets` list: on those tickets the developer
must not run v1's publish, because v1 does not find afkv2's block.
