---
name: review
description: Independent multi-aspect review of one subtask's implementation — fresh subagents (one per concern, parallel) check the slice diff against the applicable CLAUDE.md chain, the subtask's spec/acceptance contract, and senior-engineer code-quality bars, then emit a ranked findings report + a verdict. Read-only; never commits, never auto-fixes. Use when `/afk:execute` reaches its post-verification review gate (Step 10), or standalone via `/afk:review {NNNN-slug}` to audit a slice's work. Reports a structured verdict the caller gates on.
---

# afk:review — independently check the implementor's work

The implementor (`/afk:execute`) builds a subtask, gets every `## Verification` tier green, and is *about to* mark it `done`. Green tiers prove the code runs and the declared tests pass — they do **not** prove it honours the project's documented rules, covers everything the spec asked, or is free of the things a senior engineer wouldn't ship. This skill is that second gate.

It spawns **fresh subagents — one per concern, in parallel** — that see the diff, the contract, and the CLAUDE.md hierarchy, but **not** the implementor's reasoning. Independence is the point: the agent that wrote the code is the worst auditor of it. The skill is strictly **read-only** — it finds and ranks; it never edits, commits, or fixes. The caller decides what to do with the verdict.

Two entry points, same machinery:

- **Gate mode** — invoked from `/afk:execute` Step 10 after all tiers are green, before `done`. Execute reads the verdict and gates (auto-fix loop or stop). See `/afk:execute` Step 10 for the gate policy.
- **Standalone** — `/afk:review {NNNN-slug}` from a worktree on the parent branch, to audit a slice's work on demand. Same report; no gating, no side effects.

## Argument

A single subtask id — its filename stem under `plan/`, e.g. `0003-export-registry` (`.md` optional). Optional:

- `--base <ref>` — override the diff range. By default the slice diff is **this subtask's own commits**: `/afk:execute` prefixes every commit with `[{NNNN-slug}]` (its Step 6), so the slice is the combined patch of the commits on this branch whose subject starts `[{NNNN-slug}]`. This isolates exactly this subtask's contribution — **including any file it touched outside its `## Scope` globs**, which is what lets `scope-and-impact` catch scope creep (a Scope-glob-filtered diff would hide it). `--base <ref>` falls back to `git diff <ref>...HEAD` for the edge case where the subtask's history isn't cleanly isolable by prefix (e.g. a squash or a hand-amended branch).
- `--only <concerns>` / `--skip <concerns>` — narrow the concern set (names below). Default: all seven.

## What the review reads

Resolve these once, in the orchestrator, and hand each subagent only the paths it needs (don't paste the implementor's chat):

1. **The slice diff.** This subtask's own commits (by `[{NNNN-slug}]` prefix, or the `--base` range) — **not** pre-filtered by Scope globs, so out-of-scope edits stay visible to `scope-and-impact`. This is the unit under review.
2. **The subtask contract.** `plan/{NNNN-slug}.md` — `## Goal / Scope / Acceptance / Verification / Produces / Seams / Parent PRD / Parent SDD / Design refs`. In uncited mode the SDD-only sections are absent.
3. **The parent spec.** The `## Parent PRD` file, and (cited mode) the `## Parent SDD` + cited `## Design refs` ADR sections.
4. **The CLAUDE.md chain** for every touched file — walk each changed file's directory up to the repo root collecting `CLAUDE.md`, plus that service's root `CLAUDE.md`, the repo-root `CLAUDE.md`, any `.claude/rules/*.md`, and the nearest `GLOSSARY.md`. This chain is the rulebook the `claude-md-compliance` concern checks against.

## Concerns (7)

One subagent per concern, all spawned in a **single message** as parallel `Agent` calls (`subagent_type: general-purpose`). Each prompt is self-contained: the concern's checklist (below, verbatim), the resolved paths from "What the review reads", and the findings contract. Concerns may overlap a line — dedup handles it.

| Concern | Asks | Default subagent reads |
|---|---|---|
| `claude-md-compliance` | Does the diff violate any **documented** rule in the applicable CLAUDE.md chain / rules / glossary? | diff + CLAUDE.md chain |
| `spec-fidelity` | Is it **truly done** — every `## Acceptance` bullet satisfied, every cited seam implemented, every `## Produces` anchor real, no requirement silently dropped? | diff + contract + PRD/SDD |
| `logic-correctness` | Works for all reasonable inputs? Bugs, edges, null-handling, error paths, races. | diff (+ repo for context) |
| `code-quality` | Smell / anti-pattern / "a senior dev wouldn't do this." Dead code, duplication, god methods, leaky abstractions, naming, magic values, debug logs, hardcoded secrets/tokens, TODO left in. | diff |
| `test-veracity` | Do the new tests assert what matters — the framework's **real output**, not the DTO; not tautological; cover the acceptance, not just the happy path; use the Nakisa test helpers? | diff + contract |
| `scope-and-impact` | Stayed inside `## Scope` globs, no forbidden patterns, no scope creep, no stray churn — **and** what's the blast radius of the changed symbols? | diff + contract + repo |
| `refactor-safety` | Did the implementor touch **pre-existing** code — rename, re-signature, extract/move, edit a shared base/util/DTO — and is each medium/high-risk change behaviour-preserving, fully propagated, and warranted? | diff + repo |

