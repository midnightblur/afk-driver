## Goal
Make the team entry script runnable as the bare command afk-team under the allow rule Bash(afk-team *). /afk:setup's Python runtime step writes the afk-team launcher into afk-bin, beside afk-python, and its check reports a missing or stale launcher. The rule constant and its PROVIDERS.md rows change to Bash(afk-team *), and the spawn permission check confirms 3 things: the rule is in the user's settings; afk-team on PATH is the afk-bin launcher; the launcher names the running plugin folder. The setup register's offer prints the new rule, and the plugin path convention gains its one stated exception. Live rows in providers/CONFORMANCE.md prove the rule in default and auto mode, a Codex pane on Windows, and setup's launcher write in auto mode. The slice ends at the launcher, the rule and the check; the six verbs themselves are 0010-team-entry-script.

## Complexity
complex

## Design refs
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — rows "Run the team entry script", "Write the afk-team launcher" and "Write repository configuration"
- SDD: SDD.md#§7 L6 — Process & Coordination — effect E13 (packet HL5-7's E9) in the effects, idempotency, retry and failure tables
- SDD: SDD.md#§8 L7 — Module Decomposition — row "Spawn permission check" binds the 3 checks and the refusal
- SDD: SDD.md#§9 L8 — Tactical Patterns — row "Spawns under Claude Code auto mode"
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows "Claude Code plugin bin/ folder on the Bash PATH" (implement) and "Claude Code auto-mode classifier" (use)
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "Setup register `MANIFEST`: the spawn allow-rule offer" (C19), "Python runtime install and check (python_runtime.py: install, check, `place_entry`, afk-bin)" and "Plugin path convention (AGENTS.md, GLOSSARY.md "Main checkout")"
- SDD: SDD.md#§13 Open Questions — Q11, Q22, Q55, Q56; V36
- ADR: adr/design/0017-allow-rule-names-the-afk-team-command.md — the rule names the afk-team command; setup writes the launcher into afk-bin; the run check proves 3 things

## Scope
- hooks/lib/providers/claude.sh        # the rule constant becomes Bash(afk-team *)
- PROVIDERS.md                          # "Spawn allow rule" rows (:174-189)
- scripts/team/permission.py            # INVOCATION (:28), ENTRY_NAME (:29, :100) and the 3 checks
- scripts/tests/test_team_permission.py # :75 split()[2], :270-:275, :285, :304/:306, start-only test :212-219
- scripts/team/entry.py                 # :237 builds the prompt from INVOCATION
- scripts/tests/test_team_entry.py      # :368 asserts the old prompt text
- scripts/afk-team.py                   # :4 docstring shows the old command
- .claude/wiring-ious.md                # :35 IOU needs AFK_PLUGIN_ROOT in the contact agent's shell
- skills/afk/setup/scripts/python_runtime.py   # install writes the launcher; check reports it; docstrings :20-21, :266, :272
- scripts/tests/test_python_runtime_setup.py   # fixtures :200-204, :442-443, :543-547; check's afk-bin probe :500
- scripts/tests/test_afk_python_entry.py       # :72 asserts every afk-bin entry starts with afk-python
- skills/afk/setup/MANIFEST.md          # H15 offer text (C19) and notes :403-404 ("survives plugin updates": now true of the rule, not the launcher; D-135 supersedes D-75); P1 Probe and Fix :684-694, :699-704; removal note :727-730
- skills/afk/setup/AUDIT.md             # :142-149 check fail kinds
- README.md                             # :350 "exposed only as the `afk-python` command"
- AGENTS.md                             # 'Plugin paths pin to the installed plugin root' exception
- GLOSSARY.md                           # 'Main checkout' exception
- providers/CONFORMANCE.md              # live rows

