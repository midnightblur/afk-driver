"""Running gh, glab and git: bytes in UTF-8, a time limit, one failure vocabulary."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import NamedTuple

from .envelope import HTTP_CODES, Refusal, code_for_status

DEFAULT_TIMEOUT = 60
_STATUS = re.compile(r"(?:HTTP |^|: )([45]\d{2})\b", re.MULTILINE)
_MISSING = re.compile(r"not found|no pull requests? found|no open merge requests?|could not resolve to an? ", re.IGNORECASE)
_AUTH = re.compile(r"auth login|not logged in|authentication|unauthorized|bad credentials", re.IGNORECASE)


class Done(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def _limit(timeout):
    if timeout is not None:
        return timeout
    try:
        return int(os.environ.get("AFKV2_FORGE_TIMEOUT") or DEFAULT_TIMEOUT)
    except ValueError:
        return DEFAULT_TIMEOUT


def run_tool(tool, args, *, stdin_text=None, timeout=None):
    """Run what `which` found: on Windows a bare name starts only an .exe, never a .cmd."""
    exe = shutil.which(tool)
    if not exe:
        raise Refusal("unavailable", f"the `{tool}` command is not on PATH")
    limit = _limit(timeout)
    feed = {"input": stdin_text.encode("utf-8")} if stdin_text is not None else {"stdin": subprocess.DEVNULL}
    try:
        done = subprocess.run([exe, *args], capture_output=True, timeout=limit, **feed)
    except subprocess.TimeoutExpired:
        raise Refusal("timeout", f"`{tool} {args[0] if args else ''}` ran past {limit} s") from None
    except OSError as error:
        raise Refusal("cli-failed", f"`{tool}` did not start: {error}") from None
    return Done(done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace"))


def cli_code(text):
    found = _STATUS.search(text)
    if found:
        return code_for_status(int(found.group(1)))
    if _MISSING.search(text):
        return HTTP_CODES[404]
    if _AUTH.search(text):
        return HTTP_CODES[401]
    return "cli-failed"


def failure(tool, done):
    text = (done.stderr or done.stdout).strip()[:2000]
    return Refusal(cli_code(text), text or f"`{tool}` exited {done.returncode} with no message")


def checked(tool, args, *, stdin_text=None):
    done = run_tool(tool, args, stdin_text=stdin_text)
    if done.returncode != 0:
        raise failure(tool, done)
    return done.stdout


def documents(text):
    decoder = json.JSONDecoder()
    index, out = 0, []
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return out
        value, index = decoder.raw_decode(text, index)
        out.append(value)


def pages(text):
    """One value from an answer that may arrive as one JSON document per page."""
    found = documents(text)
    if not found:
        raise ValueError("no JSON document in the answer")
    if len(found) == 1:
        return found[0]
    items = []
    for document in found:
        if isinstance(document, list):
            items.extend(document)
        else:
            items.append(document)
    return items


def as_items(value):
    return value if isinstance(value, list) else [value]


def json_answer(tool, args, *, stdin_text=None):
    text = checked(tool, args, stdin_text=stdin_text)
    try:
        return pages(text)
    except ValueError:
        raise Refusal("bad-answer", f"`{tool} {args[0]}` answered no readable JSON: {text[:300]}") from None
