# Workflow Glossary

The AFK workflow's own vocabulary — pipeline stages, artifacts, modes, states, verdicts. The one home for *methodology* terms; **domain** vocabulary stays in the target repo's glossaries (start at its `GLOSSARY-MAP.md`). Any skill, report, or artifact using one of these terms points here instead of redefining it. A status line may use these terms freely, but the accompanying plain-terms sentence (`REPORTING.md`) must stand alone without this file.

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

**Ticket description (`TICKET.md`)**:
The requirements-level distillation of the PRD that `/afk:to-ticket` publishes to the parent ticket — User Stories + Acceptance Criteria mandatory, system behavior in domain language, no technical depth, no repo-artifact references. Derived: content changes start in the PRD.

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

**Feature terms file**:
`LAVISH-TIPS.md` in the ticket's spec folder — the feature's committed term → explanation store (glossary entry grammar, but not a glossary: feature- and session-scoped ids and ideas live here); parsed into every lavish render's tooltip dictionary alongside this workflow glossary (`LAVISH.md` "Tooltips").
_Avoid_: feature glossary (real domain vocabulary graduates to the service glossary)

**Plan**:
The `plan/` directory — `PLAN.md` (index: solution map, seam register, progress tracker, smoke gate) plus one subtask contract per slice. A local contract, never Jira issues.

**Main checkout (`<main-checkout>`)**:
The repo's primary checkout — the first entry of `git worktree list`, resolvable from inside any worktree. Plugin definition (skills, hooks, scripts) is always read and executed from `<main-checkout>/tools/payable/ai-agents/plugins/workflow/…`, never from a worktree's copy — a worktree carries the plugin frozen at its branch point, stale the moment the plugin advances. Only plugin paths pin here; cwd stays wherever the work is (builds run in the worktree).
_Avoid_: repo root as a plugin-path base (resolves to the worktree when cwd is one)

**Subtask contract**:
One `plan/NNNN-slug.md` file — the binding scope, acceptance, and verification of a single slice; its id is the filename stem.

**Context excerpts**:
The contract's `## Context excerpts` section — verbatim, citation-tagged PRD/SDD/ADR quotes selected at slicing time; the executor's spec context, full parent docs opened only when the excerpts don't settle a question.

**Journal**:
`plan/JOURNAL.md` — the append-only, timestamped event log of everything that happened to a plan (status changes, parks, commits, verdicts). The "what happened while you were gone" artifact. Format: `skills/afk/to-subtasks/JOURNAL-FORMAT.md`.
_Avoid_: log file (generic), history

**Trace matrix**:
`plan/TRACE.md` — the end-of-feature rollup mapping each acceptance criterion to the subtask, commits, and tests that satisfied it; emitted by the terminal sync-harness subtask.

**Grill log**:
`GRILL-LOG.md` in the ticket's spec folder — the on-disk checkpoint of a grill's settled decisions (claim ledger, locked layers, aspect verdicts), so a paused or compacted grill session can resume without re-deriving. Format: `skills/afk/grill-requirements/GRILL-LOG-FORMAT.md`.

**Staple**:
A delivered capability that became a standing expectation (registry: `{service}/STAPLES.md`); every future feature matching its trigger must consider adopting it.

**Manifest**:
`skills/afk/setup/MANIFEST.md` — the register of every external dependency the workflow needs (CLIs, MCP servers, secrets, sibling checkouts), one entry each with a runnable `Probe:` (exit 0 = healthy) and a `Fix:` (`auto:` runnable / `human:` guided). The one home for install steps; skills point at entry ids instead of restating them.
_Avoid_: prerequisites list (scattered inline — the failure the manifest retires)

**Freshness registry**:
The `FRESHNESS.md` table mapping each plugin-source artifact to its steward and the changes that must touch it in the same commit — the write-time defense against stale docs.

