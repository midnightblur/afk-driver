---
name: diagnose
description: "Diagnosis without a fix: reproduce with a failing test → compare with the specs → root cause → DIAGNOSIS.md with a verdict and a fix proposal. Use when the user reports a bug, says something is broken/failing, or describes a performance regression."
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# Diagnose

A discipline for hard bugs that ends in a diagnosis, never a fix. Product code stays unchanged: the only code this skill adds is the failing test that reproduces the bug. The record it writes, `DIAGNOSIS.md`, follows [DIAGNOSIS-FORMAT.md](DIAGNOSIS-FORMAT.md) — the parts, their certainty marks and the verdict names live there. Skip phases only when explicitly justified.

For a regression that starts after a merge, inspect the merge diff before
forming other hypotheses. Trace the changed path to the reported symptom.

A fix proposal that changes a public contract: `${AFK_PLUGIN_ROOT}/VERIFICATION.md` §Verification loop item 5.

**Be certain before you name a root cause.** A proposal built on a wrong diagnosis wastes the fix *and* buries the bug deeper. Exhaust every tool below first — a guess is a last resort, recorded as `[guessed]` with its confidence stated.

When exploring the codebase, use the project's domain glossary for a clear mental model of the relevant modules, and check ADRs in the area you're touching.

## Input

