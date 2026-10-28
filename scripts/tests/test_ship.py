#!/usr/bin/env afk-python
"""ship.py: the ship script's four steps against a stub forge and real git remotes.

The stub forge keeps the changes and notes it was asked to write, so a test
asserts both the writes and what a re-run finds. Pushes go to a bare remote in a
temporary folder. The `ci_wait` tests also run the real GitLab adapter against a
stub `glab` on PATH, and the real `none` adapter; nothing reaches a forge.
"""

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "afk" / "fix" / "scripts"))

import ship  # noqa: E402

WORK = "bug-export-drops-row"
BRANCH = f"fix/{WORK}"
FEATURE = "feat/export"
PARTS = {
    "Work id": WORK,
    "Ticket key": "",
    "Verdict": "V-1 obvious fix",
    "Base": "main@0123abc",
    "Diagnosis branch": BRANCH,
    "Symptom": "- [verified] the export has one row fewer than the grid",
    "Spec comparison": "- [verified] PRD AC-3 says every visible row exports",
    "Reproduction": "- [verified] `tests/test_export.py::test_last_row` fails on the Base commit",
    "Attempts": "",
    "Root cause": "- [inferred] the loop stops one short at `export.py:42`",
    "Fix proposal": "Iterate to the end of the filtered rows.",
    "Approval": "",
    "Outside writes": "",
}
WRITES = ("change-create-draft", "change-comment", "change-ready", "change-reviewers")
FORGE_URL = "https://forge.test/acme/widget/-/merge_requests"


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_ship", ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def diagnosis(tmp_path, **changes):
    parts = dict(PARTS, **changes)
    text = "# Diagnosis\n\n" + "".join(
        f"## {name}\n{body}\n\n" if body else f"## {name}\n\n" for name, body in parts.items()
        if body is not None)
    path = tmp_path / "spec" / WORK / "DIAGNOSIS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def entries(path):
    text = Path(path).read_text(encoding="utf-8")
    part = text.split("## Outside writes", 1)[1]
    return [line[2:] for line in part.splitlines() if line.startswith("- ")]


def hook(remote, name, body):
    script = remote / "hooks" / name
    script.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)


def commit(cwd, name, text="x\n"):
    (cwd / name).write_text(text, encoding="utf-8")
    git(cwd, "add", name)
    git(cwd, "commit", "-q", "-m", f"add {name}")
    return git(cwd, "rev-parse", "HEAD")


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    """A clone on the Diagnosis branch, one fix commit ahead of main, and its bare remote."""
    base = tmp_path_factory.mktemp("template")
    remote = base / "remote.git"
    git(base, "init", "-q", "--bare", "-b", "main", str(remote))
    work = base / "work"
    git(base, "clone", "-q", str(remote), str(work))
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.invalid")
    git(work, "config", "commit.gpgsign", "false")
    git(work, "checkout", "-q", "-b", "main")
    commit(work, "README.md")
    git(work, "push", "-q", "origin", "main")
    git(work, "checkout", "-q", "-b", FEATURE)
    commit(work, "feature.txt")
    git(work, "push", "-q", "origin", FEATURE)
    git(work, "checkout", "-q", "-b", BRANCH, "main")
    commit(work, "fix.txt")
    return base


@pytest.fixture
def repo(tmp_path, template):
    """A fresh copy of the template; the clone's origin is the copied remote."""
    for name in ("remote.git", "work"):
        shutil.copytree(template / name, tmp_path / name)
    work = tmp_path / "work"
    git(work, "remote", "set-url", "origin", str(tmp_path / "remote.git"))
    return work


class Lost:
    """A scripted answer whose write never reached the forge."""

    def __init__(self, answer):
        self.answer = answer


class Taken:
    """A scripted answer for a write that did reach the forge."""

    def __init__(self, answer):
        self.answer = answer


