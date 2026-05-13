"""Unit tests for ``github_pr_client`` (ST05).

All ``gh`` invocations flow through an injected ``GhRunner`` stub — zero
network, zero real subprocess. Coverage maps to the ST05 spec "Tests
cover" bullet:

- find-by-branch: single match, none, multiple → error
- find-by-parent: search-then-filter, body-only false positive dropped,
  ambiguity error
- open-draft-PR: idempotent re-open (existing PR returned, no create),
  fresh open (create called then re-query)
- ``Closes #{N}`` present in initial body
- splice: round-trip (empty / single / multi line) round-trip + no-write
  when body unchanged
- update-description: overwrite + retry path
- Scm Protocol conformance (``isinstance(client, Scm)``)
"""

from __future__ import annotations

import json
import subprocess
from typing import Callable

import pytest

from afk_driver.github_pr_client import (
    GhRunner,
    GitHubPrClient,
    GitHubPrError,
    OpenDraftPrSpec,
    PRInfo,
    default_runner,
    splice_marker_block,
)
from afk_driver.scm_protocol import PrRef, Scm
from afk_driver.section_splice import SectionMarkerMissing


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _proc(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _pr_row(**overrides) -> dict:
    base = {
        "number": 42,
        "url": "https://github.com/acme/widgets/pull/42",
        "state": "OPEN",
        "title": "[#10] AFK feature",
        "body": "preamble\n\n<!-- afk:subtasks:start -->\nCloses #10\n<!-- afk:subtasks:end -->\n",
        "headRefName": "mvu/afk/acme-widgets-10",
        "baseRefName": "main",
        "isDraft": True,
    }
    base.update(overrides)
    return base


class FakeRunner:
    """Predicate-keyed responder. Mirrors the GitHub-issues-client test
    suite shape so the GitHub-PR suite reads identically.
    """

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self._responses: list[
            tuple[Callable[[list[str]], bool], list[subprocess.CompletedProcess]]
        ] = []

    def add(
        self,
        predicate: Callable[[list[str]], bool],
        response: subprocess.CompletedProcess,
    ) -> None:
        self._responses.append((predicate, [response]))

    def add_sequence(
        self,
        predicate: Callable[[list[str]], bool],
        responses: list[subprocess.CompletedProcess],
    ) -> None:
        self._responses.append((predicate, list(responses)))

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(args)
        for pred, queue in self._responses:
            if pred(args):
                if len(queue) == 1:
                    return queue[0]
                return queue.pop(0)
        raise AssertionError(f"FakeRunner: no handler for {args}")


def _no_sleep(_: float) -> None:
    pass


# ---------------------------------------------------------------------------
# default_runner — smoke (no network — we monkeypatch subprocess.run)
# ---------------------------------------------------------------------------


def test_default_runner_prepends_gh(monkeypatch):
    captured: dict[str, list[str]] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        return _proc(0, "[]")

    monkeypatch.setattr("subprocess.run", fake_run)
    proc = default_runner(["pr", "list", "--repo", "acme/widgets"])
    assert captured["argv"][0] == "gh"
    assert captured["argv"][1:] == ["pr", "list", "--repo", "acme/widgets"]
    assert proc.returncode == 0


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_github_pr_client_is_scm_protocol():
    """``GitHubPrClient`` must satisfy the runtime-checkable ``Scm``
    Protocol (ST01 / SDD §9 Strategy classDiagram)."""
    r = FakeRunner()
    c = GitHubPrClient(r, sleep=_no_sleep)
    assert isinstance(c, Scm)


# ---------------------------------------------------------------------------
# find_open_pr_by_branch
# ---------------------------------------------------------------------------


def test_find_open_pr_by_branch_returns_info_on_single_match():
    r = FakeRunner()
    r.add(
        lambda a: a[:2] == ["pr", "list"] and "--head" in a,
        _proc(0, json.dumps([_pr_row()])),
    )
    c = GitHubPrClient(r, sleep=_no_sleep)
    info = c.find_open_pr_by_branch("acme/widgets", "mvu/afk/acme-widgets-10")
    assert info is not None
    assert info.number == 42
    assert info.head_ref_name == "mvu/afk/acme-widgets-10"
    assert info.base_ref_name == "main"
    assert info.is_draft is True
    # Verify the call shape.
    call = next(a for a in r.calls if a[:2] == ["pr", "list"])
    assert "--head" in call and call[call.index("--head") + 1] == "mvu/afk/acme-widgets-10"
    assert "--state" in call and call[call.index("--state") + 1] == "open"
    assert "--repo" in call and call[call.index("--repo") + 1] == "acme/widgets"


def test_find_open_pr_by_branch_returns_none_on_empty():
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["pr", "list"], _proc(0, "[]"))
    c = GitHubPrClient(r, sleep=_no_sleep)
    assert c.find_open_pr_by_branch("acme/widgets", "mvu/afk/none") is None


