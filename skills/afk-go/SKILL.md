---
name: execute
description: Execute one labelled SubTask end-to-end interactively — read its contract, design, develop under TDD, commit, push, update the Draft MR — then stop at CR/Merge for the human. You run this yourself in a session on the parent Enhancement's branch; there is no autonomous driver. Drives the SubTask through Dev-Designing → Dev-Developing and reports a structured outcome.
---

# afk:execute — run one AFK SubTask interactively

You run this skill yourself, in a Claude Code session, against a **single
SubTask**. There is no autonomous driver spawning you — you (the human) invoke
`/afk:execute SUBTASK-KEY` from a session whose cwd is a worktree checked out
on the parent Enhancement's branch.

Before you start, make sure:

- The cwd is a clean worktree on the parent Enhancement's branch
  (`mvu/afk/{enh-id}` or whatever branch the parent ticket targets). Create the
  worktree + branch yourself if it doesn't exist yet.
- A Draft MR for that branch exists (open one with `glab mr create --draft` if
  not). The MR carries the auto-maintained SubTask checklist block.

The tracker is **Jira** and the SCM is **GitLab** (`glab` CLI). Use the
`mcp__jira__*` tools for every ticket read/write and `glab` for MR operations.

Your job: take one SubTask from `Dev-Pending` through `Dev-Designing` →
`Dev-Developing`, get its Test command green, commit + push, update the Draft
MR, then **stop**. CR/Merge is the human's call — see Step 12.

## Argument

A single Jira SubTask key, e.g. `P2P-1234`. The parent Enhancement's key is on
the SubTask's `parent` field.

## Process

1. **Read the contract.** Fetch the SubTask description as Markdown via
   `mcp__jira__jira_get` and parse its sections yourself against the SubTask
   Markdown contract (`## Goal / Scope / Acceptance / Test command / Parent PRD
   / Blocked by / Implementation Notes`, plus the cited-mode sections `## Design
   refs / Produces / Parent SDD / Consumes / Conflict procedure` when present).
   Read the parent Enhancement's PRD file (the service-prefixed path per the
   `/afk:to-prd` convention).

   **Read the binding design context (cited mode).** If the SubTask has
   non-empty `## Design refs` and a `## Parent SDD`, you are running in cited
   mode and the SDD/ADRs constrain your work:

   - Read every cited SDD section and ADR via `ctx_read` BEFORE planning.
     `## Design refs` bullets look like
     `"SDD: SDD.md#l7-modules — TemplateRegistry interface lives in §8"` or
     `"ADR: adr/design/0002-template-strategy-registry.md — registry-keyed Strategy"`.
   - Treat the public interface stated in SDD §8 (Module Decomposition)
     as **frozen**. Do not invent a different signature.
   - Treat the pattern choice in the cited ADRs as **frozen**. Do not
     silently substitute another pattern.
   - Executor latitude is below the line: file/package layout *within* the
     named module, private helpers, internal naming, test fixtures, library
     API call shape (when the SDD picked the library).

2. **Preflight: verify Consumed contracts (cited mode).** If the SubTask has a
   non-empty `## Consumes` section, every line is an upstream artifact this
   SubTask depends on. Each bullet has the shape:

   ```
   {PRODUCER-KEY} {file-path}#{grep-anchor} — {description}
   ```

   For each line:

   - `ctx_read` the `{file-path}` (cwd is the worktree root, so paths are
     relative to it). If the file does not exist on this branch, the
     producer hasn't landed what they promised — stop with a
     `contract_mismatch` outcome (carry the `{PRODUCER-KEY}`) **before any
     other work** (no Dev-Designing transition, no commits, no test runs).
   - `ctx_search` for `{grep-anchor}` inside `{file-path}`. The anchor was
     chosen by `/afk:to-subtasks` to be distinctive — a class declaration, a
     method signature substring, an exported function name. If it does not
     appear, the producer drifted from the contract — stop with the same
     `contract_mismatch` outcome.
   - Quote the offending bullet verbatim in the outcome detail so you can
     comment on both the consumer (this SubTask) and the producer SubTask.

   If every line greps clean, proceed. **Do not retry the grep, and do not
   try to auto-correct the producer.** A `contract_mismatch` halts the
   chain on purpose — the producer must be fixed (re-open the producer SubTask
   or emit a corrective SubTask) before this SubTask can succeed. Post a Jira
   comment on both the consumer and the producer SubTask (via
   `mcp__jira__jira_comment`) so the break is recorded where it lives.

