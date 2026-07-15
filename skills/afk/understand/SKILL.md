---
name: understand
description: Generates one self-contained interactive HTML understanding artifact for a shipped feature — dual-depth background, intuition, seam-ordered diff walkthrough, notable plan-deviations, opt-in quiz — synthesized from the feature's actual diff, journal, and review records. Use when a human runs `/afk:understand {plan-dir}` on a Ready or already-shipped feature, or when invoked non-interactively with defaults to document a feature at ship time.
---

# afk:understand — post-ship feature understanding artifact

Generate one **team-shareable, self-contained interactive HTML** file per feature — a frozen copy of the shell template asset with an authored section payload and machine-readable header injected — written to `{spec-dir}/understanding/index.html`. It explains the implementation **as built** (the real diff), not the plan.

The artifact's shape is not defined here. Its section model, predicates, quiz rules, self-eval criteria, and meta-header grammar are one-homed in [`UNDERSTANDING-FORMAT.md`](UNDERSTANDING-FORMAT.md) (the module's public interface); the boilerplate chrome + named injection slots are the checked-in [`shell-template.html`](shell-template.html). This skill is the **orchestration spine** that fills them.

## Argument

`{plan-dir}` — a feature's plan directory (`{spec-dir}/plan/`). The spec dir is its parent; the artifact lands at `{spec-dir}/understanding/index.html`, the ticket index at `{spec-dir}/INDEX.md`.

## Modes — one pipeline, two parameterizations

The same pipeline runs both modes; they differ only in **prompting** and **commit behaviour** (PRD Catalog B).

- **M-1 auto** — invoked non-interactively with defaults: **quiz 5, standard background depth, zero prompts**. Ends in one committed, pushed docs-only commit (below). The invoking context has already authorized commit + push for this run; never open a prompt — convert any would-be question into a fail-soft outcome.
- **M-2 standalone** — a human runs `/afk:understand {plan-dir}` directly. **Prompt up front** for quiz size and background depth, then generate. Writes the files and **never commits** — the working tree is the user's.

Downstream-blind: this skill never names or assumes which stage invoked it. What it needs (mode, defaults-vs-prompt, whether commit is pre-authorized) arrives at invocation.

## Public interface (SDD §8 row "understand skill spine") — implement unmodified

`/afk:understand {plan-dir}` with the outcome statuses of the §3 invocation contract table:

| Outcome | When |
|---|---|
| `generated` | artifact written; auto mode also committed the docs-only unit and pushed; journal `generated` |
| `failed({reason})` | any pipeline stage fails-soft; nothing (or only a local uncommitted artifact) written; journal `failed({reason})`; **never a park** |
| `no_derivable_diff` | the diff-derivation ladder exhausted (M-2 retro); refuse, write nothing (see below) |

## Process

Delegate every heavy read (diff digestion, journal/review mining, context gathering) to `afk-reader` subagents per [`DELEGATION.md`](../../../DELEGATION.md) (plugin root); synthesis inherits the session model. Everything that can fail does so **before** anything is written — the write + commit is the terminal atomic unit.

1. **Resolve inputs and mode.** Read `{plan-dir}/PLAN.md`, the parent PRD/SDD (for section sourcing + seam names), `{plan-dir}/JOURNAL.md`, `{plan-dir}/TRACE.md`, and `{plan-dir}/review/` (`*.md`, `*.outcomes.json`, `PATTERN-DEBT.md`). Auto mode uses defaults; standalone prompts for quiz size + background depth first.

2. **Derive the diff range** (the git-CLI seam, ADR-0004 — see the ladder below). On exhaustion, **refuse**: no derivable diff, nothing written (`no_derivable_diff`).

