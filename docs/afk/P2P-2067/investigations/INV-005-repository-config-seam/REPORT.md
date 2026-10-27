nakisainc/core/core-services@fe27ed571348f12ecf5b3ea3633fe50582c26f79 · partial · boundaries 8/14 · unverified 0 (load-bearing 0) · ledger: 11700-payable/specs/2026r2/P2P-2067/investigations/INV-005-repository-config-seam/COVERAGE.json

## Answer

AFK stores repository choices in committed `.afk/config.yaml`; `CONFIG.md` defines the contract and supported YAML subset (`CONFIG.md:3`, `CONFIG.md:94`).
The single reader parses, layers, validates, and exposes the effective configuration (`scripts/afk-config.py:216`, `scripts/afk-config.py:363`, `scripts/afk-config.py:575`).
Shell consumers load one quoted `AFK_CFG_*` view; Python consumers import the same reader (`hooks/lib/config.sh:17`, `scripts/afk-config.py:1204`).
`/afk:setup` calls `init`, resolves each `TODO` with the human, validates, and asks for the contract to be committed (`skills/afk/setup/SKILL.md:49`).
Inference: a reusable capability adds its keys to `CONFIG.md`, the reader tables and validation, consumer access, scaffold, setup register, and focused tests.

## Sites

- Definition: `CONFIG.md:109`; `scripts/afk-config.py:46`; `scripts/afk-config.py:53`; `scripts/afk-config.py:108`.
- Load and exposure: `scripts/afk-config.py:216`; `scripts/afk-config.py:332`; `scripts/afk-config.py:342`; `scripts/afk-config.py:363`; `scripts/afk-config.py:388`; `scripts/afk-config.py:1177`; `scripts/afk-config.py:1204`; `scripts/afk-config.py:1231`; `hooks/lib/config.sh:17`.
- Validation: `scripts/afk-config.py:418`; `scripts/afk-config.py:505`; `scripts/afk-config.py:575`; `scripts/afk-config.py:777`; `scripts/tests/test_afk_config.py:56`; `scripts/tests/test_afk_config_init.py:237`.
- Bootstrap: `scripts/afk-config.py:857`; `scripts/afk-config.py:885`; `scripts/afk-config.py:912`; `scripts/afk-config.py:968`; `scripts/afk-config.py:1129`; `scripts/afk-config.py:1148`; `skills/afk/setup/MANIFEST.md:38`; `skills/afk/setup/SKILL.md:49`.
- Python consumers: `adapters/tracker/github-issues/api.py:71`; `hooks/run-hook.py:664`; `mcp-servers/tracker/server.py:62`; `scripts/protected-lookup.py:114`; `scripts/tracker_api.py:32`; `skills/afk/review/scripts/forge_ledger.py:1142`; `skills/afk/setup/scripts/developer_values.py:41`; `skills/afk/setup/scripts/setup_secrets.py:50`; `skills/utils/investigate/scripts/seed_map.py:278`.
- Shell consumers: `adapters/build-gate/maven/app-start-gate.sh:49`; `adapters/build-gate/maven/gates.sh:63`; `adapters/build-gate/maven/java-format-gate.sh:113`; `adapters/build-gate/maven/maven-compile-gate.sh:100`; `adapters/build-gate/maven/mutation-probe.sh:55`; `adapters/build-gate/npm/gates.sh:40`; `adapters/build-gate/npm/ui-lint-gate.sh:126`; `adapters/forge/github/forge.sh:26`; `adapters/forge/gitlab/forge.sh:28`; `adapters/notes/common.sh:114`; `adapters/notes/obsidian/notes.sh:12`.
- Gate and utility consumers: `hooks/behavior-registry-gate.sh:47`; `hooks/branch-name-gate.sh:89`; `hooks/comment-gate.sh:32`; `hooks/genericity-gate.sh:357`; `hooks/lib/adapter.sh:31`; `hooks/native-contract-gate.sh:794`; `hooks/precommit-gates.sh:82`; `hooks/skill-registry-gate.sh:260`; `skills/afk/gc/scripts/gc-check.sh:88`; `skills/utils/report-issue/scripts/collect_env.sh:29`; `skills/utils/report-issue/scripts/publish.sh:121`.

## Edge cases

- No file is valid at runtime and returns defaults, but setup keeps H0 unresolved until the repository commits its contract (`scripts/afk-config.py:388`, `skills/afk/setup/MANIFEST.md:44`).
- Local and shared overlays cannot change `schema`; an explicit missing file fails (`scripts/afk-config.py:379`, `scripts/afk-config.py:394`).
- Missing configured paths warn without failing schema validation (`CONFIG.md:15`, `scripts/afk-config.py:1282`).
- `init` writes `TODO` comments instead of guesses and refuses a second contract on the base branch or main worktree (`scripts/afk-config.py:968`, `scripts/afk-config.py:1129`).
- Export values are shell-quoted; a failed export records `AFK_CFG_LOAD_FAILED` and leaves selected gates off (`scripts/afk-config.py:1204`, `hooks/lib/config.sh:27`).
- Focused verification passed: `123 passed` (`afk-python -m pytest -q scripts/tests/test_afk_config.py scripts/tests/test_afk_config_init.py -o cache_dir=<scratch>/pytest-cache`, exit 0).

## Unverified

- B3 reflection/scan, B5 serialized shape, B6 generated code, B7 build graph, and B10 UI callers: no repository enumeration method.
- The repository has no `investigation:` block. Add one to `.afk/config.yaml` using `CONFIG.md:240` to close these classes.

## Frontier

- B14: other repositories, deployment manifests, and live consumers were outside this run.
