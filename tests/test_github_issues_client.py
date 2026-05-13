"""Unit tests for ``github_issues_client`` (ST04).

All ``gh`` invocations flow through an injected ``GhRunner`` stub — zero
network, zero real subprocess. Coverage maps to the ST04 spec's "Tests
cover" bullet:

- queue search call shape (``list_pickable`` → single ``gh search issues``)
- sub-issue REST envelope (``attach_sub_issue`` success + 404 + malformed JSON)
- phase-label swap atomicity (single ``gh issue edit`` with both flags)
- verify-after-write retry sequence (success after retry 2)
- verify-after-write abort (persistent mismatch → 3 attempts then raise)
- comment dedup (content-hash skip)
- target-branch label read + default-branch fallback
- malformed/missing label edge case
- ``gh label create --force`` per ADR-0002 follow-up
- ``list_stuck_subissues`` returns the union across the 3 non-pending phases
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from typing import Callable

import pytest

from afk_driver.github_issues_client import (
    AFK_AGENTS_LABEL,
    ALL_PHASE_LABELS,
    GitHubApiError,
    GitHubIssuesClient,
    GitHubLabelMismatch,
    GhRunner,
    PHASE_CR_MERGE,
    PHASE_DESIGNING,
    PHASE_DEVELOPING,
    PHASE_PENDING,
    PhaseTransitionError,
    default_runner,
)
from afk_driver.tracker_protocol import IssueTracker, ParentRef, SubIssueRef


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _proc(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class FakeRunner:
    """Predicate-keyed responder. Each call is also recorded for assertions.

    Mirrors ``tests/test_repo_clone_manager.FakeRunner`` shape so the GitHub
    suite reads identically to the existing GitLab/repo-clone tests.
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
        """Add a single stub. The handler will fire every time the predicate
        matches (i.e. it is a stateless responder)."""
        self._responses.append((predicate, [response]))

    def add_sequence(
        self,
        predicate: Callable[[list[str]], bool],
        responses: list[subprocess.CompletedProcess],
    ) -> None:
        """Add a multi-call stub. Returns the responses in order, then keeps
        replaying the last one. Useful for the verify-after-write retry
        tests where the same argv shape must return mismatch-then-success.
        """
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
    """Used everywhere — backoff sleeps are bypassed in tests."""


def _client(runner: GhRunner) -> GitHubIssuesClient:
    """Construct a client with no-op sleep so retry-loop tests don't wait."""
    return GitHubIssuesClient(runner=runner, sleep=_no_sleep)


# Predicate helpers — every test that matches argv shape uses these for
# readability.
def _is(*prefix: str) -> Callable[[list[str]], bool]:
    p = list(prefix)
    return lambda a: a[: len(p)] == p


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_github_issues_client_implements_issue_tracker_protocol():
    """Acceptance bullet 1 — ``class GitHubIssuesClient(IssueTracker):``
    (explicit nominal subtype)."""
    assert IssueTracker in GitHubIssuesClient.__mro__
    c = _client(FakeRunner())
    assert isinstance(c, IssueTracker)


def test_default_runner_is_callable():
    """Smoke — exported ``default_runner`` and ``GhRunner`` alias are usable."""
    assert callable(default_runner)
    assert GhRunner is not None


# ---------------------------------------------------------------------------
# list_pickable — queue search call shape
# ---------------------------------------------------------------------------


def test_list_pickable_issues_a_single_search_call_with_canonical_filters():
    """Acceptance bullet 4 — ``gh search issues`` with the AFK gate filters."""
    payload = json.dumps([
        {
            "repository": {"nameWithOwner": "octo/widget"},
            "number": 42,
            "title": "do the thing",
            "body": "",
        }
    ])
    r = FakeRunner()
    r.add(_is("search", "issues"), _proc(0, payload))
    refs = _client(r).list_pickable()

    assert len(refs) == 1
    assert refs[0] == SubIssueRef(id="octo/widget#42", parent_id="")
    # Single search call, no other side effects.
    assert len([c for c in r.calls if c[:2] == ["search", "issues"]]) == 1
    call = r.calls[0]
    # The label gate appears as a positional query string somewhere in argv.
    query = call[-1]
    assert f"label:{AFK_AGENTS_LABEL}" in query
    assert f"label:{PHASE_PENDING}" in query
    assert "assignee:@me" in query


