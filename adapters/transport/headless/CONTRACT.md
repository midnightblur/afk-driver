# transport/headless — capability contract (headless runs)

The plugin starts the harness with no terminal (`claude -p`, `codex exec`).
`job.py` owns the run: on Windows it holds a job object with the
kill-on-job-close limit and no breakaway limit, joins it before it starts the
agent, and so ends every member when it closes; elsewhere it leads its own
session. The handle is the agent's process id. Entry: `transport.sh`, which runs
`headless.py`.

## Verbs

| Verb | Payload | Answers |
|---|---|---|
| `agent-start` | `harness` (`claude` \| `codex`), `prompt`, `cwd`, `log` (the output file), optional `model`, `effort`, `args` (other native options), `env` | `kind`, `handle`, `pid`, `started_at` (the process's creation time), `session_id` (empty), `log` |
| `agent-send` | — | exit 3, `unsupported`: the run takes no message after its start |
| `agent-status` | `pid`, optional `log` | `alive`, `state` (`running` \| `exited`), `since`, and `exit_code` once exited |
| `agent-read` | `log`, optional `since_marker` | `text` after the marker, `marker`, `complete` (false when the read stopped at its 1 MiB cap, or before a character a running harness has only half written) |
| `agent-stop` | optional `pid`, `force` | `stopped` true with `method`, or `stopped` false with `reason` and `survivors` (process ids) |
| `agent-list` | — | exit 3, `unsupported`: a headless run has no pane id |

Each start carries the harness's update-off switch on its own launch only
(`../launch.py`). The prompt goes to the harness on standard input, from
`<log>.prompt.txt`, never on its command line, so no shell or batch shim cuts
or expands it. `agent-stop` lists the whole process tree, then kills each
member by its id; elsewhere than Windows it then kills what is left of the
run's session, which reaches a child that moved to init. It never relies on a
shell trap. A start whose job owner reports no process in 15 s ends that owner.

## Exit codes

0 the verb ran · 2 a bad payload or field, named · 3 not a verb of this kind ·
4 `unavailable`: the harness command is not on `PATH`, or the run could not be
placed under an operating-system job. Any other failure
inside a verb also answers 4, naming the verb.

## Configuration keys read

- `transport.kind` — through the dispatcher, or the machine probe's hand-in

## Runtime

Bash, Python 3, and the harness command (`claude` or `codex`) on `PATH`.

## Documented degradation

None. A process started outside the job (for example through Windows
Management Instrumentation) is reached only by the tree kill, when it is a
descendant.
