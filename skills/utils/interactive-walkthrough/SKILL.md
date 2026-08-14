---
name: interactive-walkthrough
description: Interactive HTML walkthrough widgets — notched flow slider, branching simulator, overlap gantt, before/after comparator, predict-then-reveal. Use when emitting an HTML page walking a human through a sequential, branching, concurrent, or state-change process, or a point readers predict wrong — copy the matching template and fill its data contract.
user-invocable: false
---

# Interactive walkthrough widgets

Embeddable, self-contained HTML+CSS+JS widgets for explaining a process to a
human interactively instead of as prose or a static diagram. Static diagrams
(Mermaid etc.) are owned by `skills/utils/draw-charts/SKILL.md` — this skill is
only for *interactive* walkthroughs.

## Pick the widget

| Flow shape | Widget | Template |
|---|---|---|
| Linear sequence (steps always in the same order) | Notched slider — drag or click a notch to jump to any step; card shows the step's actor, goal, result | `templates/flow-slider.html` |
| Branching (decisions, optional steps, states, failure exits) | Step simulator — Next/Back through nodes, decision nodes fork on the reader's choice, breadcrumb trail records the path | `templates/branching-simulator.html` |
| Concurrent / pipelined (things overlapping in time or across lanes) | Overlap gantt — labeled lanes with positioned bars on a shared time grid | `templates/overlap-gantt.html` |
| State change (a before → after the reader should compare) | Before/after comparator — tabbed two-state view; "what changed & why" notes light up on the after state | `templates/before-after.html` |
| Point of likely surprise (behaviour readers predict wrongly) | Predict-then-reveal — reader commits to a prediction, then the actual behaviour + why appears; ungraded, nothing recorded | `templates/predict-reveal.html` |

A branching flow with only one or two trivial forks reads better as a slider
with the fork noted in the step card. A flow of ≤3 steps needs no widget —
write prose.

## How to use a template

1. Copy the template file's contents into the page being authored (inline —
   never link or fetch it).
2. Fill the `DATA` constant at the top of its `<script>` — the data contract is
   the comment block above it. Real content only, no placeholders left behind.
3. Multiple instances of the same widget on one page: give each copy a unique
   id where the template's header comment says so; CSS/prefixes are shared, so
   keep exactly one `<style>` block per widget type.
4. Verify by opening the page in a browser: every step/node/lane reachable,
   both color themes legible, no horizontal page scroll.

## Constraints (baked into the templates — keep them intact when editing)

- **Self-contained.** No CDN scripts, external fonts, or remote images —
  artifact pages run under a CSP that blocks every external host.
- **Theme-aware.** Tokens are CSS custom properties defined per widget with
  light defaults, `@media (prefers-color-scheme: dark)` overrides, and
  `:root[data-theme="dark"]` / `:root[data-theme="light"]` overrides so a host
  page's theme toggle wins in both directions. Restyle by changing token
  values, not by adding literal colors to rules.
- **No page-level horizontal scroll.** Wide content scrolls inside the
  widget's own `overflow-x:auto` wrapper.
- **Motion is optional.** Transitions are minimal and disabled under
  `prefers-reduced-motion: reduce`.
- **Host-page hooks.** Each render calls `window.__annotate(card)` if the host
  page defines it (tooltip/term annotators re-run on dynamic content); absent
  is fine.
