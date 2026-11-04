# PRD — #163 use-lavish: how an agent writes a page and answers the human's notes

## Problem Statement

- **Pages are hard to follow.** Pages that afkv2 skills write are harder to follow than the owner's hand-made review page. The component guide (`visualize`) says how each part looks. No skill says how to order a page, how to word its headings, or what to put first.
- **Answers depend on luck.** The session that wrote the hand-made page had no skill, and it answered every owner note well. Nothing makes the next session do the same.
- **A page is tied to an afk step.** Only 3 afk skills can write a page, and every page must sit in a ticket's spec folder. An agent cannot show a human a page outside those steps, and the human cannot ask for one.

## Solution

A new afkv2 skill, **use-lavish**, tells an agent how to organize a page, write its content and answer the human's notes. It loads `visualize` for the components. Any agent may load it, in an afk step or ad hoc, and the human starts an ad-hoc page with `/afkv2:use-lavish` and a topic.

The skill holds 4 sets of instructions (Catalog): the page rules (PR), the answer rules (AR), the suggested form for each kind of information (K, with refinements RF), and when to pick a page over chat.

The page engine gains the abilities in table EG, in a new version of the page format. The owner's ruling binds the split: instructions carry the quality bar; engine code adds abilities, and deterministic logic only warns about an outcome that cannot be undone. Nothing blocks a round ([ADR-0001](adr/requirements/0001-instructions-first-warn-never-block.md)).

## Catalog

### Page rules (PR)

| Id | Rule |
|---|---|
| PR-01 | A heading states the conclusion, with a number. |
| PR-02 | A card opens with the verdict, then the evidence, then the detail, then risks and pushback. |
| PR-03 | Put first what the human needs first: what changed and where the asks are, then the overview, then the detail. Open questions first, each with a recommendation. |
| PR-04 | Show the whole topic as a map, and tie each card to its node. |
| PR-05 | Pick the form by the kind of fact (table K). |
| PR-06 | Say how each number is known: measured, inferred or estimated, and from where. |
| PR-07 | Never use colour alone: each colour comes with a word or a symbol. |
| PR-08 | Mark the steps where the human must act. |
| PR-09 | Fold secondary detail and old history. Replace a stale fact; do not leave the struck old fact beside it. |
| PR-10 | Plain words: short active sentences, digits, "you" and "I". No id codes in the prose. Explain each term at its first use on a card. |
| PR-11 | Keep every card id stable, so the human's marks and notes survive a rewrite. |
| PR-12 | Avoid: round badges stacked in one heading; trace codes in prose; new cards that push the main section down. The same tooltip on every repeat of a term is allowed. |
| PR-13 | Every diagram has a 1-line caption that says what to see. |
| PR-14 | A scope map groups its parts by module or area and draws no flow arrows; an arrow only where one part must settle before another. |

### Answer rules (AR)

| Id | Rule |
|---|---|
| AR-01 | Open with the outcome: Done, Agreed, Recorded, Kept, Deferred, Counter, No. |
| AR-02 | Say what changed and where, 1 sentence per change. |
| AR-03 | Push back plainly on disagreement: name the cost and the timing, and give a counter-proposal. |
| AR-04 | A pushback that needs the human's call becomes a new question card, with a recommendation. |
| AR-05 | A note with several points gets one answer per point, in the same row. |
| AR-06 | An answer that changes nothing says why: kept, deferred, already done. |
| AR-07 | Mark a guess as "(inferred)". Say so when the note could not be read in full. |
| AR-08 | Update every point the change touches, not only the noted card: each gets a new card that carries the old one. |
| AR-09 | Never repeat the human's note in the answer, steers included: the row already shows the note, and the skill's log keeps the exact words. |
| AR-10 | Each note gets its own row. When one answer covers several notes, the answer repeats in each of their rows; no row groups notes ([ADR-0004](adr/requirements/0004-one-note-one-row.md)). |

### Engine abilities (EG)

