---
name: to-prd
description: Turn the current conversation context into a PRD and write it to the repo as a local artifact (PRD.md + requirement ADRs). Does NOT touch any issue tracker. Use when user wants to create a PRD from the current context.
---

Do NOT interview the user on requirements content — just synthesize what you already know. (Step 2's module/tests check-in is the one sanctioned exception.)

Write `PRD.md` (and any requirement-level ADRs) to the repo and stop — publishing the PRD to a tracker is the separate **`/afk:to-ticket`** skill, run afterwards.

**Claim-ledger gate.** Before writing, check every load-bearing claim about **this repo** that the requirements rest on. If the ledger didn't survive into context, first read the ticket folder's on-disk `GRILL-LOG.md` checkpoint and take its settled rows as the ledger — re-verify from scratch only what the log lacks. Any claim still not `verified` — whether its ledger row says otherwise or is missing — is verified **now** (one search/read) or the synthesis **refuses**, naming the claim; never build a PRD on an unverified or refuted in-repo premise. Run these in-repo re-verifications in `afk-reader` subagents — parallel where the claims are independent — each returning a cited confirm/refute digest, per `DELEGATION.md` (plugin root). Claims marked `unverified-external` (outside this repo, user-acknowledged) are allowed in, but every requirement resting on one carries the literal label `(unverified premise: {claim})` where it appears in the PRD.

## Process

1. Explore the repo for current codebase state, if not already done — delegate that exploration per `DELEGATION.md`; the PRD synthesis itself stays inline, since it synthesizes this conversation. Use the project's domain glossary vocabulary throughout the PRD; respect any ADRs in the area you're touching.

2. Sketch the major modules to build or modify for the implementation. Actively look for deep modules that can be tested in isolation.

A deep module (vs a shallow one) encapsulates a lot of functionality behind a simple, testable interface that rarely changes.

Check with the user that these modules match their expectations, and which modules they want tests written for — this check-in is the sanctioned exception to the no-interview rule above.

3. Write the PRD using the format in [PRD-TEMPLATE.md](./PRD-TEMPLATE.md), applying the template's **concision doctrine** banner throughout.

4. **Emit requirement-level ADRs.** The PRD's `## Implementation Decisions` is the broad list. From it, extract the *behavioural* decisions that clear the three-part bar owned by [ADR-FORMAT.md](./ADR-FORMAT.md) ("When to emit a requirement ADR"); write each as a standalone ADR in the ticket-local `adr/requirements/` subfolder, sibling to the PRD, per that format. These record the *what / why* (feature behaviour, scope boundaries) — NOT the *how* (algorithm / pattern / tech), which `/afk:to-sdd` records separately under `adr/design/`. Skip this step entirely if no decision clears the bar — most small PRDs won't.

5. **Consolidate unverified premises.** If any requirement carries the `(unverified premise: {claim})` label, list them all in one short block under `## Further Notes` ("Assumptions this PRD rests on") — a reader must be able to see every assumption in one place instead of grepping the document.

6. **Create the ticket index.** Write `INDEX.md` sibling to the PRD per [INDEX-FORMAT.md](./INDEX-FORMAT.md): the one-paragraph feature summary (plain domain language), every artifact row seeded, this skill's rows filled (`PRD: draft`, requirement-ADR count). Later skills fill their own rows; the summary stays yours — keep it current if the PRD's problem statement materially changes.

7. **Fold in the staples.** For each staple **accepted** for this feature in context (from `{service}/STAPLES.md`), make sure the PRD carries it as a User Story / acceptance criterion — the design and plan key off the PRD, not the registry. Record each in/out **call** as a requirement ADR whenever it clears the three-part bar; an *out* on a matching staple is exactly the "surprising without context + real trade-off" shape that warrants one. If the context flagged this feature as a **candidate new staple**, note it in `## Implementation Decisions` so the terminal `NNNN-sync-harness` subtask can make the final call at delivery. **Do NOT write to `STAPLES.md` here** — its only writer is `/afk:claude-md`.

**Done when:** `PRD.md`, every requirement ADR, and the `INDEX.md` (summary + this skill's rows) are on disk; every accepted staple appears as an acceptance criterion; every `(unverified premise: …)` label is consolidated under `## Further Notes`.

## Monorepo conventions (core-services)

The **on-disk location** is load-bearing — downstream skills (`/afk:to-sdd`, `/afk:to-subtasks`) find the PRD by convention, not by a tracker pointer. This section is the owning home of the spec-folder path convention; other skills point here.

- **PRD file location.** Write to `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/PRD.md` for service-scoped work, or `tasks/{TICKET-ID}/PRD.md` when the work is cross-cutting tooling (the PRD's `## Service:` line is `tasks`). Service is derived from the ticket / project key per the project's mapping — e.g. project `P2P` maps to service `11700-payable`. `year` is the calendar year, `release` is the n-th release of that year (1-indexed).

- **`{TICKET-ID}`** is the parent ticket key the PRD belongs to (e.g. `P2P-1220`). This skill neither creates nor fetches that ticket — the key comes from the user / session context. If no key is known yet, write under a provisional slug and rename the folder once the key exists.

## Next

This skill stops at the local PRD (+ requirement ADRs). Then, in order:

- **`/afk:to-ticket`** — publish the full PRD content into the **existing** parent ticket as native Jira formatting (mermaid diagrams rendered + embedded); idempotent, and preserves any product-owner content already in the ticket. (Requires a parent key — it does not create the ticket.)
- **`/afk:prototype`** *(optional)* — if the feature has meaningful net-new UI, craft the screens interactively now, against the **real frontend's** look, before the SDD locks decisions. Writes `PROTOTYPE.md` + chosen HTML sibling to this PRD; self-gates `no_ui` for backend-only features. Feeds `/afk:grill-solution` (UX decisions) and gives `/afk:grill-verification`'s UI journeys a concrete screen to trace.
- **`/afk:grill-solution`** — interview the architecture top-down across L1 → L9 layers.
- **`/afk:to-sdd`** — synthesize the SDD + design ADRs. Without an SDD, the downstream plan slices in uncited mode (PRD-only).
- **`/afk:grill-verification`** *(optional)* → **`/afk:to-verification-plan`** — design the feature's verification scenarios now; the grill interviews, then `/afk:to-verification-plan` writes `VERIFICATION-PLAN.md`. Post-PRD it can design the **UI journeys** (the PRD's User Stories are usually concrete enough; the journey-walk often surfaces PRD gaps worth fixing here) and **defers the API scenarios** until an SDD settles the endpoints — re-run both after `/afk:to-sdd` to append them. Its plan makes `/afk:to-subtasks` add the feature smoke-test gate.
