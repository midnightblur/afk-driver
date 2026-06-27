---
name: fix
description: Orchestrate fixing a verification-phase or reported bug end-to-end — pull ticket/repro context, delegate root-cause + regression test to /afk:diagnose, add proportional api/e2e coverage, run an escape analysis on the existing test that should have caught it, reconcile the load-bearing artifacts (PRD / SDD / ADRs / VERIFICATION-PLAN) in a feature-building session, and — for AFK-delivered features — hand off a structured workflow lesson so the AFK chain stops repeating the miss. Use when a verification finding, a human/QA bug report, or a Jira bug needs fixing — especially mid-flight on an unreleased AFK feature, where no plan survives contact and gaps surface during verification. /afk:execute routes here on a stuck verification tier.

---

# afk:fix — fix a bug and keep the source of truth true

You run this yourself when a bug surfaces — typically during the **verification
phase** of an in-flight feature (agent- or human-found), or as an ad-hoc fix on
released code. It is also the **recovery path `/afk:execute` routes to** when a
verification tier stays red after its targeted retry (execute Step 8), and the
natural follow-up to a `/afk:smoke-test` red.

`fix` is a **thin orchestrator**: it does not re-implement diagnosis.
`/afk:diagnose` owns reproduce → root-cause → fix → seam regression test →
cleanup. `fix` wraps that with **context intake**, **proportional higher-tier
tests**, and **feature-session artifact reconciliation**.

`fix` does **not** commit, push, or merge — see Hard rules.

## Argument

A Jira bug key, a free-text bug description, or nothing (infer the finding from
the conversation — e.g. a verification result just came back red).

## Phase 0 — Intake & classify

1. **Source of the finding.**
   - **Jira bug** (key in arg or derivable from branch): `mcp__jira__jira_get`
     with `fields=summary,status,priority,issuetype,labels,assignee,reporter,description,comment`.
     Extract repro steps, env, expected vs actual.
   - **Ad-hoc** (human/QA/agent verification finding): take the symptom +
     repro hints from the conversation.
2. **Session type.** Decide **feature-building (unreleased)** vs **ad-hoc /
   maintenance**. Feature-building signals: cwd on an AFK feature branch
   (`mvu/afk/{ticket-id}`); a spec dir with `plan/PLAN.md` whose `Feature:` is
   not yet shipped; the bug came from *this* feature's verification. Otherwise
   ad-hoc → **skip Phase 3**.
3. **Locate artifacts** (feature session only):
   `{service}/src/main/resources/specs/{year}r{release}/{ENH-ID}/` — `PRD.md`,
   `SDD.md`, `VERIFICATION-PLAN.md`, `adr/{requirements,design}/`, `plan/`.

## Phase 1 — Diagnose (delegate, do not duplicate)

Run **`/afk:diagnose`**, handing it everything from intake (repro steps, env,
the exact captured symptom). Diagnose **owns**: the Phase-1 feedback loop
(failing test / curl / **e2e/browser** / API replay / harness), 3–5 ranked
hypotheses, instrumentation, the fix, the **seam-level regression test**, and
cleanup + post-mortem.

- For a ticketed or known-env bug, push diagnose toward an **automated** loop
  (api or e2e/browser) over HITL — you have the env and steps.
- If diagnose reports it **cannot reproduce**, or surfaces that a binding design
  decision is wrong → stop; report `cannot_reproduce` / `design_conflict` and
  route (Phase 3).

Exit gate: root cause known, fix applied, seam regression test green (or
seam-absence explicitly documented per diagnose Phase 5).

## Phase 2 — Broaden coverage (proportional)

Diagnose gave you the seam regression test. Decide whether a **higher tier** is
warranted. Add the **lowest tier that reproduces the bug pattern at its right
home** — don't gold-plate.

| Bug class | Add a test? | Where |
|-----------|-------------|-------|
| Cosmetic / copy / caption / one-off layout | No new e2e/api — rely on the seam unit test or static check | — |
| Logic / calculation / mapping / null-handling | Yes, at the seam | `unit` / `integration` |
| Contract / envelope / authz / status-code | Yes — it's a backend contract | `api` → `11700-payable/verification/api` per `…/api/AUTHORING.md` |
| User-visible flow that **escaped to the verification phase** | Yes — the journey had no guard | `e2e/browser` → `11700-payable/verification/ui-e2e` per `…/ui-e2e/AUTHORING.md` |

Tiers are the same set `/afk:execute` uses: `static → unit → integration → api
→ e2e/browser`. Reference the AUTHORING recipes — **never embed** them; new
scenarios land on the branch like code. A bug that slipped a feature's smoke
gate means the **gate** had a gap → that scenario belongs in `VERIFICATION-PLAN.md`
+ a `NNNN-smoke-*` subtask (Phase 3), not just an inline test.