| Id | Ability |
|---|---|
| EG-01 | An answer row links to each element the answer changed: a card, a table, a map node. |
| EG-02 | Ad-hoc pages: a page written by use-lavish, with or without a ticket, at the home rule of [ADR-0002](adr/requirements/0002-ad-hoc-page-home.md). |
| EG-03 | A click on a map box opens its card; hovering a box shows its state and the round of its last change. |
| EG-04 | The round banner gets a fourth list: each card or table changed since the last round, with a link. |
| EG-05 | Chip tones for state (open, blocked, settled) and for how a fact is known (measured, inferred, estimated, unverified). |
| EG-06 | Each message of a sequence diagram can be marked removed, kept or new. |
| EG-07 | A "YOU" mark on a box, a step or a message where the human acts. |
| EG-08 | Any element carries its own tooltip, so a mention of a session item (a decision number, a card) shows what it means. A top item of this ticket, taken from the durable-tooltips work of #153. |
| EG-09 | Text that names another card links to it. After any jump inside the page (card link, map box, answer link), one click returns to where the human was. |
| EG-10 | A row, or any part of a card, that changed this round shows a round mark at its edge. |
| EG-11 | The page shows its git state ([ADR-0003](adr/requirements/0003-secret-and-tracking-warnings.md)). |
| EG-12 | A secret warning ([ADR-0003](adr/requirements/0003-secret-and-tracking-warnings.md)). |
| EG-13 | One diagram-text component (Mermaid) draws the kinds marked "diagram text" in table K. |
| EG-14 | Value chips: a colour per value of a named set of fixed values. |
| EG-15 | Code blocks and diffs, coloured by a popular, proven highlighter library; afkv2 builds no highlighter. |
| EG-16 | The notes table shows the noted text in its own column, Noted text. |
| EG-17 | One session notes table shows every note and answer of the session, card notes included. |
| EG-18 | Each note the human sends is its own note, with its own id and row, also when several sit on one element. |
| EG-19 | A stable page title and tab name: `<ticket> · <short title> · <step>`. |
| EG-20 | A new round reuses the open browser tab. |
| EG-21 | The banner's lists sit side by side. |
| EG-22 | The page navigation stays out of the content. |
| EG-23 | A scope map lays its groups side by side across the page width. |
| EG-24 | A component for each form marked "new component" in table K. |

### Kinds of information and their suggested forms (K)

A suggestion: an agent may pick another form when it fits the content better, and says why in one line. "Built by" names how the form is drawn: an existing component, a new component (EG-24), diagram text (EG-13) or a code block (EG-15). Every chart and diagram follows PR-07 and PR-13.