def test_find_open_pr_by_branch_raises_on_multiple():
    """Two open PRs sharing a head ref is theoretically impossible on
    GitHub but the adapter must surface it as an error rather than
    pick — matches ``find_open_pr_by_parent`` ambiguity stance."""
    r = FakeRunner()
    r.add(
        lambda a: a[:2] == ["pr", "list"],
        _proc(0, json.dumps([_pr_row(number=1), _pr_row(number=2)])),
    )
    c = GitHubPrClient(r, sleep=_no_sleep)
    with pytest.raises(GitHubPrError, match="refusing to pick one"):
        c.find_open_pr_by_branch("acme/widgets", "mvu/afk/dup")


def test_find_open_pr_by_branch_raises_on_gh_failure():
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["pr", "list"], _proc(1, "", "auth required"))
    c = GitHubPrClient(r, sleep=_no_sleep)
    with pytest.raises(GitHubPrError, match="auth required"):
        c.find_open_pr_by_branch("acme/widgets", "mvu/afk/x")


def test_find_open_pr_by_branch_raises_on_non_json():
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["pr", "list"], _proc(0, "not json"))
    c = GitHubPrClient(r, sleep=_no_sleep)
    with pytest.raises(GitHubPrError, match="non-JSON"):
        c.find_open_pr_by_branch("acme/widgets", "mvu/afk/x")


# ---------------------------------------------------------------------------
# find_open_pr_by_parent_number
# ---------------------------------------------------------------------------


def test_find_open_pr_by_parent_number_filters_title_substring():
    """``--search`` on GitHub matches description too; a body-only
    mention of ``[#10]`` must not be returned."""
    payload = json.dumps([
        _pr_row(
            number=99,
            title="Unrelated work",
            body="see [#10] for context",
        )
    ])
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["pr", "list"] and "--search" in a, _proc(0, payload))
    c = GitHubPrClient(r, sleep=_no_sleep)
    assert c.find_open_pr_by_parent_number("acme/widgets", 10) is None


def test_find_open_pr_by_parent_number_returns_single_match():
    payload = json.dumps([_pr_row(title="[#10] AFK feature")])
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["pr", "list"] and "--search" in a, _proc(0, payload))
    c = GitHubPrClient(r, sleep=_no_sleep)
    info = c.find_open_pr_by_parent_number("acme/widgets", 10)
    assert info is not None
    assert info.number == 42
    # Verify search token shape.
    call = next(a for a in r.calls if "--search" in a)
    assert call[call.index("--search") + 1] == "[#10]"


def test_find_open_pr_by_parent_number_raises_on_ambiguous():
    payload = json.dumps([
        _pr_row(number=1, title="[#10] first"),
        _pr_row(number=2, title="[#10] second"),
    ])
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["pr", "list"] and "--search" in a, _proc(0, payload))
    c = GitHubPrClient(r, sleep=_no_sleep)
    with pytest.raises(GitHubPrError, match="ambiguous"):
        c.find_open_pr_by_parent_number("acme/widgets", 10)


def test_find_open_pr_by_parent_number_returns_none_when_no_match():
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["pr", "list"] and "--search" in a, _proc(0, "[]"))
    c = GitHubPrClient(r, sleep=_no_sleep)
    assert c.find_open_pr_by_parent_number("acme/widgets", 999) is None


