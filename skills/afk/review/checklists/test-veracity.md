# test-veracity — do the tests prove the behaviour?

Default `class: test`; test logic in production code → severity `high`. Owns everything inside test code, plus test-shaped findings about production seams. Load the nearest `TESTING.md` in the target repo's chain and apply its documented antipattern list as documented rules (breaches are hard findings, not baseline judgment calls).
**Not yours:** production-code smells outside test files → `code-quality`; whether declared tiers actually cover the acceptance bullets → `spec-fidelity` owns the mapping, you own the *strength* of what exists.

## Reviewer checklist

Assertion strength:
- **Mock echo / tautology** (Meszaros) — stub returns X, test asserts X; `assertEquals(x, x)`; asserting the mock's own recording instead of the system's output → assert on real observable output. A seam test must assert the framework's **real** serialized output, not echo the DTO back.
- **Happy-path-only** (Meszaros) — multi-branch acceptance logic with one sunny test; missing negative and authz cases; no off-boundary values around new comparisons → add the boundary/negative cases.
- **Assertion roulette** (Meszaros) — a pile of indistinguishable asserts where the repo's ApprovalTests pattern (`JsonApprovals.verifyJson(capturedSaveArg)`) or messages would say which failed → prefer the repo's approval pattern over hand-rolled field-by-field asserts.

Test structure:
- **Obscure Test** (Meszaros) — can't tell the verified behaviour from the body: many behaviours in one test (eager test), fixture hidden in a file/DB row/shared setup (mystery guest), irrelevant setup noise → one behaviour per test, relevant fixture inline.
- **Conditional test logic** (Meszaros) — `if`/loops/`try` steering the asserts inside a test body → split or parameterize.
- **Fragile test** (Meszaros) — over-mocking that pins the implementation's call sequence (breaks on refactor, not on bug); asserts coupled to shared/seeded data; time/locale/ordering assumptions (`new Date()`, `Thread.sleep`, static state) → mock at boundaries only, own the fixture, control the clock.
- **Erratic test** (Meszaros) — sleep-based waits, order-dependent tests, shared mutable state between tests → deterministic sync, isolated fixtures.

Production seams:
- **Test logic in production** (Meszaros) — `if (testMode)`, test-only hooks, reflection backdoors in production classes → move the seam to config/injection. Severity `high`.
- **Hard-to-test code** (Meszaros) — a test needing reflection, deep mock chains, or massive setup is evidence of a production seam problem → file the finding against the production code, cite the test as evidence.

## Mutation probe (gate mode, sampled)

Static reading can miss a test that runs the code but asserts nothing that matters; mutation testing catches that empirically. When the slice diff changes production Java in a module whose `## Verification` table declares a green `unit`/`integration` tier, run `bash <main-checkout>/tools/payable/ai-agents/plugins/workflow/hooks/mutation-probe.sh {module} {changed-classes-csv} [{covering-test-classes-csv}]` (`<main-checkout>` = first entry of `git worktree list` — `GLOSSARY.md` "Main checkout") — one module per review (the one with the most changed production lines), `targetClasses` = only the classes the diff changed, `targetTests` = the test classes covering them (the sibling `*Test` by convention plus any test the diff touched). Read its one-line result: a `SURVIVED` mutant on a diff-changed line is a finding (`class: test`, severity `medium`; `high` when the mutant sits on a line satisfying an `## Acceptance` bullet); `NO_COVERAGE` on a diff-changed line likewise. `MUTATION: unavailable`/timeout is **no signal**: note it once in the report header and move on — never a finding, never a verdict input. Standalone mode skips the probe unless asked. **Full-unit round only**: a delta round (`--base` + `--tag` together, per SKILL.md "Delta rounds") never re-runs the probe — the first round's signal stands.
