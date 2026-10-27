# 0010-setup-walk — `/afk:setup` walks every listed repository from any folder

## Goal
Make `/afk:setup` (no argument) and `/afk:setup repo <short name or path>` walk the repository list from any folder: machine rows once (root, notes, the shown `codex` app and trust steps), then each repository row as one plain script run in that main checkout as working folder and project folder, asking only what has no value at its owner, and ending in one report table (complete, asked, or failed with cause and rerun command). Rewrite the setup register with a scope mark per row, the docs that name the old behaviour, the freshness registry and the changelog's major-version upgrade section.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — rows "`/afk:setup` (no argument)" and "`/afk:setup repo <short name or path>`"
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — AuthZ rows for list edits, settings, root, worktree removal, trust
- SDD: SDD.md#§7 L6 — Process & Coordination — "setup walk", "worktree cleanup"; failure row "step fails in one repository"; side effects "remove a worktree inside another repository", "install git hooks in another repository", "trust the root in a harness; set the `codex` app root"
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows "`codex` app worktree root" and "harness folder trust"
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "setup walk over `setup_secrets`, `developer_values`, `install-git-hooks` register rows"; accepted finding on the term "worktree root"
- ADR: adr/design/0006-setup-walk-in-target-checkout.md — each repository step runs in that main checkout
- ADR: adr/design/0007-ignore-misplaced-values-at-once.md — the release is major

## Scope
- skills/afk/setup/SKILL.md
- skills/afk/setup/MANIFEST.md
- skills/afk/setup/AUDIT.md
- skills/afk/setup/scripts/setup_walk.py
- skills/afk/setup/scripts/repo_step_*.py
- skills/afk/setup/scripts/worktree_cleanup.py
- scripts/tests/test_setup_walk*.py
- scripts/tests/test_worktree_cleanup.py
- CONFIG.md
- README.md
- FRESHNESS.md
- CHANGELOG.md
- GLOSSARY.md
- SAFETY.md
- PROVIDERS.md

## Seams
- implement: setup walk over `setup_secrets`, `developer_values`, `install-git-hooks` register rows — scope mark per row, loop over listed repositories, one script per repository step (INV-018)
- implement: setup walk over `setup_secrets`, `developer_values`, `install-git-hooks` register rows — §9b "`codex` app worktree root" and "harness folder trust": shown steps only (INV-018)

