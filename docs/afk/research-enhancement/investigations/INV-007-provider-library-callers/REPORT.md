afk-driver-research-enhancement@d8ca9b44ea2275ac04ca61f6dc05b715f892c5f0 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/research-enhancement/investigations/INV-007-provider-library-callers/COVERAGE.json

## Answer (Q2: what reaches the provider shell library)

**Sourcing sites (10).** `hooks/stop-gates.sh:38`, `hooks/precommit-gates.sh:41`, `hooks/genericity-gate.sh:350`, `hooks/native-contract-gate.sh:377`, `hooks/skill-registry-gate.sh:253` (these three only in their standalone `[ "${BASH_SOURCE[0]}" = "$0" ]` block; under Stop they inherit it from `stop-gates.sh`), `hooks/install-git-hooks.sh:37`, `hooks/update-notice.sh:29`, `hooks/run-hook.py:261` (a `bash -c` snippet in `block()`, `:258-266`, run only when a repository handler cannot run), `skills/utils/report-issue/scripts/collect_env.sh:31`, `hooks/tests/hook-smoke.sh:13` (per case). `hooks/lib/providers/{claude,codex}.sh` are glob-sourced by the library itself (`hooks/lib/provider.sh:7-10`) and read `AFK_PROVIDER_CORE_DIR` (`claude.sh:15`, `codex.sh:17`).

**Wrapper callers.**

| Function | Sites |
|---|---|
| `afk_provider` | `provider.sh:55,60,73,144` (own wrappers) · `collect_env.sh:31` · `hook-smoke.sh:29` |
| `afk_agent_session` | `precommit-gates.sh:42` |
| `afk_plugin_root` | `install-git-hooks.sh:40` · `provider.sh:79,164` · `hook-smoke.sh:58,67` |
| `afk_plugin_data` | `update-notice.sh:31` · `hook-smoke.sh:58,67` |
| `afk_plugin_dir` / `afk_plugin_scope` | `stop-gates.sh:64-65` · `precommit-gates.sh:138-139` · `genericity-gate.sh:58,348` · `native-contract-gate.sh:34,375` · `skill-registry-gate.sh:55,251` · `hook-smoke.sh:319` (stubbed) |
| `afk_block_stop` | `stop-gates.sh:150` |
| `afk_emit_stop_block` / `afk_stop_block_code` | `run-hook.py:263` · `provider.sh:154-155` · `hook-smoke.sh:102-106` |
| `afk_emit_deny` | `run-hook.py:264` |
| `afk_hook_input` / `afk_hook_field` | `hook-smoke.sh:83` |
| `afk_emit_context`, `afk__json_escape` (external) | none — `afk__json_escape` used only inside the library (`:112,122,138`) |

**`AFK_PROVIDER` readers.** `provider.sh:20-22` (override); `hooks/branch-name-gate.sh:29-30` — a git `reference-transaction` hook that cannot source the plugin and hand-copies the detection order (`:26-35`: `AFK_PROVIDER` → `PLUGIN_ROOT`=codex → `CLAUDE_PLUGIN_ROOT`|`CLAUDECODE`=claude → unknown), matching `provider.sh:17-52` with adapters `codex.sh:32-38` (priority 10) and `claude.sh:3-9` (priority 20). `hook-smoke.sh:24,82,92,101-105,115` set it per case; `lavish-dark.sh` and `lavish-tips.sh` receive it (`:92,115`) but never read it (agent read, whole file). `.afk/config.yaml:43` lists it in a boundary pattern.

**`AFK_PROVIDER_NAMES` readers.** Only `provider.sh:5,13,21,28`. No other tracked file.

**Built names.** `afk_provider_plugin_root`, `afk_provider_plugin_data`, `afk_provider_stop_block_code` occur nowhere textually (B1 query `q-2115cc47`: 0 lines for those forms); the library builds `afk_${provider}_<member>` at `provider.sh:29-30,61,74,145` and resolves it with `command -v`.

**Tests and gates.** `hooks/tests/hook-smoke.sh:43-54` (detection order), `:56-72` (root/data precedence), `:74-123` (loop over `hooks/lib/providers/*.sh`: envelope parse, lavish pass-through, stop-block object/stderr/exit code). `hooks/native-contract-gate.sh` rule G `:306` (fixtures dir per adapter) and H `:322-329` (`PROVIDERS.md` row per adapter). Runtime entry: every `hooks/hooks.json` handler runs through `hooks/run-hook.py:314-320`; SessionStart (`install-git-hooks.sh`, `update-notice.sh`) and Stop (`stop-gates.sh`) handlers source the library; PreToolUse handlers do not; `repo-list` entries reach it only through `block()`.

**Documents naming it (consistent with code).** `PROVIDERS.md:7,11-12,35,48`, `CLAUDE.md:41,199`, `FRESHNESS.md:65`, `hooks/README.md:12,87,91`, `skills/afk/setup/MANIFEST.md:350,355,663,675-677,685`, `providers/CONFORMANCE.md:297`, `providers/PARITY.md:129-131`, `hooks/native-contract-allow.txt:26`, `CHANGELOG.md:947,1196,1470,1557`.

**Inference (labelled).** A new adapter file or a detection-order change must also touch `hooks/branch-name-gate.sh:26-35`; nothing enforces that copy (`:26-27` says so).

## Frontier
- B14: installed harness copies and consuming repositories' `.afk/hooks.json` handlers source the library at runtime outside this repository; live behaviour is a probe record (`providers/CONFORMANCE.md:21`).

## Unverified
- none. B6/B7 `n/a` (no build step `CLAUDE.md:22`; no aggregator manifest, sourcing by path `stop-gates.sh:38`). 1,991 of 2,218 nodes are `irrelevant`: 1,509 hits inside the untracked `docs/` spec folder (prior ledgers re-indexed by `--untracked`), the rest declared-pattern hits (`AFK_*` vars, `.json` paths, HTTP lines) not about the subject.

## Tooling defects seen
- `seed_map.py` splits a subject on `.`: root `provider.sh` became simple name `sh` (`-e sh`, unbounded) → 14,950 B1 hits and a 47-minute run (`git grep -i --untracked` over the spec-folder ledgers). Re-seeded with `provider.sh` as `--alias file=`; `run.roots` therefore lists `afk_provider`, `AFK_PROVIDER_NAMES` only.
- `merge_fragments.py` folds seed placeholders (`unverified` nodes, `judgment-only` rows) as conflicts; the fold used a staging copy whose rows were replaced by the fragment's (ids, `line_hash`, `query_id` unchanged).
- `run.config.sha256` here is `360476c8…` (the working-tree `investigation:` block, uncommitted at d8ca9b4). INV-003's ledger carries `44136fa3…` = sha256(`{}`), an empty block — reported, not patched.
