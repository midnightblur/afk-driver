---
name: fix
description: Orchestrates a bug fix — root-cause via /afk:diagnose, proportional coverage, escape analysis. Use when a verification finding, human/QA bug report, or Jira bug needs fixing.
---

> **Language:** read `LANGUAGE.md` (plugin root) first. It binds every reply, question, and artifact this skill produces — Simplified Technical English, glossary terms verbatim.

# afk:fix — fix a bug and keep the source of truth true

Run when a bug surfaces — typically a feature's **verification phase** (agent- or human-found), or ad-hoc on released code. Also the **recovery path** when a verification tier stays red after its targeted retry, and the follow-up to a red feature smoke gate.

`fix` is a **thin orchestrator**; does not re-implement diagnosis. `/afk:diagnose` owns reproduce → root-cause → fix → seam regression test → cleanup. `fix` wraps that with **context intake**, **proportional higher-tier tests**, **feature-session artifact reconciliation**.

`fix` does **not** commit, push, or merge — see Hard rules.

## Argument

A Jira bug key, free-text bug description, or nothing (infer the finding from conversation — e.g. a verification result just came back red).

## Phase 0 — Intake & classify

1. **Source of the finding.**
   - **Jira bug** (key in arg or derivable from branch): `mcp__jira__jira_get` with `fields=summary,status,priority,issuetype,labels,assignee,reporter,description,comment`. Delegate the pull to an `afk-reader` subagent returning a task-shaped bug digest — symptom, expected, repro hints, env, cited to ticket fields — per `DELEGATION.md` (plugin root).
   - **Ad-hoc** (human/QA/agent verification finding): take symptom + repro hints from conversation — already in context, no delegation.
2. **Session type.** **feature-building (unreleased)** vs **ad-hoc / maintenance**. Feature-building signals: cwd on an AFK feature branch (`kapteyn/development/{username}/{enh_id_lower}`); a spec dir with `plan/PLAN.md` whose `Feature:` is not yet shipped; bug came from *this* feature's verification. Otherwise ad-hoc → **skip Phase 3**.
3. **Locate artifacts** (feature session only): `{service}/specs/{year}r{release}/{TICKET-ID}/` — `PRD.md`, `SDD.md`, `VERIFICATION-PLAN.md`, `adr/{requirements,design}/`, `plan/`.

## Phase 1 — Diagnose (delegate, do not duplicate)

Run **`/afk:diagnose`**, handing it everything from intake (repro steps, env, exact captured symptom). Diagnose **owns**: the Phase-1 feedback loop (failing test / curl / **e2e/browser** / API replay / harness), 3–5 ranked hypotheses, instrumentation, the fix, the **seam-level regression test**, cleanup + post-mortem.

- Ticketed or known-env bug → push diagnose toward an **automated** loop (api or e2e/browser) over HITL — you have the env and steps.
- Diagnose **cannot reproduce**, or surfaces a wrong binding design decision → stop; report `cannot_reproduce` / `design_conflict` and route (Phase 3).

Exit gate: root cause known, fix applied, seam regression test green (or seam-absence explicitly documented per diagnose Phase 5).

## Phase 2 — Broaden coverage (proportional)

Diagnose gave you the seam regression test. Decide whether a **higher tier** is warranted. Add the **lowest tier that reproduces the bug pattern at its right home** — don't gold-plate.

| Bug class | Add a test? | Where |
|-----------|-------------|-------|
| Cosmetic / copy / caption / one-off layout | No new e2e/api — rely on the seam unit test or static check | — |
| Logic / calculation / mapping / null-handling | Yes, at the seam | `unit` / `integration` |
| Contract / envelope / authz / status-code | Yes — it's a backend contract | `api` → `11700-payable/verification/api` per `…/api/AUTHORING.md` |
| User-visible flow that **escaped to the verification phase** | Yes — the journey had no guard | `e2e/browser` → `11700-payable/verification/ui-e2e` per `…/ui-e2e/AUTHORING.md` |

Tiers are the standard set: `static → unit → integration → api → e2e/browser`. Reference the AUTHORING recipes — **never embed** them; new scenarios land on the branch like code. A bug that slipped a feature's smoke gate means the **gate** had a gap → that scenario belongs in `VERIFICATION-PLAN.md` + a `NNNN-smoke-*` subtask (Phase 3), not just an inline test.

**Corpus ratchet.** Any `api`/`e2e` scenario this phase adds is *permanent*: mark it with the catalog's corpus convention (see the matching `AUTHORING.md`) citing the ticket/finding it reproduces. A bug from an adversary-gate finding **always** gets a catalog scenario (the finding is a runtime repro by construction — its class row above never downgrades it to "no new e2e/api"). Standing suites thus accumulate every escaped bug and every adversary catch — each future feature inherits them as free checks.

