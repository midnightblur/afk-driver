#!/usr/bin/env afk-python
"""outside_writes: the one appender to Outside writes, and the read-back retry.

The seam tests drive the real github-issues adapter module, whose answers carry
`error` and `unavailable` with exit 0 and whose create can return an empty key.
"""

import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "utils" / "diagnose" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from outside_writes import (  # noqa: E402
    append_outside_write, failed, listed, retry_with_read_back)

DIAGNOSIS = """# Diagnosis

## Work id
bug-x

## Approval
dev; "go"; code; 2026-10-20

## Outside writes
- ticket: 12

## Notes
kept as written
"""


@pytest.fixture
def diagnosis(tmp_path):
    path = tmp_path / "DIAGNOSIS.md"
    path.write_text(DIAGNOSIS, encoding="utf-8")
    return path


class Clock:
    def __init__(self):
        self.waits = []

    def __call__(self, seconds):
        self.waits.append(seconds)


# --- append -----------------------------------------------------------------

def test_append_adds_one_line_at_the_end_of_the_list(diagnosis):
    assert append_outside_write(diagnosis, "change: https://forge/pr/3") is True
    text = diagnosis.read_text(encoding="utf-8")
    assert "## Outside writes\n- ticket: 12\n- change: https://forge/pr/3\n" in text
    assert text.replace("- change: https://forge/pr/3\n", "", 1) == DIAGNOSIS


def test_append_never_rewrites_an_earlier_entry(diagnosis):
    append_outside_write(diagnosis, "evidence: afk-evidence bug-x proof")
    append_outside_write(diagnosis, "in-review: 12")
    lines = diagnosis.read_text(encoding="utf-8").splitlines()
    i = lines.index("## Outside writes")
    assert lines[i + 1:i + 4] == ["- ticket: 12", "- evidence: afk-evidence bug-x proof",
                                  "- in-review: 12"]


def test_a_listed_entry_is_not_appended_twice(diagnosis):
    assert append_outside_write(diagnosis, "ticket: 12") is False
    assert diagnosis.read_text(encoding="utf-8") == DIAGNOSIS
    assert listed(diagnosis, "ticket: 12")
    assert not listed(diagnosis, "ticket: 13")


def test_append_into_an_empty_list(tmp_path):
    path = tmp_path / "DIAGNOSIS.md"
    path.write_text("## Approval\n\n## Outside writes\n", encoding="utf-8")
    append_outside_write(path, "push: feat/x@0123abc")
    assert path.read_text(encoding="utf-8") == "## Approval\n\n## Outside writes\n- push: feat/x@0123abc\n"


def test_append_keeps_crlf_line_endings(tmp_path):
    path = tmp_path / "DIAGNOSIS.md"
    path.write_bytes(DIAGNOSIS.replace("\n", "\r\n").encode("utf-8"))
    append_outside_write(path, "in-review: 12")
    data = path.read_bytes()
    assert b"- ticket: 12\r\n- in-review: 12\r\n" in data
    assert b"\n" not in data.replace(b"\r\n", b"")


@pytest.mark.parametrize("entry", ["merged: yes", "ticket", "ticket: ", "evidence: proof"])
def test_an_entry_outside_the_grammar_is_refused(diagnosis, entry):
    with pytest.raises(ValueError):
        append_outside_write(diagnosis, entry)
    assert diagnosis.read_text(encoding="utf-8") == DIAGNOSIS


def test_a_fenced_heading_in_an_earlier_part_is_skipped(tmp_path):
    path = tmp_path / "DIAGNOSIS.md"
    text = ("## Reproduction\n```\n## Outside writes\n## Notes\n```\n\n"
            "## Outside writes\n- ticket: 12\n\n## Notes\nkept\n")
    path.write_text(text, encoding="utf-8")
    append_outside_write(path, "in-review: 12")
    assert path.read_text(encoding="utf-8") == text.replace("- ticket: 12\n", "- ticket: 12\n- in-review: 12\n")


