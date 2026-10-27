nakisainc/core/core-services@fe27ed571348f12ecf5b3ea3633fe50582c26f79 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: 11700-payable/specs/2026r2/P2P-2067/investigations/INV-003-plugin-module-boundaries/COVERAGE.json

## Answer
AFK skills share executable behavior through one owner. Skills call the owner by its plugin-root path.
Mechanical behavior belongs in scripts. Python entry points run through the pinned `afk-python` runtime.
A later skill accepts inputs at invocation. It does not depend on or name its caller.
A script contract change updates its callers, tests, formats, and adapters in the same commit.

## Facts
- Script-first rule: `afk-driver@fe27ed5:AGENTS.md:31`.
- Runtime and interpreter rule: `afk-driver@fe27ed5:README.md:349`, `README.md:353`.
- Plugin-root path rule: `afk-driver@fe27ed5:AGENTS.md:204`.
- Direct skill-local script call: `afk-driver@fe27ed5:skills/afk/to-sdd/SKILL.md:42`.
- Shared review tool owner: `afk-driver@fe27ed5:skills/afk/review/SETTLEMENT.md:17`.
- Cross-skill caller: `afk-driver@fe27ed5:skills/utils/settle-change/SKILL.md:34`.
- Dependency direction rule: `afk-driver@fe27ed5:AGENTS.md:25`.
- Compatibility alias forwards all arguments and owns no behavior: `afk-driver@fe27ed5:skills/afk/to-demo-plan/SKILL.md:14`.
- Change sets for the seam gate and review tool: `afk-driver@fe27ed5:FRESHNESS.md:50`, `FRESHNESS.md:52`.

## Inference
Keep domain-specific executable logic under its owning skill. Promote logic to a plugin-root script or module only when ownership is plugin-wide.

## Sites
- `skills/afk/to-sdd/scripts/check_sdd_investigations.py`: owned by `/afk:to-sdd`; reused by `/afk:to-subtasks`.
- `skills/afk/review/scripts/forge_ledger.py`: owned by `/afk:review`; reused by `execute`, `preflight`, and `settle-change`.
- `skills/afk/to-meeting-d/SKILL.md`: canonical behavior behind the `to-demo-plan` compatibility alias.
- `runtime/pyproject.toml`: dependency set for `afk-python`.

## Unverified
None inside the pinned repository snapshot.

## Frontier
- B14: other repositories, deployment manifests, and live consumers were outside scope.
- The repository has no custom `investigation:` block. Generic defaults supplied the boundary catalog.