class FakeForge(ship.Forge):
    """Answers `run` the way the forge scripts do, so `call` and `ci_wait` parse for real."""

    def __init__(self, cwd=".", *, ci=(0, {"status": "success", "elapsed": 0, "id": "1"})):
        super().__init__(cwd)
        self.calls, self.timeouts, self.script, self.changes, self.ci = [], {}, {}, {}, ci

    def run(self, verb, payload, timeout):
        self.calls.append((verb, json.loads(json.dumps(payload))))
        self.timeouts[verb] = timeout
        queued = self.script.get(verb) or []
        item = queued.pop(0) if queued else None
        if isinstance(item, Lost):
            return 0, json.dumps(item.answer), ""
        code, answer = getattr(self, "_" + verb.replace("-", "_"))(payload)
        if isinstance(item, Taken):
            answer = item.answer
        return code, answer if isinstance(answer, str) else json.dumps(answer), ""

    def add(self, source, *, draft=True, state="opened", notes=()):
        number = str(len(self.changes) + 1)
        self.changes[number] = {"id": number, "url": f"{FORGE_URL}/{number}", "source": source,
                                "state": state, "draft": draft, "notes": list(notes), "reviewers": []}
        return self.changes[number]

    def writes(self):
        return [verb for verb, _ in self.calls if verb in WRITES]

    def _change_view(self, payload):
        ref = str(payload["id"])
        found = [c for c in self.changes.values() if c["id"] == ref or c["source"] == ref]
        if not found:
            return 0, {"error": True, "verb": "change-view", "missing": True, "reason": "no open merge requests"}
        if len(found) > 1:
            return 0, {"error": True, "verb": "change-view", "missing": False,
                       "reason": f"multiple merge requests exist for branch {ref}"}
        change = found[0]
        return 0, {key: change[key] for key in ("id", "url", "source", "state", "draft")}

    def _change_create_draft(self, payload):
        change = self.add(payload["source"])
        return 0, {"url": change["url"], "id": change["id"], "draft": True}

    def _change_comment(self, payload):
        change = self.changes[payload["id"]]
        ident = str(100 + len(change["notes"]))
        change["notes"].append({"id": ident, "body": payload["text"]})
        return 0, {"ok": True, "inline": False, "comment": ident, "url": f"{change['url']}#note_{ident}"}

    def _note_list(self, payload):
        notes = self.changes[payload["id"]]["notes"]
        return 0, {"notes": notes, "count": len(notes)}

    def _change_ready(self, payload):
        self.changes[payload["id"]]["draft"] = False
        return 0, {"ok": True, "id": payload["id"], "draft": False}

    def _change_reviewers(self, payload):
        self.changes[payload["id"]]["reviewers"].append(payload["reviewers"])
        return 0, {"ok": True, "id": payload["id"], "reviewers": payload["reviewers"]}

    def _ci_wait(self, payload):
        return self.ci


class Recorder:
    def __init__(self, answer=None):
        self.calls, self.answer = [], answer or {"ok": True, "pending": 0}

    def __call__(self, value):
        self.calls.append(value)
        return self.answer


def tools(forge, *, protected=("main",), settings=None, reasons=None, sleeps=None):
    settings = {"mrAssignee": "dev.one", "mrReviewer": "rev.two"} if settings is None else settings
    sleeps = [] if sleeps is None else sleeps
    return ship.Tools(forge=forge, protected=lambda branch: branch in protected,
                      setting=lambda key: settings.get(key, ""),
                      post_reasons=reasons or Recorder(), sleep=sleeps.append)


def proof_files(tmp_path):
    one, two = tmp_path / "p1.txt", tmp_path / "p2.txt"
    one.write_text("test_last_row: failed before, passed after", encoding="utf-8")
    two.write_text("static green; unit green", encoding="utf-8")
    return {"P-1": str(one), "P-2": str(two)}


def remote_tip(repo, branch):
    found = git(repo, "ls-remote", "--heads", "origin", f"refs/heads/{branch}").split()
    return found[0] if found else ""


