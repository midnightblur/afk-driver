# Adversary report: 0006-transport-family-and-herdr

- Cycle 2 of the adversarial gate, a fresh run with the cycle 1 brief and information diet. Cycle 1's report (A-1 to A-9, 161 scenarios, at 52a9033) is in git history at 4ec66f9; its A-1 was remediated before this run.
- Target: the plugin's command line (plan decision D-40), in a copy of HEAD 40de689 in a scratch folder.
- Verdict: `findings` · 132 probes · critical 0, high 1, medium 2, low 3.
- Written by the referee from the adversary's returned text: the harness refused the adversary's own report-file write.

Run: 2026-10-22, Windows 11, herdr 0.9.1, against a copy of HEAD (`git archive HEAD`).
Contract: `plan/0006-transport-family-and-herdr.md` (Goal, Scope, Acceptance, Seams, Produces, Context excerpts).
Running system: the plugin command line (plan decision D-40), meaning `adapters/transport/<kind>/transport.sh` and `scripts/team/probe.py`.

How the probes ran:
- Stub `claude.cmd` and `codex.cmd` sat first on `PATH` and recorded their arguments, environment and standard input. No real harness ran.
- A stub `herdr.cmd` gave scripted answers to test the tab rules, failures and time budgets. It ran under a fake session (`HERDR_PANE_ID=w9:p1`, `HERDR_TAB_ID=w9:t1`), so the real herdr server was not touched.
- Live herdr runs used only `w5:pZZZ` (a pane that does not exist) and 2 panes that the kind's own `agent-start` made in its own tab. Both panes and the tab are closed. A process listing filtered on the scratch folder shows nothing still running.
- Kill tests used process trees this run started in a hidden console of their own.

## Findings, most severe first

| Id | Severity | Class | Promise it breaks |
|---|---|---|---|
| A-1 | high | correctness | the machine probe hands its kind to the dispatcher (SDD §8 "Machine probe"; §3 answer shapes) |
| A-2 | medium | spec | a conflict between configuration and detection is reported by name (PRD AC-030) |
| A-3 | medium | spec | a message to the contact agent goes to its inbox, never into its input box (PRD AC-046; ADR-0007) |
| A-4 | low | robustness | cleanup after a failed start (SDD §7 E1) |
| A-5 | low | spec | an unknown effort is refused (SDD §3 agent-start errors) |
| A-6 | low | robustness | the update-off switch on each launch (SDD §9b) |

### A-1 · high · correctness: the probe's hand-in corrupts every backslash in a payload on Windows

Promise broken: "The machine probe resolves the best available kind and hands it to the dispatcher as if configured" (SDD §8 row "Machine probe"), and "Every verb answers in the inherited shapes" (SDD §3).

The same payload works at the kind's own entry but fails or changes through `probe.py run`:
- A Windows path in `cwd` or `log` gives exit 2.
- Text with a backslash followed by `n` or `t` is changed silently, with exit 0.

Repro 1. `r1.log` holds `hello`; `pl_back.json` holds `{"log": "C:\\Users\\…\\work\\r1.log"}`.
```
bash adapters/transport/headless/transport.sh agent-read "$(cat pl_back.json)"
  -> exit 0 {"complete": true, "marker": "7", "text": "hello\r\n"}
afk-python scripts/team/probe.py run headless agent-read "$(cat pl_back.json)"
  -> exit 2 {"error": true, "operation": "agent-read", "reason": "the payload is not JSON: Invalid \\escape: line 1 column 12 (char 11)"}
same path with forward slashes, through probe.py run -> exit 0, text "hello\r\n"
```

Repro 2, the silent change. Stub `claude` is on `PATH`; `cwd` and `log` use forward slashes.
```
afk-python scripts/team/probe.py run headless agent-start '{"harness":"claude","prompt":"read C:\\new\\task.md then reply","cwd":"C:/…/work","log":"C:/…/work/pr-run.log"}'
  -> exit 0; the started agent's standard input reads 'read C:' + LF + 'ew' + TAB + 'ask.md then reply'
same payload at bash adapters/transport/headless/transport.sh agent-start
  -> standard input reads 'read C:\new\task.md then reply'
```

Likely cause (inferred, not traced in the source): `dispatch` passes `json.dumps(payload)` to `bash.exe` as a Windows command-line argument (`scripts/team/probe.py:136`), and Git Bash's argument parser turns `\\` into `\`. A call from one bash process to another keeps the argument intact.

