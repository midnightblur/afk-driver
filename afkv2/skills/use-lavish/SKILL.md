---
name: use-lavish
description: /afkv2:use-lavish — how to write a page and reply to the human's notes: the page rules, the answer rules, the forms by kind, page or chat. Opens an ad-hoc page on a topic, and holds the page commands. Use to show a human a page, to write or answer a page round, or with a topic to start an ad-hoc page.
---

# /afkv2:use-lavish

This skill says how to order and word a page and how to reply to the human's notes. Write the page document by `/afkv2:visualize` ([../visualize/SKILL.md](../visualize/SKILL.md)): it says how each component holds, looks and is used.

## Page or chat

Offer a page for options side by side, a picture, or 3 or more questions. Ask a one-line question in chat.

A hands-off subagent, such as an autopilot executor, has no human at a page: open no page, and park the question.

## The commands

Run each command from the repository root: `<python> "<this skill's folder>/<command>"`. `<python>` is the Python in the setup install record (line `python`). Every result is one JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input.

| Command | Does |
|---------|------|
| `scripts/page_home.py start --topic T [--ticket K] [--private]` | gives a new ad-hoc page its `doc`, `session`, `raw_file` and `home` by the home rule; writes nothing |
| `scripts/page_home.py track --doc D --ticket K` | moves a page and its side files into the ticket's spec folder; its result holds `doc` and `moved` |
| `scripts/round_document.py build --doc D --session S [--ticket K] --round-input F [--ticket-file T] [--replace] [--private]` | writes the round into the page document; each entry of `warnings` in its result names a note of the last round with no reply, or a short title it ignored: reply to that note in this round, and run `build` again with `--replace` |
| `scripts/page_round.py present --doc D [--scan F]... [--no-show]` | checks, renders and shows the round; scans the page and each F (a file the skill writes beside the page, such as its log) for secrets; `--no-show` does not show it, for a round asked in chat |
| `scripts/page_round.py wait --doc D --raw-file F` | waits for the human's round send and writes it to F |
| `scripts/page_round.py reply --doc D --reply-file F` | shows the Markdown in F on the page |
| `scripts/page_round.py ingest --doc D --raw-file F` | reads the round send into the page document |
| `scripts/round_document.py apply-readings --doc D --readings F` | writes the readings of the round pass ([ROUND-PASS.md](ROUND-PASS.md)) |
| `scripts/page_round.py take-over --doc D` | records that this session took the page over; its result holds `session`, `round` and `takeovers` |
| `scripts/page_round.py end --doc D` | ends the page session |

## An ad-hoc page

1. **Topic.** With no topic, ask in chat what the page is about, and open no page. Done when you hold a topic.
2. **Start.** Run `scripts/page_home.py start --topic "<topic>"`. Add `--ticket` when the work has a ticket. Add `--private` when the content is not for the repository's readers: customer data, personal notes, work context. Done when the result holds `doc`.
3. **Round 1.** Write the round input by the rules below: `short_title` (at most 40 characters; it never changes), `step` (the topic), `banner`, `items` and `maps`. Add `value_sets` for the value chips the round uses. Add `ticket_projects`, such as `["ABC"]`, for each Jira project whose tickets the page names and the config does not list, so that each key links to its ticket. Add `ticket_titles`, such as `{"ABC-12": "Fix the login", "#4": "Add a flag"}`, for each ticket, issue or change the page names whose title you read: its link shows the title on hover. A later round adds titles and keeps the earlier ones. Run `build` with the `doc` and `session` of `start`, the same `--ticket`, and `--private` when `start` had it. Then run `present`. A refusal holds the failed `verb`. On `check` or `render`, the human has not seen the round: fix the named field in the round input, and run `build` again with `--replace`. `round-shown`: the human may be answering the round in the browser, so wait for it. On `show`, the page host is not available: show the round as Markdown in chat, with every card id, write the human's reply to `raw_file`, and go to step 5. Done when `present` succeeds and you reported its notices ("After each show").
4. **Wait.** Run `wait` as a background command the harness tracks; its exit tells you the round send is in `raw_file`. On a harness whose Stop hook waits for the page, end your turn after `present` instead, and write the raw response it hands back to `raw_file`, word for word. When the result lists side questions in `btw`, write one short Markdown answer for each to a reply file and run `scripts/page_round.py reply`. Then go to step 5, or run `wait` again when `raw_file` is null.
5. **Answer.** Run `ingest`, read the round send by [ROUND-PASS.md](ROUND-PASS.md), and run `apply-readings`. Write the next round with a reply for every note, then `build` and `present`. Done when the human ends the session; then run `end`.

## After each show

Read the result of `present` and tell the human in chat:

