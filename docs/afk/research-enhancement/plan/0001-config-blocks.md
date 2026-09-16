# 0001-config-blocks — `research:` and `consultation:` config blocks

## Goal
Extend the config reader (`scripts/afk-config.py`) and its contract (`CONFIG.md`) with the two opt-in top-level blocks `research:` and `consultation:`: child-key validation one level down for each block and its nested maps (`dispatch`, `egress`, per-participant maps, routes), the rejection rules the PRD fixes (unknown key named; `challenge_rounds` > 1; `billing: false` without a participant `billing: api`; two participants whose shell names collide; a hard-spend-cap route on a destination whose CLI cannot enforce one), the hard default `billing: subscription_only`, and the `AFK_CFG_*` shell view of both blocks. Absent blocks leave every existing reader unchanged. Pinned by `scripts/tests/test_afk_config.py` (config-key prior art) and the `CONFIG.md` drift test.

## Complexity
standard

## Design refs
- SDD: SDD.md#§3 row "config reader top-level keys" — the surface: `research:` and `consultation:` blocks; unknown child keys rejected with the key named; `export-shell` tolerant
- SDD: SDD.md#§5 "Feature flags" — defaults: `research:` absent = off; `consultation.enabled` false; `consultation.billing` `subscription_only`; `consultation.unavailable` `single`; cross-provider Claude route `enabled` false
- SDD: SDD.md#§5 "AuthZ" row "Set billing, no_training, credits" — the reader rejects `billing: false` without `billing: api`
- SDD: SDD.md#§6 invariant I-2 — at most 1 challenge round, guardian = config reader validation
- SDD: SDD.md#§8 row "config reader" — public interface `validate`, `get`, `export-shell` as today
- SDD: SDD.md#§14 row "config reader `TOP_LEVEL` and `export-shell` flattening" — landmines: shell-name collisions; `CONFIG.md` drift test covers `CHILD_KEYS` blocks only
- ADR: adr/requirements/0005-subscription-only-billing-with-credit-declarations.md — `billing` default; `credits: disabled` per destination
- ADR: adr/requirements/0002-no-training-declared-per-destination.md — `no_training` declared per destination
- ADR: adr/design/0004-gate-before-spawn-and-staging.md — declarations are the administrator's evidence; one config switch for the cross-provider Claude route

## Scope
- scripts/afk-config.py
- CONFIG.md
- scripts/tests/test_afk_config.py

## Seams
- implement: §14 row "config reader `TOP_LEVEL` and `export-shell` flattening (`scripts/afk-config.py:541,978-990`)" — this subtask owns the two new keys, their child validation, and the shell-view rule for participant names; seam-test = the `test_afk_config.py` cases below (INV-002)

## Acceptance
- [ ] `TOP_LEVEL` gains exactly `research` and `consultation`; a config without either block validates and exports exactly as before (SDD §14 row "config reader `TOP_LEVEL` and `export-shell` flattening")
- [ ] An unknown key under `research:` or `consultation:` (any nesting level the schema names) makes `validate` exit 2 naming the key by its full dotted path (PRD AC-033)
- [ ] `consultation.challenge_rounds` greater than 1 is rejected at validation with the key named (PRD AC-013)
- [ ] `consultation.billing: false` with any participant lacking `billing: api` is rejected at validation; when every participant declares it, validation passes and `get consultation.billing` returns `false` (PRD AC-034)
- [ ] Two participants whose names differ only by `-`, `_`, `.` or case are rejected at validation with both names printed (SDD §14 "Accepted compatibility-audit findings" (1))
- [ ] A route with a hard spend cap on a destination whose CLI cannot enforce one is rejected at validation with the destination named (PRD AC-037)
- [ ] With no `consultation.billing` key, `get consultation.billing` returns `subscription_only` (SDD §5 "Feature flags")
- [ ] The cross-provider Claude route is a single key defaulting to `false`; the reader accepts `enabled: true` there and nothing else enables the route (PRD AC-042)
- [ ] `export-shell` flattens both blocks to `AFK_CFG_*` names; every pre-existing `AFK_CFG_*` name is unchanged (SDD §3 row "config reader top-level keys")
- [ ] `CONFIG.md` schema table carries both blocks with every child key the reader accepts; the drift test in `test_afk_config.py` stays green (SDD §14 row "config reader `TOP_LEVEL` and `export-shell` flattening")
- [ ] Implements the public interface in SDD §8 row "config reader" unmodified: `validate`, `get`, `export-shell` (SDD §8)
- [ ] Conforms to ADR-0005 (requirements): `billing` defaults to `subscription_only`; `usage_credits: disabled` and `no_training` are per-destination declarations the reader accepts, never infers (ADR-0005)
- [ ] Every artifact in ## Produces compiles + matches its declared signature (SDD §8)
- [ ] Test fixtures use the real block names `research:` and `consultation:` and the real participant names `claude` and `codex`, never placeholders (PRD "Testing Decisions")

