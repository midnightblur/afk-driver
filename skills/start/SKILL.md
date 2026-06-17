---
name: start
description: Orient a developer to the AFK design + execution chain. Print the pipeline map, ask where they're starting (raw idea / partial PRD / SDD already in hand / ready to slice), route them to the correct entry skill, and surface the binding gates that block progress at each stage. Invoke whenever someone is unsure which `/afk:*` skill to run next, OR at the start of a new feature when a refresher is wanted. Does NOT drive subsequent stages itself — each chain skill keeps full control of its own grilling.
---

# afk:start — orientation for the AFK chain

You are this user's first contact with the AFK chain. They invoked you
because they're not sure which step to run, OR because they're starting a
new feature and want a map. **You do not drive the chain.** Your job is to
print the map, ask one routing question, and hand off cleanly to the right
skill. Do not invoke other skills via the Skill tool from inside this
session — each chain skill expects its own session.

## Process

1. **Print the pipeline map.** Show the user this mermaid block verbatim,
   captioned with one sentence:

   ```mermaid
   graph LR
       Start[/afk:start/] -->|raw idea| Grill[/afk:grill-requirements/]
       Start -->|have PRD| AG[/afk:grill-solution/]
       Start -->|have SDD| Sub[/afk:to-subtasks/]
       Grill --> Prd[/afk:to-prd/] --> Ticket[/afk:to-ticket/] --> AG --> Sdd[/afk:to-sdd/]
       Sdd -->|optional| Brief[/afk:to-design-brief/]
       Sdd --> Sub
       Brief --> Sub
       Sub -->|run once per subtask| Exec[/afk:execute/]
       Exec -.uses.-> Tdd[/afk:tdd/]
   ```

   > The chain runs left-to-right. Each stage either grills (interviews you)
   > or synthesizes (turns settled context into an artifact). You invoke
   > every stage yourself, including `/afk:execute` — run it once per
   > subtask in the local plan, in its own session on the parent's branch.

2. **Print the stage table.** One row per skill. Columns: Stage, Skill,
   Input, Output, Binding gate that blocks progress.

   | # | Skill | Input | Output | Binding gate |
   |---|-------|-------|--------|--------------|
   | 1 | `/afk:grill-requirements` | raw idea / problem | exhausted requirements decision tree | (no synthesis — moves to step 2 when user agrees the tree is exhausted) |
   | 2 | `/afk:to-prd` | the conversation from step 1 | PRD.md + requirement ADRs on disk (local artifacts only) | none — synthesis only, no gate; does NOT touch the tracker |
   | 3 | `/afk:to-ticket` | PRD.md on disk + existing parent key | full PRD content published into the parent ticket as native Jira formatting (mermaid rendered + embedded inline); idempotent update; PO content preserved | requires an existing parent ticket — refuses without `parent_key` (does NOT create the ticket); publishes PRD content only |
   | 4 | `/afk:grill-solution` | PRD | exhausted L1-L8 architecture decisions | **Grounding rule** — every claim about existing infra (libraries, services, modules, schemas) must be verified via `ctx_search` / `ctx_read` OR explicitly labelled "unverified premise" with user acknowledgement |
   | 5 | `/afk:to-sdd` | conversation from step 4 + PRD | SDD.md + per-decision ADRs | **Refuse-to-publish gate** (executor-blocking markers like `TBD` / `TODO` / `<placeholder>` + §13 Open Questions blocking executor in L2-L7) AND **library-version pin cross-check** against `pom.xml` / `package.json+lockfile` / `pyproject.toml` |
   | 6 | `/afk:to-design-brief` *(optional)* | PRD + SDD + ADRs | DESIGN-BRIEF.md (1-2 page stakeholder digest) | refuses if SDD §13 has executor-blocking open questions |
   | 7 | `/afk:to-subtasks` | PRD + SDD + ADRs (cited mode) OR PRD only (uncited, human-gated) | local `plan/` dir — `PLAN.md` index (solution map, seam register, progress tracker) + `NNNN-slug.md` per subtask with typed `## Produces` / `## Consumes` + tiered `## Verification` (no Jira) | **Slicing-time refuse gate** (re-runs §13 + library-version checks defensively) + **anchor-quality check** (forbidden generic tokens, ≥12 chars, ≤1 trial-grep match) + **acceptance citation rule** + **seam coverage** (every SDD §9b seam has a named implementer carrying its seam-test) |
   | 8 | `/afk:execute` | one subtask id (`NNNN-slug`) from the plan | code committed + pushed, tracker row `done`, Draft MR updated, handoff to human CR/Merge | **Step 2 consumer preflight** (every `## Consumes` anchor must grep clean on the branch) + **Step 9 producer self-preflight** (every own `## Produces` anchor must grep clean) + **every `## Verification` tier green** + JPA-entity liquibase-hibernate7 pickup check |
   | — | `/afk:tdd` | (called from inside `/afk:execute` Step 5) | red-green-refactor doctrine | n/a — tooling |

