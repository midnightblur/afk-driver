# INV-021 — L9 seams: /afk:bug removal, one tracker writer, registries, glossary test

`feat-small-lane@d346cfb · partial · boundaries 10/14 closed` (ledger `COVERAGE.json`, 15931 nodes, 82 claims). Frontier B14: harness loaders, installed caches, consuming repositories' `.claude/bugs`, live trackers. Written by the orchestrator from the run's reply; the run's own write was refused.

## Seam rows (draft)

| Seam | Existing contract | Planned change | Impacted | Verdict |
|---|---|---|---|---|
| S1 remove `/afk:bug` | manifests `.claude-plugin/plugin.json:19`, `.codex-plugin/plugin.json:9`, gated by `skill-registry-gate.sh:113-114`, `native-contract-gate.sh:200-208` (`test_plugin_source_gates.py:255`); `scripts/tests/test_publish_bug.py:30-33,43` imports the skill script → CI collection fails (inferred, `tests.yml:64`) | delete manifest entries + test in one commit; text refs below | `developer_values.py:148` asks `mrReviewer` (`test_setup_developer_values.py:72`), only bug reads it; `change-reviewers` sole caller `FIXER-PROMPT.md:33` — both re-consumed only once fix's ready+reviewer step lands (ordering landmine) | extends |
| S2 one tracker writer | "exactly two" at `AGENTS.md:9,193-195`, `README.md:108,117-121,682`, `MANIFEST.md:67,741,858`, `GLOSSARY.md:262`; `SPINOFF-TICKET.md:19-20,44`; `to-ticket/SKILL.md:99`; `jira/CONTRACT.md:41`; no code enforcement (`server.py:96-101,124-175`; guard `protected_branch_guard.py:40-42,91-95` passes comment/transition/attach) | rewrite sites; `adr/0008` supersedes ADR-0001 (no file); reword `AGENTS.md:201`; ADR-0002 stays history; `FRESHNESS.md:94` same commit | `/afk:report-issue` writes this repo's own tracker (`.afk/config.yaml:6,10`) — AC-035 exception | extends |
| S3a developer settings → CONFIG.md | `bug/CONFIG.md` K1-K5 (`:35-41`), K3 derivation (`:43-46`), read contract (`:50-62`), fail-closed (`:66-72`); `test_afk_config.py:356-380` one `developer` row, five keys | move; point at Discovery (`CONFIG.md:25-36`) | pointers `CONFIG.md:136`, `MANIFEST.md:127,914`, `FRESHNESS.md:78`, `README.md:340` | extends |
| S3b MANIFEST | Needed-by H2 (`:66-67`), H6 (`:126-127`), S1 (`:741`), W2 (`:913-914`); version floor pattern = C2b `sort -V` row (`:399-410`), no test; gate E (`adapter_registry_check.py:114`) register ids ↔ headings; `test_setup_h6_probe.py:22-25` | gh ≥2.99.0 floor row + github-issues `register`; `tracker_attach` at every home | H2 probe checks only `tracker_get` | extends |
| S3c FRESHNESS | rows `:77-80,86` | delete `:77,79`; edit `:80,86`; `:78` → CONFIG.md developer settings (says K1-K4, five keys) | no row covers `ADAPTERS.md`/adapter folders | reworked |
| S3d release | `release-gate.sh:91-95` checks agreement, not which part bumped; MAJOR is the human's call (`CHANGELOG.md:23-27`); `release.yml:14-18`; `update-notice.sh:124` surfaces `Migration:` | AC-041 clean-up in `Migration:` line | alias removals `to-demo-plan`, `settle-mr` due (inferred) | fits |
| S3e audit + M5 check | AUDIT checks 1,3,4,6 miss a bare `/afk:bug` in prose | new gate: `GATES` entry + `gate_<name>` (`plugin-source-gates.sh:97,186-188`), fixtures, `hooks/README.md` row; exclude spec folders; handle `/afk-toolkit:bug` (`CHANGELOG.md:2133`) | — | extends |
| S4 glossary test | `test_glossary_usage.py:160-184` walks filesystem via `rglob` (`glossary_usage.py:108-121`), case-folded substring | commit `PRD.md` (covers all five new terms: `PRD.md:1,43,26,18,96`; gc keeps it, `gc/SKILL.md:59-62`); remove `GLOSSARY.md:246-272` Bug pipeline entries | lavish tooltip dictionaries copy `afk:bug` (`requirements.html:740`, `solution.html:752`) | extends |

