# PRD — #178: the design page shows the whole design, like the grill page

## Problem Statement

The design skill (`/afkv2:propose-solution`) asks its questions layer by layer on a page. The requirements grill already gives the developer the whole picture every round. The design page does not:

- **Lost picture:** the developer sees one layer's questions at a time, so the whole design is never in view at once.
- **Hidden reasons:** a decision shows little of the requirement that drove it or the options it beat, so the developer cannot audit it.
- **Text-only design:** architecture, flows and logic are described in words, which is slow to read and easy to misread.
- **One voice:** one agent proposes the design alone, so a better design that another tool would find stays unseen.

## Solution

The design page gets the grill's experience. Agents do the work first, then show the developer a complete design, kept current every round:

- Living sections in design-level order, from the whole system down to key logic, each opening with its picture, the detail folded.
- A dedicated section for each critical part, with how it works now beside how it will work.
- Every decision explains itself: the requirements and constraints that drove it, the options it beat, and how to undo it.
- A design-patterns section that teaches each pattern and says why it works here, and one performance section for every performance fact.
- 2 solution proposers, Claude and Codex, draft in parallel in visible herdr panes; every difference between their drafts reaches the developer as a fork card.
- A herdr playbook skill, and setup that installs herdr after the developer's yes.
- The developer's notes and the agent's replies stack on top; the developer can reopen a finished design on the same page; questions only someone else can answer are tracked.
- The plan approval page shows an estimate of the agent run time.

## Catalog

The parts of a design page, in page order after the notes, the round's questions and the maps.

| Id | Part | Holds |
|----|------|-------|
| P-01 | Whole-system section | the system and its neighbours: boxes grouped by system, arrows labelled with what passes |
| P-02 | Critical-part section | 1 per critical part (a change to existing code, data or a flow, or an aspect only the developer may approve): a "critical" chip, now beside proposed; its level section links to it |
| P-03 | Level sections | 1 per design level, in level order; each opens with its picture (P-L table) and a 2-line summary, then folded detail, and links down to the next level |
| P-04 | Design-patterns section | per pattern: name, a short plain explanation of what it is, where it applies, why it works here, the quality goal it serves, the simpler option it beat, a folded class diagram; or 1 line "no pattern applied" |
| P-05 | Performance section | anticipated problems, large-data sizes, the built-in solution per problem, budgets per key flow; or 1 line why there is no performance risk |
| P-06 | Worked walk-throughs | at least 1 frequent, 1 edge and 1 risky key flow walked through the design with sample data |
| P-07 | Questions for others | design points only another person can answer, until answered, dropped with a reason, or assumed |

The picture per design level:

| Id | Level | Picture |
|----|-------|---------|
| P-L1 | The whole system and its neighbours | boxes grouped by system, arrows labelled with what passes |
| P-L2 | Boundaries and integration | a sequence diagram of the main request |
| P-L3 | Data | an entity diagram, or a field table for 3 entities or fewer |
| P-L4 | Domain model and states | a class diagram; a state diagram per item that moves through states |
| P-L5 | Process and coordination | a flowchart or a sequence diagram |
| P-L6 | Modules | boxes grouped by module, the touched parts chipped |
| P-L7 | Key logic | a flowchart or a decision table, and a short code block when the shape of the code is the point |
| P-L8 | Change impact | a now and proposed table per file, field or step |
| P-L9 | A critical part | how it works now beside how it will work |

The 5 blocks of a decision:

| Id | Block | Holds |
|----|-------|-------|
| D-1 | Decision | 1 sentence |
| D-2 | Driven by | the requirements, requirement records and constraints it serves, by name, each with its text on hover |
| D-3 | Other options | each in 1 line, with why it lost |
| D-4 | Why this one | the criterion that beat the runner-up |
| D-5 | To undo | what to revert |

The 4 parts of the performance section:

| Id | Part | Holds | Picture |
|----|------|-------|---------|
| PF-1 | Anticipated problems | each expected problem: hot paths, large data, unbounded lists, repeated queries, memory, waiting on others | a table: problem, where, cause, size |
| PF-2 | Large data | sizes of each growing table or list now, in 1 year and at worst, and the cost of each read or write | a size table |
| PF-3 | The solution | how the design meets each problem: paging, streaming, batching, indexes, caching, limits | the design picture of that part, the fix chipped |
| PF-4 | Budgets | a target per key flow (time, size or count), each marked measured, inferred or estimated | bars against the target |

