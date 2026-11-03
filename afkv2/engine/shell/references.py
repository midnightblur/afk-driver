"""Make each reference in page text a link that opens in a new tab: a ticket, a forge change, a commit.

`session.links` holds one URL template per kind, with `{id}` where the reference goes:

  issue   `#123`
  change  `!123`, and `#123` or `!123` after "PR", "MR", "pull request" or "merge request"
  ticket  `ABC-123`, only for a project key in `projects`
  commit  7 to 40 hex characters after "commit" or "sha", and 40 hex characters alone

A kind with no template stays text. Only text between tags changes, so ids and attributes keep their
bytes. Text in a link, code, a script, a style, a form control, a fold label or an SVG stays text.
"""

from __future__ import annotations

import re
from html import escape

SKIPPED = {"a", "button", "code", "label", "option", "pre", "script", "select", "style", "summary", "svg", "textarea"}
TAG = re.compile(r"(<[^>]*>)")
TAG_NAME = re.compile(r"<(/?)([A-Za-z][\w-]*)")
CHANGE_WORDS = r"(?i:\b(?:PR|MR|pull request|merge request)\s+)"
COMMIT_WORDS = r"(?i:\b(?:commits?|sha)\b:?\s+)"
LINK = '<a class="afkv2-ref" href="{}" target="_blank" rel="noopener noreferrer">{}</a>'


def _pattern(links: dict) -> re.Pattern | None:
    parts = []
    if links.get("change"):
        parts.append(rf"(?P<cw>{CHANGE_WORDS})(?P<cr>[#!]\d+)\b")
        parts.append(r"(?<![\w!&])(?P<c>!\d+)\b")
    if links.get("issue"):
        parts.append(r"(?<![\w/&#])(?P<i>#\d+)\b")
    projects = [p for p in links.get("projects") or [] if p]
    if links.get("ticket") and projects:
        keys = "|".join(re.escape(p) for p in sorted(projects, key=len, reverse=True))
        parts.append(rf"(?<![\w-])(?P<t>(?:{keys})-\d+)(?![\w-])")
    if links.get("commit"):
        parts.append(rf"(?P<kw>{COMMIT_WORDS})(?P<k>[0-9a-f]{{7,40}})(?![\w-])")
        parts.append(r"(?<![\w-])(?P<f>[0-9a-f]{40})(?![\w-])")
    return re.compile("|".join(parts)) if parts else None


def _href(template: str, reference: str) -> str:
    return escape(template.replace("{id}", reference.lstrip("#!")))


def _replace(links: dict):
    def link(match: re.Match) -> str:
        found = match.groupdict()
        if found.get("cr"):
            return found["cw"] + LINK.format(_href(links["change"], found["cr"]), found["cr"])
        for group, kind in (("c", "change"), ("i", "issue"), ("t", "ticket"), ("f", "commit")):
            if found.get(group):
                return LINK.format(_href(links[kind], found[group]), found[group])
        return found["kw"] + LINK.format(_href(links["commit"], found["k"]), found["k"])
    return link


def linkify(html: str, links: dict | None) -> str:
    """The same HTML with every reference in its text linked; without `links` the same bytes."""
    pattern = _pattern(links or {})
    if pattern is None:
        return html
    replace, depth, out = _replace(links), 0, []
    for index, part in enumerate(TAG.split(html)):
        if index % 2:
            tag = TAG_NAME.match(part)
            if tag and tag.group(2).lower() in SKIPPED and not part.endswith("/>"):
                depth = max(depth + (-1 if tag.group(1) else 1), 0)
            out.append(part)
        else:
            out.append(part if depth or not part else pattern.sub(replace, part))
    return "".join(out)
