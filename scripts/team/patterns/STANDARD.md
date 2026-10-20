# Pattern standard

Every team pattern that starts agents meets PS-1 to PS-4: a built-in record,
a saved pattern, and a one-off pattern an agent writes or proposes for one
task. The agent that writes or proposes a pattern applies the standard; no
program checks it, and the human's pick and review catch a miss. BP-1 solo
starts no agent, so the standard does not bind it.

| Id | Property | Test |
|---|---|---|
| PS-1 | Segregation of duty | The role that produces a piece of work never checks it |
| PS-2 | Independent cross-check and audit | At least 1 agent that did not produce a piece of work checks it, and each checker writes its first findings before it sees another checker's |
| PS-3 | Several angles on a problem | A problem that needs thinking gets at least 2 agents that differ in model or in brief |
| PS-4 | Maximum autonomy | The team runs to its end without the human, stops only at the stops its description names, and decides and records everything else |

A pattern's `description` says how and when the pattern is useful, names no
workflow stage, and says how the pattern meets each property. Its charter's
pattern part says the pattern's purpose and, again, how it meets each
property, so every agent the pattern starts reads it.

## Charter

A pattern with roles carries a charter: the pattern part (`charter`) and one
part per role (the role's `charter`). Neither is ever empty; the resolver
refuses a pattern with roles that lacks one, and checks only that each part
is there. A pattern with no roles carries none. A one-off pattern's charter
travels with the pattern, and the run's charter files are its only copy.

Each role part says:

- the role's responsibility, its deliverable, and what it must not do;
- whom it reports to and when, and whom it may message and why;
- how it is expected to behave;
- the milestones at which it sends progress;
- that it sends its report target progress as a message at each milestone,
  at once on a blocker or a question, and finished at the end;
- that a progress message opens with the line
  `progress: MILESTONE — SENTENCE`, where MILESTONE names the milestone and
  SENTENCE is one sentence;
- that a report target sends the roles that report to it only answers and
  data their current duty uses.

A charter part names no harness and no tool.

## Record shape

A record holds the fields of a saved pattern (`CONFIG.md`, the `patterns`
row); a built-in record is a JSON file in this folder with the same keys.
The resolver checks the values:

| Field | Value |
|---|---|
| `schema-version`, `record-version` | 1, the only known version; a one-off pattern carries no record version |
| role `model` | `<tier>@<provider>`: a tier row of `PROVIDERS.md` "Model tiers" in lower case, and a provider of `PROVIDERS.md` |
| role `lifespan` | `Turn`, `Step` or `Feature` |
| role `count` | 1 or more; one role, filled by that many agents |
| role `report-target` | a role of the same pattern, or empty for the agent that asked |
| role `hub` | `true` for at most 1 role; it moderates the pattern's debate steps |
| `edges` entry | `from` and `to`, roles of the same pattern, and `kinds`, a non-empty list of `message`, `finished`, `parked`, `exited`, `start-request` |
| `steps` entry | `name`, unique in the pattern; `roles`, the roles the step starts; `debate`, `true` for a debate step |
| `includes` | names of other patterns, combined by name |

A debate step whose pattern has no hub gets the moderator the resolver adds,
with the role part in `moderator.md`. Every role may message its report
target, and the report target the role, with no declared edge.
