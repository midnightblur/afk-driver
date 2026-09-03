---
name: to-demo-plan
description: Demo script for a delivered feature — synthesizes its specs + diff into minute-budgeted DEMO-PLAN.md. Use when the user wants to demo a feature to POs, QA, or stakeholders.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# afk:to-demo-plan — the demo script

Takes a delivered feature's spec artifacts + its diff; emits one `DEMO-PLAN.md` — a script the presenter runs top-to-bottom in front of **product owners and QA**, inside one hour.

**The demo's goal is not proof.** Nobody needs convincing the code runs — the gates settled that. The demo shows the feature from the user's chair: the pain they have today, what they now do instead, why it works the way it does. A beat whose only payload is "…and it works" doesn't belong in the plan.

One plan, two halves of the room: the **PO** judges value and behaviour; **QA** judges reach — what else moved, what to regress, where the edges are.

## Vocabulary

- **beat** — the atomic unit of the script: a **Say** (the presenter's words, in the audience's language), a **Do** (the exact steps), a show/tell class, and a minute cost.
- **show** — performed live in the running app. Costs minutes — spend them on what the audience can't picture from a sentence.
- **tell** — one spoken sentence, nothing clicked. The default for anything obvious, standard, or already familiar.
- **touch point** — a place the feature meets behaviour that already existed, classed `adds` / `changes` / `interacts`.
- **craft note** — a one-line aside on the deliberate call behind what's on screen.
- **arc** — the beat ordering: why → concepts → happy path → touch points → edges. Never descend a level before the one above it has landed.

## Process

1. **Locate + digest the sources.** Ticket spec folder per the path convention in `skills/afk/to-prd/SKILL.md` ("Monorepo conventions"); the plan lands at `.../{TICKET-ID}/DEMO-PLAN.md`, sibling to the PRD. Delegate the digestion **and** the delivered-diff read to an `afk-reader` subagent per `DELEGATION.md` — the plan is written here, from that digest.

   | Source | What it yields |
   |---|---|
   | PRD problem statement + user stories | the why, the pain, the audience's own words |
   | `VERIFICATION-PLAN.md` UI journeys | click-paths already walked concretely — reuse, don't re-derive |
   | ADRs, both tiers | candidate decisions to explain; craft notes |
   | SDD §3 / §8 / §9b + every **existing** file the diff changed | touch-point candidates |
   | `plan/` contracts + `JOURNAL.md` | what actually shipped, and what was cut on the way |
   | PRD out-of-scope + open questions, deferred staples, env-limited verification rows | pre-empts and the out-of-scope section |

   **Thin sources.** No PRD (feature delivered outside a design chain) → build from the diff + the tracker ticket, and ask the human **one** question for the pain the feature addresses. Never invent a value claim; record the plan's basis in the header.

2. **Scope to what is delivered.** A beat may only demo behaviour that exists on the branch. Not every subtask `done` → don't refuse: scope the plan to the delivered ones and name the rest in `## Out of scope`. Nothing delivered → stop and say so.

3. **Shortlist the scenarios.** Rank the user stories by the value the PRD claims for them × how often a real user hits them; the top of that ranking is the **show** list. **Every user story ends up accounted for** — a show beat, a tell line, or an `## Out of scope` row with a reason. A story that silently vanishes is what this step exists to prevent.

4. **Map the touch points.** Sweep every existing surface the feature meets (delegate — the diff is bulk) and class each:

   - `adds` — new surface beside old (a column, an action, a section). Usually **tell**.
   - `changes` — behaviour that already existed now behaves differently. **Always show.**
   - `interacts` — each side unchanged alone, but the two now compose (import/export, permissions, notifications, batch jobs, downstream postings). **Show** when the composition isn't guessable.

   Done when every existing file/endpoint the diff touched is either mapped to a touch point or recorded benign (internal refactor, nothing user-visible).

5. **Pick the decisions worth a sentence.** **≤3 ADRs**, and only ones the audience *feels*: a visible behaviour they'd otherwise question, a constraint they'd otherwise file as a bug, a trade-off they'd otherwise re-litigate in the meeting. One sentence of why, in consequence language, never mechanism. A decision invisible from the UI is out.

6. **Pre-empt.** Answer the question at the beat where it arises — never a Q&A dump at the end. Mine: rejected ADR alternatives, out-of-scope items, deferred staples, env-limited scenarios, open bugs, and anything a beat visibly makes someone wonder "does it also…". One line each.

7. **Budget the arc.** ≤60 minutes total with **≥10 reserved for questions** — beats sum to ≤45. Assign every beat its minutes, order them by the arc. Over budget → demote **show** to **tell**, weakest signal first. Never silently drop a shortlisted story or a `changes` touch point: demote it to a tell line and keep its row.

8. **Write `DEMO-PLAN.md`** using the template.

9. **Rehearsal pass.** Read the plan as the presenter, in order: every `Do` step must be executable against a running app at that moment, and every beat's precondition state must be created by a named `## Setup` step or by an earlier beat. State that nobody creates is the classic demo death — fix it here, not on the call. Then reconcile counts: beats + tells + out-of-scope rows cover the whole shortlist and the whole touch-point map.

10. **Update the ticket index.** Upsert the `Demo plan` row in the sibling `INDEX.md` per `skills/afk/to-prd/INDEX-FORMAT.md`.

**Done when:** `DEMO-PLAN.md` is on disk within budget, every user story and every touched existing surface is accounted for, the rehearsal pass is clean, and the `INDEX.md` row is upserted.

## Template

Write the plan using the template in [DEMO-PLAN-TEMPLATE.md](DEMO-PLAN-TEMPLATE.md).

## Craft notes

The room should leave sensing the feature was thought through — from evidence, not adjectives.

- Ride on something already on screen: the edge case handled, the alternative weighed and dropped, the existing behaviour deliberately left alone.
- One line, factual, in consequence language — *"we looked at X; it would have meant Y for you, so we did Z"*.
- **≤3 in the whole plan.** Never its own beat, never a superlative.
- The tell that ruins it: praising the team, the design, or the effort. State the decision; let them draw the conclusion.

## Hard rules

- **Strict synthesis.** Every claimed behaviour traces to a delivered subtask, a spec artifact, or the diff. Untraceable → cut it or move it to `## Out of scope`. No aspirational demoing.
- **Audience language.** No repo paths, class names, or workflow vocabulary in `Say` lines. `Do` steps name what the presenter clicks — or, for a feature with no UI, the request they send.
- **Show what can't be pictured; tell the rest.** Sorting, pagination, a save toast, a mandatory-field error — one sentence each. A minute spent there is the minute the sharp edge needed.
- **Every `changes` touch point is shown.** Non-negotiable: changed existing behaviour is what breaks the room's mental model and what QA must regress — the demo's highest-value minute.
- **Local artifact.** Writes `DEMO-PLAN.md` + its `INDEX.md` row. No tracker, no MR, no push.

## Next

Rehearse from the file, not from memory — the `Do` steps are the rehearsal. After the demo, questions the plan **didn't** pre-empt are the real signal: a requirements gap routes to `/afk-toolkit:to-prd` (re-publish with `/afk-toolkit:to-ticket` if the ticket is already published), a defect routes to `/afk-toolkit:bug capture`. Re-emit the plan when scope changes — a demo plan goes stale silently.
