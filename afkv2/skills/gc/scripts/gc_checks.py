"""The refusal checks of gc. Each check answers `refusal` (None, or the code, the reason and the detail the developer sees) and its data."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
FORGE = PLUGIN / "ports" / "forge" / "forge_cli.py"
sys.path.insert(0, str(PLUGIN / "ports"))

from tracker.envelope import Refusal  # noqa: E402

FORGE_LIMIT = 120
PASSED_ON = ("forge", "repo")
HEX40 = re.compile(r"[0-9a-f]{40}")
GIT_LIMIT = 60
IGNORED_SHOWN = 5


def call_forge(verb, payload, cwd):
    """One call of the forge port in `cwd`. Every failure comes back as the port's failure answer."""
    try:
        done = subprocess.run([sys.executable, str(FORGE), verb], input=json.dumps(payload).encode("utf-8"),
                              capture_output=True, cwd=cwd, timeout=FORGE_LIMIT)
        answer = json.loads(done.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": {"code": "command-failed", "reason": f"forge {verb} gave no answer: {error}"}}
    if not isinstance(answer, dict) or "ok" not in answer:
        return {"ok": False, "error": {"code": "command-failed", "reason": f"forge {verb} gave no answer object"}}
    return answer


def _change(item):
    return {"number": int(item["id"]), "url": item.get("url") or "", "state": item.get("state") or "",
            "head_sha": item.get("head_sha") or "", "target": item.get("target") or ""}


def _forge_failed(error):
    return {"refusal": {"code": "forge-failed", "reason": f"the forge call failed: {error.get('code')}: {error.get('reason')}",
                        "error": error},
            "change": None}


def _changes(answer):
    """The changes of an ok answer, or the bad-answer error that stops the check."""
    items = answer.get("changes")
    if not isinstance(items, list) or not all(isinstance(item, dict) and str(item.get("id", "")).isdigit() for item in items):
        return None, {"code": "bad-answer", "reason": "the change list holds no list of numbered changes"}
    changes = [_change(item) for item in items]
    headless = [str(item["number"]) for item in changes
                if item["state"] == "merged" and not HEX40.fullmatch(item["head_sha"])]
    if headless:
        return None, {"code": "bad-answer", "reason": f"merged change {', '.join(headless)} has no 40-hex head commit"}
    return changes, None


def check_change(repo, branch, **passed):
    """Merged and none open: at least one change of `branch` is merged and every other is merged or closed.
    `change` is the newest merged change (its head commit serves every tip check), or None. A state the forge
    port does not name counts as not merged."""
    payload = {"branch": branch, **{key: value for key, value in passed.items() if key in PASSED_ON and value}}
    answer = call_forge("change-list", payload, repo)
    if not answer.get("ok"):
        return _forge_failed(answer.get("error") or {"code": "command-failed", "reason": "no error given"})
    changes, error = _changes(answer)
    if error:
        return _forge_failed(error)
    merged = [item for item in changes if item["state"] == "merged"]
    change = merged[0] if merged else None
    if merged and all(item["state"] in ("merged", "closed") for item in changes):
        return {"refusal": None, "change": change}
    shown = [{"number": item["number"], "state": item["state"], "url": item["url"]} for item in changes]
    states = ", ".join(f"{item['number']} {item['state'] or '(no state)'}" for item in changes) or "no change"
    return {"refusal": {"code": "not-merged", "reason": f"the forge does not say merged with none open: {states}",
                        "answer": shown, "link": changes[0]["url"] if changes else None},
            "change": change}


def _git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL, timeout=GIT_LIMIT)
    if done.returncode != 0:
        raise Refusal("git-failed", f"git {args[0]} in {cwd}: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout.decode("utf-8", "replace")


def _status(worktree):
    """(changed and untracked names, ignored names). `-z` keeps each name whole; a rename's second name is its old name."""
    entries = _git(worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=matching").split("\0")
    files, ignored, skip = [], [], False
    for entry in entries:
        if skip:
            skip = False
        elif entry:
            (ignored if entry.startswith("!!") else files).append(entry[3:])
            skip = entry[0] in "RC"
    return sorted(files), sorted(ignored)


def check_clean(worktree):
    """Each uncommitted or untracked file refuses `uncommitted` by its name. Ignored files are no refusal: their
    count and the first 5; an ignored folder counts as one, by its name with a trailing `/`. An absent worktree
    reads `absent`."""
    result = {"refusal": None, "worktree": str(worktree), "absent": not Path(worktree).exists(), "files": [],
              "ignored": {"count": 0, "first": []}}
    if result["absent"]:
        return result
    files, ignored = _status(worktree)
    result.update(files=files, ignored={"count": len(ignored), "first": ignored[:IGNORED_SHOWN]})
    if files:
        result["refusal"] = {"code": "uncommitted", "reason": f"{worktree} has uncommitted or untracked files: "
                                                              f"{', '.join(files)}", "files": files}
    return result
