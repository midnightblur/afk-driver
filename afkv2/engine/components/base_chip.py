"""Chip and styled text (CMP-9), with the 4 semantic tones. Text may render a safe Markdown subset,
and may carry a label line with a badge above its words. A chip also takes a tone of state or certainty,
drawn with its own symbol beside its colour (PR-07: never colour alone). A value chip names its named set in
`set` instead of a tone: its text is the value, its colour comes from the value's position in that set."""

import re
from html import escape

from registry import register_component, value_set

TONES = ["removed", "kept", "new", "proposed"]
MARKS = {"open": "○", "blocked": "✕", "settled": "✓", "measured": "●",
         "inferred": "◐", "estimated": "≈", "unverified": "?", "you": "★"}
CHIP_TONES = TONES + list(MARKS)
# Removed and proposed chips carry a shape cue in kit.css (strike-through, dashed); kept and new a symbol.
SYMBOLS = {"kept": "=", "new": "+", **MARKS}
SET_COLOURS = 8
FAINTEST = 35
YOU_VALUE = "you"
SCALE = "var(--afkv2-scale)"
MARK_SPAN = '<span class="afkv2-chip-mark" aria-hidden="true">{}</span>'
LIST_ITEM = re.compile(r"\s*[-*] (.*)")
HEADING = re.compile(r"#{1,6}\s+(.*)")
CODE = re.compile(r"`([^`]+)`")
# Links are read in escaped text: a URL ends at an escaped quote or angle bracket.
URL = r"https?://(?:(?!&quot;|&#x27;|&lt;|&gt;)[^\s)])+"
LINK = re.compile(rf"\[([^\]]+)\]\(({URL})\)|({URL})")
BOLD = re.compile(r"\*\*(.+?)\*\*")
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


def _inline(text):
    """Escape first, then `code`, links and **bold**; nothing inside a code span is read."""
    parts = CODE.split(escape(text))
    return "".join(f"<code>{part}</code>" if i % 2 else BOLD.sub(r"<strong>\1</strong>", LINK.sub(_link, part))
                   for i, part in enumerate(parts))


def markdown(text):
    """Blank-line paragraphs, `- ` lists, `#` headings as bold lines, and the inline subset of `_inline`."""
    out, para, items = [], [], []

    def flush():
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{_inline(item)}</li>" for item in items) + "</ul>")
            items.clear()

    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        listed, heading = LIST_ITEM.fullmatch(line), HEADING.fullmatch(stripped)
        if not stripped:
            flush()
        elif listed:
            if para:
                flush()
            items.append(listed.group(1).strip())
        elif heading:
            flush()
            out.append(f'<p class="afkv2-md-h"><strong>{_inline(heading.group(1))}</strong></p>')
        elif items and line[:1] in (" ", "\t"):
            items[-1] += " " + stripped
        else:
            if items:
                flush()
            para.append(stripped)
    flush()
    return "".join(out)


def value_colour(values, value, ordered):
    """The CSS colour of `value` by its position in its named set `values`, or None outside the set.
    YOU, in any case, has one fixed strong colour; an ordered set runs strong to faint in one hue."""
    if value not in values:
        return None
    if value.lower() == YOU_VALUE:
        return "var(--afkv2-you)"
    position = values.index(value)
    if not ordered:
        return f"var(--afkv2-set-{position % SET_COLOURS + 1})"
    strength = 100 - round((100 - FAINTEST) * position / max(len(values) - 1, 1))
    return f"color-mix(in srgb, {SCALE} {strength}%, var(--surface))"


def check_chip(props):
    """A chip takes a tone or a set: never both, never neither."""
    if ("tone" in props) == ("set" in props):
        yield ("tone",), "takes a tone or a set, exactly one"


def _value_chip(props):
    named = value_set(props["set"]) or {}
    colour = value_colour(named.get("values") or [], props["text"], named.get("ordered", False))
    style = f' style="--afkv2-value: {escape(colour)}"' if colour else ""
    return f'<span class="afkv2-chip afkv2-value"{style}>{escape(props["text"])}</span>'


def render_chip(props, children):
    if "set" in props:
        return _value_chip(props) + "".join(children)
    tone = props["tone"]
    mark = MARK_SPAN.format(SYMBOLS[tone]) if tone in SYMBOLS else ""
    return (f'<span class="afkv2-chip afkv2-tone--{tone}">{mark}{escape(props["text"])}</span>'
            + "".join(children))


def _label(props):
    """The label line above the words: the label, then the badge as a neutral chip."""
    if not props.get("label") and not props.get("badge"):
        return ""
    badge = f'<span class="afkv2-chip afkv2-badge">{escape(props["badge"])}</span>' if props.get("badge") else ""
    label = f'<span class="afkv2-label-words">{escape(props["label"])}</span>' if props.get("label") else ""
    return f'<p class="afkv2-label">{label}{badge}</p>'


def render_text(props, children):
    tone = props.get("tone")
    style = f" afkv2-tone--{tone}" if tone else ""
    tail = f'<div class="afkv2-children">{"".join(children)}</div>' if children else ""
    words = (f'<div class="afkv2-md">{markdown(props["text"])}</div>' if props.get("markdown")
             else f'<p>{escape(props["text"])}</p>')
    labelled = " afkv2-labelled" if props.get("label") or props.get("badge") else ""
    return f'<div class="afkv2-text{style}{labelled}">{_label(props)}{words}{tail}</div>'


register_component("chip", {
    "type": "object", "additionalProperties": False, "required": ["text"],
    "properties": {"text": {"type": "string"}, "tone": {"enum": CHIP_TONES},
                   "set": {"type": "string", "minLength": 1}},
}, render_chip, check=check_chip, inline=True)

register_component("text", {
    "type": "object", "additionalProperties": False, "required": ["text"],
    "properties": {"text": {"type": "string"}, "tone": {"enum": TONES}, "markdown": {"type": "boolean"},
                   "label": {"type": "string", "minLength": 1, "maxLength": 60},
                   "badge": {"type": "string", "minLength": 1, "maxLength": 30}},
}, render_text)
