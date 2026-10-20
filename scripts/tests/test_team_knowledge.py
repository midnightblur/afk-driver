"""Knowledge store module: entry lifecycle, finished stamp, per-stage read filter, debate release rule."""
from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from team import knowledge  # noqa: E402

FEATURE = "feat-x"
FIELDS = ("author", "role", "model", "time", "ground", "stage", "body", "finished",
          "work_item", "debate_step", "verdict", "reason")


def write(root, author="a1", role="builder", stage="execute", time=None, **extra):
    args = dict(author=author, role=role, model="opus", ground="scripts/x.py:1", stage=stage,
                body=f"note by {author}", time=time)
    args.update(extra)
    return knowledge.write_entry(root, FEATURE, **args)


def draft(root, author, role, time, work_item="W1", stage="design"):
    return write(root, author=author, role=role, stage=stage, time=time,
                 work_item=work_item, debate_step="draft")


def finish(root, entry):
    return knowledge.mark_finished(root, FEATURE, entry["author"], entry["time"])


def authors(entries):
    return [e["author"] for e in entries]


def files(root):
    return sorted(p.name for p in knowledge.store_path(root, FEATURE).iterdir())


# --- write entry ---

def test_write_entry_creates_an_unfinished_entry_with_every_field(tmp_path):
    entry = write(tmp_path, time="2026-10-19T08:00:00Z")
    assert entry == {"author": "a1", "role": "builder", "model": "opus", "time": "2026-10-19T08:00:00Z",
                     "ground": "scripts/x.py:1", "stage": "execute", "body": "note by a1",
                     "finished": False, "work_item": None, "debate_step": None, "verdict": None,
                     "reason": None}
    path = knowledge.store_path(tmp_path, FEATURE) / "20261019T080000Z-a1.json"
    stored = json.loads(path.read_text("utf-8"))
    assert stored == {"format_version": 1, **entry}
    assert files(tmp_path) == ["20261019T080000Z-a1.json"]


def test_store_is_one_file_per_entry_keyed_by_feature(tmp_path):
    write(tmp_path, author="a1", time="2026-10-19T08:00:00Z")
    write(tmp_path, author="a2", time="2026-10-19T08:00:00Z")
    write(tmp_path, author="a1", time="2026-10-19T08:00:01Z")
    assert knowledge.store_path(tmp_path, FEATURE) == tmp_path / FEATURE / "knowledge"
    assert len(files(tmp_path)) == 3


def test_time_defaults_to_now_in_utc_to_the_second(tmp_path):
    entry = write(tmp_path)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", entry["time"])


@pytest.mark.parametrize("bad", ["2026-10-19 08:00:00", "2026-10-19T08:00:00.5Z", "2026-10-19T08:00:00+00:00",
                                 "2026-13-40T08:00:00Z", "", 5])
def test_a_time_that_is_not_utc_iso_8601_to_the_second_is_refused(tmp_path, bad):
    with pytest.raises(knowledge.KnowledgeError, match="time"):
        write(tmp_path, time=bad)
    assert not knowledge.store_path(tmp_path, FEATURE).exists()


@pytest.mark.parametrize("field", ["author", "role", "model", "ground", "stage"])
@pytest.mark.parametrize("bad", [None, "", 3])
def test_each_identifying_field_is_required(tmp_path, field, bad):
    with pytest.raises(knowledge.KnowledgeError, match=field):
        write(tmp_path, **{field: bad})


def test_body_must_be_text(tmp_path):
    with pytest.raises(knowledge.KnowledgeError, match="body"):
        write(tmp_path, body=None)


@pytest.mark.parametrize("name", ["..", ".", "a/b", "a\\b", "a:b"])
def test_an_unsafe_author_or_feature_is_refused(tmp_path, name):
    with pytest.raises(knowledge.KnowledgeError):
        write(tmp_path, author=name)
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.store_path(tmp_path, name)


def test_a_second_entry_with_the_same_author_and_time_is_refused(tmp_path):
    write(tmp_path, time="2026-10-19T08:00:00Z", body="first")
    with pytest.raises(knowledge.KnowledgeError, match="already"):
        write(tmp_path, time="2026-10-19T08:00:00Z", body="second")
    [entry] = [json.loads(p.read_text("utf-8")) for p in knowledge.store_path(tmp_path, FEATURE).iterdir()]
    assert entry["body"] == "first"


