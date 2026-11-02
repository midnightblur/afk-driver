# afkv2

Workflow vocabulary of the afkv2 plugin (AFK 2.0 beta): the words its skills, plans and pages use. Domain vocabulary of a consuming repository stays in that repository's own glossaries.

## Chain and lanes

**Chain**:
The fixed order of skills that takes a ticket to a merged change: grill, to-prd, propose-solution, to-subtasks, autopilot (with code-review), create-change-request, gc. Each skill reads what the previous one wrote and never assumes who ran before it.
`Related:` Lane, Chain smoke run

**Lane**:
The size class of a piece of work — small, medium or large — that decides which chain steps it runs. The beta ships only the medium lane; the rule that picks a lane arrives with the second lane.
`Related:` Chain

**Chain smoke run**:
One ticket taken through the whole chain to prove the chain works end to end. It passes when the ticket reaches a Draft change with green local tests, on every supported harness, with a human answering the grill and approving the plan.
`Related:` Chain, Change request

## Rules the agent carries

**Core behaviors**:
The always-loaded rule text, at most 8,000 characters, that the plugin's session-start hook adds to every session where afkv2 is enabled, on every supported harness. It never lives in the user instruction files; setup removes any v1 block from them, so a session carries one AFK rule set.
`Related:` Interim behaviors · `Avoid:` core block, behaviors block

**Interim behaviors**:
The temporary rule text in the user instruction files while v2 is being built, in place of the v1 block. It is removed when the afkv2 hook carries the core behaviors.
`Related:` Core behaviors, Friction switch · `Avoid:` interim block

**Friction switch**:
An environment variable or a file edit that turns off one v1 gate, for the v2 build only. Every switch is undone when the build ends.
`Related:` Interim behaviors

**Two-way door**:
A choice that can be undone on the branch at low cost: the agent decides it and records why. Its opposite, a one-way door, is hard to undo or reaches outside the branch, so the agent parks it for a human.
`Related:` Parked subtask · `Also:` one-way door

## Ownership

**Ownership grade**:
How freely the agent may change a piece of code: own (change freely), shared (minimal diff, tell the co-owners) or not owned (minimal diff, that code's own rules, the facts stated in the change). Code the repository config does not list counts as not owned.
`Related:` Good guest

**Good guest**:
How the agent works in code it does not own: a minimal diff, that code's own standards, the facts in the change, and no reference to our plan or ticket without a summary.
`Related:` Ownership grade

**Collaboration branch**:
An unprotected branch that several teams merge into. Its CI must stay passable, because a red CI there blocks every team on it.

## Runs and artifacts

**Run branch**:
An orphan branch per feature that holds the run files (the plan folder, journal, decision ledger, review telemetry). The spec folder (PRD, SDD, ADRs, grill log, page documents) is not a run file; it stays with the feature's change. gc keeps the run branch as the run's record.
`Related:` Chain

**Smart zone**:
The context size in which an agent still works well, about 300k tokens. A subtask must fit inside it; an oversized one is split.

**Parked subtask**:
A subtask autopilot stops on because it needs a human decision; its dependents stop with it. It counts as a grill or plan failure and is recorded for retro.
`Related:` Two-way door

**Change request**:
The forge's review unit — a merge request on GitLab, a pull request on GitHub. The agent opens it as Draft, marks it Ready at ship, and a human merges it.
`Also:` change · `Avoid:` MR, PR (when the text is forge-neutral)

## Grill and design

**Round 0**:
An optional first grill round in which the human writes their own reading of the ticket. The agent treats it as unverified input and checks it while agents read the code.

**Worked example**:
One use case — frequent, edge or risky — walked from its starting data to its result, with sample data when the feature makes data. Its picture fits the case: a flow chart for a user flow, a table for produced data, often more than one.

**Fork card**:
A card that shows the human a design choice the agent could not settle, with the options side by side. A lasting disagreement between two providers also becomes a fork card.

**Agent pane**:
A second agent session, of another provider or a higher model tier, that the agent starts and talks to — for a second design draft or an adversarial review.

## Pages

**Page engine**:
The plugin part that turns a page document into the page a human reads and answers. Agents never write page HTML; they write the page document.
`Related:` Page document, Freestyle component

**Page document**:
The JSON an agent writes for one grill or design session, round by round. It is kept in the feature's spec folder next to the PRD, so a past session can be opened again to read, audit or continue.
`Related:` Page engine

**Freestyle component**:
The one component that holds any HTML or SVG the agent writes, for what no other component covers. Each use is marked, so a repeated use can become a component.
`Related:` Page engine

**Map**:
A diagram that keeps the high-level view of a session's topic — a scope tree, a module structure, a simulated run — coloured by settled, open and current focus. A page has as many maps as its topic needs; there is no single big-picture map.
`Avoid:` big-picture map

**Steer**:
A human note on a map node or about the whole session, rather than on one card. The agent records it word for word and treats it as a standing rule for that node or that session until the session ends.

**Mark**:
A human's explicit answer on a card: accept, sign, an option, reopen, changes or a write-in. A clear, unambiguous note settles a point too; the agent states how it read the note, and a point with conflicting signals stays open.
`Related:` Steer

**Claim ledger**:
The list in the grill log of every load-bearing statement about how something works now, each with its status: pending, verified with a citation, refuted with a citation, or external and acknowledged by the human. Nothing settles on a pending claim.
`Related:` Exit gate

**Exit gate**:
The check that ends a grill: every claim verified or acknowledged, every term verified, the policy, staples, examples and devil's-advocate rows present, and no point left open in the current round.
`Related:` Claim ledger
