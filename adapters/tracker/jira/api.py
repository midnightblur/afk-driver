#!/usr/bin/env afk-python
"""tracker/jira — the Jira Cloud adapter.

Two audiences, one module:

- `call(operation, payload)` answers the ten `tracker_*` operations for the
  `tracker` MCP server (ADAPTERS.md). This is the interface every tracker kind
  implements; a skill never sees Jira.
- The publishing machinery several skills import directly: credential
  resolution, a thin REST client (multipart attachment upload plus the
  media-UUID 303-redirect trick), Markdown→ADF conversion, and PNG dimension
  reading for inline media nodes.

Credentials are read from same-named OS env vars, or from the tracker MCP
server's env block in ~/.claude.json (JIRA_BASE_URL / JIRA_EMAIL /
JIRA_API_TOKEN), or from ~/.codex/config.toml [mcp_servers.tracker.env];
resolution order env > claude.json > codex config.toml. The server was once
registered as `jira`; that name counts only for afk's own entry (setup's
`is_afk_entry`). Nothing is hardcoded.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import mimetypes
import os
import re
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from markdown_it import MarkdownIt


# ============================================================================
# Credentials
# ============================================================================
# Setup owns both server names and the test for "is this entry afk's own". The
# legacy `jira` name counts only for afk's own entry, never another vendor's.
PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def _registration_module():
    spec = importlib.util.spec_from_file_location(
        "afk_tracker_registration",
        PLUGIN_ROOT / "skills" / "afk" / "setup" / "scripts" / "tracker_registration.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


registration = _registration_module()
SERVER_NAMES = (registration.MCP_KEY, registration.LEGACY_MCP_KEY)


# The shared payload reader (adapters/tracker/payload.py). The adapters folder
# is not a package root, so it is loaded by file, the way this adapter itself is
# loaded by scripts/tracker_api.py.
def _payload_module():
    spec = importlib.util.spec_from_file_location(
        "afk_tracker_payload", Path(__file__).resolve().parent.parent / "payload.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


payload_reader = _payload_module()


def _walk_for_jira_env(obj):
    if isinstance(obj, dict):
        for name in SERVER_NAMES:
            server = obj.get(name)
            if (name == registration.LEGACY_MCP_KEY and isinstance(server, dict)
                    and not registration.is_afk_entry(server, PLUGIN_ROOT)):
                continue
            if isinstance(server, dict) and isinstance(server.get("env"), dict):
                return server["env"]
        for v in obj.values():
            r = _walk_for_jira_env(v)
            if r:
                return r
    return None


def _codex_jira_env():
    """Jira env block from ~/.codex/config.toml [mcp_servers.tracker.env] (py3.11+;
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


CRED_KEYS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")


def resolve_creds_env():
    """The `JIRA_*` values the credential chain resolves, per field, in order:
    exported variables, `~/.claude.json`, `~/.codex/config.toml`. Never exits;
    an unresolved field is absent."""
    found = {k: os.environ[k] for k in CRED_KEYS if os.environ.get(k)}
    sources = []
    cfg_path = Path.home() / ".claude.json"
    if cfg_path.exists():
        try:
            sources.append(_walk_for_jira_env(json.loads(cfg_path.read_text(encoding="utf-8"))))
        except Exception:
            pass
    sources.append(_codex_jira_env())
    for env in sources:
        for k in CRED_KEYS:
            if env and k not in found and env.get(k):
                found[k] = env[k]
    return found


def load_creds():
    found = resolve_creds_env()
    if len(found) < len(CRED_KEYS):
        sys.exit("ERROR: could not resolve Jira creds (JIRA_BASE_URL/EMAIL/API_TOKEN "
                 "from env, ~/.claude.json mcpServers.tracker.env, or "
                 "~/.codex/config.toml [mcp_servers.tracker.env]).")
    return found["JIRA_BASE_URL"].rstrip("/"), found["JIRA_EMAIL"], found["JIRA_API_TOKEN"]


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
        """Multipart upload of one file. Returns the attachment id (str)."""
        return self.upload_attachments(key, [filepath])[0]["id"]

    def upload_attachments(self, key, filepaths):
        """One multipart upload; each part carries its file's real content type.
        Returns Jira's answer: one attachment object per file."""
        boundary = "----afkPrdBoundary7MA4YWxkTrZu0gW"
        parts = []
        for filepath in filepaths:
            fname = os.path.basename(filepath).replace('"', "%22")
            with open(filepath, "rb") as f:
                payload = f.read()
            parts += [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'.encode(),
                f"Content-Type: {content_type(filepath)}\r\n\r\n".encode(),
                payload, b"\r\n",
            ]
        parts.append(f"--{boundary}--\r\n".encode())
        r = self._req("POST", f"/rest/api/3/issue/{key}/attachments", data=b"".join(parts),
                      headers={"X-Atlassian-Token": "no-check",
                               "Content-Type": f"multipart/form-data; boundary={boundary}"})
        return json.loads(r.read())

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
# Content types — sent with each upload, so Jira stores the file as what it is
CONTENT_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".txt": "text/plain", ".log": "text/plain", ".md": "text/markdown",
    ".json": "application/json", ".html": "text/html", ".xml": "application/xml",
    ".zip": "application/zip",
}


