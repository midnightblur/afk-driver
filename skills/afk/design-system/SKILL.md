---
name: design-system
description: Mirrors a service's live frontend into a team-shareable claude.ai/design catalog. Use on /afk-toolkit:design-system to seed a service's catalog or refresh after token/component drift.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# afk:design-system — mirror a service's live UI into a shared catalog

One-time (periodically refreshed) extraction of a service's real frontend into a hosted, team-accessible `claude.ai/design` catalog. A prototype run then composes from the catalog instead of re-reading the frontend each time; the team gets one link showing what the app looks like.

**Per-service, not per-feature.** Run against one frontend checkout (a service's UI), not a ticket. Output: a durable catalog many later features reference.

## When it applies

- **Seeding** a new service with a real, running frontend worth mirroring.
- **Refreshing** an existing catalog after the frontend's design tokens or core components drifted (mirror stale, not wrong by design).

Skip a service with no meaningful UI, or one you don't intend to anchor prototypes to.

## Arguments

- `frontend_path` — frontend checkout to mirror (e.g. `…/billing-ui`). `node_modules` must be installed.
- `live_url` — URL of the **running app** (e.g. `http://proxy/dev/financial-org-structure/`). This skill profiles and verifies against the live render, not just source — **required, not optional**. **If not supplied, ask before profiling** ("what URL is the running app at?"). Only if the user confirms no running instance exists do you fall back to code-only — then stamp every card and the README "fidelity: source-only, not verified against a live render" so the gap is never hidden.
- `project` *(optional)* — an existing Claude Design project to refresh. Omit on first run; the skill reuses-or-creates the service's design-system project.

## The coverage model — archetype-complete

A real app is dozens of routes and 100+ components. **Reduce the app to its repeating shapes**; cover each shape once, never one card per route:

- **Foundations** — extracted tokens: colour palette (brand, semantic, grey ramp, entity accents), type scale, spacing/shape. One card each.
- **The full primitive + overlay library** — every reusable input, select, picker, toggle, table, dialog, menu, drawer, chip, notification the app's component layer exposes. Cover exhaustively — it's what mockups compose from.
- **The app-shell + navigation chrome** — the single layout shell (header, sidebar, page container), menu, breadcrumbs, tabs, page header, global search.
- **Each page archetype, once** — list/management, detail, create/edit, dashboard, reports-hub + one representative report, approvals, bulk, admin, workspace. A reader drills into any specific screen from these.
- **Each domain as one representative instance** — not all six domains' list pages; one, labelled as the pattern the others follow.

Aim for a few dozen cards covering *everywhere reachable* by pattern, not a card-per-route. When you collapse N screens to one archetype, say so in that card's subtitle.

## Process

### 1. Profile the frontend — from BOTH the code and the live app

Two passes, both required:

- **Code pass.** Enumerate the reachable UI — routes, pages, components, layouts — enough to see the archetypes (parallel `Explore` agents help on a large app). Identify the **framework + component library** (Quasar/Vue, MUI/React, Material/Angular, …) and **where the real design tokens live** — the theme config / SCSS variables / CSS custom properties / Tailwind config the app actually compiles. That file, not anything you compute, is ground truth for token *values*.
- **Live pass.** Open `live_url` in a real browser (Playwright/browser MCP, or a screenshot tool) and **walk the reachable screens** — signature screen, each page archetype, app shell, dense components. Capture screenshots. Here you see what the *running* app looks like, including whatever a shared/3rd-party component kit renders that never appears in local CSS. No `live_url` → see Arguments.

When the passes disagree, resolve per Boundary ("live render wins").

### 2. Extract tokens as ground truth — and verify, don't eyeball

Pull palette, type scale, spacing, radius, control heights from the real token source into a `tokens.css` mirror. **Do not trust hand-computed hex or "what the SCSS looks like it does"** — framework defaults and brand overrides interact in ways static reading misses. Disagreement → resolve per Boundary ("live render wins").

### 3. Reduce to the card set

Apply the coverage model to the Step 1 profile: list foundations, component library, chrome, page archetypes, one-per-domain representatives. This list *is* the catalog scope — write it down (a README in the catalog) before authoring.

### 4. Author the cards — consistent, self-contained, verified

Each card is a **standalone HTML file, openable as `file://`** (inline CSS, no build, real data shapes as fixtures). **First line must be the card marker:**

```html
<!-- @dsCard group="GROUP_NAME" -->
```

The marker's `group` buckets cards (Foundations · Form controls · Actions · Data display · Overlays · Navigation · Patterns, or whatever shapes your service has). Keep a **shared boilerplate** — font import, body reset, heading/subtitle styles — identical across cards so the catalog reads as one system.

Authoring a few dozen cards is parallel work: hand each builder agent an **identical "KIT"** — verified tokens, conventions (Step 5's findings), boilerplate — so independently-authored cards stay consistent instead of each agent re-deriving (and diverging on) the same hex. Spawn mechanics + each builder's return contract follow `DELEGATION.md` (plugin root).

**Fidelity check — compare each card to the LIVE app, side by side.** Reference is **a screenshot of the real running screen at `live_url`**, not the card's own render, not the framework's static CSS. Per high-risk card: screenshot the matching live screen (from Step 1's live pass, or navigate now), screenshot the card, **diff by eye** — header heights, control density, spacing, exact fill/underline/tooltip treatment, how a shared component kit paints. Fix the card to the live pixel, re-shoot. A card never put next to the live app is **not verified — say so on it.** Verify variant, style, and copy-transform mismatches against the live app — none reliably visible from stylesheet source alone.

Spot-check at least the highest-risk cards (app shell + each page archetype + densest components + anything a 3rd-party/internal component library styles); full-screen patterns reuse already-verified atoms.

*Secondary tool, not a substitute:* a local harness mounting the framework's own production build from `node_modules` with brand token vars renders isolated atoms against real framework CSS without navigating to their live screens. It renders *your* markup — never what the live app's component wrappers do (disagreements: see Boundary) — and harness + screenshots are **dev-only**, never published.

### 5. Publish to Claude Design (DesignSync)

To publish the catalog to Claude Design, follow [PUBLISH.md](PUBLISH.md).

### 6. Document and report

Leave a **README in the catalog** recording: the scope decision (archetype list + what each stands in for), the fidelity basis (**which `live_url` was walked, which cards were pixel-compared to it, what that caught** — plus any cards still marked source-only), and **how to re-extract** (re-run this skill with `frontend_path` + `live_url` after a token/component change — don't hand-edit drift into the cards). Source of truth: the frontend code; fidelity reference: the running app; the cards mirror both.

End with the layered report per `REPORTING.md` (plugin root) — headline, one jargon-free `In plain terms:` sentence, then artifact pointers — stating the fidelity basis honestly:

```
OUTCOME: <status> — <n cards across m groups> · fidelity: <live-verified|source-only> [project: <url>]
In plain terms: <what happened and what the reader can now do with the catalog — no workflow jargon>
Catalog: <catalog dir / README path> [· project: <url>]
```

| Status | Meaning |
|---|---|
| `seeded` | A new service catalog was built and published. |
| `refreshed` | An existing catalog was re-extracted and re-pushed. |
| `no_ui` | The service has no UI worth mirroring. |
| `other` | Unexpected stop. |

`fidelity: live-verified` only if the high-risk cards were pixel-compared to the running app; otherwise `source-only` — and say which cards still need a live pass.

## Boundary (Hard rules)

- **The frontend code is the source of truth; the catalog is a mirror.** When the app's tokens or components change, re-extract — never hand-edit drift into the cards, never treat the hosted catalog as authoritative over the code.
- **The live render wins for appearance; the code wins for token values.** The live rendered pixel wins over computed hex and over the static harness — verify against the LIVE app, not the SCSS. Never overclaim: don't write "matches the real app" / "verified against the app" unless you actually browsed it — reading `.vue`/SCSS is "faithful to the source", a weaker, different claim.
- **Local-first, one egress.** Only network call is the Claude Design push; no Jira, no GitLab, no merge. The published project lives in the user's account, a share/preview mirror — deleting it loses nothing in the repo.
- **Archetype-complete, not screen-complete.** Cover every *shape* once; refuse a card per route. Exhaustive only on the reusable component library.

## Next

Once the catalog exists, **`/afk-toolkit:prototype`** anchors to it — its Step 1 "anchor to the real app" composes from these hosted cards instead of re-reading the frontend each run, and its opt-in share push lands ticket mockups as cards in the same project. Refresh the catalog with this skill whenever the frontend's design language moves.
