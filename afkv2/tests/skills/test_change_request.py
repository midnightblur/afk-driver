"""The change request and the CI watch: the description, the background watch, the Ready gate."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
SKILL = AFKV2 / "skills" / "create-change-request"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(AFKV2 / "ports"))

import change_request  # noqa: E402
import ci_watch  # noqa: E402
from forge import cli as forge_cli  # noqa: E402
from tracker import envelope, shell  # noqa: E402


def _real(script, verb, payload, limit=300):
    """One command in a process of its own, as the skill runs it: the JSON on stdin, and the process exits."""
    done = subprocess.run([sys.executable, str(SCRIPTS / script), verb], input=json.dumps(payload).encode("utf-8"), capture_output=True, timeout=limit)
    return json.loads(done.stdout)


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def commit(cwd, name, text, message="change"):
    (Path(cwd) / name).write_text(text, encoding="utf-8")
    git(cwd, "add", name)
    git(cwd, "-c", "user.name=t", "-c", "user.email=t@t.test", "-c", "commit.gpgsign=false", "commit", "-qm", message)
    return git(cwd, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A real git repository as the working directory, with a remote that holds `main`."""
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    git(work, "remote", "add", "origin", str(remote))
    commit(work, "a.txt", "one\n")
    git(work, "push", "-q", "origin", "main")
    git(work, "switch", "-qc", "feat/x")
    monkeypatch.chdir(work)
    return work


class Forge:
    """Stands in for the forge command: records each call and answers by verb."""

    def __init__(self):
        self.calls = []
        self.limits = []
        self.answers = {}

    def __call__(self, verb, payload, limit=None):
        self.calls.append((verb, payload))
        self.limits.append(limit)
        answer = self.answers.get(verb, {"ok": True})
        if isinstance(answer, list):
            answer = answer.pop(0)
        return answer(payload) if callable(answer) else answer

    def verbs(self):
        return [verb for verb, _ in self.calls]


@pytest.fixture
def forge(monkeypatch):
    fake = Forge()
    monkeypatch.setattr(ci_watch, "call_forge", fake)
    monkeypatch.setattr(change_request, "call_forge", fake)
    monkeypatch.setattr(ci_watch, "HEAD_GRACE", 0)
    return fake


def run(module, capsys, verb, **payload):
    capsys.readouterr()
    code = module.main([verb, json.dumps(payload)])
    return code, json.loads(capsys.readouterr().out)


def refused(module, capsys, verb, **payload):
    code, answer = run(module, capsys, verb, **payload)
    assert code == 1 and answer["ok"] is False, answer
    return answer["error"]


def unreadable(module, capsys, verb, **payload):
    code, answer = run(module, capsys, verb, **payload)
    assert code == 2 and answer["error"]["code"] == "bad-payload", answer
    return answer["error"]


PARTS = {
    "title": "Add the widget",
    "target": "main",
    "description": "Adds the widget export.",
    "requests": [{"person": "ana", "role": "assignee", "request": "merge after the demo"},
                 {"person": "bo", "role": "reviewer", "request": "read the retry loop in export.py"}],
    "proofs": [{"claim": "the export works", "evidence": "pytest tests/test_export.py: 12 passed"}],
    "mergeability": "The target is merged in and the merge has no conflict.",
    "self_critique": "The retry loop has no test for a slow server.",
}


def parts(**changes):
    return {**PARTS, **changes}


def without(key):
    return {name: value for name, value in PARTS.items() if name != key}


# --- the description


def test_the_body_holds_every_part_in_its_own_section():
    assert change_request.build_body(PARTS) == """## What changes

Adds the widget export.

## Requests

- @ana (assignee): merge after the demo
- @bo (reviewer): read the retry loop in export.py

## Proofs

- the export works: pytest tests/test_export.py: 12 passed

## Why it can merge

The target is merged in and the merge has no conflict.

## Self-critique

The retry loop has no test for a slow server.
"""


@pytest.mark.parametrize("missing", ["description", "requests", "proofs", "mergeability", "self_critique"])
def test_a_missing_part_stops_the_open_and_nothing_reaches_the_forge(repo, forge, capsys, missing):
    error = unreadable(change_request, capsys, "open", **without(missing))
    assert missing in error["reason"] and forge.calls == []


@pytest.mark.parametrize(("key", "value"), [
    ("description", "   "), ("requests", []), ("proofs", []), ("mergeability", ""), ("self_critique", " "),
    ("requests", "ana"), ("proofs", "it works"),
])
def test_a_blank_or_empty_part_stops_the_open(repo, forge, capsys, key, value):
    error = unreadable(change_request, capsys, "open", **parts(**{key: value}))
    assert key in error["reason"] and forge.calls == []


def test_the_self_critique_is_one_text_not_a_list(repo, forge, capsys):
    error = unreadable(change_request, capsys, "open", **parts(self_critique=["one", "two"]))
    assert "self_critique" in error["reason"]


def test_two_requests_to_one_person_stop_the_open(repo, forge, capsys):
    twice = [{"person": "ana", "role": "assignee", "request": "merge"}, {"person": "ANA", "role": "reviewer", "request": "read"}]
    error = unreadable(change_request, capsys, "open", **parts(requests=twice))
    assert "ana" in error["reason"].lower() and "one request" in error["reason"]


@pytest.mark.parametrize("entry", [
    {"role": "reviewer", "request": "read"},
    {"person": "bo", "request": "read"},
    {"person": "bo", "role": "reviewer"},
    {"person": "bo", "role": "owner", "request": "read"},
    {"person": "@bo", "role": "reviewer", "request": "read"},
    {"person": "--bo", "role": "reviewer", "request": "read"},
    {"person": "bo", "role": "reviewer", "request": "  "},
    "bo",
])
def test_a_request_that_is_not_whole_stops_the_open(repo, forge, capsys, entry):
    error = unreadable(change_request, capsys, "open", **parts(requests=[entry]))
    assert "requests" in error["reason"] and forge.calls == []


@pytest.mark.parametrize("proof", [{"claim": "x"}, {"evidence": "y"}, {"claim": " ", "evidence": "y"}, "x"])
def test_a_proof_with_no_evidence_stops_the_open(repo, forge, capsys, proof):
    error = unreadable(change_request, capsys, "open", **parts(proofs=[proof]))
    assert "proofs" in error["reason"] and forge.calls == []


# --- open: create or update, one change per branch


VIEW = {"ok": True, "id": "7", "url": "https://f.test/7", "state": "opened", "draft": True, "head_sha": "abc"}
NOT_FOUND = {"ok": False, "error": {"code": "not-found", "reason": "no pull requests found"}}


