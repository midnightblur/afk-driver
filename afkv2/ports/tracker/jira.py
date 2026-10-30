"""Jira Cloud REST v3: the client ported from v1, and the publish verbs on it. No create, transition or comment."""

from __future__ import annotations

import base64
import functools
import hashlib
import json
import os
import re
import struct
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NamedTuple

from . import adf, v1_facts
from .envelope import Refusal, code_for_status, need, ok

TIMEOUT_SECONDS = 60
CRED_KEYS = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
CREDENTIAL_SERVER = "tracker"
BEGIN_LINE = "afkv2:prd:start"
END_LINE = "afkv2:prd:end"
PICTURE_NAME = re.compile(r"afkv2-fig-[0-9a-f]{8}-\d+\.png")
DEFAULT_FIELDS = ("summary,status,issuetype,assignee,reporter,priority,created,updated,labels,components,"
                  "description,comment,issuelinks")
_RECEIPT = re.compile(r"[0-9a-f]{64}")
_BEGINS = {BEGIN_LINE: "afkv2", **{line: "v1" for line in v1_facts.BLOCK_BEGIN_LINES}}
_ENDS = {END_LINE: "afkv2", v1_facts.BLOCK_END_LINE: "v1"}


def _walk_for_jira_env(obj):
    if isinstance(obj, dict):
        server = obj.get(CREDENTIAL_SERVER)
        if isinstance(server, dict) and isinstance(server.get("env"), dict):
            return server["env"]
        for value in obj.values():
            found = _walk_for_jira_env(value)
            if found:
                return found
    return None


def _claude_env():
    path = Path.home() / ".claude.json"
    try:
        return _walk_for_jira_env(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def _codex_env():
    path = Path.home() / ".codex" / "config.toml"
    try:
        import tomllib
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (ImportError, OSError, ValueError):
        return None
    return _walk_for_jira_env(data.get("mcp_servers") or data.get("mcpServers") or {})


def resolve_creds_env():
    """The values found per field: exported variables, then the Claude config, then the Codex config."""
    found = {key: os.environ[key] for key in CRED_KEYS if os.environ.get(key)}
    for env in (_claude_env(), _codex_env()):
        for key in CRED_KEYS:
            if env and key not in found and env.get(key):
                found[key] = env[key]
    return found


def load_creds():
    found = resolve_creds_env()
    missing = [key for key in CRED_KEYS if key not in found]
    if missing:
        raise Refusal("no-credentials", f"no value for {', '.join(missing)} in the environment, "
                                        "the Claude user config or the Codex config")
    return found["JIRA_BASE_URL"].rstrip("/"), found["JIRA_EMAIL"], found["JIRA_API_TOKEN"]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Jira:
    def __init__(self, base, email, token):
        self.base = base
        self.auth = "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()

    def _req(self, method, path, data=None, headers=None, follow=True):
        url = path if path.startswith("http") else self.base + path
        request = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": self.auth, "Accept": "application/json", **(headers or {})})
        if follow:
            return urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
        return urllib.request.build_opener(_NoRedirect).open(request, timeout=TIMEOUT_SECONDS)

    def get_json(self, path):
        return json.loads(self._req("GET", path).read())

    def get_issue(self, key, fields):
        query = urllib.parse.urlencode({"fields": fields})
        return self.get_json(f"/rest/api/3/issue/{_segment(key)}?{query}")

    def update_description(self, key, description):
        body = json.dumps({"fields": {"description": description}}).encode()
        self._req("PUT", f"/rest/api/3/issue/{_segment(key)}", data=body, headers={"Content-Type": "application/json"})

    def delete_attachment(self, attachment_id):
        """True when deleted; False when Jira no longer has it."""
        try:
            self._req("DELETE", f"/rest/api/3/attachment/{_segment(attachment_id)}")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return False
            raise
        return True

    def upload_attachment(self, key, filepath):
        boundary = "----afkv2PrdBoundary7MA4YWxkTrZu0gW"
        name = os.path.basename(filepath)
        with open(filepath, "rb") as file:
            payload = file.read()
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'.encode(),
            b"Content-Type: image/png\r\n\r\n",
            payload, b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ])
        answer = self._req("POST", f"/rest/api/3/issue/{_segment(key)}/attachments", data=body, headers={
            "X-Atlassian-Token": "no-check", "Content-Type": f"multipart/form-data; boundary={boundary}"})
        items = json.loads(answer.read())
        if not (isinstance(items, list) and items and isinstance(items[0], dict) and items[0].get("id")):
            raise ValueError("the upload answer names no attachment id")
        return items[0]["id"]

    def resolve_media_uuid(self, attachment_id):
        """Jira gives the media id only in the Location of the 303 on the attachment content."""
        try:
            answer = self._req("GET", f"/rest/api/3/attachment/content/{_segment(attachment_id)}", follow=False)
            location = answer.headers.get("Location", "")
        except urllib.error.HTTPError as error:
            location = error.headers.get("Location", "")
        found = re.search(r"/file/([0-9a-fA-F-]{36})", location or "")
        if not found:
            raise ValueError(f"no media id in the answer for attachment {attachment_id}")
        return found.group(1)


