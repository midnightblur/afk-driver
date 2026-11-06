"""Grill start takes over a finished session, and the end check reads a version 2 page (SDD §3 rows "grill start" and
"grill end check `gate`", §7 the coming-back flow; PLAN.md decisions D-23, D-24, D-25)."""

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
    found = failures(started)
    assert [line for line in found if line.startswith("question-open")] == [
        "question-open: q-1: Which formats for q-1? (who: product owner)"]


def test_a_dropped_question_without_a_reason_fails_the_end_check(repo):
    started = settled_once(questions=[question("q-1")])
    doc = read(started["doc"])
    doc["questions"][0].update(state="dropped", dropped={"reason": "  ", "note": "N-1", "round": 1})
    write(started["doc"], doc)
    assert failures(started) == ["drop-no-reason: q-1: Which formats for q-1?"]


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
    assert set(grill_log.gate(started["doc"], started["log"])) == {"ok", "passed"}


def test_a_page_with_no_questions_stories_or_examples_passes_as_before(repo):
    started = settled_once()
    answered = grill_log.gate(started["doc"], started["log"])
    assert set(answered) == {"ok", "passed"}


# ---- a pass after a take-over lists stale later documents and changed settled points (PRD AC-050, AC-051)


def later_documents(spec_dir):
    spec_dir = Path(spec_dir)
    for name in ("PRD.md", "SDD.md", "adr/requirements/0001-a.md", "adr/design/0001-b.md"):
        (spec_dir / name).parent.mkdir(parents=True, exist_ok=True)
        (spec_dir / name).write_text("# x\n", "utf-8")


def came_back(**lists):
    done = finished(**lists)
    later_documents(done["spec_dir"])
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


def test_changed_lists_each_entry_changed_after_the_take_over_and_not_a_new_one(repo):
    taken = came_back(sections=[section("s-old"), section("s-same")])
    build(taken, card("i-b"), sections=[section("s-old", "New text."), section("s-new")])
    answer(taken, "[round R-2]\ni-b accept")
    passed = grill_log.gate(taken["doc"], taken["log"])
    assert passed["changed"] == [{"id": "s-old", "kind": "section", "text": "Title of s-old"}]


def test_a_resume_while_a_round_waits_is_no_take_over_of_a_finished_round(repo):
    started = start()
    build(started, card("i-a"))
    page_round.take_over(started["doc"])
    answer(started, "[round R-1]\ni-a accept")
    rows(started["log"])
    doc = read(started["doc"])
    doc["session"]["takeovers"][0]["at"] = "2000-01-01T00:00:00Z"
    write(started["doc"], doc)
    assert set(grill_log.gate(started["doc"], started["log"])) == {"ok", "passed"}


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"})


def test_stale_names_the_plan_of_the_run_branch_when_git_holds_it(repo):
    git(repo, "init", "-q", "-b", "feat-x")
    git(repo, "commit", "-q", "--allow-empty", "-m", "base")
    git(repo, "checkout", "-q", "--orphan", "feat-x-run")
    (repo / "plan").mkdir()
    (repo / "plan" / "PLAN.md").write_text("# Plan\n", "utf-8")
    git(repo, "add", "plan/PLAN.md")
    git(repo, "commit", "-q", "-m", "plan")
    git(repo, "checkout", "-q", "-f", "feat-x")
    assert not (repo / "plan" / "PLAN.md").exists()
    taken = came_back()
    build(taken, card("i-b"))
    answer(taken, "[round R-2]\ni-b accept")
    assert grill_log.gate(taken["doc"], taken["log"])["stale"][-1] == "feat-x-run:plan/PLAN.md"


def test_the_run_suffix_is_the_one_of_the_plan_check():
    sys.path.insert(0, str(PLUGIN / "skills" / "to-subtasks" / "scripts"))
    import check_plan
    assert grill_log.RUN_SUFFIX == check_plan.RUN_SUFFIX