def test_open_creates_a_draft_with_the_people_when_the_branch_has_no_change(repo, forge, capsys):
    forge.answers = {"change-view": [NOT_FOUND, VIEW], "change-create-draft": {"ok": True, "id": "7", "url": "https://f.test/7", "draft": True}}
    code, answer = run(change_request, capsys, "open", **PARTS)
    assert code == 0 and answer["created"] is True and answer["draft"] is True and answer["id"] == "7"
    assert forge.verbs() == ["change-view", "change-create-draft", "change-view"]
    assert forge.calls[0][1]["id"] == "feat/x"
    sent = forge.calls[1][1]
    assert sent["title"] == "Add the widget" and sent["target"] == "main" and sent["source"] == "feat/x"
    assert sent["assignee"] == ["ana"] and sent["reviewer"] == ["bo"]
    assert sent["body"] == change_request.build_body(PARTS)


def test_open_refuses_a_change_that_did_not_open_as_draft(repo, forge, capsys):
    forge.answers = {"change-view": [NOT_FOUND, {**VIEW, "draft": False}], "change-create-draft": {"ok": True, "id": "7", "url": "u", "draft": True}}
    assert refused(change_request, capsys, "open", **PARTS)["code"] == "not-draft"


@pytest.mark.parametrize("missing", ["title", "target"])
def test_a_new_change_needs_a_title_and_a_target(repo, forge, capsys, missing):
    forge.answers = {"change-view": NOT_FOUND}
    error = unreadable(change_request, capsys, "open", **without(missing))
    assert missing in error["reason"] and "change-create-draft" not in forge.verbs()


def test_open_takes_a_target_with_the_remote_name(repo, forge, capsys):
    forge.answers = {"change-view": [NOT_FOUND, VIEW], "change-create-draft": {"ok": True, "id": "7", "url": "u", "draft": True}}
    run(change_request, capsys, "open", **parts(target="origin/main"))
    assert forge.calls[1][1]["target"] == "main"


def test_open_updates_the_one_open_change_of_the_branch(repo, forge, capsys):
    forge.answers = {"change-view": VIEW, "change-update-body": {"ok": True, "id": "7", "was_draft": "true", "draft_restored": False}}
    code, answer = run(change_request, capsys, "open", **PARTS)
    assert code == 0 and answer["created"] is False and answer["id"] == "7" and answer["url"] == VIEW["url"]
    assert forge.verbs() == ["change-view", "change-update-body"]
    assert forge.calls[1][1] == {"id": "7", "body": change_request.build_body(PARTS)}


def test_open_with_an_id_updates_that_change(repo, forge, capsys):
    forge.answers = {"change-view": VIEW, "change-update-body": {"ok": True, "id": "7"}}
    code, answer = run(change_request, capsys, "open", id="7", **PARTS)
    assert code == 0 and answer["created"] is False and forge.calls[0][1]["id"] == "7"


def test_open_with_an_id_of_a_closed_change_refuses(repo, forge, capsys):
    forge.answers = {"change-view": {**VIEW, "state": "merged"}}
    assert refused(change_request, capsys, "open", id="7", **PARTS)["code"] == "change-not-open"
    assert forge.verbs() == ["change-view"]


def test_a_merged_change_on_the_branch_gets_a_new_change(repo, forge, capsys):
    forge.answers = {"change-view": [{**VIEW, "id": "3", "state": "merged"}, VIEW],
                     "change-create-draft": {"ok": True, "id": "7", "url": "u", "draft": True}}
    code, answer = run(change_request, capsys, "open", **PARTS)
    assert code == 0 and answer["created"] is True and answer["id"] == "7"


def test_a_failed_lookup_creates_nothing(repo, forge, capsys):
    forge.answers = {"change-view": {"ok": False, "error": {"code": "auth", "reason": "not logged in"}}}
    assert refused(change_request, capsys, "open", **PARTS)["code"] == "auth"
    assert "change-create-draft" not in forge.verbs()


def test_a_lost_draft_flag_on_update_stays_a_refusal(repo, forge, capsys):
    forge.answers = {"change-view": VIEW, "change-update-body": {"ok": False, "error": {"code": "draft-lost", "reason": "run glab"}}}
    assert refused(change_request, capsys, "open", **PARTS)["code"] == "draft-lost"


def test_open_on_a_detached_head_needs_an_id(repo, forge, capsys):
    git(repo, "checkout", "-q", "--detach")
    assert refused(change_request, capsys, "open", **PARTS)["code"] == "no-branch"
    assert forge.calls == []


def test_open_on_a_detached_head_takes_a_source(repo, forge, capsys):
    git(repo, "checkout", "-q", "--detach")
    forge.answers = {"change-view": [NOT_FOUND, VIEW], "change-create-draft": {"ok": True, "id": "7", "url": "u", "draft": True}}
    code, answer = run(change_request, capsys, "open", source="feat/x", **PARTS)
    assert code == 0 and answer["created"] is True
    assert forge.calls[0][1]["id"] == "feat/x" and forge.calls[1][1]["source"] == "feat/x"


def test_a_source_that_is_no_branch_name_reaches_no_forge(repo, forge, capsys):
    unreadable(change_request, capsys, "open", source="--x", **PARTS)
    assert forge.calls == []


def test_a_blank_title_creates_nothing(repo, forge, capsys):
    forge.answers = {"change-view": NOT_FOUND}
    assert "title" in unreadable(change_request, capsys, "open", **parts(title="  "))["reason"]
    assert "change-create-draft" not in forge.verbs()


def test_open_refuses_another_target_than_the_open_change_has(repo, forge, capsys):
    forge.answers = {"change-view": {**VIEW, "target": "develop"}}
    error = refused(change_request, capsys, "open", **PARTS)
    assert error["code"] == "target-differs" and error["target"] == "develop"
    assert forge.verbs() == ["change-view"]


def test_open_takes_the_target_of_the_open_change(repo, forge, capsys):
    forge.answers = {"change-view": {**VIEW, "target": "main"}, "change-update-body": {"ok": True, "id": "7"}}
    assert run(change_request, capsys, "open", **parts(target="origin/main"))[0] == 0


def test_the_forge_and_repo_values_reach_every_call(repo, forge, capsys):
    forge.answers = {"change-view": [NOT_FOUND, VIEW], "change-create-draft": {"ok": True, "id": "7", "url": "u", "draft": True}}
    run(change_request, capsys, "open", forge="gitlab", repo="acme/widget", **PARTS)
    assert all(sent["forge"] == "gitlab" and sent["repo"] == "acme/widget" for _, sent in forge.calls)


# --- merge facts on real git


def test_merge_facts_of_a_branch_with_no_conflict(repo, capsys):
    commit(repo, "b.txt", "two\n")
    code, answer = run(change_request, capsys, "merge-facts", target="main")
    assert code == 0 and answer["clean"] is True and answer["conflicts"] == []
    assert answer["ahead"] == 1 and answer["behind"] == 0 and answer["fetched"] is True
    assert answer["target"] == "origin/main"


