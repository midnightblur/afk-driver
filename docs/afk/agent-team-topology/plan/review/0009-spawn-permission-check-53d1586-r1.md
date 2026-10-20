# Review — 0009-spawn-permission-check (base 53d1586, round tag r1)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (lean trigger: 0010 consumes this slice) · skipped: refactor-safety (the diff only adds lines), domain-alignment, api-contract (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no design-level concern finding, so no verify pass · mutation probe: not run, the slice changes no production Java
caller sets: no existing public symbol changed; 0010 ## Consumes names `check_spawn_permission(`; ground ledger INV-080 (closed-with-frontier)
reviewed head: 4c812fc · slice diff: 53d1586..4c812fc · forge ledger: pull request 112, keys 0009-spawn-permission-check/f001 to f013
merged: logic-correctness LC-2 into r-002 (SF-1), LC-3 into r-004 (SF-3), LC-4 into r-003 (SF-2)

Verdict: blocking — crit=0 high=1 med=9 low=3

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | high | correctness | hooks/lib/providers/claude.sh:89 | On Windows the check counted the main checkout's local settings file, which the harness does not read there | fixed in cf432e0 |
| r-002 | medium | spec | scripts/team/permission.py:86 | The stale refusal named the first settings file, not the file holding the stale entry | fixed in cf432e0 |
| r-003 | medium | spec | scripts/team/permission.py:54 | The provider-layer refusal dropped the rule and the /afk:setup pointer | fixed in cf432e0 |
| r-004 | medium | spec | hooks/lib/providers/claude.sh:86 | Organization-managed settings are not read | fixed in cf432e0 (D-81: stated in PROVIDERS.md) |
| r-005 | medium | scope | scripts/team/permission.py:26 | The rule's command form was not carried to the entry script and the team skill | fixed in cf432e0 (D-78: IOU) |
| r-006 | medium | scope | scripts/team/permission.py:35 | A harness adapter without the spawn functions answered ok silently | fixed in cf432e0 (D-79) |
| r-007 | medium | scope | hooks/lib/providers/claude.sh:77 | The rule constant was a global any adapter could overwrite | fixed in cf432e0 |
| r-008 | medium | scope | skills/afk/setup/MANIFEST.md:375 | The new setup row shipped without its changelog line | fixed in cf432e0 (D-80) |
| r-009 | medium | test | scripts/tests/test_team_permission.py:96 | No test reached the main checkout's local file, and the fixture did not isolate git | fixed in cf432e0 |
| r-010 | medium | test | scripts/team/permission.py:54 | No test reached the provider-layer refusal | fixed in cf432e0 |
| r-011 | low | test | scripts/tests/test_team_permission.py:39 | The test's wildcard model had branches no test ran | fixed in cf432e0 |
| r-012 | low | test | scripts/tests/test_team_permission.py:136 | The unreadable-file test proved the skip only by an absence check | fixed in cf432e0 |
| r-013 | low | test | scripts/tests/test_team_permission.py:165 | One CLI test checked four behaviours | fixed in cf432e0 |

The fixer added the regression tests first: 9 of them failed on the old code and all 28 tests pass on Windows and on WSL Linux.
