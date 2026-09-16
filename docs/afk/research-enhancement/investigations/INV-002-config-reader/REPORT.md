afk-driver-research-enhancement@d8ca9b44ea2275ac04ca61f6dc05b715f892c5f0 · closed-with-frontier · boundaries 13/14 · unverified 2 (load-bearing 0) · ledger: docs/afk/research-enhancement/investigations/INV-002-config-reader/COVERAGE.json

## Answer (Q2 + Q3)

- `TOP_LEVEL` has one reader: `validate()` `scripts/afk-config.py:541`. Adding `research`/`consultation` widens the accepted set; rejection semantics stay (pinned `scripts/tests/test_afk_config.py:134`).
- `load()` (`:348-357`) never validates. `export-shell`, `effective`, `get`, `resolve` accept a file carrying the new blocks on an older plugin (probe: `export-shell` exit 0; `validate` exit 2 naming both keys). Every `AFK_CFG_*` reader keeps working.
- Shell view: `flatten()` (`:978-990`) recurses maps to any depth, lists to `_COUNT`/`_N`. `research.dispatch.max-participants` → `AFK_CFG_RESEARCH_DISPATCH_MAX_PARTICIPANTS`. `shell_name()` (`:975`) folds every non-alphanumeric to `_`: participant names differing only in `-`/`_`/`.`/case collide into one variable; the later line wins under `eval` (`hooks/lib/config.sh:30`). `get` answers a map as JSON (`:1118`).
- Precedent `investigation:`: a `TOP_LEVEL` member (`:55`) with no `CHILD_KEYS` entry; dedicated validator branch `:637-667` (`INVESTIGATION_KEYS`) + `normalize()` `:407-423`; own `CONFIG.md` section `:169-218`; consumed structurally in Python (`skills/utils/investigate/scripts/seed_map.py:285-301`); no shell reader of `AFK_CFG_INVESTIGATION_*` (0 hits).
- Child validation for a new block comes only from a `CHILD_KEYS` entry (one level, `:586-597`) or a dedicated branch. Per-participant keys below that level are unconstrained (`CONFIG.md:113-116`); a key must match `[A-Za-z0-9_.-]+` (`:150`, refused `:243`); duplicates refused (`:247`). `deep_merge` (`:316`) merges nested maps per layer; lists replace whole.

## What breaks

| Site | Facet | Breaks when | Pinned by |
|---|---|---|---|
| `scripts/afk-config.py:51` | key set | the change site itself | `test_afk_config.py:134` |
| `CONFIG.md:83-107` schema table | document | rows missing → code refutes the document | `test_afk_config.py:267` |
| `scripts/tests/test_afk_config.py:267-291` | `CONFIG.md`↔`CHILD_KEYS` drift | block in `CHILD_KEYS` and its row's backticked key-shaped words ≠ child set; one-directional — a row for a block outside `CHILD_KEYS` is never checked | itself |
| `scripts/tests/test_afk_config.py:124` | self config | this plugin's `.afk/config.yaml` gains the blocks before `TOP_LEVEL` | itself |
| `skills/utils/investigate/scripts/seed_map.py:297` | `validate` | consuming repo adds the blocks before the plugin ships → every `/afk:investigate` exits 2 | `test_seed_map_binding.py:465` |
| `skills/utils/report-issue/scripts/publish.sh:104`; `skills/afk/setup/SKILL.md:41` | `validate` | same skew → publish queues; setup fails | unguarded |
| `scripts/afk-config.py:975` | shell name | participant names collide | `test_afk_config.py:196` (shape only) |
| `scripts/afk-config.py:150` | parser | participant name outside `[A-Za-z0-9_.-]+` | `test_afk_config.py:101` |

Deployment order: plugin first (`TOP_LEVEL` + `CONFIG.md` row + tests in one commit, `FRESHNESS.md:85` pattern); repositories add the blocks after upgrading. No schema or migration effect (B9: 0 hits).

## Unchanged sites (fixed-name readers; none pinned by a test that sets `AFK_CFG_`)

`adapters/build-gate/maven/{app-start-gate.sh:51, java-format-gate.sh:33-34, maven-lib.sh:19,31, worktree-provision.sh:82-84}`, `adapters/build-gate/npm/{ui-lint-gate.sh:38-43, worktree-provision.sh:64-71}`, `adapters/forge/github/forge.sh:111`, `adapters/forge/gitlab/forge.sh:119`, `adapters/notes/common.sh:117`, `adapters/notes/obsidian/notes.sh:13`, `hooks/branch-name-gate.sh:59,90`, `hooks/gate-context.sh:51-52`, `hooks/lib/adapter.sh:32` (families only), `scripts/create-worktree:201-202`, `skills/afk/gc/scripts/gc-check.sh:89`; `scripts/worktree-provision:62` re-exports every `AFK_CFG_*` to adapter subprocesses. Loaders that source `hooks/lib/config.sh` (40 sites, counter-search t1) read nothing new. Python importers using `load()+get()`: `hooks/run-hook.py:162`, `mcp-servers/tracker/server.py:62`, `scripts/tracker_api.py:32`, `adapters/tracker/github-issues/api.py:70`, `skills/afk/setup/scripts/setup_secrets.py:45`, `skills/utils/investigate/scripts/contract.py:195`.

Inference (labelled): a new shell reader of the research/consultation variables needs a register row in `skills/afk/setup/MANIFEST.md:682-692`.

## Frontier
- B14: consuming repositories' `.afk/config.yaml` and their `.afk/hooks.json` handlers.

## Unverified
- none load-bearing. Tooling note: `merge_fragments.py` folds seed placeholders (`unverified` nodes, `no enumeration method` rows) as conflicts; the staging copy was folded with those placeholders replaced by the fragment's own rows (every seed node id, `line_hash`, `query_id` carried unchanged). Re-validated 2026-09-15 against the `investigation:` block now in `.afk/config.yaml` (`run.config.sha256` restamped): B10 `n/a` → closed by reading `mcp-servers/tracker/server.py:62` (fixed-key `get`, no validate) plus the `http-and-cli-callers` pattern as a counter-search (7 lines; `adapters/tracker/jira/api.py` reads no config); B3 gained the configured sites `hooks/lib/provider.sh:7`, `hooks/lib/adapter.sh:146` (unchanged); B5 gained `scripts/afk-config.py` as the codec site plus the `json-jsonl-artifacts` pattern as a counter-search (159 lines, no new reader). Verdict unchanged.