# --- debate fields ---

def test_a_verdict_entry_without_a_reason_is_refused(tmp_path):
    for reason in (None, ""):
        with pytest.raises(knowledge.KnowledgeError, match="reason"):
            write(tmp_path, work_item="W1", debate_step="verdict", verdict="AGREE", reason=reason)
    assert not knowledge.store_path(tmp_path, FEATURE).exists()


@pytest.mark.parametrize("verdict", [None, "agree", "DISAGREE", "AGREE,DISAGREE-FINAL", ["AGREE"]])
def test_a_verdict_entry_carries_exactly_one_known_verdict(tmp_path, verdict):
    with pytest.raises(knowledge.KnowledgeError, match="verdict"):
        write(tmp_path, work_item="W1", debate_step="verdict", verdict=verdict, reason="because")


@pytest.mark.parametrize("step", ["draft", "critique", "revision"])
def test_only_a_verdict_entry_carries_a_verdict(tmp_path, step):
    with pytest.raises(knowledge.KnowledgeError, match="verdict"):
        write(tmp_path, work_item="W1", debate_step=step, verdict="AGREE")
    entry = write(tmp_path, work_item="W1", debate_step=step, reason="optional here")
    assert entry["reason"] == "optional here" and entry["verdict"] is None


@pytest.mark.parametrize("fields, word", [
    ({"reason": "no debate"}, "reason"),
    ({"verdict": "AGREE"}, "verdict"),
    ({"work_item": "W1"}, "work"),
    ({"debate_step": "draft"}, "work"),
    ({"work_item": "W1", "debate_step": "summary"}, "debate step"),
])
def test_debate_fields_stay_empty_outside_a_debate(tmp_path, fields, word):
    with pytest.raises(knowledge.KnowledgeError, match=word):
        write(tmp_path, **fields)
    assert not knowledge.store_path(tmp_path, FEATURE).exists()


# --- mark finished ---

def test_an_unfinished_entry_is_hidden_from_a_peer_until_its_author_marks_it(tmp_path):
    entry = write(tmp_path, author="a1", time="2026-10-19T08:00:00Z")
    assert knowledge.read_finished(tmp_path, FEATURE, ["execute"]) == []
    done = finish(tmp_path, entry)
    assert done == {**entry, "finished": True}
    assert knowledge.read_finished(tmp_path, FEATURE, ["execute"]) == [done]


def test_an_entry_from_an_agent_that_ended_early_stays_unfinished(tmp_path):
    entry = write(tmp_path, author="dead", time="2026-10-19T08:00:00Z")
    path = knowledge.store_path(tmp_path, FEATURE) / "20261019T080000Z-dead.json"
    before = path.read_bytes()
    for _ in range(3):
        assert knowledge.read_finished(tmp_path, FEATURE, ["execute"]) == []
    write(tmp_path, author="next", time="2026-10-19T08:00:05Z")
    assert path.read_bytes() == before
    assert json.loads(before)["finished"] is False and entry["finished"] is False


def test_mark_finished_on_an_unknown_entry_is_refused(tmp_path):
    entry = write(tmp_path, author="a1", time="2026-10-19T08:00:00Z")
    with pytest.raises(knowledge.KnowledgeError, match="no entry"):
        knowledge.mark_finished(tmp_path, FEATURE, "a2", entry["time"])
    with pytest.raises(knowledge.KnowledgeError, match="no entry"):
        knowledge.mark_finished(tmp_path, FEATURE, "a1", "2026-10-19T08:00:01Z")


def test_mark_finished_again_changes_nothing(tmp_path):
    entry = write(tmp_path, time="2026-10-19T08:00:00Z")
    first = finish(tmp_path, entry)
    path = knowledge.store_path(tmp_path, FEATURE) / "20261019T080000Z-a1.json"
    before = path.read_bytes()
    assert finish(tmp_path, entry) == first
    assert path.read_bytes() == before


def test_mark_finished_keeps_every_other_field_and_leaves_no_temporary_file(tmp_path):
    entry = write(tmp_path, time="2026-10-19T08:00:00Z", work_item="W1", debate_step="verdict",
                  verdict="DISAGREE-FINAL", reason="the lock can be stolen")
    done = finish(tmp_path, entry)
    assert {k: v for k, v in done.items() if k != "finished"} == {k: v for k, v in entry.items() if k != "finished"}
    assert files(tmp_path) == ["20261019T080000Z-a1.json"]


