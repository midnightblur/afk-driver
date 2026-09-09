# Meeting-plan format

The one home for what any timed stakeholder meeting plan shares: **audience
lanes**, **agenda grammar**, **segment grammar**, **objection windows**, the
**outcome dispositions**, and the **time fallback**. Each producing skill points
here and states only what its own meeting needs.

This file owns structure. It owns no feature fact and no meeting outcome — a
plan carries the facts, the tracker's Meeting Summaries region carries what the
room decided.

> **Language:** read `LANGUAGE.md` (plugin root) before writing a plan — the
> room reads every word of it out loud.

## Audience lanes

A **lane** is one role plus the judgment that role makes. A plan states its
lanes once, and every segment names the lane that needs its detail. A segment
serving no lane is cut.

Lanes exist so the presenter knows who a sentence is for. Detail that only one
lane needs is said once, to that lane, and not repeated for the room.

## Agenda grammar

One table. One row per segment, in running order. Minute columns are
right-aligned integers.

**The company-meeting profile** is the fixed-hour shape: the agenda section
carries the line `Profile: company-meeting`, and its minute column totals
**exactly 60**. A total that is not 60 is a defect the plan does not ship with.
A plan budgeting to its own ceiling instead says so in its own words and stays
outside this profile.

In the company-meeting profile, check the arithmetic mechanically, never by
reading:

```
python ${AFK_PLUGIN_ROOT}/scripts/validate_agenda.py <plan.md>
```

The script's docstring owns the rules and the exit codes.

## Segment grammar

A **segment card** is the presenter's unit: one heading plus these fields, in
this order. A field with nothing to say is written `none`, never dropped — an
absent field reads as an oversight, and `none` reads as a decision.

| Field | Content |
|---|---|
| `Purpose` | the decision or the understanding this segment must produce |
| `Audience` | the lane that needs this detail |
| `Say` | the presenter's own words, short, in the room's language |
| `Show` | one visual or one live action |
| `Source` | the exact artifact section or decision record behind it |
| `Anticipated question` | the challenge this segment invites |
| `Answer` | the evidence-backed response, with its citation |
| `Objection window` | the minutes inside this segment held for challenge and response |
| `Decision needed` | the source-backed choices this segment puts to the room, or `none` |
| `Cut rule` | what this segment becomes in one sentence when time is short |

One visual per segment. A segment carrying two visuals is two segments or one
too many.

## Objection windows

An **objection window** is minutes reserved *inside* a segment, at its end, for
the room to challenge what it just saw. Objections land where their evidence is
still on screen — a question parked to the end is asked without the picture that
provoked it.

- The facilitator pauses each segment at its window. Presentation overrun never
  consumes one.
- **No single objection runs past 2 minutes.** At 2 minutes the facilitator
  records it as an open item and the segment continues on its remaining time.
- A plan may hold a trailing block for disputes that span segments. Only
  cross-cutting disputes and the exit check enter it.

## Two levels: what the plan asks, what the room answers

`Decision needed` and the dispositions below look like one field and are not.
Keeping them apart is what makes an unresolved meeting reportable.

| | `Decision needed` | Disposition |
|---|---|---|
| Who writes it | the plan author | the facilitator |
| When | before the meeting | after the room discusses the item |
| What it is | the choice this segment puts to the room | the single outcome that choice received |

**The dispositions**, exactly one per open item:

| Value | Meaning |
|---|---|
| `agreed` | the room settled it |
| `revise and return` | the owner changes the binding artifact and brings it back |
| `deferred from scope` | out of this feature, recorded so it is not re-litigated |
| `blocked by evidence` | undecidable until someone produces a named fact |

Every value except `agreed` names an owner and a target date. An item with no
owner is not classified.

## Time fallback

Each plan carries an ordered fallback list — what it sheds first, then next, to
land on time. It states which blocks are **protected**: presentation overrun
cannot take a protected block, whatever else is dropped.

Falling back demotes, it never deletes: a shed item becomes one sentence or one
reference and keeps its row. A row that disappears under time pressure is the
row nobody remembers was owed.
