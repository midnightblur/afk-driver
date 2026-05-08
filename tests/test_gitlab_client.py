"""Unit tests for gitlab_client. ``glab`` subprocess is faked; no network."""

from __future__ import annotations

import json
import subprocess
from typing import Callable

import pytest

from afk_driver.gitlab_client import (
    GitLabClient,
    GitLabError,
    MRInfo,
    SubtaskItem,
    _render_subtasks_block,
    splice_marker_block,
)
from afk_driver.section_splice import SectionMarkerMissing


def _proc(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["glab"], returncode=returncode, stdout=stdout, stderr=stderr)


def _mr_json(**overrides) -> str:
    base = {
        "iid": 25636,
        "web_url": "https://gitlab.com/foo/bar/-/merge_requests/25636",
        "state": "opened",
        "title": "[P2P-1220] AFK bootstrap",
        "description": "body",
        "source_branch": "mvu/afk/P2P-1220",
        "target_branch": "master",
    }
    base.update(overrides)
    return json.dumps(base)


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self._responses: list[tuple[Callable[[list[str]], bool], subprocess.CompletedProcess]] = []

    def add(self, predicate: Callable[[list[str]], bool], response: subprocess.CompletedProcess) -> None:
        self._responses.append((predicate, response))

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(args)
        for pred, resp in self._responses:
            if pred(args):
                return resp
        raise AssertionError(f"FakeRunner: no handler for {args}")


def test_find_mr_by_branch_returns_info():
    r = FakeRunner()
    r.add(lambda a: a[0] == "mr" and a[1] == "view", _proc(0, _mr_json()))
    c = GitLabClient(r)
    mr = c.find_mr_by_branch("mvu/afk/P2P-1220")
    assert mr is not None
    assert mr.iid == 25636
    assert mr.state == "opened"
    assert mr.target_branch == "master"


def test_find_mr_by_branch_returns_none_when_absent():
    r = FakeRunner()
    r.add(lambda a: a[0] == "mr", _proc(1, "", "no open merge request found for branch"))
    c = GitLabClient(r)
    assert c.find_mr_by_branch("mvu/afk/P2P-9999") is None


def test_find_open_mr_by_parent_key_returns_single_match():
    """User opened the parent's MR by hand against
    ``kapteyn/development/mvu/{slug}``; the runner discovers it via the
    parent key in title."""
    payload = json.dumps([
        {
            "iid": 7,
            "web_url": "https://gitlab.com/x/-/merge_requests/7",
            "state": "opened",
            "title": "[P2P-1229] Refactor payable",
            "description": "body",
            "source_branch": "kapteyn/development/mvu/payable-refactor",
            "target_branch": "master",
        }
    ])
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["mr", "list"], _proc(0, payload))
    c = GitLabClient(r)
    mr = c.find_open_mr_by_parent_key("P2P-1229")
    assert mr is not None
    assert mr.source_branch == "kapteyn/development/mvu/payable-refactor"
    # Verify the search flag was passed.
    call = next(a for a in r.calls if a[:2] == ["mr", "list"])
    assert "--search" in call and call[call.index("--search") + 1] == "P2P-1229"
    assert "-A" in call


def test_find_open_mr_by_parent_key_returns_none_when_no_match():
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["mr", "list"], _proc(0, "[]"))
    c = GitLabClient(r)
    assert c.find_open_mr_by_parent_key("P2P-9999") is None


def test_find_open_mr_by_parent_key_filters_to_opened_state():
    """A merged MR also matches the ``--search`` filter server-side; the
    client must drop non-opened states so a finished MR doesn't get
    revived as the AFK target branch."""
    payload = json.dumps([
        {
            "iid": 1, "web_url": "u", "state": "merged",
            "title": "[P2P-1229] old MR", "description": "",
            "source_branch": "old/branch", "target_branch": "master",
        }
    ])
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["mr", "list"], _proc(0, payload))
    c = GitLabClient(r)
    assert c.find_open_mr_by_parent_key("P2P-1229") is None


def test_find_open_mr_by_parent_key_filters_title_substring():
    """``--search`` matches both title and description on the GitLab side;
    a body-only mention must not be picked up as the parent's MR."""
    payload = json.dumps([
        {
            "iid": 1, "web_url": "u", "state": "opened",
            "title": "Unrelated work",
            "description": "see [P2P-1229] for context",
            "source_branch": "other/branch", "target_branch": "master",
        }
    ])
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["mr", "list"], _proc(0, payload))
    c = GitLabClient(r)
    assert c.find_open_mr_by_parent_key("P2P-1229") is None


