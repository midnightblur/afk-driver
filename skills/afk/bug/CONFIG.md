# Config contract — the `developer:` block

The per-developer config the bug pipeline reads lives under `developer:` in
`.afk/config.local.yaml`, the gitignored overlay beside the repository's
committed `.afk/config.yaml`. One file per checkout, never committed, holding
the values that name a person or one machine's paths. Read it through
`scripts/afk-config.py` like every other key — never by opening the file:

```sh
python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" get developer.trackerAssignee
```

Provisioned and probed by the workflow doctor (`H6`). This contract defines the
keys and the fail-closed rules that govern operations depending on them.

## Read contract

- **Fail closed on absence.** A config-gated operation whose required key is
  missing (overlay absent, block absent, or key absent/empty) does **not** proceed and does
  **not** partially execute. It reports the missing key and stops — never
  guesses a default, never writes an external side effect with a placeholder.
- **Capture is never gated.** Writing a bug's evidence bundle + ledger entry
  reads no config and is never blocked by a missing file — a capture is never
  lost to absent config (PRD AC-001).
- **Additive keys.** New keys may be added over time; existing keys are never
  removed or repurposed. An unknown key is ignored.

## Keys

| ID | Key | Type | Meaning | Gates |
|----|-----|------|---------|-------|
| K1 | `trackerAssignee` | string | The dev's tracker account id or email — the tracker adapter resolves it by user search; bug tickets are assigned to it | Tracker publish |
| K2 | `mrReviewer` | string | Forge user assigned as reviewer on the fix change at Ready | Change Ready flip |
| K3 | `worktreeBasePath` | string | Base directory under which fixer worktrees are created | Fixer dispatch |
| K4 | `ideBinary` | string | Path to the IDE executable launched for interactive worktree creation | (optional) interactive worktree open |

## Fail-closed matrix

| Operation | Required key(s) | Absent → |
|-----------|-----------------|----------|
| Tracker publish | K1 | No tracker call is attempted; bug stays `captured` (S1); the unpublished capture is still fully on disk and shown by `status` |
| Fixer dispatch | K3 | Dispatch refused; no worktree created, no fixer spawned; the reason names the missing key |
| Change Ready flip | K2 | The change is not flipped Ready and no reviewer is assigned; it stays Draft — the fix is never lost, only the reviewer assignment waits |
| Interactive worktree open | K4 | Worktree is still created; the IDE simply isn't launched (K4 is optional — its absence never blocks) |

## Hypothetical `.afk/config.local.yaml`

```yaml
developer:
  # account id or email — the tracker adapter resolves it by user search
  trackerAssignee: dev@example.com
  mrReviewer: some.reviewer
  worktreeBasePath: C:/Users/dev/repo-worktrees
  ideBinary: C:/Program Files/JetBrains/IntelliJ IDEA/bin/idea64.exe
```

The overlay is gitignored and may not set `schema`; everything else about it
is an ordinary configuration file, documented in `CONFIG.md` at the plugin
root.
