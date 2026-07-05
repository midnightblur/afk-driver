---
name: prototype
description: Interactively craft a feature's UI mockup with the user once the PRD's user stories are settled. Use when the user runs `/afk:prototype`, or wants to craft or settle a feature's UI mockup after the PRD exists and before the SDD locks decisions; skip for backend/API/refactor features with no net-new screens (self-gates `no_ui`). A conversational loop — it reads the PRD user stories, anchors to the real frontend's existing components and design tokens, writes self-contained HTML you open in a browser and refresh, and reshapes that HTML live as you react in plain language. Durable-lite: the won direction is captured as `PROTOTYPE.md` + the chosen HTML sibling to `PRD.md`, traceable to user stories so `/afk:grill-verification`'s UI journeys can trace to it; the losing scaffolding is thrown away. Local-first, with a frictionless opt-in push to a persistent, team-shareable `claude.ai/design` project for stakeholder review.
---

# afk:prototype — craft the UI, conversationally

An **interactive UI-crafting loop**: you and I shape a feature's screens together in a browser; the durable record falls out of the conversation. Local HTML is the canvas; your reactions steer; the won design is the artifact.

Runs once the PRD's user stories are settled (something concrete to draw) and before the SDD locks decisions (a mockup can still cheaply reshape architecture vs expensively redoing it). For a brownfield app, this answers "what should this actually look like" against the *real* app, not in someone's head.

## When it applies

Optional. Run for a feature with **meaningful net-new UI** worth settling before the SDD. Skip backend/API/refactor/tooling work.

**Self-gate first.** Read `PRD.md`'s User Stories. If none imply a net-new or materially-changed screen — feature is API/backend/refactor only — stop, report `no_ui` ("nothing to prototype here"). A backend-heavy monorepo produces many such features; don't manufacture a screen the feature doesn't need.

## Argument

- `ticket_id` *(or `prd_path`)* — locates `…/{TICKET-ID}/PRD.md` and its sibling artifact folder. Mockup lands beside the PRD.
- `scope` *(optional)* — specific story / screen to focus on (e.g. `US-2`), instead of the whole feature's UI.

## Process

### 1. Read the stories and anchor to the real app

Read `PRD.md` — User Stories and Acceptance Criteria are what the screen must serve. Then **anchor to the real frontend**: find the sibling frontend checkout's components, layout shell (header/sidebar/nav), and design tokens (the CSS / Tailwind config / component library it actually uses); read enough to mock *in that vocabulary* — the mockup must look like **your app**; a generic Tailwind page teaches nothing about whether the feature fits the product. Can't find the frontend? Say so, proceed with a neutral style, flag the missing anchor.

### 2. Open the canvas

Write a **self-contained HTML file** — no build step, no framework runtime, real data shapes inlined as fixtures — to the ticket's `prototype/` working folder (sibling to `PRD.md`). Tell the user the path; **they open it in a browser and refresh as you edit.** That refresh loop is the entire UX — keep the file openable-as-`file://` always (inline the CSS, no imports needing a server).

Screens to open with depends on how settled the direction is:

- **Direction unclear** → open with **2–3 structurally-different sketches** on one page, switchable by a `?variant=` param and a small floating bar. "Structurally different" = different layout, information hierarchy, primary affordance — *not* three recolours of the same card grid. Divergence is the point; if two come out similar, redo one.
- **Direction roughly known** → go straight to a **single mockup** and refine.

### 3. Craft, react, update — the loop

A **conversation**, not a spec hand-off:

1. The user reacts in plain language — "table's too dense", "move the actions to a sidebar", "I want the header from A with the list from B", "what if approvals were a modal?".
2. You **edit the HTML** to match and tell them to refresh.
3. Repeat. Ask the questions a designer would when the prompt is thin — "where does this open from?", "what's the empty state?", "what happens on reject?" — and answer them *in the mockup*, not in prose. Walking a real screen routinely surfaces PRD gaps (a state with no story, an action with no outcome); name it when it does — it may need to route back to `/afk:to-prd`.

Converge from divergence: once a direction wins, collapse to the single chosen mockup and polish *that* — empty states, key interactions, real density. Keep it throwaway-grade (no tests, no real mutations — point actions at inline stubs); fidelity is in the *look and flow*, not working plumbing.

### 4. Settle — capture durable-lite

When the design feels right, the **won direction** becomes the artifact; losing scaffolding is thrown away.

- Keep the **chosen HTML** as `…/{TICKET-ID}/prototype/<screen>.html`. Delete the losing variants and the switcher — they rot fast and confuse the next reader.
- Write **`…/{TICKET-ID}/PROTOTYPE.md`** (sibling to `PRD.md`): screens settled, each traced to the User Stories it serves; key interactions / states; design decisions made and *why* (so `/afk:grill-solution` and `/afk:grill-verification` inherit them); any PRD gaps surfaced; a link to the chosen HTML. This — not the HTML, not the Claude Design project — is the **canonical record**.
- Upsert the `Prototype` row (`chosen {date}`) in the sibling `INDEX.md` per `skills/afk/to-prd/INDEX-FORMAT.md`; create the file per that format if missing.

### 5. Share — Claude Design push (opt-in)

To share the prototype on Claude Design, follow [CLAUDE-DESIGN-PUSH.md](CLAUDE-DESIGN-PUSH.md).

### 6. Report

End with one line:

```
OUTCOME: <status> — <one-line summary> [pushed: <url|no>]
```

| Status | Meaning |
|---|---|
| `crafted` | A mockup was settled; `PROTOTYPE.md` + chosen HTML written. |
| `no_ui` | The feature has no net-new screens; nothing to prototype. |
| `prd_gap` | A settled mockup surfaced a PRD gap worth a `/afk:to-prd` revisit; name it. |
| `other` | Unexpected stop. |

## Boundary (Hard rules)

- **Local file is the source of truth.** `PROTOTYPE.md` + the in-repo HTML are canonical and version-controlled. The `claude.ai/design` project is an opt-in **share/preview mirror** in the user's account — delete it there, nothing in the repo is lost. Never treat the hosted copy as the record.
- **Throwaway scaffolding, durable decision.** Variant files and the switcher are disposable, pruned on settle. The *decision* (which design, and why) survives, in `PROTOTYPE.md`.
- **Touches no tracker, merges nothing.** Local-first like the rest of the design layer — no Jira, no GitLab, no branch. Only network egress is the **opt-in** Claude Design push, only when the user asks.
- **Mock the look and flow, not the backend.** No real mutations, no real DB — inline fixtures, stubbed actions. The question is "what should this look / feel like", answered before the SDD; "does the backend work" is verification's job, far downstream.
- **Anchor, don't invent a parallel design language.** Mock from the real frontend's components and tokens. A prototype that ignores the existing app produces a design engineering then has to throw away.

## Next

A settled mockup feeds two downstream skills:

- **`/afk:grill-solution`** — UX decisions captured in `PROTOTYPE.md` are inputs to the architecture interview (a modal vs a page, an inline edit vs a wizard — all have SDD consequences).
- **`/afk:grill-verification`** — the mockup is the concrete screen its **UI journeys** trace to. Designing journeys against a real screen instead of an imagined one is the difference between a verification plan that holds and one that drifts.

If the mockup surfaced a PRD gap, route back to `/afk:to-prd` first.

---

Visual extraction of the existing frontend into a shared, team-accessible `claude.ai/design` catalog lives in **`/afk:design-system`**. Run it once per service to seed the catalog; Step 1's anchor can then compose from those hosted cards instead of re-reading the frontend each run, and Step 5's share push lands ticket mockups as cards in the same project.