**Tooltip dictionary**:
The persistent term → explanation map every lavish artifact inherits — seed `hooks/lavish-tips.json` merged with this workflow glossary and the feature terms file (most specific wins; all committed, so a session resumes on any machine). Injected deterministically at render time by `hooks/lavish-tips.sh`; an agent's only job is giving missing terms a committed home once. Doctrine: `LAVISH.md` "Tooltips".
_Avoid_: legend (the on-page section this layer retires), glossary (that is the domain/methodology vocabulary system)

**Grill-question triage (debate / confirm)**:
The classification every grill question gets before it's asked (rule: `skills/afk/grill-requirements/TRIAGE.md`): *debate* — alternatives worth weighing, asked one at a time; *confirm* — a safe default the user accepts or overrides, batched at the section/layer boundary into one answer round. An overridden confirm escalates to debate.
_Avoid_: quick questions (vague), survey (implies no escalation path)

**Mission control**:
The per-feature, read-only HTML dashboard with two layers: *live* sections derived on every render from the plan's existing artifacts (tracker, journal, gate verdicts, git), and *design-digest* sections rendered from committed [Design digests](#). A viewport, never a second home for status: agents keep writing the artifacts; a renderer keeps the page true.
_Avoid_: dashboard (generic), status page, live page (the artifacts are live; the page just follows)

**Design digest**:
A committed, hash-stamped JSON synthesis of a feature's design docs (`plan/digests/*.json` — architecture, flows, entities, decisions, critical logic, legend) that mission control's design sections render. Authored only by `/afk:mission-control build`; a manifest records every source file's hash, so source drift shows as a visible *stale* banner, never as silently current content. Carries design synthesis only — never status. Contract: `skills/afk/mission-control/DIGEST-FORMAT.md`.
_Avoid_: cache (implies transparent freshness), summary file (undersells the schema contract)

## Design layers (L1–L9)

The top-down ladder the solution grill and the SDD follow. One line each — this is the legend for SDD section titles:

- **L1 — system topology**: where the feature sits among services, UIs, and external systems, and the runtime model (request/response, event-driven, batch); usually inherited from the platform.
- **L2 — service boundaries & integration**: which service owns what; the endpoints and contracts between them.
- **L3 — data architecture**: which datastore holds each piece of state — schema, storage, migration, retention; the most expensive layer to get wrong.
- **L4 — cross-cutting quality**: security (authentication and authorization), transactions, observability, error handling, idempotency, rate limits.
- **L5 — domain model**: entities, aggregates, invariants, and lifecycle states, named in the glossary's language.
- **L6 — process & coordination**: workflows, state machines, transaction boundaries, async jobs, failure recovery.
- **L7 — module decomposition**: packages and modules inside the service, their public interfaces, and dependency direction.
- **L8 — tactical patterns**: class-level design patterns (Strategy, State Machine, Builder…) that shape the seams executors implement against.
- **L9 — implementation seams**: the exact places in existing code the change plugs into, each verified against the codebase before the design is called done.

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

**Materialized seam**:
A seam whose stub + disabled contract-shape test were pre-created on the branch at slicing time (opt-in), upgrading its `Produces`/`Consumes` contract from grep-checked to compiler-checked; marked `[materialized]` in the plan. Only for new-Java seams — existing-file and non-Java seams stay grep-anchored.
_Avoid_: scaffold (generic), codegen (nothing is generated at build time)

## Execution states

**Park**:
Setting a subtask aside at `blocked(<reason>)` while independent work continues; nothing is lost — a parked row waits for a human decision.
_Avoid_: fail (a park is recoverable), skip

**Parked by inheritance**:
A subtask that never started because something it is blocked by parked. Recorded in the journal (the tracker row legitimately stays `pending`).

**Stranded**:
A subtask whose executing subagent died mid-run, leaving its tracker row at an in-flight status. The journal line flagging it is the truth; the stale cell is not.

**Driven mode**:
`execute` run non-interactively under a driver: it never pauses to ask — a decision point follows the decision protocol (`DECISIONS.md`, plugin root); only a parked fork becomes a structured failure outcome.

**Decision point**:
A fork mid-run where specs, contract, findings, or reality disagree and more than one defensible option exists. Classified per `DECISIONS.md` (plugin root): two-way doors are decided on the record; one-way doors and ties park.

