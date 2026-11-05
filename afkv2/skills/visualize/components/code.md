# Code block

## Holds

Pseudo or real code, a configuration snippet, a request or a command line.
Type `code`. Props: `text` (the code, 1 to 100,000 characters), `language` (a
language name of highlight.js, such as `python`, `java`, `sql`, `yaml`, `json`
or `bash`), `path` (the file) and `line` (the number of the first line,
default 1).

## Use it when

A claim rests on code, or the point shows code: a function, an endpoint's
request and response, a configuration file before its key table. Give `path`
and `line` when the code is in the repository, so the human can check it in one
step. A change line by line: a diff (`components/diff.md`).

## How it looks

A fixed-width block with the line numbers in a column on the left, from `line`
on. The header reads `path:line`, then the language. The page colours the code
by its language; an unknown language, or no `language`, shows uncoloured. The
text shows exactly as written: the colour is only a help, never the only cue.

## Example

```json fragment=component
{
  "type": "code",
  "id": "c-export",
  "props": {"path": "shop/export.py", "line": 10, "language": "python",
            "text": "def export(orders):\n    return [o for o in orders if o.paid]\n"}
}
```
