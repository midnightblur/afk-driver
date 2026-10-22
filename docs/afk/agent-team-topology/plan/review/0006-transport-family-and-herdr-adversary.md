# Adversary report: 0006-transport-family-and-herdr

- Target: the plugin's command line (plan decision D-40), in a copy of HEAD 52a9033 in a scratch folder.
- Surfaces: `adapters/transport/{subagent,headless,multiplexer}/transport.sh`, `scripts/team/probe.py`, `ADAPTERS.md` "transport", `skills/afk/setup/MANIFEST.md` row C15.
- Environment: Windows 11, Git Bash, herdr 0.9.1, this session inside herdr pane `w5:p1`. `HOME` and `USERPROFILE` pointed at a scratch folder. Stub `claude` and `codex` scripts recorded their arguments, environment and standard input. A fake `herdr` (a script that logs its calls and answers from a scenario file) served the tab, dialog, resume and failure cases. The real herdr served the live cases, only on panes this run created.
- Verdict: `findings`. 161 scenarios, 9 findings: 1 high, 3 medium, 5 low.
- Written by the referee from the adversary's returned text: the harness refused the adversary's own report-file write.

## Findings (most severe first)

| Id | Severity | Class | Promise it breaks |
|---|---|---|---|
| A-1 | high | robustness | agent-stop kills the agent's whole process tree (Acceptance; SDD §7 E2; herdr.md trap row "the tree is listed before the kill") |
| A-2 | medium | spec | a message to the contact agent goes to its inbox and never into its input box (Acceptance; PRD AC-046; ADR-0007) |
| A-3 | medium | robustness | agent-stop kills the whole tree, then closes the pane (Acceptance; SDD §7 E2, E3) |
| A-4 | medium | robustness | herdr.md trap row: control commands from outside a herdr pane act on a session the caller does not own |
| A-5 | low | correctness | herdr.md "Detection (herdr)": usable needs the integration current for each harness the run starts |
| A-6 | low | correctness | agents of one pattern step share tabs (Acceptance; PRD AC-053) |
| A-7 | low | robustness | exit 2 for a bad field (Acceptance; SDD §3 answer shapes) |
| A-8 | low | spec | agent-status 10000 ms, agent-list 10000 ms, agent-read 30000 ms (Acceptance; SDD §5) |
| A-9 | low | correctness | agent-start answers the agent process's creation time as started-at (SDD §3 agent-start) |

### A-1 (orphaned child survives agent-stop) — high, robustness
A descendant whose parent ended before the stop is not in the listed tree. agent-stop answers `stopped: true` with no survivors, and the descendant keeps running. A shell call that starts a background server and then exits makes this tree. The headless kind is not affected: its operating-system job ends the orphan.

Repro 1, a tree of Windows processes (processes this run started): root python, then a middle python, then a grandchild python running sleep 600; the middle one exits at once.
```bash
python tree.py "$REC" &          # writes k_root.pid, k_mid.pid, k_grand.pid
bash adapters/transport/multiplexer/transport.sh agent-stop "{\"pid\":$(cat $REC/k_root.pid)}"
tasklist //FI "PID eq $(cat $REC/k_grand.pid)"
```
Actual: `{"method": "killed the process tree", "stopped": true}`, exit 0. Grandchild 44012 still runs. Expected: the grandchild is killed, or `stopped: false` with it in `survivors`.

Repro 2, a Git Bash tree:
```bash
bash -c "echo \$\$ > b_root; bash -c 'sleep 611 & echo \$! > b_sleep'; exec sleep 612" &
WINPID=$(ps -e | awk -v a=$(cat b_root) '$1==a{print $4}')
bash adapters/transport/multiplexer/transport.sh agent-stop "{\"pid\":$WINPID}"
ps -e | grep sleep
```
Actual: `stopped: true`, `killed the process tree`. `sleep 611` still runs; its MSYS parent is 1 and its process group is the root's. Expected: no process of the root's tree is left (SDD §13 V28).

### A-2 (no inbox path; agent-send types into the contact agent's pane) — medium, spec
No file in this slice writes the contact agent's inbox. A search for `inbox` in `adapters/transport/**` and `scripts/team/*.py` found 0 writers. The multiplexer `CONTRACT.md` says the team entry script writes it. The kind itself has no guard: agent-send with the contact agent's own pane id types into its input box.

Repro (fake herdr, so the real pane `w5:p1` was not touched), with `HERDR_PANE_ID=w5:p1`:
`bash adapters/transport/multiplexer/transport.sh agent-send '{"handle":"w5:p1","text":"envelope for the contact"}'`

