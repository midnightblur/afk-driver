# scope-and-impact — stayed in lane, blast radius known

Default `class: scope` (a genuinely broken direct caller is `correctness`).

Confirm every changed path matches a `## Scope` glob (out-of-scope file = finding), no forbidden pattern (liquibase/UpgradeGroup), no unrelated churn (stray `package-lock.json` reflow, formatter-only diffs in untouched files). Then assess blast radius: for each changed public symbol (method/class signature, REST path, DTO field, event), search the repo for its callers/consumers (`Grep` the symbol name across the affected module + its `*-client`/`*-entities` siblings) and surface as a finding any caller whose contract the diff changed but did **not** update or cover with a test. A changed `*-client` DTO or endpoint signature with downstream consumers in other services is high severity.
