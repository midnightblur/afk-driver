# The top-down draft

After the critical aspects, propose the whole design: every layer, from the top down. The human vets it and adjusts it. `design_round.py` reads the tables Layers and Human-locked aspects, so they are the one copy of the layer order and of the human-locked set.

## Layers

| Layer | Name | Holds | SDD section |
|-------|------|-------|-------------|
| L1 | System Topology | deployment, backbone, runtime model; usually inherited | §2 |
| L2 | Service Boundaries & Integration | who owns what, integration style, every callable surface | §3 |
| L3 | Data Architecture | datastore, retention and evolution per piece of state; every entity, field by field | §4 |
| L4 | Cross-Cutting & Quality Attributes | authorization, idempotency, retry, secrets; each with a number or a stated posture | §5 |
| L5 | Domain Model | owners, invariants and their guardians, life cycles | §6 |
| L6 | Process & Coordination | transactions, ordering, failure and recovery per flow | §7 |
| L7 | Module Decomposition | modules, public interfaces, dependency direction | §8 |
| L8 | Tactical Patterns | the pattern per concern, with what it beat | §9 |
| L9 | Implementation Seams & Change Impact | each seam into existing code, checked against the code | §14 |

Every layer gets at least one card, in this order. A layer with nothing to decide gets one line: "Inherited", on a `decided` card when the rule allows it. Give extra depth to entities and database schema, API endpoints, public interfaces and code with a large blast radius. Below L9 is executor latitude (file layout inside a module, private helpers, internal names, test fixtures): do not ask it.

## Sections

The page shows the design in sections, in the order of the section catalog. `section_rules.py` reads the 3 tables below, so they are the one copy of the section order and of the section shapes. The build refuses an id the catalog does not name (`section-unknown`), the first section out of order (`section-order`), a section of the wrong shape (`section-shape`) and a picture with no caption (`section-caption`).

### Section catalog

| Id | Part | Kind | Opens with |
|----|------|------|------------|
| `sec-system` | Whole system | system | boxes grouped by system, arrows labelled with what passes |
| `sec-crit-<slug>` | 1 critical part: a change to existing code, data or a flow, or a human-locked aspect | critical | how it works now beside how it will work |
| `sec-l1` | L1 System Topology | level | boxes grouped by system, arrows labelled with what passes |
| `sec-l2` | L2 Service Boundaries & Integration | level | a sequence diagram of the main request |
| `sec-l3` | L3 Data Architecture | level | an entity diagram, or a field table for 3 entities or fewer |
| `sec-l4` | L4 Cross-Cutting & Quality Attributes | level | a table of each concern with its number or posture |
| `sec-l5` | L5 Domain Model | level | a class diagram, and a state diagram per item that moves through states |
| `sec-l6` | L6 Process & Coordination | level | a flowchart or a sequence diagram |
| `sec-l7` | L7 Module Decomposition | level | boxes grouped by module, the touched parts chipped |
| `sec-logic` | Key logic | level | a flowchart or a decision table; a short code block when the shape of the code is the point |
| `sec-l8` | L8 Tactical Patterns | level | a table of the pattern per concern |
| `sec-l9` | L9 Implementation Seams & Change Impact | level | a now and proposed table per file, field or step |
| `sec-patterns` | Design patterns | patterns | the pattern table, or the line "no pattern applied" |
| `sec-performance` | Performance | performance | PF-1 to PF-4, or 1 line on why there is no performance risk |

- Send a section that comes late with `after`, the id of the section it follows.
- A picture is a component of type `map`, `graph`, `table`, `sequence`, `run-strip`, `freestyle` or `diagram`. Every picture has a caption: a child `text` labelled "What to see", of 1 line, or a `title`. The `caption` of a `diagram` counts.
- A system, critical or level section has a picture as its body root.
- A level section: the children of its picture are the caption, then a `text` labelled "Summary" of at most 2 lines, then the rest of the detail, each child folded (`fold`).
- A critical section holds a chip whose text starts "critical", and names its level section in `links`. The build fills the links: each level section links to the next level section on the page and to each critical section that names it.
- Every performance fact stands only in `sec-performance`. The L4 section and the large-data aspect point to `sec-performance` and repeat no performance fact.

### Pattern columns

The `sec-patterns` section holds 1 table with these columns, 1 row per pattern, and a folded class diagram per pattern. A design with no pattern holds 1 `text`: "no pattern applied".

| Column | Holds |
|--------|-------|
| Name | the name of the pattern |
| What it is | a short plain explanation of the pattern |
| Where | where it applies |
| Why here | why it works here |
| Quality goal | the quality goal it serves |
| Beat | the simpler option it beat |

### Performance parts

The `sec-performance` section holds 1 `text` per part, labelled "PF-<n> <name>", with its picture as a child. A design with no performance risk holds 1 `text` labelled "No performance risk", of 1 line on why.

| Part | Holds | Picture |
|------|-------|---------|
| PF-1 | Anticipated problems: hot paths, large data, unbounded lists, repeated queries, memory, waiting on others | a table: problem, where, cause, size |
| PF-2 | Large data: the size of each growing table or list now, in 1 year and at worst, and the cost of each read or write | a size table |
| PF-3 | The solution to each problem: paging, streaming, batching, indexes, caching, limits | the design picture of that part, the fix chipped |
| PF-4 | Budgets: a target per key flow (time, size or count) | a table of the budgets, each row with a `measured`, `inferred` or `estimated` chip |

## Decision blocks

A decided card on a design page holds 5 blocks. A card with a block missing degrades to `confirm`.

