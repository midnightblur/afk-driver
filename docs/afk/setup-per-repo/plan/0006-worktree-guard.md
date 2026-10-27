# 0006-worktree-guard — the command guard refuses an agent's worktree outside the root

## Goal
Extend the command guard so that, for a listed repository, an agent's `git worktree add`, `git worktree move` and worktree-creator call whose real target is outside `<root>/<short name>` (or cannot be worked out) is refused with the harness deny answer, and an agent command that sets `AFK_WORKTREE_FOLDER` or `AFK_ALLOW_PROTECTED` in front of itself is refused naming the variable. The guard asks placement; unlisted repositories, the developer, and a session launched with `AFK_ALLOW_PROTECTED=1` pass as today.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — rows "command guard on `git worktree add` and `git worktree move`", "Δ command guard on the creator call", "Δ command guard on inline variables"
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — AuthZ row "create a worktree of a listed repository"
- SDD: SDD.md#§10 NFRs — guard added time ≤ 50 ms on add and move; 0 new file reads on any other command
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "guard `decide` on `git worktree add`, `move`, the `create-worktree` call, inline variables"
- ADR: adr/design/0002-one-placement-guardian.md — the guard asks placement
- ADR: adr/requirements/0004-guard-binds-agents-only.md — no agent-settable bypass

## Scope
- hooks/lib/protected_branch_guard.py
- hooks/lib/worktree_placement_rule.py
- scripts/tests/test_protected_branch_guard.py
- scripts/tests/test_protected_branch_acceptance.py
- scripts/tests/test_worktree_placement_guard.py
- hooks/tests/bench-hooks.py

## Seams
- implement: guard `decide` on `git worktree add`, `move`, the `create-worktree` call, inline variables — placement verdict and refusal text in the deny answer (INV-007)

## Acceptance
- [ ] For a listed repository, an agent's `git worktree add` whose target resolves outside `<root>/<short name>` is refused with exactly: `refused to create a worktree outside the worktree root. Cause: <target> is outside <root>/<short name>. Move: create it under <root>/<short name>, or ask the developer.` and no bypass line (SDD §3 row "command guard on `git worktree add` and `git worktree move`"; PRD §Worktree creation AC-053)
- [ ] The same refusal applies to the destination of `git worktree move` (PRD §Worktree creation AC-053)
- [ ] The add target is found by the guard's own parser, which knows `-b`, `-B`, `--orphan` and `--reason`; the target is resolved against the command's folder, its `-C` folder and links, with drive-letter case resolved on both sides; a target held in a variable counts as not worked out and is refused (SDD §3 row "command guard on `git worktree add` and `git worktree move`"; SDD §14 row "guard `decide` on `git worktree add`, `move`, the `create-worktree` call, inline variables")
- [ ] For a listed repository, an agent's worktree-creator call whose `--parent` or `--dir` lies outside `<root>/<short name>` is refused with the same text (SDD §3 row "Δ command guard on the creator call")
- [ ] An agent command that sets `AFK_WORKTREE_FOLDER` or `AFK_ALLOW_PROTECTED` in front of itself is refused naming the variable, in every form the existing inline-variable rule reads (assignment, `export`/`declare`, `setx`, a PowerShell `env:` assignment) (SDD §3 row "Δ command guard on inline variables"; PRD §Worktree creation AC-054)
- [ ] A session the developer launches with `AFK_ALLOW_PROTECTED=1` still returns before `decide` and lifts every guard rule, this one included (SDD §14 row "guard `decide` on `git worktree add`, `move`, the `create-worktree` call, inline variables"; SDD §5)
- [ ] An inside target, an unlisted repository and the developer's own terminal pass (PRD §Worktree creation AC-055, AC-056)
- [ ] The two existing tests pinning "a plain `git worktree add` passes the guard" are reversed for listed repositories and kept for unlisted ones (PRD §Testing Decisions; SDD §3 row "command guard on `git worktree add` and `git worktree move`")
- [ ] On any command other than `git worktree add`, `git worktree move` and the creator call, the guard makes 0 new file reads; a test asserts the read count (SDD §10)
- [ ] The guard's added time on add and move for a listed repository is measured by the informational bench against the 50 ms budget (one cold run measured 57 ms) and reported; the test asserts no network call and the read count, not the time (SDD §10; SDD §13; GRILL-LOG Verification grill C-23)
- [ ] Conforms to ADR-0002: the guard asks placement for the verdict and re-applies no rule (ADR-0002)