def test_merge_facts_name_each_file_in_conflict(repo, capsys):
    commit(repo, "a.txt", "branch\n")
    git(repo, "switch", "-q", "main")
    commit(repo, "a.txt", "target\n")
    git(repo, "push", "-q", "origin", "main")
    git(repo, "switch", "-q", "feat/x")
    code, answer = run(change_request, capsys, "merge-facts", target="origin/main")
    assert code == 0 and answer["clean"] is False and answer["conflicts"] == ["a.txt"]
    assert answer["behind"] == 1 and answer["ahead"] == 1


def test_merge_facts_say_when_the_fetch_failed(repo, capsys):
    git(repo, "remote", "set-url", "origin", str(repo / "no-such-remote"))
    git(repo, "update-ref", "refs/remotes/origin/main", git(repo, "rev-parse", "main"))
    code, answer = run(change_request, capsys, "merge-facts", target="main")
    assert code == 0 and answer["fetched"] is False and answer["clean"] is True


def test_merge_facts_see_a_target_commit_only_the_remote_holds(repo, tmp_path, capsys):
    commit(repo, "a.txt", "branch\n")
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", "-b", "main", str(tmp_path / "remote.git"), str(other))
    commit(other, "a.txt", "target\n")
    git(other, "push", "-q", "origin", "main")
    code, answer = run(change_request, capsys, "merge-facts", target="main")
    assert code == 0 and answer["fetched"] is True
    assert answer["behind"] == 1 and answer["conflicts"] == ["a.txt"]


def test_merge_facts_move_the_tracking_ref_in_a_clone_that_does_not_track_the_target(repo, tmp_path, capsys):
    git(repo, "config", "remote.origin.fetch", "+refs/heads/feat/x:refs/remotes/origin/feat/x")
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", "-b", "main", str(tmp_path / "remote.git"), str(other))
    commit(other, "c.txt", "new\n")
    git(other, "push", "-q", "origin", "main")
    code, answer = run(change_request, capsys, "merge-facts", target="main")
    assert code == 0 and answer["fetched"] is True and answer["behind"] == 1


def test_merge_facts_read_a_target_that_only_this_clone_holds(repo, capsys):
    git(repo, "branch", "only-here")
    commit(repo, "b.txt", "two\n")
    code, answer = run(change_request, capsys, "merge-facts", target="only-here")
    assert code == 0 and answer["target"] == "only-here" and answer["fetched"] is False and answer["ahead"] == 1


def test_a_fetch_past_its_limit_gives_the_facts_of_the_last_fetch(repo, capsys, monkeypatch):
    real_run = shell.run_tool

    def slow_fetch(tool, args, **options):
        if args[0] == "fetch":
            raise ci_watch.Refusal("timeout", "`git fetch` ran past 120 s")
        return real_run(tool, args, **options)
    monkeypatch.setattr(shell, "run_tool", slow_fetch)
    code, answer = run(change_request, capsys, "merge-facts", target="main")
    assert code == 0 and answer["fetched"] is False and answer["clean"] is True


def test_merge_facts_refuse_a_target_that_does_not_exist(repo, capsys):
    assert refused(change_request, capsys, "merge-facts", target="no-such-branch")["code"] == "no-target"


@pytest.mark.parametrize("target", ["--upload-pack=x", "-x", "a b", "a..b", ""])
def test_merge_facts_refuse_a_target_that_is_no_branch_name(repo, capsys, target):
    unreadable(change_request, capsys, "merge-facts", target=target)


# --- the watch


def record_of(repo, change="7"):
    return json.loads((Path(git(repo, "rev-parse", "--absolute-git-dir")) / "afkv2-ci" / f"{change}.json").read_text(encoding="utf-8"))


GREEN = {"ok": True, "status": "success", "elapsed": 0, "id": "7"}
RED = {"ok": True, "status": "failed", "elapsed": 0, "id": "7"}
STILL = {"ok": True, "status": "running", "elapsed": 600, "id": "7", "reason": "budget exhausted; the checks keep running"}


def test_watch_writes_the_final_status_and_its_commit_to_the_record(repo, forge, capsys):
    head = git(repo, "rev-parse", "HEAD")
    forge.answers = {"ci-wait": GREEN, "change-view": {**VIEW, "head_sha": head}}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["state"] == "finished" and answer["status"] == "success"
    assert answer["head_sha"] == head and answer["current_head"] is True
    assert record_of(repo)["status"] == "success"


def test_the_result_of_the_last_commit_is_no_result_for_the_new_commit(repo, forge, capsys, monkeypatch):
    head = git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(ci_watch, "HEAD_GRACE", 60)
    monkeypatch.setattr(ci_watch, "HEAD_PAUSE", 0)
    forge.answers = {"ci-wait": [RED, GREEN], "change-view": [{**VIEW, "head_sha": "last"}, {**VIEW, "head_sha": head}, {**VIEW, "head_sha": head}]}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["status"] == "success" and answer["head_sha"] == head and answer["current_head"] is True
    assert forge.verbs().count("ci-wait") == 2


def test_a_status_read_before_the_forge_showed_the_commit_is_no_result(repo, forge, capsys, monkeypatch):
    head = git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(ci_watch, "HEAD_GRACE", 60)
    monkeypatch.setattr(ci_watch, "HEAD_PAUSE", 0)
    shown = {"head": "last"}

    def status_then_the_forge_moves(_payload):
        answer = RED if shown["head"] == "last" else GREEN
        shown["head"] = head
        return answer

    forge.answers = {"ci-wait": status_then_the_forge_moves, "change-view": lambda _payload: {**VIEW, "head_sha": shown["head"]}}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["status"] == "success" and answer["current_head"] is True
    assert forge.verbs().count("ci-wait") == 2


def test_a_start_during_the_pause_keeps_its_record(repo, forge, capsys, monkeypatch):
    monkeypatch.setattr(ci_watch, "HEAD_GRACE", 60)
    path = ci_watch._record_path("7")
    newer = {}

    def a_newer_start(_seconds):
        newer.update(ci_watch._new_record(path, "7", "newer"))

    monkeypatch.setattr(ci_watch.time, "sleep", a_newer_start)
    forge.answers = {"ci-wait": RED, "change-view": {**VIEW, "head_sha": "other"}}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["state"] == "superseded"
    record = ci_watch._read_record(path)
    assert record["token"] == newer["token"] and record["head_sha"] == "newer" and record["state"] == "watching"


def test_a_forge_that_keeps_another_commit_ends_with_that_commit(repo, forge, capsys, monkeypatch):
    monkeypatch.setattr(ci_watch, "HEAD_GRACE", 0.2)
    monkeypatch.setattr(ci_watch, "HEAD_PAUSE", 0.05)
    forge.answers = {"ci-wait": RED, "change-view": {**VIEW, "head_sha": "other"}}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["state"] == "finished" and answer["status"] == "failed"
    assert answer["head_sha"] == "other" and answer["current_head"] is False


