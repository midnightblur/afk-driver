# afk:to-ticket — reference

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
may be the empty string. Verified against a live Jira Cloud ticket: the
attachment's content-URL 303 redirect yielded `/file/{uuid}/binary`, and the
description's media node carried
exactly that `{uuid}` with `collection: ""`. The undocumented community
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

## Meeting Summaries publish (meeting mode)

`scripts/publish_meeting.py` publishes a meeting into the issue description as a
collapsible `expand`, in a region **disjoint** from the PRD managed block — the
two engines never touch each other's nodes.

### Region shape

A single level-2 heading, then one `expand` per meeting (newest first):

- `heading` (level 2), text exactly `Meeting Summaries` — created once, at the
  **top** of the description, if absent.
- one `expand` per meeting — `attrs.title` is the meeting **key**
  (`"{date} — {title}"`, or `"{title}"` when `--date` is omitted). The whole
  meeting body lives inside it; the subsections are plain headings, **not**
  nested expands (ADF forbids `expand`-in-`expand`).

### Meeting body (the `--meeting` Markdown)

Authored by the caller from a transcript or notes, then converted to the
expand's content by the shared Markdown→ADF mapping (table at the top of this
file). The fixed shape:

```markdown
<one-line lead-in: what the meeting was>

**Recordings:**
- [<label, e.g. Demo (10:31)>](<url>)
- [<label>](<url>)

In Attendance: <names> (<optional note, e.g. "from transcript speakers">)

Documents: <links, or an em-dash when none>

---

# Summary

## 1. Decisions / Confirmations
- <decision or confirmation>

## 2. Open questions / Action items
- **[<owner>]** <action>

## 3. Meeting notes
- <clarification worth keeping>
```

Record only what the source supports. `[text](url)` links keep only
`https`/`mailto` hrefs (relative/anchor hrefs are dropped, text kept), per the
mapping table.

### Merge model (idempotent, meeting-keyed)

- **Locate** the level-2 `Meeting Summaries` heading. Absent → create it with
  the new expand at the **top** of the description → `action: created`.
- The meetings are the **contiguous run of `expand` nodes** immediately after
  that heading.
- An expand in that run whose `attrs.title` **equals** this meeting's key is
  **replaced** in place → `action: replaced` (a re-run updates, never duplicates).
- Otherwise the new expand is **inserted** directly after the heading, newest
  first → `action: inserted`.
- Every other top-level node — the PRD sentinel block, product-owner prose, any
  trailing `rule`/notes — is preserved verbatim.

Meetings are keyed solely by expand title, so keep `--title` (and `--date`)
stable across re-runs of the same meeting; a changed key adds a second expand
rather than updating the first.