The 5 steps that turn 2 drafts into 1 design:

| Id | Step | What happens |
|----|------|--------------|
| R-1 | Same inputs | both get the PRD, the requirement records, the claim ledger, the code reading, the settled critical aspects and the developer's steers; neither sees the other's draft |
| R-2 | Draft alone | each writes a whole design, every level |
| R-3 | Critique | each reads the other's draft and lists what it would change and why |
| R-4 | Reconcile | a part both critiques accept in writing becomes one design; every other difference becomes a fork card, each option credited to its tool |
| R-5 | Show | the banner says how many solution proposers ran, or why only 1 did |

The herdr playbook capabilities:

| Id | Capability |
|----|------------|
| H-1 | Workspaces, tabs and panes: what each is |
| H-2 | Open, close and rename a pane or tab |
| H-3 | Run commands in a terminal pane, not in an agent session |
| H-4 | Start Claude with `--dangerously-skip-permissions` and Codex with `--yolo`, always |
| H-5 | Send text to another pane, and read its output |
| H-6 | Check that a sent prompt was submitted and the agent is working |
| H-7 | Wait for an agent to finish without a polling loop |
| H-8 | Close each pane the agent opened once its result is read |
| H-9 | Detect a session outside herdr, and fall back |

## User Stories

1. As the developer, I want to see the whole design every round, from the system down to key logic, kept current, so that I never lose the picture.
2. As the developer, I want each decision to show the requirements that drove it and the options it beat, so that I can audit it.
3. As the developer, I want designs from both Claude and Codex, and to pick where they still disagree, so that a better design is not missed.
4. As the developer, I want to see which design patterns apply where and why, and how the design anticipates and solves its performance problems, so that I can judge its quality without knowing every pattern.
5. As the developer, I want the plan page to show how many days the agents would need to build the plan, per subtask and in total, so that I know the cost before I approve.
6. As the developer, I want to reopen a finished design with new input on the same page, so that a changed requirement does not start the design over.

## Acceptance Criteria

### The page

- [ ] AC-001 Every round of a design session shows every current section with its current text → no current section is folded into the settled points or left out.
- [ ] AC-002 A section changed in a round → it shows exactly 1 new change line for that round with its cause; an unchanged section shows no new line.
- [ ] AC-003 The sections of a design page follow the page order of the Catalog: P-01, then each P-02, then the P-03 level sections in level order, then P-04, P-05, P-06 and P-07.
- [ ] AC-004 Each P-03 level section opens with the picture its level names in table P-L and a summary of at most 2 lines; the rest of its detail is folded.
- [ ] AC-005 Each P-03 level section above the last links to the section of the next level.
- [ ] AC-006 Each critical part has its own P-02 section with a "critical" chip and a P-L9 picture; its level section links to it.
- [ ] AC-007 The developer's notes and the agent's replies show above the round's questions and the sections, newest round first.
- [ ] AC-008 Every picture on the page has a 1-line caption that says what to see.

### Decisions

- [ ] AC-009 Every decision on the page, decided or forked, shows the 5 blocks D-1 to D-5; a decision with a block missing does not show as decided.
- [ ] AC-010 Every requirement or requirement record named in a D-2 block shows its text on hover.
- [ ] AC-011 Every design record the design writes holds the same 5 blocks as its decision on the page.

### Patterns and performance

- [ ] AC-012 A design that applies a design pattern shows it in P-04 with every field P-04 names; a design with none shows the line "no pattern applied" there.
- [ ] AC-013 Every design has 1 P-05 performance section with PF-1 to PF-4, each with its picture; a design with no performance risk shows 1 line in P-05 that says why.
- [ ] AC-014 Every performance fact of a design stands only in P-05; design level 4 and the large-data aspect point to P-05 and do not repeat it.
- [ ] AC-015 Every PF-4 budget is marked measured, inferred or estimated.
- [ ] AC-016 A design page holds no new security section; the authorization design and its sign-off stay as they are.

### Solution proposers

