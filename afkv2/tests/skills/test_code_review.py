"""The review rounds: round cap, severity routing, posts through the forge port, the final report."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2] / "skills" / "code-review"
sys.path.insert(0, str(SKILL / "scripts"))

import review_rounds  # noqa: E402


@pytest.mark.parametrize(("done", "expected"), [(0, 1), (1, 2), (2, 3), (3, None), (4, None)])
def test_next_round_stops_after_round_3(done, expected):
    assert review_rounds.next_round(done) == expected


def test_route_sends_critical_and_high_to_fix_and_medium_and_low_to_post():
    findings = [{"severity": severity} for severity in ("critical", "high", "medium", "low")]
    fix, post = review_rounds.route(findings)
    assert [f["severity"] for f in fix] == ["critical", "high"]
    assert [f["severity"] for f in post] == ["medium", "low"]


class Forge:
    """Stands in for the forge command: records each call and answers from a script."""

    def __init__(self):
        self.calls = []
        self.answers = []

    def __call__(self, verb, payload):
        self.calls.append((verb, payload))
        if self.answers:
            return self.answers.pop(0)
        return {"ok": True, "inline": True, "thread": "1", "comment": str(len(self.calls)), "url": f"https://f.test/{len(self.calls)}"}


@pytest.fixture
def forge(monkeypatch):
    fake = Forge()
    monkeypatch.setattr(review_rounds, "call_forge", fake)
    return fake


@pytest.fixture
def review(tmp_path, capsys, forge):
    """Run one verb through the command line; returns (exit code, answer)."""
    plan = tmp_path / "plan"
    plan.mkdir()

    def run(verb, **payload):
        capsys.readouterr()
        code = review_rounds.main([verb, json.dumps({"plan": str(plan), "subtask": "0001-a", **payload})])
        return code, json.loads(capsys.readouterr().out)
    run.plan = plan
    return run


CONCERNS = [{"name": "correctness", "why": "the slice has branches"}]


def begin(review, **extra):
    return review("begin", change="7", concerns=CONCERNS, **extra)


def test_begin_counts_rounds_and_writes_the_state_under_the_plan_folder(review):
    code, answer = begin(review)
    assert (code, answer["round"], answer["cap"]) == (0, 1, 3)
    assert (review.plan / "review" / "0001-a.rounds.json").is_file()


@pytest.mark.parametrize("concerns", [[], None, [{"name": "correctness"}], [{"name": " ", "why": "x"}], "correctness"])
def test_begin_refuses_a_round_without_a_reason_for_each_concern(review, concerns):
    code, answer = review("begin", change="7", concerns=concerns)
    assert (code, answer["error"]["code"]) == (2, "bad-payload")
    assert not (review.plan / "review" / "0001-a.rounds.json").exists()


def test_begin_refuses_a_subtask_id_that_leaves_the_plan_folder(review):
    code, answer = review("begin", change="7", concerns=CONCERNS, subtask="../x")
    assert (code, answer["error"]["code"]) == (2, "bad-payload")


def test_begin_needs_the_change(review):
    code, answer = review("begin", concerns=CONCERNS)
    assert (code, answer["error"]["code"]) == (2, "bad-payload")


def test_begin_refuses_a_plan_folder_that_does_not_exist(review, tmp_path):
    code, answer = review("begin", change="7", concerns=CONCERNS, plan=str(tmp_path / "none"))
    assert (code, answer["error"]["code"]) == (2, "bad-payload")


def test_begin_answers_the_open_round_again_after_a_restart(review):
    begin(review)
    code, answer = begin(review)
    assert (code, answer["round"], answer["resumed"]) == (0, 1, True)


def test_a_broken_state_file_refuses_and_stays_as_it_is(review):
    begin(review)
    state = review.plan / "review" / "0001-a.rounds.json"
    state.write_text("{not json", encoding="utf-8")
    code, answer = begin(review)
    assert (code, answer["error"]["code"]) == (1, "bad-state")
    assert state.read_text(encoding="utf-8") == "{not json"


def test_a_state_of_another_subtask_refuses(review):
    begin(review)
    state = review.plan / "review" / "0001-a.rounds.json"
    state.write_text(json.dumps({**json.loads(state.read_text(encoding="utf-8")), "subtask": "0002-b"}), encoding="utf-8")
    code, answer = begin(review)
    assert (code, answer["error"]["code"]) == (1, "bad-state")


def finding(severity="high", text="the loop skips the last item", **extra):
    return {"concern": "correctness", "severity": severity, "file": "src/a.py", "line": 3,
            "finding": text, "why": "the bound is one short", "fix": "use <=", **extra}


def ids(items):
    return [item["id"] for item in items]


def test_record_routes_each_severity_and_posts_only_medium_and_low(review, forge):
    begin(review)
    code, answer = review("record", findings=[finding("critical", "one"), finding("high", "two"),
                                              finding("medium", "three"), finding("low", "four")])
    assert (code, answer["round"], answer["next"]) == (0, 1, "fix")
    assert [item["finding"] for item in answer["fix"]] == ["one", "two"]
    assert len(answer["posted"]) == 2
    assert answer["post_failed"] == []
    assert [call[0] for call in forge.calls] == ["change-comment", "change-comment"]
    assert "three" in forge.calls[0][1]["text"] and "four" in forge.calls[1][1]["text"]


def test_a_post_carries_the_change_the_line_and_every_field_a_reader_needs(review, forge):
    begin(review)
    review("record", findings=[finding("medium")])
    payload = forge.calls[0][1]
    assert (payload["id"], payload["file"], payload["line"]) == ("7", "src/a.py", 3)
    for part in ("medium", "correctness", "src/a.py:3", "the loop skips the last item", "the bound is one short", "use <="):
        assert part in payload["text"]


def test_a_finding_on_a_removed_line_posts_on_the_old_side(review, forge):
    begin(review)
    review("record", findings=[finding("low", side="old")])
    payload = forge.calls[0][1]
    assert (payload["side"], payload["old_line"]) == ("old", 3)
    assert "line" not in payload


@pytest.mark.parametrize("place", [{"file": None, "line": None}, {"line": None}])
def test_a_finding_with_no_line_posts_a_plain_note(review, forge, place):
    begin(review)
    review("record", findings=[{**finding("low"), **place}])
    payload = forge.calls[0][1]
    assert "file" not in payload and "line" not in payload


def test_a_windows_path_in_a_finding_reaches_the_forge_with_forward_slashes(review, forge):
    begin(review)
    review("record", findings=[{**finding("low"), "file": "src\\a.py"}])
    assert forge.calls[0][1]["file"] == "src/a.py"


def test_a_round_with_no_finding_to_fix_says_stop(review, forge):
    begin(review)
    assert review("record", findings=[])[1]["next"] == "stop"
    assert forge.calls == []


@pytest.mark.parametrize("bad", [
    {"severity": "blocker"}, {"severity": None}, {"line": 0}, {"line": "3"}, {"line": True}, {"side": "left"},
    {"finding": " "}, {"why": None}, {"fix": ""}, {"concern": 1}, {"file": ""},
])
def test_record_refuses_every_finding_it_cannot_route_and_posts_nothing(review, forge, bad):
    begin(review)
    code, answer = review("record", findings=[finding("low", "fine"), {**finding(), **bad}])
    assert (code, answer["error"]["code"]) == (2, "bad-payload")
    assert "1" in answer["error"]["reason"]
    assert forge.calls == []
    assert review("record", findings=[])[0] == 0


def test_record_refuses_a_payload_with_no_list(review):
    begin(review)
    assert review("record")[0] == 2


def test_record_needs_an_open_round(review):
    code, answer = review("record", findings=[])
    assert (code, answer["error"]["code"]) == (1, "no-open-round")
    begin(review)
    review("record", findings=[])
    code, answer = review("record", findings=[])
    assert (code, answer["error"]["code"]) == (1, "no-open-round")


def test_a_failed_post_is_named_kept_and_tried_again(review, forge):
    begin(review)
    forge.answers = [{"ok": False, "error": {"code": "auth", "reason": "no login"}}]
    code, answer = review("record", findings=[finding("low", "one"), finding("low", "two")])
    assert code == 0
    assert [item["reason"] for item in answer["post_failed"]] == ["no login"]
    assert len(answer["posted"]) == 1
    _, report = review("finish")
    assert report["left"]["not_posted"] == []
    assert len(report["left"]["posted"]) == 2
    assert len(forge.calls) == 3


def test_a_plain_note_answer_keeps_the_reason(review, forge):
    begin(review)
    forge.answers = [{"ok": True, "inline": False, "thread": "", "comment": "9", "url": "u", "reason": "line not in the diff"}]
    _, answer = review("record", findings=[finding("low")])
    assert answer["posted"][0]["inline"] is False
    assert answer["posted"][0]["reason"] == "line not in the diff"


def fix_all(review, answer, sha="abc1234"):
    for item in answer["fix"]:
        assert review("outcome", id=item["id"], result="fixed", sha=sha)[0] == 0


def test_a_finding_found_again_in_a_later_round_is_not_posted_twice(review, forge):
    begin(review)
    _, first = review("record", findings=[finding("high", "h"), finding("low", "same  TEXT")])
    fix_all(review, first)
    begin(review)
    _, second = review("record", findings=[{**finding("low", "same text"), "line": 9}])
    assert second["posted"] == []
    assert len(forge.calls) == 1


def test_a_low_finding_that_comes_back_high_goes_to_fix(review, forge):
    begin(review)
    _, first = review("record", findings=[finding("high", "h"), finding("low", "x")])
    fix_all(review, first)
    begin(review)
    _, second = review("record", findings=[finding("high", "x")])
    assert [item["finding"] for item in second["fix"]] == ["x"]
    assert ids(second["fix"]) != ids(first["fix"])
    posts = len(forge.calls)
    review("outcome", id=second["fix"][0]["id"], result="unfixed", reason="outside the scope")
    _, report = review("finish")
    left = report["left"]["blocking"][0]
    assert (left["finding"], left["severity"]) == ("x", "high")
    assert left["url"] and left["url"] != left["replaces"]
    assert len(forge.calls) == posts + 1
    assert left["replaces"] in forge.calls[-1][1]["text"]


def test_a_fixed_finding_found_again_opens_again_and_counts_as_a_wrong_claim(review):
    begin(review)
    _, first = review("record", findings=[finding("high", "h")])
    fix_all(review, first)
    begin(review)
    _, second = review("record", findings=[finding("high", "h")])
    assert ids(second["fix"]) == ids(first["fix"])
    assert begin(review)[1]["error"]["code"] == "fix-open"
    fix_all(review, second)
    begin(review)
    review("record", findings=[])
    assert review("finish")[1]["reopened"] == ids(first["fix"])


def test_the_same_finding_twice_in_one_round_keeps_the_higher_severity(review, forge):
    begin(review)
    _, answer = review("record", findings=[finding("low", "x"), finding("high", "x")])
    assert [item["severity"] for item in answer["fix"]] == ["high"]
    assert forge.calls == []


def test_outcome_refuses_what_it_cannot_record(review):
    begin(review)
    _, answer = review("record", findings=[finding("high", "h"), finding("low", "l")])
    item = answer["fix"][0]["id"]
    assert review("outcome", id=item, result="fixed")[0] == 2
    assert review("outcome", id=item, result="unfixed")[0] == 2
    assert review("outcome", id=item, result="maybe", sha="a")[0] == 2
    assert review("outcome", id="f99", result="fixed", sha="a")[1]["error"]["code"] == "no-such-finding"
    assert review("outcome", id=answer["posted"][0]["id"], result="fixed", sha="a")[1]["error"]["code"] == "no-such-finding"


def test_begin_refuses_a_new_round_while_a_fix_has_no_outcome(review):
    begin(review)
    _, answer = review("record", findings=[finding("high")])
    code, refusal = begin(review)
    assert (code, refusal["error"]["code"]) == (1, "fix-open")
    assert answer["fix"][0]["id"] in refusal["error"]["reason"]


@pytest.mark.parametrize("findings", [[], [finding("low")]])
def test_begin_refuses_a_new_round_when_no_fix_waits_for_review(review, findings):
    begin(review)
    review("record", findings=findings)
    assert begin(review)[1]["error"]["code"] == "no-fix-to-review"


def test_begin_refuses_a_new_round_when_every_finding_stayed_unfixed(review):
    begin(review)
    _, answer = review("record", findings=[finding("high")])
    review("outcome", id=answer["fix"][0]["id"], result="unfixed", reason="needs a change outside the scope")
    assert begin(review)[1]["error"]["code"] == "no-fix-to-review"


def run_to_the_cap(review):
    """3 rounds: each finds one new high finding; rounds 1 and 2 fix theirs."""
    answers = []
    for number in (1, 2, 3):
        begin(review)
        _, answer = review("record", findings=[finding("high", f"round {number}")])
        answers.append(answer)
        if number < 3:
            fix_all(review, answer)
    return answers


def test_round_4_is_refused_whatever_is_left(review):
    answers = run_to_the_cap(review)
    fix_all(review, answers[2])
    code, answer = begin(review)
    assert (code, answer["error"]["code"]) == (1, "round-cap")
    rounds = json.loads((review.plan / "review" / "0001-a.rounds.json").read_text(encoding="utf-8"))["rounds"]
    assert rounds[-1]["round"] == 3


def test_finish_at_the_cap_posts_every_unfixed_finding_and_reports_it(review, forge):
    answers = run_to_the_cap(review)
    code, report = review("finish")
    assert (code, report["stopped_by"], report["rounds"]) == (0, "cap", 3)
    assert ids(report["left"]["blocking"]) == ids(answers[2]["fix"])
    assert report["left"]["blocking"][0]["url"]
    assert [item["reviewed"] for item in report["fixed"]] == [True, True]
    assert "round 3" in forge.calls[-1][1]["text"]
    assert begin(review)[1]["error"]["code"] == "review-over"


def test_a_fix_in_the_last_round_is_reported_as_not_reviewed(review, forge):
    answers = run_to_the_cap(review)
    fix_all(review, answers[2])
    _, report = review("finish")
    assert report["left"]["blocking"] == []
    assert [item["reviewed"] for item in report["fixed"]] == [True, True, False]
    assert forge.calls == []


def test_finish_after_a_round_with_nothing_to_fix_stops_clean(review):
    begin(review, deferred=[{"name": "resilience", "why": "no new call; costs no more later"}])
    review("record", findings=[finding("low")])
    code, report = review("finish")
    assert (code, report["stopped_by"], report["rounds"]) == (0, "clean", 1)
    assert report["left"]["blocking"] == []
    assert len(report["left"]["posted"]) == 1
    assert report["concerns"][0]["concerns"] == CONCERNS
    assert report["deferred"][0]["name"] == "resilience"


def test_finish_when_every_finding_stayed_unfixed_reports_the_reason(review, forge):
    begin(review)
    _, answer = review("record", findings=[finding("high")])
    review("outcome", id=answer["fix"][0]["id"], result="unfixed", reason="needs a change outside the scope")
    code, report = review("finish")
    assert (code, report["stopped_by"]) == (0, "unfixed")
    assert report["left"]["blocking"][0]["reason"] == "needs a change outside the scope"
    assert "needs a change outside the scope" in forge.calls[-1][1]["text"]


def test_finish_refuses_while_a_fix_waits_for_its_review(review):
    begin(review)
    _, answer = review("record", findings=[finding("high")])
    fix_all(review, answer)
    assert review("finish")[1]["error"]["code"] == "review-owed"


def test_finish_refuses_while_a_fix_has_no_outcome_before_the_cap(review):
    begin(review)
    review("record", findings=[finding("high")])
    assert review("finish")[1]["error"]["code"] == "fix-open"


def test_finish_refuses_an_open_round_and_a_review_that_never_started(review):
    assert review("finish")[1]["error"]["code"] == "no-review"
    begin(review)
    assert review("finish")[1]["error"]["code"] == "round-open"


def test_finish_twice_posts_nothing_twice(review, forge):
    run_to_the_cap(review)
    review("finish")
    count = len(forge.calls)
    _, again = review("finish")
    assert len(forge.calls) == count
    assert again["stopped_by"] == "cap"


def test_outcome_refuses_after_the_stop(review):
    answers = run_to_the_cap(review)
    review("finish")
    code, answer = review("outcome", id=answers[2]["fix"][0]["id"], result="fixed", sha="a")
    assert (code, answer["error"]["code"]) == (1, "review-over")


def test_a_failed_post_of_a_left_finding_stays_in_the_report_and_finish_tries_again(review, forge):
    run_to_the_cap(review)
    forge.answers = [{"ok": False, "error": {"code": "auth", "reason": "no login"}}]
    _, report = review("finish")
    assert [item["post_error"] for item in report["left"]["not_posted"]] == ["no login"]
    _, again = review("finish")
    assert again["left"]["not_posted"] == []
    assert again["left"]["blocking"][0]["url"]


GH_STUB = """
import json, os, sys
args = sys.argv[1:]
body = sys.stdin.read() if "--input" in args else ""
with open(os.environ["GH_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({"args": args, "body": body}) + "\\n")
if os.environ.get("GH_FAIL") and args[:1] == ["api"]:
    sys.stderr.write("HTTP 401: bad credentials\\n")
    sys.exit(1)
if args[:2] == ["repo", "view"]:
    print(json.dumps({"nameWithOwner": "o/r"}))
elif args[:2] == ["pr", "view"]:
    print(json.dumps({"number": 7, "headRefOid": "abc"}))
else:
    print(json.dumps({"id": 55, "html_url": "https://f.test/55"}))
"""


@pytest.fixture
def real_port(tmp_path, monkeypatch):
    """The real forge command in its own process, in a repository on GitHub, with a stub `gh` on PATH."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "gh_stub.py").write_text(GH_STUB, encoding="utf-8")
    if os.name == "nt":
        (stubs / "gh.cmd").write_text(f'@"{sys.executable}" "{stubs / "gh_stub.py"}" %*\r\n', encoding="utf-8", newline="")
    else:
        launcher = stubs / "gh"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{stubs / "gh_stub.py"}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "remote", "add", "origin", "https://github.com/o/r.git"], check=True)
    log = tmp_path / "gh.log"
    monkeypatch.chdir(repository)
    monkeypatch.setenv("PATH", str(stubs) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("GH_LOG", str(log))
    monkeypatch.delenv("GH_FAIL", raising=False)
    return log


def real_review(tmp_path, capsys, verb, **payload):
    plan = tmp_path / "plan"
    plan.mkdir(exist_ok=True)
    capsys.readouterr()
    code = review_rounds.main([verb, json.dumps({"plan": str(plan), "subtask": "0001-a", **payload})])
    return code, json.loads(capsys.readouterr().out)


def test_a_finding_reaches_the_change_through_the_real_forge_command(tmp_path, capsys, real_port):
    real_review(tmp_path, capsys, "begin", change="7", concerns=CONCERNS)
    code, answer = real_review(tmp_path, capsys, "record", findings=[finding("medium")])
    assert code == 0
    assert answer["posted"] == [{"id": "f1", "url": "https://f.test/55", "inline": True, "reason": None}]
    calls = [json.loads(line) for line in real_port.read_text(encoding="utf-8").splitlines()]
    post = next(call for call in calls if call["args"][:1] == ["api"])
    assert "repos/o/r/pulls/7/comments" in post["args"]
    sent = json.loads(post["body"])
    assert (sent["path"], sent["line"], sent["side"], sent["commit_id"]) == ("src/a.py", 3, "RIGHT", "abc")
    assert "the loop skips the last item" in sent["body"]


def test_a_refusal_of_the_real_forge_command_lands_in_post_failed(tmp_path, capsys, real_port, monkeypatch):
    monkeypatch.setenv("GH_FAIL", "1")
    real_review(tmp_path, capsys, "begin", change="7", concerns=CONCERNS)
    code, answer = real_review(tmp_path, capsys, "record", findings=[finding("medium")])
    assert code == 0
    assert answer["posted"] == []
    assert answer["post_failed"][0]["id"] == "f1" and answer["post_failed"][0]["reason"]


def test_a_forge_command_that_answers_no_json_is_a_failed_post(tmp_path, capsys, real_port, monkeypatch):
    broken = tmp_path / "broken.py"
    broken.write_text("print('not json')\n", encoding="utf-8")
    monkeypatch.setattr(review_rounds, "FORGE", broken)
    real_review(tmp_path, capsys, "begin", change="7", concerns=CONCERNS)
    _, answer = real_review(tmp_path, capsys, "record", findings=[finding("low")])
    assert "no answer" in answer["post_failed"][0]["reason"]


def test_a_payload_on_stdin_and_the_published_exit_codes(review, monkeypatch, capsys):
    plan = str(review.plan)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(
        {"plan": plan, "subtask": "0001-a", "change": "7", "concerns": CONCERNS}).encode("utf-8")), encoding="utf-8"))
    assert review_rounds.main(["begin"]) == 0
    assert json.loads(capsys.readouterr().out)["round"] == 1
    assert review_rounds.main(["nothing"]) == 2


