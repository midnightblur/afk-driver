# 0005-worktree-creator — the creator, the worktree-create hook and the move helper ask placement

## Goal
Make every plugin route that creates a worktree of a listed repository land it at `<root>/<short name>/<worktree name>`: the worktree creator in every mode (`--name`, `--branch --dir [--parent]`) asks placement and refuses with exit 3 through its own exit path before anything is made; the `claude` worktree-create hook keeps its output shape; the move helper's hint takes its path from the same placement call; `afk-config.py resolve worktreeRoot` replaces `resolve worktreeBasePath`, with every caller moved in the same commit.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — rows "`create-worktree --name <name>`", "`create-worktree --branch <b> --dir <d> [--parent <p>]`", "worktree-create hook (`claude`)", "`afk-config.py resolve worktreeRoot`"
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "`create-worktree` `--name`, `--branch`, `--dir`, `--parent`" and "move helper `h2_move` hint"
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows "git worktree" and "`claude` worktree-create hook"
- SDD: SDD.md#§13 Open Questions — live check of hook exit 3 owned by this subtask
- ADR: adr/design/0002-one-placement-guardian.md — the creator runs every check before anything is made
- ADR: adr/requirements/0004-guard-binds-agents-only.md — the developer creates a worktree anywhere

## Scope
- scripts/create-worktree
- hooks/worktree-create.sh
- hooks/lib/h2_move.py
- scripts/afk-move.py
- scripts/afk-config.py
- skills/afk/bug/SKILL.md
- skills/afk/bug/CONFIG.md
- scripts/tests/test_create_worktree*.py
- scripts/tests/test_h2_move.py
- scripts/tests/test_worktree_create_hook.py
- scripts/tests/test_existing_worktree_outside_root.py
- scripts/tests/create-worktree-smoke.sh

## Seams
- implement: `create-worktree` `--name`, `--branch`, `--dir`, `--parent` — §9b "git worktree": git runs only after every placement check passed (INV-014)
- implement: move helper `h2_move` hint — the suggested path comes from the creator's placement call (INV-014)
- use: `create-worktree` `--name`, `--branch`, `--dir`, `--parent` — §9b "`claude` worktree-create hook": the harness uses the printed path and fails the creation on a non-zero exit (INV-019)

