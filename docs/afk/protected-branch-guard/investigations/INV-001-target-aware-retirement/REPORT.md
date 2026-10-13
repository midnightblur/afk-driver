midnightblur/afk-driver@4b17f1e0991529dcedf984c2182e1c0daca1b02f · partial · boundaries 0/14 · unverified 1 (load-bearing 0) · ledger: COVERAGE.json

## Answer

`git_resources` classifies the command location as the changed resource. It does not classify the named branch or worktree.

This behavior blocks `/afk:gc` from the main checkout. It can also miss a protected target from an unprotected worktree.

## Facts

- The parser returns the repository and worktree from `cwd` or `git -C` for mutating Git commands (`hooks/lib/shell_mutations.py:331-373`).
- `git branch -d`, `git branch -D`, `git worktree move`, and `git worktree remove` all enter that path (`hooks/lib/shell_mutations.py:401-405`).
- The guard applies branch protection and occupancy checks to those returned paths (`hooks/lib/protected_branch_guard.py:574-596`).
- `/afk:gc` runs both cleanup commands from the main checkout (`skills/afk/gc/SKILL.md:29-32`, `skills/afk/gc/SKILL.md:76-81`).

## Inferences

- Inference: target-aware parsing must distinguish `-d` from `-D` and ordinary removal from forced removal.

## Unverified

- B1-B2, B4, B8-B9, and B11-B13: the repository has no declared import-alias or wire-name forms.
- B3, B5-B7, and B10: `.afk/config.yaml` declares no enumeration method.

## Frontier

- B14: other repositories, deployment manifests, and live consumers were not inspected.