def frontmatter(text):
    return dict(line.split(": ", 1) for line in text.split("---")[1].strip().splitlines())


def test_the_skill_has_its_frontmatter_and_names_every_verb_and_refusal():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    fields = frontmatter(text)
    assert fields["name"] == "code-review"
    assert fields["description"]
    for verb in review_rounds.VERBS:
        assert f"`{verb}`" in text
    source = (SKILL / "scripts" / "review_rounds.py").read_text(encoding="utf-8")
    for code in re.findall(r'Refusal\("([a-z-]+)"', source):
        if code != "bad-payload":
            assert f"`{code}`" in text


def test_the_skill_points_at_its_sibling_files_and_they_exist():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for name in re.findall(r"\]\(([A-Z]+\.md)\)", text):
        assert (SKILL / name).is_file()
    assert "CONCERNS.md" in text and "REVIEWER.md" in text


def test_the_reviewer_brief_asks_for_the_fields_record_needs():
    brief = (SKILL / "REVIEWER.md").read_text(encoding="utf-8")
    sample = json.loads(re.search(r"```json\n(.*?)```", brief, re.DOTALL).group(1))[0]
    sample.update(severity="low", line=1, file="a")
    assert review_rounds._checked_finding(sample, 0)["severity"] == "low"
    for severity in review_rounds.SEVERITIES:
        assert f"| {severity} |" in brief


