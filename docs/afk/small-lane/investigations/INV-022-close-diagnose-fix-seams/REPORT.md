midnightblur/afk-driver@d346cfb5b3957f410119b4199dc2184f890d341a · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/small-lane/investigations/INV-022-close-diagnose-fix-seams/COVERAGE.json

## Seam rows

| seam | existing contract | planned change | impacted | verdict |
|---|---|---|---|---|
| `/afk:diagnose` never fixes | Phase 5 tests then fixes (`skills/utils/diagnose/SKILL.md:119-133`); Phase 6 assumes the fix (`:139-145`); hand-off to unshipped `/improve-codebase-architecture` (`:147`); description says "→ fix → regression-test" (`:3`) | writes `DIAGNOSIS.md` only; keeps heading, name, description, language pointer | `fix/SKILL.md:12,31,38,42,112`; `:3` description contradicts "never fixes"; Phase 2.5 body names Phases 3 and 6 (`:91`) | reworked |
| shared fix procedure from `/afk:fix` phases | in-place callers `execute/SKILL.md:67,77,93,123`, `preflight/SKILL.md:99,125`, `bug/FIXER-PROMPT.md:29`; only `design_conflict` routed (`execute:67`); `fixed_no_test`, `cannot_reproduce`, `needs_artifact_sync` read nowhere else | new file beside fix; 7 results | `fix/SKILL.md:14,107,110`; `grill-requirements/ROUND.md:162` (fix Phase 2); `FRESHNESS.md:53`; `review/checklists/refactor-safety.md:10`; `flaky` conflict `SDD.draft.md:98` vs `:552` | extends |
| lesson capture links | miss classes 6 = mapping 6 (`ESCAPE-ANALYSIS.md:24-29`, `lessons/LEDGER-FORMAT.md:83-88`); `lesson-append.sh:59` checks only `--class` | point at the procedure file | phase anchors `ESCAPE-ANALYSIS.md:1,3,24,37`, `WORKFLOW-FEEDBACK.md:1,6,16,19,31,33,48`; `AGENTS.md:153`; `LEDGER-FORMAT.md:79` | extends |
| grills | no argument; inputs via pre-brief (`grill-requirements/SKILL.md:16`, `grill-solution/SKILL.md:14`); PRD assumed at `grill-solution:3,14,16,49,115`; exits `grill-requirements:104`, `grill-solution:115` | accept `DIAGNOSIS.md`; no PRD; size call | `to-sdd/SKILL.md:19,70` needs PRD + INDEX.md; `AGENTS.md:94`, `README.md:480,698,741`; no size-call row in `GRILL-LOG-FORMAT.md` | extends |

## Landmines

- Confirmed: `BEHAVIORS.md:47` needs heading `Phase 2.5 — Trace the path` in diagnose (`scripts/behavior_registry.py:283-299`); a row edit needs revision 1→2 (`:316-317`). Checked by `hooks/behavior-registry-gate.sh:22`, setup render (`skills/afk/setup/MANIFEST.md:251`), `hooks/behavior-drift.sh:29-41`; pinned by `scripts/tests/test_behavior_registry_gate.py:51`, `hooks/tests/hook-smoke.sh:571`, `scripts/tests/test_protected_branch_acceptance.py:1089`. Text under the heading is free.
- Descriptions of fix and grill-solution are unquoted YAML scalars; an added ": " fails `scripts/tests/test_skill_frontmatter.py:86`.
- `scripts/tests/test_glossary_usage.py:160` is green only while untracked `docs/afk/small-lane/` is on disk (5 terms from d346cfb lack a tracked consumer).
- Manifests load each subject as one directory entry (`.claude-plugin/plugin.json:23,25,26,48`, `.codex-plugin/plugin.json:13,15,16,38`); a new sibling `.md` needs no registration, but the wiring gate needs a referrer.
- No gate enforces the downstream-blind rule (`AGENTS.md:25`).

## Stale today

- `GLOSSARY.md:337` lists 5 miss classes (6 exist).
- `providers/PARITY.md:75` and `providers/CONFORMANCE.md:44` still list a diagnose gap.

## Frontier

- B14: other repositories, deployment manifests, live consumers (installed plugin caches, harness loaders).

## Unverified

- none in the ledger. Design-side open: whether `flaky` is a new execute token (`SDD.draft.md:98` vs `:552`).
