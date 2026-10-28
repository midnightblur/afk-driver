midnightblur/afk-driver@cc6bff8c5819f21be1f46c28dcd4179a65890e92 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-024-parse-single-file/COVERAGE.json

## Answer

`parse_single_file(path)` reads one file and nothing else. No layer merge, no owner filter, no git.

| Input | Answer | Site |
|---|---|---|
| path is not a regular file | `{}` | `scripts/afk-config.py:460` |
| a readable UTF-8 file in the YAML subset | the parsed mapping, values typed by `parse()` | `scripts/afk-config.py:462`, `:242-271` |
| unreadable file | `ConfigError` naming the file | `scripts/afk-config.py:427` |
| not UTF-8 | `ConfigError` naming the file | `scripts/afk-config.py:429` |
| outside the subset, or top level not a mapping | `ConfigError` from `parse()` | `scripts/afk-config.py:274-363` |

The only open is `Path.read_text` in `_read` (`scripts/afk-config.py:425`).
A value keeps its `parse()` type: `~` and `null` give `None`, digits give a number, `true`/`false` a Boolean. A caller of `developer.worktreeRoot` checks the type.

## Sites

- Definition: `scripts/afk-config.py:458`.
- Test: `scripts/tests/test_afk_config_owner.py:283-286` (a present file unfiltered, an absent file as `{}`).
- Documents: `docs/afk/setup-per-repo/plan/0002-settings-reader.md:75`, `docs/afk/setup-per-repo/plan/0004-placement.md:47`, `docs/afk/setup-per-repo/plan/review/0002-settings-reader-adversary.md:75`.
- No plugin code calls it at this head.

## Frontier

- B14: other repositories and installed plugin copies.

## Unverified

- Whether the hit set holds every reference over the name forms searched (not load-bearing).
