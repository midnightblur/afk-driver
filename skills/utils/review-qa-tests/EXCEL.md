# Writing threaded comments into an .xlsx

QA sheets want **threaded comments** (the modern reply-boxes), not legacy **notes** (yellow stickies). `openpyxl` writes only notes, so [`scripts/annotate_sheet.py`](scripts/annotate_sheet.py) does the conversion for you. Prefer it over re-deriving the XML.

## Run it

```
python scripts/annotate_sheet.py config.json
```

`config.json`:

```json
{
  "source": "C:/path/Book.xlsx",
  "out":    "C:/path/Book.xlsx",
  "sheet":  "Sheet1",
  "author": "Your Name (dev review)",
  "template_row": 30,
  "comments": { "G3": "text…", "D7": "text…" },
  "new_rows": [
    { "C": "Test name", "D": "Scenario objective", "G": "Summary" }
  ]
}
```

- `source` is read; `out` (defaults to `source`) is written. Whatever `out` points at is copied to `<out>.PREV.xlsx` first — you always get a backup.
- `template_row` supplies styling for new rows; new rows are filled pale yellow.
- `comments` keys are cells on existing rows; `new_rows` append after the last row (only the columns you name are written).

## Two modes, auto-selected

The script picks the mode from whether `source` already holds any comments:

- **Rebuild** — `source` is comment-free (a clean copy of the original). The whole workbook is rebuilt via openpyxl, then the target sheet's notes are converted to threaded comments. Give `source` a clean file and `out` the deliverable.
- **In-place** — `source` already has threaded comments somewhere (e.g. another sheet was reviewed in an earlier pass). A plain openpyxl round-trip would flatten those back into notes, so instead the script does pure zip surgery: it adds the new rows and comments to the target sheet only, leaving every existing part **byte-identical**. Point `source`/`out` at the live workbook.

You do not choose the mode; just point at the right file. One limit: in-place refuses if the **target sheet itself** already carries comments (re-annotating one sheet twice) — review a fresh sheet, or rebuild from a clean copy.

## Two gotchas that cause "Excel found a problem … repair?"

Both are orphan/relationship faults, not bad XML — the file parses fine and still triggers repair. The script handles both; replicate them if you ever build by hand:

1. **`person.xml` must be related from the workbook** — a relationship in `xl/_rels/workbook.xml.rels` of type `…/2017/10/relationships/person`. Without it the part is an orphan and Excel repairs on open.
2. **Each threaded comment needs a matching legacy comment** — in the sheet's `comments*.xml`, every comment's author must be `tc={GUID}`, and that GUID is the threaded comment's `id`. This linkage is what makes Excel render a Comment instead of a Note.

If you ever build without the script, replicate a file Excel itself produced — read its parts, don't invent them.

## Before and after writing

- **Check the lock first.** A `~$<name>.xlsx` sibling means the file is open in Excel; the write fails with a permission error. Wait for it to close.
- **Verify after** — `python scripts/annotate_sheet.py --verify out.xlsx` checks every XML part parses, no dangling relationship targets, no orphan parts, both content-type overrides present. The script runs this automatically after every write. Then leak-scan everything you wrote against the black-box line.
- **In-place also proves preservation** — after an in-place run, confirm the other sheets' comment parts are unchanged (compare against `<out>.PREV.xlsx`); the mode is built to keep them byte-identical.
