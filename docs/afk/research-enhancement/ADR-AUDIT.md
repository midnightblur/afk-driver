# Architecture decision record audit

Audit date: 2026-09-15.

Baseline: `C:\Users\mvu\PersonalProjects\afk-driver-investigation-enhancement\docs\plans\research-enhancement\MERGED-PLAN.md`.

The audit covers all explicit baseline citations in the product requirements document (PRD).
It also covers each architecture decision record (ADR) from 0001 through 0008.

| ADR | Verdict | Citation result |
|---|---|---|
| 0001 | AMEND | The decision adds an unsupported “two features” threshold. |
| 0002 | AMEND | The decision adds an unsupported policy-URL check. |
| 0003 | APPROVE | `§6 D-3` resolves to baseline line 121. |
| 0004 | AMEND | The named role list does not match the baseline. |
| 0005 | APPROVE | `§5` and `§6 D-5` resolve to lines 86-111 and 123. |
| 0006 | AMEND | The rationale conflicts with staged evidence in A9 and D-3. |
| 0007 | APPROVE | A4, A7, and D2 resolve to lines 26, 29, and 49. |
| 0008 | APPROVE | A12, A14, and dispute 6 resolve to lines 34, 36, and 62. |

## ADR-0001

Location: `adr/requirements/0001-no-priorities-registry-now.md:8`.

Verdict: **AMEND**.

Replace line 8 with:

> Inferred organization priorities appear as advisory findings inside the research report (PRD catalog C4, AR-1). A human-accepted priority is written into CLAUDE.md only by `/afk:claude-md` through its existing inclusion bar. No `PRIORITIES.md` registry file is created in this release; the trigger to create one is `/afk:retro` observing repeated re-mining of the same priority (recorded as an IOU, homed beside the staples registry when built). Source: `MERGED-PLAN.md` §2 D1 (:48), §6 D-1 (:119).

## ADR-0002

Location: `adr/requirements/0002-no-training-declared-per-destination.md:8`.

Verdict: **AMEND**.

Replace line 8 with:

> The plugin does not infer a provider's training treatment from its auth type. The repository administrator declares `no_training` per destination in `.afk/config.yaml`, after disabling model improvement or using Team/Enterprise seats; a route that requires the declaration blocks any destination where it is absent (PRD AC-032). The declaration is the administrator's evidence, not the plugin's. Source: `MERGED-PLAN.md` §2 dispute 4 (:60), §6 D-2 (:120).

## ADR-0003

Location: `adr/requirements/0003-web-research-when-relevant-staged-egress.md:8`.

Verdict: **APPROVE**.

The decision matches baseline D-3 at line 121.

## ADR-0004

Location: `adr/requirements/0004-pilot-read-only-claude-codex.md:8`.

Verdict: **AMEND**.

Replace line 8 with:

> The pilot dispatches only read-only jobs to Claude Code and Codex CLI. Gemini CLI is excluded while billing is subscription-only; Antigravity and Grok wait for a recorded live conformance probe (PRD catalog C3). Unfinished read-only jobs resume on another host from `state.json` (AC-028); executor and write-role hops are out of scope and recorded as an IOU on that file. Source: `MERGED-PLAN.md` §1 A13 (:35), §2 D3 (:50), §3 step 5 (:79), §6 D-4 (:122).

## ADR-0005

Location: `adr/requirements/0005-subscription-only-billing-with-credit-declarations.md:8`.

Verdict: **APPROVE**.

The safeguards match baseline §5 at lines 86-111 and D-5 at line 123.

## ADR-0006

Location: `adr/requirements/0006-same-provider-participant-is-native-subagent.md:8`.

Verdict: **AMEND**.

Replace line 8 with:

> When the participant's provider is the host harness, the participant is a native subagent: no subprocess and no billing gate. The participant remains subject to staged evidence and explicit `allowed_paths` grants. `claude -p` is used only when another host calls Claude, and Codex is likewise called headless only from a non-Codex host. The tension between Anthropic's developer-key guidance and its subscription-use statement for `claude -p` is an accepted policy risk (PRD Further Notes). Source: `MERGED-PLAN.md` §1 A9 (:31), §6 D-3 (:121), D-6 (:124-126).

## ADR-0007

Location: `adr/requirements/0007-consultation-is-advisory-only.md:8`.

Verdict: **APPROVE**.

- Plan alignment: A4, A7, and D2 require advisory-only consultation. The ADR adds no decision.
- Reversibility: The decision is two-way. Later work can add an authorized decision path.
- Rationale: The rationale and rejected autonomous-decision alternative match the plan.
- Consistency: The decision matches ADRs 0001-0006 and AC-016 through AC-018.
- Citations: A4 line 26, A7 line 29, and D2 line 49 resolve correctly.

## ADR-0008

Location: `adr/requirements/0008-rejected-extensions.md:8`.

Verdict: **APPROVE**.

- Plan alignment: A12, A14, and dispute 6 reject the 3 extensions. The ADR adds no decision.
- Reversibility: All 3 rejections are two-way decisions.
- Rationale: Each rationale and rejected alternative matches the plan.
- Consistency: The decision matches ADRs 0001-0007 and AC-001 through AC-039.
- Citations: A12 line 34, A14 line 36, and dispute 6 line 62 resolve correctly.

## PRD citation corrections

Location: `PRD.md:3`.

The current statement assigns every ADR to §6. Section 6 contains only D-1 through D-6.

Replace line 3 with:

> Work item: `research-enhancement`. Source of record for D-1..D-6: `MERGED-PLAN.md` §6 (:113-126). ADR-0007 derives from A4, A7, and D2 (:26, :29, :49). ADR-0008 derives from A12, A14, and dispute 6 (:34, :36, :62). Their human acceptance is recorded in `GRILL-LOG.md` (:26-27). Vocabulary: `GLOSSARY.md` (plugin root); new terms below are registered there by the sync-harness subtask.

Location: `PRD.md:164`.

Replace `Run research (PP-1..PP-7)` with `Run research (PP-1..PP-3, PP-7)`.
PP-4 through PP-6 have no research purpose at `PRD.md:90-92`.

All other explicit PRD references and ADR citations resolve correctly.