# ---------------------------------------------------------------------------
# Scm Protocol find_open_pr_by_parent (parent_id = "owner/repo#N")
# ---------------------------------------------------------------------------


def test_find_open_pr_by_parent_protocol_takes_owner_repo_hash_n():
    payload = json.dumps([_pr_row(title="[#10] AFK feature")])
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["pr", "list"] and "--search" in a, _proc(0, payload))
    c = GitHubPrClient(r, sleep=_no_sleep)
    pr_ref = c.find_open_pr_by_parent("acme/widgets#10")
    assert pr_ref is not None
    assert isinstance(pr_ref, PrRef)
    assert pr_ref.url == "https://github.com/acme/widgets/pull/42"
    assert pr_ref.source_branch == "mvu/afk/acme-widgets-10"
    assert pr_ref.target_branch == "main"


def test_find_open_pr_by_parent_protocol_rejects_malformed_id():
    r = FakeRunner()
    c = GitHubPrClient(r, sleep=_no_sleep)
    with pytest.raises(GitHubPrError, match="owner/repo#N"):
        c.find_open_pr_by_parent("notavalid")


# ---------------------------------------------------------------------------
# open_draft_pr — idempotent re-open + fresh open + Closes #N
# ---------------------------------------------------------------------------


def _spec(**overrides) -> OpenDraftPrSpec:
    base: dict = dict(
        repo="acme/widgets",
        source_branch="mvu/afk/acme-widgets-10",
        target_branch="main",
        title="[#10] AFK feature",
        body="Human preamble: this PR is the AFK landing zone for parent #10.",
        parent_issue_number=10,
    )
    base.update(overrides)
    return OpenDraftPrSpec(**base)


def test_open_draft_pr_idempotent_when_pr_already_exists():
    """If an open PR already lives on the head branch, return it
    unchanged — no second ``gh pr create``."""
    r = FakeRunner()
    r.add(
        lambda a: a[:2] == ["pr", "list"] and "--head" in a,
        _proc(0, json.dumps([_pr_row()])),
    )
    c = GitHubPrClient(r, sleep=_no_sleep)
    pr_ref = c.open_draft_pr(_spec())
    assert pr_ref.url == "https://github.com/acme/widgets/pull/42"
    # No create call.
    assert all(a[:2] != ["pr", "create"] for a in r.calls)


def test_open_draft_pr_fresh_calls_create_then_reads_back():
    """Empty head-branch list → ``gh pr create --draft`` → re-query
    returns the new PR."""
    state = {"created": False}

    def runner(args):
        r.calls.append(args)
        if args[:2] == ["pr", "list"]:
            if state["created"]:
                return _proc(0, json.dumps([_pr_row()]))
            return _proc(0, "[]")
        if args[:2] == ["pr", "create"]:
            state["created"] = True
            return _proc(0, "https://github.com/acme/widgets/pull/42\n")
        raise AssertionError(f"unexpected {args}")

    r = FakeRunner()
    c = GitHubPrClient(runner, sleep=_no_sleep)
    pr_ref = c.open_draft_pr(_spec())
    assert pr_ref.url == "https://github.com/acme/widgets/pull/42"

    create_calls = [a for a in r.calls if a[:2] == ["pr", "create"]]
    assert len(create_calls) == 1
    create = create_calls[0]
    assert "--draft" in create
    assert "--base" in create and create[create.index("--base") + 1] == "main"
    assert "--head" in create and create[create.index("--head") + 1] == "mvu/afk/acme-widgets-10"
    assert "--title" in create and create[create.index("--title") + 1] == "[#10] AFK feature"
    # Body must contain Closes #10 inside the marker pair.
    body = create[create.index("--body") + 1]
    assert "Closes #10" in body
    assert "<!-- afk:subtasks:start -->" in body
    assert "<!-- afk:subtasks:end -->" in body
    # Preamble preserved.
    assert "Human preamble: this PR is the AFK landing zone for parent #10." in body