def test_a_failed_head_read_ends_the_wait_for_the_new_commit(repo, forge, capsys, monkeypatch):
    monkeypatch.setattr(ci_watch, "HEAD_GRACE", 60)
    forge.answers = {"ci-wait": RED, "change-view": {"ok": False, "error": {"code": "auth", "reason": "no"}}}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["status"] == "failed" and forge.verbs().count("ci-wait") == 1


def test_a_red_ci_is_a_report_and_no_refusal(repo, forge, capsys):
    forge.answers = {"ci-wait": RED, "change-view": VIEW}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["status"] == "failed" and answer["state"] == "finished"


def test_the_watch_reads_again_until_the_status_is_final(repo, forge, capsys):
    forge.answers = {"ci-wait": [STILL, STILL, GREEN], "change-view": VIEW}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["status"] == "success" and forge.verbs().count("ci-wait") == 3


def test_each_read_of_the_watch_has_its_slice_and_a_longer_limit(repo, forge, capsys):
    forge.answers = {"ci-wait": [STILL, GREEN], "change-view": VIEW}
    run(ci_watch, capsys, "watch", id="7")
    reads = [(sent["budget"], limit) for (verb, sent), limit in zip(forge.calls, forge.limits) if verb == "ci-wait"]
    assert [budget for budget, _ in reads] == [ci_watch.SLICE] * 2
    assert all(limit >= budget + 60 for budget, limit in reads)
    assert ci_watch.LOST_AFTER > ci_watch.SLICE + ci_watch.READ_MARGIN


def test_the_read_of_a_short_budget_ends_with_the_budget(repo, forge, capsys):
    forge.answers = {"ci-wait": GREEN, "change-view": VIEW}
    run(ci_watch, capsys, "watch", id="7", budget=100)
    first = forge.verbs().index("ci-wait")
    (_, sent), limit = forge.calls[first], forge.limits[first]
    assert 99 <= sent["budget"] <= 100 and limit == sent["budget"] + ci_watch.READ_MARGIN


def test_each_running_answer_gives_the_record_a_new_beat(repo, forge, capsys):
    path = ci_watch._record_path("7")
    beats = []

    def read_and_age(_payload):
        record = json.loads(path.read_text(encoding="utf-8"))
        beats.append(record["beat_at"])
        path.write_text(json.dumps({**record, "beat_at": 1.0}), encoding="utf-8")
        return STILL if len(beats) == 1 else GREEN
    forge.answers = {"ci-wait": read_and_age, "change-view": VIEW}
    run(ci_watch, capsys, "watch", id="7")
    assert beats[1] > 1.0


def test_a_watch_that_ends_its_budget_reports_no_verdict(repo, forge, capsys):
    forge.answers = {"ci-wait": STILL, "change-view": VIEW}
    code, answer = run(ci_watch, capsys, "watch", id="7", budget=0)
    assert code == 0 and answer["state"] == "no-verdict" and answer["status"] == "running"
    assert "budget" in answer["reason"]
    assert forge.verbs().count("ci-wait") == 1


def test_a_watch_that_cannot_read_ci_reports_no_verdict(repo, forge, capsys):
    forge.answers = {"ci-wait": {"ok": False, "error": {"code": "unreadable", "reason": "no status"}}, "change-view": VIEW}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["state"] == "no-verdict" and answer["status"] == ""
    assert "no status" in answer["reason"]


def test_a_failed_head_read_keeps_the_commit_the_watch_started_on(repo, forge, capsys):
    head = git(repo, "rev-parse", "HEAD")
    forge.answers = {"ci-wait": GREEN, "change-view": {"ok": False, "error": {"code": "auth", "reason": "no"}}}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["status"] == "success" and answer["head_sha"] == head


def test_a_newer_watch_takes_over_and_the_older_one_writes_nothing(repo, forge, capsys):
    def newer_starts(_payload):
        ci_watch._new_record(ci_watch._record_path("7"), "7", "newhead")
        return GREEN
    forge.answers = {"ci-wait": newer_starts, "change-view": VIEW}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["state"] == "superseded"
    record = record_of(repo)
    assert record["state"] == "watching" and record["head_sha"] == "newhead"


def test_a_superseded_watch_stops_before_its_next_read(repo, forge, capsys):
    def newer_starts(_payload):
        ci_watch._new_record(ci_watch._record_path("7"), "7", "newhead")
        return STILL
    forge.answers = {"ci-wait": newer_starts}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert answer["state"] == "superseded" and forge.verbs().count("ci-wait") == 1


def test_a_newer_watch_during_the_last_head_read_keeps_its_record(repo, forge, capsys):
    def newer_starts(_payload):
        ci_watch._new_record(ci_watch._record_path("7"), "7", "newhead")
        return VIEW
    forge.answers = {"ci-wait": GREEN, "change-view": newer_starts}
    code, answer = run(ci_watch, capsys, "watch", id="7")
    assert code == 0 and answer["state"] == "superseded"
    assert record_of(repo)["state"] == "watching" and record_of(repo)["head_sha"] == "newhead"


@pytest.mark.parametrize("has_record", [True, False])
def test_a_child_with_an_old_token_reads_nothing(repo, forge, capsys, has_record):
    if has_record:
        ci_watch._new_record(ci_watch._record_path("7"), "7", "newhead")
    code, answer = run(ci_watch, capsys, "watch", id="7", token="old")
    assert code == 0 and answer["state"] == "superseded" and forge.calls == []


def test_a_file_error_clears_with_a_retry(monkeypatch):
    monkeypatch.setattr(ci_watch, "FILE_PAUSE", 0)
    answers = [PermissionError("busy"), "done"]

    def action():
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer
    assert ci_watch._with_retries(action) == "done"


def test_a_file_error_that_stays_ends_its_tries(monkeypatch):
    monkeypatch.setattr(ci_watch, "FILE_PAUSE", 0)
    tries = []

    def action():
        tries.append(1)
        raise PermissionError("busy")
    with pytest.raises(PermissionError):
        ci_watch._with_retries(action)
    assert len(tries) == ci_watch.FILE_TRIES


def test_a_record_that_stays_locked_reads_as_broken(repo, monkeypatch):
    monkeypatch.setattr(ci_watch, "FILE_PAUSE", 0)
    path = ci_watch._record_path("7")
    ci_watch._new_record(path, "7", "abc")

    def locked(_self, **_options):
        raise PermissionError("busy")
    monkeypatch.setattr(Path, "read_text", locked)
    with pytest.raises(ci_watch.Refusal) as refusal:
        ci_watch._read_record(path)
    assert refusal.value.code == "bad-record"


def test_status_with_no_watch_says_none(repo, capsys):
    code, answer = run(ci_watch, capsys, "status", id="7")
    assert code == 0 and answer["state"] == "none" and answer["status"] == ""


