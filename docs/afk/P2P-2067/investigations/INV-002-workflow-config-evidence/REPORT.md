nakisainc/core/core-services@fe27ed571348f12ecf5b3ea3633fe50582c26f79 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: 11700-payable/specs/2026r2/P2P-2067/investigations/INV-002-workflow-config-evidence/COVERAGE.json

## Answer

AFK reads layered configuration, then routes workflow writes through note and forge adapters. Durable evidence lives in plan files and the Draft change.

AFK also starts long-running processes and keeps shared state. These facilities are local harness processes or Git metadata, not one central workflow service.

## Facts

- Configuration merges home, repository, Git-common, checkout-local, and explicit-file layers. `scripts/afk-config.py:343-399`
- Gates export configuration once per run. Adapter dispatch selects the configured implementation. `hooks/lib/config.sh:17-32`; `hooks/lib/adapter.sh:29-49,73-113`
- File evidence includes `PLAN.md`, `JOURNAL.md`, and files below the configured spec directory. `adapters/notes/common.sh:114-156`; `skills/afk/to-subtasks/SKILL.md:79-83`; `skills/afk/execute/SKILL.md:37`
- Forge evidence includes Draft change checklists, review records, rationale receipts, and preflight blocks. `skills/afk/execute/SKILL.md:63,106`; `skills/afk/preflight/SKILL.md:171-189`; `skills/afk/review/SETTLEMENT.md:38`
- Long-running processes include the tracker Model Context Protocol server, mission-control watcher, stall watchdog, and background continuous integration wait. `mcp-servers/tracker/server.py:179`; `skills/afk/mission-control/scripts/mc/server.py:84-106`; `hooks/stall-watchdog.sh:47-64`; `skills/afk/preflight/SKILL.md:192`
- Shared state includes Git-common configuration, protection data, gate cache, gate metrics, and remote forge or tracker records. `scripts/afk-config.py:342-389`; `scripts/protected-lookup.py:222`; `hooks/gate-cache.sh:25,103-105`; `hooks/gate-metrics.sh:30-31`
- The tracker server reloads repository configuration for each call and caches adapter modules by kind. `mcp-servers/tracker/server.py:66-77`; `scripts/tests/test_tracker_server.py:82-89`

## Sites

- `scripts/afk-config.py:342-399`
- `adapters/notes/common.sh:114-156`
- `skills/afk/execute/SKILL.md:37,63,106,151`
- `mcp-servers/tracker/server.py:62-85,179`
- `skills/afk/mission-control/scripts/mc/server.py:84-107`
- `hooks/gate-cache.sh:25,75-105`

## Inferences

- Inference: AFK has distributed local control state, not one central workflow service. The process entry points and Git-common writers support this conclusion.

## Unverified

- The broad literal hit set is not claimed exhaustive beyond the searched name forms.
- The repository has no `investigation:` block. Generic defaults ran; declare the block in `.afk/config.yaml` to add repository mechanisms. `.afk/config.yaml:1-24`

## Frontier

- B14: other repositories, deployment manifests, live processes, and external forge records were not inspected.
