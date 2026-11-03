"""The side-question listener: the page's btw? panel posts only its question to the wait, never to lavish.

Each test runs a real listener on 127.0.0.1; `ask` is an in-process fake, so no herdr pane is touched.
"""

import json
import socket
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
for folder in (PLUGIN / "scripts", PLUGIN / "engine", PLUGIN / "hooks"):
    sys.path.insert(0, str(folder))

import btw_listener  # noqa: E402
import codex_stop  # noqa: E402
import engine  # noqa: E402
import launcher  # noqa: E402
import side_question  # noqa: E402
from shell import page  # noqa: E402

DOC = {"schema": "afkv2.page/0",
       "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                   "started": "2026-01-05T09:00:00Z"},
       "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                   "items": [{"id": "i-a", "kind": "confirm", "body": {"type": "text", "props": {"text": "A"}}}]}]}


@pytest.fixture
def data_home(tmp_path, monkeypatch):
    home = tmp_path / "local"
    home.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(home))
    monkeypatch.delenv("LAVISH_AXI_HOST", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    return home


def post(document, body, method="POST"):
    """`(HTTP status, JSON answer or None, headers)` of one request to the listener of `document`."""
    port, _ = btw_listener.address(document)
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(f"http://127.0.0.1:{port}/btw", data=data, method=method,
                                     headers={"Content-Type": "text/plain", "Origin": "null"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None, response.headers
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read()), error.headers


def asked(questions, status="answered"):
    def ask(question):
        questions.append(question)
        return {"question": question, "status": status, "answer": f"About {question}"}
    return ask


def test_a_document_has_one_port_and_one_token(data_home, tmp_path):
    first = btw_listener.address(tmp_path / "a.json")
    assert first == btw_listener.address(tmp_path / "a.json")
    assert btw_listener.PORT_BASE <= first[0] < btw_listener.PORT_BASE + btw_listener.PORT_SPAN
    assert first[1] != btw_listener.address(tmp_path / "b.json")[1] and len(first[1]) == 32
    key = (data_home / "afkv2" / btw_listener.KEY_FILE).read_bytes()
    btw_listener.address(tmp_path / "c.json")
    assert (data_home / "afkv2" / btw_listener.KEY_FILE).read_bytes() == key


def test_the_listener_asks_the_question_and_answers_the_page(data_home, tmp_path):
    document, questions = tmp_path / "a.json", []
    token = btw_listener.address(document)[1]
    with btw_listener.Listener(document, asked(questions)):
        code, answer, headers = post(document, {"token": token, "question": "  Which ticket?  "})
        assert post(document, None, "OPTIONS")[0] == 204
    assert (code, answer) == (200, {"status": "answered", "answer": "About Which ticket?"})
    assert headers["Access-Control-Allow-Origin"] == "*" and questions == ["Which ticket?"]


def test_a_request_without_the_page_token_asks_nothing(data_home, tmp_path):
    document, questions = tmp_path / "a.json", []
    with btw_listener.Listener(document, asked(questions)):
        assert post(document, {"token": "0" * 32, "question": "Leak it?"})[:2] == (
            403, {"status": "refused", "answer": btw_listener.WRONG_PAGE})
        assert post(document, {"question": "No token?"})[0] == 400
    assert questions == []


def test_with_no_herdr_pane_the_page_is_told_to_ask_in_the_chat(data_home, tmp_path):
    document = tmp_path / "a.json"
    with btw_listener.Listener(document, asked([], status="unanswered")):
        answer = post(document, {"token": btw_listener.address(document)[1], "question": "Why?"})[1]
    assert answer == {"status": "unanswered", "answer": btw_listener.NO_PANE}


def test_a_taken_port_leaves_the_wait_without_a_listener(data_home, tmp_path):
    document = tmp_path / "a.json"
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", btw_listener.address(document)[0]))
        taken.listen()
        with btw_listener.Listener(document, asked([])) as listener:
            assert listener.server is None


PORT_ATTR, TOKEN_ATTR = "data-afkv2-btw-port", "data-afkv2-btw-token"


class PageAttrs(HTMLParser):
    """The attributes of the page's root element, `div.afkv2-page`."""

    def __init__(self, html):
        super().__init__()
        self.attrs = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        found = dict(attrs)
        if self.attrs is None and found.get("class") == "afkv2-page":
            self.attrs = found


def test_the_page_holds_the_listener_address_and_the_script_never_uses_the_lavish_queue():
    attrs = PageAttrs(page.build(DOC, (43001, "abc"))).attrs
    assert (attrs[PORT_ATTR], attrs[TOKEN_ATTR]) == ("43001", "abc")
    assert set(PageAttrs(page.build(DOC)).attrs) == {"class"}
    script = (PLUGIN / "engine" / "shell" / "btw.js").read_text("utf-8")
    assert "queuePrompt" not in script and "sendQueuedPrompts" not in script
    needed = (f"'http://127.0.0.1:' + holder.getAttribute('{PORT_ATTR}')",
              "JSON.stringify({ token: token, question: text })", "'Content-Type': 'text/plain'", "No wait is running")
    assert all(part in script for part in needed)


@pytest.fixture
def shown(tmp_path, data_home):
    root = tmp_path / "repo"
    (root / ".afkv2").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "specs"}), "utf-8")
    pages = root / "specs" / "feature" / "pages"
    pages.mkdir(parents=True)
    path = pages / "grill-s1.json"
    path.write_text(json.dumps(DOC), "utf-8")
    assert engine.main(["render", str(path)]) == 0
    return path


def test_render_writes_the_listener_address_into_the_page(shown, capsys):
    port, token = btw_listener.address(shown)
    attrs = PageAttrs(shown.with_suffix(".html").read_text("utf-8")).attrs
    assert (attrs[PORT_ATTR], attrs[TOKEN_ATTR]) == (str(port), token)


def test_the_engine_poll_answers_a_side_question_while_the_host_waits(shown, capsys, monkeypatch):
    questions, seen = [], []
    monkeypatch.setattr(side_question, "ask", asked(questions))

    def poll_status(argv):
        seen.append(post(shown, {"token": btw_listener.address(shown)[1], "question": "Why?"})[1])
        return "feedback", {"raw": "i-a accept", "prompts": [{"prompt": "[round R-1]\ni-a accept"}],
                            "session_ended": False}

    monkeypatch.setattr(launcher, "poll_status", poll_status)
    capsys.readouterr()
    assert engine.main(["poll", str(shown)]) == 0
    answer = json.loads(capsys.readouterr().out)
    assert seen == [{"status": "answered", "answer": "About Why?"}] and questions == ["Why?"]
    assert answer["raw"] == "[round R-1]\ni-a accept" and answer["btw"] == []


def test_the_codex_stop_hook_answers_side_questions_while_it_waits(shown, data_home, monkeypatch):
    questions, seen = [], []
    monkeypatch.setattr(side_question, "ask", lambda question, harness=None: asked(questions)(question))
    launcher.write_waiting_record(data_home / "afkv2", "t-1", str(shown.resolve()), "p.html")

    def wait(page_path, document=None):
        seen.append(post(document, {"token": btw_listener.address(document)[1], "question": "And?"})[1])
        return "feedback", "[round R-1]\ni-a accept"

    monkeypatch.setattr(codex_stop, "wait_for_answer", wait)
    out = json.loads(codex_stop.main(json.dumps({"session_id": "t-1"})))
    assert out["decision"] == "block" and seen == [{"status": "answered", "answer": "About And?"}]
    assert questions == ["And?"]
