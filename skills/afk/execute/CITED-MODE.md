# afk:execute — Cited mode (additional steps)

Apply **only** in Cited mode (non-empty `## Design refs` + a `## Parent SDD`); step numbers match [SKILL.md](SKILL.md), which is complete on its own without these.

## Step 1 — design/contract reconciliation (cited mode)

   **Cited mode** (non-empty `## Design refs` + a `## Parent SDD`): the SDD/ADRs
   constrain you.
   - Read every cited SDD section and ADR BEFORE planning.
   - Treat the SDD §8 public interface and cited ADR patterns as **frozen** —
     no invented signatures, no silent pattern substitution.
   - Treat `## Seams` rows as binding: a seam you `implement:` you also
     test (its seam-test is a `## Verification` row); a seam you `use:` you call
     across without changing its contract.
   - Executor latitude below the line: file/package layout within the module,
     private helpers, internal naming, test fixtures, library call shape.
   - **Materialized seams** (a `## Produces` bullet ending `[materialized]`):
     stub and its `{Seam}ContractTest` already on the branch, the binding
     starting point — fill the stub, **enable** the contract test (drop its
     `@Disabled`) and turn it green as your seam-test Verification row.
     Never re-declare the type elsewhere or leave the stub as a parallel copy.

## Step 2 — Preflight: verify Consumed contracts (cited mode)

2. **Before any other work** — no status change, no commits, no verification
   runs — run from the worktree root (`<main-checkout>` = first entry of
   `git worktree list`; the script comes from the main checkout, never this
   worktree's stale plugin copy — `GLOSSARY.md` "Main checkout"):

   ```
   bash $AFK_PLUGIN_ROOT/skills/afk/execute/scripts/verify-contract.sh plan/{NNNN-slug}.md --direction consumes --root .
   ```

   - Any miss (exit 1) → stop with `contract_mismatch` carrying the
     `{PRODUCER-ID}`. Quote the offending bullet verbatim. **Do not retry, do
     not auto-correct the producer** — fix the producer (re-run it or emit a
     corrective subtask) first. Record on both subtask files; set both PLAN.md
     rows via `scripts/plan-status.sh {plan-dir} {id}
     'blocked(contract_mismatch: {PRODUCER-ID} …)'` — that row carries the
     break for both subtasks.
   - Bullets the script reports `[materialized]` get the compiler on top of
     the grep: run `./mvnw -f all-modules-pom.xml -pl {module-of-file-path}
     --also-make test-compile -DskipUi=true` once (covering all such lines in
     that module). A compile failure in the seam surface (consumed type or its
     `{Seam}ContractTest`) → same `contract_mismatch` — the compiler caught a
     signature drift the anchor string couldn't.

## Step 9 — Producer self-preflight on `## Produces` (cited mode)

9. **Before declaring success**, run from the worktree root:

   ```
   bash $AFK_PLUGIN_ROOT/skills/afk/execute/scripts/verify-contract.sh plan/{NNNN-slug}.md --direction produces --root .
   ```

   - Any miss (exit 1) on your own `## Produces` → `produces_drift`. Quote the
     bullet; **do not retry or amend silently**. Fix the impl OR re-emit the
     slice with a corrected `## Produces`. A declared signature that turns out
     wrong is `design_conflict`, never a license to change it silently.
   - **Materialized bullets** (script reports the tag): the
     `{Seam}ContractTest` must be **enabled** — a surviving
     `@Disabled("seam pending …")` on it is `produces_drift` (the seam-test
     Verification row can't have legitimately gone green while disabled; name
     the test file).
   - **Generated-schema pickup (only where the repository generates its schema).** `{file-path}` ending `.java`
     containing `@Entity` / `@MappedSuperclass` / `@Embeddable`: a grep hit is
     necessary, not sufficient. Confirm the class's package is reachable from
     the module's entity-scan config (`@EntityScan` / `entityPackages` /
     `hibernate.archive.autodetection`), run the documented
     liquibase-hibernate7 pickup check (the subtask's integration-tier
     `## Verification` row), inspect the generated diff — no mention of the new
     entity/column/table → `produces_drift`, naming the entity and the empty
     diff path.

   `produces_drift` ("I didn't deliver the contract I declared, fix impl or
   re-slice") is **not** `design_conflict` ("the binding contract is wrong,
   route to grill-solution"). Pick the right one.

## Conflict procedure (cited mode)

If the subtask has a `## Conflict procedure` block, follow it on a
binding-contract violation. The canonical flow:

1. Stop coding the moment you realize the SDD/ADR mandate is unimplementable or
   contradicts reality. Don't paper over it.
2. Classify the fork per the decision protocol (`DECISIONS.md`, plugin root).
   A **two-way door**: record the corrective call in `plan/DECISIONS.md` (its
   `Supersedes:` line quotes the SDD/ADR passage it overrides), implement the
   recorded call, continue — no park.
3. A **one-way door or a tie**: stage no code; commit nothing under the
   conflict. Report `design_conflict` quoting the SDD section + the conflict
   and your recommendation, and set the tracker row to
   `blocked(design_conflict: …)`.
4. Run `/afk-toolkit:grill-solution` for a superseding ADR before re-running a parked
   conflict.

**Never override the SDD/ADR off the record.** An unrecorded substitution of a
different pattern or interface breaks the binding contract and produces work
other subtasks can't integrate with. The recorded two-way-door entry is the one
sanctioned deviation channel — later slices read the ledger and build on the
same call.

## Cited-mode OUTCOME statuses

These extend the OUTCOME status list in [SKILL.md](SKILL.md) Step 13:

- `design_conflict` — cited mode. A binding SDD/ADR decision is wrong,
  infeasible, or contradicts reality, and the correction is a one-way door or
  a tie (`DECISIONS.md`, plugin root — a two-way-door correction is recorded
  in `plan/DECISIONS.md` and never parks). Name the SDD section / ADR + the
  concrete conflict + your recommendation; route the human to
  `/afk-toolkit:grill-solution` for a superseding ADR before re-running.
- `contract_mismatch` — cited mode. Step 2: an upstream `## Produces`
  artifact is missing or its anchor doesn't appear. Name the `{PRODUCER-ID}`
  and quote the bullet; record on both subtask files.
- `produces_drift` — cited mode. Step 9: one of THIS subtask's own
  `## Produces` anchors doesn't appear in its file. Quote the bullet. Fix the
  impl OR re-emit the slice with a corrected `## Produces`.
