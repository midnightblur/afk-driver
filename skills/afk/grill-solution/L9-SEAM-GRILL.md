# L9 — Implementation seams & change impact (grill after L8)

L1–L8 settle *what* the design is; L9 proves it **fits the code that exists**. A design can pass every layer and still land on a seam whose real signature, guarded path, or house convention contradicts it — that contradiction must surface here, while it costs a conversation, not mid-implementation.

## Part 1 — the seam walk

For every point where the design touches existing code (calls it, extends it, is called by it, shares its data):

1. **Signature/contract alignment.** Read the actual class/method/DTO the design assumes. Does the assumed call shape exist — parameters, return type, checked exceptions, nullability, transactional posture? A mismatch is a design change or an ADR-worthy extension, never a "the executor will adapt it".
2. **Change impact.** Who else uses the seam (callers, listeners, mappers, generated companions)? Which of those flows change behaviour? Every impacted flow is named — "none" is a claim to verify, not assume.
3. **House conventions.** The CLAUDE.md chain governing that code area binds the design: class-placement contracts, base-service chains, state-machine wiring, mapper/codegen rules, scoping/authz layers. A design step that violates one is reworked or gets an explicit exception ADR.
4. **Must-do landmines.** What does the existing entry path (controller/listener/job) do that the design's new path would skip — validation, authz guards, events, auditing, balance/state bookkeeping? Every skipped obligation is either re-established on the new path or explicitly ruled out with rationale.

Record each seam as a row: `seam | existing contract (verified where) | planned change | impacted flows | conventions/landmines | verdict`, where `verdict` ∈ `fits` | `extends (ADR-NNNN)` | `reworked` (lockstep with SDD §14 — same columns, same enum). These rows are the input for the SDD's §14 table.

## Part 2 — parallel compatibility audit

After the seam walk, fan out **read-only audit subagents — one per touched module or load-bearing pattern** (e.g. one for the owning service module, one per cross-module seam, one per framework pattern the design leans on). Each gets: the settled design summary (decisions + seam rows for its area) — not the conversation — and this brief:

> Attack this design against the code you can read. Where does it contradict an existing invariant, pattern, contract, or convention in your area? What existing behaviour would it silently change? What does it assume that the code refutes? Report findings with file evidence; report nothing you cannot cite.

Findings return to the grill as challenges: each is **resolved** (design adjusted, layer re-grilled if needed) or **explicitly accepted** (with rationale, ADR-worthy if it clears the bar). An unaddressed audit finding means L9 is not exhausted.

## Exit criteria

- Every seam has a row with a verified existing contract and a verdict.
- Every landmine has a re-established obligation or an explicit rule-out.
- Every audit finding resolved or accepted with rationale.