## Seams
- implement: §9b row "Claude Code plugin bin/ folder on the Bash PATH" via §14 row "Python runtime install and check (python_runtime.py: install, check, `place_entry`, afk-bin)" — the launcher goes into afk-bin, never the plugin's bin/ folder (INV-085)
- implement: §14 row "Plugin path convention (AGENTS.md, GLOSSARY.md "Main checkout")" — one stated exception, the bare command afk-team (INV-086)
- use: §9b row "Claude Code auto-mode classifier" via §14 row "Setup register `MANIFEST`: the spawn allow-rule offer" — the rule constant and check 0009 built change to Bash(afk-team *) and 3 checks (INV-068)

## Acceptance
- [ ] Implements the public interface in SDD §8 row "Spawn permission check" unmodified: before a run's first transport command it confirms 3 things: the rule Bash(afk-team *) is in the user's settings; afk-team on PATH is the launcher in afk-bin; the launcher names the plugin folder that is running. On a miss it refuses, names the rule or /afk:setup, and nothing starts. Claude Code only; other harnesses pass (SDD §8 row "Spawn permission check")
- [ ] The one rule constant in hooks/lib/providers/claude.sh is Bash(afk-team *), and the PROVIDERS.md "Spawn allow rule" rows say so; scripts/team/permission.py's INVOCATION is afk-team, so scripts/team/entry.py:237 reads the new form unchanged (SDD §5 row "Run the team entry script")
- [ ] A joined command (afk-team ... && other) whose other part no rule covers is not treated as covered: the harness checks each part on its own (SDD §5 row "Run the team entry script")
- [ ] install writes the afk-team launcher into afk-bin: afk-team (a shell script for Bash) and, on Windows, afk-team.cmd. Each holds one line that runs the team script of the plugin folder that ran setup (SDD §7 E13)
- [ ] The launcher is written in the Python runtime step after the environment sync and after afk-python is placed, every time, since a sync can rebuild afk-bin (SDD §7 E13)
- [ ] The write goes to a staged file, then moves into place in one step, and happens only when the bytes differ; a repeat run changes nothing (SDD §7 E13)
- [ ] check also reports a launcher that is missing or names another plugin folder; an old runtime with no launcher reads as 'launcher missing'. afk-python itself, its path and every existing caller are unchanged (SDD §14 row "Python runtime install and check (python_runtime.py: install, check, `place_entry`, afk-bin)")
- [ ] The afk-team launcher takes its own layout key: the key `launcher` means afk-python (setup_secrets.py:45, stamp :352) and keeps that meaning (SDD §14 row "Python runtime install and check (python_runtime.py: install, check, `place_entry`, afk-bin)")
- [ ] scripts/tests/test_afk_python_entry.py:72 and the test_python_runtime_setup.py fixtures (:200-204, :442-443, :543-547) and check's afk-bin probe (:500) follow the new afk-bin contents; the docstrings python_runtime.py:20-21 ("afk-bin holds nothing else"), :266 and :272 state the launcher (SDD §14 row "Python runtime install and check (python_runtime.py: install, check, `place_entry`, afk-bin)")
- [ ] A Python-pin rebuild that wipes afk-bin and then fails the sync leaves both afk-python and afk-team missing until setup runs again, and the spawn permission check then refuses, naming /afk:setup (SDD §7 failure matrix row E13)
- [ ] MANIFEST.md P1 Probe and Fix (:684-694, :699-704) name the launcher; the removal note (:727-730) deletes the afk data folder, which removes afk-python and the launcher together; README.md:350 and skills/afk/setup/AUDIT.md:142-149 name afk-team beside afk-python (SDD §14 row "Python runtime install and check (python_runtime.py: install, check, `place_entry`, afk-bin)")
- [ ] The H15 offer (C19) prints Bash(afk-team *) instead of the full-path rule. Setup still prints it, waits for the human, then confirms it is present. It never writes a settings file. Skipped with no human present (SDD §14 row "Setup register `MANIFEST`: the spawn allow-rule offer")
- [ ] AGENTS.md 'Plugin paths pin to the installed plugin root' and GLOSSARY.md 'Main checkout' state one exception: the team script is run as the bare command afk-team; every other plugin file is still named by ${AFK_PLUGIN_ROOT}/... (SDD §14 row "Plugin path convention (AGENTS.md, GLOSSARY.md "Main checkout")")
- [ ] Every site that names the old invocation follows the new one in the same change: test_team_entry.py:368 (the prompt entry.py:237 builds), scripts/afk-team.py:4, the .claude/wiring-ious.md:35 IOU, the MANIFEST.md H15 notes :403-404, and ENTRY_NAME (permission.py:29, :100), so the start-only test reads `stale`, not `missing`, for an old rule (SDD §14 row "Plugin path convention (AGENTS.md, GLOSSARY.md "Main checkout")")
- [ ] Check 3 compares the folder the launcher names with the running plugin root, and a test proves a launcher that names an older plugin folder is refused, naming /afk:setup (SDD §8 row "Spawn permission check")
- [ ] No agent writes the launcher during a team run; only /afk:setup, in a setup run the human starts, writes it (SDD §5 row "Write the afk-team launcher")
- [ ] Live row in providers/CONFORMANCE.md: a Claude pane in default mode and in auto mode, with the rule in its settings, runs `afk-team agent-list '{}'` with no prompt (SDD §9b row "Claude Code auto-mode classifier")
- [ ] Live row in providers/CONFORMANCE.md: a Codex pane on Windows runs afk-team through afk-team.cmd (SDD §13 Q56)
- [ ] Live row in providers/CONFORMANCE.md: /afk:setup in auto mode writes the launcher, or the auto-mode refusal is recorded (SDD §13 Q55)
- [ ] Conforms to ADR-0017 — the rule names the afk-team command; setup writes the launcher into afk-bin; the run check proves 3 things (ADR-0017)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §8 row "Spawn permission check")
- [ ] The seam-test asserts on the real PATH: afk-team resolves from afk-bin, not from the plugin's bin/ folder (SDD §9b row "Claude Code plugin bin/ folder on the Bash PATH")

