"""tracker/none — the repository named no tracker.

Every operation answers `{"unsupported": true}` with the reason. The tracker MCP
server still registers all ten tools, so a skill gets one clear refusal instead
of a missing tool, and writes the same payload through the `notes` adapter.
`tracker_attach` also names each file it could not attach.
"""
from __future__ import annotations

import json
import sys

OPERATIONS = (
    "tracker_get", "tracker_search", "tracker_create", "tracker_edit",
    "tracker_comment", "tracker_transition", "tracker_transitions",
    "tracker_attachments", "tracker_changelog", "tracker_attach",
)

REASON = "tracker: none — set tracker: jira|github-issues in .afk/config.yaml"


def call(operation: str, payload: dict | None = None) -> dict:
    """The one entry point every tracker adapter exposes."""
    answer = {"unsupported": True, "operation": operation, "reason": REASON}
    files = (payload or {}).get("files") if operation == "tracker_attach" else None
    if isinstance(files, list):
        answer["unsupported_files"] = [{"file": str(f), "reason": REASON} for f in files]
    return answer


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--list-tools":
        for name in OPERATIONS:
            print(name)
        return 0
    if not argv:
        print(json.dumps({"operations": list(OPERATIONS), "reason": REASON}))
        return 0
    payload = json.loads(argv[1]) if len(argv) > 1 else {}
    print(json.dumps(call(argv[0], payload)))
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
