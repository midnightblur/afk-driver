# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This repo is the **`afk` Claude Code plugin** — a chain of skills implementing Matt Pocock's AFK ("async-from-keyboard") workflow, adapted to Nakisa's Jira + GitLab + Maven monorepo. There is **no autonomous driver**: every stage is run interactively by a human in a Claude Code session. The chain takes a feature from raw idea → grilled requirements → PRD → architecture → SDD → sliced Jira SubTasks → execution. You invoke each stage yourself, including `/afk:execute`, which you run once per SubTask in a session on the parent Enhancement's branch.

The repo contains only the skills (`skills/<name>/SKILL.md`) and the plugin manifests. The *work* the chain drives is Java/Maven inside a sibling core-services checkout, with Jira as the tracker (`mcp__jira__*`) and GitLab as the SCM (`glab`).

There is no Python package, no test suite, and no build step — editing a `SKILL.md` and running `/reload-plugins` is the entire dev loop.

## Plugin layout & install

The plugin lives at `.claude-plugin/plugin.json` (manifest) + `.claude-plugin/marketplace.json` (local marketplace) + `skills/<name>/SKILL.md` (one dir per skill). Install once via `/plugin marketplace add <repo>` + `/plugin install afk@afk-marketplace`, then persist via `enabledPlugins` in `~/.claude/settings.json`. After editing any `SKILL.md`, run `/reload-plugins` to pick up changes without restarting. See `README.md` for the full install snippet.

## The skills

- **Orientation**: `/afk:start` (pipeline map + entry-point router).
- **Mandatory chain**: `/afk:to-prd` → `/afk:to-ticket` → `/afk:to-subtasks` → `/afk:execute`. `/afk:to-ticket` is the one step that publishes the local PRD to the parent Enhancement (the only design-chain skill that writes to the tracker). You run `/afk:execute` yourself, once per labelled SubTask.
- **Optional design layer**: `/afk:grill-requirements` (raw-idea grilling; maintains `GLOSSARY.md` only — no decision records) → `/afk:to-prd` (PRD + requirement ADRs under `.../adr/requirements/`; **local artifacts only — does not touch the tracker**) → `/afk:architect-grill` (top-down L1→L8 interview) → `/afk:to-sdd` (writes `SDD.md` + per-decision design ADRs under `.../adr/design/` sibling to the PRD; owns the `## SDD` section of the parent Enhancement description) → `/afk:to-design-brief` (optional digest: synthesizes PRD + SDD + ADRs into a 1-2 page `DESIGN-BRIEF.md` for stakeholder review and pre-SDD reading; owns the `## Design Brief` section). Recommended for new complex features; skip for small bugs / refactors / tooling.
- **Tooling**: `/afk:tdd` (red-green-refactor doctrine, invoked from `/afk:execute` Step 5).

`/afk:to-subtasks` slices in **cited mode** when an SDD is present (each SubTask references binding SDD sections + ADRs and carries a Conflict procedure block) and in **uncited mode** otherwise (PRD-only; human-gated per ticket).

## Lockstep: the SubTask Markdown contract

The SubTask Markdown contract is the load-bearing interface between `/afk:to-subtasks` (which emits it) and `/afk:execute` (which parses it). If you add, rename, or change a section, update **both** `skills/prd-to-subtasks/SKILL.md` (Step 6 emitter) and `skills/afk-go/SKILL.md` (Step 1 parser) in the same commit — they live in the same repo specifically so this lockstep is enforced by a single commit. Likewise the outcome status set: if you broaden it, update the status list in `/afk:execute` Step 13 and any skill that references it.

The contract's 7 base sections: `## Goal / Scope / Acceptance / Test command / Parent PRD / Blocked by / Implementation Notes`. Cited mode adds five: `## Design refs / Produces / Parent SDD / Consumes / Conflict procedure`.

## Cited-mode contract

The contract is enforced at three checkpoints — drift is impossible to ship without surfacing somewhere:

1. **Slicing time (`/afk:to-subtasks` Step 8).** Two passes:
   - **Graph validation** — every `## Consumes` line resolves to a `## Produces` bullet on a SubTask earlier in rank order. Forward refs / orphan consumers / multi-producer collisions all bounce.
   - **Anchor quality** — every `## Produces` `{grep-anchor}` is checked against (a) a forbidden-generic-token list (`class`, `interface`, `void`, `function`, `def`, `method`, `struct`, `enum`, `type`, `record`); (b) length ≥12 chars; (c) trial `ctx_search` against `{file}` at HEAD must return ≤1 match. Ambiguous anchors that would fail-open at runtime are rejected at declaration time.