def test_find_open_mr_by_parent_key_raises_on_ambiguous():
    payload = json.dumps([
        {
            "iid": 1, "web_url": "u1", "state": "opened",
            "title": "[P2P-1229] one", "description": "",
            "source_branch": "branch/a", "target_branch": "master",
        },
        {
            "iid": 2, "web_url": "u2", "state": "opened",
            "title": "[P2P-1229] two", "description": "",
            "source_branch": "branch/b", "target_branch": "master",
        },
    ])
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["mr", "list"], _proc(0, payload))
    c = GitLabClient(r)
    with pytest.raises(GitLabError, match="ambiguous"):
        c.find_open_mr_by_parent_key("P2P-1229")


def test_open_draft_mr_passes_assignee_to_glab_create():
    state = {"created": False}
    runner_calls: list[list[str]] = []

    def runner(args):
        runner_calls.append(args)
        if args[:2] == ["mr", "view"]:
            return _proc(0, _mr_json()) if state["created"] else _proc(1, "", "no open merge request found")
        if args[:2] == ["mr", "create"]:
            state["created"] = True
            return _proc(0, "draft mr created\n")
        raise AssertionError(f"unexpected: {args}")

    c = GitLabClient(runner)
    c.open_draft_mr(
        source_branch="mvu/afk/P2P-1220",
        target_branch="master",
        title="t",
        description="d",
        assignee="minh.vu.nakisa",
    )
    create_args = next(a for a in runner_calls if a[:2] == ["mr", "create"])
    assert "--assignee" in create_args
    assert create_args[create_args.index("--assignee") + 1] == "minh.vu.nakisa"


def test_open_draft_mr_when_absent_creates_then_views():
    r = FakeRunner()
    state = {"created": False}

    def view_handler(args):
        if state["created"]:
            return _proc(0, _mr_json())
        return _proc(1, "", "no open merge request found")

    def create_handler(args):
        state["created"] = True
        return _proc(0, "draft mr created\n")

    r.add(lambda a: a[:2] == ["mr", "view"], None)  # placeholder; real one below
    # replace placeholder by clearing and re-adding ordered
    r._responses.clear()
    r.add(lambda a: a[:2] == ["mr", "create"], None)
    r._responses.clear()

    # simpler: dispatch by command
    def runner(args):
        r.calls.append(args)
        if args[:2] == ["mr", "view"]:
            return view_handler(args)
        if args[:2] == ["mr", "create"]:
            return create_handler(args)
        raise AssertionError(f"unexpected {args}")

    c = GitLabClient(runner)
    mr = c.open_draft_mr(
        source_branch="mvu/afk/P2P-1220",
        target_branch="master",
        title="[P2P-1220] AFK bootstrap",
        description="body",
    )
    assert mr.iid == 25636
    create_calls = [a for a in r.calls if a[:2] == ["mr", "create"]]
    assert len(create_calls) == 1
    assert "--draft" in create_calls[0]
    assert "--target-branch" in create_calls[0]
    assert "master" in create_calls[0]


def test_open_draft_mr_idempotent_when_present():
    runner_calls: list[list[str]] = []

    def runner(args):
        runner_calls.append(args)
        if args[:2] == ["mr", "view"]:
            return _proc(0, _mr_json())
        raise AssertionError(f"unexpected: {args}")

    c = GitLabClient(runner)
    mr = c.open_draft_mr(
        source_branch="mvu/afk/P2P-1220",
        target_branch="master",
        title="x",
        description="y",
    )
    assert mr.iid == 25636
    assert all(a[:2] != ["mr", "create"] for a in runner_calls)


