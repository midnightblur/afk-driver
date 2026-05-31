---
name: to-subtasks
description: Slice a PRD (and the accompanying SDD + ADRs, when present) into Jira SubTasks under a parent ticket (Enhancement or Bug — both share the Nakisa workflow), each tagged with the AFK label. Each SubTask cites the binding design artifacts that constrain it, so the implementing agent has a contract — not just a feature ask. SDD/ADR citations may be omitted for small features / bugs at the human's discretion. Use when the user has a PRD (and optionally an SDD) and a parent ticket, and wants to execute the work as AFK-eligible SubTasks via `/afk:execute`.
---

# afk:to-subtasks — slice a PRD (+ SDD/ADRs) into AFK-eligible SubTasks

The tracker is **Jira** (`mcp__jira__*` for every read/write). SubTasks attach
to the parent via the `parent.key` field and carry the AFK label
(`mvu-afk` / `afk-agents`, configurable). The SubTask body speaks the Goal /
Scope / Acceptance / Test-command vocabulary documented in Step 6.

## Arguments

- `prd_path` — path to the PRD file (typically
  `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/PRD.md` or
  `tasks/{TICKET-ID}/PRD.md` for tooling work).
- `parent_key` — Jira key of the parent ticket, e.g. `P2P-1220`. May be an
  Enhancement (typical) or a Bug (when slicing a hot-fix into AFK-eligible
  SubTasks). `/afk:execute` branches on `issuetype`: Enhancement parents get
  the Dev-Designing step (`Start Designing` then `Start Development`), Bug
  parents skip Dev-Designing and transition directly to Dev-Developing via
  `Start Development`.
- `sdd_path` *(optional)* — path to `SDD.md`. Defaults to the sibling of the PRD
  (`.../{TICKET-ID}/SDD.md`). If absent on disk and not passed, see "Design-doc
  optionality" below.
- `skip_design_docs` *(optional, default `false`)* — set `true` to slice without
  citing SDD/ADR. Human gate; see "Design-doc optionality".

## Process

1. **Read the PRD.** Use `ctx_read` (mode=full) on the PRD file. Read the
   parent ticket description for context (Target Branch, Components, etc.).
   The parent may be an Enhancement or a Bug — handle both the same way.

2. **Resolve design docs.** Look for `SDD.md` at `sdd_path` (or sibling of the
   PRD by default). If found, also enumerate `adr/design/NNNN-*.md` and
   `adr/requirements/NNNN-*.md` next to it and `ctx_read` each in
   `signatures` mode. The set of `(SDD section IDs, ADR IDs)` is your
   **citation pool** — every SubTask must reference at least one entry from it.

3. **Refuse-to-slice gate (cited mode only).** Before slicing, run two
   passes over the SDD and every ADR. **Refuse on any failure** in
   either pass — print offenders verbatim, bounce the user back to fix
   the SDD via `/afk:architect-grill` + `/afk:to-sdd` (or hand-edit + re-run this
   skill).

   **(a) Executor-blocking markers** — `ctx_search` for the same blocker
   pattern set `/afk:to-sdd` Step 7 enforces:

   - hard-blocker tokens: `\bTBD\b`, `\bTODO\b`, `\bFIXME\b`, `\bXXX\b`,
     `\?\?\?`, `<TBD>`, `<TODO>`, `<placeholder>`, `<fill>`, `<\?>`,
     `\[\?\]`, `_?FILL[_-]?IN_?`, `\(decide later\)`, `\(unresolved\)`,
     `\(open\)`,
   - unsubstituted template literals: `<TICKET-ID>`, `<NNNN>`,
     `<service>`, `{Feature Name}`, etc.,
   - §13 Open Questions rows with `Blocks executor? = yes` in any of
     L2-L7.

   Skip code-block contents (real generics like `<T>`, type-optional
   markers like `Foo?` are not blockers; only prose / table cells /
   diagram labels matter).

   **(b) Library-version pin cross-check** — for every library version
   pin the SDD or ADR cites (`Spring Boot 3.2.4`, `Hibernate 6.4.0`,
   `Vue 3.4`, `axios 1.6.x`, etc.), verify the pin against the actual
   build manifest:

   | Stack | Manifest |
   |-------|----------|
   | Maven | `pom.xml` (+ parent / BOM POMs) |
   | Gradle | `build.gradle(.kts)`, `gradle.properties`, `libs.versions.toml` |
   | Node | `package.json` + `package-lock.json` (resolved wins) |
   | Python | `pyproject.toml`, `requirements.txt`, `Pipfile.lock` |

   `ctx_search` the manifest for the artifact and compare. If the SDD's
   version differs from the manifest's pinned version, the slice
   inherits a fictional API surface — refuse and bounce. If the SDD
   labelled the version as `"inherited from {BOM}; not a direct pin"`,
   accept; that's the documented escape hatch from `/afk:to-sdd` Step 8.
   `/afk:to-sdd` should already have caught these, but the gate here
   defends against (i) hand-edits to the SDD after `/afk:to-sdd` ran,
   (ii) ADRs the SDD synthesizer didn't fully cross-check, and (iii)
   the manifest moving forward in a separate commit between SDD
   authorship and slicing.

   **Uncited mode skips both passes** — no SDD/ADRs to scan; the human
   has accepted that the PRD alone is the source of truth.

