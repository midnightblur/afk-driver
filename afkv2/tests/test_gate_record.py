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


# ---------------------------------------------------------------- write_verdict


def test_write_verdict_stores_1_verdict_per_row_once(gate):
    _write(gate)
    answer = gr.write_verdict(gate["record"], _judged(), head=HEAD)
    assert answer["written"] is True
    assert gr.read(gate["record"])["rows"][0]["verdict"] == _verdict()
    before = gate["record"].read_bytes()
    assert gr.write_verdict(gate["record"], _judged(result="fail"), head=HEAD)["written"] is False
    assert gate["record"].read_bytes() == before


@pytest.mark.parametrize("rows, judged, head, code", [
    ([_row(exits=(1, 0))], _judged(), HEAD, "gate-not-passed"),
    ([_row()], _judged(), LATER, "gate-key-differs"),
    ([_row()], _judged(rows=("VR-002",)), HEAD, "verdict-missing"),
    ([_row()], {"verdicts": {"VR-001": {**_verdict(), "extra": 1}}}, HEAD, "bad-verdict"),
    ([_row()], {"verdicts": {"VR-001": {"result": "pass"}}}, HEAD, "bad-verdict"),
])
def test_write_verdict_refuses(gate, rows, judged, head, code):
    _write(gate, rows)
    with pytest.raises(Refusal) as refused:
        gr.write_verdict(gate["record"], judged, head=head)
    assert refused.value.code == code


# ---------------------------------------------------------------- verify


def _passed(gate, rows=None, found=None, **verdict):
    rows = rows or [_row()]
    _write(gate, rows, found=found)
    gr.write_verdict(gate["record"], _judged(rows=[row["row"] for row in rows], **verdict), head=HEAD)


def _verify(gate, proofs=None, head=HEAD, changed=()):
    return gr.verify(gate["record"], [_proof()] if proofs is None else proofs, head,
                     spec_folder="docs/afk/185", repo=gate["folder"], changed=lambda old, new: list(changed))


def _codes(gate, **given):
    with pytest.raises(gr.GateRefusal) as refused:
        _verify(gate, **given)
    return refused.value.code, [failure["code"] for failure in refused.value.failures]


def test_verify_passes_a_passed_judged_gate_with_its_proofs(gate):
    _passed(gate)
    answer = _verify(gate)
    assert answer["ok"] and answer["gate"]["head"] == HEAD


def test_verify_refuses_no_gate(gate):
    with pytest.raises(Refusal) as refused:
        _verify(gate)
    assert refused.value.code == "no-gate"


@pytest.mark.parametrize("exits, waiting", [((1, 1), None), ((1, 0), None), ((), "no driver")])
def test_verify_refuses_a_row_that_did_not_pass(gate, exits, waiting):
    _write(gate, [_row(exits=exits, waiting=waiting)])
    assert _codes(gate)[0] == "gate-not-passed"


def test_verify_refuses_an_unjudged_row_and_a_failed_verdict(gate):
    _write(gate)
    assert _codes(gate)[0] == "gate-not-passed"
    gr.write_verdict(gate["record"], _judged(result="fail"), head=HEAD)
    assert _codes(gate) == ("gate-not-passed", ["gate-not-passed"])


def test_verify_refuses_a_verdict_with_no_description(gate):
    _passed(gate, seen=())
    assert "verdict-no-description" in _codes(gate)[1]


@pytest.mark.parametrize("change", ["edit", "delete", "log"])
def test_verify_hashes_again_and_refuses_evidence_changed(gate, change):
    _passed(gate)
    if change == "edit":
        (gate["folder"] / "evidence" / "click.png").write_bytes(b"\x89PNG another picture")
    elif change == "delete":
        (gate["folder"] / "evidence" / "answer.json").unlink()
    else:
        (gate["folder"] / "run-1.log").write_text("1 failed\n", encoding="utf-8")
    code, codes = _codes(gate)
    assert code == "evidence-changed" and codes == ["evidence-changed"]


def test_verify_refuses_a_missing_proof_and_a_proof_field_missing(gate):
    _passed(gate)
    assert _codes(gate, proofs=[])[0] == "proof-missing"
    for field in ("behavior", "level", "ran", "evidence"):
        with pytest.raises(gr.GateRefusal) as refused:
            _verify(gate, proofs=[_proof(**{field: " "})])
        assert refused.value.code == "proof-field-missing" and field in refused.value.reason


def test_verify_allows_a_later_change_inside_the_spec_folder_only(gate):
    _passed(gate)
    assert _verify(gate, head=LATER, changed=["docs/afk/185/PRD.md"])["ok"]
    code, _ = _codes(gate, head=LATER, changed=["docs/afk/185/PRD.md", "afkv2/scripts/x.py"])
    assert code == "gate-head-stale"
    assert _codes(gate, head=LATER, changed=["docs/afk/1850/PRD.md"])[0] == "gate-head-stale"


