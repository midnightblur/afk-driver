## Goal
Move the developer settings K1–K5 out of the bug skill's own configuration page into plugin-root `CONFIG.md`, keeping each key's id, name and meaning, and make the literal `none` read as unset for both the assignee and the reviewer.

## Complexity
mechanical

## Design refs
- SDD: SDD.md#§4 L3 — Data Architecture — row "Tracker settings read"
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "developer settings of `afk:bug`"
- ADR: adr/design/0010-developer-settings-in-the-configuration-document.md — settings and their rule live in `CONFIG.md`; ids kept

## Scope
- CONFIG.md
- skills/afk/bug/CONFIG.md
- scripts/afk-config.py
- skills/afk/setup/scripts/developer_values.py
- skills/afk/setup/MANIFEST.md
- FRESHNESS.md
- README.md
- scripts/create-worktree
- CHANGELOG.md
- scripts/tests/test_afk_config*.py
- scripts/tests/test_setup_developer_values.py

## Seams
- implement: developer settings of `afk:bug` — move the K1-K5 documentation and widen the `none` rule (INV-026)

## Acceptance
- [ ] `CONFIG.md` documents K1–K5 with the same ids, key names and meaning the bug skill's page gives today (PRD AC-040)
- [ ] The literal `none` reads exactly as an unset key for both the assignee and the reviewer, and the test that pinned the reviewer's literal `none` now asserts unset (SDD §14 row "developer settings of `afk:bug`")
- [ ] `CONFIG.md` states the rule for a missing assignee or reviewer: asked when a person is present, otherwise left unassigned and reported (SDD §14 row "developer settings of `afk:bug`")
- [ ] The bug skill's page keeps only a pointer to `CONFIG.md` for these keys, and every other home that named that page for them (`CONFIG.md`, `MANIFEST.md`, `FRESHNESS.md`, `README.md`) points at `CONFIG.md` (SDD §14 row "developer settings of `afk:bug`")
- [ ] Conforms to ADR-0010 design — no silent pattern substitution (design ADR-0010)

## Produces
- CONFIG.md### Developer settings (K1–K5) — heading of the section that owns the five keys and their rule

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged`; grep the ## Produces anchor | gates pass; the section exists |
| unit | `afk-python -m pytest scripts/tests/test_afk_config.py scripts/tests/test_afk_config_init.py scripts/tests/test_setup_developer_values.py -q` | `none` is unset for both keys; ids and names unchanged |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh`, on Windows and WSL | nothing else broke |

## Context excerpts
> (SDD §4 row "Tracker settings read") one in-review key on both trackers; scaffold key renamed; developer settings keep their K1-K5 ids; `none` means unset for assignee and reviewer (§14)
> (SDD §14 row "developer settings of `afk:bug`") INV-026: `bug/CONFIG.md:35-72` K1-K5, fail closed; `test_afk_config.py:356-380` | move to `CONFIG.md`; missing assignee or reviewer asked, or left unassigned and reported hands-off; literal `none` = unset for both keys; keep the K1-K5 ids | INV-026: `CONFIG.md:136`, `MANIFEST.md:40,53,127,213-216,914`, `FRESHNESS.md:78`, `README.md:340`; `developer_values.py:148` | only the assignee maps `none` today (`afk-config.py:830`) and `test_afk_config_init.py:206` pins the reviewer's literal `none`; fail-closed applies only to assignee and reviewer (`bug/CONFIG.md:59-61`)
> (PRD AC-040) The developer settings that `/afk:bug` documents keep their names and meaning; their documentation has a new home.

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
