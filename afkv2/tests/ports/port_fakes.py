"""Plain helpers of the port tests, in a module with a name that no other test folder uses."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

PORTS = Path(__file__).resolve().parents[2] / "ports"


class FakeResp:
    def __init__(self, body=b"", location=None):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.headers = {"Location": location} if location is not None else {}

    def read(self):
        return self._body


def http_error(status, body=b"", location=None):
    headers = {"Location": location} if location else {}
    return urllib.error.HTTPError("https://n.test/x", status, "status", headers, io.BytesIO(body))