- [ ] AC-017 With Claude and Codex both available and the session inside herdr → 2 solution proposers draft, 1 per tool, by the steps R-1 to R-5.
- [ ] AC-018 The solution proposers draft once, after every critical aspect is settled and before the first draft round; no draft starts before that.
- [ ] AC-019 The other tool's solution proposer runs in a visible herdr pane that the developer can watch.
- [ ] AC-020 Each solution proposer starts with full auto-approval (H-4), in its own throwaway worktree; only its draft file and its critique are read back, then its worktree is removed.
- [ ] AC-021 The page states that the throwaway worktree fences only the working folder and is not a sandbox.
- [ ] AC-022 Every point where the 2 drafts differ shows as a fork card with each option credited to its tool, unless both critiques state agreement on that point in writing.
- [ ] AC-023 The agent in charge does not decide a point the 2 drafts dispute; the point stays open until the developer picks.
- [ ] AC-024 The other tool missing, herdr missing, the session outside herdr, or full auto-approval forbidden → 1 solution proposer drafts alone, and the banner names the reason.
- [ ] AC-025 A design session never starts 2 or more solution proposers of the same tool, in any case.
- [ ] AC-026 After the solution proposers return, the agent in charge closes every pane it opened.

### herdr

- [ ] AC-027 The herdr playbook skill covers each capability H-1 to H-9, each checked against the official herdr documentation.
- [ ] AC-028 Setup finds herdr missing → it asks the developer once; a yes installs herdr through its official installer or a package manager; a no installs nothing and leaves design sessions with 1 solution proposer.
- [ ] AC-029 Setup never installs herdr by copying a program file into a temporary folder.
- [ ] AC-030 Setup finds herdr present → it installs nothing and asks nothing about herdr.

### Coming back and questions for others

- [ ] AC-031 A design session that passed its check, run again with new input → it continues the same page; a point the input touches returns as a new card that carries the old card; every other settled point stays settled.
- [ ] AC-032 Every pass of the design check lists the later documents that may be out of date and the settled points that changed since the last passed check; each list is empty when nothing applies.
- [ ] AC-033 An older design page with no sections, reopened → its sections are built once from its settled points, each with a change line that says so.
- [ ] AC-034 The developer's notes of each round are copied word for word into the design log.
- [ ] AC-035 A design point neither the developer nor the code can settle is tracked as a question for others; the design check refuses to pass while one is open.
- [ ] AC-036 The design page's first round shows the ticket card with the ticket text and its links.
- [ ] AC-037 A side question sent from the page during a design round gets its answer on the page, and the round stays open.

### The estimate

- [ ] AC-038 The plan approval page shows the agent run time per subtask and in total, each as a low, likely and high value in days.
- [ ] AC-039 With earlier run times in the repository's run journals → the estimate is scaled from them, and the page names how many earlier runs it used.
- [ ] AC-040 With no earlier run time → the estimate is judged from each subtask's size, marked estimated, and the page says that no earlier run exists.
- [ ] AC-041 No estimate is written to the tracker or to any ticket field.
- [ ] AC-042 The design page shows no estimate.

## Worked examples

### WE-01 — frequent: a new feature, both tools installed

| Input | Value |
|-------|-------|
| PRD | 12 requirements, 3 requirement records, 1 of them a performance goal |
| Tools | Claude runs the session in herdr; Codex is installed |

1. The developer settles the critical aspects.
2. Claude opens a herdr pane and starts Codex there in a throwaway worktree. Both draft alone.
3. Each critiques the other's draft; both agree in writing on 9 of 11 design parts.
4. The page shows the sections in level order, each with its picture; P-04 lists a strategy for 2 export formats, for changeability, with what a strategy is; P-05 shows an export of 200,000 orders streamed in pages of 1,000; 2 fork cards read "Claude proposes A, Codex proposes B". Claude closes the Codex pane.
5. The developer picks on both forks and signs the aspects only they may approve.

| Result | Value |
|--------|-------|
| Design document and records | written |
| Plan page, later | 2 to 4 days of agent run time, most likely 3, from 4 earlier runs |

### WE-02 — edge: Codex is not installed

| Input | Result |
|-------|--------|
| The same PRD; only Claude is installed | The banner says: 1 solution proposer, because Codex was not found. Claude drafts alone; no critique step; no card credits a tool. |

