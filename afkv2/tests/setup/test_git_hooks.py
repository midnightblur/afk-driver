import subprocess

import setup
from conftest import hooks_dir, v1_stub


def _stubs(repo):
    for hook in ("pre-commit", "reference-transaction"):
        (hooks_dir(repo) / hook).write_bytes(v1_stub(hook))


def test_stubs_move_into_the_backup_and_back(places, repo, runner):
    _stubs(repo)
    before = {h: (hooks_dir(repo) / h).read_bytes() for h in ("pre-commit", "reference-transaction")}
    answer = setup.move_v1_git_hooks(places, repo, runner)
    assert answer["hooks"] == {"pre-commit": "moved", "reference-transaction": "moved"}
    assert not (hooks_dir(repo) / "pre-commit").exists()
    again = setup.move_v1_git_hooks(places, repo, runner)
    assert set(again["hooks"].values()) == {"already-moved"}
    restored = setup.restore_v1_git_hooks(places)
    assert {r["action"] for r in restored} == {"restored"}
    for hook, data in before.items():
        assert (hooks_dir(repo) / hook).read_bytes() == data
    assert not (places.backup / "git-hooks").exists() or not any((places.backup / "git-hooks").iterdir())


def test_marker_as_substring_is_a_foreign_hook(places, repo, runner):
    foreign = b"#!/bin/sh\n# mentions afk-precommit-gates (installed by afk-toolkit install-git-hooks.sh). here\n"
    (hooks_dir(repo) / "pre-commit").write_bytes(foreign)
    answer = setup.move_v1_git_hooks(places, repo, runner)
    assert answer["hooks"]["pre-commit"] == "foreign"
    assert answer["hooks"]["reference-transaction"] == "absent"
    assert (hooks_dir(repo) / "pre-commit").read_bytes() == foreign


def test_hooks_path_set_skips(places, repo, runner):
    _stubs(repo)
    subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", ".husky"], check=True)
    answer = setup.move_v1_git_hooks(places, repo, runner)
    assert answer["action"] == "skipped"
    assert (hooks_dir(repo) / "pre-commit").exists()


def test_setup_writes_no_git_hook(places, repo, runner):
    names_before = {p.name for p in hooks_dir(repo).iterdir()}
    _stubs(repo)
    setup.move_v1_git_hooks(places, repo, runner)
    assert {p.name for p in hooks_dir(repo).iterdir()} == names_before


def test_a_rewritten_different_stub_is_a_conflict(places, repo, runner):
    _stubs(repo)
    setup.move_v1_git_hooks(places, repo, runner)
    (hooks_dir(repo) / "pre-commit").write_bytes(b"#!/bin/sh\nnew\n")
    restored = setup.restore_v1_git_hooks(places)
    conflict = [r for r in restored if r["action"] == "conflict"]
    assert len(conflict) == 1 and conflict[0]["path"].endswith("pre-commit")