def content_type(path):
    """The file's media type: the table above, then the platform's guess."""
    suffix = os.path.splitext(path)[1].lower()
    return (CONTENT_TYPES.get(suffix) or mimetypes.guess_type(path)[0]
            or "application/octet-stream")


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


# ============================================================================
# The tracker contract — the ten operations every tracker kind answers
# ============================================================================
OPERATIONS = (
    "tracker_get", "tracker_search", "tracker_create", "tracker_edit",
    "tracker_comment", "tracker_transition", "tracker_transitions",
    "tracker_attachments", "tracker_changelog", "tracker_attach",
)

DEFAULT_FIELDS = ("summary,status,issuetype,assignee,reporter,priority,"
                  "created,updated,labels,components")
SEARCH_FIELDS = ["summary", "status", "issuetype", "assignee", "priority",
                 "created", "updated"]

_CLIENT = None
_CLIENT_CREDS = None


def client():
    """The one REST client. Credentials resolve on every call and the client is
    rebuilt when they differ, so a corrected token or URL needs no restart."""
    global _CLIENT, _CLIENT_CREDS
    creds = load_creds()
    if _CLIENT is None or creds != _CLIENT_CREDS:
        _CLIENT, _CLIENT_CREDS = Jira(*creds), creds
    return _CLIENT


def _json(method, path, body=None, params=None):
    """One REST call, answering parsed JSON or a described error — never raising
    at the operation boundary: an MCP tool that throws tells the caller nothing
    about what went wrong on the far side."""
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
        if query:
            path = f"{path}?{query}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else None
    try:
        r = client()._req(method, path, data=data, headers=headers)
    except urllib.error.HTTPError as e:
        return {"error": True, "status": e.code, "body": e.read().decode("utf-8", "replace")[:2000]}
    except Exception as e:  # network, DNS, timeout
        return {"error": True, "reason": f"{type(e).__name__}: {e}"}
    raw = r.read()
    if not raw:
        return {"ok": True}
    try:
        return json.loads(raw)
    except ValueError:
        return {"raw": raw.decode("utf-8", "replace")[:2000]}


def _adf_doc(text, extra=()):
    """Markdown text as an Atlassian Document Format document, then the
    `extra` block nodes."""
    content = md_to_adf_content(text or "", {}) + list(extra)
    return {"type": "doc", "version": 1,
            "content": content or [{"type": "paragraph", "content": []}]}


def _default_project():
    return os.environ.get("JIRA_DEFAULT_PROJECT", "")


_READER = None


def transitions_config():
    """`jira.transitions` (key -> transition name or id), read from the project
    root on every call. Empty when the repository declared none."""
    global _READER
    if _READER is None:
        spec = importlib.util.spec_from_file_location(
            "afk_config", PLUGIN_ROOT / "scripts" / "afk-config.py")
        _READER = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_READER)
    block = _READER.get(_READER.load(_READER.project_root()), "jira") or {}
    value = block.get("transitions") if isinstance(block, dict) else None
    return value if isinstance(value, dict) else {}


def _refused(operation, reason):
    return {"error": True, "refused": True, "operation": operation,
            "reason": f"{reason}; nothing was written"}


