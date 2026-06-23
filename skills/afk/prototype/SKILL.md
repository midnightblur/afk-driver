---
name: prototype
disable-model-invocation: true
description: Interactively craft a feature's UI mockup with the user after `/afk:to-prd`. A conversational loop — it reads the PRD user stories, anchors to the real frontend's existing components and design tokens, writes self-contained HTML you open in a browser and refresh, and reshapes that HTML live as you react in plain language. A single skill that interviews, crafts, and updates the mockup as the conversation goes — not a one-shot variant dump, not a grill. Self-gates (`no_ui`) for backend/API/refactor features with no net-new screens. Durable-lite: the won direction is captured as `PROTOTYPE.md` + the chosen HTML sibling to `PRD.md`, traceable to user stories so `/afk:grill-verification`'s UI journeys can trace to it; the losing scaffolding is thrown away. Local-first, with a frictionless opt-in push to a persistent, team-shareable `claude.ai/design` project for stakeholder review. Optional — run when a feature has meaningful net-new UI worth settling before the SDD locks decisions.
---

# afk:prototype — craft the UI, conversationally

This is not an artifact-producer you run once and read, and not a grill that
only interviews. It is an **interactive UI-crafting loop**: you and I shape a
feature's screens together in a browser, and the durable record falls out of the
conversation at the end. The local HTML is the canvas; your reactions are the
steering; the won design is the artifact.

It sits **after `/afk:to-prd`** — the user stories are settled (so there's
something concrete to draw), but the SDD isn't (so a mockup can still cheaply
change the architecture instead of expensively re-doing it). For a brownfield
app this is where "what should this actually look like" gets answered against the
*real* app, not in someone's head.

## When it applies

Optional. Run it for a feature with **meaningful net-new UI** worth settling
before the SDD. Skip it for backend/API/refactor/tooling work.

**Self-gate first.** Read `PRD.md`'s User Stories. If none imply a net-new or
materially-changed screen — the feature is API/backend/refactor only — stop and
report `no_ui` ("nothing to prototype here"). A backend-heavy monorepo produces
many such features; don't manufacture a screen the feature doesn't need.

## Argument

- `ticket_id` *(or `prd_path`)* — locates `…/{TICKET-ID}/PRD.md` and its sibling
  artifact folder. The mockup lands beside the PRD.
- `scope` *(optional)* — a specific story / screen to focus on
  (e.g. `US-2`), instead of the whole feature's UI.

## Process

### 1. Read the stories and anchor to the real app

Read `PRD.md` — the User Stories and Acceptance Criteria are what the screen must
serve. Then **anchor to the real frontend**: find the sibling frontend checkout's
components, layout shell (header/sidebar/nav), and design tokens (the CSS /
Tailwind config / component library it actually uses), and read enough to mock
*in that vocabulary*. The point of prototyping a brownfield app is that the
mockup looks like **your app** — a generic Tailwind page teaches you nothing
about whether the feature fits the product. If you genuinely can't find the
frontend, say so and proceed with a neutral style, flagging that the anchor is
missing.

### 2. Open the canvas

Write a **self-contained HTML file** — no build step, no framework runtime, real
data shapes inlined as fixtures — to the ticket's `prototype/` working folder
(sibling to `PRD.md`). Tell the user the path; **they open it in a browser and
refresh as you edit.** That refresh loop is the entire UX — keep the file
openable-as-`file://` at all times (inline the CSS, no imports that need a
server).

How many screens to open with depends on how settled the direction is:

- **Direction unclear** → open with **2–3 structurally-different sketches** on one
  page, switchable by a `?variant=` param and a small floating bar. "Structurally
  different" means different layout, information hierarchy, and primary affordance
  — *not* three recolours of the same card grid. Divergence is the point; if two
  come out similar, redo one.
- **Direction roughly known** → go straight to a **single mockup** and refine.

### 3. Craft, react, update — the loop

This is the heart of the skill, and it is a **conversation**, not a spec hand-off:

1. The user reacts in plain language — "table's too dense", "move the actions to a
   sidebar", "I want the header from A with the list from B", "what if approvals
   were a modal?".
2. You **edit the HTML** to match and tell them to refresh.
3. Repeat. Ask the questions a designer would when the prompt is thin — "where does
   this open from?", "what's the empty state?", "what happens on reject?" — and
   answer them *in the mockup*, not in prose. Walking a real screen routinely
   surfaces PRD gaps (a state with no story, an action with no outcome); when it
   does, name it — it may need to route back to `/afk:to-prd`.

