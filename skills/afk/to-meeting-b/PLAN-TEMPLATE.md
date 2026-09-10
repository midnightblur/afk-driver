# `DESIGN-REVIEW-PLAN.md` template

Nine sections, this order. Grammar for the shared parts — lanes, agenda,
segment cards, objection windows, dispositions, fallback — is
[MEETING-PLAN-FORMAT.md](MEETING-PLAN-FORMAT.md); this file adds only what the
design review itself fixes.

Read `LANGUAGE.md` (plugin root) before writing. Every line here is read aloud
to four roles, two of whom do not read code.

```markdown
# {TICKET-ID} — design review plan

Basis: {PRD.md, SDD.md draft of {date}, {n} requirement ADRs, {n} design ADRs}{, and the optional sources present}.
Pre-read sent: {DESIGN-BRIEF.md | none}.

## 1. Outcome and audience

**This meeting is done when:** {the decision the room must reach today, in one sentence}.

| Lane | Judges | Leaves with |
|---|---|---|
| Product Owner | scope and value | {what this role must be able to say afterwards} |
| Quality assurance | testability and reach | {…} |
| Development Director | cost, risk, and commitment | {…} |
| Team Lead | structure and maintenance | {…} |

## 2. Source ledger

Every claim in this plan traces to a row here. A claim with no row is cut.

| Claim | Source | Section or record |
|---|---|---|
| {the assertion the presenter makes} | {PRD.md \| SDD.md \| adr/…} | {§ or record id} |

## 3. Agenda

Profile: company-meeting

| Presenter min | Objection min | Total min | Segment | Purpose | Visual | Main source |
|---:|---:|---:|---|---|---|---|
| 4 | 1 | 5 | Outcome and problem | Align the room on the user problem and today's decision. | Problem-to-outcome strip | PRD problem and top user story |
| 5 | 3 | 8 | Ask-to-scope delta | Agree what is in, added, deferred, excluded. | Story map with a scope cut line | PRD stories, acceptance criteria, out of scope, requirement ADRs |
| 6 | 2 | 8 | User journey | Make the proposed behaviour concrete. | Prototype or domain story | Prototype, PRD, verification-plan journey |
| 6 | 2 | 8 | System shape | Show affected people, systems, deployable units. | C4 context or container view | SDD topology and boundaries |
| 7 | 3 | 10 | Runtime and lifecycle | Main path, one failure path, legal state changes. | Sequence diagram, then state diagram when needed | SDD process, failure, lifecycle |
| 5 | 4 | 9 | Decisions and trade-offs | Justify up to 3 disputed or costly choices. | Equal-row decision cards | ADRs, SDD decision tables |
| 4 | 2 | 6 | Risk, verification, rollout | Show how the main risks are contained. | Risk-to-proof table | SDD risks, verification plan |
| 0 | 6 | 6 | Cross-cutting disputes and exit | Resolve only objections spanning segments; classify every open item. | Open outcome table | Live notes |

37 presenter + 23 objection = 60. The trailing 6 are part of the 23.

## 4. Concept ladder

problem → scope → user behaviour → system boundary → runtime behaviour →
state rules → trade-offs → risk and proof.

| Concept | Prerequisite | The question the previous segment created |
|---|---|---|
| {concept} | {the concept it cannot be understood without} | {…} |

The presenter opens with none of: modules, patterns, code.

## 5. Segment cards

One card per agenda row, same order, fields per `MEETING-PLAN-FORMAT.md`.

### {n}. {Segment name} — {presenter} + {objection} min

- **Purpose:** {…}
- **Audience:** {lane}
- **Say:** {the presenter's words}
- **Show:** {one visual or one live action}
- **Source:** {artifact § or record}
- **Anticipated question:** {…}
- **Answer:** {evidence-backed, cited}
- **Objection window:** {n} min
- **Decision needed:** {the choice this segment puts to the room | none}
- **Cut rule:** {what this becomes in one sentence}

### 8. Cross-cutting disputes and exit — 0 + 6 min

- **Purpose:** resolve only objections spanning segments, then classify every open item before minute 60.
- **Audience:** all lanes.
- **Show:** the open outcome table below, filled live.
- **Decision needed:** none — this block records outcomes, it does not add questions.
- **Cut rule:** protected. Nothing takes these minutes.

| Open item | Disposition | Owner | Date |
|---|---|---|---|
| {carried from any segment} | agreed \| revise and return \| deferred from scope \| blocked by evidence | {who} | {when} |

Any unresolved binding scope or design item prevents approval. The presenter says:

> We have not agreed this item. {owner} will update {PRD, SDD, or ADR} or bring evidence by {date}. We will review it in the next design review. This design remains Draft.

## 6. Anticipated objections

The bank the presenter draws from. One row per challenge the sources invite.

| Objection | Lane likely to raise it | Segment it belongs to | Answer | Source |
|---|---|---|---|---|
| {…} | {…} | {segment} | {…} | {§ or record} |

An objection with no answer stays in the bank and is listed as a known open
item — never dropped because it is uncomfortable.

## 7. Time fallback

Protected: every objection window, and the trailing 6-minute block.

1. Keep problem, scope delta, user journey, system shape.
2. Show only the primary runtime path.
3. Convert secondary decisions to one-line ADR references.
4. Move lower risks to the source ledger.

## 8. Outcome capture route

The meeting summary is published into the tracker ticket's Meeting Summaries
region by `/afk:to-ticket` meeting mode, from human-approved notes. Nothing else
writes it, and nothing writes meeting outcomes into `GRILL-LOG.md`.

## 9. Follow-up routes

| Change the room asked for | Goes to | Owned artifact |
|---|---|---|
| requirement or scope | `/afk:to-prd` | `PRD.md`, requirement ADRs |
| design | `/afk:grill-solution`, then `/afk:to-sdd` | `SDD.md`, design ADRs |
| verification reach | `/afk:grill-verification` | `VERIFICATION-PLAN.md` |

The plan records none of these changes itself. Re-emit it before the next
review.
```

## Filling it

- Section 3's table ships as written. Change a minute only with a reason, and
  re-run the agenda check — the arithmetic is not the author's to eyeball.
- One card per agenda row. A row with no card is an unwritten segment.
- Every `Show` names a visual that exists or that the plan says to draw. Draw
  through `skills/utils/draw-charts`.