def _resolve_transition(key, given, operation):
    """(transition id, None) for `given` — a `jira.transitions` key, a
    transition name or an id — or (None, the answer) when the issue offers none."""
    try:
        configured = transitions_config()
    except Exception as e:  # an unreadable config is named, never guessed past
        return None, {"error": True, "operation": operation,
                      "reason": f"jira.transitions unreadable: {type(e).__name__}: {e}"}
    wanted = str(configured.get(given, given))
    listed = _json("GET", f"/rest/api/3/issue/{key}/transitions")
    if not isinstance(listed, dict) or listed.get("error"):
        return None, listed
    transitions = listed.get("transitions") or []
    for t in transitions:
        if str(t.get("id")) == wanted or str(t.get("name", "")).lower() == wanted.lower():
            return str(t["id"]), None
    offered = ", ".join(f"{t.get('name')} ({t.get('id')})" for t in transitions) or "none"
    via = f" (`jira.transitions.{given}`)" if given in configured else ""
    return None, _refused(operation, f"{key} has no transition `{wanted}`{via}; "
                                     f"it offers: {offered}")


def _check_fix_versions(project, wanted, operation):
    """None when every entry of `wanted` (a name, or a {"name"} or {"id"}
    object) is a version of the project; else the refusal or the read error."""
    versions = _json("GET", f"/rest/api/3/project/{project}/versions")
    if not isinstance(versions, list):
        return versions if isinstance(versions, dict) else {
            "error": True, "operation": operation, "reason": "unreadable project versions"}
    names = {str(v.get("name")) for v in versions}
    ids = {str(v.get("id")) for v in versions}
    unknown = []
    for entry in wanted:
        entry = entry if isinstance(entry, dict) else {"name": entry}
        if str(entry.get("name")) not in names and str(entry.get("id")) not in ids:
            unknown.append(str(entry.get("name") or entry.get("id")))
    if unknown:
        known = ", ".join(sorted(names)) or "none"
        return _refused(operation, f"fix version {', '.join(unknown)} does not exist in "
                                   f"project {project} (known: {known})")
    return None


def _op_get(p):
    key = p["ticket_key"]
    return _json("GET", f"/rest/api/3/issue/{key}",
                 params={"fields": p.get("fields") or DEFAULT_FIELDS})


def _op_search(p):
    # `fields` is a comma string on tracker_get and a list here, so accept both
    # in both places: one adapter must not ask a caller to remember which verb
    # takes which shape. A comma string reaches /search/jql as a 400 otherwise.
    fields = p.get("fields") or SEARCH_FIELDS
    if isinstance(fields, str):
        fields = [f.strip() for f in fields.split(",") if f.strip()]
    return _json("POST", "/rest/api/3/search/jql", body={
        "jql": p["query"],
        "maxResults": int(p.get("max_results") or 50),
        "fields": fields,
    })


def _op_transitions(p):
    return _json("GET", f"/rest/api/3/issue/{p['ticket_key']}/transitions")


def _op_transition(p):
    key = p["ticket_key"]
    transition_id, refusal = _resolve_transition(key, p["transition_id"], "tracker_transition")
    if refusal is not None:
        return refusal
    return _json("POST", f"/rest/api/3/issue/{key}/transitions",
                 body={"transition": {"id": transition_id}})


def _op_changelog(p):
    return _json("GET", f"/rest/api/3/issue/{p['ticket_key']}",
                 params={"expand": "changelog"})


def _op_comment(p):
    return _json("POST", f"/rest/api/3/issue/{p['ticket_key']}/comment",
                 body={"body": _adf_doc(p["text"])})


def _op_attachments(p):
    data = _json("GET", f"/rest/api/3/issue/{p['ticket_key']}",
                 params={"fields": "attachment"})
    if not (isinstance(data, dict) and "fields" in data):
        return data
    return [{"id": a.get("id"), "filename": a.get("filename"),
             "mimeType": a.get("mimeType"), "size": a.get("size"),
             "created": a.get("created"),
             "author": (a.get("author") or {}).get("displayName"),
             "content": a.get("content")}
            for a in (data.get("fields", {}).get("attachment") or [])]


