---
name: grill-requirements
description: Grilling session that challenges your plan against the existing domain model, sharpens terminology, and updates the domain glossary (GLOSSARY.md) inline as terms crystallise. Use when user wants to stress-test a plan against their project's language and documented decisions.
---

## What to do

Interview the user relentlessly about every aspect of the plan until shared understanding is reached. Walk each branch of the design tree, resolving decision dependencies one-by-one. Recommend an answer per question.

Ask one at a time; wait for feedback before continuing.

If a question is answerable by exploring the codebase, explore instead — run that exploration in an `afk-reader` subagent returning a cited digest, per `DELEGATION.md` (plugin root), so this session's context stays on the conversation.

**Open with a pre-brief.** Before the first question, spawn one parallel set of `afk-reader` digests (per `DELEGATION.md`): the plan/idea sources, root `GLOSSARY-MAP.md` + the owning service's `GLOSSARY.md`, `{service}/STAPLES.md`, and any existing `GRILL-LOG.md` (the resume point). Grill from the digests; open a source mid-session only when a walk needs wording a digest doesn't settle.

## Domain awareness

During codebase exploration, also look for existing documentation. This repo uses a **multi-context glossary** (root `GLOSSARY-MAP.md` indexing a per-service `GLOSSARY.md`). Setup, routing, lazy-create rules, and write format are owned by **[`/afk:glossary`](../../utils/glossary/SKILL.md)** — its [`GLOSSARY-FORMAT.md`](../../utils/glossary/GLOSSARY-FORMAT.md) is canonical. Read `GLOSSARY-MAP.md` first to locate the owning glossary; follow `/afk:glossary` for everything about *how* the glossary is structured and written. This skill only adds the **grilling** that resolves terms in the first place.

## During the session

### Hunt glossary terms actively — verify early

Standing obligations, from the first exchange:

- **Scan every plan statement and user answer for candidate terms** — domain nouns, lifecycle states, actions, role names. Anything two people could read differently is a candidate.
- **Draft your own definition first** (from the code, the plan, the conversation), then ask the user to **verify** it: "I take 'X' to mean … — correct?" A proposed-definition question beats an open "what does X mean?".
- **Ask the verification question as soon as the candidate surfaces** — an unverified term poisons every question built on it; never batch term verification to the end of the session.

### Challenge against the glossary

