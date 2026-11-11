"""The gate record module: every field, every refusal of verify, idempotency, the proof comment text."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import gate_record as gr  # noqa: E402
from afkv2_config import Refusal  # noqa: E402

HEAD = "a" * 40
LATER = "b" * 40


@pytest.fixture
def gate(tmp_path):
    folder = tmp_path / "gate"
    (folder / "evidence").mkdir(parents=True)
    (folder / "evidence" / "click.png").write_bytes(b"\x89PNG picture")
    (folder / "evidence" / "answer.json").write_text('{"status": 200}', encoding="utf-8")
    (folder / "run-1.log").write_text("1 passed\n", encoding="utf-8")
    verification = tmp_path / "VERIFICATION.md"
    verification.write_text("| VR-001 | ... |\n", encoding="utf-8")
    return {"folder": folder, "record": folder / "gate.json", "verification": verification}


def _row(row="VR-001", exits=(0,), waiting=None):
    runs = [{"exit": code, "started": "2026-11-11T17:00:00Z", "seconds": 4.5, "log": "run-1.log",
             "evidence": ["evidence/click.png", "evidence/answer.json"]} for code in exits]
    return {"row": row, "behavior": "the link opens the ticket in a new tab", "level": "ui-e2e",
            "ran": "afkv2/tests/e2e/test_link.py::test_opens_tab", "runs": runs, "waiting": waiting}


def _write(gate, rows=None, **extra):
    return gr.write_run(gate["record"], lane=extra.pop("lane", "medium"), head=extra.pop("head", HEAD),
                        verification=gate["verification"], rows=rows if rows is not None else [_row()], **extra)


def _verdict(result="pass", seen=("The new tab shows the ticket page.",)):
    return {"provider": "codex", "model": "gpt-5", "effort": "medium", "seen": list(seen),
            "compare": ["It matches what the row says you should see."], "checks": [], "result": result}


def _judged(rows=("VR-001",), **verdict):
    return {"ok": True, "provider": "codex", "model": "gpt-5", "effort": "medium",
            "verdicts": {row: _verdict(**verdict) for row in rows}}


def _proof(row="VR-001", **change):
    return {"row": row, "behavior": "the link opens the ticket", "level": "ui-e2e",
            "ran": "test_opens_tab", "evidence": "click.png", **change}


# ---------------------------------------------------------------- write_run


def test_write_run_holds_the_fields_of_the_gate_record(gate):
    answer = _write(gate)
    record = json.loads(gate["record"].read_text(encoding="utf-8"))
    assert answer["ok"] and answer["written"] is True
    assert record["version"] == 1 and record["lane"] == "medium" and record["head"] == HEAD
    assert record["verification_digest"] == hashlib.sha256(gate["verification"].read_bytes()).hexdigest()
    assert record["found"] == [] and record["go"] is None and record["failed_runs"] == 0
    row = record["rows"][0]
    assert {"row", "behavior", "level", "ran", "runs", "result", "waiting", "lower", "verdict"} <= set(row)
    assert row["result"] == "pass" and row["verdict"] is None
    run = row["runs"][0]
    assert run["n"] == 1 and run["exit"] == 0 and run["seconds"] == 4.5
    picture = gate["folder"] / "evidence" / "click.png"
    assert run["evidence"][0] == {"path": "evidence/click.png", "sha256": hashlib.sha256(picture.read_bytes()).hexdigest(),
                                  "bytes": picture.stat().st_size}
    assert run["log"]["path"] == "run-1.log" and len(run["log"]["sha256"]) == 64


@pytest.mark.parametrize("exits, waiting, result", [
    ((0,), None, "pass"), ((1,), None, "fail"), ((1, 0), None, "flaky"), ((1, 1), None, "fail"), ((), "no browser driver", "waiting"),
])
def test_write_run_derives_the_row_result_from_its_runs(gate, exits, waiting, result):
    answer = _write(gate, [_row(exits=exits, waiting=waiting)])
    assert answer["results"] == {"VR-001": result}


@pytest.mark.parametrize("rows", [
    [_row(exits=(0, 0))], [_row(exits=(1, 1, 0))], [_row(exits=())], [_row(), _row()],
    [{**_row(), "behavior": ""}], [{**_row(), "level": "unit-ish"}], [{**_row(), "lower": {"level": "api"}}],
])
def test_write_run_refuses_a_bad_row(gate, rows):
    with pytest.raises(Refusal) as refused:
        _write(gate, rows)
    assert refused.value.code == "bad-payload"


def test_write_run_refuses_a_missing_evidence_file(gate):
    row = _row()
    row["runs"][0]["evidence"].append("evidence/gone.png")
    with pytest.raises(Refusal) as refused:
        _write(gate, [row])
    assert refused.value.code == "evidence-missing" and "gone.png" in refused.value.reason


def test_a_second_write_run_at_the_same_key_writes_nothing(gate):
    _write(gate)
    before = gate["record"].read_bytes()
    answer = _write(gate, [_row(exits=(1, 1))])
    assert answer["written"] is False and gate["record"].read_bytes() == before


def test_a_new_key_counts_a_failed_run_and_keeps_found_bugs(gate):
    bug = {"id": "FB-01", "what": "the save button is grey", "where": "settings page", "how": "seen in the run"}
    assert _write(gate, [_row(exits=(1, 1))], found=[bug])["failed_runs"] == 1
    answer = _write(gate, [_row(exits=(1, 0))], head=LATER)
    record = gr.read(gate["record"])
    assert answer["written"] is True and record["failed_runs"] == 2 and record["head"] == LATER
    assert record["found"] == [{**bug, "pick": None, "by": None}]
    _write(gate, head="c" * 40)
    assert gr.read(gate["record"])["failed_runs"] == 2


@pytest.mark.parametrize("found", [
    [{"id": "FB-1", "what": "x", "where": "y", "how": "z"}],
    [{"id": "FB-01", "what": "x", "where": "y"}],
    [{"id": "FB-01", "what": "x", "where": "y", "how": "z", "pick": "later"}],
    [{"id": "FB-01", "what": "x", "where": "y", "how": "z", "pick": "ticket"}],
    [{"id": "FB-01", "what": "x", "where": "y", "how": "z"}, {"id": "FB-01", "what": "x", "where": "y", "how": "z"}],
])
def test_write_run_refuses_a_bad_found_bug(gate, found):
    with pytest.raises(Refusal) as refused:
        _write(gate, found=found)
    assert refused.value.code == "bad-payload"


def test_the_small_lane_needs_its_go_and_keeps_it(gate):
    with pytest.raises(Refusal) as refused:
        _write(gate, lane="small")
    assert refused.value.code == "bad-payload"
    go = {"card": "go-1", "head": HEAD, "at": "2026-11-11T16:00:00Z"}
    _write(gate, lane="small", go=go)
    _write(gate, lane="small", head=LATER)
    assert gr.read(gate["record"])["go"] == go
    with pytest.raises(Refusal):
        _write(gate, lane="medium", head="c" * 40, go=go)


def test_read_refuses_an_unknown_major_version(gate):
    _write(gate)
    record = json.loads(gate["record"].read_text(encoding="utf-8"))
    gate["record"].write_text(json.dumps({**record, "version": 2}), encoding="utf-8")
    with pytest.raises(Refusal) as refused:
        gr.read(gate["record"])
    assert refused.value.code == "gate-version-unknown"
    with pytest.raises(Refusal):
        _write(gate, head=LATER)


def test_read_refuses_no_gate_and_an_unreadable_one(gate):
    with pytest.raises(Refusal) as refused:
        gr.read(gate["record"])
    assert refused.value.code == "no-gate"
    gate["record"].write_text("{not json", encoding="utf-8")
    with pytest.raises(Refusal) as refused:
        gr.read(gate["record"])
    assert refused.value.code == "gate-unreadable"