def client():
    return Jira(*load_creds())


def _segment(value):
    return urllib.parse.quote(str(value), safe="")


def _rest(function):
    """Answer a REST failure as the named code of the status table."""
    @functools.wraps(function)
    def wrapped(payload):
        try:
            return function(payload)
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")[:2000]
            raise Refusal(code_for_status(error.code), f"Jira answered {error.code}: {body}") from None
        except (urllib.error.URLError, OSError) as error:
            raise Refusal("network", f"Jira did not answer: {type(error).__name__}: {error}") from None
        except ValueError as error:
            raise Refusal("bad-answer", f"Jira answered no readable JSON: {error}") from None
    return wrapped


def png_size(path):
    with open(path, "rb") as file:
        head = file.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return int(width), int(height)


def description_hash(description):
    """The stale check compares this: it survives a change of key order only."""
    text = json.dumps(description, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def node_text(node):
    if node.get("type") == "hardBreak":
        return "\n"
    if node.get("type") == "text":
        return node.get("text") or ""
    return "".join(node_text(child) for child in node.get("content") or [] if isinstance(child, dict))


class ManagedBlock(NamedTuple):
    start: int
    end: int
    family: str


def _lines_of(node):
    return [line.strip() for line in node_text(node).split("\n")]


def _marker_in(line):
    return line in _BEGINS or line in _ENDS


def _holds_marker(node):
    """A marker anywhere in this node. A code block quotes a marker and holds none."""
    if node.get("type") in ("paragraph", "heading"):
        return any(_marker_in(line) for line in _lines_of(node))
    return any(_holds_marker(child) for child in node.get("content") or [] if isinstance(child, dict))


def _sole_line(node):
    if node.get("type") != "paragraph":
        return None
    lines = _lines_of(node)
    return lines[0] if len(lines) == 1 and _marker_in(lines[0]) else None


def find_managed_block(content):
    """The one block in `content` by full lines; None when there is none; `bad-block` otherwise."""
    begins, ends = [], []
    for index, node in enumerate(content):
        line = _sole_line(node)
        if line in _BEGINS:
            begins.append((index, _BEGINS[line]))
        elif line in _ENDS:
            ends.append((index, _ENDS[line]))
        elif _holds_marker(node):
            raise Refusal("bad-block", f"a block line stands inside top-level node {index}, not alone on its own line")
    if len(begins) > 1 or len(ends) > 1:
        raise Refusal("bad-block", "2 or more block lines of one kind: the description holds a doubled block")
    if begins and not ends:
        raise Refusal("bad-block", "a begin line without an end line")
    if ends and not begins:
        raise Refusal("bad-block", "an end line without a begin line")
    if not begins:
        return None
    (start, family), (end, end_family) = begins[0], ends[0]
    if end < start:
        raise Refusal("bad-block", "the end line stands before the begin line")
    if family != end_family:
        raise Refusal("bad-block", "the begin and end lines come from different block families")
    return ManagedBlock(start, end, family)


def _media_ids(node):
    found = []
    if node.get("type") == "media":
        media = (node.get("attrs") or {}).get("id")
        if media:
            found.append(media)
    for child in node.get("content") or []:
        if isinstance(child, dict):
            found.extend(_media_ids(child))
    return found


def _summary(family, nodes):
    """What a read-back compares: Jira may add attributes to a node on read, so never the nodes."""
    return {"family": family,
            "text": "\n".join(node_text(node) for node in nodes),
            "media_ids": [media for node in nodes for media in _media_ids(node)]}


def _content_of(description):
    content = (description or {}).get("content")
    return content if isinstance(content, list) else []


def _preview_for(payload, key):
    """The preview the receipt names. Any miss is `bad-receipt`: the human saw no such preview."""
    receipt = payload.get("receipt")
    if not isinstance(receipt, str) or not _RECEIPT.fullmatch(receipt):
        raise Refusal("bad-receipt", "the payload needs `receipt`, 64 lowercase hex characters")
    path = payload.get("preview")
    if not path:
        raise Refusal("bad-receipt", "the payload needs `preview`, the path of the preview file")
    try:
        preview = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Refusal("bad-receipt", f"the preview file cannot be read: {error}") from None
    if not isinstance(preview, dict):
        raise Refusal("bad-receipt", "the preview file is not one JSON object")
    if preview.get("receipt") != receipt:
        raise Refusal("bad-receipt", "the receipt does not match the preview")
    if preview.get("ticket_key") != key:
        raise Refusal("bad-receipt", f"the preview is for {preview.get('ticket_key')}, not for {key}")
    return preview


def _new_nodes(value):
    nodes = value.get("content") if isinstance(value, dict) else value
    if not isinstance(nodes, list) or not nodes or not all(isinstance(node, dict) for node in nodes):
        raise Refusal("bad-payload", "`adf` must be a non-empty list of ADF nodes, or a doc that holds one")
    return nodes


def _line_node(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text, "marks": [{"type": "em"}]}]}