# --- per-stage read filter ---

def test_a_later_stage_reads_earlier_stages_and_a_stage_outside_the_list_is_not_read(tmp_path):
    design = finish(tmp_path, write(tmp_path, author="d1", stage="design", time="2026-10-19T08:00:00Z"))
    execute = finish(tmp_path, write(tmp_path, author="e1", stage="execute", time="2026-10-19T09:00:00Z"))
    finish(tmp_path, write(tmp_path, author="r1", stage="review", time="2026-10-19T10:00:00Z"))
    assert knowledge.read_finished(tmp_path, FEATURE, ["execute"]) == [execute]
    assert knowledge.read_finished(tmp_path, FEATURE, ["design", "execute"]) == [design, execute]


@pytest.mark.parametrize("stages", ["execute", b"execute", 5, [None], ["execute", ""], [["execute"]]])
def test_stages_that_are_not_a_list_of_stage_names_are_refused(tmp_path, stages):
    with pytest.raises(knowledge.KnowledgeError, match="stage"):
        knowledge.read_finished(tmp_path, FEATURE, stages)


@pytest.mark.parametrize("debaters", [[("W1", ["pro"])], "W1", 5])
def test_debaters_that_are_not_a_map_are_refused(tmp_path, debaters):
    with pytest.raises(knowledge.KnowledgeError, match="debater"):
        knowledge.read_finished(tmp_path, FEATURE, ["design"], debaters)


@pytest.mark.parametrize("roles", ["pro", b"pro", 5, [None], ["pro", ""], [["pro"]], [{"pro"}]])
def test_debater_roles_that_are_not_a_list_of_role_names_are_refused(tmp_path, roles):
    finish(tmp_path, draft(tmp_path, "p1", "pro", "2026-10-19T08:00:00Z"))
    with pytest.raises(knowledge.KnowledgeError, match="W1"):
        knowledge.read_finished(tmp_path, FEATURE, ["design"], {"W1": roles})


def test_a_failed_write_leaves_no_partial_file_in_the_store(tmp_path, monkeypatch):
    real = Path.write_text

    def torn(self, data, *args, **kwargs):
        real(self, data[:10], *args, **kwargs)
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", torn)
    with pytest.raises(OSError, match="disk full"):
        write(tmp_path, time="2026-10-19T08:00:00Z")
    assert files(tmp_path) == []
    monkeypatch.setattr(Path, "write_text", real)
    entry = write(tmp_path, time="2026-10-19T08:00:00Z")
    monkeypatch.setattr(Path, "write_text", torn)
    with pytest.raises(OSError, match="disk full"):
        finish(tmp_path, entry)
    assert files(tmp_path) == ["20261019T080000Z-a1.json"]
    assert json.loads((knowledge.store_path(tmp_path, FEATURE) / files(tmp_path)[0]).read_text("utf-8"))["finished"] is False


def test_a_read_returns_entries_ordered_by_time_then_author(tmp_path):
    for author, time in (("b", "2026-10-19T08:00:01Z"), ("c", "2026-10-19T08:00:00Z"), ("a", "2026-10-19T08:00:01Z")):
        finish(tmp_path, write(tmp_path, author=author, time=time))
    assert authors(knowledge.read_finished(tmp_path, FEATURE, ["execute"])) == ["c", "a", "b"]


def test_a_read_of_a_store_that_does_not_exist_is_empty(tmp_path):
    assert knowledge.read_finished(tmp_path, FEATURE, ["execute"]) == []


def test_read_finished_writes_nothing(tmp_path):
    finish(tmp_path, write(tmp_path, time="2026-10-19T08:00:00Z"))
    write(tmp_path, author="a2", time="2026-10-19T08:00:01Z")
    before = {p.name: p.read_bytes() for p in knowledge.store_path(tmp_path, FEATURE).iterdir()}
    knowledge.read_finished(tmp_path, FEATURE, ["execute"], {"W1": ["pro", "con"]})
    assert {p.name: p.read_bytes() for p in knowledge.store_path(tmp_path, FEATURE).iterdir()} == before


# --- debate release rule ---

ROLES = {"W1": ["pro", "con"]}


