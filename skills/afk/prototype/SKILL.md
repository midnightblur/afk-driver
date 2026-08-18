---
name: prototype
description: Interactively craft a feature's UI mockup as self-contained drivable HTML anchored to the real frontend. Use on /afk:prototype after the PRD exists and before the SDD locks decisions.
---

> **Language:** read `LANGUAGE.md` (plugin root) first. It binds every reply, question, and artifact this skill produces — Simplified Technical English, glossary terms verbatim.

# afk:prototype — craft the UI, conversationally

Runs once the PRD's user stories are settled (something concrete to draw) and before the SDD locks decisions (a mockup can still cheaply reshape architecture vs expensively redoing it). For a brownfield app, answers "what should this actually look like **and feel like to use**" against the *real* app, not in someone's head. The user vets two things: the layout, and what the feature *does* — so the mockup is **drivable**, not a picture.

## When it applies

Optional. Run for a feature with **meaningful net-new UI** worth settling before the SDD. Skip backend/API/refactor/tooling work.

**Self-gate first.** Read `PRD.md`'s User Stories. If none imply a net-new or materially-changed screen — feature is API/backend/refactor only — stop, report `no_ui` ("nothing to prototype here"). A backend-heavy monorepo produces many such features; don't manufacture a screen the feature doesn't need.

## Argument

- `ticket_id` *(or `prd_path`)* — locates `…/{TICKET-ID}/PRD.md` and its sibling artifact folder. Mockup lands beside the PRD.
- `scope` *(optional)* — specific story / screen to focus on (e.g. `US-2`), instead of the whole feature's UI.

## Process

### 1. Read the stories and anchor to the real app

Read `PRD.md` — User Stories and Acceptance Criteria are the **capability list** the mockup must demonstrate; Step 4's capability walk gates settle on it. Then **anchor to the real frontend** — use every layer available, best evidence first:

