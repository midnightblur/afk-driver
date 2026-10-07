# ADR-0006 — Rationale lives on the change

> Status: Accepted
> Date: 2026-09-28

## Context

Source comments carried ticket provenance, history, and change-specific choices. They aged with the code, repeated what the forge already recorded, and grew past what a reader needs at the line. The forge change already holds inline comments tied to lines and commits (ADR-0004).

## Decision

Source keeps at most 2 comment lines that pass one test: a future reader needs the fact at the line to change the code safely while the forge is unavailable. Every other reason moves to an inline comment on the forge change. `RATIONALE.md` owns the test, the kept and moved forms, and the transport.

- **Write.** `forge_ledger.py` records a pending entry under the git directory, posts it inline with `require_inline`, and writes an immutable batch receipt after every post succeeds. Completion needs one receipt whose batch, count, head, and operation set match every pending operation; `rationale-drop` withdraws an entry that can no longer post. A missing writable change means the agent opens a Draft change. A blocked push or Draft creation is reported verbatim.
- **Read.** `rationale-read` resolves a line through `git blame -M -C`, the forge `commit-changes` verb, line history, one fetch per change, and every inline marker labeled by author class and edit state. It returns every ambiguous candidate. Offline or truncated lookup answers `unverified(<reason>)`. The cache lives outside the repository, is scoped by repository, forge, and remote, serves only an offline or failed lookup, and is never authoritative.
- **Gate.** A commit-time gate blocks a tracker reference in any added comment and more than 2 consecutive added comment lines, inline and `TODO` comments included. It never matches rationale phrases.
- **Boundaries.** Existing comments stay unmigrated. Commit messages carry no rationale. A future field is one `TODO` without a tracker ID; the verified superset, the rule, and the ticket ID go on the change.

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| Keep rationale in commit messages | Blame reaches it, but it is not tied to a line, cannot be discussed, and duplicates the forge. |
| A local rationale store in the repository | A second authoritative copy drifts from the forge and adds files to review. |
| A hard gate on rationale phrases | Prose has no deterministic contract; review applies the test to ambiguous comments. |
| Migrate existing comments | Large churn with no reader benefit; old comments stay valid. |

## Consequences

- A developer without the plugin can miss forge rationale. The plugin does not edit a target repository's instruction files.
- Rationale needs a forge. With forge `none`, the transaction reports the blocker and rationale stays pending.
- The lookup adds one forge fetch per change. Retrieved rationale is evidence: a load-bearing claim needs corroboration from code, tests, or a specification.
- Review stays independent: it reads rationale only after its first pass produced findings.