@_rest
def issue_get(payload):
    key = need(payload, "key")
    asked = payload.get("fields") or DEFAULT_FIELDS
    names = [name.strip() for name in asked.split(",")] if isinstance(asked, str) else list(asked)
    if "description" not in names:
        names.append("description")
    data = client().get_issue(key, ",".join(names))
    fields = dict(data.get("fields") or {})
    description = fields.pop("description", None)
    answer = ok(key=data.get("key") or key, id=data.get("id"), fields=fields, description=description,
                description_hash=description_hash(description), block=None)
    content = _content_of(description)
    try:
        block = find_managed_block(content)
    except Refusal as refusal:
        answer["block_problem"] = refusal.reason
    else:
        if block:
            answer["block"] = _summary(block.family, content[block.start + 1:block.end])
    return answer


def md_to_adf(payload):
    figures = payload.get("figures") or {}
    if not isinstance(figures, dict):
        raise Refusal("bad-payload", "`figures` must map a figure index to a list of ADF nodes")
    try:
        nodes = {int(index): value for index, value in figures.items()}
    except ValueError:
        raise Refusal("bad-payload", "`figures` keys must be figure indexes") from None
    return ok(content=adf.md_to_adf_content(need(payload, "markdown"), nodes), figure_token=adf.FIG_TOKEN)


@_rest
def attachment_list(payload):
    data = client().get_issue(need(payload, "key"), "attachment")
    items = [{"id": item.get("id"), "filename": item.get("filename"), "mimeType": item.get("mimeType"),
              "size": item.get("size"), "created": item.get("created"),
              "author": (item.get("author") or {}).get("displayName"), "content": item.get("content")}
             for item in (data.get("fields") or {}).get("attachment") or []]
    return ok(attachments=items, count=len(items))


@_rest
def attachment_put(payload):
    key, png = need(payload, "key"), need(payload, "png")
    preview = _preview_for(payload, key)
    path = Path(png)
    expected = re.compile(rf"afkv2-fig-{payload['receipt'][:8]}-\d+\.png")
    if not expected.fullmatch(path.name):
        raise Refusal("bad-name", f"{path.name} does not match afkv2-fig-{payload['receipt'][:8]}-<n>.png")
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise Refusal("bad-payload", f"the picture cannot be read: {error}") from None
    if digest not in (preview.get("picture_hashes") or []):
        raise Refusal("bad-receipt", f"the preview did not show {path.name}: its hash is not in `picture_hashes`")
    jira = client()
    attachment_id = jira.upload_attachment(key, str(path))
    try:
        media_id = jira.resolve_media_uuid(attachment_id)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise Refusal("no-media-id", f"attachment {attachment_id} is on the ticket, but its media id is unknown: {error}",
                      attachment_id=attachment_id) from None
    width, height = png_size(path) or (None, None)
    return ok(key=key, attachment_id=attachment_id, media_id=media_id, filename=path.name, width=width, height=height)


@_rest
def attachment_delete(payload):
    attachment_id = str(need(payload, "id"))
    jira = client()
    try:
        name = jira.get_json(f"/rest/api/3/attachment/{_segment(attachment_id)}").get("filename") or ""
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return ok(id=attachment_id, deleted=False)
        raise
    if not (PICTURE_NAME.fullmatch(name) or v1_facts.PICTURE_NAME.fullmatch(name)):
        raise Refusal("not-a-picture", f"attachment {attachment_id} ({name}) is not a picture of a published block")
    return ok(id=attachment_id, filename=name, deleted=jira.delete_attachment(attachment_id))


@_rest
def description_put(payload):
    key, value, expect_hash = need(payload, "key"), need(payload, "adf"), need(payload, "expect_hash")
    preview = _preview_for(payload, key)
    if preview.get("description_hash") != expect_hash:
        raise Refusal("bad-receipt", "`expect_hash` is not the description hash the preview showed")
    nodes = _new_nodes(value)
    jira = client()
    description = (jira.get_issue(key, "description").get("fields") or {}).get("description")
    if description_hash(description) != expect_hash:
        raise Refusal("stale", "the description changed after the preview: show a new preview")
    content = _content_of(description)
    block = find_managed_block(content)
    if any(_holds_marker(node) for node in nodes):
        raise Refusal("bad-block", "the new text holds a block line: it would break the next publish")
    framed = [_line_node(BEGIN_LINE), *nodes, _line_node(END_LINE)]
    if block:
        new_content = [*content[:block.start], *framed, *content[block.end + 1:]]
    else:
        new_content = [*content, *framed]
    document = {**(description or {"type": "doc", "version": 1}), "content": new_content}
    jira.update_description(key, document)
    return ok(key=key, replaced=block.family if block else None, description_hash=description_hash(document),
              block=_summary("afkv2", nodes))
