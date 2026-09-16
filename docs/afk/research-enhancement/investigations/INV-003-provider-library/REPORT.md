afk-driver-research-enhancement@d8ca9b44ea2275ac04ca61f6dc05b715f892c5f0 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/research-enhancement/investigations/INV-003-provider-library/COVERAGE.json

## Answer (Q1 + Q3 + Q5)

1. **Verb set.** `hooks/lib/providers/` holds two files. Each defines five functions: `afk_<p>_priority`, `_detect`, `_plugin_root`, `_stop_block_code`, `_plugin_data` (`claude.sh:3-29`, `codex.sh:3-31`). **Resolution = glob-sourcing + name convention**: `provider.sh:7-14` sources `providers/*.sh` and takes the file stem as the provider name; `afk_provider()` (`:17-52`) picks `AFK_PROVIDER` if set (unknown name → `unknown`), else the lowest `afk_<p>_priority` among files whose `afk_<p>_detect` succeeds (tie → `unknown`). Each wrapper then builds `afk_${provider}_<member>` and checks it with `command -v` (`:31`, `:62`, `:75`, `:145`). No verb table, no generic verb dispatcher, no verb argument.
2. **Must every file define every verb? No.** Absent `detect` → file skipped (`:31`); absent `priority` → 100 (`:33-37`); absent/empty `plugin_root` → computed from the library path (`:62-68`); absent/empty `plugin_data` → `$HOME/.afk/data/<root>` (`:75-80`); absent `stop_block_code` → 2 (`:145-150`). Every fallback is silent, exit 0.
3. **Exit shape.** The 0/2/3/4 shape is the **adapter-family** contract, not the provider library's: `ADAPTERS.md:29-34`; dispatch exit 2 `hooks/lib/adapter.sh:41-50`; exit 3 for an undeclared verb enforced by dispatch only for `instruction` kinds (`adapter.sh:97-100`); `cli` kinds answer from their own entry (`adapters/forge/none/forge.sh:10-11`, `adapters/notes/common.sh:34-38`, `adapters/tracker/none/api.py:36`), pinned for forge kinds by `scripts/tests/test_forge_adapters.py:163-167`; build gates 0/2/3/4 `adapter.sh:162-168`. Nothing in `provider.sh` or `providers/*.sh` exits 3.
4. **Codex spawn.** `absent(closed over B1-B13, frontier: B14)`. No tracked file runs `codex exec` or `claude -p`, reads `ANTHROPIC_API_KEY`/`CODEX_API_KEY`, or passes `--bare` (tracked-only search q-0a8bcbfb: 0 lines; the forms exist only in the untracked spec folder). `codex.sh` is five pure functions over `PLUGIN_ROOT`/`PLUGIN_DATA`/`CLAUDE_PLUGIN_*`. The only Codex child surface is the harness-native agent stubs `providers/codex/agents/afk-afk-*.toml` (model, effort, `sandbox_mode`), copied by `/afk:setup`; the plugin passes no environment. The nearest child-env construction is the hook launcher: `hooks/run-hook.py:142-150,312,319` copies `os.environ`, repairs `PATH`, adds `AFK_PLUGIN_ROOT`, strips nothing.

## What pins the existing members

| Pin | Site | Covers |
|---|---|---|
| hook smoke test | `hooks/tests/hook-smoke.sh:43-54` | detection order, `AFK_PROVIDER` override, unknown |
| hook smoke test | `:56-72` | root/data precedence per provider |
| hook smoke test | `:74-123` (loop over `providers/*.sh`) | envelope parse, lavish pass-through, stop-block object + stderr + exit code |
| native-contract gate G/H | `hooks/native-contract-gate.sh:305-330` | one fixtures dir per provider file; one `PROVIDERS.md` row per file |
| freshness rule | `FRESHNESS.md:65` | same-commit update of fixtures, columns, setup section, conformance row |
| conformance | `providers/CONFORMANCE.md:21,297`; `providers/PARITY.md:129-131` | live probe records; add-harness checklist names "detect, root, and data functions" |

## What breaks when the six member verbs are appended

- Nothing existing: the smoke test and gates key on the **file set** and call the five members by fixed name; `provider.sh` sources any function. The appended functions are unreachable until a caller constructs their names — no wrapper exists (inference, labelled in the ledger).
- Documents: `providers/CONFORMANCE.md:297` becomes incomplete (`breaks`, unguarded); `PROVIDERS.md:48` + `CLAUDE.md:41` oblige a same-change `PROVIDERS.md` update.
- A **new provider file** (not a new verb) breaks gate G/H (`:305-330`), the hand-copied detection order `hooks/branch-name-gate.sh:26-35`, and the checklist `CONFORMANCE.md:294-306`.
- Inference (labelled): "unsupported verb exits 3" is a second convention beside the library's fall-back-when-absent one; the in-repo precedent for exit 3 is the adapter shape, so the new dispatcher must choose fallback vs exit 3 explicitly. `SDD.draft.md:486` attributes "exit shape 0/2/3/4" to the provider library; the code puts it in `hooks/lib/adapter.sh` + `ADAPTERS.md`.

Callers of the library (all fixed-name, unchanged): `hooks/stop-gates.sh:38,150`, `hooks/precommit-gates.sh:41-42`, `hooks/genericity-gate.sh:350`, `hooks/native-contract-gate.sh:377`, `hooks/skill-registry-gate.sh:253`, `hooks/install-git-hooks.sh:37,40`, `hooks/update-notice.sh:29,31`, `hooks/run-hook.py:258-266`, `skills/utils/report-issue/scripts/collect_env.sh:31`. History: no member renamed or deleted (`git log --diff-filter=D -- 'hooks/lib/providers/*'`: empty).

## Frontier
- B14: consuming repositories' `.afk/hooks.json` handlers and the installed harness copies (`~/.codex/agents/*.toml`, plugin cache) that source the library; live harness behaviour is a probe record in `providers/CONFORMANCE.md`, not code here.

## Unverified
- none. B5/B6/B7/B10 are `n/a` with cited reasons (no serialized shape beyond the fixed hook envelope, no build step, no build graph, no UI callers). Tooling note: `merge_fragments.py` folds seed placeholders (`unverified` nodes, `no enumeration method` rows) as conflicts; the staging copy was folded with those placeholders replaced by the fragment's own rows (every seed node id, `line_hash`, `query_id` carried unchanged). A first seed run wrote its scratch under the spec folder and re-indexed itself (537 self-hits); the published run seeded from the provider scratch directory.
