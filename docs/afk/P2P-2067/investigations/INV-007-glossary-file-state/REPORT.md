nakisainc/core/core-services@5743b7dcd68f043185cd406cdbd09f385de22383 · partial · boundaries 8/14 · unverified 0 (load-bearing 0) · ledger: 11700-payable/specs/2026r2/P2P-2067/investigations/INV-007-glossary-file-state/COVERAGE.json

## Answer

The repository commits each definition file beside its owning service. Shared definitions stay at the repository root.
`GLOSSARY-MAP.md` is the route table. It maps each domain owner to a repository-relative definition file (`GLOSSARY-MAP.md:5`, `GLOSSARY-MAP.md:6`).
The committed `.afk/config.yaml` has no glossary setting. `tools/payable` contains no tracked glossary configuration or definition file (`git grep -n -I -E -i -e 'glossary' -- .afk/config.yaml`, exit 1; `git ls-files -- tools/payable .glossary .glossary-rebuild`, exit 0).
Git commits version definition changes. The current history includes definition updates and removal of volatile code references (`git log -- GLOSSARY-MAP.md GLOSSARY.md 11700-payable/GLOSSARY.md`, exit 0).
Inference: file removal is a Git deletion plus a matching map edit. Without the map edit, the route becomes stale.
Inference: team configuration under `tools/payable` needs a supported pointer from `.afk/config.yaml`, or the plugin discovery contract must change.
Inference: moving the definition files under `tools/payable` conflicts with the accepted rule that definitions stay with the owning service (`11700-payable/specs/2026r2/payable-harness-setup/adr/requirements/0006-glossary-owned-per-project.md:6`).

## Sites

- Routes and ownership: `GLOSSARY-MAP.md:5`; `GLOSSARY-MAP.md:6`.
- Definition metadata: `GLOSSARY.md:3`; `11700-payable/GLOSSARY.md:3`.
- Repository configuration: `.afk/config.yaml:12`.
- Accepted placement: `11700-payable/specs/2026r2/payable-harness-setup/PRD.md:111`; `11700-payable/specs/2026r2/payable-harness-setup/PRD.md:137`; `11700-payable/specs/2026r2/payable-harness-setup/adr/requirements/0006-glossary-owned-per-project.md:6`.
- New configuration requirement: `11700-payable/specs/2026r2/P2P-2067/PRD.md:17`.
- Installed plugin seam: `{user}/.codex/plugins/cache/afk-toolkit/afk/1.16.0/CONFIG.md:138`; `{user}/.codex/plugins/cache/afk-toolkit/afk/1.16.0/skills/utils/glossary/SKILL.md:38`.

## Edge cases

- Both current definition files link to `.glossary/confidence.json`, but Git tracks no file at that path (`GLOSSARY.md:3`; `11700-payable/GLOSSARY.md:3`; `git ls-files -- .glossary`, exit 0 with no output).
- Empty local `.glossary` and `.glossary-rebuild` directories exist. Git does not version empty directories.
- The installed plugin fixes discovery to root `GLOSSARY-MAP.md`; it does not read a configurable entry point (`CONFIG.md:138`).
- The installed configuration reader rejects unsupported child keys (`CONFIG.md:142`). A new glossary block therefore needs a schema change.

## Unverified

- B3 reflection/scan, B5 serialized shape, B6 generated code, B10 user-interface callers, and B12 tests: no repository `investigation:` block declares their complete universes.
- Add an `investigation:` block to `.afk/config.yaml` to close these classes.

## Frontier

- B14: the installed AFK plugin and live forge history are outside this repository snapshot.