| Id | Kind: when | Suggested form | Why | Built by |
|---|---|---|---|---|
| K-01 | One key number: a count, a size, a duration, a cost, an estimate with a range | A tile: the number large, a short label, how it is known with its source | The eye finds the number first; the grade sits beside it | new component |
| K-02 | Sizes or counts compared across items | Horizontal bars, sorted largest first, value at the end; a share of a whole is one split bar, not a pie | Length compares faster than digits | new component |
| K-03 | A number over days, runs or versions | A line chart with dated points, the latest value labelled, a target line when one exists | A trend shows only as a shape | new component |
| K-04 | A step, field, rule or file changes | One row per element, Now and Proposed columns, a kept, removed or new chip per Proposed cell | The change shows per row | existing |
| K-05 | A pick among 2 or more ways | One column per option, the same rows for each (cost, risk, what it blocks), the recommendation with 1 reason above | Same rows make the trade-off direct | existing |
| K-06 | Modules, files, services or skills and the calls between them | Boxes grouped by module, arrows labelled with what passes, chips on the touched parts | A structure has no order; a list misleads | existing |
| K-07 | Requests, hand-offs or retries between people and systems | A sequence diagram, now and proposed in one, a tone per message (EG-06) | Order and direction are the point | existing + EG-06 |
| K-08 | A run, pipeline or workflow, step by step | Steps left to right, today's lane above the proposed lane, a YOU mark (EG-07) | The whole run at once, and where the human acts | existing + EG-07 |
| K-09 | Many parts of one topic, each with a state | A scope map (PR-14) with a state legend; a box opens its card (EG-03) | The whole stays in view | existing + EG-03, EG-23 |
| K-10 | Records with the same fields | A table, most telling column first, long cells folded; a column of fixed values as value chips (EG-14) | Equal fields line up | existing + EG-14 |
| K-11 | The state of many items | A status table, one state chip per row (EG-05), rows that need the human first | What needs the human, without reading each row | existing + EG-05 |
| K-12 | Coverage of one list by another | A matrix, each cell a chip with a word (covered, partial, missing) as value chips | Gaps stand out as a pattern | existing + EG-14 |
| K-13 | A plan over days or milestones | One row per slot: When, Who, What; actors as value chips, rows where the human acts marked YOU | Time reads down the page | existing + EG-14 |
| K-14 | A claim rests on a code line, document passage or log line | A block labelled "Source", path and line or a link, at most 1 short excerpt | The claim can be checked in 1 step | existing |
| K-15 | A sentence, rule or clause changes words | The text inline, removed words struck, new words marked | The new text reads in place | existing |
| K-16 | What can go wrong, or disagreement | Risks: risk, chance, impact, mitigation; pushback: idea, concern, counter-proposal, the human's call; chance and impact as value chips | Each concern gets the same fields | existing + EG-14 |
| K-17 | An item moves through states | A state diagram: each state once, each legal move a labelled arrow | Shows which moves are legal | diagram text |
| K-18 | Entities, keys and relations | An entity diagram with cardinality and key marks; with 3 entities or fewer, a field table per entity | Cardinality is often the decision | diagram text |
| K-19 | An interface and its implementations | A class diagram: the interface on top, implementations below, only the methods that matter | The shape of a seam in one look | diagram text |
| K-20 | A rule or run takes different paths | A flowchart: diamonds for choices, each exit labelled | A run strip has no branches | diagram text |
| K-21 | Hosts, machines, containers and their links | Nested boxes, arrows for traffic, a key for any symbol | Nesting is the point | diagram text |
| K-22 | Steps that wait for one another | A Gantt-style timeline: bars, dependencies, milestones | Shows overlap and what blocks what | diagram text |
| K-23 | Options placed by 2 measures | A quadrant chart: options as points, each quarter named | Positions are not cells | diagram text |
| K-24 | Pseudo or real code | A code block: fixed-width font, colour by language, line numbers, a path:line header | Code in prose loses its structure | code block |
| K-25 | A change to code or config, line by line | A unified diff: removed lines red with -, added lines green with +, a header per hunk | Each changed line in its context | code block |
| K-26 | An endpoint, message or command line | A header with method and path, request and response as code blocks, a status table | An example reads faster than a definition | code block |
| K-27 | A configuration file or set of options | The snippet as a code block, then a key, default, meaning table | The snippet shows the shape; the table each key | code block |
| K-28 | A decision others will read later | Fixed blocks: context, drivers, options, outcome, consequences, status | A reader jumps to the part they need | existing |
| K-29 | A decision amended, reversed or replaced | The current text in full, a status chip, a trail below: each change with date and reason, newest first | No merging of original and change in the head | existing |
| K-30 | retired: goals and non-goals; the agent picks a form (owner, round 5) | — | — | — |
| K-31 | retired: open questions; the agent picks a form (owner, round 5) | — | — | — |
| K-32 | retired: quality requirements; the agent picks a form (owner, round 5) | — | — | — |
| K-33 | Work a review, incident or decision leaves behind | An action table: action, type, owner, tracking link, state chip | Each action has an owner and a place | existing |
| K-34 | Past events | A list in time order, each line with its time, key moments in bold | Past events read as a story | existing |
| K-35 | One measure with a goal and good or poor bands | A bullet graph: a bar for the value, a tick for the target, bands behind | Value, goal and distance in one line | new component |
| K-36 | Request times, sizes or durations, where an average hides the tail | One spread: a histogram; several spreads: box plots on a shared scale | The shape shows the tail | diagram text (histogram), new component (box plot) |
| K-37 | Estimates of time, cost or size, often several | One bar per item on a shared scale, low to high, a dot at the likely value, numbers at the end, 1 line on what the range means | A single number reads as more exact than it is | new component |
| K-38 | Faster or slower than before, over or under budget | Bars left and right of a zero line, the sign in the label | The direction is the message | new component |
| K-39 | A rule with several conditions and outcomes | A decision table: condition columns, outcome columns, one row per case | A missing case shows | existing |
| K-40 | Codes, states or enum values | A value, meaning table | One look answers what a value means | existing |
| K-41 | An earlier statement turned out false | A claimed, true, source table | The correction is visible | existing |
| K-42 | A record cites a human's call | A quote block: the words, who, when; on a page that answers notes, the notes row shows the words, so the answer does not repeat them | A ruling in its own words cannot be misread | existing |
| K-43 | retired: always-or-never guarantees; the agent picks a form (owner, round 5) | — | — | — |
| K-44 | Acceptance, readiness or a ship gate | One line per check with a state chip | What blocks, at a glance | existing |
| K-45 | Questions a reader will likely ask | One folded line per question; the answer opens on a click | The reader opens only what they wonder about | existing |
| K-46 | Words a reader may not know | A term, definition table; each term shows its definition on hover | The word is learned where it is met | existing |
| K-47 | Where a slow run spends its time | A flame graph: each box a function, width its share of time, callers below callees | The widest boxes are where to look | new component |
| K-48 | Several measures over time, side by side | Sparklines: a tiny line per table row, the latest value beside it | Many trends in little space | new component |
| K-49 | One request crosses several services and is slow | A span waterfall: one bar per step on a shared time axis, the slowest path strong | Where the time goes, what runs in parallel | new component |
| K-50 | How a quantity splits and flows | A Sankey diagram: bands as wide as their volume | Losses and splits show as widths | diagram text |
| K-51 | Why something fails or is slow | Causes grouped by area around the problem; a mind map is the nearest drawable form | No cause is forgotten | diagram text |
| K-52 | Sizes of nested parts | A treemap: nested rectangles sized by value | Big parts and their parents in one view | diagram text |
| K-53 | How branches split and merged | A git graph: one line per branch, dots for commits, curves for merges | Merge order at once | diagram text |

