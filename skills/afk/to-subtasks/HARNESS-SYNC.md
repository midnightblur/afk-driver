# Harness sync (always)

Every plan ends with one terminal `NNNN-sync-harness` documentation subtask that
updates the CLAUDE.md harness so the next agent discovers the shipped feature and
how to use it. Emit it for every feature — it is not gated on any artifact.

It delegates the write to `/afk:claude-md`; the subtask only scopes that to this
feature's net diff and states the two deliverables. `## Blocked by` lists every
other subtask (including any `NNNN-smoke-*`) so it runs last, against the finished
feature.

Emit exactly one, using the base subtask contract with the fields below:

```
## Goal
Sync the CLAUDE.md harness for {Feature} so the next agent discovers it and knows how to
use/extend it. Run /afk:claude-md scoped to THIS feature's net diff (this branch vs the parent),
capturing at most two things: (1) ONE lazily-loaded instruction in the nearest component/leaf
CLAUDE.md — max 3 dense sentences on how to add/extend or invoke the feature, pointing at the
key types + the spec dir; and (2) ONE awareness sentence in the affected service-root CLAUDE.md
that names the feature and leads to (1).

## Scope
- {service}/**/CLAUDE.md        # the affected service's CLAUDE.md chain (nearest leaf + service root)
- 11xxx*/**/CLAUDE.md           # only the other 11xxx dirs the feature genuinely spans
- tools/payable/**/CLAUDE.md    # only when the feature is harness / tooling itself
# docs only — NO source edits

## Acceptance
- [ ] The how-to note lives in the nearest component/leaf CLAUDE.md, not the service root
- [ ] The service-root CLAUDE.md carries exactly ONE awareness sentence leading to that note
- [ ] Nothing added restates code; every line clears the /afk:claude-md inclusion bar
- [ ] Written via /afk:claude-md; its cross-worktree propagation summary was surfaced

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | grep the awareness sentence's path in the service-root CLAUDE.md; confirm that leaf CLAUDE.md exists on disk | the pointer resolves |

## Blocked by
<every other subtask id, including any NNNN-smoke-* build subtasks>

## Implementation Notes (auto-maintained)
```
