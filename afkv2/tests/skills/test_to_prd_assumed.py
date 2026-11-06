"""The assumed answers of a grill page reach the requirements: `start` lists them, PRD-FORMAT.md writes each as a risk."""

import json
import shutil
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
SKILL_DIR = PLUGIN / "skills" / "to-prd"
FAKES = Path(__file__).resolve().parent / "fakes"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(PLUGIN / "tests" / "engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import prd_files  # noqa: E402
import pytest  # noqa: E402
from grill_common import Refusal  # noqa: E402
from test_page_parts_v2 import document, question  # noqa: E402
from test_to_prd import KEY, World  # noqa: E402

ASSUMED = {"question": "q-assume", "text": "May the file be zipped?", "who": ["Developer lead"],
           "assumption": "The file is never zipped."}


def _pages(tmp_path, doc, session="s1"):
    pages = tmp_path / "pages"
    pages.mkdir(parents=True)
    (pages / f"grill-{session}.json").write_text(json.dumps(doc), "utf-8")
    return pages


def test_assumed_answers_lists_each_assumed_question_with_who_must_confirm_it(tmp_path):
    doc = document()
    doc["questions"].append(question("q-two", ["tester", "designer"], "Is a blank name allowed?", state="assumed",
                                     assumption={"text": "A blank name is refused.", "card": "i-two", "round": 2}))
    assert prd_files.assumed_answers(_pages(tmp_path, doc), "s1") == [
        ASSUMED, {"question": "q-two", "text": "Is a blank name allowed?", "who": ["tester", "designer"],
                  "assumption": "A blank name is refused."}]


def test_an_answered_question_that_kept_its_assumption_is_no_longer_assumed(tmp_path):
    doc = document()
    assumed = next(item for item in doc["questions"] if item["id"] == "q-assume")
    assumed.update(state="answered", answer={"text": "Never.", "choices": [], "role": "developer lead",
                                             "date": "2026-11-05", "signal": "tick", "round": 3})
    assert prd_files.assumed_answers(_pages(tmp_path, doc), "s1") == []


def test_assumed_answers_lists_none_on_a_page_with_no_questions(tmp_path):
    doc = document()
    doc["questions"] = []
    assert prd_files.assumed_answers(_pages(tmp_path, doc), "s1") == []
    assert prd_files.assumed_answers(_pages(tmp_path / "v1", {"schema": "afkv2.page/1", "rounds": []}), "s1") == []


def test_assumed_answers_lists_none_on_a_version_1_page_that_holds_an_assumed_question(tmp_path):
    doc = {**document(), "schema": "afkv2.page/1"}
    assert any(item.get("state") == "assumed" for item in doc["questions"])
    assert prd_files.assumed_answers(_pages(tmp_path, doc), "s1") == []


def test_a_question_that_lacks_a_field_refuses_naming_the_page(tmp_path):
    doc = document()
    del next(item for item in doc["questions"] if item["id"] == "q-assume")["who"]
    pages = _pages(tmp_path, doc)
    with pytest.raises(Refusal) as refused:
        prd_files.assumed_answers(pages, "s1")
    assert refused.value.code == "unreadable" and "grill-s1.json" in refused.value.reason
    assert "q-assume" in refused.value.reason and "who" in refused.value.reason


def _world_with_engine(tmp_path):
    world = World(tmp_path)
    (world.plugin / "engine").mkdir()
    shutil.copy(FAKES / "fake_engine.py", world.plugin / "engine" / "engine.py")
    return world


def test_start_answers_the_assumed_answers_of_the_newest_grill_page(tmp_path):
    world = _world_with_engine(tmp_path)
    (world.spec / "pages" / "grill-s-1.json").write_text(json.dumps(document()), "utf-8")
    newer = document()
    newer["questions"] = [question("q-new", ["tester"], "Is a blank name allowed?", state="assumed",
                                   assumption={"text": "A blank name is refused.", "card": "i-two", "round": 2})]
    (world.spec / "pages" / "grill-s-2.json").write_text(json.dumps(newer), "utf-8")
    with world.log.open("a", encoding="utf-8") as log:
        log.write("- Settled: exit gate passed 2026-10-31 · session s-2\n")
    answer = world.run("start", ticket_key=KEY)
    assert answer["session"] == "s-2"
    assert answer["assumed"] == [{"question": "q-new", "text": "Is a blank name allowed?", "who": ["tester"],
                                  "assumption": "A blank name is refused."}]


def test_start_refuses_a_grill_page_that_is_no_json(tmp_path):
    world = _world_with_engine(tmp_path)
    (world.spec / "pages" / "grill-s-1.json").write_text("{not json", "utf-8")
    error = world.run("start", expect=2, ticket_key=KEY)["error"]
    assert error["code"] == "unreadable" and "grill-s-1.json" in error["reason"]


def test_start_answers_no_assumed_answers_when_the_page_holds_none(tmp_path):
    assert World(tmp_path).run("start", ticket_key=KEY)["assumed"] == []


def test_the_prd_format_writes_each_assumed_answer_as_a_risk_naming_who_must_confirm_it():
    text = (SKILL_DIR / "PRD-FORMAT.md").read_text("utf-8")
    rule = text[text.index("## Assumed answers"):text.index("## Worked examples")]
    assert "`- Risk: <assumption> (<text>) — assumed, <who> must confirm.`" in rule
    assert "`<who>` is the role words of `who`, joined by `and`." in rule
    assert "`assumed` is empty: write no \"Risks\" block." in rule
    further_notes = next(line for line in text.splitlines() if line.startswith("| Further Notes |"))
    assert "the block \"Risks\"" in further_notes and "`assumed` of `start`" in further_notes
    assert "`unverified_external` and `assumed`." in (SKILL_DIR / "SKILL.md").read_text("utf-8")