4. **Apply design-doc optionality** (see section below). Either proceed in
   *cited* mode (SDD/ADRs exist, `skip_design_docs=false`) or *uncited* mode.

5. **Slice into SubTasks.** A good SubTask is:
   - Independently buildable (no dependency on a sibling SubTask that hasn't
     landed yet, except where explicitly noted in `## Blocked by`).
   - Bounded by a clear Scope (one or two glob patterns under
     `tasks/{...}/**` or `{service}/{module}/**`).
   - Verifiable by a single Test command (`pytest ...`, `mvn -pl ... test`,
     etc.).
   - Sized so one `/afk:execute` session can finish in a single sitting
     (aim for under ~1 hour of work).
   - **(cited mode only)** Anchored to specific SDD section(s) and ADR(s).
     The SubTask's interface is the public interface stated in SDD §8 — do
     not invent a different one.
   - **(cited mode only)** Carries an explicit typed contract — every
     consumer-visible artifact this SubTask creates is named in `## Produces`
     with a one-line signature (the contract). Every artifact this SubTask
     reads from a prior sibling is named in `## Consumes` with the producing
     SubTask's key. The `/afk:execute` preflight greps Consumes against the branch
     before planning; mismatches halt the chain instead of crashing
     mid-implementation. This is what keeps the AFK chain reliable.

