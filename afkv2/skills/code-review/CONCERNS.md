# Review concerns

A concern is one question that one reviewer answers. Pick from this table, or write a new one when the diff calls for it. A row is a candidate, never a duty.

| Concern | Question | The diff calls for it when |
|---------|----------|----------------------------|
| acceptance | Is every `## Acceptance` bullet met, and every `## Produces` line real? | it is the first review of the subtask |
| correctness | Does it work for every reachable input, error path and order of calls? | it adds branches, state, parsing or a later subtask consumes it |
| tests | Do the tests fail when the behavior breaks, and do they assert real output? | it adds or changes tests or behavior |
| scope | Does it stay inside `## Scope`, with no change that the contract does not ask for? | it touches a file outside the expected folders |
| refactor | Does each changed existing line keep its behavior for every caller? | it edits or deletes existing lines |
| contract | Is a new or changed public surface minimal, hard to misuse and compatible with its callers? | it changes a command, schema, public signature or file format |
| resilience | Does each new outside call have a timeout, a failure path and a bounded result? | it adds a network, process or file-system call |
| security | Can an input reach a command, a query, a path or a secret? | it handles outside input, credentials or permissions |
| design | Does the module shape hide its detail, and does it follow the SDD and the ADRs? | it adds a module or spans many files |
| rules | Does it break a written rule of the instruction files on its path? | it touches a folder with its own rules |
