# Config contract — the per-developer values

The bug pipeline reads five per-developer values. Every one is optional, so a
developer can often run the pipeline having configured nothing at all.

Read them through `scripts/afk-config.py resolve`, never by opening a file and
never with `get`: `resolve` applies the whole chain in one place, so no caller
has to know the order.

```sh
afk-python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" resolve trackerAssignee
```

Exit 0 prints the value; exit 1 means nothing supplied it and the caller must
fail closed. Provisioned and probed by the workflow doctor (`H6`).

## Where the values live

| Layer | File | Holds |
|-------|------|-------|
| Machine | `~/.afk/config.yaml` | A `developer:` block of defaults for every repository on the machine. |
| Repository | `<git common dir>/afk/config.yaml` | A `developer:` block for one repository, read by all its worktrees. Untracked. The default `/afk:setup` offers. |
| Checkout | `<repo>/.afk/config.local.yaml` | A `developer:` block for a value that differs in ONE checkout. Gitignored. |

The committed `<repo>/.afk/config.yaml` holds none of these keys: K1 and K2 name
a person, and a committed file never names a person. Each developer answers for
themselves: `/afk:setup` asks in session, from any linked worktree.

Resolution, highest first: the `developer:` value from any layer (checkout
beats repository beats machine), then fail closed. K3 is the exception: its own
resolution is below the keys table.

## Keys

| ID | Key | Type | Meaning | Falls back to | Gates |
|----|-----|------|---------|---------------|-------|
| K1 | `trackerAssignee` | string | Account id or email a work item the plugin creates is assigned to — the bug ticket (fail-closed, below) and spinoff tickets via `/afk:to-ticket` (unset → no assignee). The tracker adapter resolves it by user search | nothing — a person has no default | Tracker publish |
| K2 | `mrReviewer` | string | Forge user assigned as reviewer on the fix change at Ready. The literal `none` is a valid answer: it records "nobody reviews my changes", and every consumer reads it exactly as an absent key | nothing — a person has no default | Change Ready flip |
| K3 | `worktreeRoot` | absolute path | The worktree root: the folder that holds every worktree of a repository in the repository list, at `<root>/<short name>/<worktree name>` | the suggestion `~/repo-worktrees`, or the old machine `worktreeBasePath`, while it passes the root rules | Fixer dispatch |
| K4 | `ideBinary` | string | Path to the IDE executable launched for interactive worktree creation | nothing — no default could be right | (optional) interactive worktree open |
| K5 | `mrAssignee` | string | Forge user every MR/PR the plugin opens is assigned to, the fix change included. Unset or the literal `none` means no assignee — it never gates; `none` overrides a broader layer's value | nothing — a person has no default | (optional) MR/PR create |

K3 lives only in the machine file. `afk-config.py resolve worktreeRoot` prints it
(exit 0, with a stderr note when it is not confirmed) or names the failed root rule
(exit 1). `scripts/create-worktree` asks placement itself, so the dispatch reads K3
through the script's exit status: exit 3 is a refusal. A repository not in the
repository list is not checked: its fixer worktree goes to the sibling directory
`<main-checkout-name>-worktrees`.

## Read contract

- **Ask, then fail closed.** When a required value resolves to nothing and a
  human is in the conversation, ask them for it, record the answer per
  `skills/afk/setup/MANIFEST.md` · H6 Fix steps 2-4, and resolve again. With no
  human present (a hands-off run, a subagent), or when the human declines, the
  operation does **not** proceed and does **not** partially execute. It reports
  the value it needed and names `/afk:setup` as the fix, then stops — never
  guesses, never writes an external side effect with a placeholder.
- **Capture is never gated.** Writing a bug's evidence bundle + ledger entry
  reads no config and is never blocked by absent config — a capture is never
  lost to it (PRD AC-001).
- **Additive keys.** New keys may be added over time; existing keys are never
  repurposed. K3 replaced `worktreeBasePath`, which still parses and is read
  only as the old base K3 can fall back to. An unknown key under `developer:` is
  a validation error, so a typo is named rather than silently ignored.

## Fail-closed matrix

| Operation | Required value | Nothing resolves it → |
|-----------|----------------|------------------------|
| Tracker publish | K1 | No tracker call is attempted; bug stays `captured` (S1); the unpublished capture is still fully on disk and shown by `status` |
| Fixer dispatch | K3 (fails a root rule) | Dispatch refused; no worktree created, no fixer spawned; the reason is the script's `ERROR=worktree root: <rule> <reason> - run /afk:setup` line. |
| Change Ready flip | K2 (absent, or the literal `none`) | The change is not flipped Ready and no reviewer is assigned; it stays Draft — the fix is never lost, only the reviewer assignment waits |
| Interactive worktree open | K4 | Worktree is still created; the IDE simply isn't launched (K4 is optional — its absence never blocks) |
| MR/PR create | K5 | The change opens with no assignee; creation is never blocked (K5 is optional — its absence never blocks) |

## Hypothetical files

`~/.afk/config.yaml` — the developer's own machine:

```yaml
developer:
  # account id or email — the tracker adapter resolves it by user search
  trackerAssignee: dev@example.com
  # the forge username who reviews this developer's changes
  mrReviewer: reviewer.name
  # the forge username every MR/PR this developer's runs open is assigned to
  mrAssignee: my.name
  ideBinary: C:/Program Files/JetBrains/IntelliJ IDEA/bin/idea64.exe
```

That one file satisfies every gate above: K1, K2, K4 and K5 from the machine, K3
the suggestion once `~/repo-worktrees` exists. A repository with a different
reviewer adds its own `developer:` block
in `<git common dir>/afk/config.yaml`; every worktree of that repository reads
it, so nothing needs writing again when a worktree is created.

Neither overlay may set `schema`; everything else about these files is ordinary
configuration, documented in `CONFIG.md` at the plugin root.