3. **Three parallel digest subagents** (one message, per `DELEGATION.md`), **1 retry each**, any failure after its retry → whole generation fails-soft:
   - **diff digest** — the derived feature diff, grouped by seam/flow (SEC-3 source), full-diff coverage list incl. skipped-trivial candidates.
   - **deviation mining** — the closed notable-deviation set (SEC-4). Blocking-remediated findings are derived by an **id-join of the review report JSON (severity per id) with the outcomes JSON (status per id)** in `{plan-dir}/review/` — the outcomes file alone cannot classify blocking-ness. Also mines journal park/retry events, contract-clause-satisfied-differently, and `PATTERN-DEBT.md` rows.
   - **context digest** — system-context + change-specific background (SEC-1) and the intuition essence (SEC-2) from existing code + SDD/PRD.

4. **Synthesize into a copy of the shell.** Copy `shell-template.html` verbatim; author SEC-1..SEC-5 per `UNDERSTANDING-FORMAT.md` and inject them into its slots (sections mount, header chips, quiz JSON, and the meta header). Emit the **meta header** with the generated date + the exact derived diff SHA range, per the `afk-understanding` grammar. Where a flow shape in the change matches a catalogued widget, **copy that interactive-walkthrough widget inline** per [`skills/utils/interactive-walkthrough/SKILL.md`](../../utils/interactive-walkthrough/SKILL.md) (filled DATA, unique ids per instance, one `<style>` block per widget type); bespoke JS only when no widget fits and it clears the format contract's interactivity-justification bar.

5. **Mechanical checks** (deterministic, before the skeptic — ADR-0003): fully offline / zero external request targets; full-diff coverage (every changed file walked or listed skipped-trivial); size cap (≤ 500 KB); meta-header well-formedness. Any fail → revise (step 7).

6. **Fresh-context skeptic emit gate.** A **fresh-context subagent that has not seen this run's synthesis** judges the draft against the format contract's qualitative self-eval criteria (`UNDERSTANDING-FORMAT.md#interactivity-justification`) and returns per-criterion verdicts (ADR-0003).

7. **Revise at most once.** On any mechanical or skeptic failure, revise once and re-run steps 5–6. Still failing → **fail-soft**: write nothing, journal `failed(self_eval)`.

8. **Atomic write + docs-only commit.** Write `understanding/index.html` and upsert the feature's `INDEX.md` `Understanding` row (`generated {date}`). **In auto mode**, land these two as ONE **docs-only commit** — path-guarded to the artifact directory + the ticket index file, nothing else in the commit — pushed under the invoker's existing authorization, **no rebase ever**. A push rejection → **advisory failure**: `failed(push_rejected)`, the commit is left local for the user to push (never force, never rebase). **In standalone mode**, write the files and **do not commit** — leave them as the user's working-tree change.

9. **Journal and report.** Append the journal event (below) and emit the terminal report (below).

## Diff derivation ladder (git-CLI seam — SDD §9b, ADR-0004)

First hit wins:

1. **Live feature branch exists** → three-dot diff against master (`git diff master...{feature-branch}`).
2. **Else** → union of the journal's pushed ranges: from the **first pushed SHA's parent** (`{first}^`) through the **last pushed SHA**. Complete by construction — every push is journaled.
3. **Nothing derivable** (ranges rewritten or absent) → **refuse**: write nothing and report `no_derivable_diff`, **naming the missing input**.

`plan/TRACE.md` SHAs map commits to seams for the SEC-3 walkthrough grouping **only** — they are **never** used to derive the range (they are criterion-curated, not the complete commit set).

## Reporting

Follow [`REPORTING.md`](../../../REPORTING.md) (plugin root): the terminal `OUTCOME:` line, an `In plain terms:` sentence, and a pointer to `{plan-dir}/JOURNAL.md`. `OUTCOME:` stays last.

Journal writer/event grammar is one-homed in [`to-subtasks/JOURNAL-FORMAT.md`](../to-subtasks/JOURNAL-FORMAT.md): this skill is the writer **`understand`** with subject token **`understanding`** and events `generated` / `failed({reason})` — both registered there in the same commit as this file (FRESHNESS same-commit rule).
