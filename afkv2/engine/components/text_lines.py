"""What the code block and the diff share: the language mark that the page's copy of highlight.js reads
(`shell/highlight/run.js`), and the prop rules. Registers no type."""

from html import escape

TEXT_LIMIT = 100000
LANGUAGE = {"type": "string", "pattern": "^[A-Za-z0-9_+#.-]{1,32}$"}
PATH = {"type": "string", "minLength": 1, "maxLength": 300}


def language_mark(language):
    """The class and the attribute that mark a block with its language; none for no language."""
    if not language:
        return "", ""
    return f" language-{escape(language)}", f' data-afkv2-lang="{escape(language)}"'
