"""The input of comment-put, the same on every tracker: the receipt on the first line, the picture files."""

from __future__ import annotations

import re
from pathlib import Path

from .envelope import Refusal, need

FIRST_LINE = "afkv2 proof v1 "
_RECEIPT = re.compile(r"[0-9a-f]{64}")


def first_line(text):
    return str(text or "").split("\n", 1)[0].strip()


def holds_receipt(text, receipt):
    return first_line(text) == FIRST_LINE + receipt


def request(payload):
    """(key, body, pictures as paths, receipt). Checks only what needs no tracker call."""
    receipt = payload.get("receipt")
    if not isinstance(receipt, str) or not _RECEIPT.fullmatch(receipt):
        raise Refusal("bad-receipt", "the payload needs `receipt`, 64 lowercase hex characters")
    key, body = need(payload, "key"), need(payload, "body")
    if not isinstance(body, str) or not holds_receipt(body, receipt):
        raise Refusal("bad-receipt", f"the first line of `body` must be `{FIRST_LINE}<receipt>` with this receipt")
    pictures = payload.get("pictures") or []
    if not isinstance(pictures, list) or not all(isinstance(item, str) and item for item in pictures):
        raise Refusal("bad-payload", "`pictures` must be a list of file paths")
    paths = [Path(item) for item in pictures]
    for path in paths:
        if not path.is_file():
            raise Refusal("bad-payload", f"no picture file at {path}")
    return key, body, paths, receipt


def check_sizes(paths, limit, tracker):
    for path in paths:
        size = path.stat().st_size
        if size > limit:
            raise Refusal("too-large", f"{path.name} is {size} bytes; {tracker} takes at most {limit} bytes per file")