# ---- open ------------------------------------------------------------------

def test_open_pushes_opens_one_draft_then_posts_reasons(tmp_path, repo):
    path, forge, reasons = diagnosis(tmp_path), FakeForge(repo), Recorder()
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge, reasons=reasons))
    assert result["status"] == "done", result
    assert [verb for verb, _ in forge.calls] == ["change-view", "change-create-draft"]
    assert forge.calls[0][1] == {"id": BRANCH}
    created = forge.calls[1][1]
    assert created["source"] == BRANCH and created["target"] == "main" and created["assignee"] == "dev.one"
    assert remote_tip(repo, BRANCH) == git(repo, "rev-parse", "HEAD")
    assert git(repo, "config", f"branch.{BRANCH}.merge") == f"refs/heads/{BRANCH}"
    assert entries(path) == [f"change: {FORGE_URL}/1"]
    assert reasons.calls == ["1"]


def test_open_names_an_unset_assignee_and_opens_unassigned(tmp_path, repo):
    path, forge = diagnosis(tmp_path), FakeForge(repo)
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge, settings={}))
    assert result["status"] == "done" and result["missing"] == ["mrAssignee"]
    assert "assignee" not in forge.calls[1][1]


def test_open_uses_the_change_found_by_branch(tmp_path, repo):
    path, forge = diagnosis(tmp_path), FakeForge(repo)
    forge.add(BRANCH)
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge))
    assert result["status"] == "done" and result["change_step"] == "found"
    assert forge.writes() == []
    assert entries(path) == [f"change: {FORGE_URL}/1"]


def test_open_rerun_skips_the_listed_change_and_still_posts_reasons(tmp_path, repo):
    path, forge, reasons = diagnosis(tmp_path), FakeForge(repo), Recorder()
    forge.add(BRANCH)
    path = diagnosis(tmp_path, **{"Outside writes": f"- change: {FORGE_URL}/1"})
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge, reasons=reasons))
    assert result["status"] == "skipped", result
    assert forge.calls == [] and remote_tip(repo, BRANCH) == ""
    assert reasons.calls == ["1"]


def test_several_gitlab_changes_on_one_branch_block_and_open_none(tmp_path, repo):
    path, forge = diagnosis(tmp_path), FakeForge(repo)
    forge.add(BRANCH)
    forge.add(BRANCH)
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge))
    assert result["status"] == "blocked" and "multiple merge requests" in result["reason"]
    assert forge.writes() == [] and remote_tip(repo, BRANCH) == "" and entries(path) == []


def test_a_failed_open_is_retried_only_after_the_read_back_by_branch(tmp_path, repo):
    path, forge, sleeps = diagnosis(tmp_path), FakeForge(repo), []
    forge.script["change-create-draft"] = [Lost({"error": True, "reason": "502 bad gateway"})]
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge, sleeps=sleeps))
    assert result["status"] == "done", result
    verbs = [verb for verb, _ in forge.calls]
    assert verbs == ["change-view", "change-create-draft", "change-view", "change-create-draft"]
    assert sleeps == [5] and len(forge.changes) == 1


def test_an_open_that_took_effect_is_found_not_opened_again(tmp_path, repo):
    path, forge = diagnosis(tmp_path), FakeForge(repo)
    forge.script["change-create-draft"] = [Taken({"error": True, "reason": "timeout reading the answer"})]
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge))
    assert result["status"] == "done" and result["change_step"] == "found", result
    assert forge.writes() == ["change-create-draft"] and len(forge.changes) == 1
    assert entries(path) == [f"change: {FORGE_URL}/1"]


def test_a_change_link_with_an_empty_id_blocks_before_listing(tmp_path, repo):
    path, forge = diagnosis(tmp_path), FakeForge(repo)
    forge.add(BRANCH)["url"] = f"{FORGE_URL}/"
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge))
    assert result["status"] == "blocked" and "empty change id" in result["reason"]
    assert entries(path) == []


