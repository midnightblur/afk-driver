---
name: design-system
description: Build (or refresh) a team-shareable `claude.ai/design` catalog that mirrors a service's **live frontend look** — extracts the real design tokens as ground truth and reduces the app to archetype-complete standalone HTML cards, fidelity-checked by browsing the live running app — so `/afk:prototype` and the team craft mockups against the real app instead of generic Tailwind. A per-service setup skill, not part of the per-feature chain; reads the running app and pushes to Claude Design (otherwise local); the frontend code stays the source of truth. Use when the user runs `/afk:design-system`, or wants to seed a new service's catalog or refresh it after the frontend's tokens/components drift — before mocking with `/afk:prototype`.
---

# afk:design-system — mirror a service's live UI into a shared catalog

One-time (then periodically refreshed) extraction of a service's real frontend into a hosted, team-accessible `claude.ai/design` catalog. Once it exists, a prototype run composes from the catalog instead of re-reading the frontend from scratch each time, and the whole team has one link showing what the app actually looks like.

**Per-service, not per-feature.** Run against a frontend checkout (`payable-ui`, the next service's UI, …), not a ticket. Output: a durable catalog many later features reference.

## When it applies

- **Seeding** a new service with a real, running frontend worth mirroring.
- **Refreshing** an existing catalog after the frontend's design tokens or core components drifted (mirror stale, not wrong by design).

Skip for a service with no meaningful UI, or one whose look you don't intend to anchor prototypes to.

## Arguments

- `frontend_path` — the frontend checkout to mirror (e.g. `…/payable-ui`). `node_modules` must be installed.
- `live_url` — URL of the **running app** (e.g. `http://proxy/dev/financial-org-structure/`). This skill profiles and verifies against the live render, not just source — so the URL is **required, not optional**. **If not supplied, ask before profiling** ("what URL is the running app at?"). Only if the user confirms no running instance is available do you fall back to code-only — then you MUST stamp every card and the README "fidelity: source-only, not verified against a live render" so the gap is never silently hidden.
- `project` *(optional)* — an existing Claude Design project to refresh. Omit on first run; the skill reuses-or-creates the service's design-system project.

Both inputs are load-bearing and catch **different** classes of error: code is ground truth for *token values and which component is used*; the live app is ground truth for *how it actually renders* — runtime spacing, density, and anything an internal/3rd-party component library (e.g. a shared `ess-component` kit) contributes beyond local CSS. Static reading cannot see the second; that's the gap that ships wrong-looking cards.

## The coverage model — archetype-complete

A real app is dozens of routes and 100+ components. **Reduce the app to its repeating shapes** and cover each shape once; never emit one card per route:

- **Foundations** — extracted tokens: colour palette (brand, semantic, grey ramp, entity accents), type scale, spacing/shape. One card each.
- **The full primitive + overlay library** — every reusable input, select, picker, toggle, table, dialog, menu, drawer, chip, notification the app's component layer exposes. This part you *do* cover exhaustively — it's what mockups compose from.
- **The app-shell + navigation chrome** — the single layout shell (header, sidebar, page container), menu, breadcrumbs, tabs, page header, global search.
- **Each page archetype, once** — list/management, detail, create/edit, dashboard, reports-hub + one representative report, approvals, bulk, admin, workspace. A reader drills into any specific screen from these.
- **Each domain as one representative instance** — not all six domains' list pages; one, clearly labelled as the pattern the others follow.

Aim for a few dozen cards covering *everywhere reachable* by pattern, not a card-per-route. When you collapse N screens to one archetype, say so in that card's subtitle so the reader knows what it stands in for.

## Process

### 1. Profile the frontend — from BOTH the code and the live app

Two passes, both required:

- **Code pass.** Enumerate the reachable UI — routes, pages, components, layouts — enough to see the archetypes (parallel `Explore` agents help on a large app). Identify the **framework + component library** (Quasar/Vue, MUI/React, Material/Angular, …) and **where the real design tokens live** — the theme config / SCSS variables / CSS custom properties / Tailwind config the app actually compiles. That file, not anything you compute, is ground truth for token *values*.
- **Live pass.** Open `live_url` in a real browser (the `/run` or `verify` skill, Playwright, or a screenshot tool) and **walk the reachable screens** — the signature screen, each page archetype, the app shell, the dense components. Capture screenshots. This is where you see what the *running* app looks like, including whatever a shared/3rd-party component kit renders that never appears in local CSS. If `live_url` wasn't given, **stop and ask for it** (see Arguments) — don't profile from code alone and pretend it's verified.

When the two passes disagree, the **live render wins** for appearance, the **code wins** for token values.

### 2. Extract tokens as ground truth — and verify, don't eyeball

Pull palette, type scale, spacing, radius, control heights from the real token source into a `tokens.css` mirror. **Do not trust hand-computed hex or "what the SCSS looks like it does"** — framework defaults and brand overrides interact in ways static reading misses. The verified palette wins over any agent-computed value; when two extractions disagree, the rendered one is right (see Step 4).

### 3. Reduce to the card set

Apply the coverage model above to the Step 1 profile: list foundations, component library, chrome, page archetypes, and one-per-domain representatives. This list *is* the catalog scope — write it down (a README in the catalog) before authoring.

### 4. Author the cards — consistent, self-contained, verified

Each card is a **standalone HTML file, openable as `file://`** (inline CSS, no build, real data shapes as fixtures). **First line must be the card marker:**

```html
<!-- @dsCard group="GROUP_NAME" -->
```

The marker's `group` is how the catalog buckets cards (Foundations · Form controls · Actions · Data display · Overlays · Navigation · Patterns, or whatever shapes your service has). Keep a **shared boilerplate** — font import, body reset, heading/subtitle styles — identical across cards so the catalog reads as one system.

Authoring a few dozen cards is parallel work: hand each builder agent an **identical "KIT"** — verified tokens, conventions (Step 5's findings), boilerplate — so independently-authored cards stay visually consistent instead of each agent re-deriving (and diverging on) the same hex.

**Fidelity check — compare each card to the LIVE app, side by side.** The reference is **a screenshot of the real running screen at `live_url`**, not the card's own render and not the framework's static CSS. For each high-risk card: screenshot the matching live screen (from Step 1's live pass, or navigate now), screenshot the card, and **diff them by eye** — header heights, control density, spacing, exact fill/underline/tooltip treatment, how a shared component kit actually paints. Fix the card to match the live pixel, then re-shoot. A card you never put next to the live app is **not verified — say so on it.**

In payable-ui this caught: inputs are the transparent *underline* variant, not a grey `filled` fill; errors render as a red **tooltip to the right**, not an inline message; button labels default to UPPERCASE (toolbar buttons opt out with `no-caps`). None reliably visible from the SCSS alone.

Spot-check at least the highest-risk cards (app shell + each page archetype + the densest components + anything a 3rd-party/internal component library styles); full-screen patterns reuse already-verified atoms.

*Secondary tool, not a substitute:* a local harness that mounts the framework's own production build (e.g. `quasar.umd.prod.js` + `quasar.prod.css` from `node_modules`) with the brand token vars renders an isolated component without clicking to its live screen. Useful for atoms — but it renders *your* markup against real framework CSS, so it still can't show what the live app's own component wrappers do. When the harness and the live screen disagree, the **live screen wins.** The harness and screenshots are **dev-only** — never published.

### 5. Publish to Claude Design (DesignSync)

To publish the catalog to Claude Design, follow [PUBLISH.md](PUBLISH.md).

### 6. Document and report

Leave a **README in the catalog** recording: the scope decision (the archetype list and what each stands in for), the fidelity basis (**which `live_url` was walked, which cards were pixel-compared to it, and what that caught** — plus any cards still marked source-only), and **how to re-extract** (re-run this skill with `frontend_path` + `live_url` after a token/component change — don't hand-edit drift into the cards). Source of truth is the frontend code; the running app is the fidelity reference; the cards are a mirror of both.

End with one line, stating the fidelity basis honestly:

```
OUTCOME: <status> — <n cards across m groups> · fidelity: <live-verified|source-only> [project: <url>]
```

| Status | Meaning |
|---|---|
| `seeded` | A new service catalog was built and published. |
| `refreshed` | An existing catalog was re-extracted and re-pushed. |
| `no_ui` | The service has no UI worth mirroring. |
| `other` | Unexpected stop. |

`fidelity: live-verified` only if the high-risk cards were pixel-compared to the running app; otherwise `source-only` — and say which cards still need a live pass.

## Boundary (Hard rules)

- **The frontend code is the source of truth; the catalog is a mirror.** When the app's tokens or components change, re-extract — never hand-edit drift into the cards and never treat the hosted catalog as authoritative over the code.
- **Verify against the LIVE app, not the SCSS — and never overclaim.** A card not put side by side with the running screen at `live_url` is a guess, and must be labelled one. The live rendered pixel wins over computed hex and over the static harness. Do not write "matches the real app" / "verified against the app" unless you actually browsed it — reading `.vue`/SCSS is "faithful to the source", a weaker, different claim.
- **Local-first, one egress.** The only network call is the Claude Design push; no Jira, no GitLab, no merge. The published project lives in the user's account and is a share/preview mirror — deleting it loses nothing in the repo.
- **Archetype-complete, not screen-complete.** Cover every *shape* once; refuse to emit a card per route. Exhaustive only on the reusable component library.

## Next

Once the catalog exists, **`/afk:prototype`** anchors to it — its Step 1 "anchor to the real app" composes from these hosted cards instead of re-reading the frontend each run, and its opt-in share push lands ticket mockups as cards in the same project. Refresh the catalog with this skill whenever the frontend's design language moves.
