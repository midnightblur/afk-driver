# TRIAGE.md — debate vs confirm (batching the trivial tail)

The one home for grill-question triage. Grill skills batch points here;
this file names no caller.

## The rule

Before asking, classify every pending question in the current section/layer:

- **Debate** — the decision has ≥2 live alternatives worth weighing, a premise
  the grounding rule must check, or a dependency on an unanswered question.
  Asked **one at a time**, full treatment (recommend, force alternatives,
  capture rationale) — batching never applies.
- **Confirm** — the recommendation is safe-by-default, independent of every
  unanswered question, and the user's whole job is accept-or-override:
  registry in/out calls, env-reachability flags, naming, defaults, which
  existing pattern to copy.

Confirms accumulate; at the section/layer boundary (never across layers),
present them as **one batch** — per item: question, recommended
answer, one-line why.

## Evidence pre-fill

Ground each confirm item as it accumulates — never wait for the batch to
form: on classifying an item confirm, delegate (per `DELEGATION.md`, plugin
root — in background, overlapping the interview) a fresh-context subagent
to find the repo evidence the recommendation rests on — the registry row,
existing pattern, or config — returning the recommended answer plus **one
citation** (`file:line` or registry row). By the section/layer boundary
the batch is ready with zero wait; it presents question + recommended
answer + citation, so the user scans instead of researches.
An item the subagent cannot cite, or whose evidence contradicts the
recommendation, leaves the batch and becomes debate-class before
presentation.

## Answering the batch

- **Human present:** render per LAVISH.md (RP-7, playbook `input`) — one
  control per item (accept / pick listed alternative / write-in), one send
  returns every answer. **Mandatory per LAVISH.md's Primary-path rule**;
  a licensed skip (driven mode / render failure / user opt-out) per that
  file, else below.
- **Markdown fallback / driven mode:** one numbered table in the
  conversation; the user answers all items in a single message
  (`1 yes · 2 no, use X · 3 yes`). Unanswered items are re-asked, never
  defaulted.

## Escalation and locking

- Any item the user **overrides or questions** leaves the batch, becomes
  debate-class — re-grilled one-at-a-time before locking.
- A batch-accepted item locks with its recommended rationale and checkpoints
  into `GRILL-LOG.md` like any other decision
  ([GRILL-LOG-FORMAT.md](GRILL-LOG-FORMAT.md)).
- Misclassification bias: when in doubt, debate. A wrongly-batched decision
  ships unexamined; a wrongly-debated one only costs a turn.
