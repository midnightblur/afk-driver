# Workflow Glossary

The AFK workflow's own vocabulary — pipeline stages, artifacts, modes, states, verdicts. This file is the one home for *methodology* terms; **domain** vocabulary stays in the target repo's glossaries (start at its `GLOSSARY-MAP.md`). Any skill, report, or artifact that uses one of these terms points here instead of redefining it. A status line may use these terms freely, but the plain-terms sentence that accompanies it (`REPORTING.md`) must stand alone without this file.

Format follows the canonical glossary rules in `skills/utils/glossary/GLOSSARY-FORMAT.md` — one owner per term, tight definitions, opinionated `_Avoid_` lists.

## Pipeline

**AFK**:
"Away from keyboard" — settle requirements and design interactively up front, then let the implementation middle run hands-off; the human returns for CR/Merge and the smoke verdict.

**Grill**:
An interactive interview skill (`grill-requirements`, `grill-solution`, `grill-verification`) that settles decisions in conversation and writes no design documents — only the glossary and its grill-log checkpoint.
_Avoid_: interview (as a skill name), review (that is the code gate)

**Synthesis skill**:
A skill that writes an artifact from already-settled conversation (`to-prd`, `to-sdd`, `to-verification-plan`, `to-design-brief`, `to-subtasks`); it never re-interviews.

**Full path / Lean path**:
Full = grills + SDD + verification design for complex features; lean = PRD → plan → execute for bugs/refactors/tooling. Mode of the plan follows from what exists upstream, never from a flag.

## Artifacts

**PRD**:
Product Requirements Document — the *what and why* in business language; the most human-readable artifact in the chain.

**SDD**:
Solution Design Document — the *how*, organized top-down by the L1–L9 design layers, one visualization per layer.

**ADR**:
Architecture Decision Record — one decision, its alternatives, and why. Two tiers with separate numbering: requirement ADRs (what/why, under `adr/requirements/`) and design ADRs (how, under `adr/design/`).

**Design Brief**:
The 1–2 page plain-language digest of PRD + SDD + ADRs (one diagram, a decision table, stakeholder impact) — the fastest way for a human to catch up on a design.

**Verification Plan**:
`VERIFICATION-PLAN.md` — the feature's UI journeys and API scenarios with per-aspect coverage verdicts; what turns the smoke gate from minimal into full.

**Ticket index**:
`INDEX.md` in the ticket's spec folder — the read-this-first dashboard: one-paragraph feature summary, artifact table with states, recommended reading order. Format: `skills/afk/to-prd/INDEX-FORMAT.md`.
_Avoid_: dashboard, status file

**Plan**:
The `plan/` directory — `PLAN.md` (index: solution map, seam register, progress tracker, smoke gate) plus one subtask contract per slice. A local contract, never Jira issues.

**Subtask contract**:
One `plan/NNNN-slug.md` file — the binding scope, acceptance, and verification of a single slice; its id is the filename stem.

**Journal**:
`plan/JOURNAL.md` — the append-only, timestamped event log of everything that happened to a plan (status changes, parks, commits, verdicts). The "what happened while you were gone" artifact. Format: `skills/afk/to-subtasks/JOURNAL-FORMAT.md`.
_Avoid_: log file (generic), history

**Trace matrix**:
`plan/TRACE.md` — the end-of-feature rollup mapping each acceptance criterion to the subtask, commits, and tests that satisfied it; emitted by the terminal sync-harness subtask.

**Grill log**:
`GRILL-LOG.md` in the ticket's spec folder — the on-disk checkpoint of a grill's settled decisions (claim ledger, locked layers, aspect verdicts), so a paused or compacted grill session can resume without re-deriving. Format: `skills/afk/grill-requirements/GRILL-LOG-FORMAT.md`.

**Staple**:
A delivered capability that became a standing expectation (registry: `{service}/STAPLES.md`); every future feature matching its trigger must consider adopting it.

## Design layers (L1–L9)

The top-down ladder the solution grill and the SDD follow. One line each — this is the legend for SDD section titles:

- **L1 — system topology**: where the feature sits among services, UIs, and external systems.
- **L2 — service boundaries & integration**: which service owns what; the endpoints and contracts between them.
- **L3 — data architecture**: schema, storage, migration.
- **L4 — cross-cutting quality**: security, transactions, observability, error handling.
- **L5 — domain model**: entities, aggregates, invariants.
- **L6 — process & coordination**: workflows, state machines, async jobs.
- **L7 — module decomposition**: packages and modules inside the service.
- **L8 — tactical patterns**: class-level design patterns and idioms.
- **L9 — implementation seams**: the exact places in existing code the change plugs into, each verified against the codebase.

## Seams & contracts

**Seam**:
A boundary where new code meets existing code — an existing contract (signature, endpoint, event, table) the feature extends or reworks. The riskiest rows of any plan.

**Seam register**:
The `PLAN.md` table mapping each SDD seam to the subtask that implements it and the subtasks that use it.

**Cited mode / uncited mode**:
Cited = an SDD exists, so every subtask carries typed `Produces`/`Consumes` anchors and citation tags that are grep-enforced at three checkpoints; uncited = PRD-only, human-gated instead.

**Grep-anchor**:
The unique string a `Produces` bullet declares so its existence in the codebase can be checked mechanically (`{file}#{anchor}`).

**Produces / Consumes**:
The typed contract between subtasks: what code artifacts a slice delivers, and which upstream deliveries it depends on. A consumer's miss is a `contract_mismatch`; a producer's own miss is `produces_drift`.

## Execution states

**Park**:
Setting a subtask aside at `blocked(<reason>)` while independent work continues; nothing is lost — a parked row waits for a human decision.
_Avoid_: fail (a park is recoverable), skip

**Parked by inheritance**:
A subtask that never started because something it is blocked by parked. Recorded in the journal (the tracker row legitimately stays `pending`).

**Stranded**:
A subtask whose executing subagent died mid-run, leaving its tracker row at an in-flight status. The journal line flagging it is the truth; the stale cell is not.

**Driven mode**:
`execute` run non-interactively under a driver: it never pauses to ask — a would-be question becomes the closest structured failure outcome.

**Status ladder**:
The tracker progression `pending → designing → developing → verifying → reviewing → done` that `execute` advances one cell at a time.

**OUTCOME statuses**:
The structured result tokens of an `execute` run (`success`, `test_fail`, `build_fail`, `review_fail`, `adversary_fail`, `blocked_by`, `contract_mismatch`, `produces_drift`, `design_conflict`, `timeout`, `other`). Canonical table with meanings and next actions: `README.md` §8.

## Gates & verdicts

**Review gate**:
The independent post-verification code review (`clean` / `advisory` / `blocking`) run by fresh subagents, one per concern, that never see the implementor's reasoning. Per-subtask rollup: `plan/review/INDEX.md`.

**Adversary gate**:
A fresh session probing the running app under a hard information diet, trying to break the contract (`clean` / `findings` / `tainted` / `env_unreachable`). `tainted` = the session saw forbidden material (the diff, the implementor's tests) and must be respawned.

**Smoke gate**:
The feature-level completion gate — full (runs the verification plan's UI + API suites) or minimal (compile / app-start / regression) — whose green verdict stamps `Feature: complete`. Its `Run history` lines keep every run, red ones included.

**Escape analysis**:
The post-bug-fix question "which existing test should have caught this, and why didn't it" — answered with a named miss class (`no-scenario`, `weak-assertion`, `wrong-path`, `excluded`, `disabled/flaky`).
