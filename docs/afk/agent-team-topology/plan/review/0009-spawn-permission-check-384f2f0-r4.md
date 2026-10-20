# Review — 0009-spawn-permission-check (base 384f2f0, round tag r4)

policy: lean · scope escalated (rounds 2 and 3 each found a changed rule whose sibling text was left stale) · activated: delta-sweep, test-veracity (the delta touches tests), consistency-sweep (scope escalation) · skipped: fix-owner specialists (round 3 had no critical or high finding), scope-and-impact (the delta stays inside Scope), logic-correctness and code-quality (delta under 150 changed lines and 6 files) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: 1df90bf · delta diff: 384f2f0..1df90bf · surface: every file in 53d1586..1df90bf plus the specs and setup files that state the same facts · forge ledger: pull request 112, keys 0009-spawn-permission-check/f025 to f030

Verdict: advisory — crit=0 high=0 med=2 low=4

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| ds-001 | f025 | medium | correctness | skills/afk/setup/MANIFEST.md:388 | The needs-human line would carry the says text that tells the human to rerun setup | fixed in 6a58db7: report only the cause |
| tv-r4-001 | f027 | medium | test | hooks/lib/providers/claude.sh:95 | The ownership guard had no test | fixed in 6a58db7: a test links `.claude` to a directory another user owns |
| ds-002 | f026 | low | spec | skills/afk/setup/MANIFEST.md:394 | The row did not say which status wins with no human present | fixed in 6a58db7 |
| cs-001 | f028 | low | correctness | hooks/lib/providers/claude.sh:87 | The adapter comment restated the old read conditions | fixed in 6a58db7: it points at PROVIDERS.md |
| cs-002 | f029 | low | correctness | skills/afk/setup/MANIFEST.md:387 | The opt-in tier rule still offered every probe miss in the election | fixed in 6a58db7: an entry's probe can name another status |
| cs-003 | f030 | low | spec | hooks/lib/providers/claude.sh:78 | D-75 placed the rule text in permission.py | fixed in 6a58db7 (D-83) |

On WSL Linux, disabling each of the three main-checkout guards fails its test; 32 tests pass and 1 skips there, 34 pass and 4 skip on Windows, and the static tier's 49 tests pass.
