#!/usr/bin/env afk-python
"""Repository list: the machine-wide list of main checkouts and their short-name markers.

    find_entry(path, *, root=None) -> Entry | None
    all_entries() -> list[Entry]                       (setup only)
    add_repository(path, root, short_name=None) -> Entry
    remove_repository(short_name, root) -> Removed
    repoint_repository(short_name, path, root) -> Entry

The list is `~/.afk/repositories.json` (`schema` 1, `repositories` in the order
added, each entry `path` and `shortName`). Each entry reserves one folder
`<root>/<shortName>`, whose `.afk-repository` marker holds the entry's path.
Every list and marker write goes through the safe writer (`safe_write.py`)
under the list's lock, so no lock file sits in a folder under the root.

A stored path is absolute with links resolved; paths and short names compare
without case on Windows. `find_entry` matches path text against the list file
alone and never starts git, so a worktree outside its main checkout and outside
`<root>/<shortName>` finds nothing; pass `main_checkout(path)` to find its entry.
Add and repoint resolve a worktree or subfolder to
its main checkout with git, and refuse a bare clone, a folder that is not a git
repository, and a path already listed. A refusal raises
`RepositoryListError`; a refused write raises the safe writer's
`SafeWriteError`. Standard library only.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import NamedTuple

SCHEMA = 1
LIST_NAME = "repositories.json"
MARKER_NAME = ".afk-repository"
GIT_TIMEOUT_SECONDS = 20
_SHORT_NAME = re.compile(r"[A-Za-z0-9._-]+\Z")
_WINDOWS_DEVICE = re.compile(r"(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(\..*)?\Z", re.IGNORECASE)
_GIT_REDIRECTS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_PREFIX",
)
_ENCODING = "utf-8"


def _load_safe_writer():
    name = "afk_safe_write"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            name, pathlib.Path(__file__).resolve().parent / "safe_write.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    return sys.modules[name]


safe_write = _load_safe_writer()


class RepositoryListError(Exception):
    """The list refused a call; `reason` says why, `subject` names the path or short name."""

    def __init__(self, reason: str, subject: object) -> None:
        self.reason = reason
        self.subject = str(subject)
        super().__init__(f"{subject}: {reason}")


class Entry(NamedTuple):
    path: str
    short_name: str

    @property
    def missing(self) -> bool:
        """True when the main checkout folder is gone."""
        return not os.path.isdir(self.path)


class Removed(NamedTuple):
    entry: Entry
    folder_deleted: bool


def list_file() -> pathlib.Path:
    return pathlib.Path.home() / ".afk" / LIST_NAME


def normalize(path: str | os.PathLike) -> str:
    """Absolute path with `~` expanded and links resolved."""
    return os.path.realpath(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _key(path: str) -> str:
    return os.path.normcase(path)


def _within(child_key: str, parent_key: str) -> bool:
    parent = parent_key.rstrip("\\/")
    return child_key == parent_key or child_key.startswith(parent + os.sep)


def find_entry(path: str | os.PathLike, *, root: str | os.PathLike | None = None) -> Entry | None:
    """The entry whose main checkout, or whose `<root>/<shortName>` folder, holds `path`, by text."""
    entries = _read_list()
    key = _key(normalize(path))
    holders = [entry for entry in entries if _within(key, _key(entry.path))]
    if holders:
        return max(holders, key=lambda entry: len(entry.path))
    if root is not None:
        base = normalize(root)
        for entry in entries:
            if _within(key, _key(os.path.join(base, entry.short_name))):
                return entry
    return None


def all_entries() -> list[Entry]:
    """Every listed entry in the order added. Only setup calls this."""
    return _read_list()


def add_repository(
    path: str | os.PathLike, root: str | os.PathLike, short_name: str | None = None
) -> Entry:
    """List the main checkout holding `path`; the marker is written before the entry."""
    main = main_checkout(path)
    name = os.path.basename(main) if short_name is None else short_name
    base = _root(root)
    added: list[Entry] = []

    def transform(text: str) -> str:
        entries = _parse(text)
        _refuse_listed(entries, main, name)
        _claim_folder(base, name, main)
        added.append(Entry(main, name))
        return _dump([*entries, added[0]])

    safe_write.update_locked(list_file(), transform)
    return added[0]


def remove_repository(short_name: str, root: str | os.PathLike) -> Removed:
    """Drop an entry, then its marker and folder when the folder holds nothing else."""
    base = _root(root)
    dropped: list[Entry] = []
    released: list[bool] = []

    def drop(text: str) -> str:
        entries = _parse(text)
        dropped.append(_named(entries, short_name))
        return _dump([other for other in entries if other is not dropped[0]])

    def release(text: str) -> str:
        entries = _parse(text)
        entry = dropped[0]
        taken = any(_key(other.short_name) == _key(entry.short_name) for other in entries)
        released.append(not taken and _release_folder(base, entry))
        return text

    safe_write.update_locked(list_file(), drop)
    try:
        safe_write.update_locked(list_file(), release)
    except safe_write.SafeWriteError:
        released[:] = [False]
    return Removed(dropped[0], bool(released and released[0]))


def repoint_repository(short_name: str, path: str | os.PathLike, root: str | os.PathLike) -> Entry:
    """Give an entry whose main checkout folder is gone the main checkout holding `path`."""
    main = main_checkout(path)
    base = _root(root)
    moved: list[Entry] = []

    def transform(text: str) -> str:
        entries = _parse(text)
        entry = _named(entries, short_name)
        if not entry.missing:
            raise RepositoryListError(
                f"its main checkout {entry.path} still exists; repoint only an entry whose folder is gone",
                short_name)
        others = [other for other in entries if other is not entry]
        _refuse_listed(others, main, None)
        _claim_folder(base, entry.short_name, main, previous=entry.path)
        moved.append(Entry(main, entry.short_name))
        return _dump([moved[0] if other is entry else other for other in entries])

    safe_write.update_locked(list_file(), transform)
    return moved[0]


def main_checkout(path: str | os.PathLike) -> str:
    """The normalized main checkout of the repository holding `path`; refuses bare and non-git."""
    target = normalize(path)
    if not os.path.isdir(target):
        raise RepositoryListError("is not a folder", target)
    done = _git(target, "-C", target, "worktree", "list", "--porcelain")
    if done.returncode != 0:
        cause = (done.stderr.strip().splitlines() or ["no output"])[-1]
        raise RepositoryListError(f"is not a git repository ({cause})", target)
    first = done.stdout.split("\n\n", 1)[0].splitlines()
    if not first or not first[0].startswith("worktree "):
        raise RepositoryListError("git named no main checkout", target)
    if "bare" in first[1:]:
        raise RepositoryListError("is a bare clone; add a clone with a working folder", target)
    main = normalize(first[0][len("worktree "):])
    if not os.path.isdir(main):
        raise RepositoryListError(f"its main checkout {main} is gone", target)
    if not os.path.exists(os.path.join(main, ".git")):
        main = _apart_main(target, main)
    return main


def _apart_main(target: str, git_folder: str) -> str:
    """Main checkout of a repository whose git folder lies apart (a submodule, a separate git folder)."""
    done = _git(target, f"--git-dir={git_folder}", "config", "--local", "--get", "core.worktree")
    if done.returncode == 0 and done.stdout.strip():
        main = normalize(os.path.join(git_folder, done.stdout.strip()))
    else:
        done = _git(target, "-C", target, "rev-parse", "--path-format=absolute",
                    "--git-dir", "--show-toplevel")
        lines = done.stdout.splitlines()
        if done.returncode != 0 or len(lines) != 2 or _key(normalize(lines[0])) != _key(git_folder):
            raise RepositoryListError(
                f"git names its git folder {git_folder} as the main checkout; add the main checkout itself",
                target)
        main = normalize(lines[1])
    if not os.path.isdir(main):
        raise RepositoryListError(f"its main checkout {main} is gone", target)
    return main


def _git(target: str, *args: str) -> subprocess.CompletedProcess:
    environment = {k: v for k, v in os.environ.items() if k not in _GIT_REDIRECTS}
    try:
        return subprocess.run(
            ["git", *args], cwd=target, capture_output=True, text=True, encoding=_ENCODING,
            errors="surrogateescape", env=environment, timeout=GIT_TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        raise RepositoryListError("git is not on PATH", target) from None
    except subprocess.TimeoutExpired:
        raise RepositoryListError(f"git did not answer within {GIT_TIMEOUT_SECONDS} s", target) from None


def _root(root: str | os.PathLike) -> pathlib.Path:
    raw = os.path.expanduser(os.fspath(root))
    if not os.path.isabs(raw):
        raise RepositoryListError("the worktree root is not an absolute path", raw)
    return pathlib.Path(normalize(raw))


def _check_short_name(name: str) -> None:
    if not _SHORT_NAME.match(name) or name in {".", ".."}:
        raise RepositoryListError(
            "is not a valid short name: use one folder name of letters, digits, dot, dash, "
            "underscore; pick another", name)
    if os.name == "nt" and name.endswith("."):
        raise RepositoryListError("ends in a dot, which Windows drops from a folder name; pick another", name)
    if os.name == "nt" and _WINDOWS_DEVICE.match(name):
        raise RepositoryListError("is a Windows device name, not a folder name; pick another", name)


def _refuse_listed(entries: list[Entry], main: str, name: str | None) -> None:
    """Refuse a listed path first, then an invalid or taken short name."""
    for entry in entries:
        if _key(entry.path) == _key(main):
            raise RepositoryListError(f"is already listed as {entry.short_name}", main)
    if name is None:
        return
    _check_short_name(name)
    for entry in entries:
        if _key(entry.short_name) == _key(name):
            raise RepositoryListError(f"short name is taken by {entry.path}; pick another", name)


def _named(entries: list[Entry], short_name: str) -> Entry:
    for entry in entries:
        if _key(entry.short_name) == _key(short_name):
            return entry
    raise RepositoryListError("is not listed", short_name)


def _marker_holder(marker: pathlib.Path) -> str | None:
    """The path a marker holds, None when there is no marker, "" when it is unreadable."""
    try:
        with open(marker, encoding=_ENCODING) as handle:
            held = json.load(handle).get("path")
    except FileNotFoundError:
        return None
    except (OSError, ValueError, AttributeError):
        return ""
    return held if isinstance(held, str) else ""


def _claim_folder(base: pathlib.Path, name: str, main: str, previous: str | None = None) -> None:
    folder = base / name
    marker = folder / MARKER_NAME
    held = _marker_holder(marker)
    ours = {_key(main)} | ({_key(previous)} if previous else set())
    if held is None and folder.exists() and not (folder.is_dir() and not any(folder.iterdir())):
        raise RepositoryListError(
            "folder was not made by setup for this repository; pick another short name", folder)
    if held is not None and _key(held) not in ours:
        raise RepositoryListError(
            f"folder is reserved for {held or 'an unreadable marker'}; pick another short name", folder)
    if held is not None and _key(held) == _key(main):
        return
    folder.mkdir(parents=True, exist_ok=True)
    before = marker.read_bytes() if held is not None else b""
    text = json.dumps({"path": main}, indent=2) + "\n"
    # The caller holds the list's lock, so the marker write takes no lock of its own.
    safe_write._replace_if_unchanged(marker, before, text.encode(_ENCODING), False)


def _release_folder(base: pathlib.Path, entry: Entry) -> bool:
    folder = base / entry.short_name
    marker = folder / MARKER_NAME
    held = _marker_holder(marker)
    if held is None or _key(held) != _key(entry.path):
        return False
    if [child.name for child in folder.iterdir()] != [MARKER_NAME]:
        return False
    kept = marker.read_bytes()
    marker.unlink()
    try:
        folder.rmdir()
    except OSError:
        safe_write._replace_if_unchanged(marker, b"", kept, False)
        return False
    return True


def _read_list() -> list[Entry]:
    try:
        with open(list_file(), encoding=_ENCODING) as handle:
            text = handle.read()
    except FileNotFoundError:
        return []
    return _parse(text)


def _parse(text: str) -> list[Entry]:
    if not text.strip():
        return []
    try:
        data = json.loads(text)
    except ValueError:
        raise RepositoryListError("is not valid JSON; fix or delete it", list_file()) from None
    schema = data.get("schema") if isinstance(data, dict) else None
    if type(schema) is not int:
        raise RepositoryListError("has no integer `schema`; fix or delete it", list_file())
    if schema > SCHEMA:
        raise RepositoryListError(
            f"has schema {schema}, newer than this plugin reads ({SCHEMA}); update the plugin",
            list_file())
    if schema != SCHEMA:
        raise RepositoryListError(f"has unknown schema {schema}; fix or delete it", list_file())
    rows = data.get("repositories", [])
    if not isinstance(rows, list) or not all(
        isinstance(row, dict) and isinstance(row.get("path"), str)
        and isinstance(row.get("shortName"), str) for row in rows
    ):
        raise RepositoryListError("has a malformed `repositories` list; fix or delete it", list_file())
    return [Entry(row["path"], row["shortName"]) for row in rows]


def _dump(entries: list[Entry]) -> str:
    rows = [{"path": entry.path, "shortName": entry.short_name} for entry in entries]
    return json.dumps({"schema": SCHEMA, "repositories": rows}, indent=2) + "\n"
