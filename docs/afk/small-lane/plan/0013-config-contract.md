## Goal
Make the configuration reader and setup keep the developer-settings contract `CONFIG.md` states: no developer value is read from the committed file, a bare clone derives no worktree location, a misspelled developer key is named wherever values are read, and an empty `developer:` block erases nothing. Each gap was found by the 0002 adversary and predates the small lane (D-7).

## Complexity
standard

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "developer settings of `afk:bug`"
- ADR: adr/design/0010-developer-settings-in-the-configuration-document.md — the settings keep their names and meaning

## Scope
- scripts/afk-config.py
- skills/afk/setup/scripts/developer_values.py
- skills/afk/setup/MANIFEST.md
- CONFIG.md
- CHANGELOG.md
- scripts/tests/test_afk_config*.py
- scripts/tests/test_setup_developer_values.py
- scripts/tests/test_setup_h6_probe.py

## Seams
- use: developer settings of `afk:bug` — changes how the keys resolve, not where they are documented (INV-026)

## Acceptance
- [ ] `afk-config.py validate` refuses a `developer:` block in the committed `.afk/config.yaml` and names that file; `resolve`, `developer_values.py status` and the H6 probe never take a developer value from it (PRD AC-040)
- [ ] From a bare clone, `resolve worktreeBasePath` derives nothing and exits as unset (PRD AC-040)
- [ ] A misspelled key under `developer:` in any layer is named on stderr by `resolve` and in `developer_values.py status`, not only by `validate` (PRD AC-040)
- [ ] An empty `developer:` block in a narrower layer leaves the broader layers' values in force, and `status` never lists one key as both missing and inherited (ADR-0010)
- [ ] Each case above has a test that runs the real command against a real git repository (ADR-0010)

## Produces
- scripts/afk-config.py#committed file holds no developer — the refusal message `validate` prints for a committed `developer:` block

## Consumes
- 0002-developer-settings CONFIG.md### Developer settings (K1–K5) — the contract this slice makes the code keep

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged`; grep the ## Produces anchor | gates pass; the refusal exists |
| unit | `afk-python -m pytest scripts/tests/test_afk_config.py scripts/tests/test_afk_config_init.py scripts/tests/test_setup_developer_values.py scripts/tests/test_setup_h6_probe.py -q` | each contract case holds |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh`, on Windows and WSL (CI) | nothing else broke |

## Context excerpts
> (CONFIG.md "Developer settings (K1–K5)") The committed `.afk/config.yaml` holds none of these keys: K1, K2 and K5 name a person, and a committed file never names a person. Resolution, highest first: the `developer:` value from any layer (checkout beats repository beats machine), then — for `worktreeBasePath` alone — a derived value, then nothing.
> (CONFIG.md "Developer settings (K1–K5)") A bare clone derives nothing and needs the key.
> (CONFIG.md "Developer settings (K1–K5)") an unknown key under `developer:` is a validation error, so a typo is named rather than silently ignored.
> (PRD AC-040) The developer settings that `/afk:bug` documents keep their names and meaning; their documentation has a new home.
> (0002 adversary, F1/F2/F4/F5) repros: `docs/afk/small-lane/plan/review/0002-developer-settings-adversary.md`

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
0002-developer-settings

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
