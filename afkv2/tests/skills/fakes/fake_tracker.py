"""Recorded fake of the tracker command (SDD §3), until the S3 port merges.

`cli.py <verb> [json-payload]`. FAKE_TICKETS is a JSON file: {"issues": {key: answer}, "search": [..]}.
FAKE_CALL_LOG gets one line `tracker <verb> <key or query>` per call. A write verb is logged and refused.
"""

import json
import os
import sys
from pathlib import Path


def answer(obj, code=0):
    print(json.dumps(obj))
    return code


def main(argv):
    verb = argv[0]
    payload = json.loads(argv[1]) if len(argv) > 1 else {}
    log = os.environ.get("FAKE_CALL_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as out:
            out.write(f"tracker {verb} {payload.get('key', payload.get('query', ''))}\n")
    if os.environ.get("FAKE_TRACKER_REFUSE") == verb:
        return answer({"ok": False, "error": {"code": "refused", "reason": f"{verb} refused by the fake"}}, 1)
    tickets = json.loads(Path(os.environ["FAKE_TICKETS"]).read_text("utf-8"))
    if verb == "issue-get":
        found = tickets["issues"].get(str(payload["key"]))
        if found is None:
            return answer({"ok": False, "error": {"code": "not-found", "reason": str(payload["key"])}}, 1)
        return answer({"ok": True, **found})
    if verb == "issue-search":
        return answer({"ok": True, "issues": tickets.get("search", []), "count": len(tickets.get("search", []))})
    return answer({"ok": False, "error": {"code": "unknown-verb", "reason": verb}}, 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