def test_an_open_that_never_answers_an_id_blocks_after_two_retries(tmp_path, repo):
    path, forge, sleeps = diagnosis(tmp_path), FakeForge(repo), []
    forge.script["change-create-draft"] = [Lost({"url": "", "id": "", "draft": True})] * 3
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge, sleeps=sleeps))
    assert result["status"] == "blocked" and sleeps == [5, 20] and entries(path) == []


def test_a_failed_fix_branch_push_is_retried_after_reading_the_remote(tmp_path, repo):
    hook(tmp_path / "remote.git", "pre-receive", "exit 1\n")
    path, forge, sleeps = diagnosis(tmp_path), FakeForge(repo), []
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge, sleeps=sleeps))
    assert result["status"] == "blocked" and "never forced" in result["reason"]
    assert sleeps == [5, 20]
    assert forge.writes() == [] and entries(path) == []


def test_open_never_forces_over_a_remote_fix_branch_it_does_not_contain(tmp_path, repo):
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(tmp_path / "remote.git"), str(other))
    git(other, "config", "user.name", "Other")
    git(other, "config", "user.email", "other@example.invalid")
    git(other, "checkout", "-q", "-b", BRANCH, "origin/main")
    stranger = commit(other, "other.txt")
    git(other, "push", "-q", "origin", BRANCH)
    path, forge = diagnosis(tmp_path), FakeForge(repo)
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge))
    assert result["status"] == "blocked" and "does not contain" in result["reason"]
    assert remote_tip(repo, BRANCH) == stranger and forge.writes() == []


def test_open_refuses_a_protected_push_target(tmp_path, repo):
    path, forge = diagnosis(tmp_path), FakeForge(repo)
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge, protected=(BRANCH,)))
    assert result["status"] == "refused" and "protected" in result["reason"]
    assert forge.calls == [] and remote_tip(repo, BRANCH) == ""


def test_open_refuses_a_checkout_off_the_diagnosis_branch(tmp_path, repo):
    git(repo, "checkout", "-q", "main")
    result = ship.run_ship_step("open", diagnosis(tmp_path), cwd=repo, tools=tools(FakeForge(repo)))
    assert result["status"] == "refused" and BRANCH in result["reason"]


def test_open_blocks_when_rationale_post_does_not_finish(tmp_path, repo):
    path, forge = diagnosis(tmp_path), FakeForge(repo)
    reasons = Recorder({"ok": False, "blocker": "head-mismatch", "reason": "push first"})
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge, reasons=reasons))
    assert result["status"] == "blocked" and "push first" in result["reason"]
    assert entries(path) == [f"change: {FORGE_URL}/1"]


# ---- refusals before any write ---------------------------------------------

def test_a_diagnosis_the_check_refuses_is_refused(tmp_path, repo):
    path, forge = diagnosis(tmp_path, Verdict=""), FakeForge(repo)
    result = ship.run_ship_step("open", path, cwd=repo, tools=tools(forge))
    assert result["status"] == "refused" and "missing Verdict" in result["reason"]
    assert forge.calls == []


def test_an_unknown_step_is_refused(tmp_path, repo):
    result = ship.run_ship_step("merge", diagnosis(tmp_path), cwd=repo, tools=tools(FakeForge(repo)))
    assert result["status"] == "refused"


@pytest.mark.parametrize("step", ["proof", "ready"])
def test_an_empty_change_id_is_refused(tmp_path, repo, step):
    path = diagnosis(tmp_path, **{"Outside writes": "- change: https://forge.test/acme/widget/pull/"})
    forge = FakeForge(repo)
    proof = proof_files(tmp_path) if step == "proof" else None
    result = ship.run_ship_step(step, path, proof=proof, cwd=repo, tools=tools(forge))
    assert result["status"] == "refused" and "empty change id" in result["reason"]
    assert forge.calls == []


