"""Markdown to ADF, ported from the v1 Jira client."""

from __future__ import annotations

import re

from .envelope import Refusal

FIG_TOKEN = "AFKV2FIGURE{}ENDFIGURE"
_FIG_LINE = re.compile(r"AFKV2FIGURE(\d+)ENDFIGURE")


def _inline_to_adf(token):
    out = []
    marks = []

    def push_text(text):
        if not text:
            return
        node = {"type": "text", "text": text}
        current = _adf_marks(marks)
        if current:
            node["marks"] = current
        out.append(node)

    for child in token.children or []:
        kind = child.type
        if kind == "text":
            push_text(child.content)
        elif kind == "code_inline":
            out.append({"type": "text", "text": child.content, "marks": _adf_marks(marks + [{"type": "code"}])})
        elif kind == "strong_open":
            marks.append({"type": "strong"})
        elif kind == "strong_close":
            _pop(marks, "strong")
        elif kind == "em_open":
            marks.append({"type": "em"})
        elif kind == "em_close":
            _pop(marks, "em")
        elif kind == "s_open":
            marks.append({"type": "strike"})
        elif kind == "s_close":
            _pop(marks, "strike")
        elif kind == "link_open":
            href = dict(child.attrs).get("href", "")
            if re.match(r"(?:https?|mailto):", href, re.I):
                marks.append({"type": "link", "attrs": {"href": href}})
        elif kind == "link_close":
            _pop(marks, "link")
        elif kind == "softbreak":
            push_text(" ")
        elif kind == "hardbreak":
            out.append({"type": "hardBreak"})
        elif kind == "image":
            push_text(child.content or dict(child.attrs).get("alt", "") or "[image]")
    return out


def _adf_marks(marks):
    """Jira refuses `code` beside any mark but `link`."""
    current = [dict(mark) for mark in marks]
    if any(mark["type"] == "code" for mark in current):
        current = [mark for mark in current if mark["type"] in ("code", "link")]
    return current


def _pop(marks, kind):
    for index in range(len(marks) - 1, -1, -1):
        if marks[index]["type"] == kind:
            marks.pop(index)
            return


def md_to_adf_content(md_text, fig_nodes):
    """ADF block nodes; `fig_nodes` maps a figure index to the nodes that replace its token, or is None."""
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        raise Refusal("missing-dependency", "md-to-adf needs the Python package markdown-it-py: "
                                            "run `pip install markdown-it-py`") from None
    tokens = MarkdownIt("gfm-like", {"linkify": False, "html": False}).parse(md_text)
    content, _ = _build_blocks(tokens, 0, None, fig_nodes)
    return content


def _figure_nodes(index, fig_nodes):
    """No map at all builds the preview text, which holds no figure. A map without the index would lose a picture."""
    if fig_nodes is None:
        return []
    if index not in fig_nodes:
        raise Refusal("bad-payload", f"`figures` has no entry for figure {index}")
    return fig_nodes[index]


def _build_blocks(tokens, i, stop, fig_nodes):
    nodes = []
    while i < len(tokens):
        token = tokens[i]
        kind = token.type
        if stop and kind == stop:
            return nodes, i + 1
        if kind == "heading_open":
            nodes.append({"type": "heading", "attrs": {"level": int(token.tag[1])},
                          "content": _inline_to_adf(tokens[i + 1])})
            i += 3
        elif kind == "paragraph_open":
            inline = tokens[i + 1]
            figure = _FIG_LINE.fullmatch(inline.content.strip())
            if figure:
                nodes.extend(_figure_nodes(int(figure.group(1)), fig_nodes))
            else:
                nodes.append({"type": "paragraph", "content": _inline_to_adf(inline)})
            i += 3
        elif kind == "bullet_list_open":
            children, i = _build_list_items(tokens, i + 1, "bullet_list_close", fig_nodes)
            nodes.append({"type": "bulletList", "content": children})
        elif kind == "ordered_list_open":
            attrs = dict(token.attrs)
            node = {"type": "orderedList", "content": None}
            if "start" in attrs and str(attrs["start"]) != "1":
                node["attrs"] = {"order": int(attrs["start"])}
            node["content"], i = _build_list_items(tokens, i + 1, "ordered_list_close", fig_nodes)
            nodes.append(node)
        elif kind == "blockquote_open":
            children, i = _build_blocks(tokens, i + 1, "blockquote_close", fig_nodes)
            nodes.append({"type": "blockquote", "content": children})
        elif kind == "hr":
            nodes.append({"type": "rule"})
            i += 1
        elif kind in ("fence", "code_block"):
            info = (token.info or "").strip().split()
            node = {"type": "codeBlock", "content": [{"type": "text", "text": token.content.rstrip("\n")}]}
            if info:
                node["attrs"] = {"language": info[0]}
            nodes.append(node)
            i += 1
        elif kind == "table_open":
            node, i = _build_table(tokens, i + 1)
            nodes.append(node)
        else:
            i += 1
    return nodes, i


def _build_list_items(tokens, i, stop, fig_nodes):
    items = []
    while i < len(tokens):
        if tokens[i].type == stop:
            return items, i + 1
        if tokens[i].type == "list_item_open":
            children, i = _build_blocks(tokens, i + 1, "list_item_close", fig_nodes)
            items.append({"type": "listItem",
                          "content": children or [{"type": "paragraph", "content": []}]})
        else:
            i += 1
    return items, i


def _build_table(tokens, i):
    rows = []
    while i < len(tokens):
        kind = tokens[i].type
        if kind == "table_close":
            i += 1
            break
        if kind == "tr_open":
            cells = []
            i += 1
            while tokens[i].type != "tr_close":
                cell = tokens[i].type
                if cell in ("th_open", "td_open"):
                    cells.append({"type": "tableHeader" if cell == "th_open" else "tableCell", "attrs": {},
                                  "content": [{"type": "paragraph", "content": _inline_to_adf(tokens[i + 1])}]})
                    i += 3
                else:
                    i += 1
            rows.append({"type": "tableRow", "content": cells})
        i += 1
    return {"type": "table", "attrs": {"isNumberColumnEnabled": False, "layout": "default"}, "content": rows}, i
