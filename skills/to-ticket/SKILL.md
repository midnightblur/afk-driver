---
name: to-ticket
description: Publish a finished PRD.md into its Jira parent Enhancement/Bug as native, properly-formatted Jira content (ADF) — full PRD body inline, with any mermaid diagrams rendered to images and embedded so they're viewable in Jira. Idempotent: re-run whenever PRD.md changes and it updates in place. Preserves product-owner content already in the ticket unless it's barebone. Publishes PRD content only — never SDD or lower-level design. Requires an existing parent ticket. The one design-chain skill that writes to the tracker. Use after `/afk:to-prd` once you have the parent key.
---

# afk:to-ticket — publish the PRD into the Jira ticket

`/afk:to-prd` writes `PRD.md` to disk and stops. This skill publishes that PRD
**content** into its Jira parent ticket: the full PRD body, rendered as native
Jira formatting (ADF — headings, lists, tables, code blocks, blockquotes), with
any `mermaid` diagrams rendered to images and embedded so they are viewable
directly in Jira. It is **idempotent** — re-run it whenever `PRD.md` changes and
it updates the ticket in place rather than duplicating.

The tracker is **Jira Cloud** (`nakisa.atlassian.net`), so the description field
is **ADF** and the work is done by the bundled engine
[`scripts/publish_prd.py`](./scripts/publish_prd.py) — the formatting,
diagram, and merge steps are too intricate to do by hand reproducibly, so they
are codified there for deterministic behavior.

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
  **outside** the managed block is preserved verbatim — the PO worked hard on
  it. The one exception: if the existing description is barebone/low-value
  (empty, a placeholder like "TBD", or a short stub with no real structure), the
  managed PRD block becomes the whole description.
- **PRD content only.** It never publishes the SDD, ADRs, or lower-level
  technical detail. Keep those out of `PRD.md`; this skill publishes whatever
  `PRD.md` contains and nothing more. (`## SDD` / `## Design Brief` remain owned
  by `/afk:to-sdd` / `/afk:to-design-brief`, which splice their own sections
  directly — this skill never touches them.)
- **Requires an existing parent.** It refuses without a parent key and does not
  create the Enhancement/Bug. It sets **no labels** and does **not** create a
  GitLab branch (the AFK driver is gone; `/afk:execute` self-creates its branch).

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

## Deterministic Markdown → ADF mapping

The engine maps PRD Markdown to ADF by a fixed table (CommonMark + GFM tables /
strikethrough via `markdown-it-py`'s `gfm-like` preset, `html` disabled):

| Markdown | ADF node |
|----------|----------|
| `# … ######` | `heading` (`attrs.level` 1–6) |
| paragraph | `paragraph` |
| `**bold**` / `*italic*` / `~~strike~~` | text `marks`: `strong` / `em` / `strike` |
| `` `code` `` | text mark `code` |
| `[text](url)` | text mark `link` (`attrs.href`) |
| `- ` / `* ` list (nestable) | `bulletList` → `listItem` |
| `1. ` list | `orderedList` (`attrs.order` when start ≠ 1) → `listItem` |
| GFM table | `table` → `tableRow` → `tableHeader`/`tableCell` |
| ` ```lang ` fenced code | `codeBlock` (`attrs.language`) |
| `> ` quote | `blockquote` |
| `---` | `rule` |
| line break (soft / hard) | space / `hardBreak` |
| ` ```mermaid ` fenced block | rendered PNG → `mediaSingle` → `media` (see below) |

Unmapped constructs are dropped deterministically rather than guessed at. Raw
HTML is not interpreted.

## Mermaid → viewable Jira image (verified method)

For each ```mermaid block, in document order, the engine:

1. Renders the source to `afk-fig{N}.png` locally via `mmdc` (background white),
   and reads the PNG's width/height from its IHDR.
2. Uploads it via `POST /rest/api/3/issue/{key}/attachments`
   (`X-Atlassian-Token: no-check`, multipart field `file`) → attachment id.
3. Resolves the **media UUID**: `GET /rest/api/3/attachment/content/{id}` without
   following the 303 redirect; the `Location` header is
   `https://api.media.atlassian.com/file/{uuid}/binary?token=…` — the engine
   pulls `{uuid}` out of it.
4. Embeds it inline as ADF:

   ```json
   { "type": "mediaSingle", "attrs": { "layout": "center" },
     "content": [ { "type": "media", "attrs": {
       "type": "file", "id": "{uuid}", "collection": "",
       "width": W, "height": H } } ] }
   ```

This is the only method Jira Cloud actually renders inline in a description — it
needs the Media-Services UUID (not the numeric attachment id) and `collection`
may be the empty string. Verified against a real agent-authored ticket
(P2P-1201): attachment `1230428` → content-URL 303 →
`/file/308455ab-…/binary`, and the description's first media node carried
exactly `id: 308455ab-…, collection: ""`. The undocumented community
alternatives (external-URL media, guessed `jira-{id}-field-description`
collections) render as broken placeholders — do not use them.

## Description merge model

- The managed region is delimited by two sentinel **marker paragraphs**:
  the start marker's text begins with `afk:prd:start` (followed by a "generated
  — edit PRD.md instead" note) and the end marker's text is exactly
  `afk:prd:end`. They are matched exactly on re-run.
- **Preserve.** Every top-level node outside the markers is kept verbatim.
- **Barebone exception.** If the remainder (existing description minus any prior
  managed block) is empty, a known placeholder (`TBD`/`TODO`/`N/A`/`see PRD`/…),
  or a short stub (< ~200 chars of text, no table/media/code, < 2 headings, < 3
  list items), it is treated as low-value and the managed PRD block becomes the
  whole description.
- **First insert with valuable PO content** appends the managed block after the
  existing content, separated by a `rule`.
- **Re-run** strips the prior managed block (markers inclusive) and its
  `afk-fig*.png` attachments, then re-inserts at the same position and re-renders
  the figures — so the ticket never accumulates duplicates.

## Hard rules

- **Never overwrite product-owner content.** Only the managed block is yours.
  When the barebone heuristic is borderline, default to preserving and surface it
  to the human — absorbing real PO work is the worst failure mode here.
- **PRD content only.** Do not pull SDD / ADR / design detail into the ticket.
- **Require an existing parent.** No `parent_key` → stop; tell the human to
  create the Enhancement/Bug first. Never create it here.
- **Render mermaid locally.** Never send diagram source to an external render
  service (mermaid.ink, kroki, …) — keep PRD content on-network.
- **No labels, no branch.** The driver is gone; this skill publishes content
  only.
- **Dry-run before the first publish to any ticket that already has content**,
  so you see the preserve/absorb decision before it happens.
- **Never hardcode creds.** They come from env or `~/.claude.json` at runtime.

## Next

The PRD is now live on the parent ticket. Then, per the design choice for this
ticket:

- **`/afk:architect-grill`** → **`/afk:to-sdd`** — for new complex features:
  interview the architecture, synthesize the SDD + design ADRs (those go next to
  the PRD on disk and into the `## SDD` section — not through this skill).
  Downstream SubTasks slice in **cited mode**.
- **`/afk:to-subtasks`** — for small features / bugs / refactors / tooling:
  slice the PRD straight into SubTasks in **uncited mode** (human-gated).
