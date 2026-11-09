# Write threaded comments into an .xlsx file

QA sheets need **threaded comments** (the modern reply boxes), not legacy **notes** (the yellow notes). `openpyxl` writes only notes. The script [`scripts/annotate_sheet.py`](scripts/annotate_sheet.py) changes the notes into threaded comments. Use the script. Do not write the XML yourself.

## Run it

`<python>` is the Python in the setup install record (line `python`). The script needs the `openpyxl` package. It loads `openpyxl` from `%LOCALAPPDATA%\afkv2\python-packages` first, then from the Python environment.

When the script exits 3 with `MISSING:`, `openpyxl` is in neither place. Tell the developer that the install downloads `openpyxl` from the Python Package Index (PyPI) into that folder and changes no other Python package. Ask for a yes, and end your turn. After the yes, run the command that the message gives, then run the script again. Never install without the yes.

```
<python> "<this skill's folder>/scripts/annotate_sheet.py" config.json
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

- The script reads `source` and writes `out`. If `out` is missing, the script writes to `source`. Before it writes, the script copies the file at `out` to `<out>.PREV.xlsx`, so you always have a backup.
- `template_row` gives the styles for new rows. The script fills new rows pale yellow.
- The keys of `comments` are cells on existing rows. The script adds `new_rows` after the last row. It writes only the columns that you name.

## The 2 modes

The script selects the mode. The mode depends on whether `source` already holds comments:

- **Rebuild**: `source` has no comments (a clean copy of the original). The script builds the whole workbook again with openpyxl. Then it changes the notes of the target sheet into threaded comments. Give a clean file as `source` and the deliverable as `out`.
- **In place**: `source` already has threaded comments, for example on a sheet that an earlier review annotated. An openpyxl rebuild would change those comments back into notes. So the script edits the zip parts directly. It adds the new rows and comments to the target sheet only, and keeps each existing part byte-identical. Give the live workbook as `source` and `out`.

You do not select the mode. Give the correct file. One limit: the in-place mode refuses when the **target sheet** already has comments, because the script cannot annotate 1 sheet 2 times. Review a new sheet, or rebuild from a clean copy.

## 2 causes of "Excel found a problem … repair?"

Both causes are missing or orphan relationships, not bad XML. The file parses correctly, but Excel still asks to repair it. The script prevents both. If you build a file without the script, copy these 2 rules:

1. **The workbook must relate to `person.xml`**: `xl/_rels/workbook.xml.rels` needs a relationship of type `…/2017/10/relationships/person`. Without it, the part is an orphan and Excel repairs the file when it opens it.
2. **Each threaded comment needs a matching legacy comment**: in the `comments*.xml` part of the sheet, the author of each comment must be `tc={GUID}`, and that GUID is the `id` of the threaded comment. This link makes Excel show a comment, not a note.

If you build a file without the script, copy the parts from a file that Excel made. Read its parts. Do not invent parts.

## Before and after you write

- **Check the lock first.** A `~$<name>.xlsx` file in the same folder means that the file is open in Excel, and the write fails with a permission error. Wait until the developer closes it.
- **Verify after the write.** `<python> "<this skill's folder>/scripts/annotate_sheet.py" --verify out.xlsx` checks that each XML part parses, that no relationship target is missing, that no part is an orphan, and that both content-type overrides are present. The script runs this check after each write. Then scan all text that you wrote against the black-box line.
- **After an in-place write, prove that the other parts did not change.** Compare the comment parts of the other sheets with `<out>.PREV.xlsx`. They must be byte-identical.
