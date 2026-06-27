---
name: to-ticket
description: Publish a finished PRD.md into its Jira parent Enhancement/Bug as native, properly-formatted Jira content (ADF) — full PRD body inline, with any mermaid diagrams rendered to images and embedded so they're viewable in Jira. Idempotent: re-run whenever PRD.md changes and it updates in place. Preserves product-owner content already in the ticket unless it's barebone. Publishes PRD content only — never SDD or lower-level design. Requires an existing parent ticket. The one design-chain skill that writes to the tracker. Use after `/afk:to-prd` once you have the parent key.
---

# afk:to-ticket — publish the PRD into the Jira ticket

`/afk:to-prd` writes `PRD.md` to disk and stops. This skill publishes that PRD
**content** into its Jira parent ticket and is **idempotent** — re-run it
whenever `PRD.md` changes and it updates the ticket in place rather than
duplicating.

The tracker is **Jira Cloud** (`nakisa.atlassian.net`), so the description field
is **ADF** and the work is done by the bundled engine
[`scripts/publish_prd.py`](./scripts/publish_prd.py).

## What it does / does not do

- **Publishes full PRD content inline**, not a link or pointer. The PRD body
  lives in the ticket description.
- **Renders mermaid for Jira.** Each ```mermaid block is rendered to a PNG
  **locally** (no diagram source leaves the network), attached to the issue,
  and embedded inline as an ADF media node so it renders in the description.
- **Idempotent insert + update.** The PRD lives inside an AFK-managed block
  (delimited by sentinel marker paragraphs). Re-running replaces that block and
  its figures in place — no duplicate sections, no piled-up attachments.
- **Respects the product owner's content.** Anything in the description
  **outside** the managed block is preserved verbatim. The one exception: if the
  existing description is barebone/low-value (empty, a placeholder like "TBD", or
  a short stub with no real structure), the managed block becomes the whole
  description.
- **PRD content only.** It never publishes the SDD, ADRs, or lower-level
  technical detail. Keep those out of `PRD.md`; this skill publishes whatever
  `PRD.md` contains and nothing more. (`## SDD` remains owned by `/afk:to-sdd`,
  which splices its own pointer section directly; the Design Brief is
  repo-only and never reaches the ticket — this skill touches neither.)
- **Requires an existing parent.** It refuses without a parent key and does not
  create the Enhancement/Bug. Sets no labels and creates no branch.

## Prerequisites

- **Python 3** with `markdown-it-py` (already present in this environment).
- **Node + mermaid-cli** for diagram rendering. The engine calls `mmdc` if on
  PATH, else `npx -y @mermaid-js/mermaid-cli`. The first `npx` run downloads a
  headless Chromium (one-time, ~hundreds of MB) — if the PRD has no mermaid
  blocks, nothing is rendered and this is not needed. To pre-install:
  `npm i -g @mermaid-js/mermaid-cli`.
- **Jira Cloud creds.** The engine reads `JIRA_BASE_URL` / `JIRA_EMAIL` /
  `JIRA_API_TOKEN` from same-named OS env vars, else from the Jira MCP server's
  `env` block in `~/.claude.json`. Nothing is hardcoded. (Attachment upload has
  no Jira MCP tool, so the engine talks to the REST API directly with these
  creds.)

## How to run

1. Confirm `PRD.md` is final and you know the parent key (e.g. `P2P-1220`).
2. **Dry-run first** — converts + plans, renders nothing, mutates nothing, and
   writes the would-be ADF next to the PRD as `PRD.adf.json` for inspection:

   ```
   python scripts/publish_prd.py --parent <KEY> --prd <path/to/PRD.md> --dry-run
   ```

   Read the summary line: how many diagrams, and whether existing ticket content
   will be **preserved** (`N node(s) preserved`) or **absorbed** (`barebone`).
   If it says "barebone" but you know the PO wrote something real, STOP and
   inspect the ticket — do not overwrite their work; fix the heuristic call by
   leaving their content and adjusting, or publish into a fresh ticket.
3. **Publish:**

   ```
   python scripts/publish_prd.py --parent <KEY> --prd <path/to/PRD.md>
   ```

   It prints the plan and asks for confirmation before the single `PUT`
   (pass `--yes` to skip the prompt in an automated context). Note: each publish
   updates the description field, so watchers are notified per re-run (Jira only
   honours `notifyUsers=false` for project admins, so the engine doesn't send
   it) — re-run when the PRD has meaningfully changed, not idly.

ADF mapping, the Mermaid-image method, and the description merge model are detailed in [REFERENCE.md](REFERENCE.md).

## Hard rules

- **Never overwrite product-owner content.** Only the managed block is yours.
  When the barebone heuristic is borderline, default to preserving and surface it
  to the human.
- **PRD content only.** Do not pull SDD / ADR / design detail into the ticket.
- **Require an existing parent.** No `parent_key` → stop; tell the human to
  create the Enhancement/Bug first. Never create it here.
- **Render mermaid locally.** Never send diagram source to an external render
  service (mermaid.ink, kroki, …) — keep PRD content on-network.
- **No labels, no branch.** Sets no labels and creates no branch; this skill
  publishes content only.
- **Dry-run before the first publish to any ticket that already has content**,
  so you see the preserve/absorb decision before it happens.
- **Never hardcode creds.** They come from env or `~/.claude.json` at runtime.

## Next

The PRD is now live on the parent ticket. Then, per the design choice for this
ticket:

- **`/afk:grill-solution`** → **`/afk:to-sdd`** — for new complex features:
  interview the architecture, synthesize the SDD + design ADRs (those go next to
  the PRD on disk and into the `## SDD` section — not through this skill).
  The downstream plan slices in **cited mode**.
- **`/afk:to-subtasks`** — for small features / bugs / refactors / tooling:
  slice the PRD straight into a local plan in **uncited mode** (human-gated).
