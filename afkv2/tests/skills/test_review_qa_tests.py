"""The review-qa-tests annotate script: threaded comments and new rows, in rebuild and in-place mode."""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "review-qa-tests" / "scripts" / "annotate_sheet.py"


def _workbook(path):
    wb = openpyxl.Workbook()
    for name in ("Login", "Search"):
        ws = wb.create_sheet(name)
        ws.append(["Test Name", "Scenario Objective", "Summary"])
        ws.append(["Valid input", "Accept a valid value", "Value is saved"])
    del wb["Sheet"]
    wb.save(path)


def _run(tmp_path, config):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config), "utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), str(cfg)], capture_output=True, text=True)


def _config(source, out, sheet, cell):
    return {"source": str(source), "out": str(out), "sheet": sheet, "author": "Reviewer",
            "template_row": 2, "comments": {cell: "The upper limit is missing."},
            "new_rows": [{"A": "Over limit", "B": "Reject a value over the limit", "C": "Nothing is saved"}]}


def test_rebuild_then_in_place_write_threaded_comments_and_keep_earlier_parts(tmp_path):
    clean, book = tmp_path / "clean.xlsx", tmp_path / "book.xlsx"
    _workbook(clean)

    first = _run(tmp_path, _config(clean, book, "Login", "A2"))
    assert first.returncode == 0, first.stderr
    assert "[rebuild]" in first.stdout and "VERIFY: OK" in first.stdout
    with zipfile.ZipFile(book) as z:
        earlier = {n: z.read(n) for n in z.namelist() if "comment" in n.lower()}
    assert any(n.startswith("xl/threadedComments/") for n in earlier)
    assert openpyxl.load_workbook(book)["Login"]["A3"].value == "Over limit"

    second = _run(tmp_path, _config(book, book, "Search", "C2"))
    assert second.returncode == 0, second.stderr
    assert "[in-place]" in second.stdout and "VERIFY: OK" in second.stdout
    assert (tmp_path / "book.PREV.xlsx").is_file()
    with zipfile.ZipFile(book) as z:
        for name, data in earlier.items():
            assert z.read(name) == data, name
    assert openpyxl.load_workbook(book)["Search"]["A3"].value == "Over limit"


def test_in_place_refuses_a_sheet_that_already_has_comments(tmp_path):
    clean, book = tmp_path / "clean.xlsx", tmp_path / "book.xlsx"
    _workbook(clean)
    assert _run(tmp_path, _config(clean, book, "Login", "A2")).returncode == 0

    again = _run(tmp_path, _config(book, book, "Login", "B2"))
    assert again.returncode != 0
    assert "already has comments" in again.stderr
