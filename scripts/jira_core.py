#!/usr/bin/env python3
"""
jira_core — shared Jira Cloud machinery for the AFK workflow plugin.

One home (ADR-0001, afk-bug) for the reusable mechanics several skills need to
write to Jira: credential resolution, a thin REST client (incl. multipart
attachment upload + the media-UUID 303-redirect trick), Markdown→ADF conversion,
and PNG dimension reading for inline media nodes.

Behavior matches the original inline implementation it was extracted from.
Skill-specific concerns (sentinel-block/description merge, mermaid rendering)
stay in the importing scripts.

Credentials are read from same-named OS env vars, or from the Jira MCP server's
env block in ~/.claude.json (JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN), or
from ~/.codex/config.toml [mcp_servers.jira.env]; resolution order env >
claude.json > codex config.toml (per-provider map: plugin PROVIDERS.md).
Nothing is hardcoded.
"""

from __future__ import annotations

import base64
import json
import os
import re
import struct
import sys
import urllib.error
import urllib.request
from pathlib import Path

from markdown_it import MarkdownIt


# ============================================================================
# Credentials
# ============================================================================
def _walk_for_jira_env(obj):
    if isinstance(obj, dict):
        jira = obj.get("jira")
        if isinstance(jira, dict) and isinstance(jira.get("env"), dict):
            return jira["env"]
        for v in obj.values():
            r = _walk_for_jira_env(v)
            if r:
                return r
    return None


def _codex_jira_env():
    """Jira env block from ~/.codex/config.toml [mcp_servers.jira.env] (py3.11+;
    older interpreters lack tomllib and just skip this fallback layer)."""
    cfg_path = Path.home() / ".codex" / "config.toml"
    if not cfg_path.exists():
        return None
    try:
        import tomllib
    except ImportError:
        return None
    try:
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return _walk_for_jira_env(data.get("mcp_servers") or data.get("mcpServers") or {})


def load_creds():
    base = os.environ.get("JIRA_BASE_URL")
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    sources = []
    cfg_path = Path.home() / ".claude.json"
    if cfg_path.exists():
        try:
            sources.append(_walk_for_jira_env(json.loads(cfg_path.read_text(encoding="utf-8"))))
        except Exception:
            pass
    sources.append(_codex_jira_env())
    for env in sources:
        if base and email and token:
            break
        if env:
            base = base or env.get("JIRA_BASE_URL")
            email = email or env.get("JIRA_EMAIL")
            token = token or env.get("JIRA_API_TOKEN")
    if not (base and email and token):
        sys.exit("ERROR: could not resolve Jira creds (JIRA_BASE_URL/EMAIL/API_TOKEN "
                 "from env, ~/.claude.json mcpServers.jira.env, or "
                 "~/.codex/config.toml [mcp_servers.jira.env]).")
    return base.rstrip("/"), email, token


class Jira:
    def __init__(self, base, email, token):
        self.base = base
        self.auth = "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()

    def _req(self, method, path, data=None, headers=None, follow=True):
        url = path if path.startswith("http") else self.base + path
        h = {"Authorization": self.auth, "Accept": "application/json"}
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, data=data, method=method, headers=h)
        if follow:
            return urllib.request.urlopen(req, timeout=60)
        opener = urllib.request.build_opener(_NoRedirect)
        return opener.open(req, timeout=60)

    def get_issue(self, key, fields):
        r = self._req("GET", f"/rest/api/3/issue/{key}?fields={fields}")
        return json.loads(r.read())

    def update_description(self, key, adf):
        # notifyUsers=false would suppress watcher notifications, but Jira only
        # honours it for project/system admins (else 403), so we don't send it.
        body = json.dumps({"fields": {"description": adf}}).encode()
        self._req("PUT", f"/rest/api/3/issue/{key}", data=body,
                  headers={"Content-Type": "application/json"})

    def add_comment(self, key, adf):
        """POST an ADF doc as an issue comment. Returns the comment id (str)."""
        body = json.dumps({"body": adf}).encode()
        r = self._req("POST", f"/rest/api/3/issue/{key}/comment", data=body,
                      headers={"Content-Type": "application/json"})
        return json.loads(r.read()).get("id")

    def delete_attachment(self, att_id):
        try:
            self._req("DELETE", f"/rest/api/3/attachment/{att_id}")
        except urllib.error.HTTPError as e:
            if e.code not in (204, 200, 404):
                raise

    def upload_attachment(self, key, filepath):
        """Multipart upload. Returns the attachment id (str)."""
        boundary = "----afkPrdBoundary7MA4YWxkTrZu0gW"
        fname = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            payload = f.read()
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'.encode(),
            b"Content-Type: image/png\r\n\r\n",
            payload, b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ])
        r = self._req("POST", f"/rest/api/3/issue/{key}/attachments", data=body,
                      headers={"X-Atlassian-Token": "no-check",
                               "Content-Type": f"multipart/form-data; boundary={boundary}"})
        arr = json.loads(r.read())
        return arr[0]["id"]

    def resolve_media_uuid(self, att_id):
        """GET attachment content, do NOT follow the 303; pull the UUID out of
        the api.media.atlassian.com/file/{uuid}/binary Location header."""
        try:
            r = self._req("GET", f"/rest/api/3/attachment/content/{att_id}", follow=False)
            loc = r.headers.get("Location", "")
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location", "")
        m = re.search(r"/file/([0-9a-fA-F-]{36})", loc)
        if not m:
            raise RuntimeError(f"could not resolve media UUID for attachment {att_id} "
                               f"(Location={loc!r})")
        return m.group(1)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


