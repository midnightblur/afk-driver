"""The one answer both ports print: one JSON object, exit 0, 1 or 2."""

from __future__ import annotations

import json
import sys

EXIT_OK, EXIT_REFUSED, EXIT_UNREADABLE = 0, 1, 2
UNREADABLE_CODES = {"bad-payload", "unknown-verb"}
HTTP_CODES = {400: "bad-request", 401: "auth", 403: "forbidden", 404: "not-found",
              409: "conflict", 413: "too-large", 422: "unprocessable", 429: "rate-limited"}


class Refusal(Exception):
    """A named refusal. `serve` turns it into the failure answer."""

    def __init__(self, code, reason, **extra):
        super().__init__(reason)
        self.code, self.reason, self.extra = code, reason, extra


def ok(**fields):
    return {"ok": True, **fields}


def fail(code, reason, **extra):
    return {"ok": False, "error": {"code": code, "reason": reason, **extra}}


def code_for_status(status):
    if status in HTTP_CODES:
        return HTTP_CODES[status]
    return "server-error" if 500 <= status <= 599 else "http-error"


def exit_code(answer):
    if answer.get("ok"):
        return EXIT_OK
    return EXIT_UNREADABLE if answer["error"]["code"] in UNREADABLE_CODES else EXIT_REFUSED


def read_payload(args, stream):
    """The payload from the first argument, else from the stream as UTF-8."""
    if args:
        text = args[0]
    elif stream.isatty():
        text = ""
    else:
        raw = getattr(stream, "buffer", None)
        try:
            text = raw.read().decode("utf-8") if raw is not None else stream.read()
        except UnicodeDecodeError as error:
            raise Refusal("bad-payload", f"the payload is not UTF-8: {error}") from None
    if not text.strip():
        return {}
    try:
        value = json.loads(text)
    except ValueError as error:
        raise Refusal("bad-payload", f"the payload is not JSON: {error}") from None
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise Refusal("bad-payload", "the payload must be one JSON object")
    return value


def need(payload, key):
    value = payload.get(key)
    if value is None or value == "":
        raise Refusal("bad-payload", f"the payload needs `{key}`")
    return value


def _answer(verbs, argv, stdin):
    if not argv or argv[0] not in verbs:
        named = argv[0] if argv else "(none)"
        return fail("unknown-verb", f"no verb {named}; verbs: {', '.join(sorted(verbs))}")
    try:
        return verbs[argv[0]](read_payload(argv[1:], stdin))
    except Refusal as refusal:
        return fail(refusal.code, refusal.reason, **refusal.extra)
    except Exception as error:
        return fail("internal", f"{type(error).__name__}: {error}")


def serve(verbs, argv, stdin=None):
    answer = _answer(verbs, argv, sys.stdin if stdin is None else stdin)
    print(json.dumps(answer))
    return exit_code(answer)
