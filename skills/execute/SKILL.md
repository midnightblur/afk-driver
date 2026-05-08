---
name: execute
description: Execute one labelled SubTask end-to-end (Dev-Designing → Dev-Developing, then exit success) inside the AFK driver's worktree. The runner spawns one fresh Claude Code session per SubTask and invokes this skill. The runner — not this skill — performs the final Dev-CR/Merge transition after the session exits success.
---

# afk:execute — run one AFK SubTask

You are running inside a fresh Claude Code session that the AFK driver
(`afk_driver/runner.py`) just spawned for a single SubTask. The runner has
already:

- Created the per-Enhancement worktree and ensured it's clean.
- Opened a Draft MR for the parent Enhancement's branch.
- Set the cwd to the worktree.

Your job is to take one SubTask from `Dev-Pending` through `Dev-Designing` →
`Dev-Developing`, get the test command green, push commits, and exit with a
structured outcome. The **runner** performs the final `Dev-CR/Merge` transition
(and its gate-field writes) only when this skill exits with `success` — leave
that boundary transition to the runner so it never double-fires.

## Argument

A single Jira SubTask key, e.g. `P2P-1234`. Read it from the invocation; the
parent Enhancement's key is on the SubTask's `parent` field.

## Process

1. **Read the contract.** Fetch the SubTask description as Markdown via
   `JiraClient.get_issue_description_markdown(subtask_key)` (the helper
   handles ADF → Markdown for headings, bulletList, codeBlock, hardBreak,
   and `code` text-marks). Parse the result with
   `afk_driver.subtask_template.parse(...)`. Read the parent Enhancement's
   PRD file (path: `tools/payable/afk/PRD.md` for AFK-bootstrap work, or the
   service-prefixed path per the `/afk:prd` convention).

   **Read the binding design context (cited mode).** If the parsed template
   has non-empty `design_refs` and a `parent_sdd`, you are running in
   cited mode and the SDD/ADRs constrain your work:

   - Read every cited SDD section and ADR via `ctx_read` BEFORE planning.
     `design_refs` is a tuple of bullets like
     `"SDD: SDD.md#l7-modules — TemplateRegistry interface lives in §8"` or
     `"ADR: adr/0002-template-strategy-registry.md — registry-keyed Strategy"`.
   - Treat the public interface stated in SDD §8 (Module Decomposition)
     as **frozen**. Do not invent a different signature.
   - Treat the pattern choice in the cited ADRs as **frozen**. Do not
     silently substitute another pattern.
   - Executor latitude is below the line: file/package layout *within* the
     named module, private helpers, internal naming, test fixtures, library
     API call shape (when the SDD picked the library).

2. **Preflight: verify Consumed contracts (cited mode).** If the parsed
   template has a non-empty `consumes` tuple, every line is an upstream
   artifact this SubTask depends on. Each bullet has the shape:

   ```
   {PRODUCER-KEY} {file-path}#{grep-anchor} — {description}
   ```

   For each line:

   - `ctx_read` the `{file-path}` (cwd is the worktree root, so paths are
     relative to it). If the file does not exist on this branch, the
     producer hasn't landed what they promised — exit with
     `ClaudeOutcome("contract_mismatch", detail=..., producer_key="{PRODUCER-KEY}")`
     **before any other work** (no Dev-Designing transition, no commits,
     no test runs).
   - `ctx_search` for `{grep-anchor}` inside `{file-path}`. The anchor was
     chosen by `/afk:subtasks` to be distinctive — a class declaration, a
     method signature substring, an exported function name. If it does not
     appear, the producer drifted from the contract — exit
     `contract_mismatch` with the same shape.
   - Quote the offending bullet verbatim in `detail` so the runner's
     producer-side comment surfaces what the consumer expected.

   If every line greps clean, proceed. **Do not retry the grep, and do not
   try to auto-correct the producer.** A `contract_mismatch` halts the
   chain on purpose — the human needs to fix the producer (re-open the
   producer SubTask or emit a corrective SubTask) before this SubTask can
   succeed.

3. **Plan inside the SubTask's Scope.** Stay strictly within the Scope globs
   from the parsed template. Forbidden patterns are enforced post-hoc by
   `scope_enforcer.enforce(...)` against the diff — adding entity classes is
   fine, hand-written `UpgradeGroup_*.java` / liquibase changesets / pre-DB
   migrations are not.