def test_open_draft_pr_create_failure_with_no_existing_pr_raises():
    """``gh pr create`` exit non-zero AND head-branch re-query still
    empty → surface ``GitHubPrError`` (SDD §5 retry table row
    "gh pr create --draft": "re-query for existing; if absent, fail
    parent")."""
    def runner(args):
        r.calls.append(args)
        if args[:2] == ["pr", "list"]:
            return _proc(0, "[]")
        if args[:2] == ["pr", "create"]:
            return _proc(1, "", "remote rejected: branch missing")
        raise AssertionError(f"unexpected {args}")

    r = FakeRunner()
    c = GitHubPrClient(runner, sleep=_no_sleep)
    with pytest.raises(GitHubPrError, match="branch missing"):
        c.open_draft_pr(_spec())


def test_open_draft_pr_create_failure_with_existing_pr_succeeds():
    """Race condition: ``gh pr create`` fails because someone else just
    opened the PR. Re-query finds it → return it without raising."""
    state = {"create_attempted": False}

    def runner(args):
        r.calls.append(args)
        if args[:2] == ["pr", "list"]:
            if state["create_attempted"]:
                return _proc(0, json.dumps([_pr_row()]))
            return _proc(0, "[]")
        if args[:2] == ["pr", "create"]:
            state["create_attempted"] = True
            return _proc(1, "", "a pull request for branch already exists")
        raise AssertionError(f"unexpected {args}")

    r = FakeRunner()
    c = GitHubPrClient(runner, sleep=_no_sleep)
    pr_ref = c.open_draft_pr(_spec())
    assert pr_ref.url == "https://github.com/acme/widgets/pull/42"


def test_open_draft_pr_rejects_non_spec_input():
    r = FakeRunner()
    c = GitHubPrClient(r, sleep=_no_sleep)
    with pytest.raises(TypeError, match="OpenDraftPrSpec"):
        c.open_draft_pr({"repo": "x"})  # type: ignore[arg-type]


def test_initial_body_contains_closes_for_parent_issue():
    """Tighter unit check: the initial body (as passed to ``gh pr
    create --body``) embeds ``Closes #{parent_issue_number}`` inside the
    marker block — so the human merge auto-closes the parent issue."""
    captured: dict[str, list[str]] = {}

    def runner(args):
        if args[:2] == ["pr", "list"]:
            if captured.get("created"):
                return _proc(0, json.dumps([_pr_row()]))
            return _proc(0, "[]")
        if args[:2] == ["pr", "create"]:
            captured["argv"] = args
            captured["created"] = True
            return _proc(0, "ok\n")
        raise AssertionError(f"unexpected {args}")

    c = GitHubPrClient(runner, sleep=_no_sleep)
    c.open_draft_pr(_spec(parent_issue_number=314))
    body = captured["argv"][captured["argv"].index("--body") + 1]
    # The Closes #N line sits inside the marker pair so subsequent
    # splices re-render it as part of the canonical block.
    start_idx = body.index("<!-- afk:subtasks:start -->")
    end_idx = body.index("<!-- afk:subtasks:end -->")
    inside = body[start_idx:end_idx]
    assert "Closes #314" in inside


# ---------------------------------------------------------------------------
# update_pr_description — overwrite + retry
# ---------------------------------------------------------------------------


def test_update_pr_description_for_overwrites_body():
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["pr", "edit"], _proc(0, "edited"))
    c = GitHubPrClient(r, sleep=_no_sleep)
    c.update_pr_description_for("acme/widgets", "mvu/afk/x", "new body")
    edit = next(a for a in r.calls if a[:2] == ["pr", "edit"])
    assert edit[2] == "mvu/afk/x"
    assert "--repo" in edit and edit[edit.index("--repo") + 1] == "acme/widgets"
    assert "--body" in edit and edit[edit.index("--body") + 1] == "new body"


