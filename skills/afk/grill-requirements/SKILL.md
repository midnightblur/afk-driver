---
name: grill-requirements
description: Grilling session that challenges your plan against the existing domain model, sharpens terminology, and updates the domain glossary (GLOSSARY.md) inline as terms crystallise. Use when user wants to stress-test a plan against their project's language and documented decisions.
---

<what-to-do>

Interview the user relentlessly about every aspect of the plan until a shared understanding is reached. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide a recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing.

If a question can be answered by exploring the codebase, explore the codebase instead.

</what-to-do>

<supporting-info>

## Domain awareness

During codebase exploration, also look for existing documentation. This repo uses
a **multi-context glossary** (root `GLOSSARY-MAP.md` indexing a per-service
`GLOSSARY.md`). The full setup, routing, lazy-create rules, and write format are
owned by **[`/afk:glossary`](../../utils/glossary/SKILL.md)** — its
[`GLOSSARY-FORMAT.md`](../../utils/glossary/GLOSSARY-FORMAT.md) is canonical.
Read `GLOSSARY-MAP.md` first to locate the owning glossary; follow `/afk:glossary`
for everything about *how* the glossary is structured and written. This skill only
adds the **grilling** that resolves terms in the first place.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in the
relevant `GLOSSARY.md`, call it out immediately. "Your glossary defines
'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

### Grill the access & validation policy (every feature)

When the plan touches access or validation, grill it per [ACCESS-POLICY-GRILL.md](ACCESS-POLICY-GRILL.md).

### Update GLOSSARY.md inline

When a term is resolved, update the owning service's `GLOSSARY.md` — or the root
`GLOSSARY.md` if the term is system-wide — immediately. Don't batch these up —
capture them as they happen. Use the format owned by `/afk:glossary`
([GLOSSARY-FORMAT.md](../../utils/glossary/GLOSSARY-FORMAT.md)), including the
lazy-create-and-index rules for a missing map or service glossary.

`GLOSSARY.md` should be totally devoid of implementation details. Do not treat `GLOSSARY.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Decision records come later — don't write them here

This skill builds *understanding*; it does not emit decision records. When a
decision worth recording crystallises during grilling (hard to reverse +
surprising without context + a real trade-off), note it in the conversation so
the downstream synthesis skills capture it as an ADR:

- **Requirement-level** decisions (how the feature must *behave*, what's in/out
  of scope) → recorded by **`/afk:to-prd`** as a requirements ADR.
- **Solution-level** decisions (algorithm, pattern, technology) → recorded by
  **`/afk:to-sdd`** as a design ADR.

The glossary is the one artifact this skill maintains — because it *is* the
shared understanding being built, not a record of a decision.

</supporting-info>

## Next

Once the requirements decision tree is exhausted (every actor / user story /
out-of-scope / non-functional concern is settled, **and every actor/story has a
role policy with at least one denied role, a data-scope policy, and a validation
policy**), run **`/afk:to-prd`** to
synthesize the conversation into a PRD and publish it (Jira parent + repo at
`{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/PRD.md`).
`/afk:to-prd` does NOT re-interview — it synthesizes what was settled here.