### A-2 · medium · spec: `pane-switch: pane` with no pane tool resolves to the subagent kind and reports no conflict

Promise broken: "When configuration and detection disagree, the probe reports the conflict by name" (PRD AC-030). `CONFIG.md:137` says `pane` means role agents run as pane agents.

Repro. `AFK_CONFIG` points at `transport:\n  pane-switch: pane`, and there is no `herdr` on `PATH`.
```
afk-python scripts/team/probe.py resolve
  -> exit 0 {"conflict": null, "kind": "subagent", "source": "detected", "says": "no pane transport is usable in this session, so role agents run as subagents", …}
```
Expected: a named conflict. The answer does not include the switch value, so a caller cannot detect the disagreement itself.

The probe does name its other conflicts: multiplexer forced but not usable; `pane-switch: subagent` against a forced multiplexer; desktop forced; an unknown kind; headless forced with no harness on `PATH`.

### A-3 · medium · spec: nothing in this slice writes the contact agent's inbox, and the multiplexer kind types into any pane it is given, the contact's included

Promise broken: "a message to the contact agent is written as an envelope file into its inbox under a temporary name, then renamed, and never goes into its input box" (PRD AC-046, ADR-0007).

Repro, with stub herdr and the session's own pane set to `w9:p1`:
```
bash adapters/transport/multiplexer/transport.sh agent-send '{"handle":"w9:p1","text":"envelope-1"}'
  -> exit 0 {"delivered": true, "way": "agent-prompt", …}
  herdr call made: agent prompt w9:p1 envelope-1
```

A search of `adapters/` and `scripts/team/` for `inbox` finds only the detection field `contact_delivery: "inbox"` (`herdr.py:45`). `multiplexer/CONTRACT.md` assigns the inbox write to the team entry script, which is outside this slice's Scope. So the temporary-name-then-rename write could not be tested.

Unverified: whether the plan moves this half of the bullet to the entry-script subtask. If it does, the bullet's owner needs to change. If not, this slice does not meet the bullet.

### A-4 · low · robustness: an `agent-start` that runs out of budget leaves its new pane and tab open and does not name them

Promise broken: SDD §7 E1 cleanup after a failed start. The answer gives the caller no pane id to close.

Repro. Stub herdr makes pane `w9:p50`; `agent start` and `agent get` never answer.
```
bash adapters/transport/multiplexer/transport.sh agent-start '{"harness":"claude","name":"G-a","label":"G a","cwd":"C:\\","tab":"G-s"}'
  -> exit 4 after 120.9 s, reason "herdr could not start the agent: timeout: `herdr agent start` took over 89 s"
  herdr calls: tab list, tab create, pane rename, agent start, agent get
  No pane process-info, pane close or tab close follows.
```

The `agent start` call can wait 89 s (the herdr timeout plus 10 s). That cuts the planned 40 s reserve to 29 s, and the `agent get` check after it can use all of that. When `agent get` answers promptly, cleanup works (stub cases T6 and T7 closed the pane and the tab).

### A-5 · low · spec: an unknown effort still starts the agent

Promise broken: SDD §3 agent-start errors ("exit 2 … naming the field for an unknown effort", S-233) and the PRD Testing Decisions row "Transport adapter family".

Repro: headless `agent-start` with `"effort":"ultra"` gives exit 0, and the stub saw `['-p','--model','m1','--effort','ultra']`. The multiplexer kind also gives exit 0 and calls `agent start … -- --effort ultra …`.

Unverified: whether the team entry script owns this check rather than the kind. The adversary could not read plan decisions other than D-40.

### A-6 · low · robustness: the payload's `env` field can turn the update-off switch back on

Promise broken: "Each started agent carries its harness's update-off switch on its own launch only" (SDD §9b).

Repro:
- headless `agent-start` with `"env":{"DISABLE_AUTOUPDATER":"0"}` gives exit 0, and the stub's environment has `DISABLE_AUTOUPDATER=0`.
- The multiplexer kind calls `tab create … --env DISABLE_AUTOUPDATER=0`.

The payload's `env` is merged after the switch (`headless.py:209`, `herdr.py:131`). Inferred: a caller has to set this on purpose, so the risk is low.

## Promises that held