**Two-way door**:
A decision reversible on the branch — undo is a revert plus rework; no migration, external write, or published contract survives it. A hands-off agent takes the recommended option itself and records it in the decision ledger. Opposite — **one-way door**: a wrong call outlives the feature, so the human decides.
_Avoid_: reversible/irreversible decision (rotating synonym)

**Decision ledger**:
`plan/DECISIONS.md` — the append-only record of auto-taken two-way-door decisions (grammar: `DECISIONS.md`, plugin root). Executors honour recorded entries over the spec passages they quote; the end-of-run report lists new entries for the human's audit.

**Status ladder**:
The tracker progression `pending → designing → developing → verifying → reviewing → done` that `execute` advances one cell at a time.

**OUTCOME statuses**:
The structured result tokens of an `execute` run (`success`, `test_fail`, `build_fail`, `review_fail`, `adversary_fail`, `blocked_by`, `needs_decision`, `contract_mismatch`, `produces_drift`, `design_conflict`, `timeout`, `other`). Canonical table with meanings and next actions: `README.md` §8.

## Bug pipeline

**`/afk:bug`**:
Interactive-only mid-task bug capture + autonomous fix pipeline, outside the per-feature chain. Five subcommands: `capture`/`dispatch`/`status`/`retest`/`purge`. Refuses `capture`/`dispatch` when invoked hands-off (driven/autopilot) — a human must be in the loop.
_Avoid_: bug workflow (vague — this is one skill, not a chain)

**Ledger**:
The per-bug `state.json` under `.claude/bugs/` — the single source of truth for a bug's lifecycle state, written only by the main interactive session (single-writer invariant). Format: `skills/afk/bug/LEDGER-FORMAT.md`.

**S1-S10 (bug lifecycle states)**:
The ledger's ten states (`captured`, `published`, `queued`, `fixing`, `blocked`, `fix-pushed`, `mr-ready`, `awaiting-retest`, `verified`, `refuted`). Their order, meanings, and every allowed transition edge live in one home: `skills/afk/bug/LEDGER-FORMAT.md`.

**Evidence bundle**:
`bundle.md` — the human-readable dossier of a captured bug (confidence-labeled facts, reproduction steps, capture context). Format: `skills/afk/bug/BUNDLE-FORMAT.md`.

**Publisher**:
The subagent that runs `scripts/publish_bug.py` — the pipeline's Jira-writing actor (create/transition/comment/backfill on that one Bug ticket, ADR-0001).

**Fixer**:
The subagent spawned by `dispatch` into its own git worktree to reproduce, fix, test, push, and open a Draft MR — never merges. Returns exactly one trailing `BUGFIX:` line (grammar: `skills/afk/bug/SKILL.md`).

**Retester**:
The subagent spawned by `retest` to re-run a bug's reproduction read-only once its fix lands, returning evidence + a claimed `RETEST:` verdict the main session spot-checks before advancing the ledger.

**One-live-fixer invariant**:
At most one bug across the whole ledger may hold the `fixing` (S4) lane at a time; a second bug queues (S3) instead of dispatching.

## Gates & verdicts

**Human-locked aspect**:
A design aspect the human decides and signs, never the agent and never the executor — entity design, API surface, authz + scoping, lifecycle + invariants, irreversible/outward side effects, changes to existing behaviour (HL-1..HL-6). Each carries a **contract grade**: the detail it must reach to be reviewable at all. Set + protocol: `skills/afk/grill-solution/HUMAN-SIGNOFF.md`.
_Avoid_: approval (routine), locked decision (that is any settled design call)

**Sign-off**:
The human's own affirming answer to a human-locked aspect's question, recorded verbatim as a `signoff` row in `GRILL-LOG.md` and carried into SDD §0. Void the moment the aspect's design moves; `pending` or `changes-requested` means the design isn't exhausted and the SDD can't publish.

