# 0004-placement — the one placement module: root rules and the worktree folder

## Goal
Add the placement module that owns catalog R and the worktree folder of a listed repository: the root with its state (confirmed, suggested, refused with the failed rule), the target for a new worktree (`<root>/<short name>/<worktree name>`), and a check of a chosen target (yes, not listed, or refusal with the rule). It reads only the machine file (single-file parse) and the repository list, compares by path text first, and starts git only for unusual layouts. The creator, the move helper and the guard ask it; none re-applies a rule.

## Complexity
complex

## Review
opt-in: design-quality

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row "placement (new)"
- SDD: SDD.md#§9 L8 — Tactical Patterns — row "root and short-name rules" (Chain of Responsibility)
- SDD: SDD.md#§6 L5 — Domain Model — invariants "the root passes every catalog R rule" and "an agent's worktree of a listed repository sits at `<root>/<short name>/<name>`"
- SDD: SDD.md#§10 NFRs — placement import plus machine-file parse ≤ 20 ms
- ADR: adr/design/0002-one-placement-guardian.md — one placement module guards every worktree folder
- ADR: adr/requirements/0001-one-worktree-root.md — one root per machine
- ADR: adr/requirements/0006-root-layout.md — short name, then worktree name

## Scope
- scripts/placement.py
- scripts/tests/test_placement.py

## Seams
- use: `afk-config.py` merge in `afk_config` (`load`, `validate`, `get`, `resolve`) — the single-file parse of the machine file, never the full merge (INV-013)

## Acceptance
- [ ] The root is `developer.worktreeRoot` from the machine file when set (state confirmed); else the old machine `developer.worktreeBasePath` when it passes catalog R; else the suggestion `repo-worktrees` in the home folder (state suggested); each candidate is checked against catalog R (PRD §Worktree root AC-040, AC-042, AC-043)
- [ ] For every rule in catalog R, a root or short name that fails the rule returns that rule's id and reason, first failure first, in catalog order: R-01 not absolute (including a relative or `~` root), R-02 the root or a parent is inside a git repository, R-03 missing (reported so setup creates it), R-04 a space in the path (a warning when a listed repository builds with Maven), R-05 a short-name clash, R-06 a short-name folder absent or made for another repository, R-07 checked on every read (PRD §Worktree root AC-041; PRD §Catalog R)
- [ ] A root value in any repository file is never read as the root (PRD §Worktree root AC-044)
- [ ] The target for a new worktree of a listed repository is `<root>/<short name>/<worktree name>`; for an unlisted repository placement answers "not listed" and the caller keeps today's behaviour (PRD §Worktree creation AC-050, AC-055)
- [ ] Checking a chosen target answers inside, not listed, or refused with the rule; links and drive-letter case are resolved on both sides; a relative or `~` target is made absolute before the check (SDD §14 row "guard `decide` on `git worktree add`, `move`, the `create-worktree` call, inline variables")
- [ ] Placement compares path text first and starts git only for unusual layouts (a `GIT_DIR` variable, a `core.worktree` setting, a submodule) (ADR-0002; SDD §14 accepted findings)
- [ ] Placement reads only the machine file and the repository list; a test asserts no other file is opened (SDD §3 owners table caption; SDD §10)
- [ ] Placement import plus machine-file parse stays within 20 ms, reported by the informational bench; the test asserts the file-read count, not the time (SDD §10; GRILL-LOG Verification grill C-23)
- [ ] Implements the public interface in SDD §8 row "placement (new)" unmodified: root with state; target for a new worktree; check a chosen target (SDD §8)
- [ ] Conforms to ADR-0002: one check per catalog R row in one chain, first failure returned; no caller re-applies a rule (ADR-0002)