@pytest.mark.parametrize("side", ["context", None])
def test_a_context_side_and_a_null_side_post_on_the_new_side(review, forge, side):
    begin(review)
    assert review("record", findings=[finding("low", side=side)])[0] == 0
    payload = forge.calls[0][1]
    assert payload["line"] == 3 and "side" not in payload


def test_next_says_when_no_round_reads_the_fix(review):
    answers = run_to_the_cap(review)
    assert [answer["next"] for answer in answers] == ["fix", "fix", "fix-then-finish"]


def test_the_same_text_at_another_line_of_one_round_is_another_defect(review, forge):
    begin(review)
    _, answer = review("record", findings=[{**finding("high", "missing null check"), "line": 10},
                                           {**finding("high", "missing null check"), "line": 90}])
    assert [item["line"] for item in answer["fix"]] == [10, 90]
    assert len(set(ids(answer["fix"]))) == 2


def test_the_same_text_at_a_moved_line_in_a_later_round_stays_one_defect(review):
    begin(review)
    _, first = review("record", findings=[{**finding("high", "h"), "line": 10}])
    fix_all(review, first)
    begin(review)
    _, second = review("record", findings=[{**finding("high", "h"), "line": 12}])
    assert ids(second["fix"]) == ids(first["fix"])
    assert second["fix"][0]["line"] == 12


