"""The gc target: its file in git's common folder, its key, its atomic write, its lock and the receipt of a list."""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(AFKV2 / "skills" / "gc" / "scripts"))
sys.path.insert(0, str(AFKV2 / "ports"))

import gc_target  # noqa: E402
from gc_repo import FEATURE, build_gc_repo, git  # noqa: E402
from tracker.envelope import Refusal  # noqa: E402


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


def a_target(repo, **fields):
    change = {"number": 7, "url": "https://forge.test/c/7", "state": "merged", "head_sha": "a" * 40, "target": "main"}
    return gc_target.new_target(FEATURE, str(repo.feature), change, {"run worktree": "b" * 40}, "c" * 64, **fields)


def test_a_new_target_holds_every_field_with_its_default(repo):
    target = a_target(repo)
    assert list(target) == ["schema", "feature_branch", "feature_worktree", "run_branch", "run_worktree", "remote",
                            "change", "tips", "receipt", "state", "left", "listed_at"]
    assert target["schema"] == "afkv2.gc/0"
    assert target["run_branch"] == FEATURE + "-run"
    assert target["run_worktree"] == str(repo.feature) + "-run"
    assert (target["remote"], target["state"], target["left"]) == ("origin", "listed", [])
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", target["listed_at"])
    assert a_target(repo, state="waiting", left=["remote feature branch"])["state"] == "waiting"


def test_a_written_target_reads_back_from_every_checkout_and_leaves_git_status_clean(repo):
    target = a_target(repo)
    path = gc_target.write_target(repo.feature, target)
    assert path == gc_target.target_path(repo.main, FEATURE)
    for checkout in (repo.main, repo.feature, repo.run):
        assert gc_target.read_target(checkout, FEATURE) == target
        assert git(checkout, "status", "--short", "--untracked-files=all") == ""
    assert [item.name for item in path.parent.iterdir()] == [path.name]


def test_an_absent_target_reads_as_none(repo):
    assert gc_target.read_target(repo.feature, FEATURE) is None


@pytest.mark.parametrize("text", ['{"schema": "afkv2.gc/9"}', "not json", "[1]", '{"schema": "afkv2.gc/0"}'])
def test_an_unknown_schema_or_a_broken_file_refuses_bad_target(repo, text):
    path = gc_target.target_path(repo.feature, FEATURE)
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(Refusal) as refused:
        gc_target.read_target(repo.feature, FEATURE)
    assert refused.value.code == "bad-target"


def test_a_write_replaces_the_file_whole_or_not_at_all(repo, monkeypatch):
    first = a_target(repo)
    gc_target.write_target(repo.feature, first)

    def broken_replace(source, destination):
        raise OSError("the replace failed")

    monkeypatch.setattr(gc_target.os, "replace", broken_replace)
    with pytest.raises(OSError):
        gc_target.write_target(repo.feature, a_target(repo, state="waiting"))
    path = gc_target.target_path(repo.feature, FEATURE)
    assert gc_target.read_target(repo.feature, FEATURE) == first
    assert [item.name for item in path.parent.iterdir()] == [path.name]


def test_a_second_lock_on_a_held_target_refuses_locked_until_the_first_ends(repo):
    lock = gc_target.take_lock(repo.feature, FEATURE)
    assert lock.path == gc_target.target_path(repo.feature, FEATURE).with_suffix(".lock")
    with pytest.raises(Refusal) as refused:
        gc_target.take_lock(repo.main, FEATURE)
    assert refused.value.code == "locked"
    lock.release()
    with gc_target.take_lock(repo.main, FEATURE):
        with pytest.raises(Refusal):
            gc_target.take_lock(repo.run, FEATURE)
    gc_target.take_lock(repo.run, FEATURE).release()


HOLDER = """
import sys, time
sys.path.insert(0, sys.argv[1])
import gc_target
lock = gc_target.take_lock(sys.argv[2], sys.argv[3])
print("held", flush=True)
time.sleep(120)
"""


def test_the_lock_is_free_again_when_its_holder_is_killed(repo):
    holder = subprocess.Popen([sys.executable, "-c", HOLDER, str(AFKV2 / "skills" / "gc" / "scripts"), str(repo.feature), FEATURE],
                              stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(Refusal):
            gc_target.take_lock(repo.main, FEATURE)
    finally:
        holder.kill()
        holder.wait(timeout=30)
        holder.stdout.close()
    deadline = time.monotonic() + 10
    while True:
        try:
            gc_target.take_lock(repo.main, FEATURE).release()
            break
        except Refusal:
            assert time.monotonic() < deadline, "the lock stayed held after its holder was killed"
            time.sleep(0.1)


def a_list():
    return {
        "change": {"number": 7, "url": "https://forge.test/c/7", "state": "merged", "target": "main"},
        "items": [{"item": "run worktree", "tip": "b" * 40, "link": None, "when": "now", "present": True},
                  {"item": "remote feature branch", "tip": "d" * 40, "link": "https://forge.test/t/d", "when": "now", "present": True}],
        "refusals": [{"code": "uncommitted", "detail": ["notes.txt"]}],
        "ignored": {"count": 3, "first": ["a.log", "b.log", "c.log"]},
        "state": "listed",
    }


def changed(path, value):
    listing = a_list()
    *parents, last = path
    holder = listing
    for key in parents:
        holder = holder[key]
    holder[last] = value
    return listing


def test_the_receipt_is_the_sha256_of_the_list_in_a_fixed_form():
    receipt = gc_target.receipt_of(a_list())
    assert re.fullmatch(r"[0-9a-f]{64}", receipt)
    assert gc_target.receipt_of(a_list()) == receipt
    assert gc_target.receipt_of(dict(reversed(list(a_list().items())))) == receipt
    assert gc_target.receipt_of({**a_list(), "receipt": receipt}) == receipt


@pytest.mark.parametrize("path, value", [
    (("change", "number"), 8),
    (("items", 0, "tip"), "e" * 40),
    (("items", 1, "tip"), ""),
    (("refusals", 0, "detail"), ["notes.txt", "more.txt"]),
    (("ignored", "count"), 4),
])
def test_a_change_of_the_change_a_tip_a_refusal_detail_or_the_ignored_count_gives_another_receipt(path, value):
    assert gc_target.receipt_of(changed(path, value)) != gc_target.receipt_of(a_list())
