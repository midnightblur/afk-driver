# afk:execute — Cited mode (additional steps)

These steps, the Conflict procedure, and the extra OUTCOME statuses apply **only**
in Cited mode (non-empty `## Design refs` + a `## Parent SDD`). They extend the
standard workflow in [SKILL.md](SKILL.md); the step numbers below match the
corresponding steps there. The non-cited workflow in [SKILL.md](SKILL.md) is
complete on its own — run these in addition when the subtask is in Cited mode.

## Step 1 — design/contract reconciliation (cited mode)

   **Cited mode** (non-empty `## Design refs` + a `## Parent SDD`): the SDD/ADRs
   constrain you.
   - Read every cited SDD section and ADR via `ctx_read` BEFORE planning.
   - Treat the SDD §8 public interface and the cited ADR patterns as **frozen** —
     no invented signatures, no silent pattern substitution.
   - Treat the `## Seams` rows as binding: a seam you `implement:` you also
     test (its seam-test is a `## Verification` row); a seam you `use:` you call
     across without changing its contract.
   - Executor latitude is below the line: file/package layout within the module,
     private helpers, internal naming, test fixtures, library call shape.
   - **Materialized seams** (a `## Produces` bullet ending `[materialized]`):
     the stub and its `{Seam}ContractTest` already sit on the branch and are the
     binding starting point — fill the stub, **enable** the contract test (drop
     its `@Disabled`) and turn it green as your seam-test Verification row.
     Never re-declare the type elsewhere or leave the stub as a parallel copy.

## Step 2 — Preflight: verify Consumed contracts (cited mode)

2. **Preflight: verify Consumed contracts (cited mode).** If `## Consumes` is
   non-empty, every line is `{PRODUCER-ID} {file-path}#{grep-anchor} —
   {description}`. For each:
   - `ctx_read` `{file-path}` (relative to the worktree root). Missing file →
     the producer hasn't landed what it promised → stop with `contract_mismatch`
     (carry `{PRODUCER-ID}`) **before any other work** — no status change, no
     commits, no verification runs.
   - `ctx_search` `{grep-anchor}` in `{file-path}`. Absent → producer drifted →
     same `contract_mismatch`.
   - Lines marked `[materialized]` get the compiler on top of the grep: run
     `./mvnw -f all-modules-pom.xml -pl {module-of-file-path} --also-make
     test-compile -DskipUi=true` once (covering all such lines in that module).
     A compile failure in the seam surface (the consumed type or its
     `{Seam}ContractTest`) → `contract_mismatch` — the compiler caught a
     signature drift the anchor string couldn't.
   - Quote the offending bullet verbatim. **Do not retry, do not auto-correct the
     producer.** A `contract_mismatch` halts on purpose: the producer must be
     fixed (re-run it or emit a corrective subtask) first. Record the break in
     **both** subtask files' `## Implementation Notes` and set both rows in
     PLAN.md to `blocked(contract_mismatch: …)`.

## Step 6 — Honor `## Produces` (cited mode)

   **Honor `## Produces` (cited mode).** Every declared artifact must exist on
   the branch by success. Step 9 greps every declared anchor right before the
   success exit and aborts with `produces_drift` if any are missing — drifting
   from your own declared contract is not survivable mid-session. If the declared
   signature turns out wrong, that's a `design_conflict`, not a license to change
   it silently.

## Step 9 — Producer self-preflight on `## Produces` (cited mode)

9. **Producer self-preflight on `## Produces` (cited mode).** Before declaring
   success, verify every artifact you declared lands on the branch. For each
   `{file-path}#{grep-anchor} — {contract}`:
   - `ctx_read` `{file-path}`; missing → `produces_drift`, quote the bullet, do
     not retry or amend silently.
   - `ctx_search` `{grep-anchor}`; absent → implementation diverged from the
     declared signature → `produces_drift`.
   - **Materialized seams.** For each own `## Produces` bullet marked
     `[materialized]`: its `{Seam}ContractTest` must be **enabled** — a
     surviving `@Disabled("seam pending …")` on it is `produces_drift` (the
     seam-test Verification row can't have legitimately gone green while
     disabled; name the test file).
   - **JPA-entity pickup (core-services Java).** If `{file-path}` ends `.java`
     and contains `@Entity` / `@MappedSuperclass` / `@Embeddable`: a
     class-declaration grep hit is necessary but not sufficient. Confirm the
     class's package is reachable from the module's entity-scan config
     (`@EntityScan` / `entityPackages` / `hibernate.archive.autodetection`), then
     run the documented liquibase-hibernate7 pickup check (the subtask's
     integration-tier `## Verification` row) and inspect the generated diff — if
     it does not mention the new entity/column/table, the plugin isn't picking it
     up → `produces_drift`, naming the entity and the empty diff path.

   This is symmetric to Step 2's consumer-side preflight; without it, signature
   drift surfaces only at the next consumer — on the wrong subtask.
   `produces_drift` ("I didn't deliver the contract I declared, fix impl or
   re-slice") is **not** `design_conflict` ("the binding contract is wrong, route
   to grill-solution"). Pick the right one.

## Conflict procedure (cited mode)

If the subtask has a `## Conflict procedure` block, follow it verbatim on a
binding-contract violation. The canonical flow:

1. Stop coding the moment you realize the SDD/ADR mandate is unimplementable or
   contradicts reality. Don't paper over it.
2. Stage no code; commit nothing under the conflict.
3. Report `design_conflict` quoting the SDD section + the conflict, and set the
   tracker row to `blocked(design_conflict: …)`.
4. Note it in the subtask's Implementation Notes and run `/afk:grill-solution`
   for a superseding ADR before re-running.

**Do NOT silently override the SDD/ADR.** Substituting a different pattern or
interface breaks the binding contract and produces work other subtasks can't
integrate with.

## Cited-mode OUTCOME statuses

These extend the OUTCOME status list in [SKILL.md](SKILL.md) Step 13:

- `design_conflict` — cited mode. A binding SDD/ADR decision is wrong,
  infeasible, or contradicts reality. Name the SDD section / ADR + the
  concrete conflict; route the human to `/afk:grill-solution` for a
  superseding ADR before re-running.
- `contract_mismatch` — cited mode. Step 2: an upstream `## Produces`
  artifact is missing or its anchor doesn't appear. Name the `{PRODUCER-ID}`
  and quote the bullet; record on both subtask files.
- `produces_drift` — cited mode. Step 9: one of THIS subtask's own
  `## Produces` anchors doesn't appear in its file. Quote the bullet. Fix the
  impl OR re-emit the slice with a corrected `## Produces`.
