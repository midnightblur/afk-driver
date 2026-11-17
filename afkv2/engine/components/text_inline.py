"""The inline marks of a `markdown: true` text and of a table cell given as a plain string: `code`, links,
**bold**, *italic*, ==highlight==, and code font with no mark for a code name (`CODE_NAME`). The text is
escaped first. A leaf module: it registers no component."""

import re
from html import escape

CODE = re.compile(r"`([^`]+)`")
# A code name: a file reference (a path or name with a source extension, then optional `:lines`, where each line
# item after a comma ends at a comma, a semicolon, a bracket or the end), else a snake_case id. A prose word
# holds no underscore and no source extension, so it never matches; a bare CamelCase name is not read.
EXTENSIONS = ("java|kts|kt|scala|groovy|gradle|py|pyi|ts|tsx|js|jsx|mjs|cjs|go|rs|rb|cs|cpp|hpp|swift|php|"
              "sql|xml|yaml|yml|json|toml|properties|ini|cfg|sh|ps1|cmd|bat|html|css|scss|vue|md|txt|csv|proto")
LINES = r"\d+(?:-\d+)?"
CODE_NAME = re.compile(
    rf"(?<![\w./-])(?:[\w.-]+/)*[A-Za-z_][\w.-]*\.(?:{EXTENSIONS})\b"
    rf"(?::{LINES}(?:,\s*{LINES}(?=\s*(?:[,;)\]]|$)))*)?(?![\w/])"
    r"|(?<![\w./-])[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+(?![\w/-])")

# Links are read in escaped text: a URL ends at an escaped quote or angle bracket.
URL = r"https?://(?:(?!&quot;|&#x27;|&lt;|&gt;)[^\s)])+"
LINK = re.compile(rf"\[([^\]]+)\]\(({URL})\)|({URL})")
BOLD = re.compile(r"\*\*(.+?)\*\*")
# A single star pair: no space inside either star, no word sign or star outside, so `a * b`, `2*3` and a glob stay.
ITALIC = re.compile(r"(?<![\w*])\*(?![\s*])([^*]+?)(?<![\s*])\*(?![\w*])")
HIGHLIGHT_TAG = r'<mark class="afkv2-md-mark">\1</mark>'
HIGHLIGHT = re.compile(r"(?<![=\w])==(?![\s=])(.+?)(?<![\s=])==(?![=\w])")
URL_TAIL = ".,;:!?"


# lavish's note mode lets a click through only inside `[data-lavish-action]`; without it a link never opens.
NEW_TAB = 'target="_blank" rel="noopener noreferrer" data-lavish-action="afkv2-link"'


def _link(match):
    if match.group(2):
        return f'<a href="{match.group(2)}" {NEW_TAB}>{match.group(1)}</a>'
    url = match.group(3)
    tail = ""
    while url and url[-1] in URL_TAIL and not url.endswith("&amp;"):
        url, tail = url[:-1], url[-1] + tail
    return f'<a href="{url}" {NEW_TAB}>{url}</a>{tail}'


def _marks(text):
    """Code names, then **bold**, *italic* and ==highlight==, in escaped text that holds no code span and no
    link."""
    text = CODE_NAME.sub(lambda m: f"<code>{m.group(0)}</code>", text)
    text = BOLD.sub(r"<strong>\1</strong>", text)
    text = ITALIC.sub(r"<em>\1</em>", text)
    return HIGHLIGHT.sub(HIGHLIGHT_TAG, text)


def _plain(part):
    """Links, and the marks of `_marks` on the text between links: a mark never reads inside a URL."""
    out, at = [], 0
    for match in LINK.finditer(part):
        out += [_marks(part[at:match.start()]), _link(match)]
        at = match.end()
    return "".join(out + [_marks(part[at:])])


def inline(text):
    """Escape first, then `code`, links and the marks of `_marks`; nothing inside a code span or a link is read."""
    parts = CODE.split(escape(text))
    return "".join(f"<code>{part}</code>" if i % 2 else _plain(part) for i, part in enumerate(parts))


def code_names(text):
    """The code names of a plain text that has no code font there: each `code` span, then each `CODE_NAME`
    outside a code span and a link."""
    spans = CODE.split(text)
    found = list(spans[1::2])
    for part in spans[::2]:
        found += [m.group(0) for piece in LINK.split(part)[::4] if piece for m in CODE_NAME.finditer(piece)]
    return found