# ---- proof -----------------------------------------------------------------

def test_proof_posts_one_comment_with_p1_p2_and_the_ticket_link_then_skips(tmp_path, repo):
    forge = FakeForge(repo)
    forge.add(BRANCH)
    path = diagnosis(tmp_path, **{"Ticket key": "#5", "Outside writes": f"- change: {FORGE_URL}/1"})
    link = "https://tracker.test/acme/widget/issues/5#issuecomment-9"
    args = dict(proof=proof_files(tmp_path), evidence_link=link, cwd=repo, tools=tools(forge))
    result = ship.run_ship_step("proof", path, **args)
    assert result["status"] == "done", result
    assert forge.writes() == ["change-comment"]
    body = forge.changes["1"]["notes"][0]["body"]
    assert body.splitlines()[0] == f"afk-evidence {WORK} change-proof"
    assert "### P-1" in body and "failed before, passed after" in body
    assert "### P-2" in body and "unit green" in body and link in body
    assert entries(path)[-1] == f"evidence: afk-evidence {WORK} change-proof"
    again = ship.run_ship_step("proof", path, **args)
    assert again["status"] == "skipped" and forge.writes() == ["change-comment"]


def test_proof_found_by_its_marker_is_listed_not_posted_again(tmp_path, repo):
    forge = FakeForge(repo)
    forge.add(BRANCH, notes=[{"id": "7", "body": f"afk-evidence {WORK} change-proof\n\n### P-1"}])
    path = diagnosis(tmp_path, **{"Outside writes": f"- change: {FORGE_URL}/1"})
    result = ship.run_ship_step("proof", path, proof=proof_files(tmp_path), cwd=repo, tools=tools(forge))
    assert result["status"] == "done" and result["comment"] == "found"
    assert forge.writes() == [] and entries(path)[-1].startswith("evidence: ")


def test_proof_needs_the_evidence_link_when_a_ticket_exists(tmp_path, repo):
    path = diagnosis(tmp_path, **{"Ticket key": "#5", "Outside writes": f"- change: {FORGE_URL}/1"})
    forge = FakeForge(repo)
    result = ship.run_ship_step("proof", path, proof=proof_files(tmp_path), cwd=repo, tools=tools(forge))
    assert result["status"] == "refused" and "--evidence-link" in result["reason"]
    assert forge.calls == []


def test_proof_needs_a_shipped_change(tmp_path, repo):
    forge = FakeForge(repo)
    result = ship.run_ship_step("proof", diagnosis(tmp_path), proof=proof_files(tmp_path), cwd=repo,
                                tools=tools(forge))
    assert result["status"] == "refused" and forge.calls == []


def test_proof_after_a_land_goes_on_the_feature_branch_change(tmp_path, repo):
    forge = FakeForge(repo)
    forge.add(FEATURE)
    path = diagnosis(tmp_path, Base=f"{FEATURE}@0123abc", **{"Outside writes": f"- push: {FEATURE}@abc123"})
    result = ship.run_ship_step("proof", path, proof=proof_files(tmp_path), cwd=repo, tools=tools(forge))
    assert result["status"] == "done" and result["change"] == f"{FORGE_URL}/1"
    assert forge.calls[0] == ("change-view", {"id": FEATURE})


def test_proof_after_a_land_with_no_open_change_hands_back_the_text(tmp_path, repo):
    forge = FakeForge(repo)
    path = diagnosis(tmp_path, Base=f"{FEATURE}@0123abc", **{"Outside writes": f"- push: {FEATURE}@abc123"})
    result = ship.run_ship_step("proof", path, proof=proof_files(tmp_path), cwd=repo, tools=tools(forge))
    assert result["status"] == "no-change" and "### P-2" in result["text"]
    assert forge.writes() == [] and entries(path) == [f"push: {FEATURE}@abc123"]


