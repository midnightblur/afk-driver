# Review — 0027-afk-team-launcher (base 7cef9b2, round tag r1)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity (always on), logic-correctness (complexity complex), refactor-safety (pre-existing lines changed) · skipped: api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: d82060b · diff: 7cef9b2..d82060b · verified: no design-level finding at medium or above went to a skeptic; the run parked first · forge ledger: pull request 112, round 1, all 12 keys carried

Verdict: advisory — crit=0 high=0 med=4 low=8

The run parked after this round. The referee reproduced f004 on a live Codex pane: `afk-team.cmd` drops the inner quotes of a JSON payload when PowerShell calls it, so no verb with a field runs. The reviewer rated it medium; it blocks every Codex agent on Windows. The fix changes the signed launcher files (SDD §7 E13), so it goes to the human (design_conflict).

| Id | Key | Severity | Class | Concern | Where | Finding |
|---|---|---|---|---|---|---|
| r-001 | f001 | medium | spec | spec-fidelity | providers/CONFORMANCE.md:518 | The default-mode and auto-mode rows prove the rule through --allowedTools, not a settings entry |
| r-002 | f002 | medium | test | test-veracity | scripts/tests/test_team_permission.py:579 | Three launcher-refusal tests build PATH from the host PATH, so a host with the real afk-bin on PATH (the state /afk:setup creates) makes them fail. |
| r-003 | f003 | medium | design | logic-correctness | skills/afk/setup/scripts/python_runtime.py:336 | One afk-bin launcher serves two harness plugin copies, so a setup run from the other harness repoints it and the Claude check then refuses `launcher` |
| r-004 | f004 | medium | correctness | refactor-safety | skills/afk/setup/scripts/python_runtime.py:312 | Possible payload-quoting break: the Windows call path changes from afk-python.exe to afk-team.cmd, and no test or live row sends a payload that holds double quotes. |
| r-005 | f005 | low | spec | spec-fidelity | providers/CONFORMANCE.md:525 | The Q55 row ran a driver on a scratch LOCALAPPDATA, not /afk:setup against the real afk-bin |
| r-006 | f006 | low | spec | spec-fidelity | skills/afk/setup/MANIFEST.md:385 | H15 Probe still defines exit 0 as rule present and no block entry; the launcher condition and the launcher Fix path are not stated |
| r-007 | f007 | low | design | scope-and-impact | scripts/team/permission.py:139 | permission.py becomes a second reader of python_runtime.layout()["team"] and team_launcher_root(), but no registry row or docstring names this caller. |
| r-008 | f008 | low | correctness | scope-and-impact | skills/afk/setup/scripts/python_runtime.py:348 | Possible install failure on Windows when afk-team or afk-team.cmd is in use: place_team_launcher moves with a bare os.replace, where place_entry renames a locked file away (inferred; not run). |
| r-009 | f009 | low | test | test-veracity | skills/afk/setup/scripts/python_runtime.py:550 | No test reaches two of the three failure branches of team_launcher_problem: `is not executable` and `differs from the launcher setup writes`. |
| r-010 | f010 | low | test | test-veracity | scripts/team/permission.py:159 | check_afk_team_launcher's `names no plugin folder`, `no POSIX shell`, `afk-bin cannot be located` and shell-timeout branches have no test. |
| r-011 | f011 | low | test | test-veracity | scripts/tests/test_python_runtime_setup.py:726 | Launcher bytes and the root round trip are tested only with the repo path; no test uses a plugin path holding a space or an apostrophe. |
| r-012 | f012 | low | correctness | logic-correctness | scripts/team/permission.py:103 | ENTRY_NAME shrank from `afk-team.py` to `afk-team`, so any allow entry that merely contains that text is reported `stale` instead of `missing` |
