"""The review-qa-tests annotate script: threaded comments and new rows in rebuild and in-place mode, and the on-demand openpyxl install."""

import importlib.util
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "review-qa-tests" / "scripts" / "annotate_sheet.py"


def _module():
    spec = importlib.util.spec_from_file_location("annotate_sheet", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def data_root(tmp_path_factory):
    """A data folder whose python-packages holds openpyxl: the real on-demand install when the environment lacks it."""
    root = tmp_path_factory.mktemp("localappdata")
    if importlib.util.find_spec("openpyxl") is None:
        done = subprocess.run([sys.executable, str(SCRIPT), "--install-dependencies"],
                              env=dict(os.environ, LOCALAPPDATA=str(root)), capture_output=True, text=True)
        if done.returncode != 0:
            pytest.skip(f"on-demand openpyxl install failed: {done.stderr[-500:]}")
        sys.path.insert(0, str(root / "afkv2" / "python-packages"))
    return root


@pytest.fixture
def openpyxl(data_root):
    import openpyxl as module
    return module


def _workbook(openpyxl, path):
    wb = openpyxl.Workbook()
    for name in ("Login", "Search"):
        ws = wb.create_sheet(name)
        ws.append(["Test Name", "Scenario Objective", "Summary"])
        ws.append(["Valid input", "Accept a valid value", "Value is saved"])
    del wb["Sheet"]
    wb.save(path)


def _run(tmp_path, data_root, config, *flags):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config), "utf-8")
    return subprocess.run([sys.executable, *flags, str(SCRIPT), str(cfg)], capture_output=True, text=True,
                          env=dict(os.environ, LOCALAPPDATA=str(data_root)))


def _config(source, out, sheet, cell):
    return {"source": str(source), "out": str(out), "sheet": sheet, "author": "Reviewer",
            "template_row": 2, "comments": {cell: "The upper limit is missing."},
            "new_rows": [{"A": "Over limit", "B": "Reject a value over the limit", "C": "Nothing is saved"}]}


def test_rebuild_then_in_place_write_threaded_comments_and_keep_earlier_parts(tmp_path, data_root, openpyxl):
    clean, book = tmp_path / "clean.xlsx", tmp_path / "book.xlsx"
    _workbook(openpyxl, clean)

    first = _run(tmp_path, data_root, _config(clean, book, "Login", "A2"))
    assert first.returncode == 0, first.stderr
    assert "[rebuild]" in first.stdout and "VERIFY: OK" in first.stdout
    with zipfile.ZipFile(book) as z:
        earlier = {n: z.read(n) for n in z.namelist() if "comment" in n.lower()}
    assert any(n.startswith("xl/threadedComments/") for n in earlier)
    assert openpyxl.load_workbook(book)["Login"]["A3"].value == "Over limit"

    second = _run(tmp_path, data_root, _config(book, book, "Search", "C2"))
    assert second.returncode == 0, second.stderr
    assert "[in-place]" in second.stdout and "VERIFY: OK" in second.stdout
    assert (tmp_path / "book.PREV.xlsx").is_file()
    with zipfile.ZipFile(book) as z:
        for name, data in earlier.items():
            assert z.read(name) == data, name
    assert openpyxl.load_workbook(book)["Search"]["A3"].value == "Over limit"


def test_in_place_refuses_a_sheet_that_already_has_comments(tmp_path, data_root, openpyxl):
    clean, book = tmp_path / "clean.xlsx", tmp_path / "book.xlsx"
    _workbook(openpyxl, clean)
    assert _run(tmp_path, data_root, _config(clean, book, "Login", "A2")).returncode == 0

    again = _run(tmp_path, data_root, _config(book, book, "Login", "B2"))
    assert again.returncode != 0
    assert "already has comments" in again.stderr


def test_missing_openpyxl_exits_3_and_names_the_install_command(tmp_path):
    # -S drops site-packages, so openpyxl is absent unless the empty data folder holds it.
    done = _run(tmp_path, tmp_path / "empty", _config(tmp_path / "a.xlsx", tmp_path / "b.xlsx", "Login", "A2"), "-S")
    assert done.returncode == 3
    assert "MISSING: openpyxl==3.1.5" in done.stderr and "--install-dependencies" in done.stderr
    assert not (tmp_path / "b.xlsx").exists()


def test_install_targets_the_data_folder_with_the_pinned_version(monkeypatch, tmp_path):
    module = _module()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    calls = []
    assert module.install_dependencies(run=lambda cmd: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0)) == 0
    (cmd,) = calls
    assert cmd[:4] == [sys.executable, "-m", "pip", "install"]
    assert cmd[cmd.index("--target") + 1] == str(tmp_path / "afkv2" / "python-packages")
    assert cmd[-1] == "openpyxl==3.1.5"


def test_the_data_folder_comes_before_the_environment(monkeypatch, tmp_path):
    module = _module()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    folder = tmp_path / "afkv2" / "python-packages"
    folder.mkdir(parents=True)
    monkeypatch.setattr(sys, "path", list(sys.path))
    module.use_packages_folder()
    assert sys.path[0] == str(folder)