# ============================================================================
# PNG dimensions (read IHDR)
# ============================================================================
def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    # A truncated file may carry the signature yet lack the IHDR width/height;
    # treat anything short of the 24-byte header as "unknown" so callers fall
    # back rather than crashing on a struct.error.
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return int(w), int(h)


# ============================================================================
# Markdown -> ADF
# ============================================================================
# Placeholder inserted in place of a rendered-figure block. Plain ASCII so
# CommonMark does not rewrite it (it replaces U+0000 with U+FFFD, so null
# sentinels break). The importing script substitutes each token index with a
# media block via the `fig_nodes` mapping passed to md_to_adf_content.
FIG_TOKEN = "AFKMERMAIDFIGURE{}ENDFIGURE"


def _inline_to_adf(token):
    """Convert one markdown-it `inline` token's children to ADF inline nodes."""
    out = []
    marks = []

    def push_text(text):
        if not text:
            return
        node = {"type": "text", "text": text}
        ms = _adf_marks(marks)
        if ms:
            node["marks"] = ms
        out.append(node)

    for c in token.children or []:
        t = c.type
        if t == "text":
            push_text(c.content)
        elif t == "code_inline":
            node = {"type": "text", "text": c.content,
                    "marks": _adf_marks(marks + [{"type": "code"}])}
            out.append(node)
        elif t == "strong_open":
            marks.append({"type": "strong"})
        elif t == "strong_close":
            _pop(marks, "strong")
        elif t == "em_open":
            marks.append({"type": "em"})
        elif t == "em_close":
            _pop(marks, "em")
        elif t == "s_open":
            marks.append({"type": "strike"})
        elif t == "s_close":
            _pop(marks, "strike")
        elif t == "link_open":
            href = dict(c.attrs).get("href", "")
            # Jira ADF rejects link marks whose href is not an absolute URI it
            # can render (relative repo paths, in-doc #anchors) with a generic
            # INVALID_INPUT. Keep the link text, drop the unrenderable href.
            if re.match(r"(?:https?|mailto):", href, re.I):
                marks.append({"type": "link", "attrs": {"href": href}})
        elif t == "link_close":
            _pop(marks, "link")
        elif t == "softbreak":
            push_text(" ")
        elif t == "hardbreak":
            out.append({"type": "hardBreak"})
        elif t == "image":
            # rare in a PRD; degrade to the alt text as plain text
            push_text(c.content or dict(c.attrs).get("alt", "") or "[image]")
        # unknown inline types are dropped deterministically
    return out or [{"type": "text", "text": ""}]


def _adf_marks(marks):
    """Copy the mark stack into ADF marks. Jira's `code` mark is exclusive — it
    may only co-exist with `link`; combined with strong/em/strike it triggers a
    generic INVALID_INPUT. So when `code` is present, drop the rest."""
    ms = [dict(m) for m in marks]
    if any(m["type"] == "code" for m in ms):
        ms = [m for m in ms if m["type"] in ("code", "link")]
    return ms


def _pop(marks, mtype):
    for i in range(len(marks) - 1, -1, -1):
        if marks[i]["type"] == mtype:
            marks.pop(i)
            return


def md_to_adf_content(md_text, fig_nodes):
    """Return an ADF content array (list of block nodes). fig_nodes maps
    placeholder index -> media block node (already built)."""
    md = MarkdownIt("gfm-like", {"linkify": False, "html": False})
    tokens = md.parse(md_text)
    content, _ = _build_blocks(tokens, 0, None, fig_nodes)
    return content


