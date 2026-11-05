"""The marks a diagram part may carry: `tip`, the text shown on hover, and `you`, a human act drawn as a
YOU mark. Graph and map nodes, run-strip steps and sequence messages share them. Registers no type."""

from html import escape

MARK_FIELDS = {"tip": {"type": "string", "minLength": 1, "maxLength": 300}, "you": {"type": "boolean"}}
YOU_CLASS = "afkv2-you"


def marks(part: dict) -> tuple[str, str]:
    """The extra class and the extra attributes of a part's element."""
    css = f" {YOU_CLASS}" if part.get("you") else ""
    attrs = f' data-afkv2-tip="{escape(part["tip"])}"' if part.get("tip") else ""
    return css, attrs