def test_verify_reads_the_changed_paths_from_git(gate, tmp_path):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    git = lambda *args: subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (repo / "docs" / "afk" / "185").mkdir(parents=True)
    (repo / "docs" / "afk" / "185" / "PRD.md").write_text("1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "1")
    first = git("rev-parse", "HEAD")
    _write(gate, head=first)
    gr.write_verdict(gate["record"], _judged(), head=first)
    (repo / "docs" / "afk" / "185" / "PRD.md").write_text("2\n", encoding="utf-8")
    git("commit", "-q", "-am", "2")
    spec_only = git("rev-parse", "HEAD")
    assert gr.verify(gate["record"], [_proof()], spec_only, spec_folder=str(repo / "docs" / "afk" / "185"), repo=repo)["ok"]
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "3")
    with pytest.raises(gr.GateRefusal) as refused:
        gr.verify(gate["record"], [_proof()], git("rev-parse", "HEAD"), spec_folder="docs/afk/185", repo=repo)
    assert refused.value.code == "gate-head-stale" and "app.py" in refused.value.reason
    with pytest.raises(gr.GateRefusal) as refused:
        gr.verify(gate["record"], [_proof()], "f" * 40, spec_folder="docs/afk/185", repo=repo)
    assert refused.value.code == "gate-head-stale"


@pytest.mark.parametrize("pick, by, refused", [
    (None, None, True), ("ticket", "developer", False), ("fix-now", "agent", True), ("fix-in-place", "agent", False),
])
def test_verify_refuses_found_open(gate, pick, by, refused):
    bug = {"id": "FB-01", "what": "the save button is grey", "where": "settings page", "how": "seen in the run",
           "pick": pick, "by": by}
    _passed(gate, found=[bug])
    if refused:
        assert _codes(gate) == ("found-open", ["found-open"])
    else:
        assert _verify(gate)["ok"]


def test_verify_lists_every_failure_and_leads_with_the_first(gate):
    _passed(gate, seen=())
    (gate["folder"] / "evidence" / "click.png").write_bytes(b"changed")
    code, codes = _codes(gate, proofs=[])
    assert code == "verdict-no-description"
    assert codes == ["verdict-no-description", "evidence-changed", "proof-missing"]


# ---------------------------------------------------------------- proof lines and the proof comment


def _two_rows(gate):
    (gate["folder"] / "run-2.log").write_text("1 failed\n1 passed\n", encoding="utf-8")
    second = _row("VR-002", exits=(1, 0))
    second["runs"][1]["log"] = "run-2.log"
    second["runs"][1]["evidence"] = ["evidence/answer.json"]
    return [_row(), second]


def test_proof_lines_gives_1_line_per_row_with_its_fields(gate):
    _passed(gate)
    lines = gr.proof_lines(gr.read(gate["record"]))
    picture = gate["folder"] / "evidence" / "click.png"
    assert lines == [{"row": "VR-001", "behavior": "the link opens the ticket in a new tab", "level": "ui-e2e",
                      "ran": "afkv2/tests/e2e/test_link.py::test_opens_tab", "result": "pass",
                      "evidence": f"evidence/click.png (sha256 {gr.file_digest(picture)[:12]}), "
                                  f"evidence/answer.json (sha256 {gr.file_digest(gate['folder'] / 'evidence' / 'answer.json')[:12]})"}]
    assert gr.verify(gate["record"], lines, HEAD, spec_folder="docs", repo=gate["folder"])["ok"]


def test_proof_lines_reads_the_last_run_of_a_row(gate):
    _write(gate, _two_rows(gate))
    lines = gr.proof_lines(gr.read(gate["record"]))
    assert [line["row"] for line in lines] == ["VR-001", "VR-002"]
    assert lines[1]["result"] == "flaky" and lines[1]["evidence"].startswith("evidence/answer.json (sha256 ")
    assert "click.png" not in lines[1]["evidence"]


def test_proof_comment_gives_the_receipt_rows_pictures_logs_and_footer(gate):
    _passed(gate, seen=("The new tab shows ticket P-1. Its title matches.", "The answer is 200."))
    comment = gr.proof_comment(gr.read(gate["record"]), receipt="r-123", change="https://forge/pr/191",
                               folder=gate["folder"])
    lines = comment["body"].splitlines()
    assert lines[0] == "afkv2 proof v1 r-123"
    assert lines[1] == "VR-001 · the link opens the ticket in a new tab · ui-e2e · pass · The new tab shows ticket P-1."
    log_digest = gr.file_digest(gate["folder"] / "run-1.log")
    answer_digest = gr.file_digest(gate["folder"] / "evidence" / "answer.json")
    assert "Pictures: click.png" in lines
    assert f"Logs: run-1.log sha256 {log_digest}, answer.json sha256 {answer_digest}" in lines
    assert lines[-1] == f"Head {HEAD} · change https://forge/pr/191 · judge codex gpt-5 medium"
    assert comment["pictures"] == [str(gate["folder"] / "evidence" / "click.png")]


def test_proof_comment_names_an_unjudged_row_and_no_pictures(gate):
    row = _row()
    row["runs"][0]["evidence"] = ["evidence/answer.json"]
    _write(gate, [row])
    comment = gr.proof_comment(gr.read(gate["record"]), receipt="r-1", change="https://forge/pr/1", folder=gate["folder"])
    assert "VR-001 · the link opens the ticket in a new tab · ui-e2e · pass · not judged" in comment["body"]
    assert comment["pictures"] == [] and "Pictures: none" in comment["body"]
    assert comment["body"].splitlines()[-1].endswith("judge none")


@pytest.mark.parametrize("receipt, change", [("", "https://forge/pr/1"), ("r-1", " ")])
def test_proof_comment_needs_the_receipt_and_the_change(gate, receipt, change):
    _passed(gate)
    with pytest.raises(Refusal) as refused:
        gr.proof_comment(gr.read(gate["record"]), receipt=receipt, change=change, folder=gate["folder"])
    assert refused.value.code == "bad-payload"
