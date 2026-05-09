---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead.

## Next

Once the requirements decision tree is exhausted (every actor / user story /
out-of-scope / non-functional concern is settled), run **`/afk:to-prd`** to
synthesize the conversation into a PRD and publish it (Jira parent + repo at
`{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/PRD.md`).
`/afk:to-prd` does NOT re-interview — it synthesizes what was settled here.