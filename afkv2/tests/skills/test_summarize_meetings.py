"""/afkv2:summarize-meetings: 1 meeting into the comments and descriptions of its tickets, through the real tracker
port against a local stand-in for Jira."""

import copy
import json
import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
SKILL = SKILLS / "summarize-meetings"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(PLUGIN / "ports"))

import meetings  # noqa: E402
import publish  # noqa: E402

TITLE_DAY, TITLE = "2026-11-20", "Basket review"
KEY_TITLE = "2026-11-20 — Basket review"
CONFIG = {"kind": "jira"}
OWNER_PICTURE = {"type": "mediaSingle", "attrs": {"layout": "center"},
                 "content": [{"type": "media", "attrs": {"id": "owner-media-1", "type": "file", "collection": "c"}}]}


def paragraph(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def doc(*nodes):
    return {"type": "doc", "version": 1, "content": list(nodes)}


def expect(actual, expected, about):
    """One assertion whose failure names the input, the expected value and the actual value."""
    assert actual == expected, f"{about}: expected {expected!r}, got {actual!r}"


class LocalJira(BaseHTTPRequestHandler):
    """Issues with descriptions and comments; `writes` logs each POST and PUT."""
    issues, writes, counter = {}, [], [100]

    def log_message(self, *args):
        pass

    def _send(self, code, body=None):
        data = b"" if body is None else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")

    def _parts(self):
        return self.path.split("?")[0].strip("/").split("/")

    def do_GET(self):
        parts = self._parts()
        if parts[-1] == "myself":
            return self._send(200, {"accountId": "me"})
        key = parts[4]
        issue = self.issues.get(key)
        if issue is None:
            return self._send(404, {"errorMessages": ["no issue"]})
        if parts[-1] == "comment":
            found = issue["comments"]
            return self._send(200, {"startAt": 0, "maxResults": 100, "total": len(found), "comments": found})
        return self._send(200, {"key": key, "id": key.rsplit("-", 1)[1],
                                "fields": {"summary": key, "description": issue["description"], "attachment": []}})

    def do_POST(self):
        parts, body = self._parts(), self._body()
        type(self).counter[0] += 1
        comment = {"id": str(self.counter[0]), "author": {"accountId": "me"}, "body": body["body"]}
        self.issues[parts[4]]["comments"].append(comment)
        self.writes.append(f"POST {parts[4]}")
        self._send(201, comment)

    def do_PUT(self):
        parts, body = self._parts(), self._body()
        issue = self.issues[parts[4]]
        if parts[-2] == "comment":
            comment = next(item for item in issue["comments"] if item["id"] == parts[-1])
            comment["body"] = body["body"]
            self.writes.append(f"PUT {parts[4]} comment {parts[-1]}")
            return self._send(200, comment)
        issue["description"] = body["fields"]["description"]
        self.writes.append(f"PUT {parts[4]} description")
        self._send(204)


@pytest.fixture
def jira(monkeypatch, tmp_path):
    pytest.importorskip("markdown_it")
    LocalJira.issues = {key: {"description": doc(paragraph(f"Text of the owner for {key}.")), "comments": []}
                        for key in ("PROJ-1", "PROJ-2", "PROJ-3", "PROJ-4")}
    LocalJira.issues["PROJ-1"]["description"] = doc(paragraph("The basket shows the total."), OWNER_PICTURE,
                                                    paragraph("The total holds no tax."))
    LocalJira.writes, LocalJira.counter[0] = [], 100
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalJira)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for name, value in (("JIRA_BASE_URL", f"http://127.0.0.1:{server.server_address[1]}"),
                        ("JIRA_EMAIL", "test@example.invalid"), ("JIRA_API_TOKEN", "not-a-token"),
                        ("NO_PROXY", "127.0.0.1"), ("no_proxy", "127.0.0.1")):
        monkeypatch.setenv(name, value)
    from tracker import cli, envelope, settings
    monkeypatch.setattr(settings, "read_config", lambda: {"tracker": {"kind": "jira"}})

    def tracker(verb, payload):
        try:
            return cli.VERBS[verb](payload)
        except envelope.Refusal as refusal:
            raise publish.Refusal(refusal.code, refusal.reason) from None

    yield tracker, tmp_path
    server.shutdown()
    server.server_close()


