---
name: to-ticket
description: Publish a finished PRD.md into its Jira parent Enhancement/Bug as native ADF — full PRD inline, mermaid diagrams rendered and embedded. Use when `PRD.md` exists on disk and the parent ticket key is known; idempotent — re-run whenever PRD.md changes. The one design-chain skill that writes to the tracker.
---

# afk:to-ticket — publish the PRD into the Jira ticket

This skill publishes a finished `PRD.md`'s **content** into its Jira parent ticket, **idempotent** — re-run whenever `PRD.md` changes → updates ticket in place rather than duplicating.

Tracker is **Jira Cloud** (`nakisa.atlassian.net`), so the description field is **ADF** and the work is done by bundled engine [`scripts/publish_prd.py`](./scripts/publish_prd.py).

## What it does / does not do (binding)

- **Publishes full PRD content inline**, not a link or pointer — PRD body lives in the ticket description.
- **Renders mermaid for Jira, locally.** Each ```mermaid block is rendered to PNG **locally** — never via an external render service (mermaid.ink, kroki, …); no diagram source leaves the network — attached to the issue, embedded inline as an ADF media node so it renders in the description.
- **Idempotent insert + update.** PRD lives inside an AFK-managed block (delimited by sentinel marker paragraphs). Re-running replaces that block and its figures in place — no duplicate sections, no piled-up attachments.
- **Respects the product owner's content.** Anything **outside** the managed block is preserved verbatim. One exception: a barebone/low-value existing description is absorbed — the managed block becomes the whole description (full heuristic: [REFERENCE.md](REFERENCE.md), "Description merge model"). When the barebone call is borderline, default to preserving and surface it to the human.
- **PRD content only.** Never publishes SDD, ADRs, or lower-level technical detail. Keep those out of `PRD.md`; this skill publishes whatever `PRD.md` contains, nothing more. (`## SDD` stays owned by `/afk:to-sdd`, which splices its own pointer section directly; the Design Brief is repo-only and never reaches the ticket — this skill touches neither.)
- **Requires an existing parent.** No parent key → stop; tell the human to create the Enhancement/Bug first — never create it here. Sets no labels, creates no branch.

## Prerequisites

- **Python 3** with `markdown-it-py` (already present in this environment).
- **Node + mermaid-cli** for diagram rendering. Engine calls `mmdc` if on PATH, else `npx -y @mermaid-js/mermaid-cli`. First `npx` run downloads a headless Chromium (one-time, ~hundreds of MB) — if the PRD has no mermaid blocks, nothing renders and this isn't needed. To pre-install: `npm i -g @mermaid-js/mermaid-cli`.
- **Jira Cloud creds.** Engine reads `JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN` from same-named OS env vars, else from the Jira MCP server's `env` block in `~/.claude.json`. Nothing hardcoded. (Attachment upload has no Jira MCP tool, so the engine talks to the REST API directly with these creds.)

## How to run

1. Confirm `PRD.md` is final and you know the parent key (e.g. `P2P-1220`).
2. **Dry-run first** — converts + plans, renders nothing, mutates nothing, writes the would-be ADF next to the PRD as `PRD.adf.json` for inspection:

   ```
   python scripts/publish_prd.py --parent <KEY> --prd <path/to/PRD.md> --dry-run
   ```

   Read the summary line: how many diagrams, and whether existing ticket content will be **preserved** (`N node(s) preserved`) or **absorbed** (`barebone`). If it says "barebone" but you know the PO wrote something real, STOP and inspect the ticket — do not overwrite their work; fix the heuristic call by leaving their content and adjusting, or publish into a fresh ticket.
3. **Publish:**

   ```
   python scripts/publish_prd.py --parent <KEY> --prd <path/to/PRD.md>
   ```

   Prints the plan and asks confirmation before the single `PUT` (pass `--yes` to skip the prompt in automated context). Note: each publish updates the description field → watchers notified per re-run (Jira only honours `notifyUsers=false` for project admins, so the engine doesn't send it) — re-run when the PRD has meaningfully changed, not idly.

4. **Update the ticket index.** On a successful publish, upsert the `PRD` row of the PRD's sibling `INDEX.md` to `published to Jira {date}` per `skills/afk/to-prd/INDEX-FORMAT.md`.

**Done when:** the `PUT` succeeded, every mermaid figure is attached + embedded, and the sibling `INDEX.md` `PRD` row reads `published to Jira {date}`.

ADF mapping, the Mermaid-image method, and the description merge model are detailed in [REFERENCE.md](REFERENCE.md).

## Next

The PRD is now live on the parent ticket. Then, per the design choice for this ticket:

- **`/afk:grill-solution`** → **`/afk:to-sdd`** — for new complex features: interview the architecture, synthesize the SDD + design ADRs (those go next to the PRD on disk and into the `## SDD` section — not through this skill). Downstream plan slices in **cited mode**.
- **`/afk:to-subtasks`** — for small features / bugs / refactors / tooling: slice the PRD straight into a local plan in **uncited mode** (human-gated).