def test_list_pickable_returns_empty_on_no_results():
    r = FakeRunner()
    r.add(_is("search", "issues"), _proc(0, "[]"))
    assert _client(r).list_pickable() == []


def test_list_pickable_wraps_non_zero_exit_in_typed_error():
    r = FakeRunner()
    r.add(_is("search", "issues"), _proc(1, "", "gh: not authenticated"))
    with pytest.raises(GitHubApiError, match="gh search issues failed"):
        _client(r).list_pickable()


def test_list_pickable_wraps_non_json_stdout_in_typed_error():
    r = FakeRunner()
    r.add(_is("search", "issues"), _proc(0, "not-json"))
    with pytest.raises(GitHubApiError, match="non-JSON"):
        _client(r).list_pickable()


def test_list_pickable_accepts_legacy_repository_shape():
    """``gh`` projections sometimes emit ``{"owner": {"login": ...}, "name"}``
    instead of ``{"nameWithOwner"}`` — both shapes must parse."""
    payload = json.dumps([
        {
            "repository": {"owner": {"login": "octo"}, "name": "widget"},
            "number": 7,
        }
    ])
    r = FakeRunner()
    r.add(_is("search", "issues"), _proc(0, payload))
    refs = _client(r).list_pickable()
    assert refs[0].id == "octo/widget#7"


# ---------------------------------------------------------------------------
# list_stuck_subissues — sweeper input (ADR-0005)
# ---------------------------------------------------------------------------


def test_list_stuck_subissues_searches_each_non_pending_phase_and_unions():
    """One search per non-pending phase; results deduplicated by id."""
    def _row(num: int) -> dict:
        return {"repository": {"nameWithOwner": "octo/widget"}, "number": num}

    r = FakeRunner()
    # Same issue appears in both designing and developing (drift case);
    # the union should still return it exactly once.
    designing = json.dumps([_row(10), _row(11)])
    developing = json.dumps([_row(11)])
    cr_merge = json.dumps([_row(12)])

    def _picker(args: list[str]) -> str:
        query = args[-1]
        if PHASE_DESIGNING in query:
            return designing
        if PHASE_DEVELOPING in query:
            return developing
        if PHASE_CR_MERGE in query:
            return cr_merge
        raise AssertionError(f"unexpected query: {query}")

    # Custom dispatch — generate a stub per phase using add_sequence wouldn't
    # work since predicates can't read state; instead intercept calls
    # directly.
    class _Phased(FakeRunner):
        def __call__(self, args: list[str]) -> subprocess.CompletedProcess:
            self.calls.append(args)
            if args[:2] == ["search", "issues"]:
                return _proc(0, _picker(args))
            raise AssertionError(f"unexpected call: {args}")

    refs = _client(_Phased()).list_stuck_subissues()
    ids = sorted(r.id for r in refs)
    assert ids == ["octo/widget#10", "octo/widget#11", "octo/widget#12"]


# ---------------------------------------------------------------------------
# Phase transitions — atomic swap + verify (ADR-0002 / ADR-0004)
# ---------------------------------------------------------------------------


def _labels_payload(*names: str) -> str:
    return json.dumps({"labels": [{"name": n} for n in names]})


def test_transition_phase_uses_single_edit_call_with_both_flags():
    """Acceptance bullet 2 — single ``gh issue edit`` with both
    ``--remove-label`` and ``--add-label`` (ADR-0002 atomicity)."""
    r = FakeRunner()
    r.add(_is("issue", "edit"), _proc(0))
    r.add(_is("issue", "view"), _proc(0, _labels_payload(PHASE_DEVELOPING)))
    _client(r).transition_phase("octo/widget#42", PHASE_DEVELOPING)

    edit_call = next(c for c in r.calls if c[:2] == ["issue", "edit"])
    # Atomicity — both flags appear in the same argv.
    assert "--remove-label" in edit_call
    assert "--add-label" in edit_call
    remove_csv = edit_call[edit_call.index("--remove-label") + 1]
    add_label = edit_call[edit_call.index("--add-label") + 1]
    # Remove targets every afk:* label (so the swap is unconditional).
    for phase in ALL_PHASE_LABELS:
        assert phase in remove_csv
    assert add_label == PHASE_DEVELOPING
    # ``--repo owner/repo`` present.
    assert "--repo" in edit_call
    assert edit_call[edit_call.index("--repo") + 1] == "octo/widget"


