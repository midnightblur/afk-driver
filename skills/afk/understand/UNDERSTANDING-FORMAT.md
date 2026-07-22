# UNDERSTANDING-FORMAT.md — the understanding-artifact format contract

One home for the shape of the understanding artifact. Three consumers read this file: the **generator** (synthesises sections into the shell copy), the **skeptic verifier** (judges a draft against the self-eval criteria before emit), and the **mission-control panel** (parses only the meta header). This is the module's public interface (SDD §8 row "format contract") — implement it here unmodified; every other skill points at this file, never restates it.

An artifact is one self-contained HTML file per subject: a **frozen copy of the shell template asset** with the section payload and meta header injected. All rules below are pass/fail — the skeptic verify pass grades a draft against them and blocks emit on any failure (ADR-0003).

## Subjects

The artifact teaches one **subject**; three subject families share the format:

| Subject | Material | SEC-4 | Where "diff" reads as |
|---|---|---|---|
| **feature** — a shipped feature (plan dir) | derived feature diff + journal + review records | present when a notable deviation exists | the derived diff range |
| **mr** — a GitLab MR | the MR diff (+ discovered spec, MR description/commits) | absent (no plan to deviate from) | the MR diff |
| **code** — an existing code area (`path:`/`symbol:`) | the current code in scope, no diff | absent | the in-scope file set |

Everything below applies to all three unless a rule names a subject.

## Genericity rule (applies to shell + generated content)

No real feature, ticket, product-symbol, or person name appears in this format contract, in the shell template asset's boilerplate content, or in any illustrative example either file carries. Illustrative content is obviously hypothetical (toy data, placeholder names). The Stop-hook genericity gate scans only markdown; the shell asset's HTML content is governed by **this stated rule**, unenforced by hook — a known, accepted gap (SDD §5 doctrine; SDD §14 accepted finding "Genericity enforcement gap"). The generator honours it for injected section content too.

## Section shapes — SEC-1..SEC-6

Section **kinds** appear in this fixed order. The shell's tour renders **one step per `<section>` element**; every kind is exactly one section **except SEC-3, which spans one section per walkthrough group** — a large subject gets a paced tour, not one wall-of-scroll step. SEC-1, SEC-2, SEC-3, SEC-5, and SEC-6 are always present (SEC-6's quiz is generated every time — taking it is opt-in, per ADR-0002); SEC-4 is present **exactly when** the subject is a feature **and** a notable deviation exists (omitted entirely otherwise — the only conditional kind). Each kind's **Rules** are pass/fail criteria the skeptic checks.