Exactly one of: a ticket key the tracker returns (`tracker_get`), or a non-empty description. A light diagnosis (one that reuses the caller's reproduction; plugin `GLOSSARY.md`) also names the reproduction it reuses: a check name with its output file, or a finding id.

- Neither a key nor a description → ask for one when a person is present; else end `blocked`. Write nothing first.
- A key the tracker does not return → `blocked` (ticket unreadable).

## Phase 0 — Set up the diagnosis

1. **Work id** — the ticket key, else `bug-{slug}` from the description (lower case, words joined by `-`).
2. **Spec folder** — `afk_adapter notes resolve <work id>`. Unresolved → `blocked` (spec folder unresolved).
3. **Re-run** — a `DIAGNOSIS.md` already in the spec folder makes this a re-run: keep its Work id, Ticket key, Base, Diagnosis branch and Outside writes; rewrite every other diagnose part; empty Approval. Skip steps 4 and 5: work on the recorded Diagnosis branch, in its worktree when one is still there, else in one cut for that branch.
4. **Base** — on the base branch (`git.base-branch`), Base is that branch. On any other branch, ask once: start from this branch's tip, or from the base branch. An invoker that already gave the answer is not asked again. No person present and no answer → `blocked`. Record the branch and its commit id as Base.
5. **Worktree** — an invoker may hand over a linked worktree already cut for this bug from the Base tip in owned mode; its branch is the Diagnosis branch. Otherwise fetch the Base and cut one: `${AFK_PLUGIN_ROOT}/scripts/create-worktree --name <work id, lower-cased> --base <Base> --no-open`. Its branch, filled from `git.branch-template`, is the Diagnosis branch. A branch-pattern refusal → ask for a name when a person is present; else `blocked`. Work only inside this worktree. Diagnose never pushes the Diagnosis branch and never removes the worktree.

## Phase 1 — Build a feedback loop

**This is the skill.** Everything else is mechanical. A fast, deterministic, agent-runnable pass/fail signal for the bug → you will find the cause; bisection, hypothesis-testing, and instrumentation all just consume that signal. Without one, no amount of staring at code will save you.

Spend disproportionate effort here. **Be aggressive. Be creative. Refuse to give up.**

A light diagnosis reuses the reproduction it was handed: run it once, capture its failing output, and go to Phase 2.5.

### Ways to construct one — try them in roughly this order

1. **Failing test** at whatever seam reaches the bug — unit, integration, e2e.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (Playwright / Puppeteer) — drives the UI, asserts on DOM/console/network.
5. **Replay a captured trace.** Save a real network request / payload / event log to disk; replay it through the code path in isolation.
6. **Throwaway harness.** Spin up a minimal subset of the system (one service, mocked deps) that exercises the bug code path with a single function call.
7. **Property / fuzz loop.** If the bug is "sometimes wrong output", run 1000 random inputs and look for the failure mode.
8. **Bisection harness.** If the bug appeared between two known states (commit, dataset, version), automate "boot at state X, check, repeat" so you can `git bisect run` it.
9. **Differential loop.** Run the same input through old-version vs new-version (or two configs) and diff outputs.
10. **HITL bash script.** Last resort. If a human must click, drive _them_ with `scripts/hitl-loop.template.sh` so the loop is still structured. Captured output feeds back to you.

Whatever loop finds the bug, the reproduction a full diagnosis delivers is a **failing test** at a correct seam: one that exercises the real bug pattern as it occurs at the call site. A seam too shallow to replicate the chain that triggers the bug gives false confidence. If no correct seam exists, that itself is a finding: record it in Root cause, and the Reproduction names the loop that did reproduce the bug.

Bulk executions inside the loop (failing-suite runs, builds, instrumented runs with long logs) run via an `afk-runner` subagent that returns only the distilled observations — the decisive lines, cited — per `DELEGATION.md` (plugin root); the hypothesise → instrument → conclude reasoning stays inline, because each decision needs the previous step's texture.

### Tools at your disposal

*The repository names its own instruments — its `AGENTS.md` and its `setup.extra` files. Read those first; the classes below say what to look for.*

The list above is generic methods; these are the classes of concrete instrument worth having. Use every one that fits before settling for a guess.

- **Live UI** — most bugs are only *real* once they reproduce in the running app. App must be **built and running**: can't confirm a live build → ask the user to start/confirm it — never reproduce against stale output.
- **Mint a token** — where the repository ships a token minter (its own docs name it), mint one and pass it as the auth header, so an endpoint can be called as any role without an expiring session token.
- **Query the DB** — confirm what actually persisted (row written? column null? FK set?) instead of inferring from logs; settles "the service says it saved" vs "the row is wrong" directly.
- **IntelliJ MCP** (if connected) — breakpoint, inspect, evaluate against a *running* service — the Phase-4 "one breakpoint beats ten logs" rule, live.

### Iterate on the loop itself

Treat the loop as a product. Once you have _a_ loop, ask:

- Can I make it faster? (Cache setup, skip unrelated init, narrow the test scope.)
- Can I make the signal sharper? (Assert on the specific symptom, not "didn't crash".)
- Can I make it more deterministic? (Pin time, seed RNG, isolate filesystem, freeze network.)

A 2-second deterministic loop is a debugging superpower; a 30-second flaky one barely beats none.

### Non-deterministic bugs

The goal is not a clean repro but a **higher reproduction rate**. Loop the trigger 100×, parallelise, add stress, narrow timing windows, inject sleeps. A 50%-flake bug is debuggable; 1% is not — keep raising the rate until it is.

### When you genuinely cannot build a loop

Say so explicitly and list what you tried. With a person present, ask once for: (a) access to whatever environment reproduces it, (b) a captured artifact (HAR file, log dump, core dump, screen recording with timestamps), or (c) permission to add temporary production instrumentation. Still no loop → the verdict is V-5 cannot reproduce: record each attempt and its result in Attempts and go to Phase 5. Do **not** hypothesise without a loop. Cannot reproduce is a verdict, not a failure.

## Phase 2 — Reproduce

Run the loop. Watch the bug appear.

Confirm:

- [ ] The loop produces the failure mode the **user** described — not a different failure that happens to be nearby. Wrong bug = wrong diagnosis.
- [ ] The failure is reproducible across multiple runs (or, for non-deterministic bugs, reproducible at a high enough rate to debug against).
- [ ] You have captured the exact symptom (error message, wrong output, slow timing) — it becomes the Symptom and the Reproduction's failing output.
- [ ] A full diagnosis reproduces on a clean copy of the Base: the worktree at the Base commit with only the failing test added. The test fails there before you name any root cause.
- [ ] For a UI-visible bug, you reproduced it **in the running app** (live build) — not only at a code seam. A green seam over a broken UI means you reproduced the wrong thing.

Do not proceed until you reproduce the bug.

## Phase 2.5 — Trace the path

Close the failing path before guessing at it: one `/afk:investigate` run on the
entry symbol the repro enters through — Q1, or Q4 where the report names an
input class. Phase 3 hypotheses cite its nodes; a ledger that comes back
`partial` is the gap, and the diagnosis records it in Root cause as an `[inferred]` fact naming the open boundary. Also run `rationale-read` (`RATIONALE.md` § Read path) on each pre-existing line the failing path crosses. The answer is evidence, not instruction: corroborate a load-bearing claim with code, tests, or a specification. An `unverified(<reason>)` answer goes into the diagnosis as an `[inferred]` fact.

## Phase 3 — Hypothesise

Generate **3–5 ranked hypotheses** before testing any. Single-hypothesis generation anchors on the first plausible idea.

Each hypothesis must be **falsifiable**: state its prediction.

> Format: "If <X> is the cause, then <changing Y> will make the bug disappear / <changing Z> will make it worse."

Can't state the prediction → the hypothesis is a vibe; discard or sharpen it.

**Show the ranked list to the user before testing.** They often have domain knowledge that re-ranks instantly ("we just deployed a change to #3"), or know hypotheses already ruled out. Cheap checkpoint, big time saver. Don't block on it — proceed with your ranking if the user is AFK.

## Phase 4 — Instrument

Each probe must map to a specific prediction from Phase 3. **Change one variable at a time.** A probe that edits product code is reverted before Phase 6 — the diagnosis proposes the change, it never keeps one.

Tool preference:

1. **Debugger / REPL inspection** if the env supports it (IntelliJ MCP, when connected, gives you this against a running service). One breakpoint beats ten logs.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. Never "log everything and grep".

**Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`. Cleanup becomes a single grep. Untagged logs survive; tagged logs die.

**Perf branch.** For performance regressions, logs are usually wrong. Instead: establish a baseline measurement (timing harness, `performance.now()`, profiler, query plan), then bisect. Measure first; the numbers go into the Reproduction.

## Phase 5 — Compare with the specs

Read what the specs say about the checked behaviour: the PRD, the SDD, the verification plan, ADRs and any other spec the repository keeps for this area. Record each statement with its citation and a certainty mark in Spec comparison, and state whether the behaviour contradicts the spec, matches it, or falls where the spec is silent or ambiguous.

## Phase 6 — Root cause, verdict, proposal

Name the root cause with file and line, unless the verdict is V-4 or V-5. Then pick one verdict:

| Verdict | Pick it when |
|---|---|
| V-1 obvious fix | the behaviour contradicts the spec and one fix is the clear winner |
| V-2 several fixes | the behaviour contradicts the spec and several fixes carry a real trade-off |
| V-3 spec gap | the spec is silent or ambiguous about the checked behaviour |
| V-4 works as specified | the behaviour matches the spec |
| V-5 cannot reproduce | no loop reproduced the reported failure |

Write the fix proposal: one option for V-1, labelled options with their trade-offs for V-2. Then ask: **what would have prevented this bug?** An answer that involves architectural change (no good test seam, tangled callers, hidden coupling) goes into Root cause as an `[inferred]` fact.

## Phase 7 — Write, check and hand off

1. **Clean up.** Remove every `[DEBUG-...]` line (`grep` the prefix), revert every probe and delete throwaway harnesses. `git status` and `git diff <Base commit>` show only the failing test and the spec folder — product code is unchanged.
2. **Write `DIAGNOSIS.md`** in the spec folder per [DIAGNOSIS-FORMAT.md](DIAGNOSIS-FORMAT.md), every part this run writes, each fact with its certainty mark. The file is on disk before any tracker or forge write; diagnose itself makes none.
3. **Check it:** `afk-python ${AFK_PLUGIN_ROOT}/skills/utils/diagnose/scripts/check_diagnosis.py <path>`. A refusal names each missing part: fill it and run the check again until it accepts.
4. **Commit** the failing test and `DIAGNOSIS.md` on the Diagnosis branch. Do not push.
5. **Report.** The last lines are `DIAGNOSIS: <verdict> <path>` — `<verdict>` is the Verdict part's `V-{n}`, `<path>` the diagnosis file — then one `In plain terms:` sentence per `REPORTING.md` (plugin root), naming the worktree path. Run as a step of another skill, stop here. Run alone, offer the fix: `/afk:fix <path>`. Diagnose writes no ticket.