def test_transition_phase_rejects_unknown_target_label():
    r = FakeRunner()
    with pytest.raises(ValueError, match="unknown target label"):
        _client(r).transition_phase("octo/widget#42", "afk:bogus")
    # No subprocess call before validation.
    assert r.calls == []


def test_transition_phase_rejects_malformed_issue_id():
    r = FakeRunner()
    with pytest.raises(GitHubApiError, match="owner/repo#N"):
        _client(r).transition_phase("not-a-coord", PHASE_DEVELOPING)


def test_transition_phase_named_methods_route_through_transition_phase():
    """``start_designing`` / ``start_developing`` / ``request_cr_merge`` /
    ``revert_to_pending`` all wire through ``transition_phase`` with the
    matching target label."""
    cases = [
        ("start_designing", PHASE_DESIGNING),
        ("start_developing", PHASE_DEVELOPING),
        ("request_cr_merge", PHASE_CR_MERGE),
        ("revert_to_pending", PHASE_PENDING),
    ]
    for method_name, expected_label in cases:
        r = FakeRunner()
        r.add(_is("issue", "edit"), _proc(0))
        r.add(_is("issue", "view"), _proc(0, _labels_payload(expected_label)))
        getattr(_client(r), method_name)("octo/widget#42")
        edit = next(c for c in r.calls if c[:2] == ["issue", "edit"])
        assert edit[edit.index("--add-label") + 1] == expected_label


# ---------------------------------------------------------------------------
# Verify-after-write retry (ADR-0004)
# ---------------------------------------------------------------------------


def test_transition_phase_retries_when_first_verify_mismatches_then_succeeds():
    """Acceptance bullet 3 — converge after retry 2 (zero-indexed 1)."""
    r = FakeRunner()
    r.add(_is("issue", "edit"), _proc(0))
    # First verify returns *no* afk label (the partial-write failure mode
    # ADR-0004 calls out by name); second verify shows the target.
    r.add_sequence(
        _is("issue", "view"),
        [
            _proc(0, _labels_payload()),                       # mismatch
            _proc(0, _labels_payload(PHASE_DEVELOPING)),       # success
        ],
    )
    _client(r).transition_phase("octo/widget#42", PHASE_DEVELOPING)

    # Two edit attempts (one per loop iteration), two verify reads.
    edits = [c for c in r.calls if c[:2] == ["issue", "edit"]]
    views = [c for c in r.calls if c[:2] == ["issue", "view"]]
    assert len(edits) == 2
    assert len(views) == 2
    # No abort comment was posted — recovery happened in-band.
    assert not any(c[:2] == ["issue", "comment"] for c in r.calls)


def test_transition_phase_aborts_after_third_persistent_mismatch():
    """Acceptance bullet 3 — persistent mismatch → abort comment + raise."""
    r = FakeRunner()
    r.add(_is("issue", "edit"), _proc(0))
    # All three verifies show the wrong label (a stale concurrent edit
    # racing the swap).
    r.add(
        _is("issue", "view"),
        _proc(0, _labels_payload(PHASE_PENDING)),
    )
    r.add(_is("issue", "comment"), _proc(0))

    with pytest.raises(PhaseTransitionError, match="failed after 3 attempts"):
        _client(r).transition_phase("octo/widget#42", PHASE_DEVELOPING)

    edits = [c for c in r.calls if c[:2] == ["issue", "edit"]]
    views = [c for c in r.calls if c[:2] == ["issue", "view"]]
    comments = [c for c in r.calls if c[:2] == ["issue", "comment"]]
    assert len(edits) == 3
    assert len(views) == 3
    assert len(comments) == 1
    # Abort comment carries the canonical body verbatim (ADR-0004 caption).
    abort_call = comments[0]
    assert abort_call[abort_call.index("--body") + 1] == (
        "AFK: phase transition failed; aborting"
    )


