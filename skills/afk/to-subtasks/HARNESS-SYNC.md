# Harness sync (always)

Every plan ends with one terminal `NNNN-sync-harness` documentation subtask that
updates the CLAUDE.md harness so the next agent discovers the shipped feature,
makes the final staples-registry call, **and emits the trace matrix**
(`plan/TRACE.md`). Emitted for every feature — gated on no artifact.

**The trace matrix.** Running last, everything is known — which commits landed,
which tests exist, which criteria they satisfy. This subtask
writes `plan/TRACE.md`: one table, one row per PRD Acceptance Criterion (and per
accepted staple obligation), columns `Criterion (verbatim) | Subtask | Commits
([NNNN-slug]-prefixed short SHAs) | Proven by (test file / scenario name / gate
row)`. Rows nothing satisfied are listed `— UNSATISFIED` — surfacing the gap is
the point. Written once; a re-run overwrites. The artifact answering, months
later, "which commit satisfied which requirement".

Delegates the write to `/afk:claude-md`; the subtask only scopes that to this
feature's net diff and states the deliverables. `## Blocked by` lists every
other subtask (including any `NNNN-smoke-*`) so it runs last, against the finished
feature.

**Staples at delivery.** Delivery is the *authoritative* moment for the staples
registry (`{service}/STAPLES.md`) — earlier stages only *raised* candidates. This
subtask resolves them: (a) if the PRD flagged this feature as a **candidate new
staple** and it genuinely became a standing expectation, register it; (b) if the
feature is the new best exemplar of an **existing** staple, advance that staple's
`Reference` (and fill a `TODO` Reference/Since it now satisfies). Both are
judgment calls surfaced to the human via `/afk:claude-md`'s propose→approve gate — no
candidate ⇒ no registry change.

Emit exactly one, using the base subtask contract with the fields below:

```
## Goal
Sync the CLAUDE.md harness for {Feature} so the next agent discovers it and knows how to
use/extend it, settle the staples registry, and emit the trace matrix. Run /afk:claude-md scoped
to THIS feature's net diff (this branch vs the parent), capturing: (1) ONE lazily-loaded
instruction in the nearest component/leaf CLAUDE.md — max 3 dense sentences on how to add/extend
or invoke the feature, pointing at the key types + the spec dir; (2) ONE awareness sentence in the
affected service-root CLAUDE.md that names the feature and leads to (1); and (3) ONLY IF
applicable, the STAPLES.md change — register a candidate new staple the PRD flagged, or
advance/fill an existing staple's Reference this feature now exemplifies. If nothing is
staple-worthy, (3) is a no-op. Then (4) write plan/TRACE.md per the trace-matrix spec in
skills/afk/to-subtasks/HARNESS-SYNC.md — every PRD Acceptance Criterion mapped to its subtask,
commits, and proving test, unsatisfied rows flagged.

## Scope
- {service}/**/CLAUDE.md        # the affected service's CLAUDE.md chain (nearest leaf + service root)
- {service}/STAPLES.md          # only if this feature mints a new staple or advances an existing one's Reference
- 11???*/**/CLAUDE.md           # only the other 11xxx dirs the feature genuinely spans
- tools/payable/**/CLAUDE.md    # only when the feature is harness / tooling itself
- {plan dir}/TRACE.md           # the trace matrix this subtask emits
# docs only — NO source edits

## Acceptance
- [ ] The how-to note lives in the nearest component/leaf CLAUDE.md, not the service root
- [ ] The service-root CLAUDE.md carries exactly ONE awareness sentence leading to that note
- [ ] The staples registry was settled: a PRD-flagged candidate is registered in STAPLES.md, or an existing staple's Reference advanced/filled — or, if none applied, this is explicitly a no-op
- [ ] Nothing added restates code; every line clears the /afk:claude-md inclusion bar
- [ ] Written via /afk:claude-md
- [ ] plan/TRACE.md exists: every PRD Acceptance Criterion has a row (subtask, commits, proving test), unsatisfied rows explicitly flagged

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | grep the awareness sentence's path in the service-root CLAUDE.md; confirm that leaf CLAUDE.md exists on disk | the pointer resolves |
| static | grep every PRD Acceptance Criterion against plan/TRACE.md rows — each criterion has a row (or an explicit `— UNSATISFIED` flag) | the trace matrix is complete |

## Blocked by
<every other subtask id, including any NNNN-smoke-* build subtasks>
```