def test_a_review_that_names_another_change_refuses(review):
    begin(review)
    code, answer = review("begin", change="8", concerns=CONCERNS)
    assert (code, answer["error"]["code"]) == (1, "change-mismatch")
    assert json.loads((review.plan / "review" / "0001-a.rounds.json").read_text(encoding="utf-8"))["change"] == "7"


def test_an_earlier_unfixed_finding_is_never_reported_as_clean(review):
    begin(review)
    _, answer = review("record", findings=[finding("high", "a"), finding("high", "b")])
    fix_all(review, {"fix": answer["fix"][:1]})
    review("outcome", id=answer["fix"][1]["id"], result="unfixed", reason="outside the scope")
    begin(review)
    review("record", findings=[])
    _, report = review("finish")
    assert report["stopped_by"] == "unfixed"
    assert ids(report["left"]["blocking"]) == [answer["fix"][1]["id"]]


def test_a_deferred_concern_that_runs_in_a_later_round_is_not_reported_as_deferred(review):
    deferred = [{"name": "tests", "why": "no test changed"}, {"name": "resilience", "why": "no new call"}]
    review("begin", change="7", concerns=CONCERNS, deferred=deferred)
    _, answer = review("record", findings=[finding("high")])
    fix_all(review, answer)
    review("begin", change="7", concerns=[{"name": "tests", "why": "the fix adds a test"}])
    review("record", findings=[])
    assert [item["name"] for item in review("finish")[1]["deferred"]] == ["resilience"]


@pytest.mark.parametrize("text", ["[]", "{}", "1"])
def test_a_forge_command_that_answers_no_envelope_is_a_failed_post(tmp_path, capsys, real_port, monkeypatch, text):
    broken = tmp_path / "broken.py"
    broken.write_text(f"print('{text}')\n", encoding="utf-8")
    monkeypatch.setattr(review_rounds, "FORGE", broken)
    real_review(tmp_path, capsys, "begin", change="7", concerns=CONCERNS)
    _, answer = real_review(tmp_path, capsys, "record", findings=[finding("low")])
    assert answer["post_failed"][0]["reason"] == "the forge command gave no answer object"
