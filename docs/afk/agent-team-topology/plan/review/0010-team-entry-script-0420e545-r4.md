# Review — 0010-team-entry-script (base 0420e545, round tag r4)

policy: lean · delta round · reviewers: delta-sweep, logic-correctness, test-veracity · deferred: code-quality, agents-md-compliance, design-quality, resilience (-> feature gate)
reviewed head: 360598c · forge ledger: pull request 112, round 4

Verdict: advisory — crit=0 high=0 med=2 low=4

| Id | Key | Severity | Class | Concern | Where | Finding | Outcome |
|---|---|---|---|---|---|---|---|
| r-001 | f054 | medium | correctness | logic-correctness | scripts/remove-worktree.py:424 | adopt() swaps the record with a bare os.replace, so on Windows a concurrent reader makes it fail and the swallowed error drops the adoption. | fixed 0ee8d66 |
| r-002 | f055 | medium | test | test-veracity | scripts/worktree_owner.py:259 | The new Windows retry paths _patient and _remove have no test that raises PermissionError | fixed 0ee8d66 |
| r-003 | f056 | low | correctness | logic-correctness | scripts/team/entry.py:298 | The agent-id check compares case-sensitively, so id `Contact` passes while its message ids `Contact-<n>` map to the same inbox file as `contact-<n>` on a case-insensitive disk. | fixed 0ee8d66 |
| r-004 | f057 | low | test | test-veracity | scripts/tests/test_team_entry.py:416 | The `words in body["reason"]` assertion cannot tell the two refusal branches apart | fixed 0ee8d66 |
| r-005 | f058 | low | smell | delta-sweep | scripts/tests/test_worktree_owner.py:7 | `import pytest` sits between `import json` and `import os`, splitting the stdlib import block | fixed 0ee8d66 |
| r-006 | f059 | low | correctness | delta-sweep | scripts/worktree_owner.py:283 | record_lock's failed-token-write cleanup uses a bare os.remove while the release path now uses the Windows-patient _remove | fixed 0ee8d66 |