def test_append_keeps_a_byte_order_mark(diagnosis):
    diagnosis.write_bytes(b"\xef\xbb\xbf" + DIAGNOSIS.encode("utf-8"))
    assert listed(diagnosis, "ticket: 12")
    append_outside_write(diagnosis, "in-review: 12")
    data = diagnosis.read_bytes()
    assert data.startswith(b"\xef\xbb\xbf# Diagnosis")
    assert data.count(b"\xef\xbb\xbf") == 1 and b"- ticket: 12\n- in-review: 12\n" in data


def test_earlier_line_ends_are_never_changed(tmp_path):
    path = tmp_path / "DIAGNOSIS.md"
    raw = b"## Reproduction\r\nlog\x0cpage two\nmixed\r\n\n## Outside writes\n- ticket: 12\n"
    path.write_bytes(raw)
    append_outside_write(path, "in-review: 12")
    assert path.read_bytes() == raw + b"- in-review: 12\n"


def test_a_last_line_without_a_line_end_gets_one(tmp_path):
    path = tmp_path / "DIAGNOSIS.md"
    path.write_bytes(b"## Outside writes\r\n- ticket: 12")
    append_outside_write(path, "in-review: 12")
    assert path.read_bytes() == b"## Outside writes\r\n- ticket: 12\r\n- in-review: 12\r\n"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_append_keeps_the_file_mode(diagnosis):
    diagnosis.chmod(0o644)
    append_outside_write(diagnosis, "in-review: 12")
    assert diagnosis.stat().st_mode & 0o777 == 0o644


