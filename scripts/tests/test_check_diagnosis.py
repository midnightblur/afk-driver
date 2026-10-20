#!/usr/bin/env afk-python
"""check_diagnosis: accept or refuse a DIAGNOSIS.md per the format file's tables."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "utils" / "diagnose" / "scripts"
FORMAT = ROOT / "skills" / "utils" / "diagnose" / "DIAGNOSIS-FORMAT.md"
sys.path.insert(0, str(SCRIPTS))

from check_diagnosis import check_diagnosis  # noqa: E402

PARTS = {
    "Work id": "bug-export-drops-row",
    "Ticket key": "",
    "Verdict": "V-1 obvious fix",
    "Base": "main@0123abc",
    "Diagnosis branch": "fix/bug-export-drops-row",
    "Symptom": "- [verified] the export has one row fewer than the grid; output below\n  ```\n  rows: 9 of 10\n  ```",
    "Spec comparison": "- [verified] PRD AC-3 says every visible row exports",
    "Reproduction": "- [verified] `tests/test_export.py::test_last_row` fails on the Base commit",
    "Attempts": "",
    "Root cause": "- [inferred] the loop stops one short at `export.py:42`",
    "Fix proposal": "Iterate to the end of the filtered rows.",
    "Approval": "",
    "Outside writes": "",
}


def write(tmp_path, **changes):
    parts = dict(PARTS)
    parts.update(changes)
    text = "# Diagnosis\n\n" + "".join(
        f"## {name}\n{body}\n\n" if body else f"## {name}\n\n" for name, body in parts.items()
        if body is not None)
    path = tmp_path / "DIAGNOSIS.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_complete_obvious_fix_is_accepted(tmp_path):
    result = check_diagnosis(write(tmp_path))
    assert result.ok, result.problems
    assert result.state == "Diagnosed"


@pytest.mark.parametrize("verdict, emptied, missing", [
    ("V-1 obvious fix", "Root cause", "Root cause"),
    ("V-1 obvious fix", "Fix proposal", "Fix proposal"),
    ("V-2 several fixes", "Fix proposal", "Fix proposal"),
    ("V-2 several fixes", "Root cause", "Root cause"),
    ("V-3 spec gap", "Root cause", "Root cause"),
    ("V-4 works as specified", "Reproduction", "Reproduction"),
    ("V-1 obvious fix", "Symptom", "Symptom"),
    ("V-1 obvious fix", "Base", "Base"),
])
def test_a_missing_required_part_is_named(tmp_path, verdict, emptied, missing):
    result = check_diagnosis(write(tmp_path, Verdict=verdict, **{emptied: ""}))
    assert not result.ok
    assert missing in result.missing


def test_parts_a_verdict_does_not_need_may_be_empty(tmp_path):
    path = write(tmp_path, Verdict="V-4 works as specified", **{"Root cause": "", "Fix proposal": ""})
    assert check_diagnosis(path).ok


def test_cannot_reproduce_needs_attempts_not_a_reproduction(tmp_path):
    no_attempts = check_diagnosis(write(tmp_path, Verdict="V-5 cannot reproduce", Reproduction=""))
    assert not no_attempts.ok and "Attempts" in no_attempts.missing
    with_attempts = check_diagnosis(write(
        tmp_path, Verdict="V-5 cannot reproduce", Reproduction="",
        Attempts="- [verified] ran the export on main twice; ten rows both times"))
    assert with_attempts.ok, with_attempts.problems
    assert with_attempts.state == "Stopped"


def test_every_missing_part_is_listed(tmp_path):
    result = check_diagnosis(write(tmp_path, **{"Root cause": "", "Fix proposal": "", "Symptom": ""}))
    assert set(result.missing) >= {"Root cause", "Fix proposal", "Symptom"}


def test_a_verdict_with_neither_reproduction_nor_attempt_is_refused(tmp_path):
    result = check_diagnosis(write(tmp_path, Verdict="V-3 spec gap", Reproduction="", Attempts=""))
    assert not result.ok
    assert any("reproduction or a recorded attempt" in p for p in result.problems)


def test_no_verdict_is_refused(tmp_path):
    result = check_diagnosis(write(tmp_path, Verdict=""))
    assert not result.ok and "Verdict" in result.missing


def test_an_unknown_verdict_is_refused(tmp_path):
    result = check_diagnosis(write(tmp_path, Verdict="V-9 maybe"))
    assert not result.ok
    assert any("V-1..V-5" in p for p in result.problems)


@pytest.mark.parametrize("part, body", [
    ("Symptom", "The export drops a row."),
    ("Root cause", "- the loop stops one short at `export.py:42`"),
    ("Spec comparison", "- [sure] PRD AC-3 says every visible row exports"),
])
def test_a_fact_without_a_certainty_mark_is_refused(tmp_path, part, body):
    result = check_diagnosis(write(tmp_path, **{part: body}))
    assert not result.ok
    assert any("certainty mark" in p and part in p for p in result.problems)


def test_indented_lines_and_fences_belong_to_their_fact(tmp_path):
    body = ("- [verified] the test fails on the Base commit\n"
            "  command: `pytest tests/test_export.py`\n"
            "```\nE   assert 9 == 10\n```")
    assert check_diagnosis(write(tmp_path, Reproduction=body)).ok


def test_a_non_fact_part_needs_no_mark(tmp_path):
    assert check_diagnosis(write(tmp_path, **{"Fix proposal": "Option A: iterate to the end."})).ok


@pytest.mark.parametrize("approval, writes, state", [
    ("dev; \"go\"; code; 2026-10-20", "", "Approved"),
    ("dev; \"go\"; code; 2026-10-20", "- push: feat/x@0123abc", "Landed"),
    ("dev; \"go\"; code, change; 2026-10-20", "- ticket: 12\n- change: https://forge/pr/3", "Shipped"),
    ("dev; \"go\"; code, change; 2026-10-20",
     "- ticket: 12\n- change: https://forge/pr/3\n- in-review: 12", "In review"),
    ("dev; \"go\"; code, change; 2026-10-20", "- push: feat/x@0123abc\n- change: https://forge/pr/3", "Shipped"),
    ("dev; \"go\"; code, change; 2026-10-20", "- push: feat/x@0123abc\n- in-review: 12", "In review"),
])
def test_state_is_derived_from_approval_and_outside_writes(tmp_path, approval, writes, state):
    result = check_diagnosis(write(tmp_path, Approval=approval, **{"Outside writes": writes}))
    assert result.ok, result.problems
    assert result.state == state


@pytest.mark.parametrize("verdict, state", [
    ("V-2 several fixes", "Sent to a grill"),
    ("V-3 spec gap", "Sent to a grill"),
    ("V-4 works as specified", "Stopped"),
])
def test_state_follows_the_verdict(tmp_path, verdict, state):
    result = check_diagnosis(write(tmp_path, Verdict=verdict))
    assert result.state == state


def test_an_unknown_outside_write_kind_is_refused(tmp_path):
    result = check_diagnosis(write(tmp_path, **{"Outside writes": "- merged: yes"}))
    assert not result.ok
    assert any("Outside writes" in p for p in result.problems)


def test_the_required_parts_come_from_the_format_file(tmp_path):
    # Dropping Fix proposal from V-1's row in a copy of the format file makes
    # the same diagnosis pass: the script reads the table, not a copy of it.
    text = FORMAT.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| V-1 |"))
    custom = tmp_path / "FORMAT.md"
    custom.write_text(text.replace(row, row.replace(", Fix proposal", "")), encoding="utf-8")
    path = write(tmp_path, **{"Fix proposal": ""})
    assert not check_diagnosis(path).ok
    assert check_diagnosis(path, format_path=custom).ok


def test_nothing_stores_the_state(tmp_path):
    path = write(tmp_path)
    before = path.read_bytes()
    check_diagnosis(path)
    assert path.read_bytes() == before
    assert "## State" not in before.decode("utf-8")


def _format_with(tmp_path, old, new):
    text = FORMAT.read_text(encoding="utf-8")
    assert old in text
    custom = tmp_path / "FORMAT.md"
    custom.write_text(text.replace(old, new), encoding="utf-8")
    return custom


def test_the_state_rows_come_from_the_format_file(tmp_path):
    # Moving the Landed row above Shipped in a copy of the format file flips
    # the state of a diagnosis holding both entries: the order is the table's.
    text = FORMAT.read_text(encoding="utf-8")
    shipped = next(line for line in text.splitlines() if line.startswith("| Shipped |"))
    landed = next(line for line in text.splitlines() if line.startswith("| Landed |"))
    custom = _format_with(tmp_path, f"{shipped}\n{landed}", f"{landed}\n{shipped}")
    path = write(tmp_path, Approval="dev; \"go\"; code; 2026-10-20",
                 **{"Outside writes": "- push: feat/x@0123abc\n- change: https://forge/pr/3"})
    assert check_diagnosis(path).state == "Shipped"
    assert check_diagnosis(path, format_path=custom).state == "Landed"


def test_a_verdict_no_state_row_names_is_refused(tmp_path):
    custom = _format_with(tmp_path, "| Diagnosed | verdict V-1 |", "| Diagnosed | verdict V-6 |")
    result = check_diagnosis(write(tmp_path), format_path=custom)
    assert not result.ok and result.state is None
    assert any("State table" in p for p in result.problems)


def test_a_state_row_naming_nothing_is_an_unreadable_format(tmp_path):
    custom = _format_with(tmp_path, "| Diagnosed | verdict V-1 |", "| Diagnosed | the first verdict |")
    done = subprocess.run([sys.executable, str(SCRIPTS / "check_diagnosis.py"), str(write(tmp_path)),
                           "--format", str(custom)], capture_output=True, text=True)
    assert done.returncode == 2 and "Diagnosed" in done.stderr


def test_a_short_table_row_is_an_unreadable_format(tmp_path):
    custom = _format_with(tmp_path, "| Diagnosed | verdict V-1 |", "| Diagnosed |")
    done = subprocess.run([sys.executable, str(SCRIPTS / "check_diagnosis.py"), str(write(tmp_path)),
                           "--format", str(custom)], capture_output=True, text=True)
    assert done.returncode == 2 and "cells" in done.stderr


def test_a_file_with_a_byte_order_mark_is_read(tmp_path):
    path = write(tmp_path)
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert check_diagnosis(path).ok


def test_a_repeated_part_heading_is_refused(tmp_path):
    path = write(tmp_path)
    path.write_text(path.read_text(encoding="utf-8") + "## Approval\n\n", encoding="utf-8")
    result = check_diagnosis(path)
    assert not result.ok
    assert any("Approval" in p and "more than once" in p for p in result.problems)


def test_a_fenced_heading_stays_inside_its_part(tmp_path):
    body = "- [verified] pasted output below\n```\n## Outside writes\n- merged: yes\n```"
    result = check_diagnosis(write(tmp_path, Reproduction=body))
    assert result.ok, result.problems


def test_an_evidence_entry_without_a_marker_is_refused(tmp_path):
    result = check_diagnosis(write(tmp_path, **{"Outside writes": "- evidence: proof"}))
    assert not result.ok
    assert any("evidence marker" in p for p in result.problems)
    good = check_diagnosis(write(tmp_path, **{"Outside writes": "- evidence: afk-evidence bug-x proof"}))
    assert good.ok, good.problems


def test_cli_exit_codes(tmp_path):
    good = write(tmp_path)
    done = subprocess.run([sys.executable, str(SCRIPTS / "check_diagnosis.py"), str(good)],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert "accept" in done.stdout and "Diagnosed" in done.stdout
    bad = write(tmp_path, **{"Root cause": ""})
    done = subprocess.run([sys.executable, str(SCRIPTS / "check_diagnosis.py"), str(bad)],
                          capture_output=True, text=True)
    assert done.returncode == 1
    assert "Root cause" in done.stdout
    done = subprocess.run([sys.executable, str(SCRIPTS / "check_diagnosis.py"),
                           str(tmp_path / "absent.md")], capture_output=True, text=True)
    assert done.returncode == 2