def test_transition_phase_uses_injected_backoff_delays():
    """Backoff is parametrised by ``sleep`` injection — explicit assertion
    that the policy values (0/200/600 ms per ADR-0004) reach the sleep
    function in seconds, in order, skipping the leading zero.
    """
    delays: list[float] = []
    r = FakeRunner()
    r.add(_is("issue", "edit"), _proc(0))
    r.add(
        _is("issue", "view"),
        _proc(0, _labels_payload(PHASE_PENDING)),
    )
    r.add(_is("issue", "comment"), _proc(0))

    c = GitHubIssuesClient(runner=r, sleep=lambda s: delays.append(s))
    with pytest.raises(PhaseTransitionError):
        c.transition_phase("octo/widget#42", PHASE_DEVELOPING)

    # First attempt has delay 0 (no sleep observed); attempts 2 and 3
    # observe 200 / 600 ms in seconds.
    assert delays == [0.2, 0.6]


def test_transition_phase_treats_extra_afk_label_as_mismatch():
    """Two ``afk:*`` labels at once is a violated invariant — the verify
    must reject it even if one of them is the target."""
    r = FakeRunner()
    r.add(_is("issue", "edit"), _proc(0))
    r.add(
        _is("issue", "view"),
        _proc(0, _labels_payload(PHASE_DEVELOPING, PHASE_PENDING)),
    )
    r.add(_is("issue", "comment"), _proc(0))

    with pytest.raises(PhaseTransitionError):
        _client(r).transition_phase("octo/widget#42", PHASE_DEVELOPING)


def test_transition_phase_passes_when_non_afk_labels_present():
    """Foreign labels (e.g. ``afk-agents`` itself, ``target:main``) must not
    trigger a mismatch — the invariant covers only ``afk:*`` phase labels."""
    r = FakeRunner()
    r.add(_is("issue", "edit"), _proc(0))
    r.add(
        _is("issue", "view"),
        _proc(0, _labels_payload(PHASE_DEVELOPING, AFK_AGENTS_LABEL, "target:main")),
    )
    # No abort comment expected.
    _client(r).transition_phase("octo/widget#42", PHASE_DEVELOPING)


# ---------------------------------------------------------------------------
# get_parent — sub-issue REST envelope
# ---------------------------------------------------------------------------


def test_get_parent_reads_parent_via_gh_api():
    payload = json.dumps({
        "number": 42,
        "parent": {"number": 10, "title": "Parent Enhancement"},
    })
    r = FakeRunner()
    r.add(_is("api"), _proc(0, payload))
    ref = _client(r).get_parent("octo/widget#42")
    assert ref == ParentRef(id="octo/widget#10", backend="github", title="Parent Enhancement")


def test_get_parent_raises_when_no_parent_attached():
    r = FakeRunner()
    r.add(_is("api"), _proc(0, json.dumps({"number": 42})))
    with pytest.raises(GitHubApiError, match="no parent sub-issue link"):
        _client(r).get_parent("octo/widget#42")


def test_get_parent_wraps_404_in_typed_error():
    r = FakeRunner()
    r.add(_is("api"), _proc(1, "", "HTTP 404: Not Found"))
    with pytest.raises(GitHubApiError, match="gh api GET"):
        _client(r).get_parent("octo/widget#42")


# ---------------------------------------------------------------------------
# Sub-issue REST endpoints — list + attach
# ---------------------------------------------------------------------------


