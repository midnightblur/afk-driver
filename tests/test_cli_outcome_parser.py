"""Unit tests for cli._parse_outcome_marker — the seam between the spawned
``claude --print "/afk-go ..."`` session and the runner's ClaudeOutcome.

Without a working parser, claude's exit code is the only signal back to the
runner; ``claude --print`` exits 0 on clean termination, so every structured
status (test_fail, contract_mismatch, produces_drift, design_conflict)
collapses into "success" and the no-retry / dual-comment routing built for
cited mode is fictional. Lock the marker contract here.
"""

from __future__ import annotations

from pathlib import Path

from afk_driver.cli import _parse_outcome_marker
from afk_driver.runner import ClaudeOutcome


def _write_log(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "session.log"
    p.write_text(body, encoding="utf-8")
    return p


def test_parses_success_marker_multiline(tmp_path):
    p = _write_log(
        tmp_path,
        "chatty preamble from the session\n"
        "<<<AFK_OUTCOME>>>\n"
        '{"status": "success", "detail": "all green", "producer_key": null}\n'
        "<<<END>>>\n",
    )
    assert _parse_outcome_marker(p) == ClaudeOutcome(
        status="success", detail="all green"
    )


def test_parses_success_marker_single_line(tmp_path):
    p = _write_log(
        tmp_path,
        '<<<AFK_OUTCOME>>>{"status":"success","detail":"x","producer_key":null}<<<END>>>',
    )
    out = _parse_outcome_marker(p)
    assert isinstance(out, ClaudeOutcome)
    assert out.status == "success"
    assert out.producer_key is None


def test_parses_test_fail(tmp_path):
    p = _write_log(
        tmp_path,
        '<<<AFK_OUTCOME>>>{"status":"test_fail","detail":"3 failures","producer_key":null}<<<END>>>',
    )
    out = _parse_outcome_marker(p)
    assert isinstance(out, ClaudeOutcome)
    assert out.status == "test_fail"
    assert out.detail == "3 failures"


def test_parses_build_fail(tmp_path):
    p = _write_log(
        tmp_path,
        '<<<AFK_OUTCOME>>>{"status":"build_fail","detail":"mvn -pl x compile failed","producer_key":null}<<<END>>>',
    )
    assert _parse_outcome_marker(p).status == "build_fail"


def test_parses_design_conflict(tmp_path):
    p = _write_log(
        tmp_path,
        '<<<AFK_OUTCOME>>>{"status":"design_conflict","detail":"SDD §8 mandate infeasible","producer_key":null}<<<END>>>',
    )
    assert _parse_outcome_marker(p).status == "design_conflict"


def test_parses_contract_mismatch_with_producer_key(tmp_path):
    p = _write_log(
        tmp_path,
        "<<<AFK_OUTCOME>>>\n"
        '{"status": "contract_mismatch", "detail": "P2P-1218 src/x.py#FooBarRegistry missing", "producer_key": "P2P-1218"}\n'
        "<<<END>>>\n",
    )
    out = _parse_outcome_marker(p)
    assert out == ClaudeOutcome(
        status="contract_mismatch",
        detail="P2P-1218 src/x.py#FooBarRegistry missing",
        producer_key="P2P-1218",
    )


def test_parses_produces_drift(tmp_path):
    p = _write_log(
        tmp_path,
        '<<<AFK_OUTCOME>>>{"status":"produces_drift","detail":"declared FooStrategy at x.py#FooStrategy, did not deliver","producer_key":null}<<<END>>>',
    )
    out = _parse_outcome_marker(p)
    assert out.status == "produces_drift"
    assert "FooStrategy" in out.detail


def test_parses_other(tmp_path):
    p = _write_log(
        tmp_path,
        '<<<AFK_OUTCOME>>>{"status":"other","detail":"unexpected","producer_key":null}<<<END>>>',
    )
    assert _parse_outcome_marker(p).status == "other"


def test_no_marker_returns_reason(tmp_path):
    p = _write_log(tmp_path, "no marker anywhere\nplain output line\n")
    res = _parse_outcome_marker(p)
    assert res == "no_marker"


def test_malformed_json_returns_reason(tmp_path):
    p = _write_log(tmp_path, "<<<AFK_OUTCOME>>>{not valid json}<<<END>>>")
    res = _parse_outcome_marker(p)
    assert res == "marker_malformed_json"


def test_non_object_json_returns_reason(tmp_path):
    p = _write_log(tmp_path, '<<<AFK_OUTCOME>>>"just a string"<<<END>>>')
    res = _parse_outcome_marker(p)
    # The regex requires a `{...}` payload, so a bare-string body is treated
    # as no marker rather than malformed.
    assert res == "no_marker"


def test_unknown_status_returns_reason(tmp_path):
    p = _write_log(
        tmp_path,
        '<<<AFK_OUTCOME>>>{"status":"weird_status","detail":"nope","producer_key":null}<<<END>>>',
    )
    res = _parse_outcome_marker(p)
    assert isinstance(res, str)
    assert res.startswith("marker_unknown_status:")
    assert "weird_status" in res


def test_multiple_markers_takes_last(tmp_path):
    p = _write_log(
        tmp_path,
        "first attempt:\n"
        '<<<AFK_OUTCOME>>>{"status":"test_fail","detail":"first","producer_key":null}<<<END>>>\n'
        "retry inside session:\n"
        '<<<AFK_OUTCOME>>>{"status":"success","detail":"second","producer_key":null}<<<END>>>\n',
    )
    out = _parse_outcome_marker(p)
    assert isinstance(out, ClaudeOutcome)
    assert out.status == "success"
    assert out.detail == "second"


def test_marker_inside_fenced_code_block_still_parses(tmp_path):
    # The skill is allowed to wrap the marker in a fenced code block so a
    # rendering layer can't mangle the angle brackets — the regex tolerates
    # surrounding code-fence noise.
    p = _write_log(
        tmp_path,
        "see below:\n\n"
        "```\n"
        "<<<AFK_OUTCOME>>>\n"
        '{"status":"success","detail":"ok","producer_key":null}\n'
        "<<<END>>>\n"
        "```\n",
    )
    out = _parse_outcome_marker(p)
    assert isinstance(out, ClaudeOutcome)
    assert out.status == "success"


def test_log_unreadable_returns_reason(tmp_path):
    res = _parse_outcome_marker(tmp_path / "does-not-exist.log")
    assert res == "log_unreadable"


def test_producer_key_missing_defaults_none(tmp_path):
    # producer_key is required per the contract, but if a skill omits it the
    # parser must still accept the marker rather than rejecting silently.
    p = _write_log(
        tmp_path,
        '<<<AFK_OUTCOME>>>{"status":"success","detail":"ok"}<<<END>>>',
    )
    out = _parse_outcome_marker(p)
    assert isinstance(out, ClaudeOutcome)
    assert out.producer_key is None


def test_producer_key_non_string_falls_to_none(tmp_path):
    p = _write_log(
        tmp_path,
        '<<<AFK_OUTCOME>>>{"status":"contract_mismatch","detail":"x","producer_key":123}<<<END>>>',
    )
    out = _parse_outcome_marker(p)
    assert isinstance(out, ClaudeOutcome)
    assert out.status == "contract_mismatch"
    assert out.producer_key is None


def test_detail_non_string_coerced(tmp_path):
    # Should not crash if the skill emits a non-string detail; coerce.
    p = _write_log(
        tmp_path,
        '<<<AFK_OUTCOME>>>{"status":"other","detail":42,"producer_key":null}<<<END>>>',
    )
    out = _parse_outcome_marker(p)
    assert isinstance(out, ClaudeOutcome)
    assert out.detail == "42"
