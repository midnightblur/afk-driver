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


def test_start_answers_the_assumed_answers_of_the_newest_grill_page(tmp_path):
    world = World(tmp_path)
    (world.plugin / "engine").mkdir()
    shutil.copy(FAKES / "fake_engine.py", world.plugin / "engine" / "engine.py")
    (world.spec / "pages" / "grill-s-1.json").write_text(json.dumps(document()), "utf-8")
    assert world.run("start", ticket_key=KEY)["assumed"] == [ASSUMED]


def test_start_answers_no_assumed_answers_when_the_page_holds_none(tmp_path):
    assert World(tmp_path).run("start", ticket_key=KEY)["assumed"] == []


def test_the_prd_format_writes_each_assumed_answer_as_a_risk_naming_who_must_confirm_it():
    text = (SKILL_DIR / "PRD-FORMAT.md").read_text("utf-8")
    rule = text[text.index("## Assumed answers"):]
    assert "assumed, <who> must confirm" in rule and "Risk" in rule and "`assumed`" in rule
    assert "`assumed`" in (SKILL_DIR / "SKILL.md").read_text("utf-8")