Actual: `{"delivered": true, "way": "agent-prompt"}`, exit 0. The fake herdr logged `["agent","prompt","w5:p1","envelope for the contact"]`, and no file was written. Expected by this slice's Acceptance bullet: an envelope file in the inbox under a temporary name, then renamed, with nothing typed. If the team entry script owns that write (ADR-0007), the kind still answers success for a delivery the PRD forbids.

### A-3 (agent-stop with only a handle kills nothing) — medium, robustness
With a handle and no process id, agent-stop closes the pane and answers `stopped: true`, `method: "pane close"`. It does not kill the process tree, although the same kind looks up the pane's process id for its own cleanup after a failed start. A child outside the pane's console outlives the close; herdr.md names this trap for Codex.

Repro (live herdr, tab `w5:t15` made by this run, stub agent with detached child 30884):
`bash adapters/transport/multiplexer/transport.sh agent-stop '{"handle":"w5:p2C"}'`, then `tasklist //FI "PID eq 30884"`.

Actual: `{"method": "pane close", "pane_closed": true, "pane_id": "w5:p2C", "stopped": true}`, and child 30884 still runs. Expected: the tree is killed before the close, or `stopped: false` with the survivor named.

### A-4 (headless run inherits the caller's session identity) — medium, robustness
A headless run inherits the whole caller environment. The stub recorded `HERDR_ENV=1`, `HERDR_PANE_ID=w5:p1`, `HERDR_TAB_ID=w5:t1`, `CLAUDECODE=1`, the caller's `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_MESSAGING_SOCKET` and `CLAUDE_CODE_MESSAGING_TOKEN`. The run is not in a herdr pane, but it carries the contact agent's pane id.

Repro, from a herdr pane: `bash adapters/transport/headless/transport.sh agent-start '{"harness":"claude","prompt":"x","cwd":"<work>","log":"<work>/h1.log"}'`, then read the stub's record. Expected: no pane or session identity of the caller in the run's environment.

Inferred consequence, not run: the installed herdr hook for Claude Code (`~/.claude/hooks/herdr-agent-state.ps1`) reports a `SessionStart` session id for `$env:HERDR_PANE_ID`. A real headless `claude` would then report its session as the session of the contact agent's pane, and a later resume of that pane would pick the wrong session. unverified: no real `claude` was started.

### A-5 (start goes on without the harness's herdr integration) — low, correctness
The kind checks herdr with an empty harness list, so it never checks the integration of the harness it starts. For the same state, `probe.py resolve --harness codex` answers `fixable`.

Repro (fake herdr, integration status `codex: not installed`): `agent-start '{"harness":"codex","name":"n9","label":"l9","cwd":"<work>","tab":"g s"}'`. Actual: exit 0, `session_id: ""`. Expected: exit 4 naming the setting `herdr integration for codex`. With no session id, a later resume has nothing to resume.

### A-6 (a step name that ends in a number joins another step's tab) — low, correctness
The kind reads a tab label `<tab> <n>` as the n-th tab of step `<tab>`. A request for tab `g step` splits into tab `g step 2`, which belongs to step `step 2`, when that tab has room.

Repro (fake herdr, tabs `[{"tab_id":"w5:t7","label":"g step 2","pane_count":1}]`): `agent-start` with `"tab":"g step"`. Actual: `pane split w5:p70 --direction right`. Expected: a new tab `g step`.

### A-7 (a handle that looks like an option reads as success) — low, robustness
herdr reads a handle that starts with `--` as an option and prints its help with exit 0. The kind then takes the help text as its answer.

| Call | Actual | Expected |
|---|---|---|
| `agent-send '{"handle":"--help","text":"hello"}'` | `delivered: true`, exit 0 | exit 2 naming `handle`, or exit 4 |
| `agent-status '{"handle":"--help"}'` | `alive: true`, `state: "unknown"` | not alive, or exit 2 |
| `agent-stop '{"handle":"--help"}'` | `stopped: true`, `pane_closed: true` | exit 2 naming `handle` |
| `agent-read '{"handle":"--help"}'` | herdr help text, `complete: true` | exit 2 |

Envelope text that starts with `-` or `--` arrived literally: 6 texts, live herdr. Only the handle is affected.

### A-8 (wall time passes the budget by about half a second) — low, spec
The time budget starts only after the interpreter loads, so the caller waits longer than the budget. Measured with a fake herdr call that never answers:

| Verb | Budget | Wall time | Answer |
|---|---|---|---|
| agent-status | 10000 ms | 10607 ms | exit 4, `took over 10 s` |
| agent-list | 10000 ms | 10508 ms | exit 4 |
| agent-read | 30000 ms | 30546 ms | exit 4 |
| agent-send | 30000 ms | 30567 ms | exit 4 |

