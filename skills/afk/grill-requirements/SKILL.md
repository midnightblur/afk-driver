---
name: grill-requirements
description: Grilling session that challenges your plan against the existing domain model, sharpens terminology, and updates the domain glossary (GLOSSARY.md) inline as terms crystallise. Use when user wants to stress-test a plan against their project's language and documented decisions.
---

## What to do

Interview the user relentlessly about every aspect of the plan until shared understanding is reached. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide a recommended answer.

Ask questions one at a time; wait for feedback on each before continuing.

If a question can be answered by exploring the codebase, explore it instead — run that exploration in an `afk-reader` subagent returning a cited digest, per `DELEGATION.md` (plugin root), so this session's context stays on the conversation.

## Domain awareness

During codebase exploration, also look for existing documentation. This repo uses a **multi-context glossary** (root `GLOSSARY-MAP.md` indexing a per-service `GLOSSARY.md`). Setup, routing, lazy-create rules, and write format are owned by **[`/afk:glossary`](../../utils/glossary/SKILL.md)** — its [`GLOSSARY-FORMAT.md`](../../utils/glossary/GLOSSARY-FORMAT.md) is canonical. Read `GLOSSARY-MAP.md` first to locate the owning glossary; follow `/afk:glossary` for everything about *how* the glossary is structured and written. This skill only adds the **grilling** that resolves terms in the first place.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in the relevant `GLOSSARY.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about boundaries between concepts.

### Verify claims — maintain the claim ledger

When the user states how something works — the existing behaviour, a constraint, an ownership boundary — verify it against the code before building requirements on it, per the discipline in [../grill-solution/GROUNDING-RULE.md](../grill-solution/GROUNDING-RULE.md) (trigger phrases, verify-by-claim-type, miss-handling) — delegate the verification per `DELEGATION.md`. A contradiction is surfaced immediately: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

Keep a running **claim ledger** in the conversation: every load-bearing claim gets one line — `claim → verified (where) | refuted (where) | unverified-external (user acknowledged)`. A `refuted` row must be **re-settled before exit**: correct the requirement that rested on it and update the row to `verified` against the actual behaviour. Only claims about systems outside this repo may stay unverified, and only with the user's explicit acknowledgement. The ledger is what the PRD synthesis gates on — a lost ledger means re-verifying, not waving through.

**Checkpoint the ledger to disk as it changes.** Mirror the ledger, the staples calls, and settled/open decisions into this skill's section of the ticket folder's `GRILL-LOG.md` per [GRILL-LOG-FORMAT.md](GRILL-LOG-FORMAT.md) — update rows as they lock, don't batch to the end. A compaction or pause then costs nothing: the next session resumes from the log instead of re-verifying. When a human is present, render per LAVISH.md (RP-6, playbook `diagram`) for a shared view across every grill's `GRILL-LOG.md` section; markdown fallback and driven mode read the log file directly instead.

### Challenge the want (find the real pain, not the perceived one)

Users ask for the solution they imagined, not always the one their problem needs. Two standing obligations:

- **Every requirement records its pain.** Before accepting a requirement, elicit the underlying pain/value in one sentence ("what goes wrong today without this?"). A requirement whose pain can't be stated gets challenged, not recorded.
- **Every restrictive rule pays for itself.** Whenever the plan says *disallow / only / never / prevent / must not*, ask the mandatory counter-question: "what legitimate scenario does this block, and how does the user recover when they hit it?" If a plausible legitimate scenario exists, the restriction needs an explicit trade-off decision — not a silent default to the safe-sounding option.

### Devil's-advocate pass (before synthesis)

When the decision tree feels exhausted, spawn one fresh subagent over the settled requirement set (requirements + pains + restrictions + ledger; not the conversation); spawn per `DELEGATION.md`. Its brief: attack — which requirement solves a symptom instead of the pain, which restriction blocks a legitimate scenario, which pair of requirements conflicts, what adjacent pain went unaddressed. Surface its findings to the user as the final grill round; each finding is resolved or explicitly accepted before moving on.

### Grill the access & validation policy (every feature)

Grill it per [ACCESS-POLICY-GRILL.md](ACCESS-POLICY-GRILL.md) — every run, whether or not the plan mentions access or validation; the exit gate below requires its three policies for every actor and story.

### Go through the staples (every feature)

Read the service's staples registry `{service}/STAPLES.md` at the start, alongside `GLOSSARY.md`. For each `active` staple whose **Trigger** matches this feature, resolve the user *in or out — and why?*, and record the rationale in the conversation — a matching staple must never be skipped silently. The in/out calls are confirm-class by default: batch them per [TRIAGE.md](TRIAGE.md) (a contested call escalates to debate). Then raise the mirror question: does this feature itself mint a **new** staple? If plausibly yes, flag it as a candidate — the authoritative call is made later, at delivery.

### Update GLOSSARY.md inline

When a term is resolved, update the owning service's `GLOSSARY.md` — or the root `GLOSSARY.md` if the term is system-wide — immediately. Don't batch these up — capture them as they happen. Use the format owned by `/afk:glossary` ([GLOSSARY-FORMAT.md](../../utils/glossary/GLOSSARY-FORMAT.md)), including the lazy-create-and-index rules for a missing map or service glossary.

`GLOSSARY.md` should be totally devoid of implementation details. Don't treat `GLOSSARY.md` as a spec, scratch pad, or repository for implementation decisions. It is a glossary and nothing else.

### Decision records come later — don't write them here

This skill builds *understanding*; it does not emit decision records. When a decision worth recording crystallises during grilling (hard to reverse + surprising without context + a real trade-off), note it in the conversation so downstream synthesis skills capture it as an ADR:

- **Requirement-level** decisions (how the feature must *behave*, what's in/out of scope) → recorded by **`/afk:to-prd`** as a requirements ADR.
- **Solution-level** decisions (algorithm, pattern, technology) → recorded by **`/afk:to-sdd`** as a design ADR.

The glossary is the one artifact this skill maintains — because it *is* the shared understanding being built, not a record of a decision.

## Next

Only declare the requirements decision tree exhausted when ALL hold:

- Every actor / user story / out-of-scope / non-functional concern settled.
- Every actor/story has a role policy with at least one denied role, a data-scope policy, and a validation policy.
- Every `active` staple whose Trigger matches this feature is resolved in/out with a rationale.
- The claim ledger is settled — every load-bearing claim verified or explicitly unverified-external.
- Every requirement carries its pain; every restriction survived its counter-question.
- The devil's-advocate pass ran with its findings resolved.

Then run **`/afk:to-prd`** to synthesize the conversation into a PRD written to the ticket's spec folder (path convention: `skills/afk/to-prd/SKILL.md`, "Monorepo conventions"). `/afk:to-prd` does NOT re-interview — it synthesizes what was settled here.