**Verify:** re-run diagnose's loop plus every tier you added/touched — all green before proceeding. Remove all `[DEBUG-...]` instrumentation (grep the prefix).

## Phase 2.5 — Escape analysis

Interrogate why the existing guard missed the bug and name the miss class — procedure + applicability: [ESCAPE-ANALYSIS.md](ESCAPE-ANALYSIS.md). Carry the miss class into Phase 4's report.

## Phase 3 — Reconcile the source of truth (feature sessions only)

A fix on an unreleased feature can invalidate a load-bearing artifact. Triage what changed and **route to the owning skill** — never hand-edit across an ownership boundary (breaks Jira sync, ADR numbering, grill provenance). The reads that only locate which artifacts need reconciling (PRD / SDD / ADRs / VERIFICATION-PLAN) go through an `afk-reader` returning a cited digest of what each asserts vs the fix, per `DELEGATION.md` (plugin root); triage and routing stay here.

| What the fix revealed | Stale artifact | Route to |
|-----------------------|----------------|----------|
| A behavior the PRD specifies was wrong / changed | `PRD.md` + requirement ADR | `/afk:to-prd` → `/afk:to-ticket` (republish) |
| A **frozen** SDD §8 interface / seam / design decision is wrong or infeasible | `SDD.md` + design ADR | `/afk:grill-solution` → `/afk:to-sdd` (superseding ADR under `adr/design/`) — this is a `design_conflict` |
| The bug had **no verification scenario** that would catch it | `VERIFICATION-PLAN.md` + smoke gate | `/afk:grill-verification` → `/afk:to-verification-plan`; seed a `NNNN-smoke-*` subtask |
| An in-flight subtask's `## Produces` / contract shifted | `plan/NNNN-slug.md` | surface to the `/afk:execute` run; don't silently re-slice |
| The bug could not be reproduced (diagnose built no loop) | none — nothing to reconcile yet | back to the reporter/human with the repro-attempt evidence (what was tried, what's needed); report `cannot_reproduce` |

Doc right + code wrong → no artifact change. Reconcile only when the fix changed something a doc asserts. Can't reach truth this session → record the divergence and report `needs_artifact_sync`.

## Phase 3.5 — Workflow feedback

Trace the miss to the AFK stage that under-specified the guard and **record** a structured workflow lesson in the lesson ledger (never self-applied) — procedure + applicability: [WORKFLOW-FEEDBACK.md](WORKFLOW-FEEDBACK.md). Report the lesson id in Phase 4.

## Phase 4 — Report

End with the structured line plus one plain-terms sentence per the reporting protocol (`REPORTING.md` at the plugin root):

```
OUTCOME: <status> — <one-line summary> [ticket: <KEY|none>]
In plain terms: <one jargon-free sentence — what was broken, what's true now, what (if anything) still needs a human>
```

| Status | Meaning / next action |
|---|---|
| `fixed` | Root cause found, fix applied, regression test + any added tier green. |
| `fixed_no_test` | Fix applied, no new test, naming the proportionality reason (e.g. caption fix) or the absent-seam finding from diagnose. |
| `cannot_reproduce` | Diagnose couldn't build a loop; list what was tried and what's needed (env / artifact / instrumentation). |
| `design_conflict` | Fix requires changing a frozen SDD/ADR decision; routed to `/afk:grill-solution`. |
| `needs_artifact_sync` | Fix landed but a load-bearing artifact is now stale and unreconciled; name it + the owning skill. |
| `blocked` | Anything else; explain. |

Phase 2.5 ran → add the **miss class** to the summary; Phase 3.5 ran → append the **lesson id** so the workflow-improvement lesson isn't lost:

```
OUTCOME: fixed — <summary> [ticket: <KEY>] [miss: <class>] [lesson: <L-NNNN>]
```

## Hard rules

- **Never commit, push, or merge.** `fix` is not in the commit lane — the human commits, or the calling run does (resumes and drives commit + push + MR itself). Apply edits and stop.
- **The target repo's CLAUDE.md chain binds here** — notably its DB-migration and commit rules.
- **Never hand-edit PRD / SDD / ADRs / VERIFICATION-PLAN / PLAN.md across an ownership boundary.** Route to the owning skill (Phase 3).
- **Never edit the AFK skills themselves in a fix session.** Phase 3.5's workflow lesson is **recorded in the lesson ledger** (a runtime ledger append via `hooks/lesson-append.sh`, not a skill edit) and applied later via `/afk:lessons apply` — no retrospective side-trips, no in-session edit of any `SKILL.md` under the plugin repo.
- **Don't gold-plate tests.** No brand-new e2e/api scenario for a trivial cosmetic fix — match tier to bug class (Phase 2).
- Before declaring done, all `[DEBUG-...]` instrumentation removed and throwaway harnesses deleted (diagnose Phase 6).
