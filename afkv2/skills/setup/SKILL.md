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
   Then `setup.py claude-cli` — compares the Claude CLI with the newest release of
   its `autoUpdatesChannel` and the Fable minimum, and runs `claude update` when it
   is older. `new_session` true: tell the developer to start a new session and run
   setup again, and stop. A refusal `update-required`: show its `reason` and
   `commands`, and stop; `channel-too-old`: report its `reason`, and stop. A `warning`:
   report it, and continue.
2. **Prepare.** `setup.py prepare` — checks Python 3 on the path, installs rg
   and puts it on the path of every shell, writes the install record. A red
   `rg.shells` entry: tell the developer to open a new terminal and harness, then
   run setup again.
   Then `setup.py diagram-renderer` — installs the diagram command with the browser
   download off, and writes `puppeteer-config.json` that names the installed Edge.
   A refusal `no-edge` installs nothing and downloads nothing: report its `reason`.
   Then `setup.py browser-driver` — installs Chrome DevTools MCP at its pin, registers
   it for Claude and Codex with usage statistics off and a backup first, and proves
   it in Chrome and Edge, headless and visible: open a test page, click, screenshot,
   read the console. Report each proof. A refusal (`no-browser`, `driver-install-failed`,
   `register-failed`, `proof-failed`): report its `reason`; `proof-failed` names the
   browser and the step. Ask the developer once whether the agent should drive
   their own signed-in Chrome or Edge. On yes, tell them to allow remote debugging
   at `chrome://inspect/#remote-debugging` or `edge://inspect/#remote-debugging`,
   then run `setup.py browser-driver --attach chrome|edge` with a command time limit of
   at least 5 minutes: the attach waits up to 4 minutes for the browser. An `attach` with `ok`
   false: tell the developer its `why`, and offer its `offer` items.
   A new harness session reads the new entries.
   Then the judge model: for each provider whose CLI is on the path, run
   `setup.py judge --provider <claude|codex>`. Codex runs the default model of its CLI;
   `--model <name>` picks another. Report `model` and the `which` answer. A refusal
   `no-provider` or `proof-failed`: report its `reason`.
   `status` field `gh` with `ok` false: tell the developer its `fix`.
3. **herdr.** `herdr` is `present` or `declined`: ask nothing. `herdr` is
   `installed`: ask nothing; tell the developer to open a new terminal and
   harness, so that herdr is on the path. `herdr` is `ask`:
   ask the developer once in this session whether to install herdr through its
   official installer; without it, design sessions get 1 solution proposer. Then
   `setup.py herdr --answer yes` or `setup.py herdr --answer no`. A no is recorded
   and never asked again, also after `switch-back`. A refusal `install-failed`: report its `reason`; the
   developer can install herdr by hand.
4. **Fable advisor.** Codex: no step. `advisor` is `not-used`, `declined` or `done`:
   ask nothing. `advisor` is `ask`: ask the developer once in this session whether
   Claude should consult Fable as its advisor; on some plans Fable bills to usage
   credits. Then `setup.py advisor --answer yes` or `--answer no`; a no is recorded
   and never asked again. A refusal `advisor-blocked` or `proof-failed`: report its
   `reason`. Report each `overrides` line. `consent` is a list, or `advisor` is
   `consent`: tell the developer to type each `consent` item in a Claude session,
   in order (in a Codex session, they start `claude` for it). Wait for their word
   that they did, then `setup.py advisor --consent-done`. A refusal
   `model-not-restored`: report its `reason`, and run it again after they act.
5. **Jira values.** `jira.complete` false: ask the developer to run
   `python <this skill's folder>/scripts/setup.py secrets` in their own terminal
   (it asks for `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` and stores them
   where v1 keeps them), then run `status` again. Report each key's source, never
   a value.