**Verify:** re-run diagnose's loop plus every tier you added/touched — all green
before proceeding. Remove all `[DEBUG-...]` instrumentation (grep the prefix).

## Phase 2.5 — Escape analysis (standing-suite-tier bugs only)

For a user-visible (`e2e/browser`) or backend-contract (`api`) bug, interrogate why
the existing guard missed it and name the miss class — full procedure and miss-class
table in [ESCAPE-ANALYSIS.md](ESCAPE-ANALYSIS.md). Skip for a pure unit/logic bug
that never had a higher-tier scenario. Carry the miss class into Phase 4's report.

## Phase 3 — Reconcile the source of truth (feature sessions only)

A fix on an unreleased feature can invalidate a load-bearing artifact. Triage
what changed and **route to the owning skill** — never hand-edit across an
ownership boundary (that breaks Jira sync, ADR numbering, and grill provenance).

| What the fix revealed | Stale artifact | Route to |
|-----------------------|----------------|----------|
| A behavior the PRD specifies was wrong / changed | `PRD.md` + requirement ADR | `/afk:to-prd` → `/afk:to-ticket` (republish) |
| A **frozen** SDD §8 interface / seam / design decision is wrong or infeasible | `SDD.md` + design ADR | `/afk:grill-solution` → `/afk:to-sdd` (superseding ADR under `adr/design/`) — this is a `design_conflict` |
| The bug had **no verification scenario** that would catch it | `VERIFICATION-PLAN.md` + smoke gate | `/afk:grill-verification` → `/afk:to-verification-plan`; seed a `NNNN-smoke-*` subtask |
| An in-flight subtask's `## Produces` / contract shifted | `plan/NNNN-slug.md` | surface to the `/afk:execute` run; don't silently re-slice |

Doc right + code wrong → no artifact change.
Only reconcile when the fix changed something a doc asserts. If you can't reach
truth this session, record the divergence and report `needs_artifact_sync`.

## Phase 3.5 — Workflow feedback (AFK-delivered features only)

When the feature was built with AFK assistance (Phase 0 signals: AFK branch +
`plan/PLAN.md`), trace the miss to the AFK stage that under-specified the guard and
**hand off** a structured workflow lesson via `/afk:handoff` (never self-applied) —
full stage-mapping table, handoff payload, and procedure in
[WORKFLOW-FEEDBACK.md](WORKFLOW-FEEDBACK.md). For ad-hoc/maintenance bugs there is no
AFK workflow to improve → skip. Report the handoff doc path in Phase 4.

## Phase 4 — Report

End with one structured line:

```
OUTCOME: <status> — <one-line summary> [ticket: <KEY|none>]
```

- `fixed` — root cause found, fix applied, regression test + any added tier green.
- `fixed_no_test` — fix applied, no new test, naming the proportionality reason
  (e.g. caption fix) or the absent-seam finding from diagnose.
- `cannot_reproduce` — diagnose couldn't build a loop; list what was tried and
  what's needed (env / artifact / instrumentation).
- `design_conflict` — fix requires changing a frozen SDD/ADR decision; routed to
  `/afk:grill-solution`. (When invoked from `/afk:execute`, this maps to execute's
  own `design_conflict` path.)
- `needs_artifact_sync` — fix landed but a load-bearing artifact is now stale and
  unreconciled; name it + the owning skill.
- `blocked` — anything else; explain.

When Phase 2.5 ran, add the **miss class** to the summary; when Phase 3.5 ran,
append the **handoff doc path** so the workflow-improvement lesson isn't lost:

```
OUTCOME: fixed — <summary> [ticket: <KEY>] [miss: <class>] [handoff: <path>]
```

## Hard rules

- **Never commit, push, or merge.** `fix` is not in the commit lane — the human
  commits, or the calling `/afk:execute` run does (it resumes from its Step 8 and
  drives commit + push + MR itself). Apply edits and stop.
- **Never alter the DB directly.** Add JPA entities; let liquibase-hibernate7
  pick them up. No hand-written `UpgradeGroup` / `PreDbMigration` / `db/changelog/*`.
- **Never hand-edit PRD / SDD / ADRs / VERIFICATION-PLAN / PLAN.md across an
  ownership boundary.** Route to the owning skill (Phase 3).
- **Never edit the AFK skills themselves in a fix session.** Phase 3.5's workflow
  lesson is **handed off** (`/afk:handoff`), never self-applied — no `/afk:retro`,
  no in-session edit of any `SKILL.md` under the plugin repo.
- **Don't gold-plate tests.** No brand-new e2e/api scenario for a trivial
  cosmetic fix — match the tier to the bug class (Phase 2).
- **Cross-module edits carry a `// {TICKET-ID}:` marker comment** in the added hunks.
- **No `--no-verify`, no `--force`, no global git config changes.**
- Before declaring done, all `[DEBUG-...]` instrumentation removed and throwaway
  harnesses deleted (diagnose Phase 6).