1. **Design-system catalog** (`/afk:design-system` output), when the service has one — the component vocabulary: copy its verified tokens and card markup verbatim; never re-derive what a fidelity-checked card already settled.
2. **The running app**, when reachable — the fidelity reference: screenshot the app shell and the page archetype nearest the feature (Step 4's fidelity pass diffs against these). Markup and computed styles lifted from the live DOM beat anything re-derived from source.
3. **Frontend source** — find the sibling checkout's components, layout shell, and design tokens; delegate the read to an `afk-reader` subagent returning a vocabulary digest — component names, token values, layout idioms, each with file citations — per `DELEGATION.md` (plugin root); the crafting loop mocks from the digest.

While anchoring, also map the feature's **neighborhood**: the existing screen(s) each story enters from, and the existing screens the new UI navigates to. Capture the app shell (global nav, header, breadcrumbs) and those neighbor pages in the anchor evidence — Step 2 embeds the shell and stubs the neighbors.

The mockup must look like **your app** — a generic Tailwind page teaches nothing about whether the feature fits the product. No anchor available at all? Say so, proceed with a neutral style, flag the missing anchor.

### 2. Open the canvas

Write a **self-contained HTML file** — no build step, no framework runtime, real data shapes inlined as fixtures, inline vanilla JS making the page **drivable**: clicks navigate, forms validate, actions mutate the in-page fixture state. The user must be able to *use* the feature, not inspect a picture of it. Write it to the ticket's `prototype/` working folder (sibling to `PRD.md`). Render per LAVISH.md (RP-8, playbook `input`) — **mandatory per LAVISH.md's Primary-path rule**; the mockup is a drivable artifact, so that file's Drivable-artifacts rules bind (live controls carry `data-lavish-action`, `window.lavish` calls guarded). Fallback (render failure) per that file: tell the user the path, they open it in a browser and refresh as you edit. Either way keep the file openable-as-`file://` always (inline the CSS, no imports needing a server) — portability is what makes the fallback free.

**In situ, not floating.** Every screen renders inside a replica of the real app shell — global nav, header, breadcrumbs, the correct nav item active — and the neighborhood is wired: Step 1's entry-point and navigation-target pages appear as **shallow stubs** (real layout, static fixture content, one level deep — links beyond the flow dead), so the user reaches each new screen by clicking from where they'd really start and leaves it to where they'd really land. Familiarity is the instrument: a user who feels at home in the prototype notices exactly what's off; a floating mockup hides the very seams — entry, navigation, shell fit — where gaps live.

Screens to open with depend on how settled the direction is:

- **Direction unclear** → open with **2–3 structurally-different sketches** on one page, switchable by a `?variant=` param and a small floating bar. "Structurally different" = different layout, information hierarchy, primary affordance — *not* three recolours of the same card grid. Divergence is the point; if two come out similar, redo one.
- **Direction roughly known** → go straight to a **single mockup** and refine.

While diverging, each sketch needs only its primary flow drivable; the full capability list gets simulated after convergence (Step 3).

### 3. Craft, react, update — the loop

A **conversation**, not a spec hand-off:

1. The user reacts in plain language — "table's too dense" — in chat, or pinned in the rendered session (element annotations, text selections, embedded feedback controls — delivered by `poll` per LAVISH.md). An element-pinned note beats prose when the screen has three tables; treat both channels as one conversation.
2. You **edit the HTML** to match; re-render per LAVISH.md (fallback: tell them to refresh).
3. Repeat. Ask the questions a designer would when the prompt is thin — "where does this open from?", etc. — and answer them *in the mockup*, not in prose. Walking a real screen routinely surfaces PRD gaps (a state with no story, an action with no outcome); name it when it does — it may route back to `/afk:to-prd`.

Converge from divergence: once a direction wins, collapse to the single chosen mockup and polish *that* into the full simulation — every capability on Step 1's list drivable: state transitions, validation, empty/loading/error/success states, permission variants the stories imply, real density. A capability the user can't reach by clicking isn't demonstrated — build the interaction, not a caption describing it. Keep it throwaway-grade (no tests, no real mutations — point actions at inline stubs); fidelity is in the *look and the simulated behavior*, not working plumbing.

### 4. Settle — walk, verify, then capture

When the design feels right, two gates before anything durable is written:

- **Capability walk.** Drive every PRD User Story and Acceptance Criterion through the mockup by clicking — each story started from its entry-point stub, never by opening the new screen directly — trigger the action, watch the state change, reach the states the story implies. Exhaustive: every story and AC either has an interactive path you just walked, or is logged in `PROTOTYPE.md` as not-demonstrated with a reason. A capability you couldn't click is a gap — build it or log it, never skip it silently.
- **Fidelity pass.** Put the mockup **side by side** with Step 1's live screenshots (or catalog cards when no running app was reachable) and fix what differs — shell and nav chrome, dimensions, control variants, density, spacing, type, exact component treatment. Live render wins, and fidelity claims are never overclaimed — doctrine per `skills/afk/design-system/SKILL.md` (Boundary).

Then the **won direction** becomes the artifact; losing scaffolding is thrown away.

- Keep the **chosen HTML** as `…/{TICKET-ID}/prototype/<screen>.html`. Delete the losing variants and the switcher — they rot fast and confuse the next reader.
- Write **`…/{TICKET-ID}/PROTOTYPE.md`** (sibling to `PRD.md`): screens settled; the **capability coverage table** (each User Story / AC → the interactive path demonstrating it, or the logged gap + reason); the **fidelity basis** (`live-verified` against which URL / `catalog` / `source-only`); design decisions made and *why* (so `/afk:grill-solution` and `/afk:grill-verification` inherit them); any PRD gaps surfaced; a link to the chosen HTML. (Canonicality: see Boundary.)
- Upsert the `Prototype` row (`chosen {date}`) in the sibling `INDEX.md` per `skills/afk/to-prd/INDEX-FORMAT.md`.

### 5. Share — Claude Design push (opt-in)

To share the prototype on Claude Design, follow [CLAUDE-DESIGN-PUSH.md](CLAUDE-DESIGN-PUSH.md).

### 6. Report

End with one line:

```
OUTCOME: <status> — <one-line summary> [pushed: <url|no>]
```

| Status | Meaning |
|---|---|
| `crafted` | A mockup passed both settle gates; `PROTOTYPE.md` + chosen HTML written. |
| `no_ui` | The feature has no net-new screens; nothing to prototype. |
| `prd_gap` | A settled mockup surfaced a PRD gap worth a `/afk:to-prd` revisit; name it. |
| `other` | Unexpected stop. |

Precedence: a run that both settles a mockup and surfaces a PRD gap reports `prd_gap` — the gap is the actionable outcome; the mockup artifacts are still written.

## Boundary (Hard rules)

- **Local file is the source of truth.** `PROTOTYPE.md` + the in-repo HTML are canonical and version-controlled. The `claude.ai/design` project is an opt-in **share/preview mirror** in the user's account — delete it there, nothing in the repo is lost. Never treat the hosted copy as the record.
- **Throwaway scaffolding, durable decision.** Variant files and the switcher are disposable, pruned on settle. The *decision* (which design, and why) survives in `PROTOTYPE.md`.
- **Touches no tracker, merges nothing.** Local-first like the rest of the design layer — no Jira, no GitLab, no branch. Only network egress is the **opt-in** Claude Design push, only when the user asks.
- **Simulate the behavior, mock the backend.** Every interaction runs client-side against inline fixtures — actions respond, state transitions play out — but no real mutations, no real DB, no server. A static picture where the PRD promises behavior is an unfinished mockup. The question is "what is this like to *use*", answered before the SDD; "does the backend work" is verification's job, far downstream.
- **Anchor, don't invent a parallel design language.** Mock from the real frontend's components and tokens, in situ — inside the shell, entered from and exiting to its real neighbor pages. A prototype that ignores the existing app produces a design engineering then has to throw away. Neighbor stubs stay shallow: the prototype simulates the feature's neighborhood, never rebuilds the app.

## Next

A settled mockup feeds two downstream skills:

- **`/afk:grill-solution`** — UX decisions captured in `PROTOTYPE.md` are inputs to the architecture interview (a modal vs a page, an inline edit vs a wizard — all have SDD consequences).
- **`/afk:grill-verification`** — the mockup is the concrete screen its **UI journeys** trace to. Designing journeys against a real screen instead of an imagined one separates a verification plan that holds from one that drifts.

If the mockup surfaced a PRD gap, route back to `/afk:to-prd` first.

---

Visual extraction of the existing frontend into a shared, team-accessible `claude.ai/design` catalog lives in **`/afk:design-system`**. Run it once per service to seed the catalog Step 1 anchors to first; Step 5's share push lands ticket mockups as cards in the same project.