### WE-03 — risky: the tools disagree on a change that cannot be undone

| Input | Result |
|-------|--------|
| Claude proposes a new table for saved exports; Codex proposes a column on the orders table | The critique does not reconcile them. A fork card shows both, each credited to its tool, each with the requirements it serves and its cost. The point is critical, so its P-02 section shows the current orders table beside each option. Nothing settles until the developer picks. |

### WE-04 — edge: the PRD changes after the design passed

| Input | Result |
|-------|--------|
| A design that passed its check; the PRD gains 1 requirement | The design session continues the same page; the 2 sections the change touches return as new cards; the other 9 stay settled; the check passes again and lists the plan as possibly out of date. |

### WE-05 — edge: a repository with no earlier runs

| Input | Result |
|-------|--------|
| A plan of 6 subtasks; the run journals hold no run | The plan page shows the range judged from each subtask's size, marked estimated, and says that no earlier run exists. |

## Access & validation policy

| Capability | Permitted | Denied | Data scope | Validation |
|------------|-----------|--------|------------|------------|
| Read, note, pick forks, sign off, reopen a design | the developer | solution proposers, outside people | unscoped | only a sign mark signs off; only the developer picks a disputed fork |
| Draft and critique a design | a solution proposer | — (the developer may not be replaced by it on any card) | its own draft and the other draft only | each draft covers every design level; it may not open a page, read the developer's notes, or write the design document or the tracker |
| Merge drafts, decide reversible points, write the page and documents | the agent in charge | solution proposers | the session | may not sign off, decide a disputed fork, or write the tracker |
| Answer a question for others | an outside person, through the developer | — (outside people do not see the page by default) | the question's context only | an answer settles no card; the developer confirms each point it touches |

## Implementation Decisions

- The design skill sends the page's sections, stories, walk-throughs and questions; the shared page engine and page skill already hold the mechanics. The engine changes only where a criterion cannot be met today.
- Detail by level uses ordered sections and folds, not nested sections.
- Claude and Codex as the 2 solution proposers, with no same-tool fallback: [ADR-0001](adr/requirements/0001-two-tools-no-same-tool-fallback.md).
- Full auto-approval always, fenced only by a throwaway worktree: [ADR-0002](adr/requirements/0002-full-auto-approval-in-throwaway-worktree.md).
- The estimate is agent run time on the plan page, from journal times: [ADR-0003](adr/requirements/0003-estimate-on-the-plan-page.md).
- The herdr playbook and the herdr install are part of this ticket.
- The plan skill (`/afkv2:to-subtasks`) gains the estimate on its approval page.

## Testing Decisions

- A good test drives the design round builder with a round input and checks the page document: section order, the change line per changed section, the decision blocks, the P-04 and P-05 shapes.
- The design check gets tests for the stale and changed lists, the take-over of a passed session, and the refusal on an open question for others, after the grill check's tests (prior art: the grill's version 2 tests).
- The solution-proposer flow is tested with an in-process fake of herdr and of each tool; the fallback cases of AC-024 each get a test.
- The setup install of herdr is tested with a fake installer: the yes, the no, and herdr present.
- The estimate is tested with fake journals: several runs, no run.
- A live check on a real page confirms the pictures and the layout in a browser, after the styling fix ships.

## Out of Scope

- A security section in the design (deferred by the developer; recorded as follow-up work).
- A time cap or hang handling for a solution proposer (dealt with later if it becomes a real problem).
- Styling of the newest page format's parts (sections, change lines, questions for others, walk-throughs): a separate fix on the afkv2 branch, done first.
- Nested sections, and a new page format.
- Changes to the requirements grill.
- Any tracker write of the estimate.
- The rename of the grill skill (#177, merged).

## Further Notes

- The design skill already holds an empty slot for a second design provider, switched off; this ticket replaces it.
- The design skill asks every critical-aspect question before any draft card; the solution proposers start after that, by AC-018.
- The run journals of the autopilot stamp every event with a date and minute; the estimate reads those times. Whether the cleanup after a merge deletes those journals is not verified; the design must check it.
- This ticket's page criteria rest on the styling fix, which ships first.
- An earlier design on this repository recorded a policy risk in one tool driving another under a subscription login; it was not checked again for this ticket.