def test_a_peer_draft_is_released_only_when_every_debater_role_has_a_finished_draft(tmp_path):
    pro = finish(tmp_path, draft(tmp_path, "p1", "pro", "2026-10-19T08:00:00Z"))
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"], ROLES) == []
    con = draft(tmp_path, "c1", "con", "2026-10-19T08:00:01Z")
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"], ROLES) == []
    con = finish(tmp_path, con)
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"], ROLES) == [pro, con]


def test_a_role_that_has_written_nothing_holds_the_release_back(tmp_path):
    finish(tmp_path, draft(tmp_path, "p1", "pro", "2026-10-19T08:00:00Z"))
    finish(tmp_path, draft(tmp_path, "c1", "con", "2026-10-19T08:00:01Z"))
    three = {"W1": ["pro", "con", "judge"]}
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"], three) == []


def test_a_debater_that_dies_with_its_draft_unfinished_releases_nothing(tmp_path):
    finish(tmp_path, draft(tmp_path, "p1", "pro", "2026-10-19T08:00:00Z"))
    draft(tmp_path, "c1", "con", "2026-10-19T08:00:01Z")
    for _ in range(2):
        assert knowledge.read_finished(tmp_path, FEATURE, ["design"], ROLES) == []


def test_a_replacements_finished_draft_fills_the_role_and_the_dead_draft_is_skipped(tmp_path):
    pro = finish(tmp_path, draft(tmp_path, "p1", "pro", "2026-10-19T08:00:00Z"))
    draft(tmp_path, "c1", "con", "2026-10-19T08:00:01Z")
    replacement = finish(tmp_path, draft(tmp_path, "c2", "con", "2026-10-19T08:30:00Z"))
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"], ROLES) == [pro, replacement]


def test_the_release_counts_roles_per_work_item(tmp_path):
    finish(tmp_path, draft(tmp_path, "p1", "pro", "2026-10-19T08:00:00Z", work_item="W1"))
    finish(tmp_path, draft(tmp_path, "c1", "con", "2026-10-19T08:00:01Z", work_item="W2"))
    roles = {"W1": ["pro", "con"], "W2": ["pro", "con"]}
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"], roles) == []


def test_a_draft_whose_work_item_has_no_debater_roles_is_withheld(tmp_path):
    finish(tmp_path, draft(tmp_path, "p1", "pro", "2026-10-19T08:00:00Z"))
    finish(tmp_path, draft(tmp_path, "c1", "con", "2026-10-19T08:00:01Z"))
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"]) == []
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"], {"W2": ["pro"]}) == []
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"], {"W1": []}) == []


def test_the_work_item_not_the_stage_governs_reads_between_debate_steps(tmp_path):
    pro = finish(tmp_path, draft(tmp_path, "p1", "pro", "2026-10-19T08:00:00Z", stage="design"))
    con = finish(tmp_path, draft(tmp_path, "c1", "con", "2026-10-19T08:00:01Z", stage="review"))
    assert knowledge.read_finished(tmp_path, FEATURE, ["execute"], ROLES) == [pro, con]


def test_finished_critique_revision_and_verdict_entries_are_read_without_the_draft_rule(tmp_path):
    critique = finish(tmp_path, write(tmp_path, author="p1", role="pro", stage="design", time="2026-10-19T09:00:00Z",
                                      work_item="W1", debate_step="critique"))
    write(tmp_path, author="c1", role="con", stage="design", time="2026-10-19T09:00:01Z",
          work_item="W1", debate_step="revision")
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"], ROLES) == [critique]


def test_verdicts_are_returned_one_entry_per_agent_never_combined(tmp_path):
    agree = finish(tmp_path, write(tmp_path, author="p1", role="pro", stage="design", time="2026-10-19T10:00:00Z",
                                   work_item="W1", debate_step="verdict", verdict="AGREE", reason="holds"))
    final = finish(tmp_path, write(tmp_path, author="c1", role="con", stage="design", time="2026-10-19T10:00:01Z",
                                   work_item="W1", debate_step="verdict", verdict="DISAGREE-FINAL",
                                   reason="the race stays open"))
    entries = knowledge.read_finished(tmp_path, FEATURE, ["design"], ROLES)
    assert entries == [agree, final]
    assert all(set(e) == set(FIELDS) for e in entries)
    assert [(e["verdict"], e["reason"]) for e in entries] == [("AGREE", "holds"),
                                                             ("DISAGREE-FINAL", "the race stays open")]