Converge from divergence: once a direction wins, collapse to the single chosen
mockup and polish *that* — empty states, the key interactions, the real density.
Keep it throwaway-grade (no tests, no real mutations — point actions at inline
stubs); fidelity is in the *look and flow*, not in working plumbing.

### 4. Settle — capture durable-lite

When the design feels right, the **won direction** becomes the artifact; the
losing scaffolding is thrown away.

- Keep the **chosen HTML** as `…/{TICKET-ID}/prototype/<screen>.html`. Delete the
  losing variants and the switcher — they rot fast and confuse the next reader.
- Write **`…/{TICKET-ID}/PROTOTYPE.md`** (sibling to `PRD.md`): the screens
  settled, each traced to the User Stories it serves, the key interactions /
  states, the design decisions that were made and *why* (so `/afk:grill-solution`
  and `/afk:grill-verification` inherit them), any PRD gaps surfaced, and a link to
  the chosen HTML. This — not the HTML, not the Claude Design project — is the
  **canonical record**.

### 5. Share — frictionless Claude Design push (opt-in)

The local file is the fast loop; pushing to `claude.ai/design` is one move when
you want a hosted, link-shareable preview for non-technical stakeholders. Only
when the user asks ("push it" / "share this"):

1. `DesignSync list_projects` → **reuse** the team's design-system project if it
   exists (a stable, app/team-level project — *not* a per-ticket one); else
   `create_project` once. Verify the target is a design-system project.
2. Tag the chosen HTML with a `<!-- @dsCard group="{TICKET-ID}" -->` first-line
   marker so it lands as a labelled card grouped by ticket and is **findable later**
   (`list_projects` → `list_files` re-finds any ticket's mockup months on).
3. `finalize_plan` (the one permission prompt) → `write_files` → print the
   shareable URL.

First run only: if design scopes aren't granted, tell the user to run
`/design-login` once, then retry — after that it's silent. The pushed project is a
**persistent mirror**, never the source of truth (see Boundary).

### 6. Report

End with one line, mirroring the chain's other skills:

```
OUTCOME: <status> — <one-line summary> [pushed: <url|no>]
```

- `crafted` — a mockup was settled; `PROTOTYPE.md` + chosen HTML written.
- `no_ui` — the feature has no net-new screens; nothing to prototype.
- `prd_gap` — a settled mockup surfaced a PRD gap worth a `/afk:to-prd` revisit;
  name it.
- `other` — unexpected stop.

## Boundary (Hard rules)

- **Local file is the source of truth.** `PROTOTYPE.md` + the in-repo HTML are
  canonical and version-controlled. The `claude.ai/design` project is an opt-in
  **share/preview mirror** living in the user's account — if it's deleted there,
  nothing in the repo is lost. Never treat the hosted copy as the record.
- **Throwaway scaffolding, durable decision.** Variant files and the switcher are
  disposable and get pruned on settle. The *decision* (which design, and why) is
  what survives, in `PROTOTYPE.md`.
- **Touches no tracker, merges nothing.** Local-first like the rest of the design
  layer — no Jira, no GitLab, no branch. The only network egress is the **opt-in**
  Claude Design push, and only when the user asks.
- **Mock the look and flow, not the backend.** No real mutations, no real DB —
  inline fixtures and stubbed actions. The question is "what should this look /
  feel like", answered before the SDD; "does the backend work" is verification's
  job, far downstream.
- **Anchor, don't invent a parallel design language.** Mock from the real
  frontend's components and tokens. A prototype that ignores the existing app
  produces a design engineering then has to throw away.

## Next

A settled mockup feeds two downstream skills:

- **`/afk:grill-solution`** — the UX decisions captured in `PROTOTYPE.md` are
  inputs to the architecture interview (a modal vs a page, an inline edit vs a
  wizard, all have SDD consequences).
- **`/afk:grill-verification`** — the mockup is the concrete screen its **UI
  journeys** trace to. Designing journeys against a real screen instead of an
  imagined one is the difference between a verification plan that holds and one
  that drifts.

If the mockup surfaced a PRD gap, route back to `/afk:to-prd` first.

---

*(The one-time "Phase 0" extraction of the existing frontend into a shared,
team-accessible `claude.ai/design` catalog is now its own skill —
**`/afk:design-system`**. Run it once per service to seed the catalog, then this
skill's Step 1 anchor can compose from those hosted cards instead of re-reading
the frontend each run, and Step 5's share push lands ticket mockups as cards in
the same project.)*