| Promise | Evidence |
|---|---|
| Exit codes on all 3 kinds | Bad JSON, a JSON array, an extra argument, a payload sent only on standard input, and no verb each give exit 2 with `error`, `operation` and `reason`. An unknown verb gives exit 3. A missing or wrong-typed field gives exit 2 naming the field (36 calls). |
| Kind that cannot be resolved | Exit 2, with a message on stderr naming `.afk/config.yaml` (tried a `desktop` kind, an empty `transport:` section, and `kind: bogus`). |
| Time budgets | With herdr hanging: agent-status took 10.5 s, agent-list 10.8 s, agent-read 30.8 s, agent-send 30.6 s, agent-stop 30.8 s and agent-start 120.9 s. agent-send and agent-start each made 1 herdr call and no retry. |
| agent-stop on a tree whose middle process ended | The root, the child and the orphan were all killed (multiplexer kind, also with `force`). |
| agent-stop on a process that is already gone | Answers `stopped` true with method `not running`. |
| agent-stop with only a pane handle | A pane that closes gives `stopped` true. A close that fails gives `stopped` false, `pane_closed` false and names the pane. A pane that is already gone (live `w5:pZZZ`) counts as closed. |
| Identity check when a process id is reused | The kind killed an unrelated process of this run when given its id. This matches the contract: the kind takes no start time, and the entry script owns the identity check (Acceptance bullet 2, D-32, D-38). |
| Headless agent under an operating-system job | A grandchild that outlived its parent died when the agent exited. After agent-stop, the orphan and the job owner were already gone when the stop answered. |
| Update-off switch | Headless claude got `DISABLE_AUTOUPDATER=1`. Headless codex got `exec -c check_for_update_on_startup=false`. In a live herdr pane, stub claude saw `DISABLE_AUTOUPDATER=1` and stub codex's arguments began with `-c check_for_update_on_startup=false`. The scratch home folder stayed empty, so no settings file was written. |
| Headless prompt goes on standard input | Quotes, `%PATH%` and `&` arrived unchanged. |
| Probe kind resolution | Covered: a forced kind, a forced kind that is not usable, and no pane tool. The last resolves to subagent and the answer says so. Also: an integration that is not current reports `fixable`, with the setting and its fix named (stub and real herdr). Also: herdr installed but the session not in a pane reports `outside`. |
| Probe runs the verb in its own shell | A repository forced to `subagent` still ran `headless` when the probe handed that kind in. The started agent had no `AFK_CFG_LOADED`, even when the caller had set it. `AFK_CONFIG` reached the agent only when the caller's own environment set it. |
| Tab rules (stub herdr) | The contact's tab is never split, even when it has the step's name. A full tab leads to `<tab> 2`; with tabs 1 and 3 full the next is `<tab> 4`. The 3rd pane splits the 1st downward. If the tab list or tab creation fails: exit 4 naming the tab, and no pane is made. A blocking dialog gives exit 4 with `dialog` true; its pane and tab are closed. |
| Tab rules (live herdr) | The 2nd agent split into the same step tab. Stopping the 1st agent left the tab open; stopping the 2nd closed it. Each agent's whole process tree was gone. |
| Live herdr answer formats | They match what `herdr.py` reads (`root_pane.pane_id`, `tab.tab_id`, `pane_not_found`, `agent_not_found`). |

## Not verified

- The setup row C15 behaviour (PRD AC-028, SDD §13 V31). It needs a `/afk:setup` run, which is not a command-line verb of this slice.
- SDD §13 V28, V33, V34 and V35, the Codex full-access probe row, message order to a busy pane, and delivery into a pane holding unsent text. These need a real `claude` or `codex`, which the brief forbids.
- A tool that cannot make tabs. No such tool exists in this slice.
- The POSIX session kill. This host is Windows only.
- Slow behaviour of Git's `ps` or the console read during agent-stop. Not simulated.

## Deviations from the brief

- One live `agent-send` went to `w5:pZZZ`, a pane that does not exist. herdr answered `pane_not_found`, so nothing was delivered, but agent-send is not on the brief's list of live verbs.
- Before the live start, the adversary made its own tab `adv-preflight` and ran `where.exe claude` in it with `herdr pane run`. This proved the stub resolves before the real `claude`. The tab is closed.

ADVERSARY: findings — probed=132 crit=0 high=1 med=2 low=3 [report: docs/afk/agent-team-topology/plan/review/0006-transport-family-and-herdr-adversary.md]
In plain terms: the agent start, message, stop and tab code mostly behaved as promised, but on Windows the machine probe garbles or rejects any Windows file path or backslash text in a request, and the probe hides one setting conflict; both should be fixed before this ships.