def test_update_subtasks_checklist_preserves_human_edits():
    initial_desc = (
        "## Summary\nhuman-written summary\n\n"
        "<!-- afk:subtasks:start -->\n"
        "- [ ] P2P-1221 old line\n"
        "<!-- afk:subtasks:end -->\n\n"
        "## Notes from reviewer\nplease check the rebase strategy"
    )

    runner_calls: list[list[str]] = []

    def runner(args):
        runner_calls.append(args)
        if args[:2] == ["mr", "view"]:
            return _proc(0, _mr_json(description=initial_desc))
        if args[:2] == ["mr", "update"]:
            return _proc(0, "updated")
        raise AssertionError(f"unexpected: {args}")

    c = GitLabClient(runner)
    items = [
        SubtaskItem("P2P-1221", "scaffold", done=True),
        SubtaskItem("P2P-1222", "worktree", done=True),
        SubtaskItem("P2P-1223", "jira", done=False),
    ]
    mr = c.update_subtasks_checklist("mvu/afk/P2P-1220", items)
    update_calls = [a for a in runner_calls if a[:2] == ["mr", "update"]]
    assert len(update_calls) == 1
    new_desc_arg_idx = update_calls[0].index("--description") + 1
    new_desc = update_calls[0][new_desc_arg_idx]
    assert "## Summary\nhuman-written summary" in new_desc
    assert "## Notes from reviewer\nplease check the rebase strategy" in new_desc
    assert "- [x] P2P-1221 scaffold" in new_desc
    assert "- [x] P2P-1222 worktree" in new_desc
    assert "- [ ] P2P-1223 jira" in new_desc
    assert "old line" not in new_desc
    assert mr.description == new_desc


def test_update_subtasks_no_change_skips_glab_update():
    desc = (
        "<!-- afk:subtasks:start -->\n"
        "- [x] P2P-1221 scaffold\n"
        "<!-- afk:subtasks:end -->"
    )
    runner_calls: list[list[str]] = []

    def runner(args):
        runner_calls.append(args)
        if args[:2] == ["mr", "view"]:
            return _proc(0, _mr_json(description=desc))
        if args[:2] == ["mr", "update"]:
            raise AssertionError("should not call update when description unchanged")
        raise AssertionError(f"unexpected: {args}")

    c = GitLabClient(runner)
    c.update_subtasks_checklist(
        "mvu/afk/P2P-1220", [SubtaskItem("P2P-1221", "scaffold", done=True)]
    )
    assert all(a[:2] != ["mr", "update"] for a in runner_calls)


def test_splice_marker_block_appends_when_markers_missing_with_create_if_missing():
    body = _render_subtasks_block([SubtaskItem("P2P-1", "x", done=False)])
    out = splice_marker_block(
        "## Summary\nhi", body, marker_id="subtasks", create_if_missing=True,
    )
    assert "<!-- afk:subtasks:start -->" in out
    assert "- [ ] P2P-1 x" in out
    assert "<!-- afk:subtasks:end -->" in out
    assert out.startswith("## Summary\nhi")


def test_splice_marker_block_replaces_within_markers():
    initial = (
        "before\n"
        "<!-- afk:subtasks:start -->\n"
        "- [ ] OLD\n"
        "<!-- afk:subtasks:end -->\n"
        "after"
    )
    body = _render_subtasks_block([SubtaskItem("P2P-2", "y", done=True)])
    out = splice_marker_block(initial, body, marker_id="subtasks")
    assert "- [x] P2P-2 y" in out
    assert "OLD" not in out
    assert out.startswith("before\n")
    assert out.endswith("after")


def test_splice_marker_block_strict_raises_when_markers_absent():
    """Default ``create_if_missing=False`` → raise SectionMarkerMissing.
    Catches "human deleted the markers" without silently re-creating."""
    with pytest.raises(SectionMarkerMissing, match="absent"):
        splice_marker_block("## Summary\nhi", "body", marker_id="subtasks")


def test_splice_marker_block_strict_raises_when_pair_malformed():
    """One marker without its mate is corrupt state — even with
    create_if_missing=True, refuse to auto-repair."""
    desc_only_start = (
        "## Summary\nhi\n"
        "<!-- afk:subtasks:start -->\n"
        "- [ ] orphan\n"
    )
    with pytest.raises(SectionMarkerMissing, match="malformed"):
        splice_marker_block(
            desc_only_start, "body", marker_id="subtasks", create_if_missing=True,
        )


def test_splice_marker_block_marker_id_isolation():
    """Different marker_ids must not interfere — splicing 'subtasks' leaves
    a 'reviewers' block byte-identical."""
    desc = (
        "<!-- afk:reviewers:start -->\n"
        "@alice\n"
        "<!-- afk:reviewers:end -->\n"
        "<!-- afk:subtasks:start -->\n"
        "- [ ] OLD\n"
        "<!-- afk:subtasks:end -->\n"
    )
    out = splice_marker_block(desc, "- [x] new", marker_id="subtasks")
    assert "<!-- afk:reviewers:start -->\n@alice\n<!-- afk:reviewers:end -->" in out
    assert "OLD" not in out
    assert "- [x] new" in out
