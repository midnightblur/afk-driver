# Adversary report — 0011-job-supervisor

Contract: `plan/0011-job-supervisor.md` at head 666f14ff. Mode: driven. Verdict: `findings`.

An earlier attempt on the same day ended `env_unreachable`: the protected-branch guard refused `git init` in a scratch folder, so no run could exist.

## Set-up

- The running system is the command line in the worktree (plan decision D-40): `afk-python scripts/afk-team.py <verb> '<json>'` and `afk-python scripts/team/supervisor.py '<json>'`. No source under `scripts/`, no test file, no diff and no review file was read.
- Every run lived under `AFK_TEAM_ROOT` = `<scratch>/adv-0011/runs`, opened with `run-open {"run":"ADV-n","session":"s1"}`. `<scratch>` is `C:/Users/mvu/AppData/Local/Temp/claude/C--Users-mvu-PersonalProjects-afk-driver-agent-teams/96c58aef-58cc-4e51-8bc9-2259fed7dd71/scratchpad`.
- Watched agents were throwaway Python sleep processes (`<scratch>/adv-0011/spawn.py`). Their agent entries were written by hand (`<scratch>/adv-0011/ent.py`, helper `mk` in `<scratch>/adv-0011/env.sh`): state `working`, `handle` = the process id as text, `started_at` = the operating system's creation time cut to the second. A headless agent's output was a hand-written `runs/<run>/logs/<agent-id>.log`. That path is the one `agent-read` names for a headless entry with no log (observed: `field log: …\runs\ADV-1\logs\w1.log cannot be read`).
- No `claude`, `codex` or herdr ran. `PATH` was not changed. `HERDR_*` and `CLAUDE*` variables were unset.
- Refusal recorded: the protected-branch guard refused one compound command that changed folder through a variable (`cd $W`): "it runs in a folder the guard cannot know". The commands then ran with the literal worktree path as the folder.
- Every probe process was killed at the end; a final listing found 0 supervisor or sleep processes. `git status` of the worktree is unchanged apart from this report.

## Findings (most severe first)

| # | Severity | Class | Promise broken | One line |
|---|---|---|---|---|
| A-1 | medium | correctness | SDD §8 "Job supervisor" (send exited; parked with the reset time from the provider); Acceptance "An exited message … is one of the signals that an agent died mid-work" (SDD §7); PRD AC-023 | The agent's own words near the end of its output turn a crash or a clean finish into `parked`, with a reset time taken from those words. |
| A-2 | low | correctness | Acceptance "the body path is empty only for exited or an unknown reset time" (SDD §3) | A reset time that names a time zone such as `(America/Toronto)` is sent as unknown: `parked` with an empty body path. |
| A-3 | low | spec | Acceptance "a second supervisor for one agent is refused at start with exit 2, naming the agent" (SDD §6 I20) | Before the contact agent writes the first supervisor's process entry, a second start answers exit 0 and a process id; that process refuses and ends at once. |

### A-1 — the agent's own text is read as a provider limit

Repro (run `ADV-9`, headless entry `q1`, model `implementation@claude`; the process ends by itself with exit code 0):

```sh
printf 'Done. Fixed the "usage limit reached" banner: it now shows "resets 3pm" in the user zone. Result: plan/result.md\n' > runs/ADV-9/logs/q1.log
P=$(afk-python spawn.py 12); mk ADV-9 q1 headless $P
afk-python scripts/afk-team.py agent-start '{"run":"ADV-9","watched_agent_id":"q1"}'
# wait for the process to end; read runs/ADV-9/inbox/q1-sup-1.json and runs/ADV-9/bodies/q1-sup-1
```

| Agent | Last lines of the log | How it ended | Message | Body |
|---|---|---|---|---|
| q1 | `Done. Fixed the "usage limit reached" banner: it now shows "resets 3pm" …` | exit 0, by itself | `parked` | `resets at 2026-10-28T19:00:00Z` |
| w6 | `working on the usage limit table in the brief, resets at 2026-10-28T10:15:00Z per doc` | killed | `parked` | `resets at 2026-10-28T10:15:00Z` |
| y5 | `tests/test_banner.py::test_text[5-hour limit reached - resets 3pm] PASSED`, `1 passed in 0.12s` | killed | `parked` | `resets at 2026-10-28T19:00:00Z` |
| y4 | `Fixed the bug where the usage limit reached banner showed the wrong time` | killed | `parked` | empty body path |
| y6 | `Claude AI usage limit reached|<epoch>`, then 3 lines of work | killed | `parked` | the epoch's time |
| y1 | the same limit line, then 50 lines of work | killed | `exited` | — |
| q2, y3 | `…the limit is reached.`; `…the rate limit resets at 2026-10-28T10:15:00Z…` | exit 0; killed | `exited` | — |

- Each body says `stopped on a provider limit` and quotes the agent's own line as `The provider said: …`.
- Expected: `exited` for each of q1, w6, y5, y4, y6. None of these lines came from the provider.
- Effect: the contact agent parks the role, or the whole run beyond the wait horizon (AC-023), instead of the "Agent dies mid-work" resume (SDD §7). A finished agent is reported as parked after it finished.
- Inferred: the supervisor matches limit words in the last few lines of any output, whatever the exit code. Unverified: which lines a real `claude -p` or `codex exec` log carries under the headless launch, so the real trigger rate is unknown. This repository itself holds such strings, so an agent working on it can print them.

### A-2 — a reset time with a named time zone is lost

Repro (run `ADV-8`, headless entries, each killed after start):