3. **Ask the routing question.** Then ask **exactly one** question:

   > **Where are you starting?**
   >
   > (a) Raw idea — nothing written yet. → `/afk:grill-requirements`
   > (b) PRD written on disk, not yet on the tracker. → `/afk:to-ticket`
   > (c) PRD published to the parent, no SDD yet. → `/afk:grill-solution`
   > (d) PRD + SDD + ADRs already in hand, ready to plan. → `/afk:to-subtasks`
   > (e) Stakeholder review upcoming on an existing SDD. → `/afk:to-design-brief`
   > (f) Something else / I just want to read the map and decide later.

   Wait for the user's answer. Do **not** run artifact detection on disk —
   parent-ticket key is rarely in scope at this stage, and a half-written
   PRD ≠ a published PRD. Asking is one extra prompt and never wrong.

4. **Hand off.** Based on the user's answer, print one short paragraph:

   - The literal slash command to run next.
   - One sentence on what that skill will do (interview vs. synthesize).
   - The binding gate the user should expect to hit (lifted from the table
     above).
   - For routes (a), (b) and (c), name the FULL downstream chain so the user
     can pace themselves: `/afk:grill-requirements` → `/afk:to-prd` →
     `/afk:to-ticket` → `/afk:grill-solution` → `/afk:to-sdd` → optional
     `/afk:to-design-brief` → `/afk:to-subtasks`. They will run each manually;
     this skill does not auto-advance.

   For (f), exit with no command — the user wanted only the map.

5. **Do not interview the user.** This skill is orientation, not grilling.
   The grilling skills (`/afk:grill-requirements`, `/afk:grill-solution`) are
   designed to be invoked in fresh sessions because each manages its own
   conversational state. Driving them from inside `/afk:start` confuses
   the instruction frame and produces worse interviews.

## Cited mode vs. uncited mode

The chain has two modes:

- **Cited mode** — the subtasks reference the SDD §N + ADR-NNNN that
  constrain them, list the §9b seams they implement/use, and carry typed
  `## Produces` / `## Consumes` contracts. Each subtask runs in its own fresh
  `/afk:execute` session with no memory of the previous one's plan; the only
  way subtask N+1 can verify subtask N delivered the expected interface is if
  N declared it up-front (Produces) and N+1 can grep for it (Consumes). Use
  cited mode for **new complex features** — anything touching ≥2 modules,
  introducing patterns, or with non-trivial txn / data.
- **Uncited mode** — PRD only, no SDD/ADR citations, no Produces/Consumes.
  Human-gated: `/afk:to-subtasks` asks before slicing without an SDD when
  one is absent. Use for **small features / bugs / refactors / tooling
  work** where the SDD overhead exceeds the value.

The chain is the same up through `/afk:to-prd`. The branch is at
`/afk:grill-solution`: skip it (and `/afk:to-sdd`, `/afk:to-design-brief`) for
uncited-mode work. `/afk:to-subtasks` accepts both modes.

## What this skill does NOT do

- Does NOT interview the user about their feature.
- Does NOT detect what stage they're at by scanning disk for PRD.md / SDD.md.
- Does NOT invoke other skills via the Skill tool.
- Does NOT validate the user's choice — if they say "I have an SDD" but
  don't, `/afk:to-subtasks` will refuse cleanly at its slicing-time gate.
  That's the right place for that check, not here.

## Next

Whatever skill the user routes to in step 3. After that skill completes,
its own `## Next` section points at the following stage. The chain
self-documents stage-to-stage; this skill is needed only at first contact.
