afk-driver-research-enhancement@d8ca9b44ea2275ac04ca61f6dc05b715f892c5f0 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/research-enhancement/investigations/INV-006-config-reader-definition/COVERAGE.json

## Answer (Q1)

- `TOP_LEVEL` (`scripts/afk-config.py:51-57`): a 24-member set literal — `schema, toolkit-version, tracker, forge, notes, build-gates, jira, github-issues, gitlab, github, git, repo-files, obsidian, notion, artifacts, maven, npm, verification, repo-hooks, setup, developer, worktree, investigation, report-issue`. One reader: `validate()` `:541-542` appends `<key>: unknown top-level key` per key outside the set; `main` prints each problem and exits 2 (`:1076-1080`). `git grep -w TOP_LEVEL -- scripts/afk-config.py`: 2 lines (`:51`, `:541`).
- `CHILD_KEYS` (`:105-125`): 16 blocks → child sets; `:586-597` refuses an unlisted child one level down by dotted path, and a non-mapping block (`:591`). No entry: `schema, toolkit-version, tracker, forge, notes, build-gates, repo-hooks, investigation` (8). `tracker/forge/notes` are enum-checked by `_choice` (`:544-546`, tuples `:46-48`); `build-gates` by `:548-559`.
- `investigation:` branch (`:637-667`): keys ⊆ `INVESTIGATION_KEYS = {boundaries, generated, reactor}` (`:81`, refused `:642`); `generated`/`reactor` are block lists of repository-relative paths (`:647-661`, `_relative_path :446`); `boundaries` → `_investigation_boundaries` (`:465-532`): keys ⊆ `INVESTIGATION_BOUNDARY_KEYS` (`:82-84`), `name` required, `class` ∈ `B1..B14` (`:91`, `:486`), exactly one of `pattern` or `judgment-only: true` + `site` (`:500-513`), `paths` block list, `note` string. `normalize()` (`:407-423`) folds `generated`, `reactor`, each entry's `site` and `paths` through `normalize_path` (`:378-404`) in place; `validate()` never calls it; sole caller `skills/utils/investigate/scripts/seed_map.py:300`, after `validate` `:297`.
- Discovery + merge: `DEFAULTS` `:127-139`; `layers()` `:326-345` home → repo → local overlay → `$AFK_CONFIG`; `load()` `:348-357` `deep_merge` (`:316`: mappings merge per key, other values replace); local overlay may not set `schema` (`:355`); `parse()` requires a top-level mapping (`:296`).
- Shell view (`:974-1006`): `flatten()` — mapping → dotted path to any depth (`:983`), list → `<path>.count` + `<path>.<index>` (`:985-987`), scalar → one pair (`:989`); `shell_name()` = `AFK_CFG_` + every non-`[A-Za-z0-9]` → `_`, upper-cased (`:975`); `shell_value()` None → `''`, bool → `true|false` (`:993-998`); `export_shell()` emits `NAME=shlex.quote(value)` lines then `AFK_CFG_LOADED=1` (`:1001-1006`); dispatched by `export-shell` (`:1088`). Sibling views: `effective --json` (`:1086`), `get` (`:1118`: map/list as JSON).
- Consumer: `hooks/lib/config.sh:16-32` evals the export once; reader absent or export failing → `AFK_CFG_LOADED=1` with nothing exported (`:27`, `:29`). `afk_config_list` (`:48`) rebuilds names with `tr '[:lower:].-'`; `hooks/lib/adapter.sh:32` builds `AFK_CFG_<FAMILY>` by name.
- Contract: `CONFIG.md:83-107` schema table lists the same 24 keys (checked: set difference empty); `:113-116` one-level child rule; `:169-218` investigation block + path folding; `:234-244` shell view grammar.
- Tests: `scripts/tests/test_afk_config.py:134` unknown top-level key refused; `:125` self config validates; `:197-222` three views agree, asserts `AFK_CFG_LOADED`, `AFK_CFG_BUILD_GATES_COUNT`, `_0`, `AFK_CFG_GIT_BASE_BRANCH`; `:226-233` quoting; `:237-265` per-block child typo (15 blocks); `:268-291` `CHILD_KEYS` ↔ `CONFIG.md` map rows (child sets only — `TOP_LEVEL` membership is compared by no test). `scripts/tests/test_afk_config_init.py:200,205,243,277` pin the investigation branch; `scripts/tests/test_seed_map_binding.py:431` pins `normalize`.

## Findings

- `TYPOS` (`test_afk_config.py:237-253`) has 15 blocks, `CHILD_KEYS` 16: `report-issue` has no per-block typo test.
- Inference (labelled): `afk_config_list` folds only `.`/`-`/lower-case while `shell_name` folds every non-alphanumeric — a dotted key holding another character would export under one name and list under another. No such key exists in `CHILD_KEYS`.

## Sites read (query_id null, 70 nodes)

`scripts/afk-config.py` `:51,81,105,127,296,326,348,352,355,356,378,407,412,417,465,477,486,500,541,542,586,591,593,637,640,642,647,661,667,974,975,978,983,985,989,993,1001,1004,1005,1054,1072,1075,1076,1080,1084,1086,1088,1118,1124` · `hooks/lib/config.sh:27,29,30,48` · `hooks/lib/adapter.sh:32` · `hooks/lib/provider.sh:7` · `adapters/tracker/jira/api.py:51` · `mcp-servers/tracker/server.py:63` · `CONFIG.md:83,105,113,197,228,234` · `test_afk_config.py:125,134,210,215-218,226,237,257,268` · `test_afk_config_init.py:200,205,243,277` · `test_seed_map_binding.py:431` · `seed_map.py:297,300`.

## Frontier
- B14: `hooks/update-notice.sh` (release check against the plugin's GitHub repository), `adapters/forge`, `adapters/tracker/github-issues` (live forge/tracker), consuming repositories' `.afk/config.yaml` — outside this repository.

## Unverified
- none. B6 `n/a` (`CLAUDE.md:11` "No package build step"; no `generated` declared). B7 `n/a` (`ls pom.xml package.json` at the root: both absent; no `reactor` declared).

## Tooling notes
- `run.config.sha256` = `360476c8…` (the resolved `investigation:` block, `seed_map.py:303-304`), not the empty-string digest — no defect.
- `merge_fragments.py` folds seed placeholder nodes as conflicts; folded a staging copy with placeholders replaced by the fragment's rows (ids, `line_hash`, `query_id` unchanged).
- `validate_coverage.py:351-357` counts a read node toward a `sites` row only when `traced`/`terminal`; `LEDGER-FORMAT.md:81-82` also admits `irrelevant`. Read nodes that end a path are recorded `terminal`.
- A row cannot carry both `sites` and hits (`validate_coverage.py:414-436`): B5 and B10 stay search-closed on the declared patterns, their declared sites read into `B5:scripts/afk-config.py:208,1004` and `B10:mcp-servers/tracker/server.py:63` under the agent counter-search.
- Single tracer (the orchestrator); no `afk-tracer` spawn: one module, no design phase.
