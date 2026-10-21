"""The transport family contract, version 1: six verbs, one JSON object in, one JSON object out.

A kind's entry is called as `<entry> <verb> '<json object>'` and never reads standard input. `run` maps the
verb to the kind's method, enforces the verb's time budget and prints the answer in the house shapes of
ADAPTERS.md: exit 0 the normalized object, 3 unsupported, 4 unavailable, 2 a bad payload or field. Any other
failure inside a verb answers exit 4 unavailable naming the verb and the error.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from typing import Any, Mapping

VERBS = ("agent-start", "agent-send", "agent-status", "agent-read", "agent-stop", "agent-list")
BUDGET_MS = {"agent-start": 120000, "agent-send": 30000, "agent-status": 10000,
             "agent-read": 30000, "agent-stop": 60000, "agent-list": 10000}
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class Answer(Exception):
    """A verb's final answer, raised from anywhere below the verb."""

    def __init__(self, code: int, body: dict):
        super().__init__(body.get("reason", ""))
        self.code = code
        self.body = body


def unsupported(reason: str) -> Answer:
    return Answer(3, {"unsupported": True, "reason": reason})


def unavailable(reason: str, **fields: Any) -> Answer:
    return Answer(4, {"unavailable": True, "reason": reason, **fields})


def bad(verb: str, reason: str) -> Answer:
    return Answer(2, {"error": True, "operation": verb, "reason": reason})


def now() -> str:
    return datetime.now(timezone.utc).strftime(TIME_FORMAT)


class Deadline:
    """The verb's time budget, counted from the call's start."""

    def __init__(self, verb: str, clock=time.monotonic):
        self.verb = verb
        self._clock = clock
        self._end = clock() + BUDGET_MS[verb] / 1000.0

    def left(self) -> float:
        return max(0.0, self._end - self._clock())

    def expired(self) -> bool:
        return self.left() <= 0.0


class Payload:
    """Typed reads of one verb's input; every bad field raises exit 2 naming the field."""

    def __init__(self, verb: str, data: Mapping):
        self.verb = verb
        self.data = data

    def text(self, key: str, required: bool = True) -> str | None:
        value = self.data.get(key)
        if value is None or value == "":
            if required:
                raise bad(self.verb, f"field `{key}` is required")
            return None
        if not isinstance(value, str):
            raise bad(self.verb, f"field `{key}` must be text")
        return value

    def integer(self, key: str, required: bool = True) -> int | None:
        value = self.data.get(key)
        if value is None:
            if required:
                raise bad(self.verb, f"field `{key}` is required")
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise bad(self.verb, f"field `{key}` must be a positive whole number")
        return value

    def boolean(self, key: str) -> bool:
        value = self.data.get(key, False)
        if not isinstance(value, bool):
            raise bad(self.verb, f"field `{key}` must be true or false")
        return value

    def texts(self, key: str) -> list[str]:
        value = self.data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise bad(self.verb, f"field `{key}` must be a list of text")
        return list(value)

    def mapping(self, key: str) -> dict[str, str]:
        value = self.data.get(key, {})
        if not isinstance(value, dict) or not all(
                isinstance(k, str) and k and isinstance(v, str) for k, v in value.items()):
            raise bad(self.verb, f"field `{key}` must map names to text")
        return dict(value)

    def choice(self, key: str, allowed: tuple[str, ...]) -> str:
        value = self.text(key)
        if value not in allowed:
            raise bad(self.verb, f"field `{key}`: {value!r} is not one of {', '.join(allowed)}")
        return value


def parse(argv: list[str]) -> tuple[str, Payload]:
    if not argv:
        raise bad("", "no verb given; the input is the verb, then one JSON object")
    verb = argv[0]
    if verb not in VERBS:
        raise unsupported(f"`{verb}` is not a transport verb; the verbs are {', '.join(VERBS)}")
    if len(argv) != 2:
        raise bad(verb, "the input is the verb, then one JSON object as the next argument")
    try:
        data = json.loads(argv[1])
    except ValueError as problem:
        raise bad(verb, f"the payload is not JSON: {problem}") from None
    if not isinstance(data, dict):
        raise bad(verb, "the payload is not one JSON object")
    return verb, Payload(verb, data)


def run(kind: object, argv: list[str], out=None) -> int:
    """Answer one call: the kind object has one method per verb, `agent_start(payload, deadline)` and so on."""
    out = out or sys.stdout
    verb = argv[0] if argv else ""
    try:
        verb, payload = parse(argv)
        deadline = Deadline(verb)
        code, body = 0, getattr(kind, verb.replace("-", "_"))(payload, deadline)
    except Answer as answer:
        code, body = answer.code, answer.body
    except Exception as error:      # any other failure still answers in a house shape, never a traceback
        code, body = 4, {"unavailable": True, "operation": verb,
                         "reason": f"{verb} failed: {type(error).__name__}: {error}"}
    out.write(json.dumps(body, sort_keys=True) + "\n")
    return code
