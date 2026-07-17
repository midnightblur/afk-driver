# Writing threaded comments into an .xlsx

QA sheets want **threaded comments** (the modern reply-boxes), not legacy **notes** (yellow stickies). `openpyxl` writes only notes, so the recipe is: let openpyxl write notes, then convert them to threaded comments by hand-editing the package. [`scripts/annotate_sheet.py`](scripts/annotate_sheet.py) does the whole thing from a JSON config — prefer it over re-deriving the XML.

## Run it

```
python scripts/annotate_sheet.py config.json
```

`config.json`:

```json
{
  "backup": "C:/path/Book.BACKUP.xlsx",
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

- `backup` is the clean source read from; `out` is written fresh (delete-and-replace). Always point `backup` at a real backup, never at `out`.
- `template_row` supplies font/alignment/border/number-format for new rows; new rows are also filled pale yellow.
- `comments` keys are cells on existing rows; `new_rows` append after the last row.

## Two gotchas that cause "Excel found a problem … repair?"

Both are orphan/relationship faults, not bad XML — the file parses fine and still triggers repair:

1. **`person.xml` must be related from the workbook.** Add a relationship in `xl/_rels/workbook.xml.rels` of type `…/2017/10/relationships/person` → `/xl/persons/person.xml`. Without it the part is an orphan and Excel repairs on open.
2. **Each threaded comment needs a matching legacy comment.** In `xl/comments*/…xml`, every comment's author must be `tc={GUID}`, and that GUID is the threaded comment's `id`. This linkage is what makes Excel render it as a Comment instead of a Note.

The script handles both. If you ever build it without the script, replicate a file Excel itself produced — read its parts, don't invent them.

## Before and after writing

- **Check the lock first.** A `~$<name>.xlsx` sibling means the file is open in Excel; the write will fail with a permission error. Wait for it to close.
- **Verify after.** Reopen in openpyxl, then check: every XML part parses, no dangling relationship targets, no orphan parts, both content-type overrides present (`threadedcomments+xml`, `person+xml`). Then leak-scan everything you wrote against the black-box line. The script's `--verify` flag runs these checks.
