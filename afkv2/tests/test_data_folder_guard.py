"""The guard in `conftest.py`: a test with no fixture of its own still has a temporary data folder."""

from __future__ import annotations

import os
from pathlib import Path


def test_a_test_has_a_temporary_data_folder(tmp_path):
    assert Path(os.environ["LOCALAPPDATA"]).parent == tmp_path