SUMMARIES = {
    "PROJ-1": "The team settled the basket total.\n\n# Summary\n\n## 1. Decisions / Confirmations\n"
              "- The basket total includes tax. Shared with PROJ-2.\n\n## 2. Open questions / Action items\n"
              "- **[unassigned]** Check the rounding.\n\n## 3. Meeting notes\n- See PROJ-3 for the coupon field.\n",
    "PROJ-2": "The team settled the total that the receipt prints.\n\n# Summary\n\n## 1. Decisions / Confirmations\n"
              "- The receipt prints the total with tax, as PROJ-1 shows it.\n",
    "PROJ-3": "The coupon field came up once.\n\n# Summary\n\n## 1. Decisions / Confirmations\n"
              "- The coupon field is out of this release (key decision, said once).\n",
}
TICKET = ("{{keep 0-1}}\n\n## Requirements\n\n- The basket total includes tax.\n- The receipt shows the same total "
          "as PROJ-2.\n")


def _signed_page(path, round_input):
    """The page document as ingest leaves it after the developer's sign on `i-publish`."""
    items = json.loads(Path(round_input).read_text("utf-8"))["items"]
    sign = copy.deepcopy(items[-1])
    sign.update(state="settled_by_mark", settled={"by": "mark", "round": 1, "signal": "sign"})
    path.write_text(json.dumps({"rounds": [{"n": 1, "items": [*items[:-1], sign]}]}), "utf-8")
    return path


def _meeting(tracker, root):
    run_dir = Path(meetings.start(TITLE_DAY, TITLE, root / "data")["run_dir"])
    for key, text in SUMMARIES.items():
        (run_dir / key).mkdir()
        (run_dir / key / "summary.md").write_text(text, "utf-8")
    outlined = publish.outline("PROJ-1", run_dir / "PROJ-1" / "description", tracker)
    (run_dir / "PROJ-1" / "TICKET.md").write_text(TICKET, "utf-8")
    return run_dir, outlined


def _preview_and_post(tracker, run_dir, root, name):
    answer = meetings.preview(run_dir, tracker, CONFIG)
    page = _signed_page(root / f"{name}.json", answer["round_input"])
    return answer, meetings.post(run_dir, answer["receipt"], page, root / "published.txt", tracker, CONFIG)


def _expand(comment):
    nodes = [node for node in comment["body"]["content"] if node.get("type") == "expand"]
    return nodes[0] if len(nodes) == 1 else None


def _walk(nodes):
    for node in nodes:
        yield node
        yield from _walk(node.get("content") or [])


def _text(nodes):
    """The words of the nodes, 1 text node per line."""
    return "\n".join(node["text"] for node in _walk(nodes) if node.get("type") == "text")


def test_one_meeting_reaches_each_ticket_once_and_a_rerun_edits_in_place(jira):
    tracker, root = jira
    run_dir, outlined = _meeting(tracker, root)
    expect(Path(outlined["meetings"]).read_text("utf-8"), "No meeting comment on this ticket.\n",
           "meetings.md of PROJ-1 before the first post")

    answer, done = _preview_and_post(tracker, run_dir, root, "first")
    expect([(item["key"], item["comment"], item["description"]) for item in done["tickets"]],
           [("PROJ-1", "posted", "published"), ("PROJ-2", "posted", None), ("PROJ-3", "posted", None)],
           "first post per ticket (key, comment, description)")
    expect(done["failed"], [], "failed tickets of the first post")
    expect(LocalJira.writes, ["PUT PROJ-1 description", "POST PROJ-1", "POST PROJ-2", "POST PROJ-3"],
           "writes of the first post, in order")
    expect(LocalJira.issues["PROJ-4"]["comments"], [], "comments of PROJ-4, named only in passing")
    ids = {}
    for key in ("PROJ-1", "PROJ-2", "PROJ-3"):
        comments = LocalJira.issues[key]["comments"]
        expect(len(comments), 1, f"comments on {key}")
        section = _expand(comments[0])
        expect(section["attrs"]["title"], KEY_TITLE, f"title of the comment on {key}")
        ids[key] = comments[0]["id"]
    expect("coupon field is out of this release" in _text(_expand(LocalJira.issues["PROJ-3"]["comments"][0])["content"]),
           True, "the key decision in the comment of PROJ-3")
    expect("receipt prints the total with tax" in _text(_expand(LocalJira.issues["PROJ-2"]["comments"][0])["content"]),
           True, "the PROJ-2 wording in its own comment")

    content = LocalJira.issues["PROJ-1"]["description"]["content"]
    expect(content[1], OWNER_PICTURE, "the owner's picture node of PROJ-1, kept exact")
    words = _text(content)
    expect(("The basket total includes tax." in words, "The total holds no tax." in words, "Basket review" in words),
           (True, False, False), "PROJ-1 description (has the decision, has the old line, has a meeting section)")
    links = [mark["attrs"]["href"] for node in _walk(content) for mark in node.get("marks") or [] if mark["type"] == "link"]
    expect([bool(re.fullmatch(r"http://127\.0\.0\.1:\d+/browse/PROJ-2", href)) for href in links], [True],
           f"links in the PROJ-1 description {links}")

    LocalJira.writes.clear()
    publish.outline("PROJ-1", run_dir / "PROJ-1" / "description", tracker)
    _, again = _preview_and_post(tracker, run_dir, root, "again")
    expect([(item["comment"], item["description"]) for item in again["tickets"]],
           [("unchanged", "unchanged"), ("unchanged", None), ("unchanged", None)], "re-run per ticket")
    expect(LocalJira.writes, [], "writes of the re-run")
    meetings_md = run_dir / "PROJ-1" / "description" / "meetings.md"
    expect(("## " + KEY_TITLE) in meetings_md.read_text("utf-8").splitlines(), True,
           "the outline lists the posted meeting for the next description")

    (run_dir / "PROJ-2" / "summary.md").write_text(SUMMARIES["PROJ-2"] + "\n## 3. Meeting notes\n- Rounding: unassigned.\n",
                                                   "utf-8")
    _, edited = _preview_and_post(tracker, run_dir, root, "edited")
    expect([item["comment"] for item in edited["tickets"]], ["unchanged", "edited", "unchanged"], "edit run per ticket")
    expect(LocalJira.writes, [f"PUT PROJ-2 comment {ids['PROJ-2']}"], "writes of the edit run")
    expect([item["id"] for item in LocalJira.issues["PROJ-2"]["comments"]], [ids["PROJ-2"]], "comment ids on PROJ-2")


