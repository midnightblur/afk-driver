"""The gc target: its file in git's common folder, its key, its atomic write, its lock and the receipt of a list."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(AFKV2 / "skills" / "gc" / "scripts"))

import gc_target  # noqa: E402
from gc_repo import FEATURE, build_gc_repo, git  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    return build_gc_repo(tmp_path)


def test_the_target_is_one_file_in_gits_common_folder_from_every_checkout(repo):
    common = Path(git(repo.main, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    expected = common / "afkv2-gc" / "feat%2Fgc.json"
    for checkout in (repo.main, repo.feature, repo.run):
        assert gc_target.target_path(checkout, FEATURE) == expected


@pytest.mark.parametrize("branch, stem", [
    ("feat/gc", "feat%2Fgc"),
    ('a\\b/c:d*e?f"g<h>i|j', "a%5Cb%2Fc%3Ad%2Ae%3Ff%22g%3Ch%3Ei%7Cj"),
    ("50%-off", "50%25-off"),
    ("tab\there\x01\x7f", "tab%09here%01%7F"),
    ("plain-name.v2", "plain-name.v2"),
])
def test_the_file_name_encodes_each_unsafe_character_and_decodes_back(branch, stem):
    assert gc_target.encode_branch(branch) == stem
    assert gc_target.decode_branch(stem) == branch
