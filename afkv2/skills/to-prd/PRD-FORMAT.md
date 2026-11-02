# PRD.md format

A PRD states what success and failure look like for the feature. Say each fact once, in plain domain language. It holds no file paths or code, except a decision-rich shape from a prototype. The whole file goes into the ticket: product owners and QA read it there.

## Sections

`prd_files.py check` refuses a PRD with a missing section or a missing id. Keep these `##` headings, in this order. `Catalog` is optional.

| Section | Holds | Grill log source |
|---------|-------|------------------|
| Problem Statement | the problem from the user's view: a few sentences, or a short list of pains | `Round 0`, ticket text |
| Solution | what the user gets; no restatement of the pain | `Settled` rows |
| Catalog | a set of parallel things (rules, states, roles, parts), once, as a table with a stable id column; other sections name rows by id and never repeat them | `Settled` rows |
| User Stories | the few most valuable journeys, most important first: `As a <actor>, I want <feature>, so that <benefit>` | `Settled` rows |
| Acceptance Criteria | binary, testable conditions; see below | `Settled` rows, accepted `Staples` |
| Worked examples | one `### WE-NN — <kind>: <case>` per case, with data; see below | `Examples` |
| Access & validation policy | one table row per capability: permitted roles, denied roles (at least one, or "everyone may" stated), data scope, validation rules | `Policy` |
| Implementation Decisions | modules and their duties at product level, one line per decision; where an ADR exists, the decision and a link | `Settled` rows |
| Testing Decisions | test strategy: what a good test proves here, which modules get tests, prior art | `Settled` rows |
| Out of Scope | one line each, and where it is handled when it is handled | `Spinoff`, `Settled` rows |
| Further Notes | facts a later reader must know; the block "Assumptions this PRD rests on" | `Ledger` |

Every `Steer` row and owner note binds the text. Quote a human's words exactly where the wording matters.

## Acceptance criteria

One bullet per criterion: `- [ ] AC-NNN <condition → observable outcome>`.

- One pass-or-fail condition per id. Split a compound.
- State both sides: name each boundary value and the outcome on each side.
- State the exact observable effect of a refusal, not only "rejected".
- Black box: no test data, no click path, no Given/When/Then.
- Cover the happy path of each capability, each boundary, each denied role of the policy table, each validation refusal.
- Many rows with one shape: write one criterion over the catalog, and name the table, while the table holds the columns a tester needs.
- A claim marked `unverified-external` in the grill log: each requirement that rests on it carries `(unverified premise: <claim>)`, and "Assumptions this PRD rests on" lists every such claim.

## Worked examples

At least the most frequent case, one edge and one risky case when they exist. Show the input and the result as a table; add a diagram when the flow branches. Give each case concrete values.

## Ids

- `AC-NNN` starts at `AC-001`. `WE-NN` starts at `WE-01`.
- An id never changes and is never reused. A new id takes the next number of its family, wherever its line stands in the file.
- To drop a criterion or an example, keep its line or heading and write `retired: <why>`, so the id stays in the published text.
- `prd_files.py check` compares with the last commit of the file, and refuses a gone id, a reused id, and a text that moved to another id.

## Diagrams

A diagram is a ` ```mermaid ` fence at the top level of the file. The publish renders each one as a picture. Text inside a diagram is not in the published text, so an id must also stand in the text.
