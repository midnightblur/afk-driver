"""Every test gets a temporary data folder, so no test reads or writes the real one under %LOCALAPPDATA%."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def temporary_data_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
