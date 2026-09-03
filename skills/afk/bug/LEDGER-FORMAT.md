# Ledger format — `.claude/bugs/{ticket}/state.json`

The **one home** for a bug's lifecycle: the S1–S10 state machine, the versioned
`state.json` schema, the on-disk directory layout, and the archive/purge rules.
Every other file points here by path and never restates any of it.

A bug's whole world is one gitignored directory under the ledger root
`.claude/bugs/` in the main checkout. Machine-readable position + refs live in
`state.json`; human-readable evidence lives beside it (grammar:
[BUNDLE-FORMAT.md](BUNDLE-FORMAT.md)).

## Write contract

- **Single writer.** Only the main interactive session writes `state.json`.
  Subagents (publisher, fixer, retester) return results; the writer records
  them. No subagent path targets a ledger file. Guards against concurrent-write
  corruption (ADR-0002).
- **Every write is a state transition or a history append**, never a silent
  field mutation: a changed `state` MUST be an allowed edge below and MUST push
  one `history` entry in the same write.

## Directory layout

```
.claude/bugs/
  {ticket}/                 # one dir per bug; {ticket} = Jira key, or capture-time slug until published
    state.json              # machine state (schema below)
    bundle.md               # evidence dossier — BUNDLE-FORMAT.md
    screenshots/            # image files referenced by bundle facts
  done/
    {ticket}/               # terminal bugs (S9 verified) moved here whole
```

- `{ticket}` is the Jira key once published (S2); before that a capture-time
  slug, renamed to the key when the ticket is recorded.
- **Archive.** On reaching S9 `verified`, the whole `{ticket}/` dir is moved
  under `done/` unchanged; the fixer worktree is removed.
- **Purge.** Full cleanup is explicit only — deleting a `{ticket}/` dir (live or
  archived). Nothing auto-deletes a bundle.

## State machine (Catalog A)

The lifecycle states, their meaning, and the **only** permitted transitions.
This table is the single authoritative copy of PRD Catalog A.

| ID | `state` | Meaning | Allowed next |
|----|---------|---------|--------------|
| S1 | `captured` | Bundle + ledger entry on disk; Jira publish pending (config missing or in flight) | S2 |
| S2 | `published` | Jira Bug exists: assignee = config K1, Dev-Pending, evidence embedded | S3, S4 |
| S3 | `queued` | Dispatch requested while another fixer is live | S4 |
| S4 | `fixing` | Fixer live in its worktree | S5, S6 |
| S5 | `blocked` | Fixer returned a structured question; awaiting dev answer via main-agent relay | S4 |
| S6 | `fix-pushed` | Fix + regression tests green in fixer worktree; branch pushed; Draft MR open | S7, S8 |
| S7 | `mr-ready` | Pipeline green; MR flipped Ready; reviewer (config K2) assigned | S8 |
| S8 | `awaiting-retest` | Fix landed in dev's current branch (fast path or pull) | S9, S10 |
| S9 | `verified` | Retest green, main-agent spot-check passed | — (terminal) |
| S10 | `refuted` | Retest failed; relayed to dev; may re-dispatch | S4 |

- **Terminal.** S9 only — triggers archive + worktree removal. S10 is a loop
  point, not terminal: it re-enters S4 on re-dispatch.
- **Invariants** (guarded by the single writer): at most one entry in `fixing`
  (S4) across all bugs at any time; a `state` may change only along an edge in
  the "Allowed next" column.

## state.json schema

The state.json schema is a JSON object. **Additive evolution only** — new keys may be added; existing keys
are never removed, renamed, or repurposed. Readers ignore unknown keys; a reader
seeing a `version` it predates falls back to the fields it knows.

| Key | Type | Meaning | Present from |
|-----|------|---------|--------------|
| `version` | string | Schema version, e.g. `"1"`. Bumped only on an additive change | always |
| `state` | string | Current Catalog-A id's `state` token (e.g. `"fixing"`) | always |
| `ticketKey` | string \| null | Jira key; `null` until published (S2) | always |
| `worktreePath` | string \| null | Absolute path of the fixer worktree; `null` until dispatch (S4) | always |
| `baseBranch` | string \| null | Source branch the fix targets (fixer worktree + MR base) | always |
| `mrUrl` | string \| null | Draft/Ready MR URL; `null` until first push (S6) | always |
| `fixSha` | string \| null | Commit SHA of the landed fix; ancestry probe target for retest | always |
| `retest` | object \| null | Retest sub-state: `{ state, evidencePath, verdict }`; `null` until S8 | always |
| `history` | array | **Append-only** event log; each entry `{ ts, event, detail }` | always |

- `retest.state` mirrors the retest leg (`awaiting`, `verified`, `refuted`);
  `retest.verdict` is the main agent's spot-check result, not the subagent's raw
  claim.
- `history` is append-only: entries are added, never edited or removed — the
  audit trail that lets any later session reconstruct the bug. `event` is a
  short token, `detail` a one-line human-readable clause.

### Hypothetical `state.json`

```json
{
  "version": "1",
  "state": "fixing",
  "ticketKey": "PROJ-9999",
  "worktreePath": "C:/Users/dev/repo-worktrees/bugfix-proj-9999",
  "baseBranch": "team/development/dev/some-feature",
  "mrUrl": null,
  "fixSha": null,
  "retest": null,
  "history": [
    { "ts": "2026-01-10 14:32", "event": "captured", "detail": "bundle + ledger written on disk before any external call" },
    { "ts": "2026-01-10 14:41", "event": "published", "detail": "Jira Bug PROJ-9999 created, assignee set, transitioned Dev-Pending" },
    { "ts": "2026-01-10 14:58", "event": "fixing", "detail": "fixer spawned in its own worktree off the source branch" }
  ]
}
```