def test_update_pr_description_retries_once_then_succeeds():
    """SDD §5 retry table row ``gh pr edit --body``: 2 attempts, 0/500 ms.
    First call fails, second succeeds — only one error surfaced and the
    body is written."""
    r = FakeRunner()
    r.add_sequence(
        lambda a: a[:2] == ["pr", "edit"],
        [_proc(1, "", "transient 500"), _proc(0, "ok")],
    )
    sleeps: list[float] = []
    c = GitHubPrClient(r, sleep=sleeps.append)
    c.update_pr_description_for("acme/widgets", "mvu/afk/x", "body")
    assert len([a for a in r.calls if a[:2] == ["pr", "edit"]]) == 2
    # Second attempt's backoff (500 ms) was respected; first attempt is 0.
    assert sleeps == [0.5]


def test_update_pr_description_raises_after_retry_exhaustion():
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["pr", "edit"], _proc(1, "", "persistent 500"))
    c = GitHubPrClient(r, sleep=_no_sleep)
    with pytest.raises(GitHubPrError, match="persistent 500"):
        c.update_pr_description_for("acme/widgets", "mvu/afk/x", "body")
    # 2 attempts per SDD retry budget.
    assert len([a for a in r.calls if a[:2] == ["pr", "edit"]]) == 2


# ---------------------------------------------------------------------------
# splice_pr_block — round-trip
# ---------------------------------------------------------------------------


def test_splice_pr_block_round_trips_through_existing_body():
    """Read PR body → splice new block content → write back with the
    foreign prose preserved byte-identical."""
    initial_body = (
        "## Summary\nhuman-written summary\n\n"
        "<!-- afk:subtasks:start -->\n"
        "Closes #10\n"
        "<!-- afk:subtasks:end -->\n\n"
        "## Notes from reviewer\nplease check rebase"
    )
    captured: dict[str, str] = {}

    def runner(args):
        r.calls.append(args)
        if args[:2] == ["pr", "list"]:
            return _proc(0, json.dumps([_pr_row(body=initial_body)]))
        if args[:2] == ["pr", "edit"]:
            captured["body"] = args[args.index("--body") + 1]
            return _proc(0, "edited")
        raise AssertionError(f"unexpected {args}")

    r = FakeRunner()
    c = GitHubPrClient(runner, sleep=_no_sleep)
    new_block = "Closes #10\nCloses #11\nCloses #12\n- [x] #11 scaffold\n- [ ] #12 wire"
    c.splice_pr_block_for("acme/widgets", "mvu/afk/acme-widgets-10", new_block)
    body = captured["body"]
    assert "## Summary\nhuman-written summary" in body
    assert "## Notes from reviewer\nplease check rebase" in body
    assert "Closes #10" in body
    assert "Closes #11" in body
    assert "Closes #12" in body
    assert "- [x] #11 scaffold" in body
    assert "- [ ] #12 wire" in body


def test_splice_pr_block_skips_edit_when_body_unchanged():
    """No diff between rendered body and existing → no ``gh pr edit``
    call — matches ``gitlab_client.splice_pr_block`` no-op discipline."""
    body = (
        "<!-- afk:subtasks:start -->\n"
        "Closes #10\n"
        "<!-- afk:subtasks:end -->"
    )

    def runner(args):
        r.calls.append(args)
        if args[:2] == ["pr", "list"]:
            return _proc(0, json.dumps([_pr_row(body=body)]))
        if args[:2] == ["pr", "edit"]:
            raise AssertionError("should not call pr edit when body unchanged")
        raise AssertionError(f"unexpected {args}")

    r = FakeRunner()
    c = GitHubPrClient(runner, sleep=_no_sleep)
    c.splice_pr_block_for("acme/widgets", "mvu/afk/x", "Closes #10")
    assert all(a[:2] != ["pr", "edit"] for a in r.calls)