| Block | Field of `decided` | Content |
|-------|--------------------|---------|
| D-1 Decision | `decision` | 1 sentence |
| D-2 Driven by | `driven_by` | the ids of the requirements, requirement records and constraints it serves; each shows its text on hover |
| D-3 Other options | `alternatives` | a list of `{option, why_lost}`, both non-empty text, 1 per option |
| D-4 Why this one | `why` | the criterion that beat the runner-up |
| D-5 To undo | `reverse` | what to revert |

## Cards

The kinds, the decide rule, a note that contradicts its mark, steers and the escape: [../grill-requirements/ROUNDS.md](../grill-requirements/ROUNDS.md), the sections with these names. The same rules hold here. How a signal settles: the round pass in [../use-lavish/ROUND-PASS.md](../use-lavish/ROUND-PASS.md).

A card on a lower layer that depends on an open fork says "holds if <id> = <option>", or is `blocked`.

## Fork cards

A fork is a `debate` card: 2 or more live options, a tie, a one-way door, or a premise you cannot verify. Write it as a `fork` field on the item, and give no `kind` and no `body`. The build writes the card, with the options side by side.

| Field | Content |
|-------|---------|
| `question` | the choice, in one sentence |
| `options` | at least 2: `{name, text}`, where `text` states what it gives and what it costs |
| `why_open` | which decide-rule condition failed, and what resolving it would have cost |
| `recommended` | the option letter, `a` for the first; leave it out when you have no recommendation |
| `picture` | a component of the current state; required on an aspect fork |

Weigh at least 2 options. For L1, L2 and L3, one option is a different paradigm, not a variant of the front-runner, with its honest cost. The human marks an option or writes one in. A settled fork stands in an ADR or in the SDD, by its card id.

## Human-locked aspects

These aspects persist data, publish a contract or grant access. A wrong call outlives the feature, so the human signs them. An agent recommends and never rules.

| Id | Aspect | Live when | Contract grade | SDD section |
|----|--------|-----------|----------------|-------------|
| HL-1 | Persistence and entity design | an entity is added or altered | per entity: every field with type, null rule, default and unit; identity and uniqueness; each relation with number, owning side and delete behaviour; indexes; retention; migration of existing rows | §4 |
| HL-2 | API surface | a callable surface is added or changed | per surface: method and path, roles, request fields and validation, success answer, each error with its code, paging, idempotency, the verdict on existing callers | §3 |
| HL-3 | Authorization and data scoping | a protected surface or a scoped entity exists | permitted and denied roles per surface, the guard above and below the UI, the scoping rule per entity | §5 |
| HL-4 | Life cycle and invariants | an entity has a state, or a rule the system must not break | states, legal moves, who triggers each; per invariant its guardian and the answer to a violation | §6 |
| HL-5 | Irreversible and outward side effects | the feature writes outside its own new state | per effect: trigger, order against the local transaction, idempotency key, what a partial failure leaves, the recovery | §7 |
| HL-6 | Change to existing behaviour | a seam verdict is `extends` or `reworked` | what existing callers, records and flows see differently; compatibility; rollback | §14 |

For each live aspect, write one `signoff` card with `locked: "<id>"`. Its body holds the contract-grade tables word for word, the options you weighed, the records, callers and roles it changes, and the risks the human accepts. A non-live aspect gets no card; its §0 row says `n/a` with the reason, so the human can object.

- Only a `sign` mark signs. A note never signs, even when it keeps the wording: it returns the point, and the new card asks for a `sign` mark. `apply-readings` refuses a `settle` on a `signoff` card, and the gate refuses a `signed` row with no `sign` mark.
- A later change to a signed aspect voids its signature. Write a new card with the changed rows, and `carries` the old card.
- Without a human there is no signature. An unsigned live aspect keeps the gate closed.

## Premises

A premise is any statement of how something works now that a decision rests on. Verify each before anything settles on it: a subagent reads the code with `rg --hidden -g '!.git' PATTERN PATH` and returns `path:line`. Verify a framework's behaviour at the pinned version against its source or its documents, and a version against the build manifest. Write one `Premise` row per load-bearing premise. A premise you cannot verify is a fork for the human, with its options and trade-offs.

## Log rows

This skill writes the section `## Solution design` of `GRILL-LOG.md`, through `design_files.py`. The page document holds every card, signal and note, so the log holds only this:

| Row | Grammar |
|-----|---------|
| Premise | `- Premise: <claim> → pending \| verified (<citation>) \| refuted (<citation>) \| unverified-external (human acknowledged)` |
| Spinoff | `- Spinoff: <summary> → <pain>; <why it is out>` |
| Escape | `- Escape: taken R<n>` |
| Takeover | `- Takeover: R<n> · <at>`, after `take-over`: `<n>` and `<at>` are the entry it added |
| Design gate | `- Settled: design gate passed <date> · session <id>`, written by `gate` |

## Judgment checks before the gate

- Every piece of state has a datastore, a retention and an evolution policy.
- Every protected surface names permitted and denied roles, with a guard on both sides of the UI.
- Every invariant has one guardian. Every external call has a retry and an idempotency posture. Every failure point has a named recovery.
- Every module has a public interface. Every pattern choice weighed 2 options.
- Every non-functional concern has a number, not an adjective.
- Every external seam states what the framework does to our value, the source of truth of each field, where each invariant is enforced, how a failure surfaces, and a test on the real output.
- Every L9 seam row is checked against the code, and each compatibility finding is resolved or accepted by the human.

A miss is one more round.