When a term conflicts with the existing language in the relevant `GLOSSARY.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

On vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are discussed, stress-test with specific scenarios probing edge cases, forcing the user to be precise about boundaries between concepts.

### Verify claims — maintain the claim ledger

When the user states how something works — existing behaviour, a constraint, an ownership boundary — verify against the code before building requirements on it, per [../grill-solution/GROUNDING-RULE.md](../grill-solution/GROUNDING-RULE.md) (trigger phrases, verify-by-claim-type, miss-handling); delegate the verification per `DELEGATION.md`. Surface a contradiction immediately: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

Keep a running **claim ledger** in the conversation: every load-bearing claim one line — `claim → verified (where) | refuted (where) | unverified-external (user acknowledged)`. A `refuted` row must be **re-settled before exit**: correct the requirement that rested on it, update the row to `verified` against actual behaviour. Only claims about systems outside this repo may stay unverified, and only with the user's explicit acknowledgement. PRD synthesis gates on the ledger — a lost ledger means re-verifying, not waving through.

**Checkpoint the ledger to disk as it changes.** Mirror the ledger, the staples calls, and settled/open decisions into this skill's section of the ticket folder's `GRILL-LOG.md` per [GRILL-LOG-FORMAT.md](GRILL-LOG-FORMAT.md) — update rows as they lock, don't batch to the end. A compaction or pause then costs nothing: the next session resumes from the log instead of re-verifying. When a human is present, render per LAVISH.md (RP-6, playbook `diagram`) for a shared view across every grill's `GRILL-LOG.md` section — **mandatory per LAVISH.md's Primary-path rule**; fallback (driven mode / render failure) per that file, else read the log file directly.

### Challenge the want (find the real pain, not the perceived one)

Users ask for the solution they imagined, not always the one their problem needs. Two standing obligations:

- **Every requirement records its pain.** Before accepting a requirement, elicit the underlying pain/value in one sentence ("what goes wrong today without this?"). A requirement whose pain can't be stated gets challenged, not recorded.
- **Every restrictive rule pays for itself.** Whenever the plan says *disallow / only / never / prevent / must not*, ask the mandatory counter-question: "what legitimate scenario does this block, and how does the user recover when they hit it?" If a plausible legitimate scenario exists, the restriction needs an explicit trade-off decision — not a silent default to the safe-sounding option.

### Devil's-advocate pass (before synthesis)

When the decision tree feels exhausted, spawn one fresh subagent over the settled requirement set (requirements + pains + restrictions + ledger; not the conversation); spawn per `DELEGATION.md`, in background alongside the final confirm batch so it attacks while the user answers — anything settled after the spawn gets a delta-check when its findings return. Brief: attack — which requirement solves a symptom instead of the pain, which restriction blocks a legitimate scenario, which pair of requirements conflicts, what adjacent pain went unaddressed. Surface its findings as the final grill round; resolve or explicitly accept each before moving on.

### Grill the access & validation policy (every feature)

Grill it per [ACCESS-POLICY-GRILL.md](ACCESS-POLICY-GRILL.md) — every run, whether or not the plan mentions access or validation; the exit gate below requires its three policies for every actor and story.

### Go through the staples (every feature)

The pre-brief digest carries the staples registry `{service}/STAPLES.md`. For each `active` staple whose **Trigger** matches this feature, resolve the user *in or out — and why?*, record the rationale in the conversation — a matching staple must never be skipped silently. In/out calls are confirm-class by default: batch them per [TRIAGE.md](TRIAGE.md) (a contested call escalates to debate). Then the mirror question: does this feature mint a **new** staple? If plausibly yes, flag it as a candidate — the authoritative call is made later, at delivery.

### Update GLOSSARY.md inline

When a term resolves (user-verified), immediately update the owning service's `GLOSSARY.md` — or the root `GLOSSARY.md` if system-wide. Don't batch — capture as they happen. Use the format owned by `/afk:glossary` ([GLOSSARY-FORMAT.md](../../utils/glossary/GLOSSARY-FORMAT.md)), including the lazy-create-and-index rules for a missing map or service glossary.

Grill-time definitions are *initial* — the executing skill revises an entry when implementation proves it wrong; never defer writing on that account.

`GLOSSARY.md` must be totally devoid of implementation details — not a spec, scratch pad, or repository for implementation decisions. A glossary and nothing else.

### Decision records come later — don't write them here

This skill builds *understanding*; it does not emit decision records. When a decision worth recording crystallises during grilling (hard to reverse + surprising without context + a real trade-off), note it in the conversation so downstream synthesis skills capture it as an ADR:

- **Requirement-level** decisions (how the feature must *behave*, what's in/out of scope) → recorded by **`/afk:to-prd`** as a requirements ADR.
- **Solution-level** decisions (algorithm, pattern, technology) → recorded by **`/afk:to-sdd`** as a design ADR.

The glossary is the one artifact this skill maintains — it *is* the shared understanding being built, not a record of a decision.

## Next

Only declare the requirements decision tree exhausted when ALL hold:

- Every actor / user story / out-of-scope / non-functional concern settled.
- Every candidate glossary term surfaced during the session has a **user-verified** entry in the owning `GLOSSARY.md`.
- Every actor/story has a role policy with at least one denied role, a data-scope policy, and a validation policy.
- Every `active` staple whose Trigger matches this feature is resolved in/out with a rationale.
- The claim ledger is settled — every load-bearing claim verified or explicitly unverified-external.
- Every requirement carries its pain; every restriction survived its counter-question.
- The devil's-advocate pass ran with its findings resolved.

Then **commit the session's glossary updates** as their own commit (glossary changes only — `{TICKET-ID}: glossary — <terms>`). Then run **`/afk:to-prd`** to synthesize the conversation into a PRD in the ticket's spec folder (path convention: `skills/afk/to-prd/SKILL.md`, "Monorepo conventions"). `/afk:to-prd` does NOT re-interview — it synthesizes what was settled here.