def _build_blocks(tokens, i, stop, fig_nodes):
    """Build a list of block nodes until a `stop` close-token is hit.
    Returns (nodes, next_index)."""
    nodes = []
    while i < len(tokens):
        tok = tokens[i]
        t = tok.type
        if stop and t == stop:
            return nodes, i + 1

        if t == "heading_open":
            level = int(tok.tag[1])
            inline = tokens[i + 1]
            nodes.append({"type": "heading", "attrs": {"level": level},
                          "content": _inline_to_adf(inline)})
            i += 3  # open, inline, close
        elif t == "paragraph_open":
            inline = tokens[i + 1]
            text = inline.content.strip()
            m = re.fullmatch(r"AFKMERMAIDFIGURE(\d+)ENDFIGURE", text)
            if m:  # a mermaid placeholder paragraph -> media block(s)
                nodes.extend(fig_nodes.get(int(m.group(1)), []))
            else:
                nodes.append({"type": "paragraph", "content": _inline_to_adf(inline)})
            i += 3
        elif t == "bullet_list_open":
            children, i = _build_list_items(tokens, i + 1, "bullet_list_close", fig_nodes)
            nodes.append({"type": "bulletList", "content": children})
        elif t == "ordered_list_open":
            attrs = dict(tok.attrs)
            node = {"type": "orderedList", "content": None}
            if "start" in attrs and str(attrs["start"]) != "1":
                node["attrs"] = {"order": int(attrs["start"])}
            children, i = _build_list_items(tokens, i + 1, "ordered_list_close", fig_nodes)
            node["content"] = children
            nodes.append(node)
        elif t == "blockquote_open":
            children, i = _build_blocks(tokens, i + 1, "blockquote_close", fig_nodes)
            nodes.append({"type": "blockquote", "content": children})
        elif t == "hr":
            nodes.append({"type": "rule"})
            i += 1
        elif t == "fence" or t == "code_block":
            attrs = {}
            # tok.info is the raw, untrimmed post-marker text; a fence opened
            # with only whitespace after the backticks yields a truthy but
            # empty-once-split info, so guard on the split result, not on
            # tok.info itself (else [0] raises IndexError and aborts publish).
            info_parts = (tok.info or "").strip().split()
            lang = info_parts[0] if info_parts else ""
            if lang:
                attrs["language"] = lang
            node = {"type": "codeBlock", "content": [{"type": "text", "text": tok.content.rstrip("\n")}]}
            if attrs:
                node["attrs"] = attrs
            nodes.append(node)
            i += 1
        elif t == "table_open":
            node, i = _build_table(tokens, i + 1, fig_nodes)
            nodes.append(node)
        else:
            i += 1  # skip tokens we don't map (e.g. stray inline)
    return nodes, i


def _build_list_items(tokens, i, stop, fig_nodes):
    items = []
    while i < len(tokens):
        if tokens[i].type == stop:
            return items, i + 1
        if tokens[i].type == "list_item_open":
            children, i = _build_blocks(tokens, i + 1, "list_item_close", fig_nodes)
            if not children:
                children = [{"type": "paragraph", "content": [{"type": "text", "text": ""}]}]
            items.append({"type": "listItem", "content": children})
        else:
            i += 1
    return items, i


def _build_table(tokens, i, fig_nodes):
    rows = []
    is_header_section = False
    while i < len(tokens):
        t = tokens[i].type
        if t == "table_close":
            i += 1
            break
        if t == "thead_open":
            is_header_section = True
            i += 1
        elif t == "thead_close":
            is_header_section = False
            i += 1
        elif t == "tbody_open" or t == "tbody_close":
            i += 1
        elif t == "tr_open":
            cells = []
            i += 1
            while tokens[i].type != "tr_close":
                ct = tokens[i].type
                if ct in ("th_open", "td_open"):
                    cell_type = "tableHeader" if ct == "th_open" else "tableCell"
                    inline = tokens[i + 1]
                    cells.append({"type": cell_type, "attrs": {},
                                  "content": [{"type": "paragraph",
                                               "content": _inline_to_adf(inline)}]})
                    i += 3  # open, inline, close
                else:
                    i += 1
            rows.append({"type": "tableRow", "content": cells})
            i += 1  # skip tr_close
        else:
            i += 1
    return {"type": "table", "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
            "content": rows}, i