### Refinements (RF)

Sub-forms; they do not replace the forms in table K.

| Id | For | Refinement |
|---|---|---|
| RF-01 | K-01 | Against a target, use K-35. |
| RF-02 | K-02 | Under 20 items with exact values: a table; signed differences: K-38; avoid stacked bars with many parts. |
| RF-03 | K-03 | 2 or 3 points: a slope chart; many lines: small charts side by side. |
| RF-04 | K-04 | For numbers: paired bars or a slope chart; the table stays for structure. |
| RF-05 | K-05 | Add the drivers, the consequences and a rejected-because column apart from the cons. |
| RF-06 | K-06 | One view per zoom level, and a key for any symbol. |
| RF-07 | K-12 | Numbers inside the cells; continuous positions go to K-23. |
| RF-08 | K-13 | When order or overlap matters, K-22. |
| RF-09 | K-16 | Order by priority, one mitigation per risk. |

## User Stories

1. As a human reviewing an afk step, I want every page to follow the page rules, so that I find the asks first and follow the whole topic.
2. As a human writing notes on a page, I want each note answered in its own row with a link to what changed, so that I can check every answer in one click and come back.
3. As an agent that needs a human's pick of options, a picture or 3 or more answers, I want to open an ad-hoc page by my own call, so that the human reads it in place of a long chat message.
4. As a human, I want to type `/afkv2:use-lavish` with a topic, so that the agent shows the topic on a page and answers my notes round by round until I end the session.
5. As a human, I want an ad-hoc page to find its home and tell me whether git tracks it, so that I know what gets committed and can ask for it to be tracked.
6. As a human, I want a warning when a page or its log in the repository holds a secret, so that I can remove it before a commit.

## Acceptance Criteria

Skill:

