---
name: herdr-playbook
description: herdr playbook — how an agent uses herdr to open and close panes, run commands, start Claude or Codex in another pane, send it a prompt, check the prompt was submitted, wait for the agent to finish, read its result, and fall back outside herdr. Use before any herdr command, or to start another agent in a visible pane.
---

# herdr playbook

herdr is a terminal workspace manager for coding agents. Each section below gives the commands and the official pages they were checked against: herdr docs v0.9.5, local herdr 0.9.1. When a command fails, the installed binary is the authority: run `herdr <group>` with no subcommand (for example `herdr pane`) to print its syntax. Never run bare `herdr`: it opens the terminal UI. Never omit the arguments of a command that changes the layout to learn its syntax: `herdr workspace create` runs with its defaults.

Most commands print one JSON object. Read each id from that answer; never predict an id. An error prints JSON on stderr with exit 1, and its code at `.error.code`. A usage error exits 2.

## H-1 Workspaces, tabs and panes

- A **workspace** is the top-level project container: 1 per repository, task or investigation. Id form `w1`.
- A **tab** is one layout inside a workspace. Id form `w1:t1`.
- A **pane** is one real terminal inside a tab. It exists with or without an agent in it. Id form `w1:p1`. A closed id is never used again.
- An **agent** is a coding agent that herdr recognizes in a pane. Address it by its live name or by the id of its pane.

```
herdr workspace list
herdr tab list --workspace "$HERDR_WORKSPACE_ID"
herdr pane list --workspace "$HERDR_WORKSPACE_ID"
herdr pane current --current
herdr agent list
```

Docs: <https://herdr.dev/tui/docs/concepts/>, <https://herdr.dev/tui/docs/agent-automation/#three-primitives>, <https://herdr.dev/tui/docs/agent-skill/> (the id forms and the closed-id rule)

## H-2 Open, close and rename a pane or tab

Default: a sibling pane in the current tab, with the working folder you need. Do not create a workspace or a tab unless the task asks for one. Keep the developer's focus with `--no-focus`.

```
herdr pane split --current --direction right --cwd <folder> --no-focus   # new id: .result.pane.pane_id
herdr pane rename <pane_id> <label>
herdr pane close <pane_id>
herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd <folder> --label <label> --no-focus   # .result.tab.tab_id, .result.root_pane.pane_id
herdr tab rename <tab_id> <label>
herdr tab close <tab_id>
```

Split a wide pane `right` and a tall pane `down`; `herdr pane layout --current` shows the size. `--current` needs `HERDR_PANE_ID`. Closing the last tab of a workspace closes the workspace too.

Docs: <https://herdr.dev/tui/docs/cli-reference/#panes>, <https://herdr.dev/tui/docs/cli-reference/#tabs>

## H-3 Run a command in a terminal pane

Use the pane commands for shells, tests, servers and watchers. Never send a shell command to an agent: `agent prompt` types into the agent session, not into a shell.

```
herdr pane run <pane_id> "<command>"                                    # text and Enter, in one step
herdr pane wait-output <pane_id> --match "<text>" --timeout 120000      # or --regex <pattern>
herdr pane read <pane_id> --source recent-unwrapped --lines 120
```

`pane wait-output` searches the last 80 rows (`--lines`) at once, and that includes the echoed command. Pick a match text that only new output holds. Read sources: `visible` (the screen now), `recent`, `recent-unwrapped` (best for logs), `detection`.

Docs: <https://herdr.dev/tui/docs/cli-reference/#panes>, <https://herdr.dev/tui/docs/cli-reference/#output-waits>, <https://herdr.dev/tui/docs/cli-reference/#read-sources>

## H-4 Start Claude or Codex, always with full auto-approval

`agent start` needs an existing pane at its shell prompt; it never creates a pane. Create the pane first (H-2). The name matches `[a-z][a-z0-9_-]{0,31}` and is unique among live agents. Pass the tool's own flags after `--`. Always:

```
herdr agent start <name> --kind claude --pane <pane_id> --timeout 90000 -- --dangerously-skip-permissions
herdr agent start <name> --kind codex  --pane <pane_id> --timeout 90000 -- --yolo
```

`--timeout` is in milliseconds, more than 3000 and at most 300000; the default is 30000. The answer `agent_not_ready` means the agent shows a dialog at startup: read it (H-5) before you do anything else. A policy can forbid full auto-approval:

