# transport/subagent — capability contract (harness subagents)

The harness spawns its own child with its subagent tool and owns that child's
whole lifecycle, so no script can start, message, read, stop or list it.
Entry: `transport.sh`, which runs `subagent.py`.

## Verbs

| Verb | Answer |
|---|---|
| `agent-start` | exit 3, `unsupported`: start the child with the harness's subagent tool |
| `agent-send` | exit 3, `unsupported`: a subagent takes no message after its start |
| `agent-status` | exit 3, `unsupported`: the harness's tool reports the state |
| `agent-read` | exit 3, `unsupported`: the child's report returns as text to the agent that started it |
| `agent-stop` | exit 3, `unsupported`: the child ends when its task returns |
| `agent-list` | exit 3, `unsupported`: a subagent has no pane id |

The input is the verb, then one JSON object as the next argument, as for every
transport kind (`ADAPTERS.md` "transport"). A payload that is not one JSON
object answers exit 2 before the verb's own answer.

## Configuration keys read

- `transport.kind` — through the dispatcher, or the machine probe's hand-in

## Runtime

Bash and Python 3 only. No external tool.

## Documented degradation

This kind is the fallback when no pane transport is usable: role agents run as
subagents, the run report says so, and the agent that started a subagent writes
its report file from the returned text.
