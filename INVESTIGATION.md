# INVESTIGATION.md — when reading code is finished

Binding on every step that answers a question about existing code. `LANGUAGE.md`
§ "Truth grounding" owns the bar for a single claim; this file owns the missing
half — **when the whole investigation is done, and what records the coverage**.
Completion is **closure over a boundary catalog**, never a time, turn, or token
budget. Skills point here; they never restate it.

Boundary *classes* below are generic. A repository declares its own *instances*
in the `investigation:` block of `.afk/config.yaml` (`CONFIG.md`).

## Question types

| Type | Question |
|---|---|
| Q1 | How does X work, end to end? |
| Q2 | What depends on or calls X? |
| Q3 | What breaks if X changes? |
| Q4 | What edge cases or complications exist? |
| Q5 | Does Y exist? (absence) |

## Boundary catalog

A reference to a symbol crosses code in these ways. Every applicable class gets
a verdict.

| # | Class | How a reference hides | Deterministic? |
|---|---|---|---|
| B1 | Textual reference | none | yes — search every **name form**: simple name, fully qualified name, import alias, wire or serialized name |
| B2 | Type dispatch | bound by parameter or supertype, the subtype never named | partly — search declaration and parameter forms, then read the dispatch site |
| B3 | Reflection / scan | classpath scan, name-to-class lookup, annotation processing | judgment-only — read the scanning site, decide what it reaches |
| B4 | String-keyed identity | config key, permission string, message name, bean name, route, service name — a rename breaks silently | partly — search the literal key forms, read the site that builds them |
| B5 | Serialized shape | field order, enum ordinal, wire or column name — an insert breaks readers with zero textual match | partly — enumerate readers and writers of the type (B2), read the codec |
| B6 | Generated code | output produced by a build step | yes when built; absent output is `frontier(unbuilt)`, never absence |
| B7 | Build graph | module in or out of the aggregator, client-module chains | yes — parse the declared aggregator manifests |
| B8 | Config / profile / environment | per-profile files, environment names read at start-up, feature flags | yes — search key and variable literals across every profile file |
| B9 | Persistence | entities, columns, migrations, views, indexes, cross-schema readers | yes — search entity and column names in schema and migration sources |
| B10 | UI callers | hand-written client classes, address-by-name lookups, direct cross-service calls | yes — search endpoint and service-name literals under the interface source directories |
| B11 | Async / jobs | listeners, queue consumers, scheduled work, after-commit publishers | yes — search the declared registration forms |
| B12 | Tests | which tests go red — or none, which is `unguarded` | yes — search the name forms under test sources |
| B13 | Documents | steering files, specifications, decision records asserting behaviour | yes — search the name forms in markdown; a document the code refutes is a finding |
| B14 | External | other repositories, deployment and operations manifests, live consumers | no — `frontier` or `unverified`, never silently omitted |

## Dispositions and verdicts

Every discovered node gets exactly one disposition: `traced` (an edge to the
next node) · `terminal` (an effect that ends the path) · `irrelevant(cited)` ·
`frontier(reason)` (deliberately not crossed) · `unverified(reason)`.

Every applicable boundary gets exactly one verdict: `closed(n, method)` ·
`n/a(reason)` · `frontier(reason)` · `unverified(reason)`. A class with no
enumeration method is `unverified(no method)` — never skipped, never absence.

## Completion per question type

Each list is the minimum. A question with no method for a listed item records
`unverified`, and the answer carries it.

- **Q1** — B1, B2, B10, B11 close the entry-point set. Per hop: file:line, the
  guard that decides, the transformation the hop applies, the transaction
  boundary, the identity or scoping context. Every effect enumerated: writes
  (B9), outbound messages and calls (B4, B11), files and logs. Terminal states
  and every failure path: caught, rethrown, retried, timed out, rolled back,
  fallback. Every variant the path takes: profile, role, scope, lifecycle state,
  flag. Config the path reads (B8), tests pinning each hop (B12), documents
  asserting the behaviour (B13).
- **Q2** — every name form (B1) listed; B1–B7, B10–B11 each with a verdict; the
  transitive set carried to the depth the facet propagates (see Closure). The
  result is a list of sites, never a count.
- **Q3** — Q2, plus per site: the facet relied on (name · signature ·
  serialized field · route · schema · behaviour · ordering · config key ·
  cached value · authorization or data scope), which change kinds break it,
  whether a test pins it (`unguarded` when none), and a verdict of `breaks` ·
  `unchanged(cited)` · `unverified`. B4 and B6 are checked explicitly. Two
  cross-site items close the question: schema and migration effects (B9), and
  deployment order — which side has to ship first for the other to keep working.
- **Q4** — every branch, guard, and exception on the Q1 path, plus per hop:
  null and empty, bounds and precision, lifecycle state, concurrency and
  transaction boundary, partial failure, retry and duplicate delivery,
  rollback, stale cache, unavailable dependency, configuration failure,
  authorization and data scoping, ordering, size and paging, time and time
  zone, tenant or profile, flag state. Each case is covered by code (cited),
  covered by a test (cited), or a gap.
- **Q5** — every name form (B1) and B1–B13 enumerated with the method stated,
  generated output (B6) and the full inheritance chain included. Message names
  and configuration keys (B4, B8) are searched as literals, not as symbols.
  When history is in scope, historical names too — the symbol's renames, and
  the deletions a content search over the log finds. The answer is
  `absent(closed over B1–B13, frontier: B14)` or `unverified` — never a bare no.

## Closure

The work queue is closed when no node is unchecked and no boundary is without a
verdict. Transitive expansion continues only while the **facet propagates**:

- rename or signature → direct dependents and their compile-time chain;
- serialized shape → every reader and writer of the type, at any depth;
- behaviour → callers whose tests or contracts pin it; stop where a caller's own
  contract absorbs it;
- config key → every reader of the key.

A site classified `unchanged` with a cited reason is not expanded. Siblings
sharing an exact shape are classified once with the shared reason and listed
individually. There is no time, turn, or token cap; a stalled child is handled
by the stall watchdog (`DELEGATION.md`), which parks and never truncates.

## Counter-search

A second pass over the same universe by a **different method** per boundary
class — a different name form, the registration site instead of the call site,
the generated output instead of the source. Any new node reopens the queue.

- The deterministic second-name-form pass always runs; it is free.
- An agent-driven counter-search is mandatory for Q2, Q3, Q5, and for the Q1
  entry-point and effect sets when the caller is a design step.

## Proportionality

The coverage ledger is always written. Fan-out across children and the
agent-driven counter-search are spent only when one holds: the question is Q2,
Q3, or Q5; hits span more than one module; a judgment-only class has hits; or
the caller is a design step.

## Load-bearing claims

Every claim the reader acts on is traced or labelled — `LANGUAGE.md`
§ "Truth grounding" owns that bar and is not restated here. A load-bearing claim
with no ledger node behind it is written `unverified: <reason>`.

## Coverage ledger

Every investigation writes one. Two files: the complete record as JSON, and a
short markdown report beside it. Table set, field grammar, file names, location
rule, and the report shape: `skills/utils/investigate/LEDGER-FORMAT.md`.

## Reply shape

A reply carrying an investigation's result answers, then separates facts from
inferences, then lists what was not checked. Exact shape:
`skills/utils/investigate/LEDGER-FORMAT.md`.
