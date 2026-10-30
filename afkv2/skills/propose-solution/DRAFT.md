# The top-down draft

After the critical aspects, propose the whole design: every layer, from the top down. The human vets it and adjusts it. `design_round.py` reads the 2 tables below, so they are the one copy of the layer order and of the human-locked set.

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

## Cards

The kinds, the decide rule, a note that contradicts its mark, steers and the escape: [../grill/ROUNDS.md](../grill/ROUNDS.md), the sections with these names. The same rules hold here. How a signal settles: the round pass in `../visualize/components/card.md`.

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

- A `sign` mark signs. A note that changes the wording returns the point: the new card holds the new wording and asks for a `sign` mark.
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
