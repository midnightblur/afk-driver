# Config contract — `.claude/afk.local.json`

The **one home** for the per-developer config the bug pipeline reads. One
gitignored file per checkout (never committed), holding machine-specific values
that can't live in shared plugin source. Provisioned and probed by the workflow
doctor; this afk.local.json contract defines the keys and the fail-closed rules
that govern operations depending on them.

## Read contract

- **Fail closed on absence.** A config-gated operation whose required key is
  missing (file absent, or key absent/empty) does **not** proceed and does
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
| K1 | `trackerAssignee` | string | The dev's Jira account id — bug tickets are assigned to it | Jira publish |
| K2 | `mrReviewer` | string | GitLab user assigned as reviewer on the fix MR at Ready | MR Ready flip |
| K3 | `worktreeBasePath` | string | Base directory under which fixer worktrees are created | Fixer dispatch |
| K4 | `ideBinary` | string | Path to the IDE executable launched for interactive worktree creation | (optional) interactive worktree open |

## Fail-closed matrix

| Operation | Required key(s) | Absent → |
|-----------|-----------------|----------|
| Jira publish | K1 | No Jira call is attempted; bug stays `captured` (S1); the unpublished capture is still fully on disk and shown by `status` |
| Fixer dispatch | K3 | Dispatch refused; no worktree created, no fixer spawned; the reason names the missing key |
| MR Ready flip | K2 | MR is not flipped Ready and no reviewer is assigned; it stays Draft — the fix is never lost, only the reviewer assignment waits |
| Interactive worktree open | K4 | Worktree is still created; the IDE simply isn't launched (K4 is optional — its absence never blocks) |

## Hypothetical `afk.local.json`

```json
{
  "trackerAssignee": "557058:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "mrReviewer": "some.reviewer",
  "worktreeBasePath": "C:/Users/dev/core-services-worktrees",
  "ideBinary": "C:/Program Files/JetBrains/IntelliJ IDEA/bin/idea64.exe"
}
```