# --- version rule and damaged files ---

def test_an_entry_of_an_unknown_format_version_is_not_read_not_changed_and_reported_once(tmp_path, capsys):
    store = knowledge.store_path(tmp_path, FEATURE)
    finish(tmp_path, write(tmp_path, author="a1", time="2026-10-19T08:00:00Z"))
    foreign = store / "20261019T080001Z-a2.json"
    payload = {"format_version": 2, "author": "a2", "time": "2026-10-19T08:00:01Z", "stage": "execute",
               "finished": True}
    foreign.write_text(json.dumps(payload), "utf-8")
    before = foreign.read_bytes()
    assert authors(knowledge.read_finished(tmp_path, FEATURE, ["execute"])) == ["a1"]
    assert authors(knowledge.read_finished(tmp_path, FEATURE, ["execute"])) == ["a1"]
    assert capsys.readouterr().err.count("20261019T080001Z-a2.json") == 1
    with pytest.raises(knowledge.KnowledgeError, match="format version"):
        knowledge.mark_finished(tmp_path, FEATURE, "a2", "2026-10-19T08:00:01Z")
    assert foreign.read_bytes() == before


FINISHED_CON = {"format_version": 1, "author": "c1", "role": "con", "model": "opus", "time": "2026-10-19T08:00:01Z",
                "ground": "scripts/x.py:1", "stage": "design", "body": "b", "finished": True, "work_item": "W1",
                "debate_step": "draft", "verdict": None, "reason": None}


@pytest.mark.parametrize("name, text, why", [
    ("20261019T080001Z-c1.json", "{not json", "unreadable"),
    ("20261019T080001Z-c1.json", "[]", "not a JSON object"),
    ("20261019T080001Z-c1.json", '{"format_version": 1, "author": "c1"}', "exactly"),
    ("20261019T080001Z-c1.json", json.dumps({**FINISHED_CON, "extra": 1}), "exactly"),
    ("20261019T080002Z-c1.json", json.dumps(FINISHED_CON), "file name"),
    ("20261019T080001Z-c2.json", json.dumps(FINISHED_CON), "file name"),
])
def test_a_damaged_entry_file_is_skipped_and_counts_as_no_finished_draft(tmp_path, capsys, name, text, why):
    finish(tmp_path, draft(tmp_path, "p1", "pro", "2026-10-19T08:00:00Z"))
    (knowledge.store_path(tmp_path, FEATURE) / name).write_text(text, "utf-8")
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"], ROLES) == []
    err = capsys.readouterr().err
    assert name in err and why in err


def test_the_damaged_file_cases_differ_from_a_good_file_only_in_the_damage(tmp_path):
    pro = finish(tmp_path, draft(tmp_path, "p1", "pro", "2026-10-19T08:00:00Z"))
    (knowledge.store_path(tmp_path, FEATURE) / "20261019T080001Z-c1.json").write_text(json.dumps(FINISHED_CON), "utf-8")
    con = {k: v for k, v in FINISHED_CON.items() if k != "format_version"}
    assert knowledge.read_finished(tmp_path, FEATURE, ["design"], ROLES) == [pro, con]


# --- location and promotion ---

def test_the_store_under_the_ignored_agent_directory_is_excluded_from_version_control():
    path = knowledge.store_path(REPO / ".claude" / "team", FEATURE) / "20261019T080000Z-a1.json"
    result = subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=REPO)
    assert result.returncode == 0


def test_the_module_offers_no_way_out_of_the_store_and_writes_nothing_outside_it(tmp_path):
    entry = write(tmp_path, author="a1", time="2026-10-19T08:00:00Z", work_item="W1", debate_step="verdict",
                  verdict="AGREE", reason="holds")
    finish(tmp_path, entry)
    knowledge.read_finished(tmp_path, FEATURE, ["execute"], ROLES)
    store = knowledge.store_path(tmp_path, FEATURE)
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert written and all(store in p.parents for p in written)
    public = {name for name, value in vars(knowledge).items() if not name.startswith("_")
              and inspect.isfunction(value) and value.__module__ == knowledge.__name__}
    assert public == {"write_entry", "mark_finished", "read_finished", "store_path"}