def test_status_reports_a_finished_watch_of_an_older_commit(repo, forge, capsys):
    head = git(repo, "rev-parse", "HEAD")
    forge.answers = {"ci-wait": RED, "change-view": {**VIEW, "head_sha": head}}
    run(ci_watch, capsys, "watch", id="7")
    assert run(ci_watch, capsys, "status", id="7")[1]["current_head"] is True
    commit(repo, "b.txt", "two\n")
    code, answer = run(ci_watch, capsys, "status", id="7")
    assert code == 0 and answer["status"] == "failed" and answer["current_head"] is False


def _record_with_a_beat(seconds_ago):
    path = ci_watch._record_path("7")
    ci_watch._new_record(path, "7", "abc")
    record = json.loads(path.read_text(encoding="utf-8"))
    record["beat_at"] = time.time() - seconds_ago
    path.write_text(json.dumps(record), encoding="utf-8")


def test_status_reads_a_silent_watch_as_lost(repo, capsys):
    _record_with_a_beat(ci_watch.LOST_AFTER + 1)
    code, answer = run(ci_watch, capsys, "status", id="7")
    assert code == 0 and answer["state"] == "lost" and "start" in answer["reason"]


def test_status_reads_a_watch_just_inside_the_limit_as_watching(repo, capsys):
    _record_with_a_beat(ci_watch.LOST_AFTER - 60)
    assert run(ci_watch, capsys, "status", id="7")[1]["state"] == "watching"


def test_status_reads_a_broken_record_as_a_refusal(repo, capsys):
    path = ci_watch._record_path("7")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", encoding="utf-8")
    assert refused(ci_watch, capsys, "status", id="7")["code"] == "bad-record"


@pytest.mark.parametrize("broken", ["{broken", '{"token": "a"}', "[]", '{"token": "a", "state": "watching", "beat_at": null}'])
def test_start_on_a_broken_record_reports_it_and_starts_the_watch(repo, capsys, monkeypatch, broken):
    path = ci_watch._record_path("7")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(broken, encoding="utf-8")
    monkeypatch.setattr(ci_watch, "_spawn", lambda payload: None)
    code, answer = run(ci_watch, capsys, "start", id="7")
    assert code == 0 and answer["state"] == "watching" and answer["previous"]["state"] == "bad-record"
    assert run(ci_watch, capsys, "status", id="7")[1]["state"] == "watching"


def test_outside_a_repository_the_watch_refuses(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert refused(ci_watch, capsys, "status", id="7")["code"] == "no-repository"


@pytest.mark.parametrize(("verb", "payload"), [("status", {}), ("watch", {}), ("start", {}), ("status", {"id": "--repo=x"}),
                                               ("watch", {"id": "7", "budget": "soon"})])
def test_a_watch_payload_that_is_not_usable_exits_2(repo, forge, capsys, verb, payload):
    unreadable(ci_watch, capsys, verb, **payload)


def test_a_change_url_gets_one_record_file(repo, capsys):
    path = ci_watch._record_path("https://f.test/a/pull/7")
    assert path.parent == ci_watch._record_path("7").parent
    assert path.name == "https___f.test_a_pull_7.json"


# --- the background start: a real child process, the real forge port, and a .cmd stub of gh on PATH


@pytest.fixture
def child_forge(repo, tmp_path, monkeypatch):
    """A gh stub whose checks run until the test writes the release file."""
    release = tmp_path / "release"
    tools = tmp_path / "tools"
    tools.mkdir()
    stub = tools / "gh_stub.py"
    stub.write_text(f"""
import json, os
done = os.path.exists({str(release)!r})
print(json.dumps({{"number": 7, "state": "OPEN", "headRefOid": {git(repo, "rev-parse", "HEAD")!r},
                   "statusCheckRollup": [{{"conclusion": "FAILURE"}} if done else {{"status": "IN_PROGRESS"}}]}}))
""", encoding="utf-8")
    if os.name == "nt":
        (tools / "gh.cmd").write_text(f'@"{sys.executable}" "{stub}" %*\n', encoding="utf-8")
    else:
        launcher = tools / "gh"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{stub}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    monkeypatch.setenv("PATH", str(tools) + os.pathsep + os.environ["PATH"])
    yield release
    release.write_text("end the child", encoding="utf-8")


def wait_for(check, limit=30):
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.05)
    return False


def test_start_returns_while_ci_runs_and_the_watch_outlives_the_command(repo, child_forge, capsys):
    started = _real("ci_watch.py", "start", {"id": "7", "forge": "github", "interval": 1, "budget": 60}, limit=20)
    assert started["ok"] and started["state"] == "watching"
    assert run(ci_watch, capsys, "status", id="7")[1]["state"] == "watching"
    child_forge.write_text("go", encoding="utf-8")
    path = ci_watch._record_path("7")
    assert wait_for(lambda: ci_watch._read_record(path)["state"] == "finished"), record_of(repo)
    code, answer = run(ci_watch, capsys, "status", id="7")
    assert code == 0 and answer["status"] == "failed" and answer["head_sha"] == git(repo, "rev-parse", "HEAD")


def test_start_reports_what_the_last_watch_found(repo, forge, capsys, monkeypatch):
    forge.answers = {"ci-wait": RED, "change-view": VIEW}
    run(ci_watch, capsys, "watch", id="7")
    monkeypatch.setattr(ci_watch, "_spawn", lambda payload: None)
    code, answer = run(ci_watch, capsys, "start", id="7")
    assert code == 0 and answer["previous"]["status"] == "failed" and answer["state"] == "watching"
    assert set(answer) == {"ok", "id", "state", "previous"}


def test_start_passes_the_forge_values_and_its_token_to_the_child(repo, capsys, monkeypatch):
    seen = []
    monkeypatch.setattr(ci_watch, "_spawn", seen.append)
    run(ci_watch, capsys, "start", id="7", forge="gitlab", repo="acme/w", budget=60, interval=5)
    child = seen[0]
    assert child["forge"] == "gitlab" and child["repo"] == "acme/w" and child["budget"] == 60 and child["interval"] == 5
    assert child["token"] == record_of(repo)["token"]


def test_a_child_that_did_not_start_is_a_refusal_and_the_record_says_so(repo, capsys, monkeypatch):
    def no_process(_payload):
        raise OSError("no process")
    monkeypatch.setattr(ci_watch, "_spawn", no_process)
    assert refused(ci_watch, capsys, "start", id="7")["code"] == "watch-not-started"
    assert record_of(repo)["state"] == "no-verdict"


# --- the Ready gate


SETTLED = {"ok": True, "stopped_by": "clean", "change": "7", "left": {"blocking": [], "posted": [], "not_posted": []}}
ORIGINAL_CALL_REVIEW = ci_watch.call_review