6. **For each SubTask, fill the structured Markdown contract** (the SubTask
   Markdown contract — `/afk:execute` parses these same sections):

   ```
   ## Goal
   <one paragraph: what this SubTask delivers>

   ## Design refs
   <cited mode>
   - SDD: <relative path>#<section-anchor> — <one phrase on what this section binds>
   - ADR: <relative path> — <one phrase>
   <uncited mode>
   (none — sliced without SDD/ADR per human approval; see PRD for scope)

   ## Scope
   - <glob 1>
   - <glob 2>

   ## Acceptance
   <cited mode — every bullet ends with a citation tag of the form
   `(PRD §X.Y)`, `(SDD §N)`, `(SDD §N row "...")`, or `(ADR-NNNN)`
   pointing at the specific binding artifact section the bullet
   enforces. Free-form bullets without a citation are rejected at
   Step 8 graph validation — see "Acceptance citation rule" below.>
   - [ ] <criterion 1> (PRD §X.Y)
   - [ ] <criterion 2> (SDD §N)
   - [ ] <cited mode> Implements the public interface in SDD §8 row "<module>" without modification (SDD §8)
   - [ ] <cited mode> Conforms to ADR-<NNNN> (no silent pattern substitution) (ADR-NNNN)
   - [ ] <cited mode> Every artifact in ## Produces compiles + matches its declared signature (SDD §8)
   - [ ] Tests pass via `<test command>` (SDD §10 NFRs)
   <uncited mode — citations omitted; bullets reference PRD sections by
   prose only, e.g. "Implements User Story 2.">
   - [ ] <criterion 1>
   - [ ] Tests pass via `<test command>`

   ## Produces
   <cited mode — one bullet per consumer-visible artifact created by this SubTask>
   - <relative-file-path>#<grep-anchor: class name, signature substring, or distinctive symbol> — <one-line contract>
   <uncited mode>
   (omit this block)

   ## Test command
   ```
   <exact command, runs from repo root>
   ```

   ## Parent PRD
   <prd_path>

   ## Parent SDD
   <sdd_path or "(none — uncited mode)">

   ## Blocked by
   <SubTask keys or "(none)">

   ## Consumes
   <cited mode AND Blocked by is non-empty — one bullet per artifact this SubTask reads from upstream>
   - <PRODUCER-KEY> <relative-file-path>#<grep-anchor> — <one-line description of what we expect>
   <otherwise>
   (omit this block)

   ## Conflict procedure
   If a binding decision in SDD/ADR is wrong / infeasible / contradicts
   reality during implementation, exit with `design-conflict` status quoting
   the SDD section + the conflict. Do NOT override silently. Route back to
   `/afk:architect-grill` for a superseding ADR.
   (omit this block in uncited mode)

   ## Implementation Notes (auto-maintained)
   <!-- AFK appends one bullet per completed SubTask -->
   ```

7. **Validate citations** (cited mode only):
   - Every SubTask references at least one SDD section AND at least one ADR
     OR explicitly states "no ADR applies — section binds directly."
   - Every ADR in the pool is referenced by at least one SubTask. Unreferenced
     ADRs mean either dead design or missing scope. Flag both to the user.
   - Every public interface listed in SDD §8 (Module Decomposition) is the
     subject of exactly one SubTask. Multiple SubTasks owning one interface =
     concurrency hazard; zero owners = forgotten module.

