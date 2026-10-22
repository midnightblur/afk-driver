# Adversary report: 0006-transport-family-and-herdr

- Cycle 3 of the adversarial gate, a fresh run with the cycle 1 brief and information diet, after the cycle 2 high finding was fixed in d01ac5a. Cycle 1's report is in git at 4ec66f9; cycle 2's report is in git at bca93a6.
- Target: the plugin's command line (plan decision D-40), in a copy of HEAD bca93a6 in a scratch folder.
- Verdict: `findings` · 127 probes · critical 0, high 0, medium 3, low 4. No critical or high finding, so the gate passes; the findings are advisory.
- Written by the referee from the adversary's returned text: the harness refused the adversary's own report-file write.

Run: 2026-10-22, Windows 11, herdr 0.9.1, against a copy of HEAD (`git archive HEAD`).
Contract: `plan/0006-transport-family-and-herdr.md` (Goal, Scope, Acceptance, Seams, Produces, Context excerpts).
Running system: the plugin command line (plan decision D-40), meaning `adapters/transport/<kind>/transport.sh` and `scripts/team/probe.py`.

How the probes ran:
- `HOME` and `USERPROFILE` pointed at an empty scratch folder. Stub `claude.bat` and `codex.bat` sat first on `PATH`; no real harness ran.
- A stub `herdr.bat`, with its state in a JSON file, drove the tab, pane, failure and time-limit cases.
- The real herdr ran only read verbs, and agent-stop on the absent pane `w5:pZZZ`. No real pane or tab was created.
- Every process the run started is closed. No test, review, investigation, log or diff was opened.

## Findings, most severe first

| Id | Severity | Class | Promise it breaks |
|---|---|---|---|
| A-1 | medium | correctness | a configuration key can force a kind, and a conflict is reported by name (SDD §8 "Machine probe"; PRD AC-030) |
| A-2 | medium | spec | agent-status 10000 ms and agent-list 10000 ms (SDD §5) |
| A-3 | medium | spec | a message to the contact agent goes to its inbox, never into its input box (PRD AC-046; ADR-0007) |
| A-4 | low | robustness | the agent-start 120000 ms budget, and cleanup after a failed start (SDD §5, §7 E1) |
| A-5 | low | robustness | exit 2 for a bad field (SDD §3) |
| A-6 | low | robustness | exit 2 for a bad field, Windows only (SDD §3) |
| A-7 | low | robustness | exit 2 for a bad field (SDD §3) |

Repros:
- A-1: a config with `schema: 1` and `transport: headless` (a scalar, not a mapping), then `AFK_CONFIG=<file> afk-python scripts/team/probe.py resolve` answers `{"kind":"subagent","source":"detected","conflict":null}`. `afk-config.py validate` on the same file exits 2 with `transport: must be a mapping`. `transport.pane-switch: banana` behaves the same way.
- A-2: a stub herdr that hangs on `agent get`, then `probe.py run multiplexer agent-status '{"handle":"w5:p104"}'` exits 4 after 16676 ms; agent-list after 13613 ms. A healthy agent-status through the probe takes 4487 ms: the probe adds 3 to 7 s (5 Python starts) before the kind starts its budget clock, and its kill limit is the budget plus 15 s. Through the kind's entry alone, agent-list took 10926 ms.
- A-3: no code in the copy writes an inbox envelope; only a comment in `herdr.py` and the reader `hooks/inbox-wait.sh` name it. With a stub herdr and `HERDR_PANE_ID=w5:p1`, `multiplexer/transport.sh agent-send '{"handle":"w5:p1","text":"envelope to contact"}'` exits 0 and types into the contact's pane with `agent prompt w5:p1`. `multiplexer/CONTRACT.md` gives the inbox write to the team entry script, which is not in this slice.
- A-4: a stub herdr that hangs on `agent start` and `pane process-info` gives exit 4 after 121421 ms. Pane `w5:p117` and tab `goal step9` stay open, and the answer names neither.
- A-5: on real herdr, `agent-status '{"handle":"--help"}'` exits 0 with `alive true`; agent-read returns herdr's help text as the screen; agent-stop answers `stopped true, pane_closed true`.
- A-6: with the run's own victim process 48100, headless `agent-status '{"pid":4295015396}'` (2^32 + 48100) answers `alive true, running` with the victim's creation time; agent-stop answers `stopped false, survivors [4295015396]`, and the victim lives on.
- A-7: headless `agent-read` with `since_marker:"²"` exits 4 (ValueError); with `log` naming a folder, exit 4 (PermissionError).

## Held

- Verbs and exit codes: all six verbs answer, unsupported verbs exit 3, every bad payload shape probed exits 2, standard input is ignored, and an unresolvable kind exits 2 naming the config file.
- Update-off switch: present on all four starts, on that launch only. No config file was written, and no `AFK_C*` variable reached a started agent.
- Headless prompt: it arrived intact on standard input.
- Headless job: a grandchild whose parent exited died with the stop, and a child's job breakaway was refused.
- Multiplexer stop: an orphaned Git Bash `sleep` was killed. A pid already gone, a repeated stop, a handle-only stop, a failed pane close and the no-tool case all gave the promised answers.
- Tab rules (stub herdr): the 2 by 2 grid, the overflow tab `<tab> 2`, never the contact tab, a tab closing with its last pane, a failed tab make giving exit 4 naming the tab, and a dialog giving exit 4 with `dialog true`.
- Probe: conflicts reported by name, the fixable setting named with its fix, absent, outside, and the fallback to subagent with its sentence when no pane tool is found. An inherited `AFK_CFG_LOADED` is dropped.

## Not verified

- A real herdr agent-start and agent-send: a pane's shell takes its `PATH` from herdr, so a real start could launch the real `claude`.
- V28, V33, V34, V35: they need live harness panes.
- The C15 setup install (AC-028, V31): `/afk:setup` is agent-run.
- The POSIX session kill (the host is Windows only), and a kill that fails.
- The identity check on a reused pid: out of the kinds' scope by contract (plan decisions D-32, D-38).
