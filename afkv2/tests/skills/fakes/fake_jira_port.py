"""Recorded fake of the Jira tracker command (SDD §3; payloads as the port's CONTRACT.md states), until S3 merges.

`cli.py <verb>` with the payload on stdin, or `cli.py <verb> <json-payload>`. The ticket lives in FAKE_JIRA_STATE:
{"issues": {key: {"description": ADF doc or null, "attachments": [{"id", "filename"}]}}, "next": n}.

Environment:
  FAKE_CALL_LOG            one line `<verb> <key, id or png name>` per call
  FAKE_JIRA_FAIL           `<verb>[:<code>]` answers a refusal with that code, and writes nothing
  FAKE_JIRA_EDIT_ON_PUT    description-put first adds this text to the ticket, as a person editing at that moment
  FAKE_JIRA_CORRUPT        after a description-put, the stored block differs: `text` or `media`
  FAKE_JIRA_DROP           md-to-adf loses each line that holds this text
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import fake_v1_facts

FIG_TOKEN = "AFKV2FIGURE{}ENDFIGURE"
BEGIN_LINE, END_LINE = "afkv2:prd:start", "afkv2:prd:end"
BEGINS = {BEGIN_LINE: "afkv2", fake_v1_facts.BEGIN_LINE: "v1", fake_v1_facts.BEGIN_LINE_NOTE: "v1"}
ENDS = {END_LINE: "afkv2", fake_v1_facts.END_LINE: "v1"}


class Refused(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code, self.reason = code, reason


def text_of(node):
    if node.get("type") == "text":
        return node.get("text") or ""
    return "".join(text_of(child) for child in node.get("content") or [])


def block_text(nodes):
    return "\n".join(text for text in map(text_of, nodes) if text)


def media_ids(nodes):
    found = []
    for node in nodes:
        if node.get("type") == "media":
            found.append(node["attrs"]["id"])
        found.extend(media_ids(node.get("content") or []))
    return found


def find_block(content):
    """By full lines only. None when there is none."""
    begins = [(i, BEGINS[text_of(node)]) for i, node in enumerate(content) if text_of(node) in BEGINS]
    ends = [(i, ENDS[text_of(node)]) for i, node in enumerate(content) if text_of(node) in ENDS]
    if len(begins) > 1 or len(ends) > 1:
        raise Refused("bad-block", "2 or more block lines of one kind: the description holds a doubled block")
    if begins and not ends:
        raise Refused("bad-block", "a begin line without an end line")
    if ends and not begins:
        raise Refused("bad-block", "an end line without a begin line")
    if not begins:
        return None
    if ends[0][0] < begins[0][0]:
        raise Refused("bad-block", "the end line stands before the begin line")
    return begins[0][0], ends[0][0], begins[0][1]


def description_hash(description):
    return hashlib.sha256(json.dumps(description, sort_keys=True).encode("utf-8")).hexdigest()


def paragraph(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def to_adf(markdown, figures):
    drop = os.environ.get("FAKE_JIRA_DROP")
    nodes, fence = [], None
    token = re.compile(r"AFKV2FIGURE(\d+)ENDFIGURE")
    for line in markdown.split("\n"):
        if drop and drop in line:
            continue
        if line.startswith("```"):
            if fence is None:
                fence = []
            else:
                nodes.append({"type": "codeBlock", "content": [{"type": "text", "text": "\n".join(fence)}]})
                fence = None
        elif fence is not None:
            fence.append(line)
        elif token.fullmatch(line.strip()):
            index = token.fullmatch(line.strip()).group(1)
            if figures is not None:
                if index not in figures:
                    raise Refused("bad-payload", f"`figures` has no entry for figure {index}")
                nodes.extend(figures[index])
        elif line.startswith("#"):
            hashes = len(line) - len(line.lstrip("#"))
            nodes.append({"type": "heading", "attrs": {"level": hashes},
                          "content": [{"type": "text", "text": line[hashes:].strip()}]})
        elif line.strip():
            nodes.append(paragraph(line.strip()))
    return nodes


def read_preview(payload):
    receipt = payload.get("receipt")
    if not isinstance(receipt, str) or not re.fullmatch(r"[0-9a-f]{64}", receipt):
        raise Refused("bad-receipt", "the payload needs `receipt`")
    try:
        preview = json.loads(Path(payload["preview"]).read_text("utf-8"))
    except (KeyError, OSError, ValueError) as error:
        raise Refused("bad-receipt", f"the preview file cannot be read: {error}") from None
    if preview.get("receipt") != receipt or preview.get("ticket_key") != payload["key"]:
        raise Refused("bad-receipt", "the receipt does not match the preview")
    return preview


class Port:
    def __init__(self):
        self.path = Path(os.environ["FAKE_JIRA_STATE"])
        self.state = json.loads(self.path.read_text("utf-8"))

    def save(self):
        self.path.write_text(json.dumps(self.state), "utf-8")

    def issue(self, key):
        if key not in self.state["issues"]:
            raise Refused("not-found", key)
        return self.state["issues"][key]

    def issue_get(self, payload):
        issue = self.issue(payload["key"])
        description = issue.get("description")
        content = (description or {}).get("content") or []
        answer = {"key": payload["key"], "description": description, "description_hash": description_hash(description),
                  "block": None, "fields": {}}
        try:
            block = find_block(content)
        except Refused as refused:
            answer["block_problem"] = refused.reason
        else:
            if block:
                inner = content[block[0] + 1:block[1]]
                answer["block"] = {"family": block[2], "text": block_text(inner), "media_ids": media_ids(inner)}
        return answer

    def md_to_adf(self, payload):
        figures = payload.get("figures")
        content = to_adf(payload["markdown"], figures)
        return {"content": content, "figure_token": FIG_TOKEN, "block_text": block_text(content)}

    def attachment_list(self, payload):
        items = self.issue(payload["key"])["attachments"]
        return {"attachments": items, "count": len(items)}

    def attachment_put(self, payload):
        key, png = payload["key"], Path(payload["png"])
        preview = read_preview(payload)
        tag = payload["receipt"][:8]
        if not re.fullmatch(rf"afkv2-fig-{tag}-\d+\.png", png.name):
            raise Refused("bad-name", png.name)
        if hashlib.sha256(png.read_bytes()).hexdigest() not in preview["picture_hashes"]:
            raise Refused("bad-receipt", f"the preview did not show {png.name}")
        self.state["next"] += 1
        number = self.state["next"]
        self.issue(key)["attachments"].append({"id": str(number), "filename": png.name})
        self.save()
        return {"key": key, "attachment_id": str(number), "media_id": f"media-{number}", "filename": png.name,
                "width": 640, "height": 480}

    def attachment_delete(self, payload):
        for issue in self.state["issues"].values():
            for item in issue["attachments"]:
                if item["id"] == str(payload["id"]):
                    name = item["filename"]
                    if not (re.fullmatch(r"afkv2-fig-[0-9a-f]{8}-\d+\.png", name)
                            or name in (fake_v1_facts.PICTURE, fake_v1_facts.SECOND_PICTURE)):
                        raise Refused("not-a-picture", name)
                    issue["attachments"].remove(item)
                    self.save()
                    return {"id": str(payload["id"]), "filename": name, "deleted": True}
        return {"id": str(payload["id"]), "filename": None, "deleted": False}

    def description_put(self, payload):
        key, nodes = payload["key"], payload["adf"]
        preview = read_preview(payload)
        if preview.get("description_hash") != payload["expect_hash"]:
            raise Refused("bad-receipt", "`expect_hash` is not the hash the preview showed")
        seen = hashlib.sha256((key + block_text(nodes) + "".join(preview["picture_hashes"])).encode("utf-8")).hexdigest()
        if seen != payload["receipt"]:
            raise Refused("bad-receipt", "this text and these pictures are not what the receipt covers")
        issue = self.issue(key)
        if os.environ.get("FAKE_JIRA_EDIT_ON_PUT"):
            issue["description"]["content"].append(paragraph(os.environ["FAKE_JIRA_EDIT_ON_PUT"]))
            self.save()
        if description_hash(issue.get("description")) != payload["expect_hash"]:
            raise Refused("stale", "the description changed after the preview: show a new preview")
        description = issue.get("description") or {"type": "doc", "version": 1, "content": []}
        content = description["content"]
        block = find_block(content)
        framed = [paragraph(BEGIN_LINE), *nodes, paragraph(END_LINE)]
        content = [*content[:block[0]], *framed, *content[block[1] + 1:]] if block else [*content, *framed]
        issue["description"] = {**description, "content": content}
        corrupt = os.environ.get("FAKE_JIRA_CORRUPT")
        if corrupt == "text":
            content[content.index(framed[0]) + 1] = paragraph("Jira changed this text")
        elif corrupt == "media":
            for node in content:
                for child in node.get("content") or []:
                    if child.get("type") == "media":
                        child["attrs"]["id"] = "other-media"
        self.save()
        return {"key": key, "replaced": block[2] if block else None,
                "block": {"family": "afkv2", "text": block_text(nodes), "media_ids": media_ids(nodes)}}


def main(argv):
    verb = argv[0]
    payload = json.loads(argv[1] if len(argv) > 1 else sys.stdin.read())
    if os.environ.get("FAKE_CALL_LOG"):
        with open(os.environ["FAKE_CALL_LOG"], "a", encoding="utf-8") as out:
            label = Path(payload["png"]).name if "png" in payload else payload.get("key", payload.get("id", ""))
            out.write(f"{verb} {label}\n")
    fail_verb, _, fail_code = (os.environ.get("FAKE_JIRA_FAIL") or "").partition(":")
    try:
        if fail_verb == verb:
            raise Refused(fail_code or "server-error", f"{verb} refused by the fake")
        answer = getattr(Port(), verb.replace("-", "_"))(payload)
    except Refused as refused:
        print(json.dumps({"ok": False, "error": {"code": refused.code, "reason": refused.reason}}))
        return 1
    except AttributeError:
        print(json.dumps({"ok": False, "error": {"code": "unknown-verb", "reason": verb}}))
        return 2
    print(json.dumps({"ok": True, **answer}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
