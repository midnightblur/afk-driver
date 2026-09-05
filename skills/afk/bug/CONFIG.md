# Config contract — the per-developer values

The bug pipeline reads four per-developer values. Every one is optional, and two
of them have a committed team-wide fallback, so a developer can often run the
pipeline having configured nothing at all.

Read them through `scripts/afk-config.py resolve`, never by opening a file and
never with `get`: `resolve` applies the whole chain in one place, so no caller
has to know the order.

```sh
python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" resolve trackerAssignee
```

Exit 0 prints the value; exit 1 means nothing supplied it and the caller must
fail closed. Provisioned and probed by the workflow doctor (`H6`).

## Where the values live

| Layer | File | Holds |
|-------|------|-------|
| Machine | `~/.afk/config.yaml` | A `developer:` block. The normal home: one file covers every repository on the machine. |
| Checkout | `<repo>/.afk/config.local.yaml` | A `developer:` block for a value that differs in ONE checkout. Gitignored. |
| Repository | `<repo>/.afk/config.yaml` | `tracker-defaults.assignee` and `forge-defaults.reviewer` — team facts, committed. |

Resolution, highest first: the `developer:` value from any layer (checkout
overlay beats machine), then the committed team default, then — for
`worktreeBasePath` alone — a derived value, then fail closed.

## Keys

| ID | Key | Type | Meaning | Falls back to | Gates |
|----|-----|------|---------|---------------|-------|
| K1 | `trackerAssignee` | string | Account id or email the bug ticket is assigned to — the tracker adapter resolves it by user search | `tracker-defaults.assignee` | Tracker publish |
| K2 | `mrReviewer` | string | Forge user assigned as reviewer on the fix change at Ready | `forge-defaults.reviewer` | Change Ready flip |
| K3 | `worktreeBasePath` | string | Base directory under which fixer worktrees are created | derived: a sibling directory `<main-checkout-name>-worktrees` beside the main checkout | Fixer dispatch |
| K4 | `ideBinary` | string | Path to the IDE executable launched for interactive worktree creation | nothing — no default could be right | (optional) interactive worktree open |

K3's derivation reads `git rev-parse --git-common-dir`, which answers with the
MAIN checkout even from inside a worktree, so every worktree of one repository
agrees on the directory. A repository whose git directory is not inside the tree
(a bare clone) derives nothing and needs the key.

## Read contract

- **Fail closed on absence.** A config-gated operation whose required value
  resolves to nothing does **not** proceed and does **not** partially execute. It
  reports the value it needed and both places it could have come from, then
  stops — never guesses, never writes an external side effect with a
  placeholder.
- **Capture is never gated.** Writing a bug's evidence bundle + ledger entry
  reads no config and is never blocked by absent config — a capture is never
  lost to it (PRD AC-001).
- **Additive keys.** New keys may be added over time; existing keys are never
  removed or repurposed. An unknown key under `developer:` is a validation
  error, so a typo is named rather than silently ignored.

## Fail-closed matrix

| Operation | Required value | Nothing resolves it → |
|-----------|----------------|------------------------|
| Tracker publish | K1 | No tracker call is attempted; bug stays `captured` (S1); the unpublished capture is still fully on disk and shown by `status` |
| Fixer dispatch | K3 | Dispatch refused; no worktree created, no fixer spawned; the reason names the key. Only reachable when the derivation also failed. |
| Change Ready flip | K2 | The change is not flipped Ready and no reviewer is assigned; it stays Draft — the fix is never lost, only the reviewer assignment waits |
| Interactive worktree open | K4 | Worktree is still created; the IDE simply isn't launched (K4 is optional — its absence never blocks) |

## Hypothetical files

`~/.afk/config.yaml` — the developer's own machine:

```yaml
developer:
  # account id or email — the tracker adapter resolves it by user search
  trackerAssignee: dev@example.com
  ideBinary: C:/Program Files/JetBrains/IntelliJ IDEA/bin/idea64.exe
```

`<repo>/.afk/config.yaml` — committed, the same for the whole team:

```yaml
tracker-defaults:
  assignee: 5ad8b262af21cf2a74845b29
forge-defaults:
  reviewer: team.lead
```

Between them every gate above is satisfied: K1 and K4 from the machine, K2 from
the repository, K3 derived. Nothing is per-checkout, so nothing needs writing
again when a worktree is created.

The overlay is gitignored and may not set `schema`; everything else about these
files is ordinary configuration, documented in `CONFIG.md` at the plugin root.