4. **Transition: `Dev-Designing`.** Call the Jira client to transition the
   SubTask via the "Start Designing" transition before you start writing.

5. **Apply TDD.** Use the `/afk:tdd` skill: write a failing test first, then make it
   pass, then refactor. The Test command from the parsed template is the
   green-bar check — it must pass before you transition out of Dev-Developing.

6. **Transition: `Dev-Developing`.** After the planning is done and you start
   editing, transition via "Start Development".

7. **Commit.** Each commit message starts with the SubTask key in brackets:
   `[P2P-1234] <message>`. Cross-module edits must include a JIRA-prefixed
   marker comment in the added hunks (the `scope_enforcer` enforces this).

   **Honor `## Produces` (cited mode).** Every artifact declared in the
   parsed `produces` tuple must exist on the branch by the time this
   SubTask exits with success. **Step 10 below greps every declared
   anchor right before the success exit and aborts with `produces_drift`
   if any are missing — drifting from your own declared contract is no
   longer survivable mid-session.** If you discover the declared
   signature is wrong mid-flight, that is a `design_conflict`, not a
   license to silently change it.

8. **Push and update the Draft MR.** Push commits to the per-Enhancement
   branch. Call `gitlab_client.update_subtasks_checklist(...)` so the MR's
   auto-maintained section reflects this SubTask as done.

9. **Run the Test command.** Run the exact command from the parsed template
   (`pytest ...`, `mvn -pl ... test`, etc.). If it fails, retry once with a
   targeted fix. If still failing, abort (return `ClaudeOutcome("test_fail", detail=...)`).

10. **Producer self-preflight on `## Produces` (cited mode).** Before
    declaring success, verify every artifact you declared in the parsed
    `produces` tuple actually lands on the branch. For each bullet of the
    shape `{file-path}#{grep-anchor} — {one-line contract}`:

    - `ctx_read` the `{file-path}` (cwd is the worktree root, paths are
      relative). If the file does not exist, you committed without
      producing what you declared — exit with
      `ClaudeOutcome("produces_drift", detail=...)` quoting the offending
      bullet verbatim. **Do not retry, do not amend silently.**
    - `ctx_search` for `{grep-anchor}` inside `{file-path}`. The anchor
      was chosen at slicing time to be distinctive (a class declaration,
      a method signature substring, an exported function name). If it
      does not appear, the implementation diverged from the declared
      signature — exit `produces_drift` with the same shape.
    - Quote the failing bullet in `detail` so the runner's abort comment
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
         the plugin is not picking it up. Exit `produces_drift` with
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
    consumer's preflight — wasting a drain pass and surfacing the failure
    on the wrong ticket.

    `produces_drift` is **not** the same as `design_conflict`:
    `design_conflict` means "the binding contract is wrong, route to
    `/afk:architect-grill`"; `produces_drift` means "I did not deliver the
    contract I declared, route to impl-or-slice fix." The runner does
    not retry either, but the comment framing differs — pick the right
    status. If you discover mid-flight that the declared signature itself
    is wrong (the SDD §8 mandate is infeasible), exit `design_conflict`
    instead.

11. **Update parent Implementation Notes.** One bullet per
    `(SUBTASK-KEY)` via `jira_client.update_implementation_notes(...)`.

12. **Do NOT transition to `Dev-CR/Merge`.** The runner owns this boundary
    transition and the gate-field writes (`dev_cr_merge_gate_fields` in
    `DriverConfig`). It will fire them only when this skill returns
    `success`. Calling `Request CR & Merge` from inside the session causes a
    double-transition: the runner's follow-up call then fails because the
    SubTask has already left `Dev-Developing`. Leave the SubTask in
    `Dev-Developing` and exit.