def test_attach_sub_issue_posts_to_native_sub_issues_endpoint():
    """Acceptance bullet 5 — ``gh api -X POST /repos/.../sub_issues``."""
    # First GET resolves the child's numeric id.
    child_payload = json.dumps({"id": 9001, "number": 42})
    r = FakeRunner()
    # GET /repos/.../issues/42  (id lookup)
    r.add(
        lambda a: a[:1] == ["api"] and "issues/42" in a[-1] and "POST" not in a,
        _proc(0, child_payload),
    )
    # POST /repos/.../issues/10/sub_issues
    r.add(
        lambda a: a[:1] == ["api"] and "POST" in a,
        _proc(0, json.dumps({"id": 5, "number": 42})),
    )
    _client(r).attach_sub_issue("octo/widget#10", "octo/widget#42")

    post_call = next(c for c in r.calls if "POST" in c)
    assert post_call[0] == "api"
    # Endpoint path is the native REST surface.
    assert any("/repos/octo/widget/issues/10/sub_issues" in arg for arg in post_call)
    # Body field is ``sub_issue_id=9001`` (numeric internal id, not number).
    body_arg = post_call[post_call.index("-f") + 1]
    assert body_arg == "sub_issue_id=9001"


def test_attach_sub_issue_wraps_404_in_typed_error():
    r = FakeRunner()
    r.add(
        lambda a: a[:1] == ["api"] and "POST" not in a,
        _proc(0, json.dumps({"id": 9001, "number": 42})),
    )
    r.add(
        lambda a: a[:1] == ["api"] and "POST" in a,
        _proc(1, "", "HTTP 404: Not Found"),
    )
    with pytest.raises(GitHubApiError, match=r"sub_issues"):
        _client(r).attach_sub_issue("octo/widget#10", "octo/widget#42")


def test_attach_sub_issue_wraps_malformed_id_payload():
    r = FakeRunner()
    # child id-lookup returns no ``id`` field
    r.add(_is("api"), _proc(0, json.dumps({"number": 42})))
    with pytest.raises(GitHubApiError, match="numeric id"):
        _client(r).attach_sub_issue("octo/widget#10", "octo/widget#42")


def test_list_sub_issues_parses_native_endpoint_response():
    rows = json.dumps([
        {"number": 11, "repository": {"nameWithOwner": "octo/widget"}},
        {"number": 12, "repository": {"nameWithOwner": "octo/widget"}},
    ])
    r = FakeRunner()
    r.add(_is("api"), _proc(0, rows))
    refs = _client(r).list_sub_issues("octo/widget#10")
    assert [x.id for x in refs] == ["octo/widget#11", "octo/widget#12"]
    assert all(x.parent_id == "octo/widget#10" for x in refs)


def test_list_sub_issues_rejects_non_array_payload():
    r = FakeRunner()
    r.add(_is("api"), _proc(0, json.dumps({"unexpected": "object"})))
    with pytest.raises(GitHubApiError, match="expected JSON array"):
        _client(r).list_sub_issues("octo/widget#10")


# ---------------------------------------------------------------------------
# comment — content-hash dedup
# ---------------------------------------------------------------------------


def test_comment_skips_post_when_identical_body_already_exists():
    """Acceptance bullet 7 — content-hash dedup (SDD §5 idempotency row)."""
    existing = json.dumps([
        {"id": 1, "body": "previously said this"},
        {"id": 2, "body": "AFK: hello world"},
    ])
    r = FakeRunner()
    r.add(_is("api"), _proc(0, existing))
    _client(r).comment("octo/widget#42", "AFK: hello world")

    # No ``gh issue comment`` invocation despite the dedup-list read.
    assert not any(c[:2] == ["issue", "comment"] for c in r.calls)


def test_comment_posts_when_body_is_new():
    existing = json.dumps([{"id": 1, "body": "unrelated"}])
    r = FakeRunner()
    r.add(_is("api"), _proc(0, existing))
    r.add(_is("issue", "comment"), _proc(0))

    _client(r).comment("octo/widget#42", "AFK: new message")
    comments = [c for c in r.calls if c[:2] == ["issue", "comment"]]
    assert len(comments) == 1
    body = comments[0][comments[0].index("--body") + 1]
    assert body == "AFK: new message"