- `git_state` other than `committed`: git does not track the page. Say where it lives in one line: in the repository but not committed yet (`untracked`), ignored by git (`ignored`), outside the repository (`outside`), or unknown and not scanned (`unknown`).
- Each entry of `secrets`: the file, the line and the shape, never the value. Ask the human to take it out before a commit. With `secrets_more` above 0, give that count of further hits. The round still shows.
- Each file in `scan_cut`: the scan read only its first 2 MB.
- `diagrams` with `as_text` above 0: give the counts rendered, cached and as text in one line, and the reason that the page states under each diagram it shows as text.
- Content with no known shape (customer data, personal notes, work context) on a page in the repository: warn the human, and offer to take it out.

## Track a page

When the human asks to track the page:

1. A private page cannot be tracked: its content is not for the repository's readers. Say what must come out, and offer a new page, started without `--private`, that holds only what the readers may see. A page with no ticket needs one: ask the human which ticket. Done when the page is not private and you hold its ticket.
2. Run `end` on the page at its old path.
3. Run `scripts/page_home.py track --doc D --ticket K`. `move-failed`: run `track` again; it moves the rest. `needs-ticket` or `private`: run `present` on the old `doc`, and go to step 1.
4. Commit the files in `moved` on the feature branch; with `moved` empty, the page was in the spec folder already, so commit `doc`.
5. Run `present` on the new `doc`. Done when the commit exists and `present` succeeds.

## Take over a page

A session that resumes a page whose session ended takes it over before it writes a round:

1. Run `scripts/page_round.py take-over --doc D`.
2. Write the Takeover row `- Takeover: R<n> · <at>` in the skill's log by its row command: `<n>` and `<at>` are the last entry of `takeovers`. A page with no log has no row.
3. Reply to every note that has no reply, by the answer rules. Done when each note has a reply.

## The rules

### Page rules

| Id | Rule |
|---|---|
| PR-01 | A heading states the conclusion, with a number. |
| PR-02 | A card opens with the verdict, then the evidence, then the detail, then risks and pushback. |
| PR-03 | Put first what the human needs first: what changed and where the asks are, then the overview, then the detail. Each open question has a recommendation. |
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
| PR-15 | Make a note the main answer: show the information first and the questions last. A card's question asks for the human's view; a mark is a shortcut, not the only answer. |

### Page layout

The engine lays out the page by its version: you write the content, and the engine puts each part in its place.

#### What goes first on a version 2 page

1. the title and the banner of the current round: each section that the round added, changed, merged or removed, each other element that it changed, each as a link; then what settled, what it unlocks and what is parked;
2. the notes and replies of the session;
3. the maps;
4. the sections, in the order of `sections`;
5. the worked examples, each marked frequent, edge or risky, with the stories it covers;
6. the questions for others;
7. the questions of the round: its cards in 1 block (PR-15);
8. the settled points, each folded to its heading and settled line;
9. the earlier banners, closed.

The visible text holds no element id and no round code: a round reads "round 3".

#### Sections and change lines

- Round 1 gives a section to each part of the topic: each part named in the ticket, in round 0 or reached by the code reading. A part that no question has reached yet has the state `not_reached`.
- A section shows its current text in every round. It never moves to the settled points.
- A merge sets `merged` and `merged_into`, a current section. A removal sets `removed` and `reason`. The section stays as 1 line, and it never returns. Nothing is deleted, so every note finds its element.
- A section that depends on another names it in `links`. A card names the section it asks about in `section`: the card shows a link to its section, and the section shows a chip with the count of its open questions.
- The round input holds only the entries that changed, in `sections`, `stories`, `examples` and `questions`.
- A new section goes to the end. Send it with `after`, the id of a section, to place it right after that section, or with `after: null` to place it first. A section sent again with `after` moves there.
- Send each entry whole, without `changes`, and with `change`: its 1 change line for this round, `{cause, text}`.
- The causes: `note` with `notes`; `answer` with `card`, the developer's answer on that card; `answer_from` with `question`, an answer from someone else; `finding`, an agent finding.
- The builder appends the change line. It refuses an entry without one (`no-change-line`).
- An entry left out keeps its text and its change list exactly.
- The builder refuses an entry sent unchanged (`unchanged-entry`).
- A change list shows newest first, 1 line per round with its cause. It shows open and never folds.
- The banner lists each added, changed, merged or removed section from the change lines. Write no banner field for them.

#### The questions block

- The asking cards of the round show in 1 block, after the questions for others and above the settled points. Each card with `section` shows a link to its section.
- The questions for others show as their own part, in the order of `questions`, with a filter by who to ask (`who`). A new question goes to the end; a follow-up goes right after the question it follows, by `after`; `after: null` puts a question first. A question that waits on another names it in `waits_on`, and the page links to it. A question with `choices` shows a tick for 1 option, or for several when `several` is true.

