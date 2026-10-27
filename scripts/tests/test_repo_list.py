"""Repository list: entries, short-name markers and their invariants on real git repositories."""
from __future__ import annotations

import builtins
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "repo_list.py"
IS_WINDOWS = os.name == "nt"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rl = load(SCRIPT, "afk_repo_list_under_test")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def make_repo(parent: Path, name: str = "proj") -> Path:
    repo = parent / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "dev")
    git(repo, "config", "user.name", "Test User")
    git(repo, "config", "user.email", "t@example.com")
    (repo / "sub").mkdir()
    (repo / "sub" / "README.md").write_text("seed\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "seed")
    return repo


def remove_tree(path: Path) -> None:
    def writable(function, target, *_):
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        function(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=writable)
    else:
        shutil.rmtree(path, onerror=writable)


@pytest.fixture
def home(tmp_path, monkeypatch):
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    return folder


@pytest.fixture
def root(tmp_path):
    folder = tmp_path / "wt-root"
    folder.mkdir()
    return folder


def stored(home: Path) -> dict:
    return json.loads((home / ".afk" / "repositories.json").read_text(encoding="utf-8"))


def marker_of(root: Path, short: str) -> Path:
    return root / short / ".afk-repository"


def same(a: str | Path, b: str | Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def test_a_main_checkout_is_added_with_its_folder_name_and_marker(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    entry = rl.add_repository(repo, root)
    assert entry.short_name == "proj" and same(entry.path, repo)
    assert os.path.isabs(entry.path)
    data = stored(home)
    assert data == {"schema": 1, "repositories": [{"path": entry.path, "shortName": "proj"}]}
    marker = json.loads(marker_of(root, "proj").read_text(encoding="utf-8"))
    assert marker == {"path": entry.path}


def test_a_worktree_or_subfolder_path_adds_its_main_checkout(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    worktree = tmp_path / "elsewhere" / "wt1"
    git(repo, "worktree", "add", "-q", "-b", "wt1", str(worktree))
    entry = rl.add_repository(worktree / "sub", root)
    assert same(entry.path, repo) and entry.short_name == "proj"
    other = make_repo(tmp_path / "src2", "other")
    assert same(rl.add_repository(other / "sub", root).path, other)


def test_a_bare_clone_a_plain_folder_and_a_missing_path_are_refused_with_reasons(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(rl.RepositoryListError, match="bare clone"):
        rl.add_repository(bare, root)
    with pytest.raises(rl.RepositoryListError, match="not a git repository"):
        rl.add_repository(plain, root)
    with pytest.raises(rl.RepositoryListError, match="not a folder"):
        rl.add_repository(tmp_path / "nowhere", root)
    assert not (home / ".afk" / "repositories.json").exists()
    assert list(root.iterdir()) == []


def test_a_listed_path_is_refused_in_any_spelling(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, root)
    with pytest.raises(rl.RepositoryListError, match="already listed as proj"):
        rl.add_repository(str(repo) + os.sep, root, short_name="again")
    if IS_WINDOWS:
        with pytest.raises(rl.RepositoryListError, match="already listed"):
            rl.add_repository(str(repo).upper(), root, short_name="again")
    assert len(stored(home)["repositories"]) == 1
    assert not (root / "again").exists()


def test_a_link_to_the_checkout_is_stored_resolved(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    link = tmp_path / "link"
    try:
        os.symlink(repo, link, target_is_directory=True)
    except OSError:
        pytest.skip("this machine refuses to create a symbolic link")
    entry = rl.add_repository(link, root)
    assert entry.path == os.path.realpath(repo)
    with pytest.raises(rl.RepositoryListError, match="already listed"):
        rl.add_repository(repo, root, short_name="again")


def test_two_clones_of_one_remote_are_two_entries_with_their_own_short_names(home, root, tmp_path):
    origin = make_repo(tmp_path / "origin")
    first, second = tmp_path / "a" / "proj", tmp_path / "b" / "proj"
    for clone in (first, second):
        subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True)
    rl.add_repository(first, root)
    with pytest.raises(rl.RepositoryListError, match="short name is taken"):
        rl.add_repository(second, root)
    rl.add_repository(second, root, short_name="proj-b")
    rows = stored(home)["repositories"]
    assert [row["shortName"] for row in rows] == ["proj", "proj-b"]
    assert same(rows[0]["path"], first) and same(rows[1]["path"], second)


def test_a_short_name_clash_ignores_case_on_windows(home, root, tmp_path):
    rl.add_repository(make_repo(tmp_path / "a"), root)
    other = make_repo(tmp_path / "b", "other")
    if IS_WINDOWS:
        with pytest.raises(rl.RepositoryListError, match="short name is taken"):
            rl.add_repository(other, root, short_name="PROJ")
    else:
        assert rl.add_repository(other, root, short_name="PROJ").short_name == "PROJ"


@pytest.mark.parametrize("name", ["", ".", "..", "a b", "a/b", "a\\b", "x.", "naïve", "a:b"])
def test_a_short_name_that_is_not_one_plain_folder_name_is_refused(home, root, tmp_path, name):
    repo = make_repo(tmp_path / "src")
    with pytest.raises(rl.RepositoryListError, match="not a valid short name"):
        rl.add_repository(repo, root, short_name=name)
    assert list(root.iterdir()) == []


def test_a_default_short_name_outside_the_set_is_refused_so_setup_asks(home, root, tmp_path):
    repo = make_repo(tmp_path / "src", "my repo")
    with pytest.raises(rl.RepositoryListError, match="not a valid short name"):
        rl.add_repository(repo, root)
    assert rl.add_repository(repo, root, short_name="my-repo").short_name == "my-repo"


def test_a_folder_holding_another_paths_marker_refuses_the_short_name(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    (root / "proj").mkdir()
    foreign = json.dumps({"path": str(tmp_path / "someone-else")}) + "\n"
    marker_of(root, "proj").write_text(foreign, encoding="utf-8")
    with pytest.raises(rl.RepositoryListError, match="reserved for"):
        rl.add_repository(repo, root)
    assert marker_of(root, "proj").read_text(encoding="utf-8") == foreign
    assert not (home / ".afk" / "repositories.json").exists()


def test_a_folder_setup_did_not_make_refuses_the_short_name(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    (root / "proj").mkdir()
    (root / "proj" / "notes.txt").write_text("mine\n", encoding="utf-8")
    with pytest.raises(rl.RepositoryListError, match="not made by setup"):
        rl.add_repository(repo, root)
    marker_of(root, "proj").unlink(missing_ok=True)
    (root / "proj" / "notes.txt").unlink()
    (root / "proj" / ".afk-repository").write_text("not json", encoding="utf-8")
    with pytest.raises(rl.RepositoryListError, match="unreadable marker"):
        rl.add_repository(repo, root)


def test_an_empty_folder_is_claimed(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    (root / "proj").mkdir()
    entry = rl.add_repository(repo, root)
    assert json.loads(marker_of(root, "proj").read_text(encoding="utf-8")) == {"path": entry.path}


def test_an_add_stopped_after_the_marker_is_completed_by_the_next_add(home, root, tmp_path, monkeypatch):
    repo = make_repo(tmp_path / "src")
    real_swap = rl.safe_write._swap
    list_path = home / ".afk" / "repositories.json"

    def stop_on_list(temporary, write_target, target, expected):
        if Path(target) == list_path:
            raise rl.safe_write.SafeWriteError("stopped", target)
        return real_swap(temporary, write_target, target, expected)

    monkeypatch.setattr(rl.safe_write, "_swap", stop_on_list)
    with pytest.raises(rl.safe_write.SafeWriteError):
        rl.add_repository(repo, root)
    held = json.loads(marker_of(root, "proj").read_text(encoding="utf-8"))
    assert same(held["path"], repo)
    assert not list_path.exists() or stored(home)["repositories"] == []
    monkeypatch.setattr(rl.safe_write, "_swap", real_swap)
    before = marker_of(root, "proj").stat().st_mtime_ns
    entry = rl.add_repository(repo, root)
    assert entry.short_name == "proj" and len(stored(home)["repositories"]) == 1
    assert marker_of(root, "proj").stat().st_mtime_ns == before


def test_no_lock_file_sits_under_the_root_and_no_repository_file_changes(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    snapshot = sorted((str(p), p.stat().st_size, p.stat().st_mtime_ns)
                      for p in repo.rglob("*") if p.is_file())
    rl.add_repository(repo, root)
    rl.remove_repository("proj", root)
    rl.add_repository(repo, root)
    assert [p.name for p in root.rglob("*")] == ["proj", ".afk-repository"]
    after = sorted((str(p), p.stat().st_size, p.stat().st_mtime_ns)
                   for p in repo.rglob("*") if p.is_file())
    assert after == snapshot
    assert git(repo, "status", "--porcelain", "--ignored") == ""


HOLDER = r"""
import importlib.util, pathlib, sys, time
spec = importlib.util.spec_from_file_location("sw", sys.argv[1])
sw = importlib.util.module_from_spec(spec); spec.loader.exec_module(sw)
ready = pathlib.Path(sys.argv[3])
def hold(text):
    ready.write_text("held")
    time.sleep(float(sys.argv[4]))
    return text
sw.update_locked(sys.argv[2], hold)
"""


def test_the_marker_is_written_only_under_the_lists_lock(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    ready = tmp_path / "ready"
    holder = subprocess.Popen([sys.executable, "-c", HOLDER, str(ROOT / "scripts" / "safe_write.py"),
                               str(home / ".afk" / "repositories.json"), str(ready), "6"])
    try:
        deadline = time.monotonic() + 30
        while not ready.exists():
            assert time.monotonic() < deadline and holder.poll() is None
            time.sleep(0.05)
        with pytest.raises(rl.safe_write.SafeWriteError, match="is locked"):
            rl.add_repository(repo, root)
        assert not (root / "proj").exists()
    finally:
        holder.wait(timeout=60)
    assert rl.add_repository(repo, root).short_name == "proj"


def test_a_gone_folder_is_reported_missing_and_stays_until_removed(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, root)
    assert [entry.missing for entry in rl.all_entries()] == [False]
    remove_tree(repo)
    assert [(entry.short_name, entry.missing) for entry in rl.all_entries()] == [("proj", True)]
    assert len(stored(home)["repositories"]) == 1
    removed = rl.remove_repository("proj", root)
    assert removed.entry.short_name == "proj" and removed.folder_deleted
    assert rl.all_entries() == [] and not (root / "proj").exists()


def test_repoint_moves_a_missing_entry_and_its_marker(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, root)
    moved = make_repo(tmp_path / "moved")
    with pytest.raises(rl.RepositoryListError, match="still exists"):
        rl.repoint_repository("proj", moved, root)
    remove_tree(repo)
    entry = rl.repoint_repository("proj", moved / "sub", root)
    assert same(entry.path, moved) and entry.short_name == "proj"
    assert stored(home)["repositories"] == [{"path": entry.path, "shortName": "proj"}]
    assert json.loads(marker_of(root, "proj").read_text(encoding="utf-8")) == {"path": entry.path}
    with pytest.raises(rl.RepositoryListError, match="is not listed"):
        rl.repoint_repository("nope", moved, root)


def test_repoint_refuses_a_path_listed_under_another_entry(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    other = make_repo(tmp_path / "other-src", "other")
    rl.add_repository(repo, root)
    rl.add_repository(other, root)
    remove_tree(repo)
    with pytest.raises(rl.RepositoryListError, match="already listed as other"):
        rl.repoint_repository("proj", other, root)
    assert json.loads(marker_of(root, "proj").read_text(encoding="utf-8"))["path"] == str(
        stored(home)["repositories"][0]["path"])


def test_remove_keeps_the_marker_while_a_worktree_remains_in_the_folder(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, root)
    git(repo, "worktree", "add", "-q", "-b", "wt1", str(root / "proj" / "wt1"))
    removed = rl.remove_repository("proj", root)
    assert not removed.folder_deleted
    assert marker_of(root, "proj").is_file() and (root / "proj" / "wt1").is_dir()
    assert rl.all_entries() == []
    with pytest.raises(rl.RepositoryListError, match="is not listed"):
        rl.remove_repository("proj", root)


def test_remove_with_an_empty_folder_deletes_the_marker_and_folder(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, root)
    rl.add_repository(make_repo(tmp_path / "b", "other"), root)
    assert rl.remove_repository("PROJ" if IS_WINDOWS else "proj", root).folder_deleted
    assert not (root / "proj").exists()
    assert [entry.short_name for entry in rl.all_entries()] == ["other"]


def test_a_higher_schema_is_refused_with_an_update_message_and_left_alone(home, root, tmp_path):
    list_path = home / ".afk" / "repositories.json"
    list_path.parent.mkdir()
    text = json.dumps({"schema": 2, "repositories": []})
    list_path.write_text(text, encoding="utf-8")
    repo = make_repo(tmp_path / "src")
    for call in (lambda: rl.add_repository(repo, root), rl.all_entries, lambda: rl.find_entry(repo)):
        with pytest.raises(rl.RepositoryListError, match="schema 2.*update the plugin"):
            call()
    assert list_path.read_text(encoding="utf-8") == text
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("text", ["{", "[]", '{"schema": "1"}', '{"schema": 1, "repositories": [{"path": 1}]}'])
def test_a_damaged_list_is_refused_and_left_alone(home, root, tmp_path, text):
    list_path = home / ".afk" / "repositories.json"
    list_path.parent.mkdir()
    list_path.write_text(text, encoding="utf-8")
    with pytest.raises(rl.RepositoryListError, match="fix or delete it"):
        rl.add_repository(make_repo(tmp_path / "src"), root)
    assert list_path.read_text(encoding="utf-8") == text


def test_find_entry_matches_checkout_subfolder_and_root_folder_by_text(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    entry = rl.add_repository(repo, root)
    assert rl.find_entry(repo) == entry
    assert rl.find_entry(repo / "sub" / "not-yet-made") == entry
    assert rl.find_entry(str(repo) + "-sibling") is None
    assert rl.find_entry(root / "proj" / "wt1") is None
    assert rl.find_entry(root / "proj" / "wt1", root=root) == entry
    assert rl.find_entry(root / "proj-2", root=root) is None
    if IS_WINDOWS:
        assert rl.find_entry(str(repo / "sub").upper()) == entry


def test_find_entry_picks_the_innermost_listed_checkout(home, root, tmp_path):
    outer = make_repo(tmp_path / "src", "outer")
    inner = make_repo(outer / "vendor", "inner")
    rl.add_repository(outer, root)
    rl.add_repository(inner, root)
    assert rl.find_entry(inner / "sub").short_name == "inner"
    assert rl.find_entry(outer / "sub").short_name == "outer"


def test_find_entry_reads_only_the_list_file_and_starts_no_process(home, root, tmp_path, monkeypatch):
    repo = make_repo(tmp_path / "src")
    rl.add_repository(repo, root)
    opened = []
    real_open = builtins.open

    def recording_open(file, *args, **kwargs):
        opened.append(Path(file))
        return real_open(file, *args, **kwargs)

    def no_process(*args, **kwargs):
        raise AssertionError("find_entry started a process")

    monkeypatch.setattr(builtins, "open", recording_open)
    monkeypatch.setattr(subprocess, "run", no_process)
    monkeypatch.setattr(subprocess, "Popen", no_process)
    assert rl.find_entry(root / "proj" / "wt1", root=root).short_name == "proj"
    assert opened == [home / ".afk" / "repositories.json"]


def test_an_empty_list_finds_nothing_and_lists_nothing(home, root, tmp_path):
    assert rl.find_entry(tmp_path) is None
    assert rl.all_entries() == []
    with pytest.raises(rl.RepositoryListError, match="is not listed"):
        rl.remove_repository("proj", root)


def test_a_relative_root_is_refused(home, tmp_path):
    with pytest.raises(rl.RepositoryListError, match="not an absolute path"):
        rl.add_repository(make_repo(tmp_path / "src"), "relative/root")


def test_a_new_process_reads_the_same_list(home, root, tmp_path):
    repo = make_repo(tmp_path / "src")
    entry = rl.add_repository(repo, root)
    code = ("import importlib.util, json, sys; s = importlib.util.spec_from_file_location('rl', sys.argv[1]);"
            " m = importlib.util.module_from_spec(s); s.loader.exec_module(m);"
            " print(json.dumps([list(e) for e in m.all_entries()]))")
    done = subprocess.run([sys.executable, "-c", code, str(SCRIPT)], capture_output=True, text=True,
                          check=True, env=dict(os.environ, HOME=str(home), USERPROFILE=str(home)))
    assert json.loads(done.stdout) == [[entry.path, "proj"]]


def test_a_callers_git_redirect_does_not_change_the_main_checkout(home, root, tmp_path, monkeypatch):
    repo = make_repo(tmp_path / "src")
    other = make_repo(tmp_path / "other-src", "other")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    assert same(rl.add_repository(repo / "sub", root).path, repo)


def test_only_setup_code_calls_the_read_all_call():
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True,
                           check=True).stdout.decode("utf-8").split("\0")
    allowed = ("scripts/repo_list.py", "scripts/tests/test_repo_list.py")
    callers = []
    for name in files:
        if not name.endswith((".py", ".sh")) or name in allowed or name.startswith("skills/afk/setup/"):
            continue
        path = ROOT / name
        if path.is_file() and "all_entries(" in path.read_text(encoding="utf-8", errors="replace"):
            callers.append(name)
    assert callers == []