13. **Emit the structured outcome marker, then exit.** This block is the
    contract between this session and the runner — without it, the runner
    has no way to tell `success` from `contract_mismatch` from
    `produces_drift`, because the spawned `claude --print` process exits
    `0` on clean termination regardless of the narrative outcome. Print
    exactly the following as the **last** thing in your output, on its own
    lines, not inside a tool result or commit message:

    ```
    <<<AFK_OUTCOME>>>
    {"status": "<status>", "detail": "<one-line summary>", "producer_key": <"PRODUCER-KEY" | null>}
    <<<END>>>
    ```

    The substring between the markers MUST be valid JSON. `producer_key`
    is required (set to `null` when not applicable). The runner regex-
    scans the log for the **last** occurrence of the marker (so a retry
    inside this session that re-emits the marker wins); a missing,
    malformed, or unknown-status marker is recorded by the runner as
    `other` with detail `"no AFK_OUTCOME marker emitted (...)"` and the
    SubTask is treated as an unexpected failure — i.e. silence is louder
    than failure now. If a wrapping framework (e.g. tool-call rendering)
    might mangle the angle-bracket markers, print them inside a fenced
    code block whose body is exactly the three lines shown above; the
    runner's regex tolerates surrounding whitespace and code-fence noise.

    Allowed `status` values and their meaning:

    - `success` — Test command green, code committed + pushed,
      Designing/Developing transitions landed. The runner will perform the
      final `Dev-CR/Merge` transition + gate fields after this skill exits.
    - `test_fail` / `build_fail` — let the runner retry up to `retry_count`.
    - `timeout` — exited because of the wall-clock cap. (You will rarely
      emit this yourself; the runner records `timeout` when subprocess.run
      raises `TimeoutExpired` and no marker was emitted in time.)
    - `design_conflict` — cited mode only. A binding decision in the SDD
      or a cited ADR is wrong, infeasible, or contradicts reality (e.g. the
      named library's API does not allow the signature SDD §8 specifies).
      Put the offending SDD section / ADR ID + the concrete conflict in
      `detail`. The runner does NOT retry; it posts a comment routing the
      human to `/afk:architect-grill` to emit a superseding ADR before
      re-queueing the SubTask. Do **not** fall back to `other` for
      binding-contract issues — the explicit status is what tells the
      human "the design is wrong, not the code."
    - `contract_mismatch` — cited mode only. Raised by Step 2 preflight
      when an upstream `## Produces` artifact is missing or its
      `{grep-anchor}` does not appear in the named file. Populate
      `producer_key` with the `{PRODUCER-KEY}` from the offending
      `## Consumes` line and quote the offending bullet in `detail`. The
      runner does NOT retry; it posts a comment on the consumer (this
      SubTask) AND a separate comment on the producer SubTask so the human
      can fix the producer (re-open it or emit a corrective SubTask)
      before re-queueing this one. Use this status — not `other` — for
      every preflight grep miss.
    - `produces_drift` — cited mode only. Raised by Step 10's producer
      self-preflight when one of THIS SubTask's own `## Produces` anchors
      does not appear in its declared file. Quote the offending bullet
      verbatim in `detail`. Symmetric to `contract_mismatch` but no
      separate producer ticket — consumer == producer == this SubTask.
      The runner does NOT retry; it posts a single comment framing it as
      "producer self-check failed" and routing the human to fix the impl
      OR re-emit the slice with a corrected `## Produces`. Use this
      status — not `design_conflict` — when YOUR implementation drifted
      from YOUR declaration (versus the SDD/ADR mandate being wrong).
    - `other` — unexpected failure; the runner will abort and comment.

## Conflict procedure (cited mode)

If the parsed SubTask has a `## Conflict procedure` block, follow it
verbatim when you hit a binding-contract violation. The canonical flow:

1. Stop coding the moment you realize the SDD/ADR mandate is unimplementable
   or contradicts reality. Don't paper over it with workarounds.
2. Stage no code. Commit nothing under the conflict.
3. Exit with `ClaudeOutcome("design_conflict", detail=<concrete description
   quoting the SDD section + the conflict>)`.
4. The runner handles the rest: posts a Jira comment surfacing the
   conflict, transitions the SubTask back to `Dev-Pending`, and tells the
   human to run `/afk:architect-grill` for a superseding ADR.

**Do NOT silently override the SDD/ADR.** Substituting a different pattern
or interface from inside this session breaks the binding contract and
produces work other SubTasks cannot integrate with.

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
- **Stay inside Scope globs.** If the work requires going outside, abort with
  detail explaining what was needed and why.

## Invoked by

The AFK driver (`afk_driver/cli.py`) spawns one fresh Claude Code session per
SubTask and invokes `/afk:execute SUBTASK-KEY`. Not invoked manually. The
caller is the runner; the only "next" after a successful exit is the runner's
own `Dev-CR/Merge` transition + gate-field writes.
