# code-quality — implementation-level smells

The senior-review lens, line-by-line on the diff. Default `class: smell`; hardcoded secrets → `correctness`, severity `critical`. Baseline items follow PRECEDENCE.md.
**Not yours:** module shape (middle man, shotgun surgery, speculative generality, flag args) → `design-quality`; names vs domain glossary → `domain-alignment`; unbounded queries/N+1 → `resilience`; anything in test code → `test-veracity`.

## Reviewer checklist

Naming & duplication:
- **Mysterious Name** (Fowler) — new symbol needing its body read to understand; a name that lies about side effects (`get` that creates, `find` that mutates) → rename honestly; no honest name = wrong shape, say so.
- **Duplicated knowledge** (Fowler) — the same rule/logic shape in two hunks, or a near-copy of an existing repo helper → extract, or call the existing one. Incidental textual similarity between different intents is NOT duplication — don't flag it.
- **Feature Envy** (Fowler) — new method interrogating another object's getters more than its own state → move the method onto the data it envies.
- **Data Clumps / Primitive Obsession** (Fowler) — the same field/param group travels together again; a String/BigDecimal pair standing in for a concept the codebase already types → introduce or reuse the value type.
- **Repeated Switch** (Fowler) — a second `switch`/if-cascade over the same type-code appears in the change → polymorphism, or one map both sites share.
- **Message Chain** (Fowler) — new `a.getB().getC().getD()` across objects *with behaviour* → hide the walk behind one method. Pure DTO/record navigation is exempt.

Immutability & exposure:
- **Mutable where immutable meant** (EJ-17) — new class with setters nothing calls, fields that could be final, a record candidate written as a bean → make it immutable.
- **Leaked internals** (EJ-15, EJ-50) — mutable collection/date returned or stored without a defensive copy; wider visibility than the one caller needs → copy at the boundary, minimize access.
- **Null discipline** (EJ-54, EJ-55) — internal method returns a null collection; Optional as field/param or `get()` unguarded → empty collections; Optional only as a return type.

Failure handling:
- **Exceptions as control flow** (EJ-69) — catch steering expected logic → a conditional.
- **Swallowed or blurred failure** (EJ-77) — empty/log-only catch on a path the caller must know about; `catch (Exception)` hiding specific causes; failure exiting with the object half-mutated → rethrow at the right abstraction; keep failure atomic.
- **Barricade breach** (CC2) — external input (request, file, message, remote response) consumed without validation at the perimeter — or paranoid re-validation noise deep inside already-trusted code → validate at the boundary, trust inside it.

Local hygiene:
- **Variable double-duty** (CC2) — one variable serving two meanings; a flag that is also an index; init far from first use → one purpose per variable, declare at first use.
- **Deep nesting** (CC2) — new conditional nesting >3 levels → guard clauses, extraction, or a table-driven map.
- **Hand-rolled library** (EJ-59) — reimplementing what the JDK or the repo's dependency set already provides (joins, retries, date math) → use the library.
- **Comment deodorant** (Fowler) — new comment explaining *what* confusing code does, or repeating it → fix the code; keep only why/non-obvious comments. Never flag a comment's *presence*.
- **Debug artifacts** — `System.out`/`printStackTrace`, commented-out code, dead code, ownerless `TODO`/`FIXME` in the diff → delete.
- **Hardcoded secrets/config** — credentials, tokens, host URLs, environment assumptions baked into code → config/secret store. This one is `class: correctness`, `critical`.

Calibration (contested items — do not flag):
- Function-length and parameter-count numerology — tooling territory; flag only when the length genuinely obscures one readable intent.
- Over-fragmentation is as flaggable as length: a cloud of 3-line private methods each read once is a shallow-module problem (report the fragmentation, not "long method").
- Imperative loop vs stream — style preference, skip.