**Default `class` per concern** — each subagent stamps `class` on its findings so the caller's Step 10 routing is deterministic: `claude-md-compliance`→`compliance`, `spec-fidelity`→`spec`, `logic-correctness`→`correctness`, `code-quality`→`smell`, `test-veracity`→`test`, `scope-and-impact`→`scope` (but a genuinely broken direct caller is `correctness`), `refactor-safety`→`correctness` or `scope` per its rule below. A cross-class finding takes the class that drives the right fix (correctness/spec → `/afk:fix`; compliance/smell/scope/test → inline).

### Checklists

**`claude-md-compliance`** — load the resolved CLAUDE.md chain; for each documented rule, check the diff for a violation. The house landmines that recur in this repo (flag any the diff trips):
- `@Transactional(rollbackFor=…)` must be repeated on **every** override, not just the base — a subclass override that calls `super.x()` bypasses the proxy and silently commits on a checked exception.
- Cost Center and Profit Center must be sourced as a **pair** from one source — never mixed.
- **Never** hand-write `UpgradeGroup_*.java`, `PreDbMigration`, or `db/changelog/*`; add JPA `@Entity` classes and let liquibase-hibernate7 pick them up. An `@Entity` in the diff with no passing pickup is a violation.
- Jackson 3 / SB4: a new enum needs `@Skip` or `@GenerateEnumSwaggerSchema`; `@JsonDeserialize` annotations live under `tools.jackson.databind.annotation`; a `@Builder` DTO without `@NoArgsConstructor` breaks J3 creator visibility.
- `*-ui` npm deps must be ≥30 days old and **exact-pinned** (incl. transitive) — no carets/tildes, no fresh-published versions.
- Code touching tenant/security context in tests must use the Nakisa helpers (`@WithTenantContext`, `@WithSimpleSecurityContext`, `@WithDevTokenSecurityContext`) — plain JUnit setup fails.
- The access boundary to verify is **company and/or vendor**, not tenant (build-per-tenant = single-tenant at runtime).
- Match `eclipse-code-formatter.xml`; don't reformat untouched lines.
- Cross-module edits (outside the home module) carry a `// {TICKET-ID}:` marker comment in the added hunks.
- Commits start with `[{NNNN-slug}]`.
- Any rule stated in a service/sub-package `CLAUDE.md` that the diff contradicts — quote the rule and the offending line.

**`spec-fidelity`** — walk every `## Acceptance` bullet and find the diff line(s) that satisfy it; an unsatisfied or partially-satisfied bullet is a finding (severity by how load-bearing). In cited mode, every SDD §9b seam this subtask `implement:`s must be present and assert on the framework's real output. Every `## Produces` `{grep-anchor}` must resolve in the diff. Flag silent scope-shrink: an acceptance bullet "handled" by a stub, a `TODO`, or a swallowed branch is **not** done.

**`logic-correctness`** — the bug-hunt lens. Boundary values, empty/null/missing inputs, error and rollback paths, off-by-one, concurrency/ordering, integer/decimal precision (BigDecimal for money), partial-failure handling. Cite `file:line`; give a concrete failing input.

**`code-quality`** — the senior-review lens. Dead/commented-out code, copy-paste duplication, methods doing too much, primitive obsession, leaky/ misplaced abstractions, unclear names, magic numbers/strings, swallowed exceptions, `System.out`/debug logging left in, hardcoded credentials/tokens/URLs, stray `TODO`/`FIXME`. Not style nits the formatter owns — substance.

**`test-veracity`** — does the test prove the behaviour? A seam test must assert on the framework's **real** serialized output, not echo the DTO back. Flag tautological asserts (`assertEquals(x, x)`), asserts on mocks instead of results, happy-path-only coverage of a multi-branch acceptance bullet, missing negative/authz cases, and the repo's ApprovalTests `JsonApprovals.verifyJson(capturedSaveArg)` pattern where a hand-rolled field-by-field assert was used instead.

**`scope-and-impact`** — confirm every changed path matches a `## Scope` glob (out-of-scope file = finding), no forbidden pattern (liquibase/UpgradeGroup), no unrelated churn (stray `package-lock.json` reflow, formatter-only diffs in untouched files). Then assess blast radius: for each changed public symbol (method/class signature, REST path, DTO field, event), search the repo for its callers/consumers (`Grep` the symbol name across the affected module + its `*-client`/`*-entities` siblings) and surface any caller the diff changed the contract for but did **not** update or cover with a test as a finding. A changed `*-client` DTO or endpoint signature with downstream consumers in other services is high severity.