3. **Plan inside the SubTask's Scope.** Stay strictly within the Scope globs
   from the contract. Check your own diff against those globs and the
   forbidden-pattern list before committing — adding entity classes is fine,
   hand-written `UpgradeGroup_*.java` / liquibase changesets / pre-DB
   migrations are not (see Hard rules).

4. **Transition: `Dev-Designing`.** Transition the SubTask via the "Start
   Designing" transition (`mcp__jira__jira_transition`) before you start
   writing.

5. **Apply TDD.** Use the `/afk:tdd` skill: write a failing test first, then make it
   pass, then refactor. The Test command from the contract is the
   green-bar check — it must pass before you transition out of Dev-Developing.

6. **Transition: `Dev-Developing`.** After the planning is done and you start
   editing, transition via "Start Development" (`mcp__jira__jira_transition`).

7. **Commit.** Each commit message starts with the SubTask key in brackets:
   `[P2P-1234] <message>`. Cross-module edits must include a JIRA-prefixed
   marker comment in the added hunks (see Hard rules).

   **Honor `## Produces` (cited mode).** Every artifact declared in the
   `## Produces` section must exist on the branch by the time this SubTask
   exits with success. **Step 10 below greps every declared anchor right
   before the success exit and aborts with `produces_drift` if any are
   missing — drifting from your own declared contract is not survivable
   mid-session.** If you discover the declared signature is wrong mid-flight,
   that is a `design_conflict`, not a license to silently change it.

8. **Push and update the Draft MR.** Push commits to the parent Enhancement's
   branch. Update the MR's auto-maintained SubTask checklist block (bracketed
   by `<!-- afk:subtasks:start -->` … `<!-- afk:subtasks:end -->`) via `glab`
   so it reflects this SubTask as done — preserve everything outside the block
   verbatim.

9. **Run the Test command.** Run the exact command from the contract
   (`pytest ...`, `mvn -pl ... test`, etc.). If it fails, retry once with a
   targeted fix. If still failing, stop with a `test_fail` outcome.

10. **Producer self-preflight on `## Produces` (cited mode).** Before
    declaring success, verify every artifact you declared in the `## Produces`
    section actually lands on the branch. For each bullet of the
    shape `{file-path}#{grep-anchor} — {one-line contract}`:

    - `ctx_read` the `{file-path}` (cwd is the worktree root, paths are
      relative). If the file does not exist, you committed without
      producing what you declared — stop with a `produces_drift` outcome,
      quoting the offending bullet verbatim. **Do not retry, do not amend
      silently.**
    - `ctx_search` for `{grep-anchor}` inside `{file-path}`. The anchor
      was chosen at slicing time to be distinctive (a class declaration,
      a method signature substring, an exported function name). If it
      does not appear, the implementation diverged from the declared
      signature — stop with `produces_drift`.
    - Quote the failing bullet in the outcome detail so the abort comment
      surfaces what was promised vs. what landed.
    - **JPA-entity pickup check (core-services Java only).** If
      `{file-path}` ends in `.java` AND the file contains `@Entity` (or
      `@MappedSuperclass`, `@Embeddable`), the artifact is a JPA shape
      that the liquibase-hibernate7 plugin must pick up to land in a
      generated changelog. A grep-on-class-declaration hit is necessary
      but not sufficient; verify also:
      1. The package the class lives in is reachable from
         `spring.jpa.properties.hibernate.archive.autodetection` /
         `entityPackages` / equivalent scan configuration in the
         module's `application.yml` / `application.properties` /
         `@EntityScan` annotation. Mismatched package = entity is
         compiled but invisible to Hibernate, schema diverges silently.
      2. Run the project's documented liquibase-hibernate7 pickup
         verification (typically `mvn -pl {module} compile
         liquibase:diff -Dliquibase.diffChangeLogFile=target/afk-diff.xml`,
         or whatever sibling SubTasks have used — `ctx_search` the
         module's `pom.xml` for the `liquibase-hibernate7` plugin
         config to find the right goal). Inspect the generated diff
         file; if it does NOT mention the new entity / column / table,
         the plugin is not picking it up. Stop with `produces_drift`,
         detail naming the entity and the empty diff path.

      This is the symmetric counterpart to the `## Produces` grep:
      grep proves the *file* exists and the *symbol* is declared; the
      pickup check proves the *runtime infrastructure* will actually
      consume it. A SubTask that declares a JPA entity but isn't
      picked up by liquibase-hibernate7 ships a code-only change that
      breaks at the next environment refresh — `produces_drift` is
      the right framing because the SubTask delivered the declared
      file but failed to deliver the contract the file was supposed
      to honour.

    This is the symmetric counterpart to Step 2's consumer-side preflight.
    Without it, signature drift is observable only at the **next**
    consumer's preflight — surfacing the failure on the wrong ticket.

    `produces_drift` is **not** the same as `design_conflict`:
    `design_conflict` means "the binding contract is wrong, route to
    `/afk:architect-grill`"; `produces_drift` means "I did not deliver the
    contract I declared, route to impl-or-slice fix." Pick the right status.
    If you discover mid-flight that the declared signature itself
    is wrong (the SDD §8 mandate is infeasible), use `design_conflict`
    instead.