@pytest.fixture
def ship(repo, tmp_path, forge, monkeypatch):
    """A plan folder with 2 subtasks, both reviews settled, CI green and the change at the local head."""
    plan = tmp_path / "plan"
    plan.mkdir()
    for name in ("PLAN.md", "JOURNAL.md", "DECISIONS.md", "0001-a.md", "0002-b.md"):
        (plan / name).write_text("x", encoding="utf-8")
    forge.answers = {"change-view": {**VIEW, "head_sha": git(repo, "rev-parse", "HEAD")},
                     "ci-status": {"ok": True, "status": "success", "url": "https://f.test/ci"},
                     "change-ready": {"ok": True, "id": "7", "draft": False}}
    reviews = {"0001-a": SETTLED, "0002-b": SETTLED}
    monkeypatch.setattr(ci_watch, "call_review", lambda _plan, subtask: reviews[subtask])
    ship = {"plan": plan, "reviews": reviews, "forge": forge}
    return ship


def mark(ship, capsys):
    return run(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))


def test_a_finished_review_with_a_posted_finding_allows_ready(ship, capsys):
    ship["reviews"]["0002-b"] = {**SETTLED, "left": {"blocking": [], "posted": [{"id": "f3"}], "not_posted": []}}
    code, answer = mark(ship, capsys)
    assert code == 0 and answer["marked"] is True


def test_settled_review_and_green_ci_mark_the_change_ready(ship, capsys):
    code, answer = mark(ship, capsys)
    assert code == 0 and answer["marked"] is True and answer["draft"] is False
    assert ship["forge"].verbs()[-1] == "change-ready"


@pytest.mark.parametrize(("status", "code"), [("failed", "ci-red"), ("canceled", "ci-red"), ("running", "ci-running"), ("", "ci-none")])
def test_ready_is_refused_unless_ci_is_green(ship, capsys, status, code):
    ship["forge"].answers["ci-status"] = {"ok": True, "status": status, "url": "https://f.test/ci"}
    error = refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))
    assert error["code"] == code and error["status"] == status and error["url"] == "https://f.test/ci"
    assert "change-ready" not in ship["forge"].verbs()


def test_ready_is_refused_when_the_ci_read_fails(ship, capsys):
    ship["forge"].answers["ci-status"] = {"ok": False, "error": {"code": "auth", "reason": "no login"}}
    assert refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))["code"] == "auth"
    assert "change-ready" not in ship["forge"].verbs()


@pytest.mark.parametrize(("review", "named", "next_step"), [
    ({"ok": False, "error": {"code": "no-review", "reason": "no review has started"}}, "no review", "run-review"),
    ({"ok": False, "error": {"code": "review-owed", "reason": "a fix waits"}}, "a fix waits", "run-review"),
    ({"ok": False, "error": {"code": "fix-open", "reason": "no outcome"}}, "no outcome", "run-review"),
    ({"ok": False, "error": {"code": "round-open", "reason": "no findings yet"}}, "no findings", "run-review"),
    ({"ok": False, "error": {"code": "command-failed", "reason": "no answer"}}, "no answer", "mark-again"),
    ({"ok": False, "error": {"code": "bad-state", "reason": "no state"}}, "no state", "developer"),
    ({**SETTLED, "stopped_by": "unfixed", "left": {"blocking": [{"id": "f1"}], "posted": [], "not_posted": []}}, "f1", "developer"),
    ({**SETTLED, "left": {"blocking": [], "posted": [], "not_posted": [{"id": "f2"}]}}, "f2", "mark-again"),
    ({**SETTLED, "change": "9"}, "9", "developer"),
    ({"ok": True}, "report", "developer"),
])
def test_ready_is_refused_while_a_review_is_open(ship, capsys, review, named, next_step):
    ship["reviews"]["0002-b"] = review
    error = refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))
    assert error["code"] == "review-open"
    assert [entry["subtask"] for entry in error["reviews"]] == ["0002-b"]
    assert named in error["reviews"][0]["why"] and error["reviews"][0]["next"] == next_step
    assert "ci-status" not in ship["forge"].verbs() and "change-ready" not in ship["forge"].verbs()


@pytest.mark.parametrize("changes", [{"state": "merged"}, {"head_sha": "another"}])
def test_a_gate_refused_on_the_change_or_the_head_stops_no_review(ship, capsys, monkeypatch, changes):
    ship["forge"].answers["change-view"] = {**ship["forge"].answers["change-view"], **changes}
    finished = []
    monkeypatch.setattr(ci_watch, "call_review", lambda _plan, subtask: finished.append(subtask))
    refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))
    assert finished == []


def test_the_change_is_read_before_and_after_the_reviews_and_ci_last(ship, capsys, monkeypatch):
    order = []
    view = ship["forge"].answers["change-view"]
    monkeypatch.setattr(ci_watch, "call_review", lambda _plan, subtask: order.append("review") or SETTLED)
    ship["forge"].answers["ci-status"] = lambda _payload: order.append("ci") or {"ok": True, "status": "success", "url": "u"}
    ship["forge"].answers["change-view"] = lambda _payload: order.append("view") or view
    mark(ship, capsys)
    assert order == ["view", "review", "review", "view", "ci"] and ship["forge"].verbs()[-1] == "change-ready"


def test_a_push_during_the_reviews_refuses_the_mark(ship, repo, capsys, monkeypatch):
    def push_during_the_review(_plan, subtask):
        commit(repo, f"{subtask}.txt", "late\n")
        return SETTLED
    monkeypatch.setattr(ci_watch, "call_review", push_during_the_review)
    assert refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))["code"] == "head-differs"
    assert "change-ready" not in ship["forge"].verbs()


def test_the_draft_flag_is_read_after_the_reviews(ship, capsys):
    view = ship["forge"].answers["change-view"]
    ship["forge"].answers["change-view"] = [view, {**view, "draft": False}]
    code, answer = mark(ship, capsys)
    assert code == 0 and answer["marked"] is False and "change-ready" not in ship["forge"].verbs()


def test_a_change_given_as_a_url_matches_the_review_of_its_number(ship, capsys):
    code, answer = run(ci_watch, capsys, "mark-ready", id="https://f.test/7", plan=str(ship["plan"]))
    assert code == 0 and answer["marked"] is True


def test_a_review_begun_with_the_url_matches_a_mark_by_number(ship, capsys):
    ship["reviews"]["0001-a"] = {**SETTLED, "change": VIEW["url"]}
    assert mark(ship, capsys)[1]["marked"] is True


def test_a_capped_review_with_a_fix_no_round_read_allows_ready(ship, capsys):
    ship["reviews"]["0001-a"] = {**SETTLED, "stopped_by": "cap", "fixed": [{"id": "f1", "sha": "abc", "reviewed": False}]}
    assert mark(ship, capsys)[1]["marked"] is True


def test_every_open_review_is_named_at_once(ship, capsys):
    for subtask in ship["reviews"]:
        ship["reviews"][subtask] = {"ok": False, "error": {"code": "no-review", "reason": "none"}}
    error = refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))
    assert [entry["subtask"] for entry in error["reviews"]] == ["0001-a", "0002-b"]