# ---- ready: ci_wait routing --------------------------------------------------

CI_ANSWERS = {
    "red": (1, {"status": "failed", "elapsed": 360, "id": "1"}),
    "canceled": (1, {"status": "canceled", "elapsed": 360, "id": "1"}),
    "timeout": (2, {"status": "running", "elapsed": 5400, "id": "1", "reason": "budget exhausted"}),
    "unreadable": (3, {"status": "unreadable", "elapsed": 360, "reason": "3 consecutive read errors"}),
    "no_ci": (3, {"unsupported": True, "verb": "ci-wait", "reason": "forge: none"}),
    "dispatch": (2, ""),
    "unavailable": (4, {"unavailable": True, "verb": "ci-wait", "reason": "glab is not on PATH"}),
    "mismatch": (0, {"status": "failed"}),
}


def ready_case(tmp_path, repo, ci, settings=None):
    forge = FakeForge(repo, ci=ci)
    forge.add(BRANCH)
    path = diagnosis(tmp_path, **{"Outside writes": f"- change: {FORGE_URL}/1"})
    result = ship.run_ship_step("ready", path, cwd=repo, tools=tools(forge, settings=settings))
    return forge, result


def test_ci_wait_green_marks_ready_then_adds_the_reviewer(tmp_path, repo):
    forge, result = ready_case(tmp_path, repo, (0, {"status": "success", "elapsed": 180, "id": "1"}))
    assert result["status"] == "done" and result["reviewer"] == "rev.two", result
    assert forge.writes() == ["change-ready", "change-reviewers"]
    assert forge.changes["1"]["draft"] is False and forge.changes["1"]["reviewers"] == ["rev.two"]


def test_ci_wait_green_without_a_reviewer_names_the_missing_key(tmp_path, repo):
    forge, result = ready_case(tmp_path, repo, (0, {"status": "success", "elapsed": 0, "id": "1"}), settings={})
    assert result["status"] == "done" and result["missing"] == ["mrReviewer"]
    assert forge.writes() == ["change-ready"]


@pytest.mark.parametrize("case", sorted(CI_ANSWERS))
def test_ci_wait_anything_but_green_leaves_the_change_draft_with_the_reason(tmp_path, repo, case):
    forge, result = ready_case(tmp_path, repo, CI_ANSWERS[case])
    assert result["status"] == "draft" and "stays Draft" in result["reason"], result
    assert forge.writes() == [] and forge.changes["1"]["draft"] is True
    if case == "no_ci":
        assert result["reason"].startswith("no CI")


def test_ci_wait_polls_every_180_s_for_at_most_5400_s(tmp_path, repo):
    forge, _ = ready_case(tmp_path, repo, (0, {"status": "success", "elapsed": 0, "id": "1"}))
    sent = dict(forge.calls)["ci-wait"]
    assert sent == {"id": "1", "budget": 5400, "interval": 180}
    assert forge.timeouts["ci-wait"] >= 5400 and forge.timeouts["change-view"] < 5400


def test_ci_wait_is_skipped_for_a_change_already_ready(tmp_path, repo):
    forge = FakeForge(repo)
    forge.add(BRANCH, draft=False)
    path = diagnosis(tmp_path, **{"Outside writes": f"- change: {FORGE_URL}/1"})
    result = ship.run_ship_step("ready", path, cwd=repo, tools=tools(forge))
    assert result["status"] == "skipped" and [verb for verb, _ in forge.calls] == ["change-view"]