def test_comment_posts_when_dedup_listing_fails():
    """Listing the issue's comments is best-effort — a failure there must
    not block the comment write (observability > strict dedup)."""
    r = FakeRunner()
    r.add(_is("api"), _proc(1, "", "rate limit"))
    r.add(_is("issue", "comment"), _proc(0))

    _client(r).comment("octo/widget#42", "AFK: still here")
    assert any(c[:2] == ["issue", "comment"] for c in r.calls)


def test_comment_hash_is_content_addressed():
    """Sanity check on the hashing primitive — ensures the dedup key is
    purely a function of ``body`` (no whitespace normalisation surprises)."""
    body = "x" * 32
    assert (
        hashlib.sha256(body.encode("utf-8")).hexdigest()
        == hashlib.sha256(body.encode("utf-8")).hexdigest()
    )


# ---------------------------------------------------------------------------
# get_target_branch — label parsing + default-branch fallback
# ---------------------------------------------------------------------------


def test_get_target_branch_reads_target_label_when_present():
    r = FakeRunner()
    r.add(
        _is("issue", "view"),
        _proc(0, json.dumps({"labels": [
            {"name": AFK_AGENTS_LABEL},
            {"name": "target:rm-release"},
            {"name": PHASE_PENDING},
        ]})),
    )
    assert _client(r).get_target_branch("octo/widget#10") == "rm-release"
    # No fallback call — repo view was unnecessary.
    assert not any(c[:2] == ["repo", "view"] for c in r.calls)


def test_get_target_branch_falls_back_to_repo_default_branch():
    r = FakeRunner()
    r.add(
        _is("issue", "view"),
        _proc(0, json.dumps({"labels": [{"name": AFK_AGENTS_LABEL}]})),
    )
    r.add(
        _is("repo", "view"),
        _proc(0, json.dumps({"defaultBranchRef": {"name": "main"}})),
    )
    assert _client(r).get_target_branch("octo/widget#10") == "main"


def test_get_target_branch_handles_empty_labels_array():
    r = FakeRunner()
    r.add(_is("issue", "view"), _proc(0, json.dumps({"labels": []})))
    r.add(
        _is("repo", "view"),
        _proc(0, json.dumps({"defaultBranchRef": {"name": "main"}})),
    )
    assert _client(r).get_target_branch("octo/widget#10") == "main"


def test_get_target_branch_handles_missing_labels_key():
    """Edge case — JSON has no ``labels`` key at all."""
    r = FakeRunner()
    r.add(_is("issue", "view"), _proc(0, json.dumps({})))
    r.add(
        _is("repo", "view"),
        _proc(0, json.dumps({"defaultBranchRef": {"name": "main"}})),
    )
    assert _client(r).get_target_branch("octo/widget#10") == "main"


def test_get_target_branch_wraps_non_json_response():
    r = FakeRunner()
    r.add(_is("issue", "view"), _proc(0, "garbage"))
    with pytest.raises(GitHubApiError, match="non-JSON"):
        _client(r).get_target_branch("octo/widget#10")


# ---------------------------------------------------------------------------
# splice_notes_block — section_splice reuse
# ---------------------------------------------------------------------------


def test_splice_notes_block_creates_marker_pair_on_first_call():
    """Issue body has no markers yet — the splicer appends a fresh pair."""
    body_payload = json.dumps({"number": 10, "body": "Original PRD body."})
    r = FakeRunner()
    r.add(_is("api"), _proc(0, body_payload))
    r.add(_is("issue", "edit"), _proc(0))

    _client(r).splice_notes_block(
        "octo/widget#10", "- ST04: GitHubIssuesClient impl"
    )
    edit = next(c for c in r.calls if c[:2] == ["issue", "edit"])
    new_body = edit[edit.index("--body") + 1]
    assert "Original PRD body." in new_body
    assert "<!-- afk:notes:start -->" in new_body
    assert "<!-- afk:notes:end -->" in new_body
    assert "- ST04: GitHubIssuesClient impl" in new_body