def test_a_plan_with_no_subtask_is_no_settled_review(ship, capsys):
    for name in ("0001-a.md", "0002-b.md"):
        (ship["plan"] / name).unlink()
    error = refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))
    assert error["code"] == "review-open" and error["reviews"][0]["next"] == "developer"
    assert "change-ready" not in ship["forge"].verbs()


def test_a_plan_folder_that_is_not_there_is_unreadable_input(repo, forge, capsys, tmp_path):
    unreadable(ci_watch, capsys, "mark-ready", id="7", plan=str(tmp_path / "no-plan"))


def test_ready_is_refused_when_local_commits_are_not_on_the_change(ship, repo, capsys):
    commit(repo, "b.txt", "two\n")
    assert refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))["code"] == "head-differs"
    assert "ci-status" not in ship["forge"].verbs() and "change-ready" not in ship["forge"].verbs()


@pytest.mark.parametrize("state", ["merged", "closed"])
def test_ready_is_refused_on_a_change_that_is_not_open(ship, capsys, state):
    ship["forge"].answers["change-view"] = {**ship["forge"].answers["change-view"], "state": state}
    assert refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))["code"] == "change-not-open"


def test_a_change_that_is_already_ready_is_not_marked_again(ship, capsys):
    ship["forge"].answers["change-view"] = {**ship["forge"].answers["change-view"], "draft": False}
    code, answer = mark(ship, capsys)
    assert code == 0 and answer["marked"] is False and "change-ready" not in ship["forge"].verbs()


def test_a_ready_change_with_a_red_ci_is_still_refused(ship, capsys):
    ship["forge"].answers["change-view"] = {**ship["forge"].answers["change-view"], "draft": False}
    ship["forge"].answers["ci-status"] = {"ok": True, "status": "failed", "url": "u"}
    assert refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))["code"] == "ci-red"


def test_a_failed_ready_call_stays_a_refusal(ship, capsys):
    ship["forge"].answers["change-ready"] = {"ok": False, "error": {"code": "forbidden", "reason": "no"}}
    assert refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))["code"] == "forbidden"


def _review_command(plan, verb, **payload):
    done = subprocess.run([sys.executable, str(ci_watch.REVIEW), verb], input=json.dumps({"plan": str(plan), "subtask": "0001-a", **payload}).encode("utf-8"),
                          capture_output=True, timeout=60)
    return json.loads(done.stdout)


def test_the_gate_reads_the_real_review_command(repo, forge, tmp_path, capsys):
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "0001-a.md").write_text("x", encoding="utf-8")
    forge.answers = {"change-view": {**VIEW, "head_sha": git(repo, "rev-parse", "HEAD")},
                     "ci-status": {"ok": True, "status": "success", "url": "u"},
                     "change-ready": {"ok": True, "id": "7", "draft": False}}
    first = refused(ci_watch, capsys, "mark-ready", id="7", plan=str(plan))["reviews"][0]
    assert first["subtask"] == "0001-a" and first["next"] == "run-review"
    assert _review_command(plan, "begin", change="7", concerns=[{"name": "c", "why": "w"}])["ok"]
    assert refused(ci_watch, capsys, "mark-ready", id="7", plan=str(plan))["reviews"][0]["next"] == "run-review"
    assert _review_command(plan, "record", findings=[])["ok"]
    code, answer = run(ci_watch, capsys, "mark-ready", id="7", plan=str(plan))
    assert code == 0 and answer["marked"] is True


FOUND = {"concern": "c", "finding": "wrong answer", "why": "w", "fix": "x", "file": "a.txt", "line": 1}


@pytest.fixture
def real_review(repo, forge, tmp_path):
    """The real review command on one subtask, with green CI on the change. The repository has no forge, so a post fails."""
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "0001-a.md").write_text("x", encoding="utf-8")
    forge.answers = {"change-view": {**VIEW, "head_sha": git(repo, "rev-parse", "HEAD")},
                     "ci-status": {"ok": True, "status": "success", "url": "u"},
                     "change-ready": {"ok": True, "id": "7", "draft": False}}
    assert _review_command(plan, "begin", change="7", concerns=[{"name": "c", "why": "w"}])["ok"]
    return plan


def test_a_review_stopped_with_an_unfixed_finding_goes_to_the_developer(real_review, forge, capsys):
    answer = _review_command(real_review, "record", findings=[{**FOUND, "severity": "high"}])
    finding = answer["fix"][0]["id"]
    assert _review_command(real_review, "outcome", id=finding, result="unfixed", reason="out of scope")["ok"]
    review = refused(ci_watch, capsys, "mark-ready", id="7", plan=str(real_review))["reviews"][0]
    assert finding in review["why"] and review["next"] == "developer"
    assert _review_command(real_review, "begin", change="7", concerns=[{"name": "c", "why": "w"}])["error"]["code"] == "review-over"
    assert "change-ready" not in forge.verbs()


def test_a_finding_with_no_outcome_and_a_fix_with_no_round_can_run(real_review, capsys):
    answer = _review_command(real_review, "record", findings=[{**FOUND, "severity": "high"}])
    finding = answer["fix"][0]["id"]
    assert refused(ci_watch, capsys, "mark-ready", id="7", plan=str(real_review))["reviews"][0]["next"] == "run-review"
    assert _review_command(real_review, "outcome", id=finding, result="fixed", sha="abc")["ok"]
    assert refused(ci_watch, capsys, "mark-ready", id="7", plan=str(real_review))["reviews"][0]["next"] == "run-review"


def test_a_review_on_another_change_goes_to_the_developer(real_review, forge, capsys):
    assert _review_command(real_review, "record", findings=[])["ok"]
    forge.answers["change-view"] = {**forge.answers["change-view"], "id": "9"}
    review = refused(ci_watch, capsys, "mark-ready", id="9", plan=str(real_review))["reviews"][0]
    assert review["next"] == "developer" and "change 7" in review["why"]


def test_a_finding_that_is_not_on_the_change_asks_for_another_mark(real_review, capsys):
    answer = _review_command(real_review, "record", findings=[{**FOUND, "severity": "low"}])
    failed = answer["post_failed"][0]["id"]
    review = refused(ci_watch, capsys, "mark-ready", id="7", plan=str(real_review))["reviews"][0]
    assert failed in review["why"] and review["next"] == "mark-again"


@pytest.mark.parametrize("source", ["", "print('[1]')", "print('{\"a\": 1}')", "print('not json')", "import time; time.sleep(30)"])
def test_a_command_with_no_answer_object_is_the_failure_answer(tmp_path, source):
    script = tmp_path / "command.py"
    script.write_text(source, encoding="utf-8")
    answer = ci_watch._call(script, "x", {}, 2)
    assert answer["ok"] is False and answer["error"]["code"] == "command-failed"