**`refactor-safety`** — separate the **net-new** code from changes to **pre-existing** code; the latter is refactoring and carries behaviour-preservation risk that green tiers don't catch (the existing tests may have moved with the code). Identify each refactor in the diff — symbol/file rename, signature or return-type change, extracted/inlined method, logic moved between classes/modules, edits to a **shared base class / util / `*-client` DTO / `*-entities` / state-machine**, reworked control flow in an existing method, changed defaults or data structures — and rate its risk as blast radius × behaviour-change potential × test coverage:
- **high** — a medium/high-blast refactor (base class, widely-called helper, cross-service `*-client` contract, or any symbol with callers outside the home module) with **no characterization/regression test** proving behaviour is preserved; or a signature/rename whose call sites are not **all** updated (`Grep` the old name — a stray hit is a break).
- **medium** — an in-module refactor that reworks behaviour-bearing code with thin coverage; or an **opportunistic** refactor outside the subtask's `## Goal`/`## Scope` (risk *and* scope creep — even if it reads cleaner, it shouldn't ride this slice; it belongs in its own change).

Route findings by cause: behaviour-preservation risk → `class: correctness` (needs a behaviour-pinning test before the refactor is trusted — the `/afk:fix` path); unnecessary / out-of-scope refactor → `class: scope` (trim it out or split it into its own subtask). A refactor reaching into **another team's module** (other `11xxx`, or `16xxx`–`19xxx`) raises severity and must carry the `// {TICKET-ID}:` marker comment plus a reviewer note — flag its absence. When a refactor renames/moves a symbol, every call site must change in lockstep — a partial rename is high severity, not a nit.

## Findings contract

Each subagent returns a JSON array; the orchestrator merges, dedups by `file:line` (keep highest severity, union the `concern` list), assigns ids `r-001..r-NNN`, and ranks most-severe first.

```json
{
  "id": "r-001",
  "concern": "claude-md-compliance",
  "severity": "critical|high|medium|low",
  "class": "correctness|spec|compliance|smell|scope|test",
  "file": "11700-payable/.../Foo.java",
  "line": 42,
  "finding": "One-line headline.",
  "why": "One sentence — the rule broken / input that fails / requirement missed.",
  "fix": "One-line remediation.",
  "evidence": "Quoted rule text or the diff line."
}
```

`class` drives how the caller remediates (correctness/spec → diagnose-backed fix; compliance/smell/scope/test → inline fix). Severity rubric:

- **critical** — ships a wrong result, data corruption, security/authz hole, or violates a "Never …" hard rule.
- **high** — an acceptance bullet unmet, a documented rule broken, a real bug on a reachable path, a broken direct caller.
- **medium** — smell / weak test / missing negative case / convention drift that a reviewer would block on but isn't load-bearing.
- **low** — nit, optional improvement.

## Verdict & output

Write the full report to `plan/review/{NNNN-slug}-{base-short}.md` (human-readable, ranked) and the machine list alongside as `…-{base-short}.findings.json`. End with one line the caller parses:

```
REVIEW: <verdict> — crit=<n> high=<n> med=<n> low=<n> [findings: <path>]
```

| Verdict | When | Caller (gate mode) |
|---|---|---|
| `clean` | zero findings | proceed to `done` |
| `advisory` | only `medium`/`low` | note them in MR + Implementation Notes; proceed to `done` |
| `blocking` | any `critical`/`high` | gate per `/afk:execute` Step 10 (auto-fix loop, ≤2 cycles, then `review_fail`) |

Standalone mode stops here — print the verdict and the report path; gate nothing.

## Hard rules

- **Read-only.** Never edit, commit, push, or fix. This skill finds; the caller (or `/afk:fix`) remediates.
- **Independence.** Reviewer subagents get the diff, contract, spec, and CLAUDE.md chain — **never** the implementor's chat or rationale. A reviewer that's told "the author says this is fine" isn't a reviewer.
- **Cite or drop.** Every finding carries `file:line` and quoted evidence (the rule text, the failing input, the unmet acceptance bullet). No vibes-only findings; if unsure of the line, cite the hunk header.
- **Parallel fan-out, single message.** Spawn all concern subagents at once; never sequential.
- **Don't re-run the build or tests.** Tiers are already green at the gate; this is static review — read the diff and search the repo for callers; don't compile or run.
- **No new contract sections.** This skill only *reads* the plan; it owns no PLAN.md cell and no Implementation-Notes block. The caller records outcomes.

## See also

- `skills/afk/execute/SKILL.md` Step 10 — the gate that invokes this and acts on the verdict.
- `skills/afk/fix/SKILL.md` — where execute routes a `correctness`/`spec` blocking finding (diagnose-backed fix + regression test).
- The plugin `CLAUDE.md` — Section ownership invariants + the outcome-status lockstep.
