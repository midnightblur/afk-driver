"""The side-question listener: the page's btw? panel posts one question here, never to the lavish queue.

The engine's `poll` and the Codex Stop hook run the listener while they wait for a round. It listens on
127.0.0.1 at the port of the page
document (`address`). The rendered page holds the port and a token; a request without that token is
refused, so no other page can type into the agent's terminal.

    POST /btw   body: JSON {"token", "question"}, sent as text/plain, so the browser sends no preflight
    answer:     JSON {"status", "answer"}: the result of `ask(question)` (`side_question.ask`)

Every answer carries `Access-Control-Allow-Origin: *`: lavish shows the page in a sandboxed frame, whose
origin is opaque (`null`). One question is asked at a time. A port that another process holds leaves the
wait with no listener; the page then says that no wait is running.
"""

from __future__ import annotations

import hashlib
import hmac
import http.server
import json
import os
import secrets
import threading
from pathlib import Path

from afkv2_config import Refusal, data_folder

HOST = "127.0.0.1"
PATH = "/btw"
PORT_BASE, PORT_SPAN = 43000, 4000
KEY_FILE = "btw-key"
MAX_BODY = 8192
NO_PANE = "Not answered: the agent does not run in a herdr pane. Ask it in the agent's chat."
WRONG_PAGE = "This page is not the page the wait shows. Reload the page, then ask again."


def _key() -> bytes:
    """The secret of this data folder, made once; every token derives from it."""
    path = data_folder() / KEY_FILE
    try:
        return path.read_bytes()
    except FileNotFoundError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "xb") as out:
            out.write(secrets.token_hex(32).encode("ascii"))
    except FileExistsError:
        pass
    return path.read_bytes()


def _name(document: str | os.PathLike) -> bytes:
    return os.path.normcase(str(Path(document).resolve())).encode("utf-8")


def address(document: str | os.PathLike) -> tuple[int, str]:
    """`(port, token)` of a page document: the same document always gives the same pair."""
    name = _name(document)
    port = PORT_BASE + int.from_bytes(hashlib.sha256(name).digest()[:4], "big") % PORT_SPAN
    return port, hmac.new(_key(), name, hashlib.sha256).hexdigest()[:32]


class _Server(http.server.ThreadingHTTPServer):
    allow_reuse_address = False  # on Windows, address reuse lets a second process bind the same port
    daemon_threads = True


def _handler(token: str, ask, lock: threading.Lock):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:  # a hook's output must stay its JSON answer
            pass

        def _send(self, code: int, body: dict | None = None) -> None:
            data = json.dumps(body).encode("utf-8") if body is not None else b""
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "content-type")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            if body is not None:
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self) -> None:
            self._send(204)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if self.path != PATH or not 0 < length <= MAX_BODY:
                return self._send(400, {"status": "failed", "answer": "Not a side question."})
            try:
                request = json.loads(self.rfile.read(length).decode("utf-8"))
                sent, question = str(request["token"]), str(request["question"]).strip()
            except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                return self._send(400, {"status": "failed", "answer": "Not a side question."})
            if not hmac.compare_digest(sent, token):
                return self._send(403, {"status": "refused", "answer": WRONG_PAGE})
            if not question:
                return self._send(400, {"status": "failed", "answer": "The question is empty."})
            with lock:
                result = ask(question)
            if result["status"] == "unanswered":
                result = {**result, "answer": NO_PANE}
            self._send(200, {"status": result["status"], "answer": result["answer"]})

    return Handler


class Listener:
    """`with Listener(document, ask):` serves side questions for that page until the block ends."""

    def __init__(self, document: str | os.PathLike, ask):
        self.document, self.ask, self.server = document, ask, None

    def __enter__(self) -> "Listener":
        try:
            port, token = address(self.document)
            self.server = _Server((HOST, port), _handler(token, self.ask, threading.Lock()))
        except (OSError, Refusal):  # no data folder, or the port is taken: the page says no wait runs
            return self
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
