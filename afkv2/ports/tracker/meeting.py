"""The meeting comment rules both trackers share: the dated title, the receipt, which write to make, the read-back."""

from __future__ import annotations

import hashlib
import re

from .envelope import Refusal, need

DATED = re.compile(r"^\d{4}-\d{2}-\d{2}\b")
_RECEIPT = re.compile(r"[0-9a-f]{64}")


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_dated(title):
    return isinstance(title, str) and bool(DATED.match(title)) and "\n" not in title and "\r" not in title


def request(payload):
    """(key, title, receipt, expect_hash). Checks only what needs no tracker call."""
    key, title = need(payload, "key"), need(payload, "title")
    if not is_dated(title):
        raise Refusal("bad-payload", "`title` must start with a date YYYY-MM-DD and hold no line break")
    if "expect_hash" not in payload:
        raise Refusal("bad-payload", "the payload needs `expect_hash`: the hash of the comment, or null for none")
    expect_hash = payload["expect_hash"]
    if expect_hash is not None and not isinstance(expect_hash, str):
        raise Refusal("bad-payload", "`expect_hash` must be a hash text or null")
    receipt = payload.get("receipt")
    if not isinstance(receipt, str) or not _RECEIPT.fullmatch(receipt):
        raise Refusal("bad-receipt", "the payload needs `receipt`, 64 lowercase hex characters")
    return str(key), title, receipt, expect_hash


def check_receipt(key, title, text, receipt):
    if sha256(key + title + text) != receipt:
        raise Refusal("bad-receipt", "this title and text are not what the receipt covers: show a new preview")


def choose(listed, title, new_hash, expect_hash):
    """`("post", None)`, `("unchanged", comment)` or `("edit", comment)`; a refusal when no write is safe."""
    same = [item for item in listed if item["title"] == title]
    if not same:
        if expect_hash is not None:
            raise Refusal("stale", f"no meeting comment `{title}` exists, and `expect_hash` names one: read again")
        return "post", None
    if len(same) > 1:
        ids = ", ".join(str(item["comment_id"]) for item in same)
        raise Refusal("duplicate-meeting", f"{len(same)} meeting comments have the title `{title}`: {ids}")
    found = same[0]
    if not found["own"]:
        raise Refusal("not-own", f"meeting comment {found['comment_id']} belongs to another account")
    if found["comment_hash"] == new_hash:
        return "unchanged", found
    if found["comment_hash"] != expect_hash:
        raise Refusal("stale", f"meeting comment {found['comment_id']} changed after it was read: read again")
    return "edit", found


def read_back(listed, title, new_hash):
    """The one meeting comment with the title and the new hash, else `read-back-mismatch`."""
    same = [item for item in listed if item["title"] == title]
    if len(same) != 1:
        raise Refusal("read-back-mismatch", f"after the write, {len(same)} meeting comments have the title `{title}`; "
                                            "expected 1")
    if same[0]["comment_hash"] != new_hash:
        raise Refusal("read-back-mismatch", f"after the write, meeting comment {same[0]['comment_id']} has the hash "
                                            f"{same[0]['comment_hash']}; expected {new_hash}")
    return same[0]
