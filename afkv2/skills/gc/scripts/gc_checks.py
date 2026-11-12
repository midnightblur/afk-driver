"""The refusal checks of gc. Each check answers `refusal` (None, or the code, the reason and the detail the developer sees) and its data."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
FORGE = PLUGIN / "ports" / "forge" / "forge_cli.py"
sys.path.insert(0, str(PLUGIN / "ports"))

from tracker.envelope import Refusal  # noqa: E402

sys.path.insert(0, str(PLUGIN / "skills" / "autopilot" / "scripts"))
from end_gate import GATE_FOLDER, RECORD_FILE  # noqa: E402
from start_gate import RUN_SUFFIX  # noqa: E402

sys.path.insert(0, str(PLUGIN / "skills" / "create-change-request" / "scripts"))
import ci_watch  # noqa: E402

FORGE_LIMIT = 120
PASSED_ON = ("forge", "repo")
HEX40 = re.compile(r"[0-9a-f]{40}")
GIT_LIMIT = 60
IGNORED_SHOWN = 5
RECORD = f"plan/{GATE_FOLDER}/{RECORD_FILE}"  # the gate record, in the plan folder at the root of the run branch


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


def _local_tip(repo, branch):
    done = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}"], cwd=repo,
                          capture_output=True, stdin=subprocess.DEVNULL, timeout=GIT_LIMIT)
    return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else ""


def _remote_tip(repo, remote, branch):
    """The tip on the remote itself, not the remote-tracking ref, which can be stale."""
    ref = f"refs/heads/{branch}"
    lines = _git(repo, "ls-remote", remote, ref).splitlines()
    return next((line.split("\t")[0] for line in lines if line.split("\t")[-1] == ref), "")


def _outside(repo, remote, branch, tip, head):
    """Each commit of `tip` that `head` lacks, newest first. A remote tip this clone never fetched is fetched first."""
    known = subprocess.run(["git", "cat-file", "-e", f"{tip}^{{commit}}"], cwd=repo, capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=GIT_LIMIT)
    if known.returncode != 0:
        _git(repo, "fetch", "--quiet", "--no-tags", remote, f"refs/heads/{branch}")
    lines = _git(repo, "log", "--format=%h%x09%s", f"{head}..{tip}", "--").splitlines()
    return [{"id": line.partition("\t")[0], "title": line.partition("\t")[2]} for line in lines if line]


def _commits_text(commits):
    if commits is None:
        return "unchecked, no merged change gives a head commit"
    return ", ".join(f"{commit['id']} {commit['title']}" for commit in commits)


def check_tips(repo, feature_branch, head, remote="origin"):
    """Every branch tip of the work; an empty tip is an absent branch. A feature branch tip, local or remote, that is
    not `head` or older refuses `outside-commits` with each commit's short id and title. The run branch is an orphan
    by design: its tips are given, never compared. No `head` leaves each feature tip unchecked, which refuses."""
    run_branch = feature_branch + RUN_SUFFIX
    tips = {"feature branch": _local_tip(repo, feature_branch),
            "remote feature branch": _remote_tip(repo, remote, feature_branch),
            "run branch": _local_tip(repo, run_branch),
            "remote run branch": _remote_tip(repo, remote, run_branch)}
    result = {"refusal": None, "run_branch": run_branch, "tips": tips,
              "absent": [item for item, commit in tips.items() if not commit]}
    branches = []
    for item in ("feature branch", "remote feature branch"):
        if not tips[item]:
            continue
        commits = _outside(repo, remote, feature_branch, tips[item], head) if head else None
        if commits != []:
            branches.append({"item": item, "branch": feature_branch, "tip": tips[item], "commits": commits})
    if branches:
        shown = "; ".join(f"{branch['item']}: " + _commits_text(branch["commits"]) for branch in branches)
        result["refusal"] = {"code": "outside-commits", "reason": f"commits outside the change: {shown}", "branches": branches}
    return result


def check_platform(system=None):
    """gc removes a worktree folder on Windows only: another system refuses `not-windows`. `system` is an `os.name`."""
    system = os.name if system is None else system
    if system == "nt":
        return {"refusal": None, "system": system}
    return {"refusal": {"code": "not-windows", "reason": f"afkv2 runs on Windows only; this system is {system}, "
                                                         "so no worktree folder is removed"},
            "system": system}


def _record_bytes(repo, run_worktree, run_branch):
    """The gate record of the run: the file in the run worktree, else the committed file on the run branch; None
    when the run has none."""
    path = Path(run_worktree) / RECORD
    if path.is_file():
        return path.read_bytes()
    if not _local_tip(repo, run_branch):
        return None
    ref = f"refs/heads/{run_branch}"
    if not _git(repo, "ls-tree", "--name-only", ref, "--", RECORD).strip():
        return None
    return _git(repo, "show", f"{ref}:{RECORD}").encode("utf-8")


def check_proof_posted(repo, run_worktree, run_branch):
    """A run branch with a gate record keeps its proof until mark-ready posted the proof comment of that exact
    record; else it refuses `proof-not-posted` (SDD §6 I-12). A run with no gate record, an old plan, is not checked."""
    try:
        record = _record_bytes(repo, run_worktree, run_branch)
    except Refusal as failed:
        return {"refusal": {"code": "proof-not-posted", "reason": f"the gate record of {run_branch} cannot be read, so "
                                                                  f"its proof comment is unchecked: {failed.reason}"},
                "checked": True}
    result = {"refusal": None, "checked": record is not None}
    if record is not None and not ci_watch.proof_posted(repo, record):
        result["refusal"] = {"code": "proof-not-posted",
                             "reason": f"the run branch {run_branch} holds a gate record ({RECORD}) whose proof comment "
                                       "is not posted: run the Ship section of /afkv2:create-change-request first, or the "
                                       "proof goes with the run branch"}
    return result
