"""Live round-trip on a real pull request: `forge_round_trip.py <pull request number>`. Removes its own comments."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parents[3] / "ports" / "forge" / "cli.py"
MARKER = "afkv2 forge port round-trip, removed by the check"


def forge(verb, **payload):
    done = subprocess.run([sys.executable, str(CLI), verb, json.dumps(payload)], capture_output=True, timeout=180)
    answer = json.loads(done.stdout.decode("utf-8"))
    assert done.returncode == (0 if answer["ok"] else 1), done.stderr.decode("utf-8", "replace")
    return answer


def good(verb, **payload):
    answer = forge(verb, **payload)
    assert answer["ok"], answer
    print(f"ok {verb}")
    return answer


def first_added_line(diff):
    """A path and line the pull request adds: the place an inline comment can stand."""
    path, line = None, None
    for text in diff.splitlines():
        if text.startswith("+++ b/"):
            path = text[6:]
        elif text.startswith("@@"):
            line = int(re.search(r"\+(\d+)", text).group(1))
        elif path and line is not None and text.startswith("+") and not text.startswith("+++"):
            return path, line
        elif path and line is not None and not text.startswith("-"):
            line += 1
    raise AssertionError("the diff adds no line")


def remove(path):
    subprocess.run(["gh", "api", "-X", "DELETE", path], check=True, capture_output=True, timeout=60)


def main(change):
    assert good("auth-status")["authenticated"] is True
    view = good("change-view", id=change)
    assert view["id"] == change and view["draft"] is True and view["state"] == "opened" and view["head_sha"]
    repo = re.search(r"github\.com/([^/]+/[^/]+)/pull", view["url"]).group(1)

    diff = good("change-diff", id=change)
    assert diff["lines"] > 0
    path, line = first_added_line(diff["diff"])

    plain = good("change-comment", id=change, text=f"{MARKER} (plain)")
    inline = None
    try:
        assert plain["inline"] is False and plain["comment"]
        inline = good("change-comment", id=change, text=f"{MARKER} (inline)", file=path, line=line, require_inline=True)
        assert inline["inline"] is True and inline["thread"] == inline["comment"]

        notes = good("note-list", id=change)
        found = [note for note in notes["notes"] if note["id"] == plain["comment"]]
        assert found and MARKER in found[0]["body"] and found[0]["edited"] is False

        threads = good("thread-list", id=change)
        thread = [item for item in threads["threads"] if item["id"] == inline["thread"]]
        assert thread and thread[0]["line"] == line and thread[0]["new_path"] == path and thread[0]["side"] == "new"
    finally:
        remove(f"repos/{repo}/issues/comments/{plain['comment']}")
        if inline:
            remove(f"repos/{repo}/pulls/comments/{inline['comment']}")

    left = [note for note in good("note-list", id=change)["notes"] if MARKER in note["body"]]
    assert not left, left

    status = good("ci-status", id=change)
    assert status["status"] in ("", "success", "failed", "canceled", "running") and status["url"] == view["url"]
    waited = forge("ci-wait", id=change, budget=0)
    final = ("success", "failed", "canceled")
    assert waited["ok"] and waited["status"] == (status["status"] if status["status"] in final else "running")
    print(json.dumps({"change": change, "inline_path": path, "inline_line": line, "ci": status["status"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