## Produces
- hooks/lib/providers/claude.sh#Bash(afk-team *) — the one rule constant setup prints and the check reads
- scripts/team/permission.py#def check_afk_team_launcher( — afk-team on PATH is the afk-bin launcher and names the running plugin folder; else a refusal naming /afk:setup
- skills/afk/setup/scripts/python_runtime.py#def place_team_launcher( — writes afk-team (and afk-team.cmd on Windows) into afk-bin, staged, only when the bytes differ
- AGENTS.md#bare command afk-team — the one stated exception to the plugin path convention
- GLOSSARY.md#bare command afk-team — the same exception under "Main checkout"
- providers/CONFORMANCE.md#afk-team launcher probes — the live rows for the rule, the Codex pane on Windows and setup in auto mode

## Consumes
- 0009-spawn-permission-check scripts/team/permission.py#def check_spawn_permission( — the check this slice extends with the 2 launcher checks
- 0009-spawn-permission-check hooks/lib/providers/claude.sh#AFK_SPAWN_ALLOW_RULE — the rule constant this slice changes

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash -n hooks/lib/providers/claude.sh && afk-python -m py_compile scripts/team/permission.py skills/afk/setup/scripts/python_runtime.py && grep -n 'Bash(afk-team \*)' hooks/lib/providers/claude.sh && grep -n 'def check_afk_team_launcher(' scripts/team/permission.py && grep -n 'def place_team_launcher(' skills/afk/setup/scripts/python_runtime.py && grep -n 'bare command afk-team' AGENTS.md GLOSSARY.md && grep -n 'afk-team launcher probes' providers/CONFORMANCE.md` | code parses; the Produces anchors exist |
| static | `afk-python -m pytest scripts/tests/test_native_contract_events.py scripts/tests/test_set_instruction_files.py -q` | checks A and K pass with the changed constant and offer; set_instruction_files.py unchanged |
| unit | `afk-python -m pytest scripts/tests/test_team_permission.py -q`, cases: settings with Bash(afk-team *) and a matching afk-bin launcher give ok; no rule gives a refusal carrying the rule text; an afk-team earlier on PATH outside afk-bin, a missing launcher, or a launcher naming another plugin folder gives a refusal naming /afk:setup; a non-Claude harness passes | the 3 checks; seam-test for the row "Claude Code auto-mode classifier" |
| unit | `afk-python -m pytest scripts/tests/test_python_runtime_setup.py scripts/tests/test_afk_python_entry.py -q`, cases: install writes afk-team (and afk-team.cmd on Windows) after the sync and after afk-python; a repeat install with the same bytes leaves the file untouched; the write is staged then moved; check reports 'launcher missing' and a launcher naming another plugin folder; a Python-pin rebuild that wipes afk-bin and then fails the sync leaves both commands missing; every afk-bin entry is afk-python or afk-team | E13; the Python runtime §14 row; seam-test for the row "Claude Code plugin bin/ folder on the Bash PATH" |
| integration | Environment-gated on Claude Code and herdr: a Claude pane in default mode and in auto mode, with the rule in its settings, runs `afk-team agent-list '{}'` with no prompt; recorded under "afk-team launcher probes" in providers/CONFORMANCE.md | the rule decides first; seam-test for the rows "Claude Code auto-mode classifier" and "Claude Code plugin bin/ folder on the Bash PATH" |
| integration | Environment-gated on Codex CLI and herdr on Windows: a Codex pane runs `afk-team agent-list '{}'` through afk-team.cmd; recorded in providers/CONFORMANCE.md | Q56 |
| integration | Environment-gated on Claude Code in auto mode: /afk:setup writes the launcher, or the refusal is recorded; recorded in providers/CONFORMANCE.md | Q55 |

## Context excerpts
> (packet HL3-4, signed R-47, row 1) | Run the team entry script (all six commands: agent-start, agent-send, agent-status, agent-read, agent-stop, agent-list) | The contact agent, by the command afk-team, under your allow rule Bash(afk-team *). A Claude worker under the same user settings. A Codex worker under the full-auto launch flags you authorised. | Any call the harness refuses. A joined command (afk-team ... && other) whose other part no rule covers: the harness checks each part on its own and asks you. | The harness permission layer. The rule decides before the auto-mode check (trial of 2026-10-26, Claude Code 2.1.310 and 2.1.311 (scratchpad trial-bin)). | Rule text was Bash(afk-python "${AFK_PLUGIN_ROOT}/scripts/afk-team.py" *). The command was afk-python with the full script path. |
> (packet HL3-4, signed R-47, row 2) | Write the afk-team launcher | /afk:setup, in a setup run you start, in the same step that places afk-python. | Every agent during a team run. The run only reads the launcher. | By convention, plus the spawn permission check below, which refuses a launcher that does not match the running plugin. | New row. |
> (packet HL3-4, signed R-47, row 3) | Spawn permission check, before a run's first transport command | The contact agent, through the provider layer (Claude Code only; other harnesses pass). | A run whose check fails: nothing starts. | The check itself. It confirms 3 things: the rule is in your settings; afk-team on PATH is the launcher in afk-bin; the launcher names the plugin folder that is running. On a miss it refuses and names the rule or /afk:setup. | Was 1 thing: the rule is present. The 2 launcher checks are new. |
> (packet HL3-4, risks) The rule trusts whatever afk-team PATH finds first. Another file named afk-team earlier on PATH would run under your rule. The spawn permission check refuses when afk-team is not the afk-bin launcher. The rule matches any arguments to afk-team, as the old rule matched any arguments to the script. Same reach as before. Not tried yet: a Codex agent on Windows calling afk-team from PowerShell. A build-time check proves it (see the side-effects packet).
> (packet HL5-7, signed R-47; SDD §7 E13) | E9 write the afk-team launcher into afk-bin (%LOCALAPPDATA%\afk\python\afk-bin on Windows; ~/.local/share/afk/python/afk-bin elsewhere). Files: afk-team (a shell script for Bash) and, on Windows, afk-team.cmd. Each holds one line that runs the team script of the plugin folder that ran setup. | A /afk:setup run you start: the Python runtime step, after the environment sync and after afk-python is placed. A sync can rebuild afk-bin, so the launcher is written after it every time. | Written to a staged file, then moved into place in one step. No manifest line and no repository file depends on it. | The file content. Setup writes only when the bytes differ; a repeat run changes nothing. | A missing launcher, or one that names an older plugin folder. The spawn permission check then refuses before the first transport command and names /afk:setup. Nothing starts. | Run /afk:setup again. To remove: delete the afk folder under %LOCALAPPDATA% (or ~/.local/share), which removes afk-python and the launcher together. |
> (packet HL5-7, risks) Inferred, not tried: the auto-mode check may also refuse setup's launcher write when setup runs in auto mode. Then you approve it, or run setup in default mode. afk-python is written to the same folder today without a refusal. afk-team.cmd and Codex on Windows are not tried. The build step proves them with a live row in the conformance record before it merges.
> (packet HL6-10, signed R-47, row 1) | Setup register: the spawn allow-rule offer (change C19) | The printed rule is Bash(afk-team *) instead of the full-path rule. Setup still prints it, waits for you, then confirms it is present. It still never writes a settings file. Skipped with no human present. | Only adds for a new user. On this machine the old full-path rule stays in your settings unused until you remove it. | Revert the commit, or install the previous plugin version. The rule stays in your settings until you remove it. | extends |
> (packet HL6-10, signed R-47, row 2) | Python runtime install (python_runtime.py: install and check) | install also writes the launcher (effect E9). check also reports a launcher that is missing or names another plugin folder. afk-python itself, its path and every existing caller are unchanged. | Only adds. An old runtime with no launcher reads as 'launcher missing', fixed by the next setup run. | Revert the commit. A leftover launcher is harmless: no rule from an older version names it. | extends |
> (packet HL6-10, signed R-47, row 3) | Path convention for plugin files (AGENTS.md, GLOSSARY.md 'Main checkout') | One stated exception: the team script is run as the bare command afk-team. Every other plugin file is still named by ${AFK_PLUGIN_ROOT}/... | Docs only; no existing command changes. | Revert the commit. | extends |
> (GRILL-LOG.md:746, trial of 2026-10-26) A plugin bin/ folder reaches the Bash PATH only through Claude Code's shell snapshot, which hit its 10 s limit in 3 of 4 sessions on this host (exit 127, 'afk-team: command not found').
> (INV-084) Step order: uv, python, environment (`uv sync`), launcher (`place_entry`), path (python_runtime.py:262-268, loop :316-350). place_entry runs only after the sync exits 0, so a launcher written there follows any wipe. An incompatible one (Python pin change, pyvenv.cfg conflict, broken link): sync calls `clear_virtualenv` on UV_PROJECT_ENVIRONMENT = `python/`, deleting every entry, afk-bin included, then recreates it. Sync wipes then fails: install returns 1 before place_entry with the stamp already gone (:312, :344-349); both commands are absent until setup re-runs. Untested.
> (ADR-0017) Before a run's first transport command, the spawn permission check proves 3 things: the rule is in the user's settings; afk-team on PATH is the launcher in afk-bin; the launcher names the plugin folder that is running. On a miss it refuses, names the rule or `/afk:setup`, and nothing starts. The check runs on Claude Code only; other harnesses pass (HL3-4).

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
0009-spawn-permission-check

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