def test_a_review_command_that_crashes_refuses_the_gate(ship, tmp_path, capsys, monkeypatch):
    script = tmp_path / "crash.py"
    script.write_text("raise SystemExit(3)", encoding="utf-8")
    monkeypatch.setattr(ci_watch, "REVIEW", script)
    monkeypatch.setattr(ci_watch, "call_review", ORIGINAL_CALL_REVIEW)
    error = refused(ci_watch, capsys, "mark-ready", id="7", plan=str(ship["plan"]))
    assert error["code"] == "review-open" and error["reviews"][0]["next"] == "mark-again"
    assert "change-ready" not in ship["forge"].verbs()


# --- no merge, and the same behaviour on both forges


@pytest.mark.parametrize("kind", ["github", "gitlab"])
def test_the_forge_port_has_no_merge_verb(kind):
    assert not [verb for verb in forge_cli.KINDS[kind].VERBS if "merge" in verb]


@pytest.mark.parametrize("script", ["ci_watch.py", "change_request.py"])
def test_no_merge_command_and_no_forge_tool_is_reachable_from_the_scripts(script):
    source = (SCRIPTS / script).read_text(encoding="utf-8")
    assert not re.search(r"""["'](merge|change-merge)["']|\b(pr|mr) merge\b|--auto\b|automerge""", source)
    assert not re.search(r"""["'](gh|glab)["']""", source)
    named = set(re.findall(r"""(?:call_forge|forge_answer)\(\s*["']([a-z-]+)["']""", source))
    assert named and named <= {"change-view", "change-create-draft", "change-update-body", "change-ready", "ci-status", "ci-wait"}


class Tools:
    """Stands in for `shell.run_tool`: answers gh or glab from the state of one change, runs git for real."""

    def __init__(self, real_run, kind, head):
        self.real_run, self.kind, self.head = real_run, kind, head
        self.draft, self.exists, self.ci = True, False, "success"
        self.commands = []

    def _view(self):
        if not self.exists:
            return shell.Done(1, "", "no pull requests found" if self.kind == "github" else "no open merge request available")
        if self.kind == "github":
            rollup = [{"conclusion": {"success": "SUCCESS", "failed": "FAILURE", "running": ""}[self.ci], "status": "COMPLETED"}]
            return shell.Done(0, json.dumps({"number": 7, "url": "https://f.test/7", "title": "t", "state": "OPEN", "isDraft": self.draft,
                                             "headRefOid": self.head, "statusCheckRollup": rollup}), "")
        return shell.Done(0, json.dumps({"iid": 7, "web_url": "https://f.test/7", "title": "t", "state": "opened", "draft": self.draft,
                                         "sha": self.head, "head_pipeline": {"status": self.ci, "web_url": "https://f.test/ci"}}), "")

    def __call__(self, tool, args, *, stdin_text=None, timeout=None):
        if tool == "git":
            return self.real_run(tool, args, stdin_text=stdin_text, timeout=timeout)
        assert tool == {"github": "gh", "gitlab": "glab"}[self.kind]
        self.commands.append(list(args))
        if args[1] == "view":
            return self._view()
        if args[1] == "create":
            self.exists = True
            assert "--draft" in args
            return shell.Done(0, "https://f.test/" + ("pull" if self.kind == "github" else "-/merge_requests") + "/7\n", "")
        if args[1] == "ready" or "--ready" in args:
            self.draft = False
        if self.kind == "gitlab" and "--description" in args:
            self.draft = False
        if "--draft" in args:
            self.draft = True
        return shell.Done(0, "", "")


@pytest.fixture(params=["github", "gitlab"])
def real_port(request, repo, monkeypatch):
    """The real forge port in process, over one stand-in tool."""
    kind = request.param
    tools = Tools(shell.run_tool, kind, git(repo, "rev-parse", "HEAD"))
    monkeypatch.setattr(shell, "run_tool", tools)

    def call(verb, payload, limit=None):
        return envelope._answer(forge_cli.VERBS, [verb, json.dumps({"forge": kind, **payload})], io.StringIO(""))
    monkeypatch.setattr(ci_watch, "call_forge", call)
    monkeypatch.setattr(change_request, "call_forge", call)
    monkeypatch.setattr(ci_watch, "call_review", lambda _plan, _subtask: SETTLED)
    return tools


def test_the_whole_path_answers_the_same_on_both_forges(real_port, repo, tmp_path, capsys):
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "0001-a.md").write_text("x", encoding="utf-8")

    code, opened = run(change_request, capsys, "open", **PARTS)
    assert code == 0 and (opened["id"], opened["created"], opened["draft"]) == ("7", True, True)
    code, updated = run(change_request, capsys, "open", **PARTS)
    assert code == 0 and (updated["id"], updated["created"]) == ("7", False)
    assert real_port.draft is True

    real_port.ci = "failed"
    code, watched = run(ci_watch, capsys, "watch", id="7", interval=1)
    assert code == 0 and (watched["state"], watched["status"], watched["current_head"]) == ("finished", "failed", True)
    assert refused(ci_watch, capsys, "mark-ready", id="7", plan=str(plan))["code"] == "ci-red"
    assert real_port.draft is True

    real_port.ci = "success"
    code, marked = run(ci_watch, capsys, "mark-ready", id="7", plan=str(plan))
    assert code == 0 and marked["marked"] is True and real_port.draft is False
    assert not [command for command in real_port.commands if "merge" in command[:2]]


# --- the skill file


def test_the_skill_has_its_frontmatter_and_names_every_verb():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    head = text.split("---")[1]
    assert re.search(r"^name: create-change-request$", head, re.M)
    assert re.search(r"^description: \S", head, re.M)
    for verb in list(change_request.VERBS) + list(ci_watch.VERBS):
        assert f"`{verb}`" in text, verb


# --- the live tier: AFKV2_LIVE_CHANGE=<id of a Draft change of this repository> <python> -m pytest ... -k live


LIVE = os.environ.get("AFKV2_LIVE_CHANGE")
live = pytest.mark.skipif(not LIVE, reason="set AFKV2_LIVE_CHANGE to the id of a Draft change")


@live
def test_live_the_watch_reads_the_real_ci_state():
    watched = _real("ci_watch.py", "watch", {"id": LIVE, "budget": 0})
    assert watched["ok"] and watched["status"] in ("success", "failed", "canceled", "running")
    read = ci_watch.call_forge("ci-status", {"id": LIVE})
    assert read["ok"] and watched["status"] in (read["status"], "running")
    reported = _real("ci_watch.py", "status", {"id": LIVE})
    assert reported["status"] == watched["status"] and reported["head_sha"]


@live
def test_live_the_background_start_writes_a_real_record():
    started = _real("ci_watch.py", "start", {"id": LIVE, "budget": 0})
    assert started["ok"] and started["state"] == "watching"
    assert wait_for(lambda: _real("ci_watch.py", "status", {"id": LIVE})["state"] != "watching", limit=120)
    assert _real("ci_watch.py", "status", {"id": LIVE})["head_sha"]