def test_no_sign_writes_nothing(jira):
    tracker, root = jira
    run_dir, _ = _meeting(tracker, root)
    answer = meetings.preview(run_dir, tracker, CONFIG)
    page = root / "page.json"
    page.write_text(json.dumps({"rounds": [{"n": 1, "items": [{**item, "state": "open"} for item in json.loads(Path(answer["round_input"]).read_text("utf-8"))["items"]]}]}),
                    "utf-8")
    with pytest.raises(publish.Refusal) as refused:
        meetings.post(run_dir, answer["receipt"], page, root / "published.txt", tracker, CONFIG)
    expect((refused.value.code, LocalJira.writes), ("no-sign", []), "post with no sign (code, writes)")


def test_a_summary_changed_after_the_sign_writes_nothing(jira):
    tracker, root = jira
    run_dir, _ = _meeting(tracker, root)
    answer = meetings.preview(run_dir, tracker, CONFIG)
    page = _signed_page(root / "page.json", answer["round_input"])
    (run_dir / "PROJ-3" / "summary.md").write_text(SUMMARIES["PROJ-3"] + "- An added line.\n", "utf-8")
    with pytest.raises(publish.Refusal) as refused:
        meetings.post(run_dir, answer["receipt"], page, root / "published.txt", tracker, CONFIG)
    expect((refused.value.code, LocalJira.writes), ("bad-receipt", []), "post after a summary edit (code, writes)")


def test_a_stale_description_posts_no_comment_for_that_ticket(jira):
    tracker, root = jira
    run_dir, _ = _meeting(tracker, root)
    answer = meetings.preview(run_dir, tracker, CONFIG)
    page = _signed_page(root / "page.json", answer["round_input"])
    LocalJira.issues["PROJ-1"]["description"]["content"].append(paragraph("An owner edit."))
    done = meetings.post(run_dir, answer["receipt"], page, root / "published.txt", tracker, CONFIG)
    expect(done["failed"], ["PROJ-1"], "failed tickets")
    expect(done["tickets"][0]["error"]["code"], "stale", "refusal of PROJ-1")
    expect(LocalJira.issues["PROJ-1"]["comments"], [], "comments on PROJ-1")
    expect(LocalJira.writes, ["POST PROJ-2", "POST PROJ-3"], "writes")


def test_the_preview_round_builds_as_a_page(jira):
    tracker, root = jira
    run_dir, _ = _meeting(tracker, root)
    answer = meetings.preview(run_dir, tracker, CONFIG)
    target = root / "pages" / "use-lavish-s-20260101-000000.json"
    target.parent.mkdir()
    run = subprocess.run([sys.executable, str(SKILLS / "use-lavish" / "scripts" / "round_document.py"), "build",
                          "--doc", str(target), "--session", "s-20260101-000000",
                          "--round-input", answer["round_input"], "--private"],
                         cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=120, env={**os.environ})
    expect(run.returncode, 0, f"build of the round\n{run.stdout}\n{run.stderr}")
    items = json.loads(run.stdout)["items"]
    expect(items, ["i-proj-1", "i-proj-2", "i-proj-3", "i-publish"], "cards of the round")


def test_the_meeting_key_is_the_date_and_the_title():
    expect(meetings.meeting_key("2026-11-20", "  Basket   review "), KEY_TITLE, "meeting key")
    with pytest.raises(publish.Refusal):
        meetings.meeting_key("20-11-2026", "Basket review")
