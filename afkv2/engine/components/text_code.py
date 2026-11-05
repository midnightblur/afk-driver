"""Code block (EG-15, K-24, ADR-0003 design): a fixed-width block with line numbers and a `path:line` header. The
engine marks the block with its language; the page's copy of highlight.js colours it in the browser, and an
unknown language stays uncoloured (`shell/highlight/run.js`)."""

from html import escape

from components.text_lines import LANGUAGE, PATH, TEXT_LIMIT, language_mark
from registry import register_component


def render_code(props, children):
    text, first = props["text"].removesuffix("\n"), props.get("line", 1)
    count = text.count("\n") + 1
    language = props.get("language")
    head = f'<span class="afkv2-code-where">{escape(props["path"])}:{first}</span>' if props.get("path") else ""
    head += f'<span class="afkv2-code-lang">{escape(language)}</span>' if language else ""
    css, attrs = language_mark(language)
    numbers = "\n".join(str(n) for n in range(first, first + count))
    return (f'<figure class="afkv2-code">' + (f'<figcaption class="afkv2-code-head">{head}</figcaption>' if head else "")
            + f'<div class="afkv2-code-body"><pre class="afkv2-code-numbers" aria-hidden="true">{numbers}</pre>'
            f'<pre class="afkv2-code-lines"><code class="afkv2-code-text{css}"{attrs}>{escape(text, quote=False)}</code>'
            f'</pre></div></figure>' + "".join(children))


register_component("code", {
    "type": "object", "additionalProperties": False, "required": ["text"],
    "properties": {"text": {"type": "string", "minLength": 1, "maxLength": TEXT_LIMIT}, "language": LANGUAGE,
                   "path": PATH, "line": {"type": "integer", "minimum": 1}},
}, render_code)