## Acceptance
- [ ] `/afk:setup` run from any folder offers the repository list with add and remove; add asks the developer to paste a path and suggests no folders; a gone entry is reported with remove or a new path offered (PRD §Repository list AC-001, AC-002, AC-006)
- [ ] For each listed repository, setup asks only for settings with no value at their owner (catalog S); a run with nothing missing asks nothing and reports every repository complete (PRD §Setup walk AC-010; SDD §3 row "`/afk:setup` (no argument)")
- [ ] `/afk:setup repo <short name or path>` selects the repository by a listed short name, or by a path whose main checkout is listed (main checkout, worktree or subfolder); an unlisted path is offered for adding; an unknown short name is refused with the list of names; the developer may name one setting to change and nothing else is asked (SDD §3 row "`/afk:setup repo <short name or path>`"; PRD §Setup walk AC-011)
- [ ] Every register row carries a scope mark, machine or repository; machine rows run once; each repository row runs as one plain script with that main checkout as working folder and project folder, never a chained shell line; the register's inline shell checks move into those scripts (ADR-0006; SDD §14 row "setup walk over …")
- [ ] Every per-repository step acts on the repository it is given, whatever the current folder is; the walk never runs `init` in another repository (PRD §Setup walk AC-012; ADR-0006)
- [ ] A failed step records status `failed` with its reason and rerun command, and the walk goes on; a forge host that refuses or cannot be reached fails that repository with nothing saved for it (SDD §7 failure row "step fails in one repository"; PRD §Accounts AC-030)
- [ ] A later `/afk:setup repo <name>` saves the account once the host accepts it; after saving, setup suggests that account as change assignee and work item assignee (PRD §Accounts AC-031, AC-032)
- [ ] The forge remote is asked only when the clone has more than 1 remote (PRD §Setting owners AC-026)
- [ ] Setup prints the secret-step commands and never runs them; the long-path register line names `longpaths` (PRD §Setup walk AC-013; SDD §14 row "secret step `setup_secrets`")
- [ ] An existing machine-wide Jira sign-in becomes the sign-in for its site, and setup asks which listed repositories use that site (PRD §Accounts AC-036)
- [ ] Setup asks for the worktree root once per machine, suggesting `repo-worktrees` in the home folder; each catalog R rule gives its outcome; a missing root is created (PRD §Worktree root AC-040, AC-041; PRD §Catalog R R-03)
- [ ] When a harness asks to trust the root, setup shows the step to trust it once (PRD §Worktree root AC-045); live check recorded in `plan/JOURNAL.md`: in `claude` and in `codex`, a worktree in a subfolder raises no further trust prompt (SDD §13; SDD §9b row "harness folder trust")
- [ ] When the `codex` app is installed, setup shows the step to set its worktree root to the same root; when it is not, setup shows nothing; how setup detects the app is decided here and recorded in `plan/DECISIONS.md` (PRD §Worktree root AC-046; VERIFICATION-PLAN.md Gaps surfaced)
- [ ] Setup lists worktrees that sit inside another repository, shows each clean one as idle or unknown, offers to remove it on the developer's yes with `git worktree remove` without force, keeps every other one and keeps the branch (PRD §Existing worktrees AC-061; SDD §7 side effect "remove a worktree inside another repository")
- [ ] The walk lists ignored values (from the reader) and offers each move to its owner's file; it runs copy deletion and reports each deleted and kept copy (ADR-0007; PRD §Setting owners AC-024)
- [ ] A repository with no committed AFK file passes the setup check for the AFK file (PRD §Setting owners AC-025)
- [ ] Only a setup run the developer asks for reads or writes another listed repository (PRD §Session scope AC-080)
- [ ] `CONFIG.md`, README section 4 and about 30 doc lines describe the new behaviour; "worktree root" names only the folder holding every worktree and one worktree's own folder becomes "the worktree's top folder" in about 7 places (SDD §14 row "setup walk over …"; SDD §14 accepted findings)
- [ ] The freshness registry gains rows for the four new modules (safe writer, repository list, placement, forge account helper) (SDD §14 row "setup walk over …")
- [ ] `CHANGELOG.md` carries the next major version's upgrade section listing every changed behaviour (SDD §14, HL-6) and "run /afk:setup once on each machine" (ADR-0007)
- [ ] Conforms to ADR-0006 — no silent pattern substitution (ADR-0006)

## Produces
- skills/afk/setup/scripts/setup_walk.py#def walk_repositories( — machine rows once, then each repository row in its main checkout; the report table
- skills/afk/setup/scripts/setup_walk.py#def select_repository( — short name or path to a listed entry; unlisted offered; unknown refused with names
- skills/afk/setup/scripts/worktree_cleanup.py#def worktrees_inside_repositories( — worktrees inside another repository, each clean / idle / unknown
- skills/afk/setup/MANIFEST.md#scope: repository — the per-row scope mark

## Consumes
- 0003-repository-list scripts/repo_list.py#def all_entries( — every listed repository; setup only
- 0003-repository-list scripts/repo_list.py#def add_repository( — add a pasted path
- 0004-placement scripts/placement.py#def root_state( — the root and each failed rule for the root question
- 0007-forge-account skills/afk/setup/scripts/forge_account_check.py#def check_forge_account( — save only when the host accepts
- 0008-jira-sign-in skills/afk/setup/scripts/jira_account_check.py#def check_jira_account( — the site accepts the sign-in
- 0009-settings-writer skills/afk/setup/scripts/developer_values.py#def write_setting( — one key to its owner's file
- 0009-settings-writer skills/afk/setup/scripts/copy_deletion.py#def delete_team_copies( — deleted and kept copies

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier + grep each ## Produces anchor | gates pass; declared symbols present |
| unit | `unit` tier; `scripts/tests/test_setup_walk.py` in a sandbox home with 3 temporary repositories, stub `gh`/`glab`/Jira on PATH, the walk run from outside all of them: each repository step's working folder is its main checkout; nothing missing asks nothing; a refused host fails one repository and the walk goes on; the report rows and rerun commands | the walk on real repositories |
| unit | `select_repository` per input: short name, main checkout, worktree, subfolder, unlisted path, unknown name | repository lookup |
| unit | `scripts/tests/test_worktree_cleanup.py`: a clean worktree inside another repository offered, a changed one kept, the remove without force, the branch kept | cleanup |
| smoke | `smoke` tier | hooks end to end |

