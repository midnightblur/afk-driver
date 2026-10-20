# INV-016 — fix, diagnose and to-ticket files; what a new file or script must pass

feat-small-lane@d346cfb · closed-with-frontier · 13/14 boundaries · unverified 3 (load-bearing 0) · ledger: COVERAGE.json (11848 nodes, 51 claims)

## Answer

**The 3 skills: 9 files.**

| File | Read by |
|---|---|
| `fix/SKILL.md` | execute `:67,77,93,123`; preflight `:99,125`; `review/SKILL.md:196`; `refactor-safety.md:10`; `retro/SKILL.md:69`; `grill-requirements/ROUND.md:162` |
| `fix/ESCAPE-ANALYSIS.md` | `fix/SKILL.md:59`; `lessons/LEDGER-FORMAT.md:80` (lockstep) |
| `fix/WORKFLOW-FEEDBACK.md` | `fix/SKILL.md:79` |
| `diagnose/SKILL.md` | `fix/SKILL.md:12,31,38,112` (Phase 5 and 6 pointers); `BEHAVIORS.md:47`; `CAPABILITIES.md:68` |
| `diagnose/scripts/hitl-loop.template.sh` | `diagnose/SKILL.md:38`; MANIFEST C1 |
| `to-ticket/SKILL.md`, `REFERENCE.md` | `fix/SKILL.md:67`; to-prd; SPINOFF-TICKET; INDEX-FORMAT |
| `to-ticket/scripts/publish_prd.py`, `publish_meeting.py` | `SKILL.md:45,79`; both import root `tracker_api` (`:61-67`) |

No test reaches any of the 9 files directly.

**Scripts and tests.**
- Paths are `${AFK_PLUGIN_ROOT}/…` (`AGENTS.md:202`). to-ticket `:45,79` and diagnose `:38` use skill-relative paths (inferred deviation).
- `afk-python` is the only interpreter name (native-contract check J, `:442-477`).
- CI runs `afk-python -m pytest scripts/tests -q` and `hook-smoke.sh` on ubuntu and on windows under Git Bash (`tests.yml:20-26,64,67`).
- **The 8 tests under `skills/*/scripts/tests/` run in no CI step.**
- Tests load a script by path (`test_publish_bug.py:26-33`).

**Gates for a new file.**

| Gate | Sibling `.md` | Script |
|---|---|---|
| skill-registry A/B/D/F | no (SKILL.md and agents only) | no |
| native-contract A, J, K, N | yes | J and N |
| native-contract I (LF) | no | .sh only |
| genericity 0b | yes | yes |
| genericity 1-3 | yes | no |
| comment gate (≤2 lines) | no | yes |
| FRESHNESS same-commit; MANIFEST on a new dependency | yes | yes |
| `/afk:setup audit` §3 cited paths resolve | yes | — |
| wiring-gate: named by another file or an IOU | yes | yes (tests exempt) |

No gate checks the LANGUAGE.md read-first pointer on sibling files.

**Pointers across skill folders.**
- About 110–130 lines point into another skill's folder:
  - about 90 from the plugin root;
  - 16 with `../`;
  - 5 with `${AFK_PLUGIN_ROOT}`.
- fix and to-ticket already do this; diagnose does not.
- No gate checks that a pointer's target exists; only audit §3 does.
- Moving fix Phase 2 or diagnose Phases 5–6 would break `ROUND.md:162` and `fix/SKILL.md:38,112`, and no gate would fail.

**`/afk:bug` removal size.**
- The skill has 7 files and 909 lines.
- Outside it, 51 lines in 20 files reference it, plus `scripts/tests/test_publish_bug.py`.
- These block a commit or CI:
  - both plugin manifests (skill-registry-gate `:113-115`; native-contract `:207-208`);
  - `test_publish_bug.py` (CI pytest);
  - `GLOSSARY.md:246-272` (inferred, if its terms stay).
- The other references go stale with no gate: AGENTS.md, README.md, FRESHNESS.md, MANIFEST.md, skills/afk/AGENTS.md, gc, CAPABILITIES.md, CONFIG.md:136, SPINOFF-TICKET.md, jira CONTRACT.md, hooks/README.md, PARITY.md, `afk-config.py:69`, `create-worktree:63`, `test_tracker_create_assignee.py:3`, lessons LEDGER-FORMAT, to-meeting-d.

## Findings

- `bug/CONFIG.md` is the only home of the developer-key contract, which execute and to-ticket still read. AC-040 needs a new home for it.
- The glossary test already reports 5 small-lane terms as unconsumed on the tracked tree.
- Validator defect: `LEDGER-FORMAT.md:79-82` allows an `irrelevant` read-site node, but `validate_coverage.py:355` rejects it.
- Plugin defect: merge_fragments seed placeholders (11159 dropped before the fold).

## Unverified

- Seed name forms beyond those searched.
- No gate was run on a hypothetical new file.
- `test_plugin_source_gates` was not run with a failing tracked file.

## Frontier

B14: other repositories, harness loaders, installed caches.

Written by the orchestrator from the investigation's reply; the investigation's own REPORT.md write was refused.