| Log line | Message | Body |
|---|---|---|
| `Claude usage limit reached. Your limit will reset at 7pm (America/Toronto).` | `parked` | empty body path |
| `Claude usage limit reached. Your limit will reset at 7pm (Asia/Tokyo).` | `parked` | empty body path |
| `5-hour limit reached ∙ resets 3pm (America/Toronto)` | `parked` | empty body path |
| `5-hour limit reached ∙ resets 3pm (Europe/Paris)` (run `ADV-7`) | `parked` | empty body path |
| `Claude usage limit reached. Your limit will reset at 7pm.` | `parked` | `2026-10-28T23:00:00Z` (local zone) |
| `You've hit your limit · resets 10am (UTC)` | `parked` | `2026-10-28T10:00:00Z` |

- Expected: the body carries the stated time in UTC, for example `2026-10-28T23:00:00Z` for 7pm America/Toronto.
- Cause, inferred: `afk-python -c "import zoneinfo; zoneinfo.ZoneInfo('America/Toronto')"` fails with `ZoneInfoNotFoundError`, and `import tzdata` fails with `ModuleNotFoundError` on this Windows host.
- Unverified: whether the current Claude Code or Codex limit text names a zone. The contact agent then parks with no date.

### A-3 — a second start in the window before the process entry answers exit 0

Repro (run `ADV-5`, live entry `z1`, one live supervisor, no process entry written yet):

```sh
afk-python scripts/afk-team.py agent-start '{"run":"ADV-5","watched_agent_id":"z1"}'
# → {"label": "ADV-5 z1 supervisor", "pid": 55772}, exit 0; 4 s later process 55772 does not exist
# run ADV-1, entry w1, one live supervisor: the second supervisor itself refuses
afk-python scripts/team/supervisor.py '{"run":"ADV-1","watched_agent_id":"w1"}'
# → {"error": true, "operation": "supervise", "reason": "agent w1 already has a job supervisor, process 53428"}, exit 2
```

- With the process entry written, agent-start answers exit 2: `agent w1 already has a job supervisor, process 1572`. That case holds.
- Expected: exit 2 naming the agent in both cases. Actual: exit 0, so the contact agent writes a process entry for a process that has ended.
- The invariant itself holds: only 1 supervisor ran per agent in every probe.
- Routing note: the contract gives the refusal at start to the team entry script, so the fix may belong to `0010-team-entry-script`.

## Promises that held (53 scenarios)

| Area | Scenarios | Result |
|---|---|---|
| Start through agent-start | 4 | `watched_agent_id` is the one field; answer is only `label` and `pid`; label = pane label + ` supervisor` (`ADV-1 builder opus max supervisor`); the supervisor keeps running after agent-start returns; the manifest is unchanged after start and after each message (4 runs, 0 process entries, every agent still `working`) |
| Start refusals | 8 | unknown id, empty id, integer id, `../` in id, extra `agent_id`, extra `role`, unknown run, second start with a process entry: exit 2 naming the field, the id or the agent |
| exited | 9 | killed agent, clean exit, process already gone at start, process id reused by another process (creation time differs), log missing, pane kind (`herdr`) with limit text in its log: `exited`, body path empty |
| Sender identity | 3 | `agent_id`, `from_role` and `generation` are the watched agent's (`reviewer-a`, generation 3 while the run is at 1); `format_version` 1; inbox only |
| Message id | 3 | `<agent-id>-sup-<n>`; a later supervisor for the same agent sends `w1-sup-2`; when the agent had already used `q4-sup-1`, the supervisor sent `q4-sup-2` |
| parked with reset time | 12 | epoch form, `resets 3pm`, `resets Oct 30, 9am`, Codex `try again in 2 hours 5 minutes`, `in 3 days 4 hours`, `at 3:15 PM`, stream JSON line, 30 MB log, invalid bytes and CRLF: body is free text with a UTC ISO 8601 time (`2026-10-28T03:02:12Z`); limit with no time, out-of-range epoch, `resets 25pm`: `parked` with empty body path |
| Only at the end | 5 | no message while the agent runs (60 s with limit text in the log) |
| Stop | 2 | agent-stop on the supervisor's process entry kills its process tree; a supervisor killed by force leaves a state file, and the next start runs |

Observations, not findings:

- A relative time (`try again in 2 hours 5 minutes`, log line stamped `01:00:00`) gave `03:07:13Z`: counted from when the supervisor read the log, 2 min 13 s after the stamp. The error is on the late side.
- A reset time in the past (epoch 1 hour ago) is sent as is.
- `agent-send` accepts a message id of the form `<agent-id>-sup-<n>` and kind `exited` from the agent itself (run `ADV-9`, agent `q3`). That is the entry script's surface; the supervisor skips an id already used.

## Not verified

- Real `claude -p` and `codex exec` limit output, and which lines the headless launch writes to the log. Every log above was written by hand.
- How often the supervisor checks: messages arrived 30 s to 60 s after the agent ended. No acceptance bullet sets a bound.
- Kinds other than headless and `herdr` (subagent, desktop tool).
- Linux and macOS: every probe ran on Windows 11.

Evidence: helper scripts and run folders under `<scratch>/adv-0011/` (`env.sh`, `spawn.py`, `ent.py`, `runs/ADV-1` … `runs/ADV-9`).

```
ADVERSARY: findings — probed=53 [crit=0 high=0 med=1 low=2] [report: docs/afk/agent-team-topology/plan/review/0011-job-supervisor-adversary.md]
In plain terms: the watcher that tells the lead agent a worker stopped works, but if the worker's last words mention a usage limit, it wrongly reports "hit a usage limit" instead of "stopped", which can pause the whole run for hours; two smaller faults lose a reset time that names a time zone and let a duplicate start look successful.
```