- [ ] AC-001 The plugin ships a skill named use-lavish → `/afkv2:use-lavish <topic>` opens an ad-hoc page on that topic.
- [ ] AC-002 `/afkv2:use-lavish` with no topic → the agent asks for a topic in chat and opens no page.
- [ ] AC-003 Each page-writing afk skill (grill, propose-solution, propose-verification) points to use-lavish for page order, wording and answers → its pages follow PR-01 to PR-14.
- [ ] AC-004 Each skill that reads the human's notes, to-subtasks included, points to use-lavish for answers → its answers follow AR-01 to AR-10.
- [ ] AC-005 use-lavish holds tables PR, AR, K and RF; `visualize` holds only how each component holds, looks and is used → no page-order rule and no note-answering rule stands in `visualize`.
- [ ] AC-006 An agent that picks a form other than the one table K suggests → its page states why in one line.
- [ ] AC-007 Table K in use-lavish holds no row for K-30, K-31, K-32 or K-43 → for those kinds the agent picks a form.
- [ ] AC-008 Content with options side by side, a picture, or 3 or more questions → the agent offers a page; a one-line question → the agent asks in chat.
- [ ] AC-009 A hands-off subagent, such as an autopilot executor, meets a question for the human → it opens no page and parks the question.

Notes and answers:

- [ ] AC-010 The human sends 3 notes on one element → the notes table shows 3 rows, each with its own note id.
- [ ] AC-011 A round with notes → every note has an answer before the next round shows.
- [ ] AC-012 One answer covers 2 notes → the answer stands in both rows; no row holds 2 notes.
- [ ] AC-013 An answer that changed elements → its row gives one click to each changed card, table or map node.
- [ ] AC-014 An answer that changed nothing → its row has no change link and says why: kept, deferred or already done.
- [ ] AC-015 The human jumps inside the page by an answer link, a card link or a map box → one click returns to the place before the jump.
- [ ] AC-016 A note on a selection → the Noted text column shows the selected text, and the Your note column shows only the human's words.
- [ ] AC-017 Any answer → it holds no copy of the note's words.
- [ ] AC-018 The session notes table → it lists every note and answer of the session, card notes included, newest round first, each row linked to the card or element it is on.
- [ ] AC-019 The session notes table on round 3 or later → the current and the previous round show open; each older round is a closed group with its own count line that opens with one click; each card still shows its own notes under it.

Page abilities:

- [ ] AC-020 A click on a map box → the page scrolls to its card; hovering the box shows its state and the round of its last change.
- [ ] AC-021 A round after round 1 → the banner lists each card or table changed since the last round, each with a link.
- [ ] AC-022 A chip with a state or certainty tone (open, blocked, settled, measured, inferred, estimated, unverified) → it shows its word and its own look in light and dark themes.
- [ ] AC-023 A sequence message marked removed, kept or new → it shows that mark.
- [ ] AC-024 A box, step or message marked as a human act → it shows a YOU mark.
- [ ] AC-025 An element with its own tooltip text → hovering it shows that text; the same tooltip may show on every mention.
- [ ] AC-026 Text that names another card on the page → it links to that card.
- [ ] AC-027 A row or part of a card changed this round → it shows a round mark at its edge; an unchanged row shows none.
- [ ] AC-028 A column of a named set of fixed values → each value shows as a chip with its word and its colour; the same value has the same colour on the whole page; ordered values run strong to faint; YOU always has the same strong colour.
- [ ] AC-029 A code block → it shows a fixed-width font, colour by its language, line numbers and a path:line header.
- [ ] AC-030 A diff → removed lines show red with -, added lines green with +, with a file and line header per hunk.
- [ ] AC-031 Diagram text of a kind marked "diagram text" in table K → the page shows it as a picture.
- [ ] AC-032 A round whose diagram text did not change since the last render → that diagram is not rendered again.
- [ ] AC-033 The diagram renderer is missing or fails → the diagram shows as its text in a code block with one line that says why, and the page still renders.
- [ ] AC-034 Each form marked "new component" in table K → a page document can draw it with that component, with no freestyle drawing.
- [ ] AC-035 Any page → the heading and the browser tab read `<ticket> · <short title> · <step>`, with a short title of at most 40 characters that stays the same every round; an ad-hoc page shows its topic in place of the step.
- [ ] AC-036 A new round with the page open in a tab → that tab shows the new round, and no second tab opens (unverified premise: the page host can reuse an open tab).
- [ ] AC-037 A new round with the page open and a host that cannot reuse a tab → the open page reloads itself when the round is ready.
- [ ] AC-038 A window wide enough for 3 columns → the banner lists sit side by side; a narrower window → they stack.
- [ ] AC-039 A wide window → the page navigation sits in the left margin and never covers content; a narrow window → it is one small button whose list opens on a click and closes after a jump.
- [ ] AC-040 The human collapses the navigation → it stays collapsed on the next round.
- [ ] AC-041 A scope map on a wide window → its groups sit side by side across the page width; a narrow window → they stack.
- [ ] AC-042 A page document written before this ticket → the engine opens and renders it, and does not rewrite it.

