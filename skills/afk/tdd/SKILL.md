---
name: tdd
description: Runs the red-green-refactor TDD loop. Use when implementing test-first, or when a caller mandates it.
user-invocable: false
---

# Test-Driven Development

## Philosophy

**Core principle**: tests verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't.

**Good tests** are integration-style — exercise real code paths through public APIs:

- Verify behavior through public interface, not implementation — describe _what_ the system does, not _how_.
- Survive refactors → don't care about internal structure.
- **Bad tests** couple to implementation — red-flag lists + examples: [tests.md](tests.md); mocking boundaries: [mocking.md](mocking.md).

## Anti-Pattern: Horizontal Slices

**DO NOT write all tests first, then all implementation** — bulk-written tests test _imagined_ behavior and go insensitive to real changes; instead work vertical slices via tracer bullets: one test → one implementation → repeat, each test informed by what the last cycle taught.

```
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

RIGHT (vertical):
  RED→GREEN: test1→impl1
  RED→GREEN: test2→impl2
  RED→GREEN: test3→impl3
  ...
```

## Workflow

### 1. Planning

When exploring the codebase, use the project's domain glossary so test names and interface vocabulary match the project's language; respect ADRs in the area you're touching.

Before writing any code:

- [ ] Confirm what interface changes are needed
- [ ] Confirm which behaviors to test (prioritize)
- [ ] Identify opportunities for deep modules — small interface, deep implementation: few methods, simple params, complexity hidden inside. Avoid shallow modules (large interface, thin pass-through implementation).
- [ ] Design interfaces for testability: accept dependencies instead of creating them inside; return results instead of side effects; keep the surface small (fewer methods and params = simpler tests).
- [ ] List behaviors to test (not implementation steps)
- [ ] Get the plan approved

**Interactive runs**: the user is the approver. Ask: "What should the public interface look like? Which behaviors are most important to test?" — confirm priority behaviors with the user before coding.

**When a subtask contract drives the work** (non-interactive): the contract's `## Acceptance` bullets ARE the approved behavior list and its `## Verification` tiers ARE the approved green-bar checks; interfaces fixed by the contract or its design refs count as confirmed. Proceed without asking — no human gate.

### 2. Tracer Bullet

Write ONE test confirming ONE thing about the system:

```
RED:   Write test for first behavior → test fails
GREEN: Write minimal code to pass → test passes
```

Your tracer bullet — proves the path works end-to-end.

### 3. Incremental Loop

For each remaining behavior:

```
RED:   Write next test → fails
GREEN: Minimal code to pass → passes
```

Rules:

- One test at a time
- Only enough code to pass current test
- Don't anticipate future tests
- Keep tests focused on observable behavior

### 4. Refactor

After all tests pass, look for refactor candidates:

- [ ] Duplication → extract function/class
- [ ] Long methods → break into private helpers (keep tests on the public interface)
- [ ] Shallow modules → combine or deepen (move complexity behind simple interfaces)
- [ ] Feature envy → move logic to where the data lives
- [ ] Primitive obsession → introduce value objects
- [ ] Existing code the new code reveals as problematic
- [ ] Apply SOLID principles where natural
- [ ] Run tests after each refactor step

**Never refactor while RED.** Get to GREEN first.

## Checklist Per Cycle

Each cycle: test meets the good-test bars ([tests.md](tests.md) Characteristics); code minimal for this test, nothing speculative (§3 rules).

## Done

Terminal condition: every planned behavior has a green test, the refactor pass (step 4) has run, and the full suite for the touched module is green.