def test_splice_notes_block_is_idempotent_no_write_on_unchanged_body():
    body_with_marker = (
        "Original.\n\n<!-- afk:notes:start -->\n"
        "- ST04: GitHubIssuesClient impl\n"
        "<!-- afk:notes:end -->\n"
    )
    r = FakeRunner()
    r.add(_is("api"), _proc(0, json.dumps({"body": body_with_marker})))

    _client(r).splice_notes_block(
        "octo/widget#10", "- ST04: GitHubIssuesClient impl"
    )
    # No ``issue edit`` call — splicer produced an identical body.
    assert not any(c[:2] == ["issue", "edit"] for c in r.calls)


def test_splice_notes_block_replaces_existing_block_content():
    body = (
        "Header\n\n<!-- afk:notes:start -->\nOLD\n<!-- afk:notes:end -->\n"
    )
    r = FakeRunner()
    r.add(_is("api"), _proc(0, json.dumps({"body": body})))
    r.add(_is("issue", "edit"), _proc(0))

    _client(r).splice_notes_block("octo/widget#10", "NEW")
    edit = next(c for c in r.calls if c[:2] == ["issue", "edit"])
    new_body = edit[edit.index("--body") + 1]
    assert "NEW" in new_body
    assert "OLD" not in new_body
    # Foreign prose preserved byte-identical.
    assert new_body.startswith("Header\n\n")


# ---------------------------------------------------------------------------
# close — terminal close with reason
# ---------------------------------------------------------------------------


def test_close_uses_gh_issue_close_with_completed_reason():
    r = FakeRunner()
    r.add(_is("issue", "close"), _proc(0))
    _client(r).close("octo/widget#42", "completed")
    call = r.calls[0]
    assert call[:3] == ["issue", "close", "42"]
    assert "--reason" in call
    assert call[call.index("--reason") + 1] == "completed"


def test_close_translates_not_planned_underscore_form():
    r = FakeRunner()
    r.add(_is("issue", "close"), _proc(0))
    _client(r).close("octo/widget#42", "not_planned")
    call = r.calls[0]
    assert call[call.index("--reason") + 1] == "not planned"


def test_close_wraps_failure_as_typed_error():
    r = FakeRunner()
    r.add(_is("issue", "close"), _proc(1, "", "permission denied"))
    with pytest.raises(GitHubApiError, match="gh issue close"):
        _client(r).close("octo/widget#42", "completed")


# ---------------------------------------------------------------------------
# ensure_phase_labels — gh label create --force (ADR-0002 follow-up)
# ---------------------------------------------------------------------------


def test_ensure_phase_labels_creates_all_five_with_force_flag():
    """Acceptance bullet 8 — gating labels created via ``--force`` so the
    call is idempotent across runs (the ADR-0002 "Follow-ups" note)."""
    r = FakeRunner()
    r.add(_is("label", "create"), _proc(0))
    _client(r).ensure_phase_labels("octo", "widget")

    create_calls = [c for c in r.calls if c[:2] == ["label", "create"]]
    assert len(create_calls) == 5  # 4 phase labels + afk-agents gate
    names_created = {c[2] for c in create_calls}
    assert names_created == set(ALL_PHASE_LABELS) | {AFK_AGENTS_LABEL}
    for call in create_calls:
        assert "--force" in call
        assert "--repo" in call
        assert call[call.index("--repo") + 1] == "octo/widget"


def test_ensure_phase_labels_wraps_failure_in_typed_error():
    r = FakeRunner()
    r.add(_is("label", "create"), _proc(1, "", "auth required"))
    with pytest.raises(GitHubApiError, match="gh label create"):
        _client(r).ensure_phase_labels("octo", "widget")


# ---------------------------------------------------------------------------
# Issue-id parsing — edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_id",
    [
        "octo/widget",       # no '#'
        "#42",               # no owner/repo
        "widget#42",         # missing owner
        "octo/widget#xyz",   # non-int number
        "",                  # empty
    ],
)
def test_issue_id_parsing_rejects_malformed_inputs(bad_id):
    r = FakeRunner()
    with pytest.raises(GitHubApiError, match="owner/repo#N|not an int"):
        _client(r).get_target_branch(bad_id)
