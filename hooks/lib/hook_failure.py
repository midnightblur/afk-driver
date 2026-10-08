"""The one line a failed hook leaves, and where the harness shows it.

Shape: `[afk] <handler> (<event>) failed: <outcome>: <reason>`, where outcome is
`exit <n>` or a timeout, and reason is the handler's last stderr line or `no message`.
It always goes to stderr. A provider whose declaration sets `hook_failure_notice` to
`system_message` drops stderr on a failed exit, so the caller also carries the line in
a `systemMessage` at exit 0 (`notice()`). Contract: CAPABILITIES.md "Hook failures".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def last_line(said: bytes | str | None) -> str:
    text = said.decode("utf-8", "replace") if isinstance(said, bytes) else (said or "")
    lines = [part.strip() for part in text.replace("\r", "\n").split("\n") if part.strip()]
    return lines[-1] if lines else "no message"


def line(handler: str, event: str | None, outcome: str, said: bytes | str | None) -> str:
    return f"[afk] {handler} ({event or 'unknown event'}) failed: {outcome}: {last_line(said)}"


def system_message(facts: dict | None = None) -> bool:
    """True where the harness shows a failed hook only through `systemMessage` at exit 0."""
    if facts is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            import provider_facts
            facts = provider_facts.facts()
        except Exception:
            facts = {}
    return facts.get("hook_failure_notice") == "system_message"


def notice(lines: list[str]) -> str:
    return json.dumps({"systemMessage": "\n".join(lines)})


def crashed(handler: str, event: str, problem: BaseException, *, notify: bool) -> None:
    """A direct entry's caught exception: the line on stderr; with `notify`, also as the stdout document."""
    text = line(handler, event, "uncaught exception", f"{type(problem).__name__}: {problem}")
    sys.stderr.write(text + "\n")
    if notify and system_message():
        sys.stdout.write(notice([text]) + "\n")
