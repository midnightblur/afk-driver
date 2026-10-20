# Review — 0009-spawn-permission-check (base b397b3d, round tag r10)

policy: lean · scope escalated · activated: delta-sweep, test-veracity (the delta touches tests), consistency-sweep (scope escalation) · skipped: fix-owner specialists (round 9 had no critical or high finding), scope-and-impact (the delta stays inside Scope; plan records excluded), logic-correctness and code-quality (delta under 150 changed lines and 6 files) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: d824640 · delta diff: b397b3d..d824640 without docs/afk/agent-team-topology/plan/ · surface: every file in 53d1586..d824640 plus the specs and setup files that state the same facts · forge ledger: pull request 112, keys 0009-spawn-permission-check/f055 to f061

Verdict: advisory — crit=0 high=0 med=2 low=5 · round cap reached: stalemate, all 7 open for a human

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| ds-r10-1 | f055 | medium | correctness | scripts/team/permission.py:70 | The ok answer for an adapter with no rule says none is needed, an untried premise | open |
| TV-1 | f057 | medium | test | scripts/tests/test_team_permission.py:92 | No test pins the new wording of the missing refusal | open |
| ds-r10-2 | f056 | low | correctness | scripts/team/permission.py:98 | The missing refusal does not say when no settings file could be read | open |
| TV-2 | f058 | low | test | scripts/tests/test_team_permission.py:104 | Three refusal tests skip the shared refusal check | open |
| cs-r10-001 | f059 | low | correctness | scripts/team/permission.py:70 | "none is needed" also stands in the usage line and row H15's probe | open |
| cs-r10-002 | f060 | low | spec | skills/afk/setup/MANIFEST.md:381 | ADR-0005 prose, SDD C19 and 0009 bullet 1 still say the rule's presence is confirmation | open (a ledger entry or the human's contract edit) |
| cs-r10-003 | f061 | low | spec | PROVIDERS.md:186 | ADR-0005 and the context excerpts still say every refusal names the rule | open (a ledger entry) |

39 tests pass and 1 skips on WSL Linux and 34 pass and 6 skip on Windows at d824640; the static tier passes (49).
