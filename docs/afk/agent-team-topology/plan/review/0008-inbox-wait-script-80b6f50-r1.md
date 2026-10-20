# Review — 0008-inbox-wait-script (base 80b6f50, round tag r1)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (lean trigger: 0010 and 0014 consume this slice), refactor-safety (one changed line in AGENTS.md) · skipped: domain-alignment, api-contract (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no design-level concern finding, so no verify pass · mutation probe: the slice changes a shell script, not Java, so test-veracity ran hand-made mutants on a scratch copy; 6 survived and became findings r-003 and r-004
caller sets: no caller of hooks/inbox-wait.sh or the background_job_wake row exists outside tests and docs (repository search); .claude/wiring-ious.md owes both to 0010, 0014 and 0015; ground ledger INV-079 (closed-with-frontier)
reviewed head: 60f939f · slice diff: commit 60f939f · forge ledger: pull request 112, keys 0008-inbox-wait-script/f001 to f007

Verdict: advisory — crit=0 high=0 med=4 low=3

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | medium | correctness | hooks/inbox-wait.sh:42 | An inbox removed during the wait read as empty, so the job never ended | fixed in e5367fe |
| r-002 | medium | correctness | hooks/inbox-wait.sh:42 | A half-written envelope under a temporary name counted as a message | fixed in e5367fe |
| r-003 | medium | test | hooks/tests/hook-smoke.sh:1019 | The park-until test did not time the exit, so a wrong date sum or a missing short last nap passed | fixed in e5367fe |
| r-004 | medium | test | hooks/tests/hook-smoke.sh:1040 | No boundary cases for the hour, second and leap-year checks, or for a third argument after a valid time | fixed in e5367fe |
| r-005 | low | correctness | hooks/inbox-wait.sh:36 | An empty park-until meant no park-until instead of a usage error | fixed in e5367fe |
| r-006 | low | scope | .claude/wiring-ious.md:33 | Two IOU lines in a file outside the Scope list | withdrawn on adjudication |
| r-007 | low | scope | investigations/INV-079-wait-script-ground/REPORT.md:1 | The investigation ledger committed outside the Scope list | withdrawn on adjudication |

The test-veracity reviewer ran mutants on a scratch copy of the script. After the fix, each of the 9 sampled mutants fails the inbox wait section.