8. **Validate the slice** (cited mode only). Two passes — both must pass
   before any SubTask is created in Jira.

   **(a) Contract graph.** Walk every SubTask's `## Consumes` block and
   verify each line:
   - `{PRODUCER-KEY}` resolves to a SubTask **earlier in the slicing order**
     (forward references = circular dep; bounce, do not emit).
   - `{file-path}#{anchor}` appears verbatim as one of the producer's
     `## Produces` bullets. If a consumer expects a signature the producer
     does not declare, the slice is broken — refuse to create the SubTasks
     and report which producer/consumer pair is misaligned.
   - Every artifact in any `## Produces` block has at least one consumer OR
     is the public interface of a leaf SubTask (last in the chain). Orphan
     producers are warning-level, not blocking — surface them so the human
     can confirm the leaf was intentional.

   **(b) Anchor quality.** For every `{grep-anchor}` appearing in any
   `## Produces` bullet, run three checks. Reject the slice on any
   failure (don't silently downgrade — fix the anchor and re-emit):

   - **Forbidden-token check.** The anchor must not be one of the generic
     keywords below, taken alone or with only whitespace around it:
     `class`, `interface`, `void`, `function`, `def`, `method`, `struct`,
     `enum`, `type`, `record`. These match dozens of unrelated
     declarations and would silently pass on partial drift.
   - **Length check.** Anchor must be ≥12 characters. A bare class name
     ("`Foo`") rarely clears this; pair it with a signature fragment
     ("`class Foo implements Bar<E>`") so the grep breaks loudly when the
     signature changes.
   - **Trial grep.** If `{file-path}` exists at the worktree HEAD,
     `ctx_search` for `{grep-anchor}` in that file. Expected results:
     - **0 matches** — file will be modified or the anchor lands in
       new code added by this SubTask. Acceptable.
     - **1 match** — anchor is unique. Acceptable.
     - **≥2 matches** — anchor is ambiguous; a future grep could pass
       even on partial drift. Refuse and report `{file}#{anchor}`.

     For files that do not yet exist (a new file this SubTask creates),
     the trial grep is N/A — only the forbidden-token + length checks
     apply.

   The graph check (a) catches consumer/producer misalignment at
   declaration time. The anchor-quality check (b) catches anchors that
   would fail-open at runtime — anchors that *technically* match the
   producer's declaration but would also match unrelated code, letting
   signature drift sneak through `/afk:execute`'s preflight. Together they
   make contract drift impossible to ship: catch it here, save a wasted
   `/afk:execute` run.

   **(c) Acceptance citation rule (cited mode only).** Every bullet in
   `## Acceptance` MUST end with a citation tag of one of these shapes:

   - `(PRD §X.Y)` or `(PRD §X.Y "Section title")` — points at a PRD
     section / User Story / Implementation Decision
   - `(SDD §N)` or `(SDD §N row "...")` — points at an SDD layer /
     specific table row / specific diagram
   - `(ADR-NNNN)` — points at a specific ADR

   For each bullet:

   - **Citation present?** `\(PRD §`, `\(SDD §`, or `\(ADR-` near the
     end of the bullet. If absent, refuse the slice.
   - **Citation resolves?** The cited section / row / ADR must exist
     in the corresponding artifact. `ctx_search` the SDD/PRD/ADR file
     for the section anchor or quote — a phantom citation is worse
     than no citation because it gives reviewers false confidence.
     Refuse on phantom resolves.
   - **At least one bullet cites the SDD §8 module row** that this
     SubTask owns (cited mode), so the binding interface is impossible
     to miss when the executor scans Acceptance.

   This rule turns Acceptance into a binding-traceability table: every
   bullet has a definite source-of-truth that the executor can re-read
   if the bullet's prose is ambiguous, and reviewers can answer "where
   did this bullet come from?" without spelunking. Without it,
   Acceptance is free-form prose — easy to write, easy to satisfy
   *textually* without satisfying the *binding constraint* (the
   executor green-bars the test, but the prose was a paraphrase that
   missed the edge case the SDD's table row pinned).

   **Uncited mode skips this rule** — there is no SDD/ADR to cite; the
   PRD is the only source and bullets reference its User Stories by
   prose.

9. **Create the SubTasks in Jira** under the parent ticket. For each:
   - `issuetype` = "SubTask".
   - `parent.key` = `parent_key` (the Enhancement or Bug key passed in).
   - `labels` includes the AFK label (`mvu-afk`, configurable).
   - `summary` is `[AFK] <short title>`.
   - `description` is the structured Markdown above wrapped in ADF.
   - Rank order matches the slicing order (use `customfield_10004` /
     `Rank` field — drag if the Jira API doesn't expose it directly).
   - `fixVersions` and `components` inherited from the parent.

10. **Validate.** Re-read each created SubTask's description and confirm it
    round-trips against the SubTask Markdown contract — every section parses
    and nothing was mangled by the ADF round-trip. If a section is missing or
    malformed, fix the template and update the SubTask before exiting.

11. **Output.** A short bullet list of created SubTask keys + summaries +
    their cited SDD/ADR refs (or a "uncited" tag) for the user to scan. The
    user gates the run by transitioning each SubTask from `Creating` →
    `Dev-Pending` (review-then-approve flow).

## Design-doc optionality

Not every parent ticket is worth an SDD. The cost of writing one is real
(architect-grill + to-sdd is a 30-90 minute investment); for trivial work it
is overkill. The human decides per ticket.

**Decision matrix:**

| Parent shape | SDD recommended? | If skipped |
|--------------|-------------------|------------|
| New complex feature touching ≥2 modules / introducing patterns / non-trivial txn or data | **Yes — required.** Refuse to slice without SDD unless `skip_design_docs=true` is explicitly set. | — |
| Small enhancement to one module, well-trodden pattern | Optional. Recommend SDD if pattern choice or interface is non-obvious; otherwise PRD-only is fine. | Slice in uncited mode. |
| Bug fix (hot-fix or defect) | Usually skip. Only require SDD if the fix changes a public contract or introduces a new module. | Slice in uncited mode. |
| Refactor / rename / dep bump | Skip. PRD describes scope; SDD adds nothing. | Slice in uncited mode. |
| Tooling / scripts / CI / docs | Skip. | Slice in uncited mode. |

**When SDD is missing:**

1. Check disk: is `SDD.md` present at the resolved path? If yes → cited mode.
2. If no, and `skip_design_docs` is unset/false: **ASK the user** before
   proceeding. One question:
   *"No SDD found at `{path}`. Is this a small feature / bug / refactor that
   doesn't need one? Reply `yes` to slice without design citations, `no` to
   pause and run `/afk:architect-grill` + `/afk:to-sdd` first."*
3. If `skip_design_docs=true` (or user replies `yes`): slice in uncited mode.
   The `## Design refs` block reads `(none — sliced without SDD/ADR per
   human approval; see PRD for scope)`. Drop the `## Conflict procedure`
   block — there is no binding contract to conflict with.
4. Record the human's choice in the user-visible output so it is auditable.

**Never silently slice without an SDD when the parent ticket warrants one.**
The optionality is human-gated, not skill-decided.

## Typed contracts (`## Produces` / `## Consumes`) — cited mode

The Acceptance bullets describe *behavior* the SubTask must satisfy. Without
something more, two SubTasks can both pass their own Acceptance and still
collide at integration: the producer's interface drifts from what the consumer
assumed, and the chain wedges mid-run. Typed contracts close that gap.

**`## Produces`** — emitted on every cited SubTask, even ones with no
downstream consumer. Each bullet names one consumer-visible artifact:

```
- {file-path}#{grep-anchor} — {one-line contract}
```

- `{file-path}` is relative to the worktree root.
- `{grep-anchor}` is a distinctive substring `/afk:execute` can grep for —
  a class declaration (`class FooStrategy implements ExportStrategy<E>`), a
  method signature (`register(format: String, strategy: ExportStrategy)`),
  an enum constant, an exported function name. Pick whatever uniquely
  identifies the artifact in the file.
- `{one-line contract}` says what the artifact is for, in stakeholder
  language. It is the reviewer's cheat-sheet AND the consumer's spec.

Choose anchors that **break loudly** if the producer drifts. A class name
alone is too coarse — the class can stay named `FooStrategy` while its
method signature changes. Anchor on the signature line whenever the
signature is the contract.

**`## Consumes`** — emitted only when `## Blocked by` is non-empty. Each
bullet names one upstream artifact:

```
- {PRODUCER-KEY} {file-path}#{grep-anchor} — {one-line description}
```

The `{file-path}#{grep-anchor}` MUST appear verbatim in the producer's
`## Produces` block (Step 8 graph validation enforces this). `/afk:execute`'s
preflight greps for `{grep-anchor}` in `{file-path}` before the consumer's
session does any work; a missing or signature-divergent anchor exits with
`contract_mismatch` outcome — no wasted attempt, no half-applied changes.

**Why this is mandatory in cited mode**: each SubTask runs in its own fresh
`/afk:execute` session. The session has no memory of what
the previous session's plan was. The only way SubTask N+1 can verify
SubTask N delivered the expected interface is if N's interface was
declared up-front and N+1 can grep for it. Without typed contracts, the
session re-reads the SDD, re-derives an expected signature, and may guess
differently than its predecessor — same SDD, different reading. Typed
contracts make the handoff explicit.

## Slicing heuristics

- One SubTask per independently shippable module (worktree manager, jira
  client, etc.) — *not* per acceptance bullet.
- **In cited mode**, slice along SDD §8 module boundaries. One SubTask =
  one module's public interface filled in. If you find yourself splitting a
  module, the SDD module is too coarse — bounce back, do not invent a new
  split that contradicts §8.
- Aim for 4–10 SubTasks per parent ticket. More than 10 means the PRD is too
  big or the slicing is too fine.
- Test commands should be specific: `pytest tasks/foo/tests/test_bar.py`
  beats `pytest`.

## Hard rules

- **Don't fabricate Acceptance bullets.** Every bullet must trace back to
  something in the PRD's User Stories, Implementation Decisions, or (cited
  mode) the SDD / an ADR. Cited mode enforces this with the Step 8(c)
  Acceptance citation rule: every bullet ends with `(PRD §X.Y)` /
  `(SDD §N)` / `(ADR-NNNN)`, the citation must resolve to a real
  section, and at least one bullet cites the SDD §8 row this SubTask
  owns. Bullets without citations are not free-form prose — they're
  bugs.
- **Don't invent a public interface.** In cited mode, the interface comes
  from SDD §8 verbatim. If the SDD does not name it, that is a design gap —
  bounce to `/afk:architect-grill`, do not improvise.
- **Don't apply the AFK label to risky SubTasks.** DB schema migrations,
  cross-team library bumps, anything that touches `db/changelog/**` —
  these need a human in the loop, so omit `mvu-afk`.
- **JPA-entity SubTasks must verify liquibase-hibernate7 pickup**
  (core-services Java only). When a SubTask's `## Produces` includes a
  `.java` file containing `@Entity` / `@MappedSuperclass` / `@Embeddable`,
  the `## Test command` MUST include the project's documented
  liquibase-hibernate7 pickup verification (typically
  `mvn -pl {module} compile liquibase:diff
  -Dliquibase.diffChangeLogFile=target/afk-diff.xml` followed by a
  grep against `target/afk-diff.xml` for the entity / column name) —
  not just unit tests against the entity in isolation. A SubTask that
  declares a JPA entity but only runs `mvn -pl {module} test` will
  pass while the plugin silently skips the entity (wrong package,
  missing scan config, malformed annotation), and the schema diverges
  at the next environment refresh. `/afk:execute` Step 10's symmetric
  pickup check enforces this at runtime, but slicing-time enforcement
  catches it before the SubTask ever runs.
- **Never set status directly.** Leave SubTasks in `Creating` for the user
  to review and transition manually.
- **Cited mode SubTasks must include the Conflict procedure block.**
  Without it, executors have no documented escape hatch and may drift from
  the SDD silently.
- **Cited mode SubTasks must include `## Produces`.** Even leaf SubTasks
  with no downstream consumer name their consumer-visible artifacts — the
  block doubles as the reviewer's cheat-sheet. Skipping it makes the next
  consumer's preflight unverifiable.
- **`## Consumes` is mandatory iff `## Blocked by` is non-empty.** Every
  upstream dependency declared in `Blocked by` must have at least one
  matching `Consumes` line, and every `Consumes` line must reference a key
  that appears in `Blocked by`. Otherwise the dependency is opaque and the
  preflight has nothing to grep.
- **Anchors must be distinctive enough to grep.** Step 8(b) enforces
  three machine checks: (1) anchor must not be one of the forbidden
  generic tokens [`class`, `interface`, `void`, `function`, `def`,
  `method`, `struct`, `enum`, `type`, `record`]; (2) anchor must be
  ≥12 characters; (3) trial grep against `{file-path}` at HEAD must
  return 0 or 1 match (≥2 = ambiguous, refuse to emit). Anchor on the
  declaration line or method signature so the grep fails when the
  producer drifts. A bare class name rarely passes all three.
- **Uncited mode must be human-approved per ticket.** The skill never
  decides on its own that an SDD isn't needed.

## Next

After SubTasks land in Jira and you've reviewed the slice, transition each
SubTask from `Creating` → `Dev-Pending` and apply the AFK label
(default `afk-agents`). Then work them one at a time: in a session on the
parent Enhancement's branch, run **`/afk:execute SUBTASK-KEY`** for each
SubTask in rank order (respecting `## Blocked by`). Each run takes that
SubTask through Dev-Designing → Dev-Developing, commits, pushes, and updates
the Draft MR; you handle CR/Merge after reviewing.