#### What goes first on a version 0 or 1 page

1. the title and the banner of the current round;
2. "Notes on the whole session": every note of the session, card notes included, with its reply, in one fold per round;
3. the maps;
4. the points of the current round, one card per point, in kind order (`debate`, `confirm`, `decided`, `signoff`, `info`), then the copy bar; an asking card of an earlier round that is still open stays here too;
5. "Settled by earlier rounds": the other points, newest round first, each folded to its heading and settled line;
6. "Earlier banners", closed.

A point is the newest card and the cards it `carries`. A part drops out when it is empty or repeats an earlier part.

#### Title and tab

The browser tab title and the page heading are `<ticket> · <short title> · <step>`. They hold no round number, so they stay the same every round. A page with no `short_title` (an upgraded format 0 page) shows its feature. A later round shows in the tab that the first show opened: `present` answers `tab: reused`. Give the human the `url` in one line then, so a closed tab costs nothing.

#### Controls the engine adds

You do not write these; the engine puts them on every page.

- Copy bar, below the current round's cards: copies the marks when the page has no lavish session.
- btw? button, bottom left: a one-line side question and one Ask button. Ask posts only the question to the side-question listener of the wait; the marks and notes the human queued stay queued for Send. The wait asks it in the agent's terminal pane (`/btw` on Claude, `/side` on Codex, through herdr), and the panel shows the answer; the round stays open. With no wait running, the panel says so. Engine modules: `engine/btw_listener.py` and `engine/side_question.py` (plugin root).

### Answer rules

| Id | Rule |
|---|---|
| AR-01 | Open with the outcome: Done, Agreed, Recorded, Kept, Deferred, Counter, No. |
| AR-02 | Say what changed and where, 1 sentence per change. |
| AR-03 | Push back plainly on disagreement: name the cost and the timing, and give a counter-proposal. |
| AR-04 | A pushback that needs the human's call becomes a new question card, with a recommendation. |
| AR-05 | A note with several meanings (an answer, a new idea, a question) gets 1 reply that states each reading, in that note's row. |
| AR-06 | A reply that changes nothing says why: kept, deferred, already done. |
| AR-07 | Mark a guess as "(inferred)". Say so when the note could not be read in full. |
| AR-08 | Update every point the change touches, not only the noted card: each gets a new card that carries the old one. |
| AR-09 | Never repeat the human's note in the reply, steers included: the row already shows the note, and the skill's log keeps the exact words. |
| AR-10 | Each note gets its own row. It also gets its own reply, written for that note. No reply copies another note's reply, and no row groups notes. On a version 2 page, `build` and `apply-readings` refuse a reply that names 2 or more notes (`reply-many-notes`). |

### Forms by kind

A suggestion: pick another form when it fits the content better, and state on the page in one line why. For a kind with no row, pick a form. "Built by" names how the form is drawn: an existing component, a new component (EG-24), diagram text (EG-13) or a code block (EG-15). Every chart and diagram follows PR-07 and PR-13.

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
| K-33 | Work a review, incident or decision leaves behind | An action table: action, type, owner, tracking link, state chip | Each action has an owner and a place | existing |
| K-34 | Past events | A list in time order, each line with its time, key moments in bold | Past events read as a story | existing |
| K-35 | One measure with a goal and good or poor bands | A bullet graph: a bar for the value, a tick for the target, bands behind | Value, goal and distance in one line | new component |
| K-36 | Request times, sizes or durations, where an average hides the tail | One spread: a histogram; several spreads: box plots on a shared scale | The shape shows the tail | diagram text (histogram), new component (box plot) |
| K-37 | Estimates of time, cost or size, often several | One bar per item on a shared scale, low to high, a dot at the likely value, numbers at the end, 1 line on what the range means | A single number reads as more exact than it is | new component |
| K-38 | Faster or slower than before, over or under budget | Bars left and right of a zero line, the sign in the label | The direction is the message | new component |
| K-39 | A rule with several conditions and outcomes | A decision table: condition columns, outcome columns, one row per case | A missing case shows | existing |
| K-40 | Codes, states or enum values | A value, meaning table | One look answers what a value means | existing |
| K-41 | An earlier statement turned out false | A claimed, true, source table | The correction is visible | existing |
| K-42 | A record cites a human's call | A quote block: the words, who, when; on a page that replies to notes, the notes row shows the words, so the reply does not repeat them | A ruling in its own words cannot be misread | existing |
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

### Refinements

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
