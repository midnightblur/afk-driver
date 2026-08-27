---
name: understand
description: Generates an interactive HTML learning artifact for a shipped feature, a GitLab MR, or a code area. Use via /afk:understand {subject} when the user wants to learn or be walked through a feature, MR, or code.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# afk:understand — the code-learning artifact

Generate one **team-shareable, self-contained interactive HTML** file per subject — a frozen copy of the shell template asset with an authored section payload and machine-readable header injected. It teaches the code **as it is** (the real diff / the real files), not the plan.

The artifact's shape is not defined here. Its subject families, section model, predicates, quiz rules, self-eval criteria, and meta-header grammar are one-homed in [`UNDERSTANDING-FORMAT.md`](UNDERSTANDING-FORMAT.md) (the module's public interface); the boilerplate chrome + named injection slots are the checked-in [`shell-template.html`](shell-template.html). This skill is the **orchestration spine** that fills them.

## Subject

One argument selects the subject family (the format contract's "Subjects" table):

- **feature** — `{plan-dir}` (a feature's plan directory, `{spec-dir}/plan/`). The spec dir is its parent; the artifact lands at `{spec-dir}/understanding/index.html`, the ticket index at `{spec-dir}/INDEX.md`.
- **mr** — a GitLab MR URL (matches `https?://.*/-/merge_requests/`).
- **code** — `path:{repo-relative-path}` or `symbol:{ClassOrFunction}`. A symbol matching multiple files → list the matches, ask which (or take a `path:` to disambiguate).

Ambiguous argument → ask. mr/code intake mechanics are in "MR / code intake" below; the feature pipeline is unchanged by them.

## Modes — one pipeline, two parameterizations

The same pipeline runs both modes; they differ only in **prompting** and **commit behaviour** (PRD Catalog B).

- **M-1 auto** — **feature subjects only**; invoked non-interactively with defaults: **quiz 5, standard background depth, zero prompts**. Ends in one committed, pushed docs-only commit (below). The invoking context has already authorized commit + push for this run; never open a prompt — convert any would-be question into a fail-soft outcome.
- **M-2 standalone** — a human runs `/afk:understand {subject}` directly (the only mode for mr/code subjects). **Prompt up front** for quiz size and background depth, then generate. Writes the files and **never commits** — the working tree is the user's.

Downstream-blind: this skill never names or assumes which stage invoked it. What it needs (mode, defaults-vs-prompt, whether commit is pre-authorized) arrives at invocation.

## Public interface (SDD §8 row "understand skill spine") — implement unmodified

`/afk:understand {subject}` with the outcome statuses of the §3 invocation contract table:

| Outcome | When |
|---|---|
| `generated` | artifact written; auto mode also committed the docs-only unit and pushed; journal `generated` (feature subjects) |
| `failed({reason})` | any pipeline stage fails-soft; nothing (or only a local uncommitted artifact) written; journal `failed({reason})` (feature subjects); **never a park** |
| `no_derivable_diff` | the diff-derivation ladder exhausted (feature, M-2 retro); refuse, write nothing (see below) |
| `refused(scope_too_large)` | mr/code subject over the size gate; refuse, write nothing, name the narrowing move (`path:` a subtree / a tighter symbol) |

## Process

Delegate every heavy read (diff/code digestion, journal/review mining, context gathering) to `afk-reader` subagents per [`DELEGATION.md`](../../../DELEGATION.md) (plugin root); synthesis inherits the session model. Everything that can fail does so **before** anything is written — the write (+ commit, feature auto mode) is the terminal atomic unit.

1. **Resolve subject, inputs, and mode.**
   - *feature:* read `{plan-dir}/PLAN.md`, the parent PRD/SDD (section sourcing + seam names), `{plan-dir}/JOURNAL.md`, `{plan-dir}/TRACE.md`, and `{plan-dir}/review/` (`*.md`, `*.outcomes.json`, `PATTERN-DEBT.md`).
   - *mr / code:* run the intake below (fetch/scope + size gate + optional spec discovery).
   - Auto mode uses defaults; standalone prompts for quiz size + background depth first.

2. **Derive the code scope.** *feature:* the diff-derivation ladder below (the git-CLI seam, ADR-0004) — on exhaustion, **refuse**: `no_derivable_diff`, nothing written, naming the missing input. *mr:* the fetched MR diff. *code:* the resolved file set at repo `HEAD` (no diff).

3. **Three parallel digest subagents** (one message, per `DELEGATION.md`), **1 retry each**, any failure after its retry → whole generation fails-soft:
   - **diff/code digest** — *feature/mr:* the diff grouped by seam/flow (SEC-3 source), full-coverage list incl. skipped-trivial candidates. *code:* the in-scope code grouped by flow — entry points → module boundaries → key classes → end-to-end scenarios — same full-coverage list. Either way: note footguns, edge cases, and surprising behaviour as **misconception fodder** (cited).
   - **deviation mining** (*feature only*) — mines `UNDERSTANDING-FORMAT.md`'s closed notable-deviation set (SEC-4) from `{plan-dir}/review/`, the journal, and `PATTERN-DEBT.md`. The mined records double as **misconception sources** for SEC-3 callouts. A mined record is a **lead, never evidence** — the journal is never amended when a later decision reverses it. Resolve every mined deviation naming a mechanism, field, column, or code path against the code at the taught tip: open the symbol, or `git log` the file for a later reversal. Report a reversed one as the pair `substituted X, reversed by {commit}`; label one you cannot resolve `unverified: {reason}`.
   - **context digest** — system-context + subject-specific background, the key concepts & constraints (terms from the SDD / the service's domain `GLOSSARY.md` / code; invariants from both), and the intuition essence (SEC-1/SEC-2) from existing code + whatever specs exist (SDD/PRD; mr: discovered spec, MR description + commits).

4. **Synthesize into a copy of the shell.** Copy `shell-template.html` verbatim; author the sections per `UNDERSTANDING-FORMAT.md` (SEC-1..SEC-6; SEC-3 as one `<section>` per walkthrough group) and inject them into its slots (sections mount, header chips + `data-source-hint`, quiz JSON, and the meta header). **Strip HTML comments before matching any slot** — anchor on the real element, never on its first textual occurrence; the same binds the step-5 checks that read the emitted file back. Emit the **meta header** with the generated date + the subject's SHA range per the `afk-understanding` grammar. Interactive elements per the format contract's "Interactive elements" section; execution: filled DATA, unique ids per instance, one `<style>` block per widget type.

5. **Mechanical checks** (deterministic, before the skeptic — ADR-0003): fully offline / zero external request targets; full coverage (every changed/in-scope file walked or listed skipped-trivial); size cap (≤ 500 KB); meta-header well-formedness. Any fail → revise (step 7).

6. **Fresh-context skeptic emit gate.** A **fresh-context subagent that has not seen this run's synthesis** judges the draft against the format contract's qualitative self-eval criteria (`UNDERSTANDING-FORMAT.md#interactivity-justification`) and returns per-criterion verdicts (ADR-0003).

7. **Revise at most once.** On any mechanical or skeptic failure, revise once and re-run steps 5–6. Still failing → **fail-soft**: write nothing, journal `failed(self_eval)` (feature subjects).

8. **Write (+ commit, feature auto mode).**
   - *feature:* write `understanding/index.html` and upsert the feature's `INDEX.md` `Understanding` row (`generated {date}`). **In auto mode**, land these two as ONE **docs-only commit** — path-guarded to the artifact directory + the ticket index file, nothing else in the commit — pushed under the invoker's existing authorization, **no rebase ever**. A push rejection → **advisory failure**: `failed(push_rejected)`, the commit is left local for the user to push (never force, never rebase). **In standalone mode**, write the files and **do not commit**.
   - *mr / code:* write `${CLAUDE_JOB_DIR:-<temp dir>}/understanding-{slug}-{YYYYMMDD-HHMMSS}/index.html` (slug = `mr{IID}`, or the sanitized path/symbol). When the subject maps to a ticket spec folder (discovered spec at `specs/**/{KEY}/`, or the caller passed `save:{spec-dir}`), **offer** to copy it to `{spec-dir}/understanding/{slug}.html` so future readers find it — copy on yes; never commit.

9. **Journal and report.** Feature subjects: append the journal event (below). All subjects: emit the terminal report (below).

## Diff derivation ladder (feature subjects — git-CLI seam, SDD §9b, ADR-0004)

First hit wins:

1. **Live feature branch exists** → three-dot diff against the remote target (`git diff origin/{target}...{feature-branch}`, `{target}` = the branch the feature merges into). Never the local `master` ref — no one fast-forwards it in a worktree, so it silently widens the scope to other teams’ merged work.
2. **Else** → union of the journal's pushed ranges: from the **first pushed SHA's parent** (`{first}^`) through the **last pushed SHA**. Complete by construction — every push is journaled.
3. **Nothing derivable** (ranges rewritten or absent) → **refuse**: write nothing and report `no_derivable_diff`, **naming the missing input**.

`plan/TRACE.md` SHAs map commits to seams for the SEC-3 walkthrough grouping **only** — they are **never** used to derive the range (they are criterion-curated, not the complete commit set).

## MR / code intake

- **mr:** validate `glab` (`glab --version` + `glab auth status`; missing/unauth → `failed(glab_unavailable)` with the `glab auth login` hint). Fetch via the bundled [`scripts/fetch-mr.sh`](scripts/fetch-mr.sh) → `mr.json` + `mr.diff` in `${CLAUDE_JOB_DIR:-/tmp}`. **Spec discovery** (best-effort, enriches SEC-1): cascade against the MR description — ticket URL regex → markdown-link key → free-text key → commit messages; a key whose repo has `specs/**/{KEY}/PRD.md` → read it; else Jira MCP / WebFetch; all misses → proceed, SEC-1 falls back to the MR description + commits. Draft/closed/merged MRs all proceed.
- **code:** resolve the scope against the current repo (or a caller-named `--repo` path) **read-only**. Empty `path:`/`symbol:` → error out.
- **Size gate (both):** diff lines (mr) or in-scope LOC (code): `<5000` silent, `5000–15000` warn and continue, `>15000` → `refused(scope_too_large)`.
- **Hard rules (both):** static read only — never run app/build/tests; never modify the user's worktree; never invent symbols/files/line numbers — cite paths from the diff or repo verbatim.

## Reporting

Follow [`REPORTING.md`](../../../REPORTING.md) (plugin root): the terminal `OUTCOME:` line, an `In plain terms:` sentence, and a pointer to the artifact (feature subjects: also `{plan-dir}/JOURNAL.md`). `OUTCOME:` stays last.

Journal writer/event grammar is one-homed in [`to-subtasks/JOURNAL-FORMAT.md`](../to-subtasks/JOURNAL-FORMAT.md): this skill is the writer **`understand`** with subject token **`understanding`** and events `generated` / `failed({reason})` — both registered there in the same commit as this file (FRESHNESS same-commit rule). mr/code subjects have no plan journal — they report only.
