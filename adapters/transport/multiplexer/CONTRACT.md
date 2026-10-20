# transport/multiplexer — capability contract (multiplexer panes)

Each agent runs in a pane of the terminal multiplexer this session runs inside.
The verbs are the same for every tool; one recipe file per tool in this folder
states how each verb maps to that tool's commands. Tools: [herdr](herdr.md).
Entry: `transport.sh`, which runs `multiplexer.py`; it answers with the first
tool usable in this session, or exit 4 naming each tool's state.

## Verbs

| Verb | Payload | Answers |
|---|---|---|
| `agent-start` | `harness` (`claude` \| `codex`), `name` (the agent name), `label` (the pane label), `cwd`, `tab` (the tab name: goal and pattern step), optional `prompt`, `model`, `effort`, `resume` (the session id to resume), `args` (other native options), `env` | `kind`, `tool`, `handle` (the pane id), `pid`, `started_at` (the agent process's creation time), `pane_label`, `agent_name`, `session_id` (may be empty), `tab_id` |
| `agent-send` | `handle`, `text` (the envelope) | `delivered`, `at`, `way` |
| `agent-status` | `handle` | `alive`, `state`, `since` (empty when the tool reports no time) |
| `agent-read` | `handle`, optional `since_marker` | `text` after the marker, `marker`, `complete` (false when the marker is no longer on screen) |
| `agent-stop` | optional `pid`, `handle`, `force` | `stopped` true with `method`, or false with `reason` and `survivors`; `pane_closed` and `pane_id` when a handle is given |
| `agent-list` | `prefix` (the agent-name prefix) | `agents`, each with `agent_name` and `pane_id` |

`agent-start` never opens a pane in the contact agent's tab. It adds a pane to
a tab of the same name with fewer than 4 panes, as a 2 by 2 grid, else it makes
a new tab; a tab it cannot make answers exit 4 naming the tab. A start a dialog
blocks is stopped and answers exit 4 with `dialog` true. Each start carries the
harness's update-off switch on its own launch only (`../launch.py`).

`agent-stop` kills the whole process tree first, by each member's id, then
closes the pane, then the tab when its last pane is gone. A pane already gone
counts as closed. It never relies on a shell trap: a pane close sends no signal
one catches.

`agent-send` delivers into the receiver's pane by the tool's delivery way. The
contact agent's messages never come here: the team entry script writes them to
its inbox, because herdr's one way types into the input box.

## Exit codes

0 the verb ran · 2 a bad payload or field, named · 3 not a verb of this kind ·
4 `unavailable`: no usable tool, a tab that cannot be made, a blocked start, a
failed resume, or a receiver that is gone (`receiver_gone` true).

## Configuration keys read

- `transport.kind` — through the dispatcher, or the machine probe's hand-in

## Runtime

Bash, Python 3, and one tool: herdr (`skills/afk/setup/MANIFEST.md` · C15),
with this session inside a herdr pane.

## Documented degradation

No usable tool → exit 4; the machine probe then resolves another kind.