## Acceptance
- [ ] `create-worktree --name <name>` for a listed repository prints `WORKTREE_PATH=<root>/<short name>/<name>` as the last stdout line and exits 0; for an unlisted repository it lands inside the main checkout as today (SDD §3 row "`create-worktree --name <name>`"; PRD §Worktree creation AC-050, AC-055)
- [ ] When the root fails a catalog R rule, including a relative or `~` root, the creator exits 3 with `ERROR=worktree root: <rule> <reason> - run /afk:setup`, through its own exit path and not the error trap, and no worktree, branch or folder is made; every other failure exits 1 with `ERROR=<reason>` (SDD §3 row "`create-worktree --name <name>`"; PRD §Worktree root AC-041, AC-042)
- [ ] An existing destination is refused, and a refused run leaves no worktree (SDD §3 row "`create-worktree --name <name>`")
- [ ] In an agent session (the plugin's agent detector) for a listed repository, `create-worktree --branch <b> --dir <d> --parent <p>` with `<p>` outside `<root>/<short name>` exits 3 with `ERROR=parent <path> is outside <root>/<short name>` plus the fixing command; `~` and relative `--parent` values are made absolute first (SDD §3 row "`create-worktree --branch <b> --dir <d> [--parent <p>]`"; PRD §Worktree creation AC-051, AC-053)
- [ ] A relative or `~` path never lands a worktree inside the main checkout; the creator refuses it and the exit status says so (PRD §Worktree creation AC-051)
- [ ] Without an agent session, `--parent` works anywhere as today (PRD §Worktree creation AC-056; ADR-0004 requirements)
- [ ] The worktree-create hook prints only the bare path and exits 0 on success; when the creator fails it exits non-zero with empty stdout (SDD §3 row "worktree-create hook (`claude`)"; PRD §Worktree creation AC-052)
- [ ] The move helper's suggested path equals the path the creator would choose for the same name, and placement is loaded only when the helper plans a move (SDD §14 row "move helper `h2_move` hint")
- [ ] `afk-config.py resolve worktreeRoot` prints the confirmed root and exits 0; prints the suggestion with a stderr note when that is the root; exits 1 with the failed rule on stderr when neither passes; `resolve worktreeBasePath` is gone and every caller (the creator, `skills/afk/bug`) moved in the same commit (SDD §3 row "`afk-config.py resolve worktreeRoot`")
- [ ] A worktree that already exists outside the root keeps working with the creator, the move helper and cleanup as before (PRD §Existing worktrees AC-060)
- [ ] The implementer lists, from the code, every plugin hook, gate and script that reads a worktree path, records the list in `plan/DECISIONS.md`, and a test runs each one on a worktree outside the root; a member that cannot run in a sandbox is recorded as an exclusion with its reason (PRD §Existing worktrees AC-060)
- [ ] Creator tests cut real worktrees in temporary repositories under the root, beside the checkout, inside a checkout, with a relative path, a `~` path and a space in the path (SDD §9b row "git worktree"; PRD §Testing Decisions)
- [ ] Live check recorded in `plan/JOURNAL.md`: in a real `claude` session, the harness worktree tool lands under the root, and a hook exit 3 creates no worktree; a different outcome exits `design_conflict` (SDD §13; SDD §9b row "`claude` worktree-create hook")
- [ ] Conforms to ADR-0002: every check runs before anything is made; the creator asks placement and computes no folder itself (ADR-0002)

## Produces
- scripts/create-worktree#ERROR=worktree root: — the exit-3 refusal line naming the rule and `run /afk:setup`
- scripts/create-worktree#ERROR=parent  — the agent `--parent` refusal line `ERROR=parent <path> is outside <root>/<short name>`
- scripts/create-worktree#resolve worktreeRoot — the creator reads the root through `afk-config.py resolve worktreeRoot`, which replaces `resolve worktreeBasePath`

## Consumes
- 0004-placement scripts/placement.py#def target_for( — the folder for a new worktree, or the refused rule
- 0004-placement scripts/placement.py#def check_target( — the verdict on an agent's `--parent`
- 0004-placement scripts/placement.py#def root_state( — the root and its state for `resolve worktreeRoot`

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier + grep each ## Produces anchor | gates pass; declared symbols present |
| unit | `unit` tier; creator tests cutting real worktrees in a sandbox home: listed vs unlisted, each catalog R refusal (exit 3, line text, nothing made), agent vs developer `--parent`, relative / `~` / space paths, existing destination | creator contract on real git |
| unit | seam test: run the real `hooks/worktree-create.sh` with a `claude` envelope on stdin, once succeeding and once with a root that fails a rule; assert stdout is exactly the bare path / empty and the exit status | the hook's real output shape the harness reads |
| unit | `scripts/tests/test_h2_move.py`: the hint path equals the creator's `WORKTREE_PATH=` for the same name | one placement answer for both |
| unit | `scripts/tests/test_existing_worktree_outside_root.py`: one case per listed hook, gate and script, each run on a real worktree outside the root; assert it exits as it does inside the root and changes nothing in the worktree | AC-060 over the whole set |
| smoke | `smoke` tier, plus `bash scripts/tests/create-worktree-smoke.sh` | hooks and creator end to end |

## Context excerpts
> (SDD §3 row "`create-worktree --name <name>`") worktree-create hook, launch helper, move helper, agents | agent, developer / none | unchanged name check; the root passes every catalog R rule | last stdout line `WORKTREE_PATH=<path>`, exit 0; listed repository lands at `<root>/<short name>/<name>`; unlisted: inside the main checkout as today | root fails a rule, including a relative or `~` root: exit 3, `ERROR=worktree root: <rule> <reason> - run /afk:setup`; Δ the line names the failing rule and the fixing command, through the creator's own exit path, not the error trap; every other failure: exit 1, `ERROR=<reason>` | an existing destination is refused; a refused run leaves no worktree | path changes for listed repositories; every code caller reads the `WORKTREE_PATH=` line (INV-001)

> (SDD §3 row "`create-worktree --branch <b> --dir <d> [--parent <p>]`") `/afk:settle-change`, `/afk:execute`, developer | agent under `<root>/<short name>`, developer anywhere / an agent with a target outside it | for a listed repository and an agent session (the plugin's agent detector): `--parent` resolves inside `<root>/<short name>`; `~` and relative paths are made absolute first; without an agent session `--parent` works as today | `--parent` outside the folder for an agent: exit 3, `ERROR=parent <path> is outside <root>/<short name>` plus the fixing command | breaking for an agent `--parent` outside the root and for a set worktree base value; skills naming the base value change in the same commit

> (SDD §3 row "worktree-create hook (`claude`)") harness | as the creator | the bare path, exit 0 | creator fails: non-zero exit, no output | compatible: same output shape

> (SDD §3 row "`afk-config.py resolve worktreeRoot`") worktree creator, setup | none; the confirmed root, else the suggestion, each checked against catalog R | the root path, exit 0; a stderr note when it is the suggestion | neither passes: exit 1, the failed rule on stderr | replaces `resolve worktreeBasePath`; callers move in the same commit

> (SDD §14 row "`create-worktree` `--name`, `--branch`, `--dir`, `--parent`") computes the folder itself; every failure exits 1 through one trap (INV-014, INV-019) | asks placement; refusal exit 3 through its own exit path; an agent `--parent` outside the folder refused | worktree-create hook, launch helper, move helper, settle-change, execute (INV-014, INV-019) | all checks before anything is made; a relative `--parent` made absolute first | reworked (ADR-0002)

> (SDD §14 row "move helper `h2_move` hint") prints a path computed beside the creator (INV-014, INV-019) | takes the path from the same placement call as the creator | sessions refused in the main checkout | load placement only when it plans a move

> (SDD §9b row "git worktree") `git worktree add` creates the folder and branch; the creator runs it only after every check passed | git error → exit 1, unchanged | creator tests cutting real worktrees under, beside and inside a checkout, relative and `~` paths, a space

> (SDD §9b row "`claude` worktree-create hook") calls the hook and uses its printed path; a non-zero exit or a missing path fails the creation (code.claude.com/docs/en/hooks, INV-019) | non-zero exit, no output | live check before build: hook exit 3 creates no worktree

> (SDD §11) Rolling back a creator failure after git added the worktree, and the move helper's half-made folder on retry: issue #119.

> (PRD §Worktree creation) AC-050 Every agent route that creates a worktree of a listed repository puts it at `<root>/<short name>/<worktree name>`. This covers the plugin's worktree creator in every mode and the harness worktree tool (unverified premise: `claude` moves worktrees only through its worktree-create hook; the harness creates and isolates worktrees through that hook). AC-051 A relative or `~` path never lands a worktree inside the main checkout. The creator refuses it, and the exit status says so. AC-052 When the plugin's worktree-create hook fails, the harness tool creates no worktree outside the root (unverified premise: where a harness tool lands when its hook fails or is missing). AC-055 A worktree of a repository that is not in the list is not checked. AC-056 The developer can create a worktree anywhere from their own terminal.

> (PRD §Existing worktrees) AC-060 A worktree that already exists outside the root keeps working with every plugin hook, gate and script, and is cleaned up as before.

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
