# Diff

## Holds

A change to code or configuration, line by line. Type `diff`. Props: `text` (a
unified diff, as `git diff` writes it, 1 to 100,000 characters), `path` (the
file, when the text has no `---` and `+++` lines) and `language` (a language
name of highlight.js; by default the extension of the file).

## Use it when

The point shows what a change does to each line, in its context: a proposed
fix, the edit a decision causes. Code with no change: a code block
(`components/code.md`).

## How it looks

One part per hunk, under a header that reads `file:line`, then the hunk's `@@`
line. Each line has its old and new line number. A removed line shows red with
`-`; an added line shows green with `+`; a kept line shows plain. The sign
carries the change, never colour alone. The page colours the code by the
language of its file. A text that is no unified diff is refused by `check`,
with the line that breaks it.

## Example

```json fragment=component
{
  "type": "diff",
  "id": "x-export-paid",
  "props": {"text": "--- a/shop/export.py\n+++ b/shop/export.py\n@@ -10,3 +10,3 @@ def export(orders):\n     rows = []\n-    for o in orders:\n+    for o in paid(orders):\n         rows.append(o)\n"}
}
```
