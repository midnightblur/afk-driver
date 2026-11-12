"""The small lane: the lane line, the diagnosis verdict, no code before the go, the grow stop, the small gate."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[1].parent
SKILL = AFKV2 / "skills" / "small-change"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(AFKV2 / "scripts"))
sys.path.insert(0, str(AFKV2 / "ports"))

import gate_record  # noqa: E402
import small_lane  # noqa: E402
from tracker.envelope import Refusal  # noqa: E402

PY = f'"{sys.executable}"'
VERDICT = {"provider": "codex", "model": "m", "effort": "medium", "seen": ["The log shows the link answers 200."],
           "compare": ["It matches the row."], "checks": [{"check": "VC-4", "result": "pass", "why": "it asserts"}],
           "result": "pass"}


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=60,
                          stdin=subprocess.DEVNULL)
    assert done.returncode == 0, f"git {args}: {done.stderr}"
    return done.stdout.strip()


def commit(repo, name, text, message):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    commit(root, "src/app.py", "VALUE = 1\n", "seed")
    commit(root, "tests/check.py", "import sys\nfrom pathlib import Path\n"
           "sys.exit(0 if 'VALUE = 2' in Path('src/app.py').read_text() else 1)\n", "the check")
    return root


def call(verb, **payload):
    try:
        return small_lane.VERBS[verb](payload)
    except Refusal as refusal:
        return {"ok": False, "error": {"code": refusal.code, "reason": refusal.reason}}


def code_of(answer):
    return None if answer.get("ok") else answer["error"]["code"]


def page(tmp_path, card, signal="sign"):
    """A page document whose card holds the developer's mark, as page_round ingest stores it."""
    settled = {"by": "mark", "signal": signal}
    item = {"id": card, "kind": "signoff", "state": "settled_by_mark" if signal == "sign" else "open", "settled": settled}
    doc = tmp_path / "pages" / "small.json"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(json.dumps({"rounds": [{"items": [item]}]}), encoding="utf-8")
    return doc


def started(repo, kind="bug"):
    answer = call("start", repo=str(repo), kind=kind, why="1 file, 1 behavior, no format another skill reads")
    assert answer["ok"], answer
    return answer


def gone(repo, tmp_path, kind="bug"):
    started(repo, kind)
    if kind == "bug":
        assert call("diagnose", repo=str(repo), verdict="one-fix", cause="VALUE is 1 where the spec says 2")["ok"]
    answer = call("go", repo=str(repo), doc=str(page(tmp_path, "c-go")), card="c-go", test_plan="api: the check reads 2")
    assert answer["ok"], answer
    return answer


# --- the lane line --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["bug", "enhancement"])
def test_a_bug_or_a_small_enhancement_takes_the_small_lane_with_a_1_line_reason(repo, kind):
    answer = started(repo, kind)
    assert answer["line"] == f"Lane: small ({kind}): 1 file, 1 behavior, no format another skill reads"
    assert "\n" not in answer["line"]
    assert answer["base"] == git(repo, "rev-parse", "HEAD")
    assert Path(answer["doc"]).name == f"small-change-{answer['session']}.json"
    assert Path(answer["raw_file"]).name == f"small-change-{answer['session']}.raw.txt"


def test_start_refuses_another_kind_and_a_reason_of_more_than_1_line(repo):
    assert code_of(call("start", repo=str(repo), kind="feature", why="x")) == "bad-payload"
    assert code_of(call("start", repo=str(repo), kind="bug", why="one\ntwo")) == "bad-payload"


# --- the diagnosis --------------------------------------------------------------------------------------------------

def test_a_bug_ends_its_diagnosis_in_1_of_the_5_verdicts(repo):
    started(repo)
    assert code_of(call("diagnose", repo=str(repo), verdict="probably-fixed", cause="x")) == "bad-payload"
    for verdict in small_lane.VERDICTS:
        assert call("diagnose", repo=str(repo), verdict=verdict, cause="the cause")["ok"]
    text = (SKILL / "DIAGNOSIS.md").read_text(encoding="utf-8")
    for verdict in small_lane.VERDICTS:
        assert f"`{verdict}`" in text


def test_a_bug_gets_no_go_before_its_diagnosis(repo, tmp_path):
    started(repo)
    answer = call("go", repo=str(repo), doc=str(page(tmp_path, "c-go")), card="c-go", test_plan="api")
    assert code_of(answer) == "no-diagnosis"


# --- the go ---------------------------------------------------------------------------------------------------------

def test_go_refuses_no_go_mark_without_the_developers_sign_mark(repo, tmp_path):
    started(repo, "enhancement")
    doc = page(tmp_path, "c-go", signal="note")
    assert code_of(call("go", repo=str(repo), doc=str(doc), card="c-go", test_plan="api")) == "no-go-mark"
    assert code_of(call("go", repo=str(repo), doc=str(page(tmp_path, "c-go")), card="c-other", test_plan="api")) == "no-go-mark"


