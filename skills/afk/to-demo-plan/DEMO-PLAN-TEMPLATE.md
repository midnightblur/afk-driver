# `DEMO-PLAN.md` template

Fill every section. Prose is what the presenter **says**, so write it speakable — short sentences, no clauses to unpack mid-breath. `{…}` are slots; the bullets under each heading are authoring rules, not content to copy.

---

```markdown
# {Feature name} — demo plan

**Audience:** product owners + QA · **Runtime:** {n} min of beats + {m} min questions
**Demo on:** {environment / branch} · **Basis:** {PRD + SDD + diff | diff only} · **Last updated:** {date}

## The pitch

{2–3 speakable sentences: what the user has to do today and why it hurts, what they do
instead now, who feels it. This is the only section the presenter may deliver from memory.}

## Setup — before anyone joins

| # | Do this | Leaves you with |
|---|---|---|
| S1 | {step} | {the state a beat depends on} |

- Everything a beat needs and no beat creates lives here — logins, records in a
  particular state, a second user, a switched-off toggle.
- Name the reset: how to get back to S-state if a beat has to be re-run live.

## Run sheet

| # | Beat | Class | Min | Covers |
|---|---|---|---|---|
| B1 | {title} | show | {n} | {user story / touch point / decision} |

- The whole demo on one screen, in running order, following the arc:
  why → concepts → happy path → touch points → edges.
- `Class` is `show` or `tell`. Minutes live only here.
- Beats sum to ≤45; questions keep ≥10.

## Beats

### B1 — {title}

**Say:** {the point of this beat, in the audience's words. 1–3 sentences.}

**Do:**
1. {exact step — the screen, the element, the value typed}
2. {…}

**Land it:** {the one sentence they should leave the beat holding.}

**Pre-empt:** {question they're about to ask} → {one-line answer}

**Craft note:** {optional, ≤3 across the whole plan — the deliberate call behind what's on screen}

**If it stalls:** {optional — what to say and where to go next if this beat misbehaves live}

- A `tell` beat has a `Say` and `Do: —`.
- `Do` steps are followable by someone who has never opened the feature: no
  "navigate to the usual place", no implied state.
- Never write the beat's payload only in `Do`. If the screen carries the meaning,
  `Say` still states it — the audience watches the cursor, not the diff.

## Touch points with what already exists

| Existing surface | Class | What the room needs to know | Where |
|---|---|---|---|
| {screen / job / export} | changes | {what is different now} | B{n} |
| {…} | adds | {what is new beside it} | tell only |
| {…} | interacts | {what the two now do together} | B{n} |

- Every `changes` row points at a beat — never `tell only`.
- QA reads this table as the regression scope; keep it exhaustive even where the
  answer is "no visible change" (say so and why).

## Decisions worth a sentence

| You'll notice | Why it's that way |
|---|---|
| {the visible behaviour or constraint} | {one sentence, in consequences — not mechanism} |

- ≤3 rows. Only decisions the audience can see or feel.

## Out of scope

| Not in this demo | Why | Coming? |
|---|---|---|
| {capability / scenario} | {deliberately deferred / not built / can't run in this environment} | {next iteration / no — reason / undecided} |

- Everything the shortlist dropped, everything the PRD deferred, every
  environment-limited scenario. Silence here becomes an assumption in the room.

## If it goes wrong

- {the two or three failure modes with a live recovery: which beat to skip to,
  what to say, what not to debug on the call}

## Coverage ledger

| User story | Shown as | 
|---|---|
| {story} | B{n} / tell in B{n} / out of scope |

- Every user story from the PRD appears exactly once. This is the check that the
  demo represents the feature, not just its most demoable parts.
```
