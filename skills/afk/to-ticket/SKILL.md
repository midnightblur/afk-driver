---
name: to-ticket
description: Publishes a finished PRD.md into its Jira parent as a requirements-level native-ADF ticket; also posts meeting summaries onto tickets and mints stub Enhancements for grill spinoffs. Use when PRD.md exists and the parent key is known.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

# afk:to-ticket — publish into the Jira ticket

Three independent modes writing to the configured tracker:

- **PRD mode** (below) — distill a finished `PRD.md` into a requirements-level ticket description and publish it into the parent Enhancement/Story/Bug as native **ADF**; engine [`scripts/publish_prd.py`](./scripts/publish_prd.py).
- **Meeting mode** ([jump](#meeting-mode--record-a-meeting-on-a-ticket)) — record a meeting on **any** ticket as a collapsible ADF `expand`; engine [`scripts/publish_meeting.py`](./scripts/publish_meeting.py).
- **Spinoff mode** ([jump](#spinoff-mode--mint-a-stub-for-deferred-work)) — mint a **new** stub Enhancement for work a grill deferred out of scope; no engine — the `tracker_create` MCP tool.

PRD and meeting mode both write **ADF** into an existing issue's description, are **idempotent** (re-run updates in place, never duplicates), and own **disjoint regions** so they never collide; their engines share creds + the Markdown→ADF mapping. Spinoff mode instead **creates** an issue — no description-region ownership, guarded against duplicates by the grill log (below).

## What it does / does not do (binding)

- **Publishes the distilled ticket description inline**, not a link or pointer, and not the raw PRD — the ticket's readers are the Product Owner and QA; content contract in "Distill `TICKET.md`" below.
- **Renders mermaid locally** — never via an external render service; no diagram source leaves the network. Method: [REFERENCE.md](REFERENCE.md).
- **Idempotent.** The published description lives inside an AFK-managed sentinel block; re-runs replace it and its figures in place (merge model: [REFERENCE.md](REFERENCE.md)). History lives in comments — a re-publish posts the requirements delta as an issue comment (step 3).
- **Respects the product owner's content.** Anything **outside** the managed block is preserved verbatim. One exception: a barebone/low-value existing description is absorbed — the managed block becomes the whole description (full heuristic: [REFERENCE.md](REFERENCE.md), "Description merge model"). Borderline barebone call → default to preserving and surface it to the human.
- **Requirements level only.** Never publishes SDD content, ADR documents, or any technical depth — the distill step strips them. (The SDD and Design Brief are disk-only — neither ever reaches the ticket.)
- **Requires an existing parent (PRD mode).** No parent key → stop; tell the human to create the Enhancement/Story/Bug first — PRD mode never creates it. Sets no labels, creates no branch. (Spinoff mode is the one create path — a *new* stub for deferred work, never the PRD's parent.)

## Prerequisites

Register: `skills/afk/setup/MANIFEST.md` — needs **P1/P2** (Python 3 + `markdown-it-py`), **N2** (mermaid-cli; only if the PRD has ```mermaid blocks — engine calls `mmdc` if on PATH, else `npx -y @mermaid-js/mermaid-cli`), and **S1** (Jira REST creds — attachment upload has no MCP tool, so the engine calls the REST API directly). Missing one → `/afk-toolkit:setup`.

## How to run

1. Confirm `PRD.md` is final and you know the parent key (e.g. `PROJ-1220`).
2. **Distill `TICKET.md`** — synthesize the ticket description from `PRD.md`, written sibling to it. `TICKET.md` is a derived artifact: content changes start in `PRD.md`; re-derive whenever the PRD changed since the last publish. **Re-publish?** The on-disk `TICKET.md` is the last-published content (the done-criterion below guarantees it) — copy it aside before overwriting; it's the baseline for step 3's delta. Content contract:
   - **Mandatory sections: User Stories and Acceptance Criteria** — carried from the PRD, trimmed to what the Product Owner and QA act on.
   - Plus a problem/goal summary and the **system behavior** in plain domain language: what changes for the user, inputs → observable outcomes, edge-case behavior QA must exercise.
   - **Strictly requirements and system behavior — no technical depth.** No implementation detail (class/endpoint/schema/module names, code references), no workflow vocabulary, no SDD/Design Brief content.
   - **Never reference local repo artifacts** — no `PRD.md`/`SDD.md`/ADR file/`plan/` mentions, no repo paths; ticket readers have no repo access.
   - An ADR decision worth surfacing (it changes what the user gets) appears **restated as a behavior/constraint statement** at the same requirements level — never as a document pointer.
   - Keep a ```mermaid block only when it depicts user-visible flow or behavior; drop architecture/sequence internals.
3. **Distill the delta (re-publish only)** — diff step 2's baseline against the new `TICKET.md` and write `TICKET-CHANGES.md` sibling to it; the engine posts it as an issue comment, the historical record of *what moved* that the silent in-place description replace doesn't give readers. Same audience and level as `TICKET.md` (requirements only, no repo artifacts). Shape: one lead-in line `**Requirements update — {YYYY-MM-DD}**`, then `**Added**` / `**Changed**` / `**Removed**` bullet groups (omit empty groups), each bullet naming a requirement-level change — a new user story, a tightened/relaxed acceptance criterion, a closed requirement gap, scope pulled in or cut — never a line-diff or wording churn. No ```mermaid (comments can't embed figures). Diff purely cosmetic (no requirement moved) → skip this step and publish without `--changes`.
4. **Dry-run first** — converts + plans, renders nothing, mutates nothing, writes the would-be ADF next to the input as `TICKET.adf.json` (and the would-be comment as `TICKET-CHANGES.adf.json`) for inspection:

   ```
   python scripts/publish_prd.py --parent <KEY> --prd <path/to/TICKET.md> [--changes <path/to/TICKET-CHANGES.md>] --dry-run
   ```

   Read the summary lines: `action` (`first publish` / `re-publish`), how many diagrams, and whether existing ticket content will be **preserved** (`N node(s) preserved`) or **absorbed** (`barebone`). Says "barebone" but you know the PO wrote something real → STOP and inspect the ticket; don't overwrite their work — fix the heuristic call by leaving their content and adjusting, or publish into a fresh ticket. Says `re-publish` but you skipped step 3 → confirm the diff really was cosmetic before proceeding.
5. **Publish** — same command minus `--dry-run`:

   Prints the plan, asks confirmation before the single `PUT` (pass `--yes` to skip the prompt in automated context); on success the engine posts the `--changes` comment (skipped with a warning on a first publish — no delta to record). Each publish updates the description field → watchers notified per re-run (Jira only honours `notifyUsers=false` for project admins, so the engine doesn't send it) — re-run when the PRD meaningfully changed, not idly.

6. **Update the ticket index.** On a successful publish, upsert the `PRD` row of the PRD's sibling `INDEX.md` to `published to Jira {date}` per `skills/afk/to-prd/INDEX-FORMAT.md`.

**Done when:** the `PUT` succeeded, every mermaid figure attached + embedded, `TICKET.md` on disk matches the published content, a re-publish with a real delta has its comment live on the ticket, and the sibling `INDEX.md` `PRD` row reads `published to Jira {date}`.

ADF mapping, the Mermaid-image method, and the description merge model: [REFERENCE.md](REFERENCE.md).

## Next

The requirements-level ticket description is now live on the parent ticket. Then, per the design choice for this ticket:

- **`/afk-toolkit:grill-solution`** → **`/afk-toolkit:to-sdd`** — for new complex features: interview the architecture, synthesize the SDD + design ADRs (disk-only, next to the PRD — never published to the ticket). Downstream plan slices in **cited mode**.
- **`/afk-toolkit:to-subtasks`** — for small features / bugs / refactors / tooling: slice the PRD straight into a local plan in **uncited mode** (human-gated).

## Meeting mode — record a meeting on a ticket

A second, standalone capability — **not** part of the PRD design chain. Publishes a **meeting summary** into any ticket's description as a collapsible `expand`, idempotent per meeting. Separate engine [`scripts/publish_meeting.py`](./scripts/publish_meeting.py); no PRD, no mermaid.

The description grows a plain `Meeting Summaries` heading (created once, at the top) holding one collapsible `expand` per meeting, **newest first**. Re-publishing the same meeting (same expand title) updates it in place; a new meeting adds an expand; **everything else — the PRD managed block, product-owner prose — is preserved verbatim.**

### How to run

1. **Get the meeting content** — a transcript (e.g. a `.vtt`) or notes. Bulk transcript reading is a delegation trigger (`DELEGATION.md`): pull out the substance, not the raw cues.
2. **Synthesize the meeting body** into a Markdown file in the fixed shape (lead-in → Recordings → In Attendance → Documents → `# Summary` → `## 1. Decisions` / `## 2. Open questions` / `## 3. Meeting notes`). Template + ADF/merge model: [REFERENCE.md](REFERENCE.md) ("Meeting Summaries publish"). Record only what the source supports — never invent decisions; mark inferred attendee roles or unclear points as such.
3. **Dry-run** — converts + plans, mutates nothing, writes the would-be ADF next to the body as `MEETING.adf.json`. The summary line's `action` reads `created` (new section) / `inserted` (new meeting) / `replaced` (same-title update) — confirm it matches your intent:

   ```
   python scripts/publish_meeting.py --parent <KEY> --title "<short name>" --date <YYYY-MM-DD> --meeting <path/to/MEETING.md> --dry-run
   ```

4. **Publish** — drop `--dry-run` (the engine prompts before the single `PUT`; pass `--yes` to skip the prompt in automated context).

**Done when:** the `PUT` succeeded and the meeting reads as a collapsible section on the ticket. Recording a meeting edits a **shared** ticket's prose — show the synthesized summary to the human and get a go-ahead before the non-dry-run `PUT`, unless pre-authorized.

## Spinoff mode — mint a stub for deferred work

A third, standalone capability — **not** part of the PRD design chain. During a grill, work surfaces that's real but out of the current ticket's scope; the grill records it as a spinoff **candidate row** and, when the human directs it, hands the candidate here to file. Protocol, candidate-row fields, link-debt, and dedup are one-homed in `SPINOFF-TICKET.md` (plugin root) — this mode is only its **create mechanism**.

Creating an issue has a first-class MCP tool, so spinoff mode uses it directly — no REST engine, no ADF (a stub is plain text).

### How to run

1. **Read the candidate** from the grill's `GRILL-LOG.md` spinoff row — kind, summary, pain, why-out, intended links.
2. **Dedup.** Row already reads `filed {KEY}` → stop; the stub exists (`SPINOFF-TICKET.md`, dedup on resume).
3. **Create** via `tracker_create` — `summary`, `issue_type: Enhancement`, `epic` (the parent epic), `fix_version`, and a plain-text `description` carrying the pain + why-deferred/what-unblocks. Requirements-level, no repo-artifact references (ticket readers have no repo access).
4. **Record + link-debt.** The instant create returns, write `{KEY}` back onto the candidate row. `tracker_create` (and `tracker_edit`) **cannot set `issuelinks`**, so every intended `blocked-by`/`relates` link is **link-debt**: mark the row `filed {KEY} · link-debt` and tell the human which links to set by hand.

**Done when:** the issue exists, its key is on the candidate row, and any unset links are surfaced as link-debt. **Human-present + user-directed only** (`SPINOFF-TICKET.md`) — never mint in a driven run.