## Context excerpts
> (ADR-0006) Register rows carry a scope mark, machine or repository. Machine rows run once. For each listed repository, each repository row runs as one plain command, a script, with that main checkout as its working folder and as the session's project folder. The register's inline shell checks move into those scripts. The walk never runs `init` in another repository and changes another repository's files only through its scripts. A failed step records status `failed` with its reason and rerun command, and the walk goes on.

> (ADR-0007) The release is the next major version, with a changelog upgrade section listing every changed behaviour (SDD §14, HL-6) and "run /afk:setup once on each machine".

> (SDD §3 row "`/afk:setup` (no argument)") developer | developer / teammate; an agent on its own initiative | none | one report table: per repository complete, asked, or failed with cause and rerun command | a forge host refuses or cannot be reached: that repository failed, nothing saved for it, walk goes on | asks only what is missing; nothing missing asks nothing | compatible: base, audit and teardown keep their meaning

> (SDD §3 row "`/afk:setup repo <short name or path>`") a listed short name, or a path whose main checkout is listed; an unlisted path is offered for adding; an unknown short name is refused with the list of names; the developer may name one setting to change | as above, one repository | new

> (SDD §14 row "setup walk over `setup_secrets`, `developer_values`, `install-git-hooks` register rows") each step acts on the working folder; multi-line shell probes in the register (INV-002, INV-011, INV-018) | scope mark per row; loop over listed repositories; each repository check a script run in that main checkout with the project folder set; status `failed` | every setup step; `CONFIG.md`, README section 4 and about 30 doc lines rewritten; the freshness registry gains rows for the four new modules (INV-018, INV-020) | never run `init` in another repository; never a chained shell line | extends (ADR-0006)

> (SDD §14 accepted findings) One term changes meaning: "worktree root" now names only the folder holding every worktree; one worktree's own folder becomes "the worktree's top folder" (the folder `git rev-parse --show-toplevel` prints) in about 7 places (R-7 L9-15b). Accepted as a doc rewrite in the setup-walk subtask.

> (SDD §7 side effects) remove a worktree inside another repository | setup, on the developer's yes per worktree | clean, and Δ idle (every recorded session dead) or unknown (no record), marked as such; `git worktree remove` without force; the guard checks again; branch kept | `git worktree add` from the kept branch · install git hooks in another repository | setup walk, per listed repository | existing step, run in that repository · trust the root in a harness; set the `codex` app root | shown by setup | the developer does it

> (SDD §9b) `codex` app worktree root | `codex` app | keeps its own root, set in its settings screen (unverified-external) | none: setup shows the step | none: shown step only · harness folder trust | `claude`, `codex` | trust extends to subfolders (unverified-external, AC-045) | an extra trust prompt | live check before build

> (PRD §Repository list) AC-001 Setup run from any folder offers the repository list, with add and remove. AC-002 On add, setup asks the developer to paste a path. It does not suggest folders. AC-006 An entry whose folder is gone is reported, and setup offers remove or a new path.

> (PRD §Setup walk) AC-010 For each listed repository, setup asks only for settings that have no value at their owner (catalog S). A run with nothing missing asks nothing and reports every repository complete. AC-011 Setup can change one setting of one repository without asking anything else. AC-012 Every per-repository setup step acts on the repository it is given, whatever the current folder is. AC-013 The secret step runs in the developer's own terminal, never in an agent shell.

> (PRD §Accounts) AC-031 Recovery after AC-030: a later setup run for that repository alone saves the account once the host accepts it. AC-032 After it saves the account, setup suggests that account as the change assignee and the work item assignee. AC-036 An existing machine-wide Jira sign-in becomes the sign-in for its site. Setup asks which listed repositories use that site.

> (PRD §Worktree root) AC-045 When a harness asks to trust the root, setup trusts it once, and a worktree in any subfolder needs no further trust prompt (unverified premise: `claude` and `codex` extend folder trust to subfolders). AC-046 When the `codex` app is installed, setup shows the step to set its worktree root to the same root (unverified premise: the `codex` app keeps its worktrees under its own root, movable only in its settings screen, and names its own folders there).

> (PRD §Existing worktrees) AC-061 Setup lists worktrees that sit inside another repository. It offers to remove each one that is clean and idle, and keeps every other one.

> (PRD §Session scope) AC-080 A session reads only its own repository's settings and accounts. Only a setup run the developer asks for reads or writes another listed repository.

## Parent PRD
docs/afk/setup-per-repo/PRD.md

## Parent SDD
docs/afk/setup-per-repo/SDD.md

## Blocked by
0003-repository-list, 0004-placement, 0007-forge-account, 0008-jira-sign-in, 0009-settings-writer

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
