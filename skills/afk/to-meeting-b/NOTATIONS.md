# Notations for a design review

The closed set. A visual in the plan uses one of these, inside its limit. Widen
the set only by editing this file — a notation nobody in the room reads costs a
segment and buys nothing.

| Notation | Use it for | Limit |
|---|---|---|
| [C4](https://c4model.com/diagrams) context or container view | the system shape segment | one view, one zoom level. Component detail only where it carries a decision the Team Lead must judge. Never mix levels in one picture |
| [Domain story](https://domainstorytelling.org/quick-start-guide) | the user journey, when the process crosses roles or systems | the business flow reaches the Product Owner and quality assurance before any technical diagram |
| [Story map](https://jpattonassociates.com/wp-content/uploads/2015/03/story_mapping.pdf) with a scope cut line | the ask-to-scope delta | one map. The cut line is what makes removed, added and deferred scope visible to all four lanes at once |
| Sequence diagram | runtime behaviour crossing systems | the main path, plus one failure path. Domain labels, never code names |
| State diagram | lifecycle | only when a legal transition changes product behaviour or test coverage |
| [ADR](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) cards | the decisions segment | **at most 3**, equal rows: constraint, choice, rejected option, consequence. The full record stays in its ADR and is linked |
| [arc42](https://arc42.org/overview/) | coverage checking while writing the plan | a checklist for the author. Its sections are never presented, and the SDD stays the source |
| [EventStorming](https://www.eventstorming.com/) | domain behaviour still disputed | belongs in a separate workshop, not here. A short event strip is fair when event order carries the design |
| [Wardley map](https://www.wardleymaps.com/faqs/what-is-wardley-mapping) | one disputed build, buy, or commodity-platform choice | not by default. It explains strategy, not runtime behaviour |

Render every diagram through `skills/utils/draw-charts`.

**The pre-read carries the prose.** Send `DESIGN-BRIEF.md` ahead of the meeting
and spend the hour on objections and decisions
([Google's practice guidance](https://google.github.io/styleguide/docguide/best_practices.html):
a design document collects feedback, then becomes an archive). Changes persist
in the PRD, the SDD, or an ADR — never in the meeting plan.
