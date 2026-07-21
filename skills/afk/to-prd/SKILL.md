---
name: to-prd
description: Turn the current conversation context into a PRD and write it to the repo as a local artifact (PRD.md + requirement ADRs). Does NOT touch any issue tracker. Use when user wants to create a PRD from the current context.
---

Don't interview on requirements content — synthesize what you already know. (Step 2's module/tests check-in is the only exception.)

Write `PRD.md` (+ any requirement ADRs) to the repo and stop. Publishing to a tracker = separate **`/afk:to-ticket`**, run afterwards.

**Claim-ledger gate.** Before writing, check every load-bearing claim about **this repo** the requirements rest on. If the ledger didn't survive into context, read the ticket folder's `GRILL-LOG.md` checkpoint and take its settled rows as the ledger; re-verify from scratch only what the log lacks. Any claim not `verified` — ledger says otherwise or row missing — is verified **now** (one search/read) or the synthesis **refuses**, naming the claim. Never build on an unverified/refuted in-repo premise. Run in-repo re-verifications in `afk-reader` subagents (parallel where independent), each returning a cited confirm/refute digest, per `DELEGATION.md` (plugin root). Claims marked `unverified-external` (outside this repo, user-acknowledged) are allowed, but every requirement resting on one carries the literal label `(unverified premise: {claim})` where it appears.

## Process

1. Explore the repo for codebase state if not already done — delegate per `DELEGATION.md`; PRD synthesis stays inline (it synthesizes this conversation). Use the domain glossary vocabulary throughout; respect ADRs in the area you touch.

2. Sketch the major modules to build/modify. Favor **deep modules** — a lot of functionality behind a simple, testable interface that rarely changes (vs a shallow one). Check with the user that these match expectations and which they want tests for — the one sanctioned exception to no-interview.

3. Write the PRD per [PRD-TEMPLATE.md](./PRD-TEMPLATE.md), applying its **concision doctrine** throughout.

4. **Emit requirement-level ADRs.** From the PRD's `## Implementation Decisions`, extract the *behavioural* decisions clearing the three-part bar in [ADR-FORMAT.md](./ADR-FORMAT.md) ("When to emit"); write each standalone in `adr/requirements/` sibling to the PRD, per that format. These record *what / why* (behaviour, scope boundaries) — NOT *how* (algorithm/pattern/tech), which `/afk:to-sdd` records under `adr/design/`. Skip if nothing clears the bar (most small PRDs).

5. **Consolidate unverified premises.** If any requirement carries a `(unverified premise: {claim})` label, list them all in one block under `## Further Notes` ("Assumptions this PRD rests on") — every assumption visible in one place.

6. **Create the ticket index.** Write `INDEX.md` sibling to the PRD per [INDEX-FORMAT.md](./INDEX-FORMAT.md): one-paragraph feature summary (plain domain language), every artifact row seeded, this skill's rows filled (`PRD: draft`, requirement-ADR count). Later skills fill their rows; the summary stays yours — keep it current if the problem statement materially changes.

7. **Fold in the staples.** For each staple **accepted** for this feature (from `{service}/STAPLES.md`), carry it in the PRD as a User Story / acceptance criterion — design and plan key off the PRD, not the registry. Record each in/out **call** as a requirement ADR when it clears the three-part bar; an *out* on a matching staple is the "surprising + real trade-off" shape that warrants one. If context flagged this feature as a **candidate new staple**, note it in `## Implementation Decisions` so the terminal `NNNN-sync-harness` subtask decides at delivery. **Do NOT write `STAPLES.md`** — its only writer is `/afk:claude-md`.

**Done when:** `PRD.md`, every requirement ADR, and `INDEX.md` (summary + this skill's rows) are on disk; every accepted staple appears as an acceptance criterion; every `(unverified premise: …)` label is consolidated under `## Further Notes`.

## Monorepo conventions (core-services)

The **on-disk location** is load-bearing — downstream skills (`/afk:to-sdd`, `/afk:to-subtasks`) find the PRD by convention, not a tracker pointer. This is the owning home of the spec-folder path convention; others point here.

- **PRD location.** `{service}/specs/{year}r{release}/{TICKET-ID}/PRD.md` for service-scoped work, or `tasks/{TICKET-ID}/PRD.md` for cross-cutting tooling (PRD's `## Service:` line = `tasks`). Service derives from the ticket/project key per the project mapping — e.g. `P2P` → `11700-payable`. `year` = calendar year; `release` = n-th release of that year (1-indexed).
- **`{TICKET-ID}`** = the parent ticket key (e.g. `P2P-1220`). This skill neither creates nor fetches it — the key comes from user/session context. If none yet, write under a provisional slug and rename the folder once it exists.

## Next

Stops at the local PRD (+ requirement ADRs). Then, in order:

- **`/afk:to-ticket`** — distill the PRD to a requirements-level ticket description and publish it into the **existing** parent ticket as native Jira formatting (mermaid rendered + embedded); idempotent, preserves product-owner content. Requires a parent key — doesn't create the ticket.
- **`/afk:prototype`** *(optional)* — if the feature has meaningful net-new UI, craft the screens now against the **real frontend's** look, before the SDD locks decisions. Writes `PROTOTYPE.md` + chosen HTML sibling to the PRD; self-gates `no_ui` for backend-only. Feeds `/afk:grill-solution` and gives `/afk:grill-verification`'s UI journeys a concrete screen.
- **`/afk:grill-solution`** — interview the architecture top-down L1 → L9.
- **`/afk:to-sdd`** — synthesize SDD + design ADRs. Without an SDD the plan slices uncited (PRD-only).
- **`/afk:grill-verification`** *(optional)* → **`/afk:to-verification-plan`** — design verification scenarios; the grill interviews, then `/afk:to-verification-plan` writes `VERIFICATION-PLAN.md`. Post-PRD it can design the **UI journeys** (User Stories are usually concrete enough; the walk often surfaces PRD gaps) and **defers API scenarios** until an SDD settles the endpoints — re-run both after `/afk:to-sdd`. Its plan makes `/afk:to-subtasks` add the feature smoke-test gate.