Home, tracking and secrets:

- [ ] AC-043 An ad-hoc page with a ticket, and content the repository's readers may see → it lives in the ticket's spec folder and is committed.
- [ ] AC-044 An ad-hoc page with no ticket → it lives outside the repository and is not committed.
- [ ] AC-045 An ad-hoc page whose content the repository's readers may not see → it lives outside the repository, also with a ticket.
- [ ] AC-046 Each show → the page header shows one of 4 git-state lines: committed; in the repository but not committed yet; ignored by git; outside the repository.
- [ ] AC-047 The agent opens a page that git does not track → it also says so in chat.
- [ ] AC-048 The human asks to track an untracked page → the agent moves it into the ticket's spec folder and commits it; with no ticket, it asks which ticket; with content not for the repository's readers, it says what must come out first.
- [ ] AC-049 A show whose page document or skill log, inside the repository and not ignored by git, holds a value of a known secret shape → the page and the chat show a warning that names the file.
- [ ] AC-050 A secret warning → the round still shows, and no commit is refused.
- [ ] AC-051 A page outside the repository or ignored by git → the engine does not scan it.
- [ ] AC-052 The secret scan → it calls no model and no network.
- [ ] AC-053 Content with no known shape (customer data, personal notes, work context) on a page in the repository → the agent warns the human.

Writer and commands:

- [ ] AC-054 The session that owns a page ended, and a new session resumes the work → the new session answers the open notes, and the page and the log record the takeover.
- [ ] AC-055 Grill, propose-solution, to-subtasks and ad-hoc pages → they all show, wait, read and end a round through the same commands, from one home.
- [ ] AC-056 A page that breaks a page rule or an answer rule → no engine check refuses it.

## Worked examples

Data is made up.

### WE-01 — usual: a grill round with notes

| Start | What the agent does | Result |
|---|---|---|
| The human sends 4 marks and 3 notes. Note 1 on the export-format card: "CSV is fine, add a header row". Notes 2 and 3, on 2 cards: "drop the fax field". | Note 1: "Agreed. The export-format card now names a header row." Notes 2 and 3: the same answer, "Done. The fax field is removed from both cards." | 3 rows, 3 answers (2 equal). Each answer links to the card it changed. |

### WE-02 — edge: 3 points in 1 note

| Start | What the agent does | Result |
|---|---|---|
| On an info card: "Who owns this? When does it ship? Is the limit still 200?" | 1 row with 3 answers, one per point (AR-05). It settles nothing, because an info card asks nothing. | 1 row, 3 answers, no settle. |

### WE-03 — risky: private content, and nobody to ask

| Start | What the agent does | Result |
|---|---|---|
| An ad-hoc page about a bug, on a ticket, shows a customer's data sample. Separately, an autopilot executor meets a one-way door. | The bug page goes outside the repository; the page header and the chat say git does not track it. The executor opens no page: it parks the question. | Nothing private is committed. No page waits for a reader who is not there. |

## Access & validation policy

Instructions only: nothing in the engine enforces these rows (AC-056).

| Capability | Permitted | Denied | Data scope | Validation |
|---|---|---|---|---|
| Write a page | any agent session with a human at the page | a hands-off subagent, such as an autopilot executor; it parks the question | the topic of its session; a page in the repository shows only what the repository's readers may see | one round at a time; an id on every element the human may note |
| Answer the notes | the session that owns the page document, or a new session that takes over a page whose session ended | a second live session on the same page | the notes of its own page | every note gets an answer before the next round, by AR-01 to AR-10 |
| Read and answer a page | the human at the lavish host on their machine | a person who opens the page file without a lavish session: they can read it, but their notes reach no agent | the whole page | marks and notes reach the agent only through Send to Agent |
| Start an ad-hoc page by command | the human, with `/afkv2:use-lavish` and a topic | an agent with no topic: it asks in chat first | the named topic | the home rule of ADR-0002 |