## Produces
- scripts/afk-config.py#RESEARCH_KEYS — the accepted child-key set of `research:`; `validate` rejects any other key by dotted path
- scripts/afk-config.py#CONSULTATION_KEYS — the accepted child-key set of `consultation:` (incl. nested `dispatch`, `egress`, `participants`, `routes` maps); `validate` rejects any other key by dotted path
- scripts/afk-config.py#validate_consultation_block — the rule set: challenge-round cap, `billing: false` guard, shell-name collision, hard-spend-cap route, Claude-route switch shape
- CONFIG.md#consultation.participants — the documented schema of both blocks, one row per child key, defaults stated

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `python -m py_compile scripts/afk-config.py` + grep every ## Produces anchor | code loads; declared symbols present |
| unit | `python -m pytest scripts/tests/test_afk_config.py -q` — new cases: unknown key named (AC-033), challenge cap (AC-013), `billing: false` guard (AC-034), shell-name collision, spend-cap route (AC-037), Claude-route switch default (AC-042), absent blocks unchanged, `export-shell` names, `CONFIG.md` drift | every rule above; seam-test for the config-reader seam |

## Context excerpts
> (PRD AC-033) An unknown key under `research:` or `consultation:` is rejected by the config reader with the key named.
> (PRD AC-034) `billing: false` with a participant lacking `billing: api` is rejected at validation; when accepted, the value appears in AR-3 and one journal line.
> (PRD AC-013) Exactly 1 challenge round runs; a configuration requesting more is rejected at validation.
> (PRD AC-037) A route that requires a hard spend cap on a destination whose CLI cannot enforce one blocks that route at validation with the destination named; no job runs.
> (PRD AC-042) The cross-provider `claude -p` route is off by default; with no explicit `enabled: true` on that route, no `claude` subprocess is spawned and the participant is reported `unsupported` (FC-2).
> (PRD §Solution) Four capabilities, all opt-in through `.afk/config.yaml`, absent config = today's behaviour
> (SDD §3 row "config reader top-level keys") `.afk/config.yaml` | repository administrator | `research:` and `consultation:` blocks; unknown child keys rejected with the key named (AC-033) | as today | validate exit 2 naming the key | — | schema 1 | **compatible**: one reader of the key list; `export-shell` tolerates the blocks on an older plugin (INV-002)
> (SDD §5 "Feature flags") `research:` block present | absent (off) · `consultation.enabled` | false · `consultation.billing` | `subscription_only` | admin-only change · `consultation.unavailable` | `single` (advisory); `block` per high-impact route | per route · cross-provider Claude route `enabled` | false | admin-only, after the policy conditions (ADR-0006)
> (SDD §5 "AuthZ" row "Set billing, no_training, credits") repository administrator in `.afk/config.yaml` | any agent | values echoed to `request.json` and one journal line (AC-034) | config reader rejects `billing: false` without `billing: api`
> (SDD §6 I-2) At most 1 challenge round | consultation run | config reader validation | config rejected, key named (AC-013)
> (SDD §8 row "config reader") `research:` and `consultation:` blocks; validation | as today: `validate`, `get`, `export-shell` | — | —
> (SDD §14 row "config reader `TOP_LEVEL` and `export-shell` flattening") one reader of the key list; unknown top-level key rejected; nested maps flatten to `AFK_CFG_*` (INV-006, INV-002) | +`research`, `consultation` keys; child validation for each block | every `AFK_CFG_` reader unchanged; validate-skew if a repo adds the blocks first (INV-002) | participant names differing only by `-`/`_`/`.`/case collide in the shell view; `CONFIG.md` drift test covers `CHILD_KEYS` blocks only; plugin ships before repos add blocks | extends
> (SDD §14 "Accepted compatibility-audit findings") (1) shell-view name collisions for participant keys are accepted with a validation rule that rejects two participants whose shell names collide
> (ADR-0005 requirements) `consultation.billing` defaults to `subscription_only`. A participant runs only when its auth gate reports a subscription login; API keys in the environment or the CLI config, gateway credentials and enterprise cloud modes are refused, never fallen back to (PRD AC-024, AC-025). Quota exhaustion ends the participant for the window (AC-026). Because a subscription CLI may draw an enabled credit balance silently, the administrator declares `credits: disabled` per destination
> (PRD AC-041) A `subscription_only` route requires the participant declaration `usage_credits: disabled` (the config spelling of the `credits: disabled` declaration in ADR-0005)
> (ADR-0002 requirements) The repository administrator declares `no_training` per destination in `.afk/config.yaml`
> (ADR-0006 requirements) (d) the cross-provider `claude -p` route is opt-in and off by default, behind one config switch so that decision B (written Anthropic guidance required before enabling) would change one key only.
> (PRD "Testing Decisions") Prior art: `scripts/tests/test_afk_config.py` for config keys

## Parent PRD
docs/afk/research-enhancement/PRD.md

## Parent SDD
docs/afk/research-enhancement/SDD.md

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
