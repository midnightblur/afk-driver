"""Diff (EG-15, K-25): a unified diff, one table per hunk under a `file:line` header. A removed line shows red with
-, an added line green with +, each with its old and new line number. Each line is marked with the language of its
file, so the page's copy of highlight.js colours it (`components/text_lines.py`)."""

import re
from html import escape
from pathlib import PurePosixPath

from components.text_lines import LANGUAGE, PATH, TEXT_LIMIT, language_mark
from registry import register_component

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
KINDS = {" ": "kept", "-": "removed", "+": "added", "\\": "note", "": "kept"}
NO_FILE = "/dev/null"


class _NoDiff(Exception):
    pass


def _name(line):
    name = line[4:].split("\t", 1)[0].strip()
    if name == NO_FILE:
        return None
    return name[2:] if name[:2] in ("a/", "b/") else name


def parse(text, path=None):
    """The hunks of a unified diff: `{file, head, line, lines: [(kind, old n, new n, text)]}`. A line outside a hunk
    other than `---` and `+++` is a header (`diff`, `index`, a mode, a message) and shows nowhere. `_NoDiff` names
    the line that breaks the form."""
    hunks, old_name, new_name, left = [], None, None, None
    for number, line in enumerate(text.splitlines(), 1):
        if left and (left[0] > 0 or left[1] > 0 or line.startswith("\\")):
            kind = KINDS.get(line[:1])
            if kind is None:
                raise _NoDiff(f"line {number} of the hunk starts with neither a space, -, + nor \\")
            hunk = hunks[-1]
            old = left[2] if kind in ("kept", "removed") else ""
            new = left[3] if kind in ("kept", "added") else ""
            hunk["lines"].append((kind, old, new, line[1:]))
            if kind in ("kept", "removed"):
                left[0], left[2] = left[0] - 1, left[2] + 1
            if kind in ("kept", "added"):
                left[1], left[3] = left[1] - 1, left[3] + 1
            if left[0] < 0 or left[1] < 0:
                raise _NoDiff(f"line {number}: the hunk holds more lines than its header counts")
            continue
        if line.startswith("@@"):
            found = HUNK.match(line)
            if not found:
                raise _NoDiff(f"line {number}: a hunk header reads @@ -old,count +new,count @@")
            file = new_name or old_name or path
            if not file:
                raise _NoDiff(f"line {number}: the hunk names no file; add the --- and +++ lines or the path prop")
            old_start, new_start = int(found.group(1)), int(found.group(3))
            old_count, new_count = int(found.group(2) or 1), int(found.group(4) or 1)
            hunks.append({"file": file, "head": line, "line": new_start if new_count else old_start, "lines": []})
            left = [old_count, new_count, old_start, new_start]
            continue
        if line.startswith("--- "):
            old_name, new_name = _name(line), None
        elif line.startswith("+++ "):
            new_name = _name(line)
    if not hunks:
        raise _NoDiff("the text holds no hunk (@@ -old,count +new,count @@)")
    if left[0] > 0 or left[1] > 0:
        raise _NoDiff("the text ends before the last hunk holds the lines its header counts")
    return hunks


def check_diff(props):
    try:
        parse(props["text"], props.get("path"))
    except _NoDiff as why:
        yield ("text",), str(why)


def _language(file, language):
    return language or PurePosixPath(file).suffix.lstrip(".").lower() or None


def _hunk(hunk, language):
    css, attrs = language_mark(_language(hunk["file"], language))
    signs = {"kept": " ", "removed": "-", "added": "+", "note": "\\"}
    rows = "".join(
        f'<tr class="afkv2-diff-line afkv2-diff-line--{kind}"><td class="afkv2-diff-n">{old}</td>'
        f'<td class="afkv2-diff-n">{new}</td><td class="afkv2-diff-sign">{signs[kind]}</td>'
        f'<td class="afkv2-diff-code"><code class="afkv2-diff-text{"" if kind == "note" else css}"'
        f'{"" if kind == "note" else attrs}>{escape(text, quote=False)}</code></td></tr>'
        for kind, old, new, text in hunk["lines"])
    return (f'<div class="afkv2-diff-hunk"><div class="afkv2-diff-head"><span class="afkv2-diff-where">'
            f'{escape(hunk["file"])}:{hunk["line"]}</span> <span class="afkv2-diff-range">{escape(hunk["head"])}</span>'
            f'</div><table class="afkv2-diff-lines">{rows}</table></div>')


def render_diff(props, children):
    hunks = parse(props["text"], props.get("path"))
    drawn = "".join(_hunk(hunk, props.get("language")) for hunk in hunks)
    return f'<figure class="afkv2-diff">{drawn}</figure>' + "".join(children)


register_component("diff", {
    "type": "object", "additionalProperties": False, "required": ["text"],
    "properties": {"text": {"type": "string", "minLength": 1, "maxLength": TEXT_LIMIT}, "path": PATH,
                   "language": LANGUAGE},
}, render_diff, check=check_diff)