A caller that enforces the exact budget stops the verb before its answer arrives.

### A-9 (start succeeds with no process id) — low, correctness
When `pane process-info` lists no foreground process and no shell id, agent-start answers exit 0 with `pid: null` and a `started_at` taken from the clock, not from the operating system. A later stop then has no process id, and an identity check against that time cannot pass.

Repro (fake herdr, empty `process_info`): `agent-start '{"harness":"claude","name":"g-dev-opus-high-1","label":"g dev opus high","cwd":"<work>","tab":"g step1","prompt":"read charter"}'`. Actual: `{"pid": null, "started_at": "2026-10-22T00:07:01Z", ...}`, exit 0. Expected: exit 4 naming the missing process, or the agent process's creation time.

## Scenarios that held

| Area | Scenarios | Result |
|---|---|---|
| Input shapes, 3 kinds | no verb, missing payload, bad JSON, array, null, extra argument, unknown verb, wrong-typed `pid`/`force`/`prompt`/`args`/`env`, unknown harness, standard input given with and without a payload | exit 2 with `error`, `operation` and a `reason` naming the field; unknown verb exit 3; standard input never read |
| subagent kind | all 6 verbs | exit 3 `unsupported` with a reason |
| headless start | claude and codex stubs; prompt with `%PATH%`, `&`, `^`, quotes, non-ASCII text and line breaks | prompt arrives byte-exact on standard input; codex gets `-c check_for_update_on_startup=false`; claude gets `DISABLE_AUTOUPDATER=1`; no file under the scratch `HOME` names either switch |
| headless job | child that outlives its parent; root with an orphaned grandchild; `force`; pid already gone; repeat stop | orphans end with the job; `stopped: true`; repeat stop answers `not running` |
| headless status and read | exited run, marker mid-text, marker past the end, bad marker, missing log | answers and exit codes as `CONTRACT.md` states |
| multiplexer, live herdr | start in a new tab with stub claude; status; read with a marker; list by prefix; 4 sends during a 6 s busy turn; stop with pid and handle; repeat stop | tab made, and closed with its last pane; messages arrive in send order; no process left |
| multiplexer, fake herdr | contact tab never used, also when it carries the step's label; full tabs lead to `<tab> 3`; grid splits right, down, down; failed tab make and failed split answer exit 4 naming the tab; a dialog answers `dialog: true` and closes the pane; a Codex resume uses `pane run`, then `agent rename`; a failed pane close answers `pane_closed: false` naming the pane | as the recipe states |
| probe resolve | no config; forced subagent, headless, multiplexer, desktop or unknown kind; pane switch alone and against a forced pane kind; herdr absent, outside a pane, server down, integration missing; headless forced with no harness; unreadable config | the kind, or a conflict by name, as Acceptance states; with no pane tool it resolves `subagent` and says so |
| probe run | caller exports `AFK_CFG_LOADED=1` | the started agent's environment has no `AFK_CFG_LOADED` and no `AFK_CONFIG`; the caller's shell is unchanged; an unknown kind answers exit 2 naming `.afk/config.yaml` |

## Not probed

- unverified: the setup install path (PRD AC-028, SDD §13 V31). An agent runs /afk:setup from `SKILL.md`, and no script drives row C15, so no installer stub run was possible. The C15 text names no harness, keeps "No skill invokes it", and prints a removal line.
- unverified: SDD §13 V28, V33, V34 and V35 on real harnesses. The brief forbade a real `claude` or `codex` process, and stubs prove only the transport side.
- unverified: envelope text with line breaks on a real harness. The stub's console input received `line1line2` for `line1\nline2`; a real terminal interface may read it as a paste.
- unverified: a pid reused by an unrelated process. The kinds kill whatever pid they get. Acceptance (plan D-32, D-38) puts the identity check in the team entry script, which is outside this slice.
- unverified: a tool that cannot make tabs (PRD AC-054). herdr is the only tool, and it makes tabs.

## Cleanup

Every tab, pane and process the adversary created is closed or killed. `herdr tab list --workspace w5` showed only `Agents`.

ADVERSARY: findings — probed=161 crit=0 high=1 med=3 low=5 [report: docs/afk/agent-team-topology/plan/review/0006-transport-family-and-herdr-adversary.md]
In plain terms: the part that starts and stops helper agents mostly works, but stopping an agent can leave its background processes running while it reports them stopped, and a message meant for the main agent would be typed into its input box, so these two need fixing before shipping.