- Claude: `permissions.disableBypassPermissionsMode` is `"disable"` in a managed source: `managed-settings.json` or a file of `managed-settings.d/` in `/Library/Application Support/ClaudeCode/` (macOS), `/etc/claude-code/` (Linux and WSL) or `C:\Program Files\ClaudeCode\` (Windows); the registry value `Settings` under `HKLM\SOFTWARE\Policies\ClaudeCode` or `HKCU\SOFTWARE\Policies\ClaudeCode` (Windows); the macOS profile domain `com.anthropic.claudecode`.
- Codex: a `requirements.toml` in `/etc/codex/` (Linux and macOS) or `%ProgramData%\OpenAI\Codex\` (Windows), or the macOS key `com.openai.codex:requirements_toml_base64`, sets `allowed_sandbox_modes` without `danger-full-access`, sets `allowed_approval_policies` without `never`, or sets `allowed_permission_profiles` without `:danger-full-access = true`.

An unreadable policy counts as a ban. Then do not start the agent; fall back as in H-9.

Docs: <https://herdr.dev/tui/docs/agent-automation/#agent-identity-and-launch>, <https://code.claude.com/docs/en/permission-modes>, <https://code.claude.com/docs/en/managed-settings>, <https://developers.openai.com/codex/cli/reference>, <https://developers.openai.com/codex/enterprise/managed-configuration>

## H-5 Send text to another pane, and read its output

```
herdr agent prompt <name> "<text>"                       # to an agent: text and Enter, in one step
herdr agent read <name> --source recent-unwrapped --lines 120
herdr agent send-keys <name> esc                         # a key to the agent's UI: esc, enter, ctrl+c, up
herdr pane send-text <pane_id> "<text>"                  # raw text to a terminal, no Enter
herdr pane send-keys <pane_id> enter
herdr pane read <pane_id> --source visible --lines 40
```

`agent prompt` refuses `agent_blocked` and sends nothing when the agent shows an approval or a question dialog. Read the dialog, then ask the developer before you answer it with `agent send-keys`. For a dialog at startup, wait for idle before you prompt. A full-screen agent refuses `agent read --lines N` with `agent_not_idle` while it is working, blocked or unknown: wait for idle and read again, or use `--source visible`. When a longer `recent-unwrapped` read still cuts the answer, ask the agent to write it to a file and reply with the path; then read the file. Use this only as a fallback, never in the first prompt.

Docs: <https://herdr.dev/tui/docs/agent-automation/#choose-the-control-surface>, <https://herdr.dev/tui/docs/agent-automation/#alternate-screen-history-reads>, <https://herdr.dev/tui/docs/cli-reference/#agents>

## H-6 Check that a prompt was submitted and the agent works

```
herdr agent prompt <name> "<text>" --wait --until working --timeout 30000
```

Exit 0: the agent started work. The code `agent_prompt_stalled`: herdr saw no work within 5 seconds. A stall or a `timeout` does not prove that the text did not arrive, so never send the prompt again. Do this:

1. `herdr pane read <pane_id> --source visible --lines 40`.
2. The text is gone from the input line: run `herdr agent wait <name> --until working --timeout 30000`.
3. The text still sits in the input line: send 1 Enter with `herdr pane send-keys <pane_id> enter`, then run the same wait. Send no second Enter.
4. The wait exits not 0: the agent can finish before herdr sees it work, so check `completion_seq` in `herdr agent get <name>`. Only when it shows no finished work, report the prompt as not submitted.

Docs: <https://herdr.dev/tui/docs/cli-reference/#agents>, <https://herdr.dev/tui/docs/cli-reference/#output-waits>

## H-7 Wait for an agent to finish, with no polling loop

```
herdr agent wait <name> --until idle --until done --until blocked
```

The wait is event-driven, and it has no time limit when you omit `--timeout`. Run it as one background job of your harness, so that its exit wakes you. Do not loop over `agent get` or `pane read`. `idle` and `done` both mean the agent is ready for input. `blocked` means a dialog waits: read it (H-5). `unknown` does not prove that the work succeeded. When the wait answers, check the result file the agent had to write.

Docs: <https://herdr.dev/tui/docs/agent-automation/#choose-the-control-surface>, <https://herdr.dev/tui/docs/cli-reference/#output-waits>

## H-8 Close each pane you opened, once its result is read

Record each pane id and each worktree you create, when you create it. After you read the result:

```
herdr pane close <pane_id>
git worktree remove <worktree>                           # only a worktree you created for the agent
```

The code `pane_not_found` means the pane is already gone. Close only the panes you opened, never the pane of the developer or of another agent.

Docs: <https://herdr.dev/tui/docs/cli-reference/#panes>, <https://git-scm.com/docs/git-worktree>

## H-9 Detect a session outside herdr, and fall back

herdr sets `HERDR_ENV=1` in each process of a pane it manages, with `HERDR_PANE_ID`, `HERDR_TAB_ID` and `HERDR_WORKSPACE_ID`. Before the first herdr command, check both:

- `HERDR_ENV` is `1`.
- `herdr` is on `PATH`.

If one check fails, send no herdr command: an agent outside herdr must not control a session it does not own. Fall back: do the work in your own session or a subagent, and tell the developer the reason (herdr missing, or the session outside herdr). Setup installs herdr after the developer's yes.

Docs: <https://herdr.dev/tui/docs/cli-reference/#environment-variables>, <https://herdr.dev/tui/docs/agent-skill/>, <https://herdr.dev/tui/docs/install/>
