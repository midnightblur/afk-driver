# herdr — tool recipe for the multiplexer transport

The tool's code is [`herdr.py`](herdr.py). It reads its answers from herdr's
JSON output. A herdr error is JSON with an `error.code`; `pane_not_found`,
`agent_not_found` and `tab_not_found` mean the target is gone. Setup register
row: `skills/afk/setup/MANIFEST.md` · C15. Built against herdr 0.9.1.

## Detection (herdr)

herdr is usable in this session when all four hold, checked in this order:

| Check | Fails as |
|---|---|
| `herdr` is on `PATH` | `absent` |
| `HERDR_ENV` is `1` and `HERDR_PANE_ID` is set: this session runs inside a herdr pane | `outside` — installed, but not usable in this session |
| `herdr status` shows `status: running` | `broken` — the session's server does not answer |
| `herdr integration status` shows `<harness>: current` for each harness the run starts | `fixable` — names the setting `herdr integration for <harness>` and its fix `herdr integration install <harness>` |

The integration reports each agent's state (`idle`, `working`, `blocked`,
`done`) and its harness session id; without it a start cannot tell when the
agent is ready, and a resume has no session id (inferred from herdr's
integration list and `agent get` output).

## Verb map (herdr)

| Verb | herdr commands |
|---|---|
| `agent-start` | `tab list --workspace $HERDR_WORKSPACE_ID`; a tab of this step with fewer than 4 panes gets `pane split <pane> --direction right\|down --cwd <cwd> --no-focus --env K=V`, else `tab create --workspace … --cwd … --label <tab> --no-focus --env K=V`; then `pane rename <pane> <label>`; then `agent start <name> --kind <harness> --pane <pane> --timeout <ms> -- <args>`; then `pane process-info --pane <pane>` for the process id and `agent get <pane>` for the session id |
| `agent-send` | `agent prompt <pane> <envelope>`, with no `--wait` |
| `agent-status` | `agent get <pane>`; on a gone agent, `pane get <pane>` tells `exited` (the pane is left) from `gone` |
| `agent-read` | `pane read <pane> --source recent-unwrapped --lines 2000`; the marker holds a short hash of each of the last 16 non-empty lines, so the text after it is found even under a footer a TUI keeps at the bottom |
| `agent-stop` | the process tree kill by process id, then `pane get <pane>` for its tab, `pane close <pane>`, and `tab close <tab>` when `tab get` shows no pane left |
| `agent-list` | `agent list`, filtered to names that start with the prefix |

A `codex` resume does not use `agent start` (see the traps): it types the resume
command into the new pane with `pane run <pane> <command line>`, waits until
`agent get` shows the agent `idle`, then `agent rename <pane> <name>`.

## Delivery way (herdr)

One way: `agent prompt` into the receiver's pane. It sends the text and Enter as
one submission. A busy `claude` 2.1.305 pane queues the messages and takes them
all once its running tool call ends, in the same turn. A busy `codex` 0.163.0 pane either takes the
first message into the running turn and queues the rest for the next one, or holds them all
until the running command ends; either way the turn that takes several queued messages together
answers only the last of them. Either
way a busy pane delays delivery and never reorders it. herdr rejects a prompt to an agent waiting at a dialog
(`agent_blocked`) before it sends anything.

`agent prompt` types into the input box, so the contact agent never gets a
message this way: its messages go to its inbox. Every other agent gets its
messages in its pane, and nobody types in those panes.

## Tab support (herdr)

herdr makes tabs. The contact agent's tab (`$HERDR_TAB_ID`) holds only the
contact agent. Agents of one pattern step share a tab named by the goal and the
step, at most 4 panes in a 2 by 2 grid: the 2nd pane splits the 1st to the
right, the 3rd splits the 1st down, the 4th splits the 2nd down. A full tab is
followed by one named `<tab> 2`, then `<tab> 3`. A tab closes when its last pane
closes. A tab that cannot be made refuses the start, naming the tab.

## Known traps (herdr)

| Trap | Seen | Handling |
|---|---|---|
| A `codex` resume through `herdr agent start` left no pane; typed into a new pane with `herdr pane run`, it worked | `providers/CONFORMANCE.md` probe row "A blocked pane agent stays live…" (2026-09-30) | `codex` resumes by `pane run`, then `agent rename` |
| A pane close sends no signal a shell trap catches; a plain pane's process is killed within 10 s | probe row "A capture command's run-time limit…" (2026-09-30) | `agent-stop` kills the process tree by id before the close |
| A `codex` pane agent's shell child outlived a pane close with no live parent, owned by the sandbox user, and the operator's `Stop-Process` got Access is denied | the same row, re-probe 2026-10-06 | the tree is listed before the kill, so an orphaned member is still killed by id; a member that survives is named in `survivors` and `stopped` is false |
| A message sent while the pane holds unsent typed text is appended to it, and both are submitted as one prompt | trial T11 case D (2026-09-28) | nobody types in a pane agent's pane |
| A busy pane delays messages. In trial T11 they waited until the turn and its Stop handlers ended, and turn-end gates held 2 turns for 3 and 9 minutes. `codex` 0.163.0 takes the first into the running turn or holds all until the running command ends, and a turn that takes several queued messages answers only the last; `claude` 2.1.305 takes all queued messages when the running tool call ends, before the Stop handlers | trial T11; probe rows "A busy pane agent receives several sent messages in order" and "agent-send delivers each envelope once…" (2026-10-20, re-run 2026-10-21) | a delay, never a reorder |
| `agent start` returns `agent_not_ready` when a dialog blocks the start; `claude`'s folder trust dialog blocks every start in a folder no trusted folder contains | herdr's own help; the trust-dialog probe row (2026-10-20) | the start reads the screen's last 6 lines, stops the agent, closes the pane, and answers exit 4 with `dialog` true and those lines |
| `agent start` waits until the agent is idle, so a launch prompt's whole first turn counts against its timeout | probe row "Parallel pane agents' wiring scans…" (2026-10-20) | herdr gets the start budget less 40 s; on its `timeout`, a working agent counts as started and a blocked one as a dialog |
| A Git Bash child's Windows parent is a fork stub that is gone, so the Windows process tree misses it | probe row "agent-stop leaves no process…" (2026-10-20) | the tree adds each MSYS child that Git for Windows' `ps` names |
| A `codex` sandbox runs shell commands as its sandbox user; the operator cannot kill them (`Access is denied`) and Git's `ps` does not show their MSYS children | the same row | `stopped` false names the members it saw; cleanup reports the agent unkillable |
| `pane read` answers plain text, not JSON | `herdr pane read` on 0.9.1 | the read takes the text as it comes |
| Control commands act on the server of the caller's session; outside a herdr pane they would act on a session the caller does not own | `herdr --skill` | detection answers `outside` and no verb runs |