### SEC-1 — Background & objectives
- **Content:** three blocks, in order:
  1. **Learning objectives** — 2–5 "after this walkthrough you can …" bullets stating concrete abilities (things the reader could do or explain), not topic labels.
  2. **Dual-depth background** — a collapsible **system-context layer** (orients a teammate new to the area) plus a **subject-specific layer** (this change's / this code's local context). Sourced from existing code and the SDD/PRD where they exist.
  3. **Key concepts & constraints** — every term of art the subject leans on, each defined in one line (sourced from the SDD, the service's domain `GLOSSARY.md`, or the code), plus the invariants/constraints the code must uphold.
- **Rules (pass/fail):**
  - Objectives present and concrete — a reader can check each one off after the recap.
  - Dual-depth present; the system-context layer is **collapsed / skippable by default** — a reader already fluent in the area skips it without scrolling past it.
  - Key concepts & constraints block present; every term of art used anywhere in the artifact is defined **here or at its first use** (the jargon-before-use criterion).

### SEC-2 — Intuition
- **Content:** the essence of the subject conveyed with concrete **toy-data examples** and a small reusable diagram family. The single mental model is stated in **one memorable sentence** — SEC-3 groups and the SEC-5 recap re-invoke it, so the same idea recurs in different forms. Sourced from the SDD and the diff/code.
- **Rules (pass/fail):**
  - Comes **before any code** — intuition precedes the SEC-3 walkthrough.
  - The mental-model sentence is present and re-invocable (short enough to repeat verbatim).
  - **No ASCII diagrams.** Diagrams are the reusable visual family (rendered), never ASCII-art boxes.
  - Interactive elements, when used, follow the interactivity rules below (SEC-2/SEC-3 are the only kinds that carry them).

### SEC-3 — Walkthrough (one section per group)
- **Content:** a literate, syntax-highlighted walkthrough grouped by **seam/flow**, one `<section>` (= one tour step) per group. Sourced from the diff (feature/mr), the in-scope code (code), `plan/TRACE.md` and the SDD seams (feature).
- **Rules (pass/fail):**
  - Grouped by **seam/flow, never file-path / alphabetical order** — a reviewer can name the seam each group maps to (AC-006). Feature groups key to the SDD's seam names where an SDD exists; mr/code subjects use synthesizer-derived flow names in plain domain terms (SDD §6).
  - **Stated ordering rationale:** the first walkthrough section names, in one line, the order the groups follow (entry-point-first, request-flow order, or dependency order) — and the groups follow it. High level descends to detail; no group assumes material from a later group.
  - **Overview before code:** every group opens with a plain-language paragraph — what this seam does and why it changed (or, code subjects, why it matters) — before its first code block.
  - **Full coverage:** every changed file (feature/mr) / every in-scope file (code) either appears in a walkthrough group **or** is listed as skipped-trivial with its one-clause reason (see the trivial-file predicate). Nothing is silently dropped.
  - **Misconception callouts:** where the evidence supports one, a group carries a "where you'd naturally go wrong" callout — the wrong assumption a reader would plausibly bring, and why the code defies it. Feature subjects mine remediated review findings, adversary reports, and fix records; mr/code subjects ground callouts in actual code behaviour. Every callout cites its source; zero callouts is a legal count — never invent a gotcha.
  - **Formative check (per group, optional):** a group may close with **one** check question (same shape as a quiz question, injected as that section's own quiz-data block; equally opt-in and unrecorded). A group that introduces a new mechanism should carry one.

### SEC-4 — Deviations (feature subjects only)
- **Content:** notable divergences from plan → landed. Sourced from `plan/JOURNAL.md`, `plan/review/` (`*.outcomes.json`, `PATTERN-DEBT.md`), and the subtask contracts.
- **Rules (pass/fail):**
  - **Notable-only**, and the section is **omitted entirely when clean** — a purely as-planned feature yields no SEC-4 (AC-005, AC-007; ADR-0003). mr/code subjects never carry one.
  - Every entry is drawn from the closed **notable-deviation** enumeration below and carries its source citation. No editorial additions.

### SEC-5 — Recap
- **Content:** one screen that closes the loop: the SEC-2 mental-model sentence restated, the SEC-1 objectives re-walked as a "you can now …" checklist, and the 3–7 load-bearing takeaways.
- **Rules (pass/fail):**
  - The mental model is restated **faithfully** — same model, no new framing.
  - Every SEC-1 objective reappears; no objective is silently dropped.
  - **No new material** — a fact appearing first in the recap fails.

### SEC-6 — Quiz
- **Content:** N application-style multiple-choice questions over SEC-1..5 content, client-side scored with immediate feedback.
- **Rules (pass/fail):**
  - **Opt-in**, no result recorded anywhere (ADR-0002). See the quiz rules below for question shape and count.
  - Correct-answer position and length are randomized.

## Trivial-file predicate (SDD §6 row "Trivial-file")

State verbatim in the artifact where SEC-3 lists skips:

> **Trivial-file = a mechanical or derivable diff** — generated code, lockfiles, version bumps, translation keys, or formatting-only churn.

(Code subjects read "diff" as "file" — generated or boilerplate files in scope skip the same way.) Each skipped file is **listed individually with a one-clause reason** (e.g. "lockfile — regenerated", "translation keys — mechanical"). A file is either walked in SEC-3 or listed here; never omitted from both. Guardian: skeptic verify vs this contract.

## Notable-deviation predicate — closed enumeration (SDD §6 row "Notable-deviation"; PRD AC-007)

SEC-4 entries come **only** from this closed set — no editorial additions:

1. A **park / retry event** recorded in `plan/JOURNAL.md`.
2. A **remediated blocking review finding** (a `critical`/`high` review finding that was fixed — derived by an id-join of the finding JSON and the outcomes JSON in `plan/review/`).
3. A **contract clause satisfied differently** than the subtask contract specced.
4. A **pattern-debt entry** (`plan/review/PATTERN-DEBT.md`).

Purely as-planned subtasks yield **no** entry; if none of the four exist, SEC-4 is absent. Guardian: skeptic verify.

## Machine-readable meta-header grammar — `afk-understanding` {#afk-understanding}

The artifact embeds exactly one machine-readable meta element. **This is the mission-control panel's only parse target** — the panel reads nothing else from the artifact (SDD §4 row "Machine-readable header"; SDD §8 panel row). This grammar and the panel's parser are a **lockstep pair**: a change to the element name or its content fields is a same-commit change to the panel's parse code.

- **Element name:** `afk-understanding` — a single meta element (e.g. `<meta name="afk-understanding" …>` or an equivalent element the shell asset stamps) carrying the fields below as its content.
- **Content fields (both mandatory):**
  1. **generated date** — the date the artifact was generated.
  2. **diff SHA range** — feature: the derived diff range (branch tip stamped at generation; retro per SDD §4 / ADR-0004); mr: the MR's diff range; code: the repo `HEAD` SHA at generation (the degenerate range — the code state the artifact describes).
- **Well-formedness:** the element is present and both fields are populated. Guardian: mechanical check (pre-verify); the panel is the consuming parser and returns its `Absent(reason)` case rather than raising when the header is missing or malformed.

Separately from the parse target, the page `<header>` carries a **`data-source-hint`** attribute — the subject locator (plan-dir path, MR URL, or `path:`/`symbol:` argument) — which the shell's ask-the-teacher affordance embeds in the prompt it assembles, so an aided session knows where the sources live. Not part of the panel's grammar.

## Interactive elements (SEC-2 / SEC-3)

Interactive elements are sourced from the **interactive-walkthrough widget catalog** — the agent-invoked utils skill at `skills/utils/interactive-walkthrough/SKILL.md`, which owns the widget set, each widget's flow shape, and the copy-inline constraints. The obligation runs **both ways**:

- **Reach for the widget:** when a concept in SEC-2/SEC-3 is flow-shaped or state-shaped and a catalogued widget matches, **copy that widget inline per that skill's contract** — prose alone for such a concept fails the representation-match criterion below. The shell must stamp `data-theme` so copied widgets follow the artifact's dark/light family.
- **Earn the bespoke:** write bespoke JS only when no catalogued widget fits the flow shape, and only when it clears the interactivity-justification bar below (SDD §14 row "Interactive-walkthrough widget catalog").

## Anti-slop self-eval criteria — the skeptic's checklist {#interactivity-justification}

The qualitative criteria a fresh-context skeptic subagent judges a draft against before emit (PRD AC-009; ADR-0003; SDD §10). An artifact failing any criterion is **revised once, then re-checked**; still failing → fail-soft (nothing emitted). The skeptic returns a per-criterion verdict:

1. **Size cap — artifact ≤ 500 KB** (single HTML file, measured at the mechanical check; SDD §10). Over budget fails.
2. **One mental model per section** — each section develops a single mental model; a section juggling several unrelated models fails.
3. **Interactivity-justification bar** — every bespoke micro-sim / interactive element earns its place: it justifies why no catalogued widget fit and what comprehension it adds. Decorative or unjustified interactivity fails.
4. **Representation match** — a flow- or state-shaped concept explained as prose alone, where a catalogued widget (or, failing that, a rendered diagram) fits, fails. The complement of criterion 3: 3 kills decoration, 4 kills missed teaching.
5. **Objectives & recap integrity** — SEC-1 objectives are concrete abilities; the SEC-5 recap restates the mental model faithfully, re-walks every objective, and introduces no new material.
6. **Jargon before use** — every term of art is defined in SEC-1's key-concepts block or at its first use; a term used before defined fails.
7. **Ordering rationale** — the walkthrough's stated group order (entry-point / request-flow / dependency) is named and actually followed; each group opens plain-language before code.
8. **Grounded misconceptions** — every "where you'd naturally go wrong" callout cites its source (a review/adversary/fix record, or the code behaviour itself); an invented gotcha fails.

Mechanical criteria (offline / zero external requests, full coverage, meta-header well-formedness, size) are checked deterministically **before** the skeptic wave (ADR-0003); the criteria above are the skeptic's judgement.

## Quiz rules (SDD §6 row "Quiz"; PRD AC-008; ADR-0002)

- **Stem:** application-style (tests applying the change, not recalling a fact).
- **Options:** exactly **one correct answer + three distractors**.
- **Explanation:** mandatory on every question, and names the section it re-tests (the quiz is the artifact's second pass over the same knowledge).
- **Randomization:** the correct answer's **position and length** are randomized (the correct option is not systematically first, nor systematically the longest).
- **Count:** **5 by default** (auto mode); in standalone the prompted count is honoured.
- **Opt-in and untracked:** taking the quiz is voluntary; it is scored client-side with immediate feedback and **no result is written to any file, MR, or tracker** (ADR-0002).
- **Formative checks** (SEC-3 group closers) follow the same question shape and the same opt-in/untracked rule — at most one per group.
