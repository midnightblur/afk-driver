# Config contract — how the bug pipeline acts on a missing value

The per-developer values K1–K5 — their ids, meanings, layers, resolution and
the general missing-value rule — live in `CONFIG.md` "Developer settings
(K1–K5)" at the plugin root. This page keeps only the bug pipeline's own,
stricter rule for its operations.

## Read contract

- **Ask, then fail closed.** When a value an operation below requires resolves
  to nothing and a human is in the conversation, ask them for it, record the
  answer per `skills/afk/setup/MANIFEST.md` · H6 Fix steps 2-4, and resolve
  again. With no human present (a hands-off run, a subagent), or when the human
  declines, the operation does **not** proceed and does **not** partially
  execute. It reports the value it needed and names `/afk:setup` as the fix,
  then stops — never guesses, never writes an external side effect with a
  placeholder.
- **Capture is never gated.** Writing a bug's evidence bundle + ledger entry
  reads no config and is never blocked by absent config — a capture is never
  lost to it (PRD AC-001).

## Fail-closed matrix

| Operation | Required value | Nothing resolves it → |
|-----------|----------------|------------------------|
| Tracker publish | K1 | No tracker call is attempted; bug stays `captured` (S1); the unpublished capture is still fully on disk and shown by `status` |
| Fixer dispatch | K3 | Dispatch refused; no worktree created, no fixer spawned; the reason names the key. Only reachable when the derivation also failed. |
| Change Ready flip | K2 (absent, or the literal `none`) | The change is not flipped Ready and no reviewer is assigned; it stays Draft — the fix is never lost, only the reviewer assignment waits |
| Interactive worktree open | K4 | Worktree is still created; the IDE simply isn't launched (K4 is optional — its absence never blocks) |
| MR/PR create | K5 | The change opens with no assignee; creation is never blocked (K5 is optional — its absence never blocks) |