def test_open_proof_ready_then_again_write_each_once_in_order(tmp_path, repo):
    receipts = tmp_path / "pushes.txt"
    hook(tmp_path / "remote.git", "post-receive", f"cat >> '{receipts.as_posix()}'\n")
    path, forge, reasons = diagnosis(tmp_path), FakeForge(repo), Recorder()
    kit = tools(forge, reasons=reasons)
    for _ in range(2):
        for step in ("open", "proof", "ready"):
            proof = proof_files(tmp_path) if step == "proof" else None
            result = ship.run_ship_step(step, path, proof=proof, cwd=repo, tools=kit)
            assert result["status"] in ("done", "skipped"), result
    assert forge.writes() == list(WRITES)
    assert len(receipts.read_text(encoding="utf-8").splitlines()) == 1
    assert entries(path) == [f"change: {FORGE_URL}/1", f"evidence: afk-evidence {WORK} change-proof"]


# ---- the real adapters, for the ci-wait seam ---------------------------------

needs_bash = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")


def forge_config(tmp_path, monkeypatch, kind):
    config = tmp_path / "afk-config.yaml"
    config.write_text(f"schema: 1\nforge: {kind}\n", encoding="utf-8")
    monkeypatch.setenv("AFK_CONFIG", str(config))
    monkeypatch.setenv("AFK_PLUGIN_ROOT", str(ROOT))
    monkeypatch.setenv("AFK_BASH", str(BASH))


@needs_bash
def test_ci_wait_on_forge_none_exits_3_at_once_and_reads_as_no_ci(tmp_path, monkeypatch):
    forge_config(tmp_path, monkeypatch, "none")
    started = time.monotonic()
    code, answer, stderr = ship.Forge(tmp_path).ci_wait("7")
    assert code == 3 and answer["unsupported"] is True, (code, answer, stderr)
    assert time.monotonic() - started < 60
    green, reason = ship.route_ci(code, answer, stderr)
    assert not green and reason.startswith("no CI")


GLAB = """#!/bin/sh
printf '%s\\n' "$*" >> "$AFK_GLAB_LOG"
case "$1 $2" in
  "mr view")
    if [ "$AFK_PIPELINE" = unreadable ]; then echo ""; exit 0; fi
    printf '{"iid":7,"draft":true,"title":"Draft: fix","state":"opened","web_url":"https://gitlab.test/acme/widget/-/merge_requests/7","head_pipeline":{"status":"%s"}}\\n' "$AFK_PIPELINE" ;;
  "mr update") echo "updated" ;;
  *) echo "{}" ;;
esac
"""