## Implementation Decisions

- **use-lavish owns writing and answering; `visualize` keeps how components look.** Each fact has one home. The note-answering lines leave `visualize`, and the page-writing skills point to use-lavish.
- **The round commands move to one shared home** that use-lavish names. Every page writer and every ad-hoc page calls them there, not in the grill skill.
- **A new page format version** carries the engine abilities, ad-hoc pages and one note per annotation. Version-0 page documents keep opening and rendering, and none is rewritten. Records checked: this branch holds 1 page document; other branches may hold more (inferred, not checked).
- **Instructions first** ([ADR-0001](adr/requirements/0001-instructions-first-warn-never-block.md)). Deterministic logic only warns about an outcome that cannot be undone, and never blocks.
- **Ad-hoc page home** ([ADR-0002](adr/requirements/0002-ad-hoc-page-home.md)).
- **Git-state notice and secret warning** ([ADR-0003](adr/requirements/0003-secret-and-tracking-warnings.md)). The secret scan uses a fixed list of about 10 shapes that rarely give false alarms (cloud keys, forge tokens, chat tokens, private-key blocks, signed web tokens, passwords inside web addresses). It grows only after a real miss. The agent covers what has no shape.
- **One note, one row** ([ADR-0004](adr/requirements/0004-one-note-one-row.md)).
- **One diagram-text component (Mermaid)** draws the "diagram text" kinds with the renderer setup installs. The engine keeps each rendered diagram and renders it again only when its text changes. Graph, sequence, map and run strip stay native, because their boxes take notes; a Mermaid diagram takes a note only as a whole (inferred).
- **Code blocks use a popular, proven highlighter library.** The design picks which one.
- **The tooltip ability (EG-08) is built in this ticket as a top item**, taken from the durable-tooltips work of #153.
- **All accepted forms are built in this ticket** ([ADR-0005](adr/requirements/0005-all-forms-in-this-ticket.md)). The plan builds the skill, the answer rules and the answer abilities first, so the 2 pains close early.
- **The title's short title** is written by the agent in round 1 and never changed.

## Testing Decisions

- A good test drives the real entry point: render a page document through the engine and read the HTML; send a made-up host answer through ingest and read the page document.
- Engine abilities (EG-01 to EG-24): one render test per ability, light and dark where the look differs.
- One note per annotation (EG-18): an ingest test with several annotations on one element gives one note and one row each.
- Git-state notice (EG-11): one test per state, in a throwaway repository: committed, not committed yet, ignored, outside.
- Secret scan (EG-12): harmless made-up markers that match each shape; a hit warns and the round still shows; an untracked page is not scanned.
- Diagram fallback: a render with no renderer on the path shows the text block and no failure.
- Old pages: this grill's version-0 page document renders after the change.
- The skill's instructions (PR, AR, K) have no automated check, by the ruling; a dogfood grill run on the built skill proves them.

## Out of Scope

- The grill's glossary rule falls back to the v1 root glossary when no glossary map exists: a grill skill defect, reported from this dogfood run; handled by its own ticket.
- Goals and non-goals, open questions, quality requirements and always-or-never guarantees as table K rows: the agent picks a form.
- Engine checks that force the page rules or the answer rules: ruled out by the owner.
- Engine detection of private content with no secret shape: an instruction to the agent (AC-053).

## Further Notes

- The owner's ruling (2026-11-03): "instructions only. No engine checks or guardrails to force this". The owner's steer refines it: "less deterministic guardrails which might create friction or blockers, instead having them as instruction. we still can have guardrails or deterministic logic, especially when it comes to critical/irreversible outcome … definitely cannot have blocker situations".
- The reference page and its study live outside this public repository, on the owner's machine. Never commit them.
- Measured: a 10-shape secret scan of a 182 KB page document takes 5.3 ms, and 52 ms at 10 times the size. One Mermaid render takes about 3.7 s; a rendered diagram weighs 6 to 45 KB.
- The diagram renderer installs nothing on a machine with no Edge browser; AC-033 covers that machine.

### Assumptions this PRD rests on

- The page host can reuse an open browser tab for a new round (unverified-external; the human acknowledged it). AC-036 rests on it; AC-037 is the fallback.