def test_a_file_without_the_list_is_refused(tmp_path):
    path = tmp_path / "DIAGNOSIS.md"
    path.write_text("## Work id\nbug-x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        append_outside_write(path, "ticket: 12")


# --- failed -----------------------------------------------------------------

@pytest.mark.parametrize("answer", [
    {"error": True, "reason": "x"},
    {"unavailable": True, "reason": "x"},
    {"unsupported": True, "reason": "x"},
    None,
    "not an answer",
])
def test_failed_answers(answer):
    assert failed(answer)


def test_an_empty_key_fails_only_when_a_key_is_required():
    assert failed({"key": "", "url": ""}, key="key")
    assert not failed({"key": "12", "url": "u"}, key="key")
    assert not failed({"ok": True})


# --- retry_with_read_back ---------------------------------------------------

def test_a_successful_write_is_not_read_back():
    read_back = mock.Mock()
    outcome = retry_with_read_back(lambda: {"key": "12"}, read_back, key="key", sleep=Clock())
    assert outcome.ok and outcome.attempts == 1 and outcome.answer == {"key": "12"}
    read_back.assert_not_called()


def test_a_write_without_a_read_back_is_not_retried():
    write = mock.Mock(return_value={"error": True})
    clock = Clock()
    outcome = retry_with_read_back(write, None, sleep=clock)
    assert not outcome.ok and write.call_count == 1 and clock.waits == []


def test_retries_twice_after_5_then_20_seconds_when_the_read_back_finds_nothing():
    write = mock.Mock(return_value={"error": True})
    read_back = mock.Mock(return_value=None)
    clock = Clock()
    outcome = retry_with_read_back(write, read_back, sleep=clock)
    assert not outcome.ok
    assert write.call_count == 3
    assert clock.waits == [5, 20]
    assert read_back.call_count == 3


def test_a_read_back_that_finds_the_write_stops_the_retries():
    write = mock.Mock(return_value={"error": True})
    outcome = retry_with_read_back(write, lambda: {"key": "12"}, sleep=Clock())
    assert outcome.ok and outcome.found and outcome.answer == {"key": "12"}
    assert write.call_count == 1


def test_a_retry_that_succeeds_ends_the_loop():
    write = mock.Mock(side_effect=[{"error": True}, {"key": "12"}])
    clock = Clock()
    outcome = retry_with_read_back(write, lambda: None, key="key", sleep=clock)
    assert outcome.ok and outcome.attempts == 2 and clock.waits == [5]


def test_an_unreadable_read_back_is_not_retried():
    write = mock.Mock(return_value={"error": True})
    clock = Clock()
    outcome = retry_with_read_back(write, lambda: {"unavailable": True}, sleep=clock)
    assert not outcome.ok and write.call_count == 1 and clock.waits == []
    assert "read-back" in outcome.reason


def test_read_first_finds_an_unlisted_write_and_does_not_send_it_again():
    write = mock.Mock(return_value={"key": "13"})
    outcome = retry_with_read_back(write, lambda: {"key": "12"}, key="key", read_first=True, sleep=Clock())
    assert outcome.ok and outcome.found and outcome.answer == {"key": "12"}
    write.assert_not_called()


def test_read_first_that_finds_nothing_writes_once():
    write = mock.Mock(return_value={"key": "13"})
    read_back = mock.Mock(return_value=None)
    outcome = retry_with_read_back(write, read_back, key="key", read_first=True, sleep=Clock())
    assert outcome.ok and not outcome.found and write.call_count == 1 and read_back.call_count == 1


def test_read_first_that_cannot_tell_sends_nothing():
    write = mock.Mock(return_value={"key": "13"})
    outcome = retry_with_read_back(write, lambda: {"unavailable": True}, read_first=True, sleep=Clock())
    assert not outcome.ok and "read-back" in outcome.reason
    write.assert_not_called()


def test_a_write_that_raises_counts_as_failed():
    def boom():
        raise OSError("socket closed")
    outcome = retry_with_read_back(boom, None, sleep=Clock())
    assert not outcome.ok and "socket closed" in outcome.reason


def test_success_then_append_records_the_write(diagnosis):
    outcome = retry_with_read_back(lambda: {"key": "13"}, None, key="key", sleep=Clock())
    assert outcome.ok
    append_outside_write(diagnosis, f"ticket: {outcome.answer['key']}")
    assert listed(diagnosis, "ticket: 13")


# --- seam: the real github-issues adapter -----------------------------------

def _github_issues():
    path = ROOT / "adapters" / "tracker" / "github-issues" / "api.py"
    spec = importlib.util.spec_from_file_location("afk_test_github_issues_api", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seam_unavailable_answer_with_exit_zero_is_a_failed_write():
    api = _github_issues()
    with mock.patch.object(api.shutil, "which", return_value=None):
        answer = api.call("tracker_create", {"summary": "s", "description": "d"})
    assert answer.get("unavailable") is True
    clock = Clock()
    outcome = retry_with_read_back(lambda: answer, None, key="key", sleep=clock)
    assert not outcome.ok and clock.waits == []


def test_seam_create_with_an_empty_key_is_a_failed_write():
    api = _github_issues()
    with mock.patch.object(api, "_gh", return_value={"ok": True}), \
         mock.patch.object(api, "_repo_args", return_value=[]):
        answer = api.call("tracker_create", {"summary": "s", "description": "d"})
    assert answer.get("key") == "" and not answer.get("error")
    assert failed(answer, key="key")
    write = mock.Mock(return_value=answer)
    outcome = retry_with_read_back(write, lambda: None, key="key", sleep=Clock())
    assert not outcome.ok and write.call_count == 3


def test_seam_error_answer_is_a_failed_write():
    api = _github_issues()
    with mock.patch.object(api, "_gh", return_value={"error": True, "status": 1, "body": "denied"}), \
         mock.patch.object(api, "_repo_args", return_value=[]):
        answer = api.call("tracker_comment", {"ticket_key": "12", "text": "afk-evidence bug-x proof"})
    assert answer.get("error") is True
    assert failed(answer)
