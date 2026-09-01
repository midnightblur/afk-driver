# Native harness conformance

This ledger records live probes for the committed plugin tree. `CAPABILITIES.md` owns degradation. `PROVIDERS.md` owns provider mappings.

## Run metadata

| Field | Claude Code | Codex CLI |
|---|---|---|
| Date | 2026-09-01 | 2026-09-01 |
| Version | 2.1.257 | 0.152.0 (confirmed live, meets the minimum tested version) |
| Install | Enabled plugin, this session; reload owed after this change | Marketplace registered, plugin installed and enabled; cache predates this change, so a refresh is owed |

## Probe ledger

| Probe | Claude Code | Codex CLI | Evidence |
|---|---|---|---|
| Native manifest loads | pass 2026-09-01 | partial 2026-09-01 | Both manifests parse with the same 40 skill paths. Second harness: marketplace registered and `afk@nak-marketplace` installed and enabled at 0.0.0, still through the legacy manifest path; acceptance of the new native manifest needs a live refresh |
| 40 `/afk:<x>` skills load | pending reload | pending | Catalog counted from the manifest; a session started after this change re-counts the live catalog |
| No generated mirror skills | n/a | pending | Generator and its outputs are deleted from the repository |
| Shared hooks load and are trusted | pass 2026-09-01 | pending | Both hook surfaces fired live this session: a PreToolUse guard denial and a Stop gate block |
| SessionStart envelope and environment names | pass 2026-09-01 | pending | `hooks/tests/hook-smoke.sh` parses every fixture under both adapters; live capture on the second harness still owed |
| CrowdStrike guard denies a system-root recursive scan | pass 2026-09-01 | pending | Live deny of an unscoped recursive command this session, plus the fixture case under both adapters |
| Stop gates block after a plugin edit | pass 2026-09-01 | pending | Live block at turn end; full suite green afterwards in 111s |
| Shared Jira MCP tool is callable | pass 2026-09-01 | pending | Plugin-scoped tool returned an issue; the plugin `.mcp.json` path form still needs the second harness |
| `afk-reader` returns a cited digest | pass 2026-09-01 | pending | Read-only child returned a two-line cited digest with file and line |
| Agent sandbox and write boundaries | pass 2026-09-01 | pending | Read-only role asked to create a file: declined at role level, no write tool in its definition, file not created |
| Same-child continuation | pass 2026-09-01 | pending | Follow-up reached the same child, which answered from its own context with zero tool calls |
| Cache refresh after source-only change | n/a | pending | — |
| Script-only hook change trust behavior | n/a | pending | — |
| Disable or uninstall leaves repository inert | pass (static) 2026-09-01 | pending | No activation surface is tracked: no `.agents/`, `.codex/` or local steering block in git, and the repository registers no plugin hook of its own. A live disable run is still owed |
| Native contract negative probe blocks | pass 2026-09-01 | n/a | Scratch skill with a `harness:` frontmatter key, a harness-tool reference, a fallback-free project-dir read, and a harness name: gate exit 2 naming all six findings; exit 0 after removal |

## Unresolved items

- `[U]` Plugin-root expansion in MCP arguments.
- `[U]` Exact local-plugin cache refresh command.
- `[U]` Instrumented hook environment on Codex.
- `[U]` Script-only hook changes and handler trust hashes.
- `[U]` Same-child continuation on Codex.

## Add harness #N

1. Add the harness row to the supported-harness registry in `PROVIDERS.md`.
2. Add `hooks/lib/providers/<name>.sh` with detect, root, and data functions.
3. Add one envelope fixture per shared event under `hooks/tests/envelopes/<name>/`.
4. Add a native manifest twin only when the harness cannot consume an existing manifest.
5. Add unchanged agent-definition stubs when the harness cannot consume `agents/*.md`.
6. Add one `CAPABILITIES.md` provider column and one `PROVIDERS.md` mapping column.
7. Add one `/afk:setup` probe section.
8. Run `hooks/tests/hook-smoke.sh` and `hooks/native-contract-gate.sh`.
9. Install through the harness enable flag. Run every probe in this ledger.
10. Record version, date, commands, verdicts, and unresolved capabilities here.
11. Confirm no skill prose changed for the harness.