def _op_edit(p):
    key, fields = p["ticket_key"], p["fields"]
    wanted = fields.get("fixVersions") if isinstance(fields, dict) else None
    if wanted:
        issue = _json("GET", f"/rest/api/3/issue/{key}", params={"fields": "project"})
        if isinstance(issue, dict) and issue.get("error"):
            return issue
        project = (((issue or {}).get("fields") or {}).get("project") or {}).get("key") \
            if isinstance(issue, dict) else None
        if not project:
            return _refused("tracker_edit", f"could not read the project of {key} "
                                            f"to check its fix versions")
        refusal = _check_fix_versions(project, wanted, "tracker_edit")
        if refusal is not None:
            return refusal
    return _json("PUT", f"/rest/api/3/issue/{key}", body={"fields": fields})


def _op_create(p):
    project = p.get("project") or _default_project()
    if not project:
        return {"error": True,
                "message": "project is required (no JIRA_DEFAULT_PROJECT, and "
                           "`jira.project` in .afk/config.yaml was not passed)"}

    fields = {"project": {"key": project},
              "issuetype": {"name": p["issue_type"]},
              "summary": p["summary"]}
    if p.get("description"):
        fields["description"] = _adf_doc(p["description"])
    if p.get("parent"):
        fields["parent"] = {"key": p["parent"]}
    if p.get("fix_version"):
        refusal = _check_fix_versions(project, [p["fix_version"]], "tracker_create")
        if refusal is not None:
            return refusal
        fields["fixVersions"] = [{"name": p["fix_version"]}]

    created = _json("POST", "/rest/api/3/issue", body={"fields": fields})
    key = created.get("key") if isinstance(created, dict) else None
    if not key:
        return created
    result = {"key": key, "id": created.get("id")}

    # Assignment and the opening transition are separate calls, and a failure in
    # either must not lose the issue that was already created — each reports as
    # a warning on the successful create.
    assignee = p.get("assignee")
    if assignee:
        users = _json("GET", "/rest/api/3/user/assignable/search",
                      params={"query": assignee, "project": project})
        account_id = users[0]["accountId"] if isinstance(users, list) and users else None
        if account_id:
            _json("PUT", f"/rest/api/3/issue/{key}",
                  body={"fields": {"assignee": {"accountId": account_id}}})
            result["assignee"] = {"accountId": account_id, "query": assignee}
        else:
            result["assignee_warning"] = f"could not resolve '{assignee}'"

    # Jira lists transitions per issue, so the opening state is checked after
    # create; tracker_transition checks before its write.
    status = p.get("status")
    if status:
        match, refusal = _resolve_transition(key, status, "tracker_create")
        if match:
            _json("POST", f"/rest/api/3/issue/{key}/transitions",
                  body={"transition": {"id": match}})
            result["transitioned_to"] = status
        else:
            result["status_warning"] = (refusal or {}).get("reason") or f"no transition '{status}'"
    return result


def _media_node(uuid, path, mime):
    """One embedded file: an image or a video inline, any other file as a card."""
    attrs = {"type": "file", "id": uuid, "collection": ""}
    if mime.startswith(("image/", "video/")):
        size = png_size(path) if mime == "image/png" else None
        if size:
            attrs.update(width=size[0], height=size[1])
        return {"type": "mediaSingle", "attrs": {"layout": "center"},
                "content": [{"type": "media", "attrs": attrs}]}
    return {"type": "media", "attrs": attrs}


def _missing_files(files):
    """Why `files` cannot be attached, or None: it must list files on disk."""
    if not isinstance(files, list) or not files:
        return "`files` must be a non-empty list of file paths"
    gone = [str(f) for f in files if not os.path.isfile(str(f))]
    return f"no such file: {', '.join(gone)}; nothing was written" if gone else None