@needs_bash
@pytest.mark.parametrize("pipeline,status,ready", [
    ("success", "done", True), ("failed", "draft", False),
    ("running", "draft", False), ("unreadable", "draft", False),
])
def test_ci_wait_through_the_gitlab_adapter_routes_each_answer(tmp_path, monkeypatch, pipeline, status, ready):
    forge_config(tmp_path, monkeypatch, "gitlab")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    (binaries / "glab").write_text(GLAB, encoding="utf-8")
    (binaries / "glab").chmod(0o755)
    log = tmp_path / "glab.log"
    monkeypatch.setenv("PATH", str(binaries) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("AFK_GLAB_LOG", str(log))
    monkeypatch.setenv("AFK_PIPELINE", pipeline)
    monkeypatch.setattr(ship, "CI_INTERVAL", 1)
    monkeypatch.setattr(ship, "CI_BUDGET", 3)
    path = diagnosis(tmp_path, **{"Outside writes": "- change: https://gitlab.test/acme/widget/-/merge_requests/7"})
    kit = ship.Tools(setting=lambda key: "rev.two", protected=lambda branch: False,
                     post_reasons=Recorder(), sleep=lambda seconds: None)
    if pipeline == "unreadable":
        kit.forge = FakeViewThenRealForge(tmp_path)
    result = ship.run_ship_step("ready", path, cwd=tmp_path, tools=kit)
    assert result["status"] == status, result
    calls = log.read_text(encoding="utf-8")
    assert ("mr update 7 --ready" in calls) is ready
    assert ("--reviewer +rev.two" in calls) is ready


class FakeViewThenRealForge(ship.Forge):
    """The real adapter for every verb but the first change-view, which an unreadable stub cannot answer."""

    def run(self, verb, payload, timeout):
        if verb == "change-view":
            return 0, json.dumps({"id": "7", "url": "https://gitlab.test/acme/widget/-/merge_requests/7",
                                  "state": "opened", "draft": True}), ""
        return super().run(verb, payload, timeout)


# ---- land: the fast_forward seam on a real remote -----------------------------

def land_case(tmp_path, repo):
    git(repo, "checkout", "-q", "-B", BRANCH, f"origin/{FEATURE}")
    head = commit(repo, "fix.txt", "fixed\n")
    return diagnosis(tmp_path, Base=f"{FEATURE}@0123abc"), head


def test_fast_forward_land_pushes_with_upstream_and_lists_the_push(tmp_path, repo):
    path, head = land_case(tmp_path, repo)
    forge = FakeForge(repo)
    result = ship.run_ship_step("land", path, cwd=repo, tools=tools(forge))
    assert result["status"] == "done", result
    assert remote_tip(repo, FEATURE) == head
    assert git(repo, "config", f"branch.{BRANCH}.merge") == f"refs/heads/{FEATURE}"
    assert entries(path) == [f"push: {FEATURE}@{head}"]
    assert forge.calls == []
    again = ship.run_ship_step("land", path, cwd=repo, tools=tools(forge))
    assert again["status"] == "skipped"


def test_fast_forward_check_refuses_a_moved_remote_tip(tmp_path, repo):
    path, head = land_case(tmp_path, repo)
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", "-b", FEATURE, str(tmp_path / "remote.git"), str(other))
    git(other, "config", "user.name", "Other")
    git(other, "config", "user.email", "other@example.invalid")
    moved = commit(other, "moved.txt")
    git(other, "push", "-q", "origin", FEATURE)
    result = ship.run_ship_step("land", path, cwd=repo, tools=tools(FakeForge(repo)))
    assert result["status"] == "not-fast-forward" and result["tip"] == moved, result
    assert remote_tip(repo, FEATURE) == moved and entries(path) == []


def test_fast_forward_push_sees_a_tip_that_moved_after_the_fetch(tmp_path, repo):
    _, head = land_case(tmp_path, repo)
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", "-b", FEATURE, str(tmp_path / "remote.git"), str(other))
    git(other, "config", "user.name", "Other")
    git(other, "config", "user.email", "other@example.invalid")
    moved = commit(other, "moved.txt")
    git(other, "push", "-q", "origin", FEATURE)
    outcome = ship._push(repo, tools(FakeForge(repo)), "origin", FEATURE, head)
    assert not outcome.ok and outcome.answer["moved"] is True and outcome.answer["tip"] == moved


def test_fast_forward_push_refused_by_the_remote_is_retried_after_read_back(tmp_path, repo):
    path, _ = land_case(tmp_path, repo)
    hook(tmp_path / "remote.git", "pre-receive", "exit 1\n")
    sleeps = []
    result = ship.run_ship_step("land", path, cwd=repo, tools=tools(FakeForge(repo), sleeps=sleeps))
    assert result["status"] == "blocked" and sleeps == [5, 20] and entries(path) == []


def test_fast_forward_land_refuses_a_protected_target(tmp_path, repo):
    path, _ = land_case(tmp_path, repo)
    before = remote_tip(repo, FEATURE)
    result = ship.run_ship_step("land", path, cwd=repo, tools=tools(FakeForge(repo), protected=(FEATURE,)))
    assert result["status"] == "refused" and remote_tip(repo, FEATURE) == before


def test_command_line_prints_one_json_result_and_exits_by_status(tmp_path, repo):
    done = subprocess.run([sys.executable, str(ROOT / "skills" / "afk" / "fix" / "scripts" / "ship.py"),
                           "ready", str(diagnosis(tmp_path))], cwd=repo, capture_output=True, text=True)
    assert done.returncode == 1
    assert json.loads(done.stdout)["status"] == "refused"
