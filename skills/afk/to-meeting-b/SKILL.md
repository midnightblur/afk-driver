---
name: to-meeting-b
description: Meeting B, the design review — a timed design-review meeting plan. Synthesizes PRD, SDD and ADRs into a 60-minute DESIGN-REVIEW-PLAN.md with segment cards, objection windows and an undecided exit. Use when the user must present settled scope and design to a product owner, QA, a development director, or a team lead.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# afk:to-meeting-b — the design-review script

Meeting B is the design review: the room sees settled scope and design before
the code is built (`GLOSSARY.md`, "Meeting B").

Takes a feature's settled specs; emits one `DESIGN-REVIEW-PLAN.md` — the run
sheet a presenter works top-to-bottom in a fixed hour, in front of four roles
who each judge something different.

**The meeting is not a readthrough.** The room already has the pre-read. The
hour buys challenge and verdicts, so the plan's real payload is the objection it
anticipates and the evidence that answers it. A segment that only recites an
artifact section is the segment that leaves no time for the dispute.

**This skill decides nothing about the design.** It selects, orders, budgets and
arms. Discovery, options and sign-off stay upstream in their own artifacts, and
a change the room asks for goes back to the owner of the artifact that holds it.

Shared grammar — lanes, agenda, segment cards, objection windows, dispositions,
fallback — is [MEETING-PLAN-FORMAT.md](MEETING-PLAN-FORMAT.md). The visual set
is [NOTATIONS.md](NOTATIONS.md). The artifact shape is
[PLAN-TEMPLATE.md](PLAN-TEMPLATE.md).

## Process

1. **Locate + digest the sources.** Ticket spec folder per the path convention
   in `skills/afk/to-prd/SKILL.md` ("Monorepo conventions"); the plan lands at
   `.../{TICKET-ID}/DESIGN-REVIEW-PLAN.md`, sibling to the PRD. Delegate the
   digestion to an `afk-reader` subagent per `DELEGATION.md` — the plan is
   written here, from that digest.

   | Source | Required | What it yields |
   |---|---|---|
   | `PRD.md` | yes | the problem, scope, stories, out-of-scope, success |
   | `SDD.md` (complete Draft) | yes | topology, runtime, lifecycle, risks, seams |
   | `adr/requirements/`, `adr/design/` | yes | the decisions worth defending, with rejected options |
   | `GRILL-LOG.md` | no | what is signed off and what is still open — **read only** |
   | `VERIFICATION-PLAN.md` | no | concrete journeys and scenarios; proof for the risk segment |
   | `DESIGN-BRIEF.md` | no | the pre-read to send ahead |
   | `PROTOTYPE.md` + the chosen prototype HTML | no | the user-journey visual |

   **Readiness.** Refuse only when the required three cannot support a
   presentation — no PRD, no SDD beyond an outline, no decisions recorded. Open
   stakeholder decisions are what the meeting is for, so they never block it. A
   missing optional source removes the content it would have supported and
   nothing else.

2. **Check the sources against each other, before writing anything.** Authority
   follows ownership: `PRD.md` owns requirement and scope facts; `SDD.md` and
   design ADRs own solution facts; `GRILL-LOG.md` owns sign-off and open state.
   Where two authoritative sources disagree, **stop**. Name both sources and the
   contradiction, route it to the owning artifact, and emit no plan. A
   disagreement between the requirement and the design is exactly what a design
   review exists to surface — a plan that quietly picks a winner spends the
   meeting hiding it.

3. **Build the source ledger.** One row per claim the presenter will make,
   pointing at the artifact section behind it. Write it first: a claim that
   cannot get a row is a claim the plan drops, and finding that out here costs
   nothing.

4. **Lay the concept ladder.** problem → scope → user behaviour → system
   boundary → runtime behaviour → state rules → trade-offs → risk and proof.
   Each rung names the question the rung before it created. A technical view
   that answers no question the room already has is out of order, however good
   the diagram.

5. **Write the segment cards**, one per agenda row, fields per the format file.
   Each card's `Show` picks its visual from `NOTATIONS.md`, inside that
   notation's limit. `Decision needed` is filled here, by the author, with the
   source-backed choices that segment puts to the room — or `none`. It is not
   the outcome; the facilitator assigns that in the meeting.

6. **Arm the objection bank.** Mine the rejected ADR alternatives, the
   out-of-scope list, the open grill items, the risks the SDD names, and the
   verification the plan cannot yet reach. Each row gets a lane, a segment, an
   answer and a citation. An objection with no answer is listed as a known open
   item — the room finds it either way, and finding it in the plan is cheaper.

7. **Check the budget mechanically.** Run
   `python ${AFK_PLUGIN_ROOT}/scripts/validate_agenda.py {plan}` and fix what it
   names. Presenter minutes and objection minutes are separate columns because
   they are separate commitments — an overrun that eats an objection window is
   the failure this budget exists to prevent.

8. **Write `DESIGN-REVIEW-PLAN.md`** using [PLAN-TEMPLATE.md](PLAN-TEMPLATE.md).

9. **Rehearsal pass.** Read the plan as the presenter, in order. Every `Show`
   exists or is named for drawing; every `Answer` carries its citation; every
   agenda row has a card; every lane leaves with what section 1 promises it. Then
   confirm the exit block: an item classified `revise and return`,
   `deferred from scope` or `blocked by evidence` names an owner and a date.

10. **Update the ticket index.** Upsert the `Design review plan` row in the
    sibling `INDEX.md` per `skills/afk/to-prd/INDEX-FORMAT.md`.

**Done when:** the plan is on disk, the agenda check exits clean, every claim
has a ledger row, every agenda row has a card, and the `INDEX.md` row is
upserted.

## The undecided exit

A design review that cannot close a dispute is a normal meeting, not a failed
one. It ends on time, with every open item classified.

- Exactly one disposition per open item (`MEETING-PLAN-FORMAT.md`), assigned by
  the facilitator after the room discusses it.
- Everything except `agreed` names an owner and a target date.
- Any unresolved binding scope or design item keeps the SDD in **Draft** and
  schedules a second review. Say so in the room, in the words the template
  carries.
- The second review is convergence. Overrunning the first one to avoid it trades
  a scheduled hour for an unscheduled one.

## Hard rules

- **Strict synthesis.** Every claim traces to a ledger row. The plan creates no
  design that the SDD does not already carry, and re-derives nothing.
- **Writes its plan and its index row.** Nothing else. It never writes
  `GRILL-LOG.md`, the PRD, the SDD, an ADR, or the plan directory.
- **Meeting outcomes are not this skill's.** They reach the tracker through
  `/afk:to-ticket` meeting mode, from human-approved notes.
- **Room language.** No repository paths, class names, or workflow vocabulary in
  a `Say` line. Citations live in `Source`, where the presenter can reach them
  under challenge without reading them aloud.
- **Local artifact.** No tracker write, no merge request, no push.

## Render

Human present → render per `LAVISH.md` (RP-11, playbook `slides`), **authored
path**: the page is the live presentation surface and carries no per-item answer
control, so the page-writer child writes it under that file's Authoring
delegation. It is a view of the plan on disk and never a second source — the
markdown file stays the artifact. Markdown fallback, driven mode, and a user
opt-out per `LAVISH.md` present the file itself.

## Next

Send `DESIGN-BRIEF.md` as the pre-read. After the meeting, publish the summary
through `/afk:to-ticket` meeting mode, route each open item to the artifact
owner it names, and re-emit this plan before the next review — a meeting plan
goes stale silently.
