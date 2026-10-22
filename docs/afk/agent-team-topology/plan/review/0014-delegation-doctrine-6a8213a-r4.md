# Review — 0014-delegation-doctrine (base 6a8213a, round tag r4)

policy: lean · delta round · activated: delta-sweep (always) · skipped: every specialist (no high finding in round 3, no delta trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: d856ea9 · delta: 6a8213a..d856ea9 · forge ledger: pull request 112, keys 0014-delegation-doctrine/f014 to f016

Verdict: advisory — crit=0 high=0 med=3 low=0

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f014 | medium | correctness | DELEGATION.md:38 | The fallback parked at once where a lost debater's debate should wait | fixed in b5c054b: the line only points at /afk:team |
| r-002 | f015 | medium | compliance | DELEGATION.md:38 | "the team skill" instead of the literal /afk:team | fixed in b5c054b |
| r-003 | f016 | medium | compliance | DELEGATION.md:38 | "lost-agent recovery" names a section no contract defines | fixed in b5c054b, with a wiring note anchored to the subtask that builds /afk:team |
