## Goal

Build the `repo_clone_manager` module: an idempotent wrapper over `gh repo clone` that ensures any GitHub repo discovered in multi-repo queue mode is locally available under `worktree_root/github/{owner}/{repo}/` before `worktree_manager` is asked to create a per-Enhancement worktree inside it.

## Design refs

- SDD: `../SDD.md` §3 row "repo_clone_manager" — idempotent `gh repo clone` wrapper.
- SDD: `../SDD.md` §7 use-case 1 sequence — clone-on-first-encounter step in pre-flight.
- SDD: `../SDD.md` §8 module table row "repo_clone_manager".
- ADR: `../adr/0003-multi-repo-discovery-and-auto-clone.md` — per-repo failure isolation; auth-error halts.

## Scope

- `src/afk_driver/repo_clone_manager.py`
- `tests/test_repo_clone_manager.py`

## Acceptance

- [ ] Public function `ensure_clone(owner: str, repo: str, root: Path) -> Path` returns the local clone path (ADR-0003)
- [ ] If the destination path is absent, runs `gh repo clone {owner}/{repo} {dest}` once and returns the path on success (ADR-0003 flowchart "clone exists? → no → gh repo clone")
- [ ] If the destination path exists and is a valid git repo, runs `git fetch` and returns the path (no re-clone) — idempotent on re-invocation (SDD §5 idempotency table — "create-or-find" pattern)
- [ ] If the destination path exists but is NOT a git repo, raises a typed `RepoCloneError` — refuses to operate on foreign directories (SDD §7 failure-recovery matrix row "gh repo clone fails")
- [ ] Clone subprocess timeout = 120 000 ms; on timeout raises `RepoCloneError` so the caller can mark the repo failed and skip (SDD §5 retry table row "gh repo clone")
- [ ] Injected `GhRunner: Callable[[list[str]], CompletedProcess]` so tests stub the subprocess — mirrors `GlabRunner` pattern in `gitlab_client` (SDD §3 — "subprocess pattern parallels existing `glab`")
- [ ] No dependency on `tracker_protocol` / `scm_protocol` / `runner` — bottom-of-stack module per the onion DAG (SDD §8 dependency DAG)
- [ ] Tests cover: clone-when-absent, no-op when already cloned (verify `git fetch` is called instead), refuse-when-destination-is-not-git, clone-failure-surfaces-as-typed-error (PRD §"Testing Decisions" — repo_clone_manager coverage list)
- [ ] Tests pass via `pytest tests/test_repo_clone_manager.py` (SDD §10 NFRs)

## Produces

- `src/afk_driver/repo_clone_manager.py#def ensure_clone(owner: str, repo: str, root: Path) -> Path:` — idempotent clone-or-fetch entrypoint.
- `src/afk_driver/repo_clone_manager.py#class RepoCloneError(RuntimeError):` — typed error for clone failure.
- `src/afk_driver/repo_clone_manager.py#GhRunner = Callable[[list[str]], subprocess.CompletedProcess]` — injectable runner type for test stubbing.

## Test command

```
pytest tests/test_repo_clone_manager.py
```

## Parent PRD

`tasks/github-backend/PRD.md`

## Parent SDD

`tasks/github-backend/SDD.md`

## Blocked by

(none)

## Conflict procedure

If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, exit with `design-conflict` status quoting the SDD section + the conflict. Do NOT override silently. Route back to `/afk:architect-grill` for a superseding ADR.

## Implementation Notes (auto-maintained)

<!-- AFK appends one bullet per completed SubTask -->