**Review gate**:
The independent post-verification code review (`clean` / `advisory` / `blocking` per invocation) run by fresh subagents, one per concern, that never see the implementor's reasoning. Gate-mode callers settle it via the settle loop. Per-subtask rollup: `plan/review/INDEX.md`.

**Review policy (lean / full)**:
The slice review gate's roster scale, stamped per plan (PLAN.md header, seeded `lean`) with per-contract `## Review` override. `full` = every implementation concern on every slice; `lean` = only concerns whose defects compound or are invisible at feature altitude run per slice — the rest defer to the feature-level review, which widens to cover them and sweeps the deferred findings. Split + resolution: `skills/afk/review/SKILL.md` "Gate policy".

**Settle loop**:
The review gate's round-based caller protocol — review with fresh contexts, fix or dispute every finding (nits included), adjudicate disputes with fresh skeptics, repeat until a round yields nothing actionable. Roles, round structure, termination, and the referee's information diet: `skills/afk/review/SETTLEMENT.md`.

**Stalemate**:
The settle loop's failure exit — the hard round cap reached with findings still open. Always flagged to a human (`review_fail` / `park`): non-convergence at the cap signals a real defect being danced around, an unowned spec ambiguity, or a gamed loop — never routine.

**Adversary gate**:
A fresh session probing the running app under a hard information diet, trying to break the contract (`clean` / `findings` / `tainted` / `env_unreachable`). `tainted` = the session saw forbidden material (the diff, the implementor's tests) and must be respawned.

**Smoke gate**:
The feature-level completion gate — full (runs the verification plan's UI + API suites) or minimal (compile / app-start / regression) — whose green verdict stamps `Feature: complete`. Its `Run history` lines keep every run, red ones included.

**Preflight**:
The feature-level ship gate chained by autopilot after a green smoke gate — brings the branch up to date with master (merge, never rebase), re-runs repo validations and the final seam check, reviews the integrated diff as a whole, readies the MR with evidence, and babysits CI to green. Fixes only mechanical failures; anything semantic parks for the human.
_Avoid_: no-mistakes (the upstream tool it derives from), pre-ship check (vague)

**CI-babysit**:
Preflight's tail — watching the pushed pipeline until green, auto-fixing only mechanical reds (format, config validations, merge-induced compile breaks, one flaky retry) within a bounded number of fix-push cycles; CI-only test failures and secret hits always escalate.

**Escape analysis**:
The post-bug-fix question "which existing test should have caught this, and why didn't it" — answered with a named miss class (`no-scenario`, `weak-assertion`, `wrong-path`, `excluded`, `disabled/flaky`).

**Retro**:
The cross-feature retrospective (`/afk:retro`) that mines delivered plans' exhaust — journals, review rollups, adversary verdicts, park reasons, gate-latency metrics, the lesson ledger — into recurring signals and evidence-cited proposals to change the *workflow*; read-only, a human applies the edits. The systemic counterpart of the per-bug escape analysis, and the safety net behind conclude-at-detection lesson capture.
_Avoid_: postmortem (that is per-incident), audit (that is `/afk:setup audit`'s staleness hunt)

**Lesson**:
A concluded workflow-improvement observation — classified, with a drafted durable edit — captured into the lesson ledger the moment it's detected and confirmable (a human confirms a finding, corrects a misunderstanding, clarifies a term; escape analysis names a miss). Capture protocol: `skills/afk/lessons/CAPTURE.md`.
_Avoid_: retro item (aggregation comes later), todo (a lesson carries its own drafted fix)

**Lesson ledger**:
`.claude/lessons/LEDGER.jsonl` in the **main checkout** (shared across worktrees) — the append-only, event-sourced record of every lesson (`opened → applied → verified`, or `rejected` / `superseded`), stewarded by `/afk:lessons`. Grammar, class enum, statuses: `skills/afk/lessons/LEDGER-FORMAT.md`.

**Escalation ladder**:
The graded response to an applied lesson whose signal recurs: reword → relocate → checklist criterion → Stop-hook gate. One rung per recurrence, each a new lesson superseding the old. Owned by `skills/afk/lessons/LEDGER-FORMAT.md`.