def test_go_records_the_card_the_head_and_the_time(repo, tmp_path):
    answer = gone(repo, tmp_path)
    go = small_lane.read_lane(repo)["go"]
    assert go["card"] == "c-go" and go["head"] == git(repo, "rev-parse", "HEAD") and go["at"]
    assert answer["go"] == go
    assert (Path(answer["folder"]) / small_lane.TEST_PLAN).read_text(encoding="utf-8").strip() == "api: the check reads 2"


def test_go_refuses_code_before_go_for_a_code_commit_or_an_uncommitted_code_file(repo, tmp_path):
    started(repo, "enhancement")
    doc = page(tmp_path, "c-go")
    (repo / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert code_of(call("go", repo=str(repo), doc=str(doc), card="c-go", test_plan="api")) == "code-before-go"
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "early fix")
    assert code_of(call("go", repo=str(repo), doc=str(doc), card="c-go", test_plan="api")) == "code-before-go"


def test_a_test_file_before_the_go_is_no_code(repo, tmp_path):
    started(repo, "enhancement")
    commit(repo, "tests/test_more.py", "def test_x():\n    pass\n", "a test")
    assert call("go", repo=str(repo), doc=str(page(tmp_path, "c-go")), card="c-go", test_plan="api")["ok"]


def test_a_page_file_of_the_spec_folder_is_no_code(repo, tmp_path):
    commit(repo, ".afkv2/config.json", json.dumps({"spec_folder": "docs/afk", "forge": "github"}), "config")
    started(repo, "enhancement")
    commit(repo, "docs/afk/1/pages/small-change-s-1.json", "{}", "the page round")
    (repo / "docs" / "afk" / "1" / "pages" / "small-change-s-1.raw.txt").write_text("x", encoding="utf-8")
    assert call("go", repo=str(repo), doc=str(page(tmp_path, "c-go")), card="c-go", test_plan="api")["ok"]
    assert small_lane._code_changes(repo, small_lane.read_lane(repo)["base"]) == []


def test_the_go_mark_function_is_record_go(repo, tmp_path):
    started(repo, "enhancement")
    go = small_lane.record_go(repo, page(tmp_path, "c-go"), "c-go", "api")
    assert go["card"] == "c-go"


# --- the grow stop --------------------------------------------------------------------------------------------------

def test_work_that_grows_stops_the_lane_and_proposes_the_medium_lane(repo, tmp_path):
    gone(repo, tmp_path)
    answer = call("grow", repo=str(repo), reason="the fix changes a format other skills read")
    assert answer["ok"] and "medium lane" in answer["proposal"] and "a format other skills read" in answer["proposal"]
    assert code_of(call("before", repo=str(repo), command=f"{PY} tests/check.py")) == "grew-past-small"
    assert code_of(call("gate", repo=str(repo), behavior="b", level="api", command="x", session="claude")) == "grew-past-small"


# --- before and after -----------------------------------------------------------------------------------------------

def test_before_records_the_failing_high_level_test_before_the_fix(repo, tmp_path):
    gone(repo, tmp_path)
    answer = call("before", repo=str(repo), command=f"{PY} tests/check.py")
    assert answer["ok"] and answer["exit"] != 0
    assert Path(answer["log"]).is_file()


def test_before_refuses_a_test_that_passes_and_a_fix_already_made(repo, tmp_path):
    gone(repo, tmp_path)
    assert code_of(call("before", repo=str(repo), command=f"{PY} -c \"pass\"")) == "not-red"
    commit(repo, "src/app.py", "VALUE = 2\n", "the fix")
    assert code_of(call("before", repo=str(repo), command=f"{PY} tests/check.py")) == "fix-before-before"


class FakeJudge:
    def __init__(self, result="pass"):
        self.result, self.folders = result, []

    def __call__(self, folder, session):
        self.folders.append(sorted(path.relative_to(folder).as_posix() for path in Path(folder).rglob("*")))
        rows = json.loads((Path(folder) / "rows.json").read_text(encoding="utf-8"))
        return {"verdicts": {row["id"]: {**VERDICT, "result": self.result} for row in rows}}


def gate(repo, judge, **extra):
    payload = {"repo": str(repo), "behavior": "the check reads 2", "level": "api", "command": f"{PY} tests/check.py",
               "test": "tests/check.py", "session": "claude", **extra}
    try:
        return small_lane.gate(payload, judge=judge)
    except Refusal as refusal:
        return {"ok": False, "error": {"code": refusal.code, "reason": refusal.reason}}