## Produces
- hooks/lib/worktree_placement_rule.py#refused to create a worktree outside the worktree root — the deny text, cause and move
- hooks/lib/worktree_placement_rule.py#def parse_worktree_add( — the add parser knowing `-b`, `-B`, `--orphan`, `--reason`
- hooks/lib/worktree_placement_rule.py#AFK_WORKTREE_FOLDER — the inline variables the guard refuses for agents

## Consumes
- 0004-placement scripts/placement.py#def check_target( — inside, not listed, or refusal naming the rule

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier + grep each ## Produces anchor | gates pass; declared symbols present |
| unit | `unit` tier; `scripts/tests/test_worktree_placement_guard.py` drives the real guard hook with harness envelopes (agent detector on/off) in a sandbox home with a listed and an unlisted repository: add with each flag, move, `-C`, a link, a variable target, the creator call with `--parent` and `--dir`, each inline-variable form, the launch flag; asserts the deny JSON the harness reads and its exact text | the guard's real deny answer per route |
| unit | read-count test on a non-worktree command; informational timing in `hooks/tests/bench-hooks.py` | the 0-read and 50 ms budgets |
| smoke | `smoke` tier | every hook still runs end to end |

## Context excerpts
> (SDD §3 row "command guard on `git worktree add` and `git worktree move`") harness, before every agent shell command | an agent command whose real target is inside `<root>/<short name>` / an agent command whose target is outside it or cannot be worked out | the target of add and the destination of move, resolved against the command's folder, its `-C` folder and links; a target in a variable counts as not worked out; Δ add has its own parser knowing `-b`, `-B`, `--orphan`, `--reason` | nothing: the command runs | the harness deny answer: `refused to create a worktree outside the worktree root. Cause: <target> is outside <root>/<short name>. Move: create it under <root>/<short name>, or ask the developer.` No bypass line | read only | breaking for agents in listed repositories; two tests pinning "a plain worktree add passes" reverse for listed repositories; unlisted: unchanged

> (SDD §3 row "Δ command guard on the creator call") harness | as above | for a listed repository, the creator's `--parent` or `--dir`; outside `<root>/<short name>` is refused | runs | deny answer as above | read only | new refusal

> (SDD §3 row "Δ command guard on inline variables") harness | none for agents | an agent command that sets `AFK_WORKTREE_FOLDER` or `AFK_ALLOW_PROTECTED` in front of itself | — | deny answer naming the variable | read only | new refusal; a session the developer launches with `AFK_ALLOW_PROTECTED=1` keeps lifting every guard rule

> (SDD §14 row "guard `decide` on `git worktree add`, `move`, the `create-worktree` call, inline variables") add passes; move checked only against protected resources; inline `LAVISH_AXI_HOST` already refused (INV-007, INV-014) | own add parser knowing `-b`, `-B`, `--orphan`, `--reason`; listed repositories only; placement by path prefix first, git only for unusual layouts; links and drive-letter case resolved on both sides | every agent shell command; two tests pinning "a plain add passes" reverse for listed repositories (INV-014, INV-019) | `AFK_ALLOW_PROTECTED` from the launch environment still returns before `decide`; refusal text names cause and move | reworked (ADR-0002)

> (SDD §5 AuthZ row "create a worktree of a listed repository") an agent under `<root>/<short name>`; developer anywhere from their own terminal | an agent anywhere else | skills name the worktree creator | creator refuses (exit 3); guard refuses `git worktree add`, `move` and Δ the creator call outside the folder, and Δ inline `AFK_WORKTREE_FOLDER` / `AFK_ALLOW_PROTECTED`; Δ a session the developer launches with `AFK_ALLOW_PROTECTED=1` lifts this rule, as it lifts every guard rule

> (SDD §10) guard added time on `git worktree add` and `move`, listed repository (ms) | ≤ 50, no network call | timing in the guard seam test; measured 2 to 13 over 21 runs, 1 cold run 57 (L9-S2) | placement · guard added time on any other command (ms) | 0 new file reads | guard test asserts no read | guard

> (ADR-0004 requirements) The guard refuses an agent's worktree of a listed repository outside the root, with no agent-settable bypass. A developer can still create a worktree anywhere from their own terminal, because the requirement covers worktrees created by future agents only.

> (PRD §Worktree creation) AC-053 An agent's `git worktree add` or `git worktree move` for a listed repository whose real target is outside `<root>/<short name>` is refused. The refusal names the root folder. AC-054 After a refusal, the agent creates the worktree under the root or asks the developer. No agent-settable bypass exists.

## Parent PRD
docs/afk/setup-per-repo/PRD.md

## Parent SDD
docs/afk/setup-per-repo/SDD.md

## Blocked by
0004-placement

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