2. **Consumer preflight (`/afk:execute` Step 2).** Reads `## Design refs` and `## Parent SDD` to load binding SDD/ADR context. Then for each `## Consumes` line `{PRODUCER-KEY} {file}#{grep-anchor}`, reads `{file}` and greps for `{grep-anchor}`. A miss exits `contract_mismatch` carrying the producer key (no retry; comment on both consumer and producer SubTask). A binding-decision break exits `design_conflict` (no retry; routes to `/afk:architect-grill`).
3. **Producer self-preflight (`/afk:execute` Step 10).** Right before declaring `success`, the SubTask greps each of its own `## Produces` anchors on the branch. A miss exits `produces_drift` (no retry; route the human to fix the impl OR re-emit the slice). Without this step, signature drift would surface only at the next consumer's preflight — surfacing the failure on the wrong ticket.

`## Produces` is mandatory on every cited SubTask, even leaves with no consumer — it doubles as the reviewer's cheat-sheet, the producer-self-preflight grep target, AND the next SubTask's consumer-preflight grep target.

## Section ownership invariants (don't violate)

- **Parent Enhancement description**: the PRD content is authored by `/afk:to-prd` (on disk) and published into the parent — as the full inlined body in native Jira formatting (ADF), inside an AFK-managed sentinel block — by `/afk:to-ticket`, which preserves all content outside that block. `## SDD` (when present) is owned by `/afk:to-sdd`. `## Design Brief` (when present) is owned by `/afk:to-design-brief`. `## Implementation Notes (auto-maintained)` is spliced by `/afk:execute` (idempotent — preserves human prose around the block). Other prose belongs to the human.
- **MR description**: the `<!-- afk:subtasks:start --> ... <!-- afk:subtasks:end -->` block is auto-maintained by `/afk:execute`; everything outside is preserved verbatim.
- **SubTask description**: the SubTask Markdown contract must round-trip losslessly. If you add a section, update both the `/afk:to-subtasks` emitter and the `/afk:execute` parser together (see Lockstep above).

## Skill ↔ human ownership split (CR/Merge)

`/afk:execute` drives the in-flight transitions (`Dev-Designing`, `Dev-Developing`), the TDD loop, commits, push, MR checklist, and the parent Implementation Notes splice — then **stops**. It does NOT fire `Request CR & Merge` or merge the MR. The human reviews the Draft MR and performs the `Dev-CR/Merge` transition (and any gate-field writes) out of band. Auto-merging is outside the skill's lane — preserve this boundary when editing `/afk:execute`.

## Tracker boundary

`/afk:to-prd` produces **local artifacts only** (PRD.md + requirement ADRs on disk); it does not create or update any Jira/GitLab issue. Publishing the PRD to the tracker is the job of **`/afk:to-ticket`**: it publishes the **full PRD content** into an **existing** parent ticket's description as native Jira formatting (ADF — Jira Cloud), with any `mermaid` blocks rendered to PNGs **locally**, attached, and embedded inline as media nodes (the verified media-UUID method; no diagram source leaves the network). It is **idempotent** — the PRD lives in an AFK-managed sentinel block, so re-running updates in place and replaces prior `afk-fig*` attachments rather than duplicating; content **outside** the managed block (product-owner prose) is preserved verbatim unless the existing description is barebone. The intricate formatting/diagram/merge work is codified in `skills/to-ticket/scripts/publish_prd.py` for deterministic behavior (it reads Jira creds from env or `~/.claude.json` and talks to the REST API directly, since attachment upload has no MCP tool). It deliberately **does not** create the parent (refuses without `parent_key`), sets **no label**, creates **no GitLab branch** (`/afk:execute` self-creates its branch), and publishes **PRD content only** — not the SDD/Design Brief. `/afk:to-ticket`, `/afk:to-subtasks`, and `/afk:execute` touch Jira directly; `/afk:to-prd` is the one upstream artifact skill that does not (it stops at disk). `/afk:to-sdd` and `/afk:to-design-brief` still splice their own `## SDD` / `## Design Brief` sections into the parent directly — only the PRD is routed through `to-ticket`.

## Conventions to keep

- **Branch names** must match the GitLab regex `^[a-z0-9][a-z0-9/\-\.]*$` — the `mvu/afk/{enh_id_lower}` pattern is load-bearing for `/afk:execute`'s push.
- **Two ADR tiers, separate subfolders.** Requirement-level ADRs (what/why) live in `.../{TICKET-ID}/adr/requirements/NNNN-*.md` and are owned by `/afk:to-prd`. Design-level ADRs (how) live in `.../{TICKET-ID}/adr/design/NNNN-*.md` and are owned by `/afk:to-sdd`. Numbering is local to each subfolder; the tiers never share numbering. The retired repo-wide `docs/adr/` is gone — all ADRs are ticket-local.

## Reference

- `README.md` — install, the chain map, and the per-skill summary.
- Parent ticket: P2P-1220 (Jira).
