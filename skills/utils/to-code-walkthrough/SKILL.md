---
name: to-code-walkthrough
description: Generate top-down narrative walkthrough of a GitLab MR or existing code module — caveman prose w/ mermaid diagrams. Layers TL;DR -> context -> architecture -> modules -> classes -> logic flow -> UI flow -> data model -> footguns. Use when user drops an MR URL asking to understand/explain/walk through the changes, or wants a tour of an existing codebase area (path: or symbol: prefix). Distinct from review-code (verdicts + findings) — this skill produces narrative understanding, no judgments.
---

# to-code-walkthrough

Top-down narrative walkthrough. Parallel per-layer agents. One markdown file. Mermaid for visuals. Caveman prose. Two modes: **MR** (URL) | **code** (path/symbol).

Purpose: reader understands the change w/o opening the code. Reviewer skim before diving. Onboarder tours module fast.

## Inputs

- **MR mode:** `<MR_URL>` (GitLab merge request).
- **Code mode:** `path:<repo-relative-path>` or `symbol:<ClassOrFunction>`.
- Preset: `quick` | `standard` | `deep`. Default `standard`.
- Filters: `skip L1,L2,...` | `only L3,L4,...`. Compose on preset.
- `--list-layers` -> print layers + aliases + presets, exit (no input needed).
- `--repo <path>` -> skip worktree prompt, use this path read-only.

## Layers (9)

Top-down. Each self-contained w/ stable anchor for cross-ref.

| ID | Layer | Asks | Default mermaid |
|---|---|---|---|
| L1 | `tldr` | What changes / why / blast radius | (none) |
| L2 | `context` | Ticket intent + business why (MR) or module purpose (code) | (none) |
| L3 | `architecture` | Non-obvious decisions, patterns, ADRs implied | (optional flowchart) |
| L4 | `modules` | New/changed/deleted modules + boundaries | `flowchart LR` |
| L5 | `classes` | Key classes/components — role, collaborators, place in flow | `classDiagram` (sparse) |
| L6 | `logic` | End-to-end flow per scenario | `sequenceDiagram` |
| L7 | `ui` | Screen flow + route map + state (frontend only, auto-skip if no FE files touched) | `flowchart` + `stateDiagram-v2` |
| L8 | `data` | Schema / DTO / event changes (auto-skip if none touched) | `erDiagram` |
| L9 | `footguns` | Clever bits, edge cases, do-not-refactor warnings | (none) |

Aliases: `tl;dr`->`tldr`, `ctx`->`context`, `arch`->`architecture`, `mods`->`modules`, `cls`->`classes`, `flow`->`logic`, `frontend`->`ui`, `schema`->`data`, `gotchas`->`footguns`.

Per-layer agent prompts: [LAYERS.md](LAYERS.md). Mermaid templates + tips: [DIAGRAMS.md](DIAGRAMS.md).

## Presets

| Preset | Layers | Use case |
|---|---|---|
| Quick (3) | L1 tldr, L4 modules, L5 classes | Skim small MR / quick orient |
| Standard (9, default) | All; L7 + L8 auto-skip if nothing touched | Typical MR / module tour |
| Deep (9 + multi-scenario L6) | All; L6 emits one sequenceDiagram per distinct scenario | Big/complex MR (multi-flow) |

Auto-suggest by diff size (MR mode): `<200` -> "Quick?", `>2000` -> "Deep?". Suggest only, never auto-switch. Skip if user passed preset/filter arg.

Filter rules:
- `skip X,Y` -> remove from preset.
- `only X,Y` -> **replace preset entirely**. Targeted re-runs.
- Unknown name -> exit w/ canonical list. Never silently drop.

## Workflow

