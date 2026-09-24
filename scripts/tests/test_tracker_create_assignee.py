"""The tracker create verb assigns the work item only when an assignee is set.

`/afk:bug` and `/afk:to-ticket` resolve `trackerAssignee` and pass it as the
create `assignee`. These tests pin the adapter half: a set assignee reaches the
tracker, an unset one changes nothing about the create. No network, no `gh`.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest import mock

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = PLUGIN_ROOT / "adapters" / "tracker"


def load(kind: str):
    spec = importlib.util.spec_from_file_location(
        f"afk_tracker_create_{kind.replace('-', '_')}", ADAPTERS / kind / "api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---- jira: a post-create assignable-search + PUT, only when set -------------

def _run_jira(payload):
    api = load("jira")
    calls = []

    def fake_json(method, path, body=None, params=None):
        calls.append({"method": method, "path": path, "body": body})
        if method == "POST" and path == "/rest/api/3/issue":
            return {"key": "PROJ-1", "id": "1"}
        if "assignable/search" in path:
            return [{"accountId": "acc-9"}]
        return {}

    with mock.patch.object(api, "_json", fake_json):
        result = api._op_create(payload)
    return result, calls


def test_jira_create_sets_the_assignee_when_present():
    result, calls = _run_jira(
        {"project": "PROJ", "issue_type": "Task", "summary": "s", "assignee": "dev@x.test"})
    assert any("assignable/search" in c["path"] for c in calls)
    puts = [c for c in calls if c["method"] == "PUT"]
    assert len(puts) == 1
    assert puts[0]["body"]["fields"]["assignee"] == {"accountId": "acc-9"}
    assert result["assignee"]["accountId"] == "acc-9"


def test_jira_create_omits_the_assignee_when_absent():
    result, calls = _run_jira({"project": "PROJ", "issue_type": "Task", "summary": "s"})
    # The one create POST, nothing else: no assignable search, no assignment PUT.
    assert [(c["method"], c["path"]) for c in calls] == [("POST", "/rest/api/3/issue")]
    assert "assignee" not in result


# ---- github-issues: `--assignee` on the `gh issue create` argv, only when set

def _run_github(payload):
    api = load("github-issues")
    captured = {}

    def fake_gh(*args, stdin=None):
        captured["args"] = list(args)
        return {"raw": "https://github.com/x/y/issues/5"}

    with mock.patch.object(api, "_gh", fake_gh), \
            mock.patch.object(api, "_repo_args", lambda: []), \
            mock.patch.object(api, "state_labels", lambda: {}):
        result = api._op_create(payload)
    return result, captured["args"]


def test_github_create_passes_the_assignee_when_present():
    result, args = _run_github(
        {"summary": "s", "issue_type": "Task", "assignee": "octocat"})
    assert "--assignee" in args and args[args.index("--assignee") + 1] == "octocat"
    assert result["key"] == "5"


def test_github_create_omits_the_assignee_when_absent():
    _result, args = _run_github({"summary": "s", "issue_type": "Task"})
    assert "--assignee" not in args


# ---- none: create is refused, assignee or not -------------------------------

def test_none_create_ignores_the_assignee():
    api = load("none")
    answer = api.call("tracker_create", {"summary": "s", "assignee": "dev"})
    assert answer["unsupported"] is True
