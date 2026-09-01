# Native harness conformance

This ledger records live probes for the committed plugin tree. `CAPABILITIES.md` owns degradation. `PROVIDERS.md` owns provider mappings.

## Run metadata

| Field | Claude Code | Codex CLI |
|---|---|---|
| Date | 2026-09-01 | 2026-09-01 |
| Version | 2.1.257 | 0.152.0 |
| Install | Pending final native reload | Pending final native cache refresh |

## Probe ledger

| Probe | Claude Code | Codex CLI | Evidence |
|---|---|---|---|
| Native manifest loads | pending | pending | — |
| 40 `/afk:<x>` skills load | pending | pending | — |
| No generated mirror skills | n/a | pending | — |
| Shared hooks load and are trusted | pending | pending | — |
| SessionStart envelope and environment names | pending | pending | — |
| CrowdStrike guard denies a system-root recursive scan | pending | pending | — |
| Stop gates block after a plugin edit | pending | pending | — |
| Shared Jira MCP tool is callable | pending | pending | — |
| `afk-reader` returns a cited digest | pending | pending | — |
| Agent sandbox and write boundaries | pending | pending | — |
| Same-child continuation | pending | pending | — |
| Cache refresh after source-only change | n/a | pending | — |
| Script-only hook change trust behavior | n/a | pending | — |
| Disable or uninstall leaves repository inert | pending | pending | — |
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