0. **Helper short-circuit.** `--list-layers` in args -> print layers + aliases + presets, exit.
1. **Detect mode.** Arg matches `https?://.*/-/merge_requests/` -> MR mode. Starts w/ `path:` or `symbol:` -> code mode. Ambiguous -> ask.
2. **Validate.** MR mode: `glab --version` + `glab auth status`. Code mode: ensure `--repo` resolves or prompt.
3. **Fetch.** MR mode: `bash scripts/fetch-mr.sh <URL>` (bundled in this skill, resolved relative to the skill's base dir) -> `$CLAUDE_JOB_DIR/mr.json` + `mr.diff`. The helper is self-contained (needs only `glab` on PATH). Code mode: skip.
4. **Size gate.** MR diff lines or code subtree LOC: `<5000` silent, `5000-15000` warn, `>15000` refuse — require `only path:src/foo/**` or narrower symbol.
5. **Resolve repo path.** Same prompt as review-code (`Existing worktree path for {project}@{target_branch}?` -> validate / clone fresh / `skip` -> `diff-only`). **Strictly read-only** on user-owned repos. `diff-only` degrades L5/L7/L8/L9 (annotate sections w/ "(diff-only — code not consulted)").
6. **Discover spec** (MR mode only). Reuse review-code cascade against `mr.json.description`: URL regex `https?://[^\s)]+(atlassian\.net/browse/[A-Z]+-\d+|/issues/\d+)` -> markdown link `\[([A-Z]+-\d+)\]\([^)]+\)` -> free-text `[A-Z]+-\d+` -> commit messages. Key + repo has `specs/**/{KEY}/PRD.md` -> file. Else jira MCP / WebFetch. -> `$CLAUDE_JOB_DIR/spec.md`. Fail -> `spec_path=none`, mode flag `no-spec` (L2 falls back to MR description + commits).
7. **Auto-skip detection.** Glob changed paths for frontend (`*.vue`, `*.tsx`, `*.jsx`, `*.svelte`) -> include L7, else drop. Glob for schema/DTO/event signals (`*.sql`, `**/entity/**`, `**/dto/**`, `**/event/**`, `**/*Entity.java`, `**/*Dto.java`) -> include L8, else drop. `only` arg overrides auto-skip.
8. **Resolve layer list.** Preset -> `only` replaces -> `skip` removes -> auto-skip applies. Empty -> exit w/ `--list-layers` hint.
9. **Spawn layer agents.** Single message, parallel Agent calls. One per layer. All `subagent_type: general-purpose`. See "Subagent prompt" below.
10. **Aggregate.** Collect outputs in layer order (L1 -> L9). Stitch:
    - Header: mode + ticket (if any) + MR title + branches + generated timestamp + layers run.
    - TOC: anchor links to each layer section.
    - Sections in order.
    - Footer: cross-ref to `review.md` if exists in `$CLAUDE_JOB_DIR/`; closing line.
    Final caveman pass: aggregator scans for filler ("just", "really", "basically", "we can see that") and trims. Technical terms / mermaid blocks / code blocks **never** modified.
    Save to `$CLAUDE_JOB_DIR/walkthrough-{slug}-{YYYYMMDD-HHMMSS}.md`. Slug = `mr{IID}` (MR mode) or sanitized path/symbol (code mode, replace `/` and special chars w/ `-`).
11. **Closing line:**
    ```
    Walkthrough: $CLAUDE_JOB_DIR/walkthrough-<slug>-<TS>.md
    Read top-down. Mermaid renders in any MD viewer w/ mermaid support.
    Upload manually to Jira if companion to a review handoff (glab/atlassian-token unavailable).
    ```

## Subagent prompt

Each Agent call: `subagent_type: general-purpose`. Prompt carries layer-specific bits only:

```
role: {LAYER_ID} ({LAYER_NAME})
mode: {mr | code}
source:
  diff_path: $CLAUDE_JOB_DIR/mr.diff (mr mode) or "none"
  mr_path:   $CLAUDE_JOB_DIR/mr.json (mr mode) or "none"
  spec_path: $CLAUDE_JOB_DIR/spec.md or "none"
  repo_path: <abs path> or "diff-only"
  target_paths: <subset for code mode, or "all changed files" for mr mode>
budget: ~{N} lines narrative + ~{M} diagrams
style: caveman (drop articles, fragments OK, arrows for causality, one word when enough, technical terms exact, code blocks + mermaid syntax verbatim)

layer_prompt:
{paste matching layer section from LAYERS.md verbatim}

mermaid_guidance:
{paste matching diagram section from DIAGRAMS.md verbatim, only for diagram types this layer uses}

output_format:
- Section starts with `## {LAYER_NAME}` followed by anchor `<a id="{LAYER_ID}"></a>`.
- Mermaid in ```mermaid fenced blocks.
- Code in ```{lang} fenced blocks.
- Cite file paths inline as `path/to/file.ext:LINE` when referencing specific code.
- No preamble. No postamble. No "in this section we will..." narrator voice.
- Self-contained — cross-refs use anchor IDs (e.g. "see [classes](#L5)") not "as we saw above".
```

## Hard rules

- Static read only. Never run app / build / tests.
- Never modify user's cwd / worktree. Read-only on user-owned repos. Writes only inside `$CLAUDE_JOB_DIR`.
- Caveman prose throughout; technical terms + code + mermaid syntax verbatim.
- Mermaid blocks only — never ASCII boxes/arrows for diagrams.
- Each layer self-contained w/ stable anchor `L1..L9` for cross-ref.
- Never invent symbols / files / line numbers. Cite paths from diff or repo verbatim.
- Always parallel fan-out in single message — never sequential layer agents.
- Aggregator never inserts judgments ("looks risky", "should refactor") — that's review-code's job.

## Edge cases

- `glab` missing/unauth -> exit w/ install/login hint (MR mode only).
- Repo too large to shallow-clone -> `diff-only`, warn (L5/L7/L8/L9 degrade w/ annotation).
- Binary / generated files -> layer agents skip, note in section.
- MR has no spec -> L2 falls back to MR description + commits (mode flag `no-spec`).
- Code mode w/ empty `path:` / `symbol:` -> exit w/ error.
- Symbol matches multiple files -> list matches, ask which (or `path:<file>` to disambiguate).
- Mermaid render failure (downstream) -> not our problem; document in skill that diagrams may need touch-up in pathological cases.
- MR draft / WIP -> proceed (walkthrough is useful pre-merge).
- MR closed/merged -> proceed (post-hoc tour still valuable).

## The bundled fetcher

MR mode calls `scripts/fetch-mr.sh`, **bundled inside this skill** (sibling to `SKILL.md`), so the skill is self-contained — no dependency on a repo-root `scripts/` home or on any other skill. The helper needs only `glab` on PATH; it writes `mr.json` + `mr.diff` to `$CLAUDE_JOB_DIR`.

If `glab` is missing or unauthenticated, the fetcher exits non-zero with a clear hint (`glab auth login`). Code mode (`path:` / `symbol:` input) is fully standalone — no fetcher needed.