11. **Update parent Implementation Notes.** Splice one bullet per
    `(SUBTASK-KEY)` into the parent Enhancement's
    `## Implementation Notes (auto-maintained)` section via
    `mcp__jira__jira_edit` — preserve the human-edited prose around the block.

12. **Stop at CR/Merge — the human decides.** Do **not** fire
    `Request CR & Merge` or merge the MR yourself. Leave the SubTask in
    `Dev-Developing` with the Draft MR updated and report `success`. The human
    reviews the MR and performs the `Dev-CR/Merge` transition (and any gate-
    field writes) out of band. Auto-merging is outside this skill's lane.

13. **Report the structured outcome.** End your run with a one-line outcome so
    the invoking human (or an orchestrator like `/afk:iterate-afk`) can tell
    `success` from a structured failure at a glance. State the status and a
    one-line detail (and, for `contract_mismatch`, the producer key):

    ```
    OUTCOME: <status> — <one-line summary> [producer: <PRODUCER-KEY|none>]
    ```

    Status values and their meaning:

    - `success` — Test command green, code committed + pushed,
      Designing/Developing transitions landed, MR updated. The human handles
      CR/Merge.
    - `test_fail` / `build_fail` — the Test command / build did not go green
      after one targeted retry.
    - `timeout` — exited because of a wall-clock cap.
    - `design_conflict` — cited mode only. A binding decision in the SDD
      or a cited ADR is wrong, infeasible, or contradicts reality (e.g. the
      named library's API does not allow the signature SDD §8 specifies).
      Name the offending SDD section / ADR ID + the concrete conflict.
      Route the human to `/afk:architect-grill` to emit a superseding ADR
      before re-running the SubTask.
    - `contract_mismatch` — cited mode only. Raised by Step 2 preflight
      when an upstream `## Produces` artifact is missing or its
      `{grep-anchor}` does not appear in the named file. Name the
      `{PRODUCER-KEY}` from the offending `## Consumes` line and quote the
      offending bullet. Comment on both the consumer and the producer SubTask.
    - `produces_drift` — cited mode only. Raised by Step 10's producer
      self-preflight when one of THIS SubTask's own `## Produces` anchors
      does not appear in its declared file. Quote the offending bullet.
      Symmetric to `contract_mismatch` but no separate producer ticket —
      consumer == producer == this SubTask. Fix the impl OR re-emit the
      slice with a corrected `## Produces`.
    - `other` — unexpected failure.

## Conflict procedure (cited mode)

If the SubTask has a `## Conflict procedure` block, follow it
verbatim when you hit a binding-contract violation. The canonical flow:

1. Stop coding the moment you realize the SDD/ADR mandate is unimplementable
   or contradicts reality. Don't paper over it with workarounds.
2. Stage no code. Commit nothing under the conflict.
3. Report a `design_conflict` outcome with a concrete description quoting the
   SDD section + the conflict.
4. Post a Jira comment surfacing the conflict, transition the SubTask back to
   `Dev-Pending`, and run `/afk:architect-grill` for a superseding ADR before
   re-running.

**Do NOT silently override the SDD/ADR.** Substituting a different pattern
or interface breaks the binding contract and produces work other SubTasks
cannot integrate with.

## Hard rules (inherited from core-services CLAUDE.md)

- **Never alter DB directly.** Add JPA entities; let liquibase-hibernate7 pick
  them up. No hand-written `UpgradeGroup`, `PreDbMigration`, or
  `db/changelog/*` edits. Step 10's JPA-entity pickup check is what enforces
  this — adding `@Entity` without a matching pickup-verification run is
  treated as `produces_drift`, not success.
- **Never auto-commit outside this AFK lane.** This skill is the *only*
  context where the agent commits autonomously.
- **Cross-module edits need marker comments.** A JIRA-prefixed line like
  `// P2P-1234: shared helper added` in the added hunks of any file outside
  the home module.
- **No `--no-verify`, no `--force`, no global git config changes.**
- **Stay inside Scope globs.** If the work requires going outside, stop with
  detail explaining what was needed and why.