def test_the_small_gate_writes_a_small_lane_gate_record_with_before_and_after(repo, tmp_path):
    gone(repo, tmp_path)
    assert call("before", repo=str(repo), command=f"{PY} tests/check.py")["ok"]
    head = commit(repo, "src/app.py", "VALUE = 2\n", "the fix")
    judge = FakeJudge()
    answer = gate(repo, judge)
    assert answer["ok"] and answer["result"] == "pass", answer
    record = gate_record.read(answer["path"])
    assert record["lane"] == "small" and record["head"] == head
    assert record["go"]["card"] == "c-go"
    (row,) = record["rows"]
    assert row["level"] == "api" and row["result"] == "pass" and row["verdict"]["result"] == "pass"
    names = [Path(item["path"]).name for item in row["runs"][0]["evidence"]]
    assert "before.log" in names
    assert any(name.endswith("evidence/SL-1/before.log") for name in judge.folders[0])
    assert any(name.endswith("tests/tests/check.py") or name == "tests/tests/check.py" for name in judge.folders[0])
    assert gate_record.verify(answer["path"], gate_record.proof_lines(record), head, spec_folder="docs", repo=repo)["ok"]


def test_the_small_gate_refuses_no_go_mark_and_code_before_go(repo, tmp_path):
    started(repo, "enhancement")
    assert code_of(gate(repo, FakeJudge())) == "no-go-mark"
    gone(repo, tmp_path, "enhancement")
    lane = small_lane.read_lane(repo)
    commit(repo, "src/early.py", "x = 1\n", "code before the go")
    lane["go"]["head"] = git(repo, "rev-parse", "HEAD")  # a go recorded after a code commit
    small_lane._save_lane(repo, lane)
    assert code_of(gate(repo, FakeJudge())) == "code-before-go"


def test_the_small_gate_takes_only_a_high_level_test(repo, tmp_path):
    gone(repo, tmp_path, "enhancement")
    assert code_of(gate(repo, FakeJudge(), level="unit")) == "bad-payload"


def test_a_bug_needs_its_before_evidence_at_the_gate(repo, tmp_path):
    gone(repo, tmp_path)
    commit(repo, "src/app.py", "VALUE = 2\n", "the fix")
    assert code_of(gate(repo, FakeJudge())) == "no-before"


def test_a_failed_fix_fails_the_gate_and_no_judge_runs(repo, tmp_path):
    gone(repo, tmp_path, "enhancement")
    judge = FakeJudge()
    answer = gate(repo, judge)
    assert answer["ok"] and answer["result"] == "fail"
    assert judge.folders == []


def test_a_gate_again_at_the_same_head_keeps_the_cited_evidence_and_only_asks_the_judge(repo, tmp_path):
    gone(repo, tmp_path, "enhancement")
    commit(repo, "tests/check.py", "import sys, time\nfrom pathlib import Path\nprint(time.time_ns())\n"
           "sys.exit(0 if 'VALUE = 2' in Path('src/app.py').read_text() else 1)\n", "a check with its time")
    commit(repo, "src/app.py", "VALUE = 2\n", "the fix")

    def no_judge(folder, session):
        raise small_lane.afkv2_config.Refusal("no-provider", "no other provider")

    first = gate(repo, no_judge)
    assert first["ok"] and first["result"] == "pass" and first["judge"].startswith("judge: no-provider"), first
    judge = FakeJudge()
    again = gate(repo, judge)
    assert again["ok"] and again["written"] is False and again["verdict"] == "pass" and again["judge"] is None
    assert len(judge.folders) == 1
    folder = Path(again["path"]).parent
    (row,) = gate_record.read(again["path"])["rows"]
    assert [gate_record._changed_file(folder, item) for item in gate_record._stored_files(row)] == \
        [None] * len(gate_record._stored_files(row))


def test_the_fix_proposers_run_the_engine_with_their_own_adapter():
    import small_proposers as sp
    assert sp.VERBS == sp.engine.VERBS and "plan" in sp.VERBS
    assert sp.ADAPTER.prefix == "small" and sp.ADAPTER.noun == "fix"
    assert sp.state_path("x/small-change-s-1.json").name == "small-change-s-1.proposers.json"


def test_the_real_command_answers_one_object(repo, tmp_path):
    script = SKILL / "scripts" / "small_lane.py"
    done = subprocess.run([sys.executable, str(script), "start"], cwd=repo, capture_output=True, timeout=120,
                          input=json.dumps({"kind": "bug", "why": "1 file"}).encode("utf-8"))
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["line"] == "Lane: small (bug): 1 file"


def test_the_skill_names_each_verb_and_refusal_code():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert re.search(r"^name: small-change$", text, re.MULTILINE)
    source = (SKILL / "scripts" / "small_lane.py").read_text(encoding="utf-8")
    for verb in small_lane.VERBS:
        assert f"`{verb}`" in text
    for code in re.findall(r'Refusal\("([a-z-]+)"', source):
        assert f"`{code}`" in text


PROBE = f'"{Path(sys.executable).as_posix()}" -c "import sys; print(sys.argv[1:])" /api/orders --path=/v1/x'
UNCHANGED = "['/api/orders', '--path=/v1/x']"


def test_a_small_lane_command_gets_its_posix_path_arguments_unchanged(tmp_path):
    out = tmp_path / "out.log"
    with out.open("wb") as output:
        assert small_lane._run(PROBE, tmp_path, output) == 0
    assert UNCHANGED in out.read_text(encoding="utf-8")
