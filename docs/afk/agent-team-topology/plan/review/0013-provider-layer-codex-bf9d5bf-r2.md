# Review — 0013-provider-layer-codex (base bf9d5bf, round tag r2)

policy: lean · activated: delta-sweep (delta round) · skipped: fix-owner specialists (round 1 had no critical or high finding) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: ebad0d6 · delta diff: bf9d5bf..ebad0d6 · forge ledger: pull request 112, keys 0013-provider-layer-codex/f007 to f009

Verdict: advisory — crit=0 high=0 med=2 low=1

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| ds-001 | f007 | medium | design | CHANGELOG.md:107 | Setup's check still cannot spot an outdated copy, so a reader who skips the notes keeps the old names | withdrawn by a fresh adjudicator: Scope leaves out setup's MANIFEST.md; Acceptance accepts the posture |
| ds-002 | f008 | medium | correctness | PROVIDERS.md:157 (anchored at :138, the nearest changed line) | The tier-pin refresh step still trusted a setup re-run alone | fixed in a46c988 |
| ds-003 | f009 | low | compliance | PROVIDERS.md:23 | The row restated setup's probe instead of pointing at entry O5 | fixed in a46c988 |

f008 repeats round 1's shape (a corrected instruction whose sibling kept the old text).
