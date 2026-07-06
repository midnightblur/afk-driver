---
name: tdd
description: Test-driven development with the red-green-refactor loop. Use when implementing features or fixes test-first, when the user mentions TDD, red-green-refactor, or integration-style tests, or when a caller mandates test-driven implementation.
user-invocable: false
---

# Test-Driven Development

## Philosophy

**Core principle**: tests verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't.

**Good tests** are integration-style — exercise real code paths through public APIs:

- Verify behavior through public interface, not implementation — describe _what_ the system does, not _how_.
- Survive refactors → don't care about internal structure.
- **Bad tests** couple to implementation: mock internal collaborators, test private methods, or verify through external means (e.g. querying a database directly instead of using the interface).

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.

## Anti-Pattern: Horizontal Slices

**DO NOT write all tests first, then all implementation.** That's "horizontal slicing" — treating RED as "write all tests" and GREEN as "write all code."

Produces **Bad tests**:

- Bulk-written tests test _imagined_ behavior, not _actual_ behavior
- You test the _shape_ of things (data structures, function signatures) rather than user-facing behavior
- Tests go insensitive to real changes — pass when behavior breaks, fail when behavior is fine
- You outrun your headlights, committing to test structure before understanding the implementation

**Correct approach**: vertical slices via tracer bullets. One test → one implementation → repeat. Each test responds to what the previous cycle taught you. Because you just wrote the code, you know exactly what behavior matters and how to verify it.

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

When exploring the codebase, use the project's domain glossary so test names and interface vocabulary match the project's language, and respect ADRs in the area you're touching.

Before writing any code:

- [ ] Confirm what interface changes are needed
- [ ] Confirm which behaviors to test (prioritize)
- [ ] Identify opportunities for deep modules — small interface, deep implementation: few methods, simple params, complexity hidden inside. Avoid shallow modules (large interface, thin pass-through implementation).
- [ ] Design interfaces for testability: accept dependencies instead of creating them inside; return results instead of producing side effects; keep the surface small (fewer methods and params = simpler tests).
- [ ] List behaviors to test (not implementation steps)
- [ ] Get the plan approved

**Interactive runs**: the user is the approver. Ask: "What should the public interface look like? Which behaviors are most important to test?" — and get explicit approval on the plan before coding. **You can't test everything** — confirm with the user exactly which behaviors matter most; focus testing effort on critical paths and complex logic, not every possible edge case.

**When a subtask contract drives the work** (non-interactive): the contract's `## Acceptance` bullets ARE the approved behavior list and its `## Verification` tiers ARE the approved green-bar checks; interfaces fixed by the contract or its design refs count as confirmed. Proceed without asking anyone — there is no human gate.

### 2. Tracer Bullet

Write ONE test that confirms ONE thing about the system:

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

```
[ ] Test describes behavior, not implementation
[ ] Test uses public interface only
[ ] Test would survive internal refactor
[ ] Code is minimal for this test
[ ] No speculative features added
```

## Done

Terminal condition: every planned behavior has a green test, the refactor pass (step 4) has run, and the full suite for the touched module is green.