## S1 text references (no gate) → replacement

`afk-config.py:69`, `create-worktree:63` → CONFIG.md · `gc/SKILL.md:89-90` delete · `lessons/LEDGER-FORMAT.md:23` delete · `CAPABILITIES.md:65` → to-ticket only · `providers/PARITY.md:47` row + `:18` totals · `skills/afk/AGENTS.md:5-7` → steering line for format/helper/check-script lockstep · `hooks/README.md:123` → standalone fix ship · `to-meeting-d/SKILL.md:114` → to-ticket from a description · `agents/afk-implementor.md:3,9` delete "bug dossiers" · `test_tracker_create_assignee.py:3` docstring. `adapters/tracker/jira/api.py` keeps its users (`publish_prd.py:69-75,295-296`).

## Landmines

- S4: clean `git archive d346cfb` export fails "no consumer found for: Small lane, Light diagnosis, Diagnosis verdict, Fix proposal, Prior approval" (worktree passes on untracked files). "One-live-fixer invariant" stays "consumed" by `glossary_usage.py:30,58`, `GLOSSARY-FORMAT.md:35` — test cannot flag it if left.
- `resolve` returns `none` literally (`test_afk_config_init.py:206`) — fix treats `none` as absent, stays Draft.
- K1 required for a bug ticket, optional for a spinoff (`bug/CONFIG.md:37,68`) — bug mode picks one rule.
- `jira.transitions` names (`afk-config.py:1031`, `server.py:159-164`) vs id `12463` (`monorepo-config.yaml:20`, `test_afk_config.py:74-75`).
- `providers/PARITY.md:70` claims to-subtasks "proved tracker_create", contradicts `to-subtasks/SKILL.md:10`.
- "Nine operations" `ADAPTERS.md:42-45`, `server.py:1-3`, `CONFORMANCE.md:95-96`; `github-issues/CONTRACT.md:54` stale.
- AC-038 collision: 1357 lines in 26 files under `docs/afk/small-lane/`; PRD + ADR-0003 stay after gc.

## Must-dos

- Design gaps: worktree retirement (old path archived + deleted fixer worktree, `bug/LEDGER-FORMAT.md:36-37`; `gc-check.sh:99` needs `plan/PLAN.md`); write-to-disk-first for a description ticket (`bug/SKILL.md:28` vs `GRILL-LOG.md:44`).
- Re-establish in bug mode: refuse unknown fix version before any write (`test_publish_bug.py:247-272`); show 4xx bodies, retry 5xx twice, never 4xx (`:278-350`); keep content outside sentinel + meeting regions (`to-ticket/SKILL.md:22-23`); dry-run first (`:42-48`); dedup + link-debt (`SPINOFF-TICKET.md:53-67`).
- Already re-established: clean-base reproduction (`GRILL-LOG.md:27`); diagnosis written first (`:28`); redaction new (`:88`); hands-off refusal → prior approval (`PRD.md:130`); Dev-Pending → configured in-review state (`GRILL-LOG.md:83`).

## Unverified

B1, B12, B13 partial (alias/wire forms). c-9d353f85: first-pass name forms missed dependents; blind counter-search found 28, folded. No gate/pytest ran on a skill-removed tree (glossary export the exception). fix reading `mrReviewer` rests on design text. gh `--version` probe not run (local 2.92.0). Harness loader handling of a missing skill folder.

## Fold notes (plugin defects)

Seed placeholders dropped; `merge_fragments.py` lets seed boundary rows win (worst status) — reset to closed/no hits; 34 ids with two versions (owner kept); P3 tracer hashed ids in console code page, rehashed UTF-8; 2 seed query ids removed from B1/B12/B13; B3 given a read method.