6. **Repository config.** `config_file` false: setup writes `.afkv2/config.json`
   once, and it needs a spec folder. `spec_folder.value` set: use it, and pass no
   flag. `spec_folder.value` null: ask the developer in this session for a folder
   path relative to the repository root, then pass `--spec-folder <path>`.
   `v1_config.v1_config` true: show the developer `v1_config.keys` and offer one
   copy. On yes, `setup.py copy-config`; on no, `setup.py copy-config --no-v1-values`.
   No v1 config: `setup.py copy-config`. The v1 file stays as it is. A refusal
   `no-spec-folder` or `bad-spec-folder` writes nothing: report its `reason`, and ask again.
7. **Ownership.** `ownership` is `missing`: ask once which paths the developer's
   team owns and which it shares. Answer given: `setup.py ownership --own <globs>
   --shared <globs>`. Skipped: `setup.py ownership --skip`.
8. **Codex hook trust review.** The developer uses Codex (a `codex_plugins` entry,
   or a block in `v1_blocks.codex`): ask them to start a new Codex session in this
   repository, trust the afkv2 hooks in Codex's hook review, and end that session.
   Codex skips an untrusted hook without a message.
9. **Proof and takeover.** Find the line `afkv2-core-behaviors end <sha12>` in
   your own context — the session-start hook put it there. Run
   `setup.py takeover --provider <claude|codex> --end-marker "<that full line>"`
   (`--end-marker ""` when the line is absent). The script proves the hook, then
   removes the v1 rule block from both instruction files, moves the v1 git hook
   stubs aside, switches the plugins (Claude: this project's
   `.claude/settings.local.json`, kept out of git by a line in `.git/info/exclude`
   when git does not already ignore it; Codex: the global config) and installs
   lavish host 0.1.86 — each with a backup. It also writes `codex_rules`, which lets
   the plugin's own scripts run outside the Codex sandbox with no prompt: tell the
   developer this in the report. After a plugin update, run setup again.
   A v1 session that starts in the repository installs the git hook stubs again;
   `removed-again` means setup removed them a second time, so tell the developer
   that v1 is still running somewhere in this repository.
   - `proof.proved` false: the v1 block stays and its backup is kept. Tell the
     developer each line of `proof.reasons`, then to start a new session and run
     `/afkv2:setup` again.
   - Another step failed: report its `error`; a re-run continues where it stopped.
10. **Report.** One line per step: done, already done, or why not.

## Return to afkv2 after a switch-back

Switch-back hides this skill. Tell the developer to enable afkv2 first: on Codex
`codex plugin add afkv2@<marketplace>`; on Claude
`claude plugin enable afkv2@<marketplace> --scope local` in that repository. Then
start a new session and run `/afkv2:setup`. When it answers that the hook fired
before the install record, start one more new session and run it again.

## Switch back to v1

`/afkv2:setup switch-back`: run `setup.py switch-back`. It restores the v1 block,
the git hook stubs, the plugin settings, the Jira values and the lavish host
version from the backups, and leaves only v1 on. A file the harness changed since
keeps those changes (`merged`); a deleted repository is skipped (`repo-missing`). A
`.claude/settings.local.json` that holds the off value stays, with its ignore
line. Report each restored item and each `conflict` or `failed` entry with its `backup`
path. For `codex_config: failed` the backup is `codex/config.toml` under the
top-level `backup_dir`; for a failed `lavish` report its `error`; `codex_rules: failed`
names the file to delete by hand, `~/.codex/rules/afkv2.rules`. `jira_values`
names each key's outcome and never a value. An `error.code` of `backup-not-private`
means setup could not limit the backup folder to the current user and wrote no token
backup: report its `reason` and do not work around it. In a takeover it is under
`plugins.codex`; the Claude switch is already done, and a new run finishes the step. The backup of those values holds the
token in plain text under `backup_dir`: never open or print it. Restored user
environment values reach a new terminal, not a running one. Report the
`published_tickets` list: on those tickets the developer
must not run v1's publish, because v1 does not find afkv2's block. The diagram
package and its config stay installed (`diagram_renderer: left-installed`); v1 does not read them. Switch-back
removes the browser driver entries from both harnesses (`browser_driver`); the driver
package stays installed. `advisor` `restored` puts back the developer's own advisor
value; `kept-changed` means the developer changed it since, so it stays.
