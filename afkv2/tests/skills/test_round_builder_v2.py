"""The round builder and the reading tool on a version 2 page (SDD §3 rows "round builder `build`" and "reading
tool `apply-readings`", §4 Migration and backfill, §14 rows "Builder's version" and "Reply for a card's notes")."""

import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
for _folder in (PLUGIN / "skills" / "use-lavish" / "scripts", PLUGIN / "scripts", PLUGIN / "engine"):
    sys.path.insert(0, str(_folder))

import engine  # noqa: E402
import page_round  # noqa: E402
import round_document as rd  # noqa: E402
from grill_common import Refusal  # noqa: E402

V1, V2 = "afkv2.page/1", "afkv2.page/2"
SESSION = {"id": "s-1", "skill": "grill", "feature": "PROJ-1", "ticket": "PROJ-1"}


def card(item_id, **extra):
    return {"id": item_id, "kind": "confirm", "body": {"type": "text", "id": f"{item_id}-body", "props": {"text": "x"}},
            **extra}


def round_input(*item_ids, **extra):
    return {"banner": {"settled": [], "unlocks": [], "parked": []}, "items": [card(i) for i in item_ids], **extra}


def options(*ids, several=False):
    return {"options": [{"id": option, "text": f"Option {option}"} for option in ids], "several": several}


def question(question_id, **extra):
    return {"id": question_id, "who": ["product owner"], "question": "Which formats?", "context": "The export.",
            "why": "It sets the scope.", "origin": {"card": "i-a"}, "state": "open", **extra}


def read(path):
    return json.loads(Path(path).read_text("utf-8"))


def write(path, doc):
    Path(path).write_text(json.dumps(doc), "utf-8")


def check(path):
    out = []
    original = print
    try:
        engine.print = out.append
        code = engine.main(["check", str(path)])
    finally:
        engine.print = original
    return code, json.loads(out[0])


def ingest(path, raw):
    raw_file = Path(path).with_name("raw.txt")
    raw_file.write_text(raw, "utf-8")
    return page_round.ingest(path, raw_file)


def as_version_2(path, **lists):
    """Rewrite a built version 1 page as the version 2 page of the same session, with the given lists."""
    doc = read(path)
    doc["schema"] = V2
    doc.update(lists)
    write(path, doc)
    assert check(path)[0] == 0, check(path)


@pytest.fixture
def path(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return tmp_path / "pages" / "grill-s-1.json"


def settled_round_1(path, *more):
    """Round 1 settles card i-a by an accept mark; round 2 is current with the cards `more`."""
    rd.build_round_document(path, SESSION, round_input("i-a"))
    ingest(path, "[round R-1]\ni-a accept")
    rd.build_round_document(path, SESSION, round_input(*more))


# ---- ingest passes on what the agent must read (decision D-9)


def test_ingest_passes_on_the_questions_and_the_settled_notes_to_read_on_a_version_2_page(path):
    settled_round_1(path, "i-b")
    line = {"round": 1, "cause": "finding", "text": "Asked."}
    as_version_2(path, questions=[{**question("q-one", choices=options("csv", "xls")), "changes": [line]}])
    answer = ingest(path, "[round R-2]\ni-a note 1\n  Fine as it is.\nq-one tick csv")
    assert [signal["target"] for signal in answer["questions_to_read"]] == ["q-one"]
    assert answer["questions_to_read"][0]["choices"] == ["csv"]
    assert answer["settled_notes_to_read"] == ["N-2-i-a-1"]


def test_ingest_on_a_version_1_page_answers_as_before(path):
    settled_round_1(path, "i-b")
    answer = ingest(path, "[round R-2]\ni-b accept")
    assert "questions_to_read" not in answer and "settled_notes_to_read" not in answer
