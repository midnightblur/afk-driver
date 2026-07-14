# UNDERSTANDING-FORMAT.md — the understanding-artifact format contract

One home for the shape of the understanding artifact. Three consumers read this file: the **generator** (synthesises sections into the shell copy), the **skeptic verifier** (judges a draft against the self-eval criteria before emit), and the **mission-control panel** (parses only the meta header). This is the module's public interface (SDD §8 row "format contract") — implement it here unmodified; every other skill points at this file, never restates it.

An artifact is one self-contained HTML file per feature: a **frozen copy of the shell template asset** with the section payload and meta header injected. All rules below are pass/fail — the skeptic verify pass grades a draft against them and blocks emit on any failure (ADR-0003).

## Genericity rule (applies to shell + generated content)

No real feature, ticket, product-symbol, or person name appears in this format contract, in the shell template asset's boilerplate content, or in any illustrative example either file carries. Illustrative content is obviously hypothetical (toy data, placeholder names). The Stop-hook genericity gate scans only markdown; the shell asset's HTML content is governed by **this stated rule**, unenforced by hook — a known, accepted gap (SDD §5 doctrine; SDD §14 accepted finding "Genericity enforcement gap"). The generator honours it for injected section content too.

## Section shapes — SEC-1..SEC-5

The artifact contains **four or five** sections in this fixed order (PRD Catalog A). SEC-1..3 and SEC-5 are always present when their preconditions hold; SEC-4 is present **exactly when** a notable deviation exists (omitted entirely when clean). Each section's **Rules** are pass/fail criteria the skeptic checks.

