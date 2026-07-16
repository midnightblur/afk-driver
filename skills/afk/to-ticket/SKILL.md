---
name: to-ticket
description: Publish a finished PRD.md into its Jira parent Enhancement/Bug as native ADF — full PRD inline, mermaid diagrams rendered and embedded — or publish a meeting summary onto any ticket as a collapsible expand. Use when `PRD.md` exists and the parent key is known, or to record a meeting on a ticket. Idempotent; the one design-chain skill writing to the tracker.
---

# afk:to-ticket — publish into the Jira ticket

Two independent capabilities, both writing native **ADF** to a **Jira Cloud** (`nakisa.atlassian.net`) issue description, both **idempotent** (re-run updates in place, never duplicates):

- **PRD mode** (below) — publish a finished `PRD.md`'s **content** into its parent Enhancement/Bug; engine [`scripts/publish_prd.py`](./scripts/publish_prd.py).
- **Meeting mode** ([jump](#meeting-mode--record-a-meeting-on-a-ticket)) — record a meeting on **any** ticket as a collapsible `expand`; engine [`scripts/publish_meeting.py`](./scripts/publish_meeting.py).

The two engines share creds + the Markdown→ADF mapping but own **disjoint regions** of the description, so they never collide.

## What it does / does not do (binding)

- **Publishes full PRD content inline**, not a link or pointer — PRD body lives in the ticket description.
- **Renders mermaid for Jira, locally.** Each ```mermaid block rendered to PNG **locally** — never via an external render service (mermaid.ink, kroki, …); no diagram source leaves the network — attached to the issue, embedded inline as an ADF media node so it renders in the description.
- **Idempotent insert + update.** PRD lives inside an AFK-managed block (delimited by sentinel marker paragraphs). Re-running replaces that block and its figures in place — no duplicate sections, no piled-up attachments.
- **Respects the product owner's content.** Anything **outside** the managed block is preserved verbatim. One exception: a barebone/low-value existing description is absorbed — the managed block becomes the whole description (full heuristic: [REFERENCE.md](REFERENCE.md), "Description merge model"). Borderline barebone call → default to preserving and surface it to the human.
- **PRD content only.** Never publishes SDD, ADRs, or lower-level technical detail. Keep those out of `PRD.md`; this skill publishes whatever `PRD.md` contains, nothing more. (`## SDD` stays owned by `/afk:to-sdd`, which splices its own pointer section directly; the Design Brief is repo-only and never reaches the ticket — this skill touches neither.)
- **Requires an existing parent.** No parent key → stop; tell the human to create the Enhancement/Bug first — never create it here. Sets no labels, creates no branch.

## Prerequisites

Register: `skills/afk/setup/MANIFEST.md` — needs **P1/P2** (Python 3 + `markdown-it-py`), **N2** (mermaid-cli; only if the PRD has ```mermaid blocks — engine calls `mmdc` if on PATH, else `npx -y @mermaid-js/mermaid-cli`), and **S1** (Jira REST creds — attachment upload has no MCP tool, so the engine calls the REST API directly). Missing one → `/afk:setup`.

## How to run

1. Confirm `PRD.md` is final and you know the parent key (e.g. `P2P-1220`).
2. **Dry-run first** — converts + plans, renders nothing, mutates nothing, writes the would-be ADF next to the PRD as `PRD.adf.json` for inspection:

   ```
   python scripts/publish_prd.py --parent <KEY> --prd <path/to/PRD.md> --dry-run
   ```

   Read the summary line: how many diagrams, and whether existing ticket content will be **preserved** (`N node(s) preserved`) or **absorbed** (`barebone`). Says "barebone" but you know the PO wrote something real → STOP and inspect the ticket; don't overwrite their work — fix the heuristic call by leaving their content and adjusting, or publish into a fresh ticket.
3. **Publish:**

   ```
   python scripts/publish_prd.py --parent <KEY> --prd <path/to/PRD.md>
   ```

   Prints the plan, asks confirmation before the single `PUT` (pass `--yes` to skip the prompt in automated context). Each publish updates the description field → watchers notified per re-run (Jira only honours `notifyUsers=false` for project admins, so the engine doesn't send it) — re-run when the PRD meaningfully changed, not idly.

4. **Update the ticket index.** On a successful publish, upsert the `PRD` row of the PRD's sibling `INDEX.md` to `published to Jira {date}` per `skills/afk/to-prd/INDEX-FORMAT.md`.

**Done when:** the `PUT` succeeded, every mermaid figure attached + embedded, and the sibling `INDEX.md` `PRD` row reads `published to Jira {date}`.

ADF mapping, the Mermaid-image method, and the description merge model: [REFERENCE.md](REFERENCE.md).

## Next

The PRD is now live on the parent ticket. Then, per the design choice for this ticket:

- **`/afk:grill-solution`** → **`/afk:to-sdd`** — for new complex features: interview the architecture, synthesize the SDD + design ADRs (those go next to the PRD on disk and into the `## SDD` section — not through this skill). Downstream plan slices in **cited mode**.
- **`/afk:to-subtasks`** — for small features / bugs / refactors / tooling: slice the PRD straight into a local plan in **uncited mode** (human-gated).

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
