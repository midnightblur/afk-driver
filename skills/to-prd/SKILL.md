---
name: to-prd
description: Turn the current conversation context into a PRD and write it to the repo as a local artifact (PRD.md + requirement ADRs). Does NOT touch any issue tracker. Use when user wants to create a PRD from the current context.
---

This skill takes the current conversation context and codebase understanding and produces a PRD. Do NOT interview the user — just synthesize what you already know.

**This skill produces local artifacts only.** It writes `PRD.md` (and any
requirement-level ADRs) to the repo and stops there. It does **not** create,
read, or update Jira / GitLab / GitHub issues — publishing the PRD to a tracker
is the job of the separate **`/afk:to-ticket`** skill, run afterwards.

## Process

1. Explore the repo to understand the current state of the codebase, if you haven't already. Use the project's domain glossary vocabulary throughout the PRD, and respect any ADRs in the area you're touching.

2. Sketch out the major modules you will need to build or modify to complete the implementation. Actively look for opportunities to extract deep modules that can be tested in isolation.

A deep module (as opposed to a shallow module) is one which encapsulates a lot of functionality in a simple, testable interface which rarely changes.

Check with the user that these modules match their expectations. Check with the user which modules they want tests written for.

3. Write the PRD using the template below.

<prd-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts — not a working demo, just the important bits.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this PRD.

## Further Notes

Any further notes about the feature.

</prd-template>

4. **Emit requirement-level ADRs.** The PRD's `## Implementation Decisions` is
   the broad list. From it, extract the subset of *behavioural* decisions that
   pass all three of (hard to reverse) AND (surprising without context) AND (a
   real trade-off with ≥2 genuine alternatives), and write each as a standalone
   ADR in the ticket-local `adr/requirements/` subfolder, sibling to the PRD —
   `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/adr/requirements/NNNN-slug.md`.
   Numbering is local to that subfolder, starting at `0001`. Use the format in
   [ADR-FORMAT.md](./ADR-FORMAT.md). These record the *what / why* (feature
   behaviour, scope boundaries) — NOT the *how* (algorithm / pattern / tech),
   which `/afk:to-sdd` records separately under `adr/design/`. Skip this step
   entirely if no decision clears the three-part bar — most small PRDs won't.

## Monorepo conventions (core-services)

The **on-disk location** is load-bearing — downstream skills (`/afk:to-sdd`,
`/afk:to-subtasks`) find the PRD by convention, not by a tracker pointer:

- **PRD file location.** Write to
  `{service}/src/main/resources/specs/{year}r{release}/{ENH-ID}/PRD.md`
  for service-scoped work, or `tasks/{ENH-ID}/PRD.md` when the work is
  cross-cutting tooling (the PRD's `## Service:` line is `tasks`). Service is
  derived from the ticket / project key per the project's mapping — e.g.
  project `P2P` maps to service `11700-payable`. `year` is the calendar year,
  `release` is the n-th release of that year (1-indexed).

- **`{ENH-ID}`** is the parent ticket key the PRD belongs to (e.g. `P2P-1220`).
  This skill does not create or fetch that ticket — the key is supplied by the
  user / session context. If no key is known yet, write under a provisional
  slug and rename the folder once the key exists.

Everything tracker-side — publishing the full PRD content into the (already
existing) parent ticket's description as native Jira formatting, with any
mermaid diagrams rendered and embedded — is handled by **`/afk:to-ticket`**,
not here.

## Next

This skill stops at the local PRD (+ requirement ADRs). Then, in order:

- **`/afk:to-ticket`** — publish the full PRD content into the **existing**
  parent ticket as native Jira formatting (mermaid diagrams rendered + embedded);
  idempotent, and preserves any product-owner content already in the ticket.
  (Requires a parent key — it does not create the ticket.)
- **`/afk:grill-solution`** — interview the architecture top-down across
  L1 → L8 layers.
- **`/afk:to-sdd`** — synthesize the SDD + design ADRs. Without an SDD,
  downstream SubTasks slice in uncited mode (PRD-only).