## Produces
- scripts/placement.py#def root_state( — the root and its state: confirmed, suggested, or refused with the failed rule
- scripts/placement.py#def target_for( — `<root>/<short name>/<worktree name>` for a listed repository, or not listed, or refused rule
- scripts/placement.py#def check_target( — inside, not listed, or refusal naming the rule and `<root>/<short name>`
- scripts/placement.py#ROOT_RULES = — the catalog R chain, in catalog order

## Consumes
- 0002-settings-reader scripts/afk-config.py#def parse_single_file( — the machine file parsed without the merge
- 0003-repository-list scripts/repo_list.py#def find_entry( — the listed entry and short name for a path

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier + grep each ## Produces anchor | gates pass; declared symbols present |
| unit | `unit` tier; `scripts/tests/test_placement.py` with a sandbox home and real temporary git repositories: one test per catalog R row, confirmed / old base value / suggestion paths, listed vs unlisted, inside / beside / inside a checkout targets, relative and `~` targets, a space, a link, drive-letter case, a submodule | every root rule's outcome and the target check on real paths |
| unit | file-read count test: patch the open call, run `check_target` for a listed repository, assert only the machine file and the list file are read | the placement read budget |

## Context excerpts
> (ADR-0002) One placement module owns the root rules (one check per catalog R row, first failure returned) and the worktree folder. The creator, the move helper and the command guard all ask it. The creator runs every check before anything is made and refuses with exit 3. The guard, which reads its own environment, refuses an agent's `git worktree add`, `git worktree move` and creator call whose target is outside `<root>/<short name>`, and an agent command that sets `AFK_WORKTREE_FOLDER` or `AFK_ALLOW_PROTECTED` inline. Placement reads only the machine file and the repository list, compares by path text first, and starts git only for unusual layouts. Unlisted repositories are not checked.

> (SDD §8 row "placement (new)") root rules and worktree folder | root with state (confirmed, suggested, refused with rule); target for a new worktree; check a chosen target (yes or refusal with rule) | list, single-file parse | worktree root

> (PRD §Catalog R) R-01 the root is an absolute path | setup refuses it, names the rule · R-02 the root and none of its parents is inside any git repository | setup refuses it, names the repository · R-03 the root exists | setup creates it · R-04 the root path has no space | setup accepts it and warns when a listed repository builds with Maven: its worktrees share the default Maven cache · R-05 a repository's short name is its main checkout folder name | on a clash with another listed repository, setup asks for another short name · R-06 the short name's folder under the root is absent or was made by setup for that repository | setup asks for another short name · R-07 the root is checked on every read | agents refuse to create a worktree and name the failed rule

> (PRD §Worktree root) AC-040 Setup asks for the root once per machine and suggests `repo-worktrees` in the home folder. AC-041 For every rule in catalog R, a root or short name that fails the rule gets that row's outcome. AC-042 Until the developer confirms a root, agents use the suggestion if it passes catalog R. If it fails, agents refuse to create a worktree and say to run setup. AC-043 An existing machine-wide worktree base value becomes the root if it passes catalog R. If it fails, agents refuse to create a worktree until setup is answered. AC-044 A worktree root in any repository file is ignored with a warning.

> (SDD §4 machine file) `developer.worktreeRoot` | absolute path | absent: not confirmed, the suggestion `~/repo-worktrees` applies | catalog R on write and on every read · `developer.worktreeBasePath` | read as the root only while `worktreeRoot` is absent and the value passes catalog R

> (SDD §14 accepted findings) Placement on unusual layouts (a `GIT_DIR` variable, a `core.worktree` setting, a submodule) starts git and may exceed the 50 ms budget. Accepted: these layouts are rare, and a text-only check there would misjudge the target (R-7 F-2).

> (SDD §10) placement import plus machine-file parse (ms) | ≤ 20 | measured 18 plus under 1 (L7.5) | placement

## Parent PRD
docs/afk/setup-per-repo/PRD.md

## Parent SDD
docs/afk/setup-per-repo/SDD.md

## Blocked by
0002-settings-reader, 0003-repository-list

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
