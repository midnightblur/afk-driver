# L9 — Implementation seams & change impact (grill after L8)

L1–L8 settle *what* the design is; L9 proves it **fits the code that exists**. A design can pass every layer and still land on a seam whose real signature, guarded path, or house convention contradicts it — that contradiction must surface here, while it costs a conversation, not mid-implementation.

## Part 1 — the seam walk

For every point where the design touches existing code (calls it, extends it, is called by it, shares its data), a seam row answers four checks:

1. **Signature/contract alignment.** Read the actual class/method/DTO the design assumes. Does the assumed call shape exist — parameters, return type, checked exceptions, nullability, transactional posture? A mismatch is a design change or an ADR-worthy extension, never "the executor will adapt it".
2. **Change impact.** Who else uses the seam (callers, listeners, mappers, generated companions)? Which of those flows change behaviour? Name every impacted flow — "none" is a claim to verify, not assume.
3. **House conventions.** The CLAUDE.md chain governing that code area binds the design: class-placement contracts, base-service chains, state-machine wiring, mapper/codegen rules, scoping/authz layers. A design step violating one is reworked or gets an explicit exception ADR.
4. **Must-do landmines.** What does the existing entry path (controller/listener/job) do that the design's new path would skip — validation, authz guards, events, auditing, balance/state bookkeeping? Every skipped obligation is re-established on the new path or explicitly ruled out with rationale.

**Gather in parallel, adjudicate in conversation.** Fan out read-only children — one per seam, or per module where seams cluster, per `DELEGATION.md` (plugin root) — each returning a **draft row**: file-cited evidence for all four checks plus a proposed verdict. The walk then spends conversation only where it's owed: a draft proposing `fits` with uncontradicted evidence is confirm-class (batch per `skills/afk/grill-requirements/TRIAGE.md`); a proposed `extends`/`reworked`, an evidence–design contradiction, or a live landmine is debate-class, one at a time. Spot-check citations before locking any row (`DELEGATION.md` return contract) — a draft is evidence, not a verdict.

Record each locked seam as a row: `seam | existing contract (verified where) | planned change | impacted flows | conventions/landmines | verdict`, where `verdict` ∈ `fits` | `extends (ADR-NNNN)` | `reworked` (lockstep with SDD §14 — same columns, same enum). These rows are the input for the SDD's §14 table.

## Part 2 — parallel compatibility audit

Fan out **read-only audit subagents — one per touched module or load-bearing pattern** (e.g. one for the owning service module, one per cross-module seam, one per framework pattern the design leans on), launching each as its area's seam rows lock — the audit overlaps the tail of the walk rather than following it. Each gets: the settled design summary (decisions + seam rows for its area) — not the conversation — and this brief; spawn mechanics and each auditor's return contract follow `DELEGATION.md` (plugin root):

> Attack this design against the code you can read. Where does it contradict an existing invariant, pattern, contract, or convention in your area? What existing behaviour would it silently change? What does it assume that the code refutes? Report findings with file evidence; report nothing you cannot cite.

Findings return to the grill as challenges: each is **resolved** (design adjusted, layer re-grilled if needed) or **explicitly accepted** (with rationale, ADR-worthy if it clears the bar). An unaddressed audit finding means L9 is not exhausted.

## Exit criteria

- Every seam has a row with a verified existing contract and a verdict.
- Every landmine has a re-established obligation or an explicit rule-out.
- Every audit finding resolved or accepted with rationale.