### SEC-1 — Background
- **Content:** dual-depth. A collapsible **system-context layer** (orients a teammate new to the area) plus a **change-specific layer** (this feature's local context). Sourced from existing code and the SDD/PRD.
- **Rules (pass/fail):**
  - Dual-depth present: both the system layer and the change-specific layer.
  - The system-context layer is **collapsed / skippable by default** — a reader already fluent in the area skips it without scrolling past it.

### SEC-2 — Intuition
- **Content:** the essence of the change conveyed with concrete **toy-data examples** and a small reusable diagram family. Sourced from the SDD and the diff.
- **Rules (pass/fail):**
  - Comes **before any code** — intuition precedes the SEC-3 walkthrough.
  - **No ASCII diagrams.** Diagrams are the reusable visual family (rendered), never ASCII-art boxes.
  - Interactive elements, when used, follow the interactivity rules below (SEC-2/SEC-3 are the only sections that carry them).

### SEC-3 — Walkthrough
- **Content:** a literate, syntax-highlighted walkthrough of the feature diff, grouped by **seam/flow**. Sourced from the feature diff, `plan/TRACE.md`, and the SDD seams.
- **Rules (pass/fail):**
  - Ordered by **seam/flow, never file-path / alphabetical order** — a reviewer can name the seam each group maps to (AC-006). Walkthrough groups key to the feature SDD's seam names where an SDD exists; a retro feature without one uses synthesizer-derived flow names in plain domain terms (SDD §6).
  - **Full-diff coverage:** every changed file either appears in a walkthrough group **or** is listed as skipped-trivial with its one-clause reason (see the trivial-file predicate). No changed file is silently dropped.

### SEC-4 — Deviations
- **Content:** notable divergences from plan → landed. Sourced from `plan/JOURNAL.md`, `plan/review/` (`*.outcomes.json`, `PATTERN-DEBT.md`), and the subtask contracts.
- **Rules (pass/fail):**
  - **Notable-only**, and the section is **omitted entirely when clean** — a purely as-planned feature yields no SEC-4 (AC-005, AC-007; ADR-0003).
  - Every entry is drawn from the closed **notable-deviation** enumeration below and carries its source citation. No editorial additions.

### SEC-5 — Quiz
- **Content:** N application-style multiple-choice questions over SEC-1..4 content, client-side scored with immediate feedback.
- **Rules (pass/fail):**
  - **Opt-in**, no result recorded anywhere (ADR-0002). See the quiz rules below for question shape and count.
  - Correct-answer position and length are randomized.

## Trivial-file predicate (SDD §6 row "Trivial-file")

State verbatim in the artifact where SEC-3 lists skips:

> **Trivial-file = a mechanical or derivable diff** — generated code, lockfiles, version bumps, translation keys, or formatting-only churn.

Each skipped file is **listed individually with a one-clause reason** (e.g. "lockfile — regenerated", "translation keys — mechanical"). A changed file is either walked in SEC-3 or listed here; never omitted from both. Guardian: skeptic verify vs this contract.

## Notable-deviation predicate — closed enumeration (SDD §6 row "Notable-deviation"; PRD AC-007)

SEC-4 entries come **only** from this closed set — no editorial additions:

1. A **park / retry event** recorded in `plan/JOURNAL.md`.
2. A **remediated blocking review finding** (a `critical`/`high` review finding that was fixed — derived by an id-join of the finding JSON and the outcomes JSON in `plan/review/`).
3. A **contract clause satisfied differently** than the subtask contract specced.
4. A **pattern-debt entry** (`plan/review/PATTERN-DEBT.md`).

Purely as-planned subtasks yield **no** entry; if none of the four exist, SEC-4 is absent. Guardian: skeptic verify.

## Machine-readable meta-header grammar — `afk-understanding`

The artifact embeds exactly one machine-readable meta element. **This is the mission-control panel's only parse target** — the panel reads nothing else from the artifact (SDD §4 row "Machine-readable header"; SDD §8 panel row). This grammar and the panel's parser are a **lockstep pair**: a change to the element name or its content fields is a same-commit change to the panel's parse code.

- **Element name:** `afk-understanding` — a single meta element (e.g. `<meta name="afk-understanding" …>` or an equivalent element the shell asset stamps) carrying the fields below as its content.
- **Content fields (both mandatory):**
  1. **generated date** — the date the artifact was generated.
  2. **diff SHA range** — the diff range the artifact covers (branch tip stamped at generation; for a retro feature, the resolved range per SDD §4 / ADR-0004).
- **Well-formedness:** the element is present and both fields are populated. Guardian: mechanical check (pre-verify); the panel is the consuming parser and returns its `Absent(reason)` case rather than raising when the header is missing or malformed.

## Interactive elements (SEC-2 / SEC-3)

Interactive elements are sourced from the **interactive-walkthrough widget catalog** — the agent-invoked utils skill at `skills/utils/interactive-walkthrough/SKILL.md`, which ships three widget templates with fill-in DATA contracts: **flow slider** (linear flow), **branching simulator** (branching flow), **overlap gantt** (concurrent flow). When a flow shape in the change matches one of the three, **copy that widget inline** per that skill's contract (self-contained, theme-aware via CSS tokens + a `data-theme` override, unique element ids per instance, one `<style>` block per widget type per page). The shell must stamp `data-theme` so widgets follow the artifact's dark/light family.

Write **bespoke JS only when no catalogued widget fits the flow shape**, and only when it clears the interactivity-justification bar below (SDD §14 row "Interactive-walkthrough widget catalog").

## Anti-slop self-eval criteria — the skeptic's checklist {#interactivity-justification}

The **interactivity-justification** block: the qualitative criteria a fresh-context skeptic subagent judges a draft against before emit (PRD AC-009; ADR-0003; SDD §10). An artifact failing any criterion is **revised once, then re-checked**; still failing → fail-soft (nothing emitted). These are the criteria — the skeptic returns a per-criterion verdict:

1. **Size cap — artifact ≤ 500 KB** (single HTML file, measured at the mechanical check; SDD §10). Over budget fails.
2. **One mental model per section** — each section develops a single mental model; a section juggling several unrelated models fails.
3. **Interactivity-justification bar** — every micro-sim / interactive element earns its place: it either copies a catalogued interactive-walkthrough widget for a matching flow shape, or (bespoke JS) justifies why no widget fit and what comprehension it adds. Decorative or unjustified interactivity fails.

Mechanical criteria (offline / zero external requests, full-diff coverage, meta-header well-formedness, size) are checked deterministically **before** the skeptic wave (ADR-0003); the three qualitative criteria above are the skeptic's judgement.

## Quiz rules (SDD §6 row "Quiz"; PRD AC-008; ADR-0002)

- **Stem:** application-style (tests applying the change, not recalling a fact).
- **Options:** exactly **one correct answer + three distractors**.
- **Explanation:** mandatory on every question.
- **Randomization:** the correct answer's **position and length** are randomized (the correct option is not systematically first, nor systematically the longest).
- **Count:** **5 by default** (auto mode); in standalone the prompted count is honoured.
- **Opt-in and untracked:** taking the quiz is voluntary; it is scored client-side with immediate feedback and **no result is written to any file, MR, or tracker** (ADR-0002).