def test_splice_pr_block_appends_when_markers_missing():
    """``create_if_missing=True`` path — first splice after the PR is
    opened by a human (whose body has no markers yet) must inject the
    marker pair rather than raise."""
    def runner(args):
        r.calls.append(args)
        if args[:2] == ["pr", "list"]:
            return _proc(0, json.dumps([_pr_row(body="just human prose")]))
        if args[:2] == ["pr", "edit"]:
            captured["body"] = args[args.index("--body") + 1]
            return _proc(0, "edited")
        raise AssertionError(f"unexpected {args}")

    r = FakeRunner()
    captured: dict[str, str] = {}
    c = GitHubPrClient(runner, sleep=_no_sleep)
    c.splice_pr_block_for("acme/widgets", "mvu/afk/x", "Closes #10")
    body = captured["body"]
    assert body.startswith("just human prose")
    assert "<!-- afk:subtasks:start -->" in body
    assert "Closes #10" in body
    assert "<!-- afk:subtasks:end -->" in body


def test_splice_pr_block_raises_when_no_open_pr():
    r = FakeRunner()
    r.add(lambda a: a[:2] == ["pr", "list"], _proc(0, "[]"))
    c = GitHubPrClient(r, sleep=_no_sleep)
    with pytest.raises(GitHubPrError, match="no open PR"):
        c.splice_pr_block_for("acme/widgets", "mvu/afk/gone", "body")


# ---------------------------------------------------------------------------
# Scm Protocol-shape update / splice (need repo stashed via open_draft_pr)
# ---------------------------------------------------------------------------


def test_protocol_update_after_open_uses_stashed_repo():
    """The two-arg Protocol ``update_pr_description(branch, body)`` must
    address the same repo that ``open_draft_pr`` opened against."""
    state = {"opened": False}

    def runner(args):
        r.calls.append(args)
        if args[:2] == ["pr", "list"]:
            if state["opened"]:
                return _proc(0, json.dumps([_pr_row()]))
            return _proc(0, "[]")
        if args[:2] == ["pr", "create"]:
            state["opened"] = True
            return _proc(0, "ok\n")
        if args[:2] == ["pr", "edit"]:
            return _proc(0, "edited")
        raise AssertionError(f"unexpected {args}")

    r = FakeRunner()
    c = GitHubPrClient(runner, sleep=_no_sleep)
    c.open_draft_pr(_spec())
    c.update_pr_description("mvu/afk/acme-widgets-10", "new body")
    edit = next(a for a in r.calls if a[:2] == ["pr", "edit"])
    # The repo was stashed by open_draft_pr — Protocol caller didn't
    # need to pass it again.
    assert edit[edit.index("--repo") + 1] == "acme/widgets"


def test_protocol_update_without_prior_open_raises():
    r = FakeRunner()
    c = GitHubPrClient(r, sleep=_no_sleep)
    with pytest.raises(GitHubPrError, match="no recorded repo"):
        c.update_pr_description("mvu/afk/orphan", "body")


# ---------------------------------------------------------------------------
# splice_marker_block — direct unit tests (mirror gitlab_client suite)
# ---------------------------------------------------------------------------


def test_splice_marker_block_replaces_within_markers():
    initial = (
        "before\n"
        "<!-- afk:subtasks:start -->\n"
        "old\n"
        "<!-- afk:subtasks:end -->\n"
        "after"
    )
    out = splice_marker_block(initial, "Closes #10\nCloses #11", marker_id="subtasks")
    assert "Closes #10" in out
    assert "Closes #11" in out
    assert "old" not in out
    assert out.startswith("before\n")
    assert out.endswith("after")


def test_splice_marker_block_appends_when_missing_with_create_if_missing():
    out = splice_marker_block(
        "## Summary\nhi", "Closes #10", marker_id="subtasks", create_if_missing=True,
    )
    assert out.startswith("## Summary\nhi")
    assert "<!-- afk:subtasks:start -->" in out
    assert "Closes #10" in out
    assert "<!-- afk:subtasks:end -->" in out


def test_splice_marker_block_strict_raises_when_absent():
    with pytest.raises(SectionMarkerMissing, match="absent"):
        splice_marker_block("hi", "body", marker_id="subtasks")


def test_splice_marker_block_strict_raises_when_malformed():
    half = "## Summary\nhi\n<!-- afk:subtasks:start -->\norphan\n"
    with pytest.raises(SectionMarkerMissing, match="malformed"):
        splice_marker_block(half, "body", marker_id="subtasks", create_if_missing=True)
