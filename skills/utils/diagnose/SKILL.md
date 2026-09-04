---
name: diagnose
description: "Disciplined diagnosis loop: reproduce → minimise → hypothesise → instrument → fix → regression-test. Use when the user reports a bug, says something is broken/failing, or describes a performance regression."
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# Diagnose

A discipline for hard bugs. Skip phases only when explicitly justified.

**Be certain before you fix.** A fix on a wrong diagnosis wastes the fix *and* buries the bug deeper. Don't edit code to "try" a fix until the loop has **confirmed** the cause. Exhaust every tool below first — a guess is a last resort, taken only after you've said so explicitly and stated your confidence.

When exploring the codebase, use the project's domain glossary for a clear mental model of the relevant modules, and check ADRs in the area you're touching.

## Phase 1 — Build a feedback loop

**This is the skill.** Everything else is mechanical. A fast, deterministic, agent-runnable pass/fail signal for the bug → you will find the cause; bisection, hypothesis-testing, and instrumentation all just consume that signal. Without one, no amount of staring at code will save you.

Spend disproportionate effort here. **Be aggressive. Be creative. Refuse to give up.**

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

Bulk executions inside the loop (failing-suite runs, builds, instrumented runs with long logs) run via an `afk-runner` subagent that returns only the distilled observations — the decisive lines, cited — per `DELEGATION.md` (plugin root); the hypothesise → instrument → conclude reasoning stays inline, because each decision needs the previous step's texture.

### Tools at your disposal

*The repository names its own instruments — its `CLAUDE.md` and its `setup.extra` files. Read those first; the classes below say what to look for.*

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

Stop and say so explicitly. List what you tried. Ask the user for: (a) access to whatever environment reproduces it, (b) a captured artifact (HAR file, log dump, core dump, screen recording with timestamps), or (c) permission to add temporary production instrumentation. Do **not** hypothesise without a loop.

Do not proceed to Phase 2 until you have a loop you believe in.

## Phase 2 — Reproduce

Run the loop. Watch the bug appear.

Confirm:

- [ ] The loop produces the failure mode the **user** described — not a different failure that happens to be nearby. Wrong bug = wrong fix.
- [ ] The failure is reproducible across multiple runs (or, for non-deterministic bugs, reproducible at a high enough rate to debug against).
- [ ] You have captured the exact symptom (error message, wrong output, slow timing) so later phases can verify the fix actually addresses it.
- [ ] For a UI-visible bug, you reproduced it **in the running app** (live build) — not only at a code seam. A green seam over a broken UI means you reproduced the wrong thing.

Do not proceed until you reproduce the bug.

## Phase 3 — Hypothesise

Generate **3–5 ranked hypotheses** before testing any. Single-hypothesis generation anchors on the first plausible idea.

Each hypothesis must be **falsifiable**: state its prediction.

> Format: "If <X> is the cause, then <changing Y> will make the bug disappear / <changing Z> will make it worse."

Can't state the prediction → the hypothesis is a vibe; discard or sharpen it.

**Show the ranked list to the user before testing.** They often have domain knowledge that re-ranks instantly ("we just deployed a change to #3"), or know hypotheses already ruled out. Cheap checkpoint, big time saver. Don't block on it — proceed with your ranking if the user is AFK.

## Phase 4 — Instrument

Each probe must map to a specific prediction from Phase 3. **Change one variable at a time.**

Tool preference:

1. **Debugger / REPL inspection** if the env supports it (IntelliJ MCP, when connected, gives you this against a running service). One breakpoint beats ten logs.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. Never "log everything and grep".

**Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`. Cleanup becomes a single grep. Untagged logs survive; tagged logs die.

**Perf branch.** For performance regressions, logs are usually wrong. Instead: establish a baseline measurement (timing harness, `performance.now()`, profiler, query plan), then bisect. Measure first, fix second.

## Phase 5 — Fix + regression test

Write the regression test **before the fix** — but only if a **correct seam** exists for it.

A correct seam is one where the test exercises the **real bug pattern** as it occurs at the call site. If the only available seam is too shallow (single-caller test when the bug needs multiple callers, unit test that can't replicate the chain that triggered the bug), a regression test there gives false confidence.

**If no correct seam exists, that itself is the finding.** Note it — the codebase architecture is preventing the bug from being locked down. Flag for the next phase.

If a correct seam exists:

1. Turn the minimised repro into a failing test at that seam.
2. Watch it fail.
3. Apply the fix.
4. Watch it pass.
5. Re-run the Phase 1 feedback loop against the original (un-minimised) scenario.

## Phase 6 — Cleanup + post-mortem

Required before declaring done:

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop)
- [ ] Regression test passes (or absence of seam is documented)
- [ ] All `[DEBUG-...]` instrumentation removed (`grep` the prefix)
- [ ] Throwaway prototypes deleted (or moved to a clearly-marked debug location)
- [ ] For a UI-visible bug, the fix was confirmed **in the running UI** (re-mint token, re-drive the app) — not only by the test seam
- [ ] The hypothesis that turned out correct is stated in the commit / PR message — so the next debugger learns

**Then ask: what would have prevented this bug?** If the answer involves architectural change (no good test seam, tangled callers, hidden coupling), hand off to the `/improve-codebase-architecture` skill with the specifics if available; otherwise record the recommendation in the diagnosis notes. Make the recommendation **after** the fix is in, not before.
