"""Grill start takes over a finished session, and the end check reads a version 2 page (SDD §3 rows "grill start" and
"grill end check `gate`", §7 the coming-back flow; PLAN.md decisions D-24, D-25; `changed` measures from the last passed round, which supersedes
D-23)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
for _folder in (PLUGIN / "skills" / "grill" / "scripts", PLUGIN / "skills" / "use-lavish" / "scripts", PLUGIN / "engine"):
    sys.path.insert(0, str(_folder))

import grill_log  # noqa: E402
import grill_start  # noqa: E402
import page_round  # noqa: E402
import round_document as rd  # noqa: E402
from grill_common import Refusal  # noqa: E402

TICKET = "PROJ-1"
FINDING = {"cause": "finding", "text": "Wrote the part."}
ROWS = (("Policy", "developer: may export; guest denied; own orders; total required"), ("Staples", "none"),
        ("Examples", "WE-1 frequent, WE-2 edge, WE-3 risky"), ("Devil", "pass ran; findings resolved"))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A repository root with no git above it, whose config names the spec folder `specs`."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setattr(grill_start, "read_config", lambda: {"spec_folder": "specs", "tracker": {"kind": "jira"}})
    return root


def card(item_id, **extra):
    return {"id": item_id, "kind": "confirm", "body": {"type": "text", "id": f"{item_id}-body",
                                                       "props": {"text": f"Point {item_id}"}}, **extra}


def round_input(*cards, **lists):
    sent = {kind: [{"change": FINDING, **entry} for entry in value] for kind, value in lists.items()}
    return {"banner": {"settled": [], "unlocks": [], "parked": []}, "items": list(cards), **sent}


def section(section_id, text="Text."):
    return {"id": section_id, "title": f"Title of {section_id}", "state": "current",
            "body": {"type": "text", "id": f"{section_id}-text", "props": {"text": text}}}


def story(story_id):
    return {"id": story_id, "text": f"As a user, I do {story_id}."}


def example(example_id, kind, *stories):
    return {"id": example_id, "title": f"Example {example_id}", "kind": kind, "stories": list(stories),
            "body": {"type": "text", "props": {"text": "From 3 rows to 1 file."}}}


def question(question_id, **extra):
    return {"id": question_id, "who": ["product owner"], "question": f"Which formats for {question_id}?",
            "context": "The export.", "why": "It sets the scope.", "origin": {"card": "i-a"}, "state": "open", **extra}


def read(path):
    return json.loads(Path(path).read_text("utf-8"))


def write(path, doc):
    Path(path).write_text(json.dumps(doc), "utf-8")


def start():
    return grill_start.start(["--ticket", TICKET])


def session_of(started):
    return {"id": started["session"], "skill": "grill", "feature": TICKET, "ticket": TICKET}


def build(started, *cards, **lists):
    return rd.build_round_document(started["doc"], session_of(started), round_input(*cards, **lists))


def answer(started, raw):
    raw_file = Path(started["raw_file"])
    raw_file.write_text(raw, "utf-8")
    return page_round.ingest(started["doc"], raw_file)


def rows(log):
    for kind, text in ROWS:
        grill_log.write_row(log, kind, text)


def finished(**lists):
    """A grill whose 1 round settled card i-a by an accept mark and whose end check passed."""
    started = start()
    build(started, card("i-a"), **lists)
    answer(started, "[round R-1]\ni-a accept")
    grill_log.sync(started["doc"], started["log"])
    rows(started["log"])
    grill_log.gate(started["doc"], started["log"])
    return started


def failures(started):
    with pytest.raises(Refusal) as refused:
        grill_log.gate(started["doc"], started["log"])
    assert refused.value.code == "exit-gate"
    return refused.value.extra["failures"]


# ---- grill start takes over the newest finished session (PRD AC-048)


def test_start_on_a_finished_grill_answers_takeover_with_that_session_not_a_new_page(repo):
    done = finished()
    again = start()
    assert again["takeover"] == done["session"] and again["session"] == done["session"]
    assert again["doc"] == done["doc"] and again["resume"] is False
    assert grill_start.finished_session(Path(done["spec_dir"]) / "pages", done["log"]) == done["session"]
    assert sorted(p.name for p in (Path(done["spec_dir"]) / "pages").glob("grill-*.json")) == [Path(done["doc"]).name]


def test_a_second_start_finds_the_same_session(repo):
    done = finished()
    first, second = start(), start()
    assert first["session"] == second["session"] == done["session"]
    page_round.take_over(done["doc"])
    build(done, card("i-b"))
    grill_log.sync(done["doc"], done["log"])
    resumed = start()
    assert resumed["session"] == done["session"] and resumed["takeover"] is None and resumed["resume"] is True


def two_sessions(finished_one):
    """An older and a newer page of 1 answered round each; `finished_one` ("older" or "newer") passed its end check."""
    older = start()
    build(older, card("i-a"))
    answer(older, "[round R-1]\ni-a accept")
    pages = Path(older["doc"]).parent
    newer = {**older, "session": "s-29990101-000000", "doc": (pages / "grill-s-29990101-000000.json").as_posix(),
             "raw_file": (pages / "grill-s-29990101-000000.raw.txt").as_posix()}
    build(newer, card("i-b"))
    answer(newer, "[round R-1]\ni-b accept")
    rows(older["log"])
    done = {"older": older, "newer": newer}[finished_one]
    grill_log.gate(done["doc"], done["log"])
    for when, started in ((1_000_000_000, older), (2_000_000_000, newer)):
        os.utime(started["doc"], (when, when))
    return older, newer


def test_start_takes_over_the_newer_of_2_sessions_when_it_finished(repo):
    older, newer = two_sessions("newer")
    again = start()
    assert again["takeover"] == again["session"] == newer["session"] and again["resume"] is False


def test_an_older_finished_session_beside_a_newer_open_one_resumes_the_newer(repo):
    older, newer = two_sessions("older")
    again = start()
    assert again["session"] == newer["session"] and again["resume"] is True and again["takeover"] is None


def test_start_on_an_open_or_no_session_answers_no_takeover(repo):
    fresh = start()
    assert fresh["takeover"] is None and fresh["resume"] is False
    build(fresh, card("i-a"))
    resumed = start()
    assert resumed["takeover"] is None and resumed["resume"] is True and resumed["session"] == fresh["session"]
    assert grill_start.finished_session(Path(fresh["spec_dir"]) / "pages", fresh["log"]) is None


def test_a_taken_over_old_page_takes_the_upgrade(repo):
    done = finished()
    doc = read(done["doc"])
    doc["schema"] = "afkv2.page/1"
    write(done["doc"], doc)
    taken = start()
    assert taken["takeover"] == done["session"] and taken["doc"] == done["doc"]
    page_round.take_over(taken["doc"])
    built = rd.build_round_document(taken["doc"], session_of(taken),
                                    {**round_input(card("i-b"), sections=[section("s-intro")]), "upgrade": True})
    assert read(taken["doc"])["schema"] == "afkv2.page/2" and built["entries"] == ["s-intro"]


# ---- the end check on a version 2 page (PRD AC-044, AC-019, AC-047)


def settled_once(**lists):
    started = start()
    build(started, card("i-a"), **lists)
    answer(started, "[round R-1]\ni-a accept")
    rows(started["log"])
    return started


def test_an_open_question_for_others_fails_the_end_check_and_is_named(repo):
    started = settled_once(questions=[question("q-1"), question("q-2")])
    doc = read(started["doc"])
    doc["questions"][1].update(state="dropped", dropped={"reason": "Nobody owns it.", "note": "N-1", "round": 1})
    write(started["doc"], doc)
    assert failures(started) == ["question-open: q-1: Which formats for q-1? (who: product owner)"]


def test_a_dropped_question_without_a_reason_fails_the_end_check(repo):
    started = settled_once(questions=[question("q-1")])
    doc = read(started["doc"])
    doc["questions"][0].update(state="dropped", dropped={"reason": "  ", "note": "N-1", "round": 1})
    write(started["doc"], doc)
    assert failures(started) == ["drop-no-reason: q-1: Which formats for q-1?"]


def test_a_dropped_question_with_no_drop_record_fails_the_end_check(repo):
    started = settled_once(questions=[question("q-1")])
    doc = read(started["doc"])
    doc["questions"][0].update(state="dropped", dropped=None)
    write(started["doc"], doc)
    assert failures(started) == ["drop-no-reason: q-1: Which formats for q-1?"]


def test_a_version_1_page_takes_none_of_the_version_2_checks(repo):
    started = settled_once(questions=[question("q-1")])
    doc = read(started["doc"])
    doc["schema"] = "afkv2.page/1"
    write(started["doc"], doc)
    assert grill_log.gate(started["doc"], started["log"])["ok"] is True


def test_a_story_with_no_example_and_each_missing_kind_fail_the_end_check(repo):
    started = settled_once(stories=[story("st-1"), story("st-2")], examples=[example("ex-1", "frequent", "st-1")])
    assert failures(started) == ["story-without-example: st-2: As a user, I do st-2.",
                                 "kind-missing: no worked example of kind edge",
                                 "kind-missing: no worked example of kind risky"]


def test_every_story_covered_and_every_kind_present_passes(repo):
    started = settled_once(stories=[story("st-1")], examples=[
        example("ex-1", "frequent", "st-1"), example("ex-2", "edge", "st-1"), example("ex-3", "risky", "st-1")],
        questions=[question("q-1")])
    doc = read(started["doc"])
    doc["questions"][0].update(state="assumed", assumption={"text": "Only csv.", "card": "i-a", "round": 1})
    write(started["doc"], doc)
    assert set(grill_log.gate(started["doc"], started["log"])) == {"ok", "passed", "stale", "changed"}


def test_a_page_with_no_questions_stories_or_examples_passes_as_before(repo):
    started = settled_once()
    answered = grill_log.gate(started["doc"], started["log"])
    assert set(answered) == {"ok", "passed", "stale", "changed"}
    assert answered["stale"] == [] and answered["changed"] == []


# ---- a pass after a take-over lists stale later documents and changed settled points (PRD AC-050, AC-051)


LATER = ("PRD.md", "SDD.md", "adr/requirements/0001-a.md", "adr/design/0001-b.md")


def later_documents(spec_dir, names=LATER):
    spec_dir = Path(spec_dir)
    for name in names:
        (spec_dir / name).parent.mkdir(parents=True, exist_ok=True)
        (spec_dir / name).write_text("# x\n", "utf-8")


def came_back(names=LATER, **lists):
    done = finished(**lists)
    later_documents(done["spec_dir"], names)
    taken = start()
    assert taken["takeover"] == done["session"]
    page_round.take_over(taken["doc"])
    return taken


def test_a_grill_that_came_back_ends_only_after_its_end_check_passes_again(repo):
    taken = came_back()
    build(taken, card("i-b", carries=["i-a"]))
    grill_log.sync(taken["doc"], taken["log"])
    assert not grill_log.exit_gate_passed(taken["log"], taken["session"])
    assert any("round 2 has no answer" in line for line in failures(taken))
    answer(taken, "[round R-2]\ni-b accept")
    passed = grill_log.gate(taken["doc"], taken["log"])
    spec = taken["spec_dir"]
    assert passed["stale"] == [f"{spec}/PRD.md", f"{spec}/adr/requirements/0001-a.md", f"{spec}/SDD.md",
                               f"{spec}/adr/design/0001-b.md"]
    assert passed["changed"] == [{"id": "i-a", "kind": "card", "text": "Point i-a"}]
    assert grill_log.exit_gate_passed(taken["log"], taken["session"])



def test_a_pass_with_no_take_over_entry_still_names_each_later_document(repo):
    done = finished()
    later_documents(done["spec_dir"])
    build(done, card("i-b"))
    answer(done, "[round R-2]\ni-b accept")
    passed = grill_log.gate(done["doc"], done["log"])
    assert len(passed["stale"]) == 4 and passed["changed"] == []


@pytest.mark.parametrize("names", [("PRD.md",), ()])
def test_stale_leaves_out_each_later_document_that_does_not_exist(repo, names):
    taken = came_back(names)
    build(taken, card("i-b"))
    answer(taken, "[round R-2]\ni-b accept")
    assert grill_log.gate(taken["doc"], taken["log"])["stale"] == [f"{taken['spec_dir']}/{name}" for name in names]


def test_changed_lists_each_entry_changed_after_the_take_over_and_not_a_new_one(repo):
    taken = came_back(sections=[section("s-old"), section("s-same")])
    build(taken, card("i-b"), sections=[section("s-old", "New text."), section("s-new")])
    answer(taken, "[round R-2]\ni-b accept")
    passed = grill_log.gate(taken["doc"], taken["log"])
    assert passed["changed"] == [{"id": "s-old", "kind": "section", "text": "Title of s-old"}]


def test_a_grill_that_never_passed_lists_no_changed_point_after_a_resume(repo):
    started = start()
    build(started, card("i-a"))
    page_round.take_over(started["doc"])
    answer(started, "[round R-1]\ni-a accept")
    build(started, card("i-b", carries=["i-a"]))
    answer(started, "[round R-2]\ni-b accept")
    rows(started["log"])
    assert read(started["doc"])["session"]["takeovers"][0]["round"] == 1
    assert grill_log.gate(started["doc"], started["log"])["changed"] == []


def test_a_pass_with_no_take_over_entry_lists_a_point_a_later_card_carries(repo):
    done = finished()
    build(done, card("i-b", carries=["i-a"]))
    answer(done, "[round R-2]\ni-b accept")
    assert read(done["doc"])["session"]["takeovers"] == []
    assert grill_log.gate(done["doc"], done["log"])["changed"] == [{"id": "i-a", "kind": "card", "text": "Point i-a"}]


def test_a_second_comeback_lists_only_the_points_changed_since_the_last_pass(repo):
    taken = came_back(sections=[section("s-one"), section("s-two")])
    build(taken, card("i-b", carries=["i-a"]), sections=[section("s-one", "New text.")])
    answer(taken, "[round R-2]\ni-b accept")
    first = grill_log.gate(taken["doc"], taken["log"])["changed"]
    assert first == [{"id": "i-a", "kind": "card", "text": "Point i-a"},
                     {"id": "s-one", "kind": "section", "text": "Title of s-one"}]
    again = start()
    assert again["takeover"] == taken["session"]
    page_round.take_over(again["doc"])
    build(again, card("i-c", carries=["i-b"]), sections=[section("s-two", "New text.")])
    grill_log.sync(again["doc"], again["log"])
    assert "- Last pass: R2 · session " in Path(again["log"]).read_text("utf-8")
    answer(again, "[round R-3]\ni-c accept")
    second = grill_log.gate(again["doc"], again["log"])["changed"]
    assert second == [{"id": "i-b", "kind": "card", "text": "Point i-b"},
                      {"id": "s-two", "kind": "section", "text": "Title of s-two"}]
    assert grill_log.gate(again["doc"], again["log"])["changed"] == []
    assert Path(again["log"]).read_text("utf-8").count("- Last pass: ") == 1
    log_format = (PLUGIN / "skills" / "grill" / "GRILL-LOG-FORMAT.md").read_text("utf-8")
    assert "| Last pass | `gate`, `grill_start` | `- Last pass: R<n> · session <id>`" in log_format
    assert "keeps the `Last pass` row" in log_format


def test_a_comeback_on_a_log_with_no_last_pass_row_measures_from_the_take_over(repo):
    """A log from before the `Last pass` row: the take-over writes it at the passed round."""
    done = finished()
    log = Path(done["log"])
    log.write_text("".join(line for line in log.read_text("utf-8").splitlines(True)
                           if not line.startswith("- Last pass: ")), "utf-8")
    taken = start()
    assert taken["takeover"] == done["session"]
    assert f"- Last pass: R1 · session {done['session']}" in log.read_text("utf-8")
    page_round.take_over(taken["doc"])
    build(taken, card("i-b", carries=["i-a"]))
    answer(taken, "[round R-2]\ni-b accept")
    assert grill_log.gate(taken["doc"], taken["log"])["changed"] == [{"id": "i-a", "kind": "card", "text": "Point i-a"}]
    assert "- Last pass: R2 · session " in log.read_text("utf-8")


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"})


@pytest.mark.parametrize("only_on_origin", [False, True])
def test_stale_names_the_plan_of_the_run_branch_when_git_holds_it(repo, only_on_origin):
    git(repo, "init", "-q", "-b", "feat-x")
    git(repo, "commit", "-q", "--allow-empty", "-m", "base")
    git(repo, "checkout", "-q", "--orphan", "feat-x-run")
    (repo / "plan").mkdir()
    (repo / "plan" / "PLAN.md").write_text("# Plan\n", "utf-8")
    git(repo, "add", "plan/PLAN.md")
    git(repo, "commit", "-q", "-m", "plan")
    git(repo, "checkout", "-q", "-f", "feat-x")
    if only_on_origin:
        git(repo, "update-ref", "refs/remotes/origin/feat-x-run", "feat-x-run")
        git(repo, "branch", "-q", "-D", "feat-x-run")
    assert not (repo / "plan" / "PLAN.md").exists()
    taken = came_back()
    build(taken, card("i-b"))
    answer(taken, "[round R-2]\ni-b accept")
    assert grill_log.gate(taken["doc"], taken["log"])["stale"][-1] == "feat-x-run:plan/PLAN.md"


def test_the_run_suffix_is_the_one_of_the_plan_check():
    sys.path.insert(0, str(PLUGIN / "skills" / "to-subtasks" / "scripts"))
    import check_plan
    assert grill_log.RUN_SUFFIX == check_plan.RUN_SUFFIX


def passed_after_came_back(monkeypatch=None, run=None):
    taken = came_back()
    build(taken, card("i-b"))
    answer(taken, "[round R-2]\ni-b accept")
    if run is not None:
        monkeypatch.setattr(grill_log.subprocess, "run", run)
    return grill_log.gate(taken["doc"], taken["log"])


def test_stale_names_the_plan_as_not_checked_when_git_does_not_answer(repo, monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")
    stale = passed_after_came_back(monkeypatch, no_git)["stale"]
    assert stale[-1].startswith("<feature branch>-run:plan/PLAN.md (not checked: ") and len(stale) == 5


def test_the_git_calls_of_the_plan_check_share_one_time_limit(repo, monkeypatch):
    clock, limits = [0.0], []
    monkeypatch.setattr(grill_log.time, "monotonic", lambda: clock[0])

    def slow_git(command, **kwargs):
        limits.append(kwargs["timeout"])
        clock[0] += grill_log.GIT_LIMIT_S * 0.6
        if command[3] == "rev-parse":
            return subprocess.CompletedProcess(command, 0, b"feat-x\n", b"")
        return subprocess.CompletedProcess(command, 1, b"", b"")
    stale = passed_after_came_back(monkeypatch, slow_git)["stale"]
    assert limits == [grill_log.GIT_LIMIT_S, pytest.approx(grill_log.GIT_LIMIT_S * 0.4)]
    assert stale[-1].startswith("feat-x-run:plan/PLAN.md (not checked: ")
