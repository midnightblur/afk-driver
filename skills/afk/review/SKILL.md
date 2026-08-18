---
name: review
description: Independent read-only review of a subtask slice or feature diff → clean/advisory/blocking verdict. Use as the post-verification gate or via /afk:review {NNNN-slug} | --feature.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# afk:review — independently check the implementor's work

The implementor builds a subtask, gets every `## Verification` tier green, and is *about to* mark it `done`. Green tiers prove the code runs and the declared tests pass — they do **not** prove it honours the project's documented rules, covers everything the spec asked, or is free of things a senior engineer wouldn't ship. This skill is that second gate.

One fresh subagent per concern, independent and strictly read-only (Hard rules below); the caller decides what to do with the verdict.

Two entry points, same machinery:

- **Gate mode** — invoked by the caller after all tiers green, before `done`. The caller gates through the settle loop in [SETTLEMENT.md](SETTLEMENT.md) — re-review after every remediation, fix-or-dispute per finding, referee-kept termination; that file owns the loop, the caller owns finding-class routing.
- **Standalone** — `/afk:review {NNNN-slug}` from a worktree on the parent branch, to audit a slice's work on demand. Same report; no gating, no side effects.

## Argument

A single subtask id — its filename stem under `plan/`, e.g. `0003-export-registry` (`.md` optional) — or `--feature`. Optional:

- `--base <ref>` — override the diff range. By default the slice diff is **this subtask's own commits**: every commit is prefixed `[{NNNN-slug}]` by convention, so the slice is the combined patch of the commits on this branch whose subject starts `[{NNNN-slug}]`. Isolates exactly this subtask's contribution — **including any file it touched outside its `## Scope` globs**, which lets `scope-and-impact` catch scope creep (a Scope-glob-filtered diff would hide it). `--base <ref>` falls back to `git diff <ref>...HEAD` for the edge case where the subtask's history isn't cleanly isolable by prefix (e.g. a squash or a hand-amended branch).
- `--only <concerns>` / `--skip <concerns>` — narrow the concern set (names below); overrides gate policy and trigger activation. Default: every active concern.
- `--tag <suffix>` — appended to every artifact basename this run writes (`{basename}-{base-short}-{tag}.md` / `.findings.json`, and the caller's matching `.outcomes.json`) so repeated gate-mode invocations over the same base don't overwrite each other. Naming only — the tag never appears in any reviewer prompt.
- `--feature` — review the **integrated feature diff** instead of one slice: the diff is `git diff $(git merge-base origin/master HEAD)...HEAD` (or `--base`). Roster is fixed (triggers ignored): the four design-level concerns, briefed on what's invisible at slice altitude — change patterns emerging *across* subtasks (shotgun surgery/divergent change spanning slices), coupling drift between the touched modules, coherence of the integrated API surface and vocabulary — plus `logic-correctness` and `code-quality` over the whole diff — and `claude-md-compliance` when the plan's header reads `Review policy: lean` ("Gate policy" below): the one lean-deferrable concern the fixed roster doesn't already carry. Reads the feature's PRD/SDD/ADRs and `plan/PLAN.md` in place of one subtask contract; report basename `feature` replaces `{NNNN-slug}`.

## What the review reads

Resolve these once, in the orchestrator, and hand each subagent only the paths it needs (don't paste the implementor's chat):

1. **The slice diff.** This subtask's own commits (by `[{NNNN-slug}]` prefix, or the `--base` range) — **not** pre-filtered by Scope globs, so out-of-scope edits stay visible to `scope-and-impact`. The unit under review. **Materialize it once**: write the diff to a scratch file (`{scratchpad}/review-{basename}-{base-short}.diff`) and hand every subagent that path — never paste diff text into a prompt.

   **Delta rounds.** When `--base` and `--tag` are both passed (a settle-loop delta round — [SETTLEMENT.md](SETTLEMENT.md)), also materialize the **full cumulative diff** (the whole slice/feature range) to a sibling scratch file and hand every subagent both paths: the delta is the unit under review — findings anchor there; the full diff is **context only**, so surrounding and related/similar code stays visible without re-reviewing it.
2. **The subtask contract.** `plan/{NNNN-slug}.md` — `## Goal / Scope / Acceptance / Verification / Produces / Seams / Parent PRD / Parent SDD / Design refs`. In uncited mode the SDD-only sections are absent.
3. **The parent spec.** The `## Parent PRD` file, and (cited mode) the `## Parent SDD` + cited `## Design refs` ADR sections.
4. **The CLAUDE.md chain** for every touched file — walk each changed file's directory up to the repo root collecting `CLAUDE.md`, plus that service's root `CLAUDE.md`, the repo-root `CLAUDE.md`, any `.claude/rules/*.md`, and the nearest `GLOSSARY.md`. The rulebook the `claude-md-compliance` concern checks against.

## Concerns (11)

One subagent per concern, all spawned in a **single message** as parallel `Agent` calls (`subagent_type: general-purpose`). Each prompt is self-contained: `checklists/PRECEDENCE.md` pasted **verbatim**, **plus** the concern's `checklists/{concern}.md` pasted verbatim through the end of its `## Reviewer checklist` section — any trailing `## Guardrails` block excluded (its consumers are design-time, not reviewers; the subagent has no other access to these files) — the resolved paths from "What the review reads", and the findings contract. Concerns may overlap a line — the checklist files' one-owner exclusions prevent most of it; dedup handles the rest. Spawn mechanics and each reviewer's return contract follow `DELEGATION.md` (plugin root).

The roster scales twice. First by **gate policy** ("Gate policy" below): `full` runs the six implementation/conformance concerns on every **full-unit** review, the four design-level concerns plus `refactor-safety` behind diff-shape triggers (below); `lean` shrinks the always-set to the three concerns whose defects compound or are invisible at feature altitude and defers the rest to the feature-level review. Then **delta rounds scale further** — the always-set consolidates into one sweep reviewer plus signal-activated specialists ("Delta-round roster" below).

| Concern | Asks | Default subagent reads |
|---|---|---|
| `claude-md-compliance` | Does the diff violate any **documented** rule in the applicable CLAUDE.md chain / rules / glossary? | diff + CLAUDE.md chain |
| `spec-fidelity` | Is it **truly done** — every `## Acceptance` bullet satisfied, every cited seam implemented, every `## Produces` anchor real, no requirement silently dropped? | diff + contract + PRD/SDD |
| `logic-correctness` | Works for all reasonable inputs? Bugs, edges, null-handling, error paths, races. | diff (+ repo for context) |
| `code-quality` | Smell / anti-pattern / "a senior dev wouldn't do this." Dead code, duplication, god methods, leaky abstractions, naming, magic values, debug logs, hardcoded secrets/tokens, TODO left in. | diff |
| `test-veracity` | Do the new tests assert what matters — the framework's **real output**, not the DTO; not tautological; cover the acceptance, not just the happy path; use the Nakisa test helpers? | diff + contract |
| `scope-and-impact` | Stayed inside `## Scope` globs, no forbidden patterns, no scope creep, no stray churn — **and** what's the blast radius of the changed symbols? | diff + contract + repo |
| `refactor-safety` | Did the implementor touch **pre-existing** code — rename, re-signature, extract/move, edit a shared base/util/DTO — and is each medium/high-risk change behaviour-preserving, fully propagated, and warranted? | diff + repo |
| `design-quality` | Module shape: shallow/pass-through layers, change-pattern smells (shotgun surgery, divergent change), coupling, speculative generality. | diff + repo + SDD/ADRs |
| `domain-alignment` | Domain language vs the glossary, aggregate/invariant placement, transaction boundaries, data ownership. | diff + nearest `GLOSSARY.md` + SDD/ADRs |
| `resilience` | Every new out-of-process touchpoint: timeouts, failure story, unbounded results, N+1, idempotency, dual writes. | diff + repo |
| `api-contract` | New/changed public surface: minimal, misuse-resistant, expand-contract compatible, coherent with the local dialect. | diff + repo + contract |

**Default `class` per concern** — each subagent stamps `class` on its findings so the caller's routing is deterministic: `claude-md-compliance`→`compliance`, `spec-fidelity`→`spec`, `logic-correctness`→`correctness`, `code-quality`→`smell`, `test-veracity`→`test`, `scope-and-impact`→`scope` (but a genuinely broken direct caller is `correctness`), `refactor-safety`→`correctness` or `scope` per its rule, the four design-level concerns→`design` (escalation and `pattern-debt` rules live in their checklist files + `PRECEDENCE.md`). A cross-class finding takes the class naming the underlying cause. `delta-sweep` has no single default — its checklist stamps `class` per item.

### Gate policy (slice mode)

Slice rosters scale by a per-plan **review policy**. Resolution, first hit wins: the contract's `## Review` `policy:` line → the PLAN.md header `> Review policy:` → `full` (absent everywhere — older plans keep full).

- **`full`** — the six always-on concerns plus the trigger table below.
- **`lean`** — always-on shrinks to **`spec-fidelity` + `scope-and-impact` + `test-veracity`**. `refactor-safety`, `api-contract`, `domain-alignment` keep their trigger rows; `logic-correctness` activates only on the lean trigger: the slice has a downstream consumer (a later contract's `## Consumes` cites this id, or the seam register lists it under *Used by*) or its `## Complexity` is `complex`. Everything else — `code-quality`, `claude-md-compliance`, `design-quality`, `resilience`, untriggered `logic-correctness` — **defers to the feature-level review**.

One criterion decides the split: **does the defect compound if caught late?** Scope creep and per-slice acceptance are invisible at feature altitude; a weak test poisons every later gate that trusts green tiers; a wrong producer contract, refactor, or entity shape propagates into every dependent — those review per slice. A smell, a documented-rule breach, a module-shape or resilience gap costs the same fixed at the feature gate, whose roster already covers the deferred set (`--feature` above; under a lean plan it also gains `claude-md-compliance`). Deferral is routing, never dropping — a deferred concern is recorded in the report header and the caller's later gate sweeps deferred findings back in (`SETTLEMENT.md` "Deferral rule").

A contract's `## Review` section (grammar: `skills/afk/to-subtasks/SUBTASK-CONTRACT.md`) overrides per slice: its `policy:` line replaces the plan default; its `opt-in:` line forces named deferred concerns onto this slice's roster as if always-on.

### Trigger activation (slice mode)

Before spawning, scan the slice diff — changed-file list + added hunks, cheap greps in the orchestrator, no subagent:

| Concern | Activate when the diff contains |
|---|---|
| `refactor-safety` | any modified or deleted pre-existing line (a diff that is purely additions of new files has nothing to break) |
| `design-quality` | a new class/interface/module, or changes spanning more than ~6 files |
| `domain-alignment` | a new or modified `@Entity`, any `@Transactional`, or a new public service-layer method |
| `resilience` | a new out-of-process call (HTTP client/JMS/RFC), repository query, endpoint, or scheduled job |
| `api-contract` | a touched `*-client`/`*-entities` module, public DTO, or controller signature |

Under `lean`, the `design-quality` and `resilience` rows are suspended (those concerns defer instead) and `logic-correctness` uses the lean trigger ("Gate policy" above); the other rows apply under either policy.

No trigger hit → skip the concern and record it in the report header (`activated: … · skipped: … (no trigger)`); a concern deferred by policy records `deferred: … (→ feature gate)` in the same line — skipped or deferred is auditable, never silent. `--only`/`--skip` override triggers; `--feature` ignores them (fixed roster).

### Delta-round roster (settle-loop delta rounds)

On a delta round (`--base` + `--tag` together — see "Delta rounds" above), the always-set does **not** all respawn — a small remediation doesn't warrant a specialist per concern each re-reading the contract and rule chain. The roster:

1. **`delta-sweep`** — always, one reviewer, `checklists/delta-sweep.md`: the full-roster always-set's highest-yield items condensed to a remediation-delta lens. Not a 12th concern — a delta-round consolidation; its prompt names any co-spawned specialists so one-owner exclusions hold.
2. **Fix-owner specialists** — every concern that owned a `critical`/`high` finding remediated since the previous round runs in full: the lens that demanded the fix re-examines the territory. Roster selection is orchestrator metadata — the reviewer is spawned cold, its prompt carrying no finding history or round context.
3. **Delta triggers** — the design-level table above, scanned on the delta, plus: `test-veracity` when the delta touches test code; `claude-md-compliance` when the delta touches a directory whose CLAUDE.md chain no prior round collected; `scope-and-impact` only when the orchestrator's **own** Scope-glob/forbidden-pattern grep over the delta hits (run that check inline first — it's a grep, not an agent); `logic-correctness` + `code-quality` when the delta exceeds ~150 changed lines or ~6 files (below that, the sweep owns their territory).

The report header's activation line records the delta roster like any other run. `--only`/`--skip` still override.

### Checklists

One home per concern: `checklists/{concern}.md`, pasted into the reviewer's prompt (paste rule above) together with `checklists/PRECEDENCE.md` (baseline precedence, the `pattern-debt` rule, one owner per smell, the mandatory open question). Each file states its default `class`, its escalations, and its "Not yours" exclusions. Design-level files also carry a `## Guardrails` digest for design-time consumers. The `test-veracity` file owns the sampled mutation-probe rule (gate mode only). `checklists/delta-sweep.md` is the delta-round consolidation reviewer's checklist — same mechanics, not one of the 11 concerns.

## Findings contract

Each subagent returns a JSON array; the orchestrator merges, dedups by `file:line` (keep highest severity, union the `concern` list), assigns ids `r-001..r-NNN`, ranks most-severe first.

```json
{
  "id": "r-001",
  "concern": "claude-md-compliance",
  "criterion": "<checklist item name, e.g. 'Shallow Module (APoSD)', or 'open-question'>",
  "severity": "critical|high|medium|low",
  "class": "correctness|spec|compliance|smell|scope|test|design|pattern-debt",
  "file": "11700-payable/.../Foo.java",
  "line": 42,
  "finding": "One-line headline.",
  "why": "One sentence — the rule broken / input that fails / requirement missed.",
  "fix": "One-line remediation.",
  "evidence": "Quoted rule text or the diff line."
}
```

`class` names the finding's cause and drives the caller's routing:

| `class` | Means |
|---|---|
| `correctness` | a real bug — wrong behaviour on a reachable path |
| `spec` | a requirement / acceptance bullet unmet or silently dropped |
| `compliance` | a documented CLAUDE.md-chain rule broken |
| `smell` | code-quality substance a senior reviewer would flag |
| `scope` | an out-of-scope or unwarranted change riding the slice |
| `test` | a test that doesn't prove the behaviour it claims to |
| `design` | a design-level judgment call — module shape, domain boundary, resilience gap, contract-surface defect |
| `pattern-debt` | the diff follows a documented repo pattern where the baseline catalog disagrees — never blocks, feeds the debt ledger |

`criterion` names the checklist item that produced the finding (`open-question` for the open-question slot) — the key for per-criterion outcome telemetry: the caller records each finding's remediation outcome as `plan/review/{basename}-{base-short}.outcomes.json` (`--tag` appends `-{tag}`) (`{"r-001": "fixed" | "dismissed(<reason>)" | "deferred"}` — the caller's own artifact in this directory, like the adversary's reports), and `/afk:retro` aggregates which criteria earn their keep.

## Verify pass (design-level findings)

After merge/dedup, take every finding from a design-level concern with severity ≥ `medium` and spawn one fresh skeptic subagent per finding — all in a single message, parallel. Each skeptic gets the finding, the diff, and the CLAUDE.md-chain + spec paths, with one brief: **refute it** — show the flagged design is justified by the spec, an established repo pattern, or a constraint the reviewer missed; return `upheld` only when no refutation holds, else `downgraded (<reason>)` or `refuted (<reason>)`. Refuted → drop the finding; downgraded → severity − 1, keep. Stamp the report header `verified: <n> upheld / <n> downgraded / <n> dropped`. Implementation-level findings skip the pass — they're cheap to dismiss at remediation.

Severity rubric:

- **critical** — ships a wrong result, data corruption, security/authz hole, or violates a "Never …" hard rule.
- **high** — an acceptance bullet unmet, a documented rule broken, a real bug on a reachable path, a broken direct caller.
- **medium** — smell / weak test / missing negative case / convention drift that a reviewer would block on but isn't load-bearing.
- **low** — nit, optional improvement.

## Verdict & output

Write the full report to `plan/review/{NNNN-slug}-{base-short}.md` (human-readable, ranked, prose per `LANGUAGE.md` at the plugin root — read it before writing; `--feature` mode uses basename `feature`; `--tag` appends `-{tag}`) and the machine list alongside as `…-{base-short}.findings.json`. The report header carries the policy + activation line (`policy: … · activated: … · skipped: … · deferred: …`) and the verify-pass stamp. `{base-short}` is `git rev-parse --short` of the diff base: the `--base` ref when given; in default mode, the parent commit of the slice's first `[{NNNN-slug}]` commit.

**Update the rollup.** Upsert this subtask's row in `plan/review/INDEX.md` (create with the header row if missing) — the one place a human sees every subtask's latest review state without hunting per-base filenames:

```
| Subtask | Latest report | Verdict | crit/high/med/low | Open advisories |
|---|---|---|---|---|
| {NNNN-slug} | {NNNN-slug}-{base-short}.md | advisory | 0/0/2/1 | m: <one-line each, or "none"> |
```

One row per subtask, latest review wins the row; `Open advisories` lists the medium/low findings still unaddressed so they stop vanishing into MR bodies. Adversary reports (`{NNNN-slug}-adversary.md`) live in this directory too; when one exists, mention it in the row's `Latest report` cell.

End with one line the caller parses, plus the plain-terms line per `REPORTING.md` (plugin root):

```
REVIEW: <verdict> — crit=<n> high=<n> med=<n> low=<n> [findings: <path>]
In plain terms: <one jargon-free sentence — the worst thing found and whether it blocks shipping>
```

| Verdict | When |
|---|---|
| `clean` | zero findings (`pattern-debt` excluded — it never counts toward any verdict) |
| `advisory` | only `medium`/`low` findings |
| `blocking` | any `critical`/`high` finding |

**Pattern-debt ledger.** Append each `pattern-debt` finding as one row to `plan/review/PATTERN-DEBT.md` (create with the header row if missing): `| date | source report | criterion | overriding repo rule | one-line conflict |`. The ledger is the evidence trail for evolving the documented pattern — a criterion recurring across features is a signal, not noise.

What the caller does with the verdict is the caller's policy; each blocking finding's `class` drives the caller's routing. Standalone mode stops here — print the verdict and the report path; gate nothing. When a human is present, render per LAVISH.md (RP-4, playbook `table`) for findings triage; markdown fallback and driven mode use the written report above instead.

## Hard rules

- **Read-only.** Never edit, commit, push, or fix. This skill finds; the caller (or `/afk:fix`) remediates.
- **Independence.** Reviewer subagents get the diff, contract, spec, and CLAUDE.md chain — **never** the implementor's chat or rationale. A reviewer told "the author says this is fine" isn't a reviewer.
- **Cite or drop.** Every finding carries `file:line` and quoted evidence (rule text, failing input, unmet acceptance bullet). No vibes-only findings; if unsure of the line, cite the hunk header.
- **Verify pass fan-out.** The verify pass is a second single-message parallel wave.
- **Don't re-run the build or tests.** Tiers are already green at the gate; this is static review — read the diff and search the repo for callers; don't compile or run. **One carve-out:** the `test-veracity` concern's sampled mutation probe (its checklist owns the sampling rule) — it measures test *strength*, which no static read can, and fails open to "no signal".
- **No new contract sections.** This skill only *reads* the plan; it owns no PLAN.md cell and no Implementation-Notes block. The caller records outcomes.

## See also

- The plugin `CLAUDE.md` — Section ownership invariants + the outcome-status lockstep.