def _op_attach(p):
    """Upload every file in one request with its real content type, read back
    each stored name and type, then post one comment that embeds the files and
    names each mismatch."""
    key, files = p["ticket_key"], p["files"]
    problem = _missing_files(files)
    if problem:
        return {"error": True, "operation": "tracker_attach", "reason": problem}
    files = list(dict.fromkeys(str(f) for f in files))
    try:
        uploaded = client().upload_attachments(key, files)
    except urllib.error.HTTPError as e:
        return {"error": True, "operation": "tracker_attach", "status": e.code,
                "body": e.read().decode("utf-8", "replace")[:2000]}
    except Exception as e:  # network, DNS, timeout
        return {"error": True, "operation": "tracker_attach",
                "reason": f"{type(e).__name__}: {e}"}

    stored = _json("GET", f"/rest/api/3/issue/{key}", params={"fields": "attachment"})
    listed = ((stored.get("fields") or {}).get("attachment") or []) if isinstance(stored, dict) else []
    by_id = {str(a.get("id")): a for a in listed}
    attached, mismatches, inline, cards, notes = [], [], [], [], []
    # Jira answers one attachment per part, in part order (unverified; live check before release).
    for path, answer in zip(files, uploaded if isinstance(uploaded, list) else []):
        att_id = str(answer.get("id"))
        sent = {"filename": os.path.basename(path), "mimeType": content_type(path)}
        found = by_id.get(att_id) or {}
        got = {"filename": found.get("filename"), "mimeType": found.get("mimeType")}
        attached.append({"file": path, "id": att_id, **got})
        if got != sent:
            mismatches.append({"file": path, "id": att_id, "sent": sent, "stored": got})
            notes.append(f"- `{sent['filename']}` was sent as {sent['mimeType']} and is "
                         f"stored as `{got['filename']}` ({got['mimeType']})")
        try:
            node = _media_node(client().resolve_media_uuid(att_id), path, sent["mimeType"])
        except Exception as e:  # attached but not embeddable: the comment says so
            notes.append(f"- `{sent['filename']}` is attached but not embedded ({type(e).__name__})")
            continue
        (inline if node["type"] == "mediaSingle" else cards).append(node)

    text = p.get("text") or ""
    if notes:
        text += "\n\n**Check these files:**\n\n" + "\n".join(notes)
    extra = inline + ([{"type": "mediaGroup", "content": cards}] if cards else [])
    comment = _json("POST", f"/rest/api/3/issue/{key}/comment",
                    body={"body": _adf_doc(text, extra)})
    result = {"ticket_key": key, "attached": attached, "mismatches": mismatches,
              "unsupported_files": []}
    if isinstance(comment, dict) and comment.get("error"):
        return {"error": True, "operation": "tracker_attach",
                "reason": "the files are attached; the comment failed", "comment_error": comment,
                **result}
    return {"ok": True, "comment": comment.get("id") if isinstance(comment, dict) else None,
            **result}


_DISPATCH = {
    "tracker_get": _op_get,
    "tracker_search": _op_search,
    "tracker_create": _op_create,
    "tracker_edit": _op_edit,
    "tracker_comment": _op_comment,
    "tracker_transition": _op_transition,
    "tracker_transitions": _op_transitions,
    "tracker_attachments": _op_attachments,
    "tracker_changelog": _op_changelog,
    "tracker_attach": _op_attach,
}


def call(operation, payload=None):
    """The one entry point every tracker adapter exposes."""
    fn = _DISPATCH.get(operation)
    if fn is None:
        return {"unsupported": True, "operation": operation,
                "reason": f"tracker/jira has no operation {operation}"}
    try:
        return fn(payload or {})
    except KeyError as e:
        return {"error": True, "operation": operation,
                "reason": f"missing required argument {e}"}
    except SystemExit as e:
        # `load_creds` exits for the CLI; in the server that would end it. No
        # client is cached, so the next call re-reads the credentials.
        return {"error": True, "operation": operation, "reason": str(e.code)}


def main(argv):
    if argv and argv[0] == "--check-creds":
        # Presence only: load_creds exits with its own message when a variable
        # is missing, and nothing here prints a value.
        load_creds()
        print("ok")
        return 0
    if argv and argv[0] == "--list-tools":
        for name in OPERATIONS:
            print(name)
        return 0
    if not argv:
        print(json.dumps({"operations": list(OPERATIONS)}))
        return 0
    payload, unreadable = payload_reader.parse(
        argv[1] if len(argv) > 1 else None, argv[0])
    if unreadable is not None:
        print(json.dumps(unreadable))
        return payload_reader.EXIT_UNREADABLE_PAYLOAD
    answer = call(argv[0], payload)
    print(json.dumps(answer))
    return 3 if isinstance(answer, dict) and answer.get("unsupported") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
