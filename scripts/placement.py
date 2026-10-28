#!/usr/bin/env afk-python
"""Placement: the worktree root rules (catalog R) and the worktree folder of a listed repository.

    root_state() -> RootState
    target_for(folder, name, *, environ=None) -> Verdict
    check_target(target, folder, *, environ=None) -> Verdict

The root is `developer.worktreeRoot` of the machine file (`~/.afk/config.yaml`,
parsed alone, never merged), else its old `developer.worktreeBasePath`, else the
suggestion `~/repo-worktrees`. `ROOT_RULES` holds one check per catalog R row in
catalog order; the first failed check refuses, and R-04 only warns. Every call
reads the files again (R-07), so no answer is cached.

`folder` is the folder git runs in. Its repository is found by path text against
the repository list; git starts only for an unusual layout: a `GIT_DIR`,
`GIT_COMMON_DIR` or `GIT_WORK_TREE` variable, or a `.git` that is not the
entry's main checkout or a worktree under `<root>/<short name>` (a submodule, a
nested clone, a worktree elsewhere). A target is inside when, with `~`
expanded, made absolute against `folder` and links resolved, it lies below
`<root>/<short name>`; paths compare without case on Windows. Placement reads
only the machine file, the list file and the entry's short-name marker. A file
or git failure raises `PlacementError`; an unreadable machine file still lets an
unlisted repository answer not listed. Standard library only.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys
from typing import Callable, Mapping, NamedTuple

CONFIRMED, SUGGESTED, REFUSED = "confirmed", "suggested", "refused"
INSIDE, NOT_LISTED = "inside", "not listed"
OUTSIDE = "outside"
SUGGESTION_NAME = "repo-worktrees"
_REDIRECTS = ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE")
_HERE = pathlib.Path(__file__).resolve().parent


def _load(name: str, file: str):
    loaded = sys.modules.get(name)
    if loaded is not None and pathlib.Path(getattr(loaded, "__file__", None) or "").resolve() != _HERE / file:
        name = f"_afk_placement_{name}"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, _HERE / file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    return sys.modules[name]


afk_config = _load("afk_config", "afk-config.py")
repo_list = _load("afk_repo_list", "repo_list.py")


class PlacementError(Exception):
    """A file or git could not be read, so placement has no answer."""


class Finding(NamedTuple):
    rule: str
    reason: str


class RootState(NamedTuple):
    path: str
    state: str
    source: str
    rule: str | None = None
    reason: str | None = None
    warnings: tuple[Finding, ...] = ()


class Verdict(NamedTuple):
    state: str
    target: str | None
    folder: str | None = None
    rule: str | None = None
    reason: str | None = None
    warnings: tuple[Finding, ...] = ()


class _Ask(NamedTuple):
    root: object
    entry: object | None = None
    folder: str | None = None


class Rule(NamedTuple):
    id: str
    scope: str
    check: Callable[[_Ask], str | None]
    warns: bool = False


def machine_file() -> pathlib.Path:
    return pathlib.Path.home() / ".afk" / "config.yaml"


def _key(path: str) -> str:
    return os.path.normcase(repo_list.normalize(path))


def _below(child: str, parent: str) -> bool:
    child_key, parent_key = _key(child), _key(parent)
    return child_key != parent_key and child_key.startswith(parent_key.rstrip("\\/") + os.sep)


def _absolute(ask: _Ask) -> str | None:
    root = ask.root
    if not isinstance(root, str):
        return f"{root!r} is not a path"
    drive_missing = os.name == "nt" and not os.path.splitdrive(root)[0]
    if root.startswith("~") or not os.path.isabs(root) or drive_missing:
        return f"{root} is not an absolute path"
    return None


def _outside_repositories(ask: _Ask) -> str | None:
    for start in dict.fromkeys((os.path.abspath(ask.root), repo_list.normalize(ask.root))):
        top = _git_top(start)
        if top is not None:
            return f"{ask.root} is inside the git repository {top}"
    return None


def _exists(ask: _Ask) -> str | None:
    if os.path.isdir(ask.root):
        return None
    if os.path.lexists(ask.root):
        return f"{ask.root} is not a folder"
    return f"{ask.root} does not exist; run /afk:setup to create it"


def _no_space(ask: _Ask) -> str | None:
    if " " in ask.root:
        return (f"{ask.root} has a space; worktrees of a repository that builds with Maven "
                "share the default Maven cache")
    return None


def _short_name_free(ask: _Ask) -> str | None:
    """A valid folder name that no entry listed earlier also claims under the root."""
    name = ask.entry.short_name
    try:
        repo_list._check_short_name(name)
    except repo_list.RepositoryListError as error:
        return f"short name {name} {error.reason}"
    owner = _find(os.path.join(ask.root, name), ask.root)
    if owner is not None and _key(owner.path) != _key(ask.entry.path):
        return f"short name {name} is also listed for {owner.path}; pick another"
    return None


def _short_name_folder(ask: _Ask) -> str | None:
    folder = ask.folder or os.path.join(ask.root, ask.entry.short_name)
    if not os.path.lexists(folder):
        return None
    if not os.path.isdir(folder):
        return f"{folder} is not a folder; pick another short name"
    held = repo_list._marker_holder(pathlib.Path(folder) / repo_list.MARKER_NAME)
    if held is None:
        try:
            empty = not any(os.scandir(folder))
        except OSError as error:
            raise PlacementError(f"{folder}: cannot be read ({error})") from error
        return None if empty else f"{folder} was not made by setup for {ask.entry.path}; pick another short name"
    if os.path.normcase(held) != os.path.normcase(ask.entry.path):
        return f"{folder} is reserved for {held or 'an unreadable marker'}; pick another short name"
    return None


ROOT_RULES = (
    Rule("R-01", "root", _absolute),
    Rule("R-02", "root", _outside_repositories),
    Rule("R-03", "root", _exists),
    Rule("R-04", "root", _no_space, warns=True),
    Rule("R-05", "short name", _short_name_free),
    Rule("R-06", "short name", _short_name_folder),
)


def _run(rules, ask: _Ask) -> tuple[Finding | None, tuple[Finding, ...]]:
    """First failure in catalog order, and the warnings met before it."""
    warnings: list[Finding] = []
    for rule in rules:
        reason = rule.check(ask)
        if reason is None:
            continue
        if not rule.warns:
            return Finding(rule.id, reason), tuple(warnings)
        warnings.append(Finding(rule.id, reason))
    return None, tuple(warnings)


def _given(value) -> bool:
    return value is not None and not (isinstance(value, str) and not value.strip())


def _candidate() -> tuple[object, str, str]:
    try:
        document = afk_config.parse_single_file(machine_file())
    except afk_config.ConfigError as error:
        raise PlacementError(str(error)) from error
    developer = document.get("developer", {})
    if developer is None:
        developer = {}
    if not isinstance(developer, dict):
        raise PlacementError(f"{machine_file()}: `developer` is not a mapping")
    if _given(developer.get("worktreeRoot")):
        return developer["worktreeRoot"], CONFIRMED, "developer.worktreeRoot"
    if _given(developer.get("worktreeBasePath")):
        return developer["worktreeBasePath"], SUGGESTED, "developer.worktreeBasePath"
    return str(pathlib.Path.home() / SUGGESTION_NAME), SUGGESTED, "suggestion"


def root_state() -> RootState:
    """The root and its state: confirmed, suggested, or refused with the first failed rule."""
    value, state, source = _candidate()
    ask = _Ask(value)
    failed, warnings = _run([rule for rule in ROOT_RULES if rule.scope == "root"], ask)
    path = os.path.normpath(value) if failed is None else str(value)
    if failed is not None:
        return RootState(path, REFUSED, source, failed.rule, failed.reason, warnings)
    return RootState(path, state, source, warnings=warnings)


def target_for(folder: str | os.PathLike, name: str, *, environ: Mapping[str, str] | None = None) -> Verdict:
    """`<root>/<short name>/<name>` for the repository at `folder`, not listed, or refused."""
    _require_text(folder)
    _require_text(name)
    return _place(folder, environ, None, name)


def check_target(target: str | os.PathLike, folder: str | os.PathLike, *,
                 environ: Mapping[str, str] | None = None) -> Verdict:
    """Whether a worktree at `target`, for the repository at `folder`, lies inside `<root>/<short name>`."""
    _require_text(target)
    _require_text(folder)
    raw = os.path.expanduser(os.fspath(target))
    absolute = raw if os.path.isabs(raw) else os.path.join(os.path.abspath(os.fspath(folder)), raw)
    return _place(folder, environ, os.path.realpath(absolute), None)


def _place(folder, environ, target: str | None, name: str | None) -> Verdict:
    environ = os.environ if environ is None else environ
    try:
        root = root_state()
    except PlacementError:
        if _entry_for(os.fspath(folder), environ, None) is None:
            return Verdict(NOT_LISTED, target)
        raise
    rooted = root.rule != "R-01"
    entry = _entry_for(os.fspath(folder), environ, root.path if rooted else None)
    if entry is None:
        return Verdict(NOT_LISTED, target)
    base = os.path.join(root.path, entry.short_name) if rooted else None
    if name is not None:
        target = os.path.normpath(os.path.join(base, name)) if base is not None else None
    if root.state == REFUSED:
        return Verdict(REFUSED, target, base, root.rule, root.reason, root.warnings)
    if name is None:  # a new target keeps the folder as written (a subst drive stays); a check resolves it
        base = os.path.realpath(base)
    failed, _ = _run([rule for rule in ROOT_RULES if rule.scope == "short name"], _Ask(root.path, entry, base))
    if failed is not None:
        return Verdict(REFUSED, target, base, failed.rule, failed.reason, root.warnings)
    if not _below(target, base):
        return Verdict(REFUSED, target, base, OUTSIDE, f"{target} is outside {base}", root.warnings)
    return Verdict(INSIDE, target, base, warnings=root.warnings)


def _find(path: str, root: str | None):
    try:
        return repo_list.find_entry(path, root=root)
    except repo_list.RepositoryListError as error:
        raise PlacementError(str(error)) from error


def _entry_for(folder: str, environ: Mapping[str, str], root: str | None):
    """The listed entry whose repository git acts on from `folder`; by text when the layout allows."""
    if not any(environ.get(name) for name in _REDIRECTS):
        top = _git_top(repo_list.normalize(folder))
        if top is None:
            return None
        entry = _find(top, root)
        if entry is not None and (_key(entry.path) == _key(top) or _worktree_under(top, root, entry)):
            return entry
        if entry is None and os.path.isdir(os.path.join(top, ".git")):
            return None
    main = _main_by_git(folder, environ)
    if main is None:
        return None
    entry = _find(main, None)
    return entry if entry is not None and _key(entry.path) == _key(main) else None


def _worktree_under(top: str, root: str | None, entry) -> bool:
    """`top` is a worktree below `<root>/<short name>`, not a repository nested in one."""
    if root is None or not os.path.isfile(os.path.join(top, ".git")):
        return False
    base = os.path.join(root, entry.short_name)
    outer = _git_top(os.path.dirname(top))
    return _below(top, base) and (outer is None or not _below(outer, base))


def _git_top(start: str) -> str | None:
    """The nearest folder at or above `start` holding a `.git`."""
    folder = start
    while True:
        if os.path.lexists(os.path.join(folder, ".git")):
            return folder
        parent = os.path.dirname(folder)
        if parent == folder:
            return None
        folder = parent


def _main_by_git(folder: str, environ: Mapping[str, str]) -> str | None:
    """The main checkout git names for `folder`; None when git finds no repository there."""
    done = _git(folder, environ, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if done.returncode != 0 or not done.stdout.strip():
        return None
    common = repo_list.normalize(done.stdout.strip())
    if os.path.basename(common).lower() == ".git":
        return os.path.dirname(common)
    done = _git(folder, environ, "config", "--file", os.path.join(common, "config"), "--get", "core.worktree")
    if done.returncode != 0 or not done.stdout.strip():
        return None
    return repo_list.normalize(os.path.join(common, done.stdout.strip()))


def _git(folder: str, environ: Mapping[str, str], *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", folder, *args], capture_output=True, text=True,
            encoding="utf-8", errors="surrogateescape", env=dict(environ),
            timeout=repo_list.GIT_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        raise PlacementError("git is not on PATH") from None
    except subprocess.TimeoutExpired:
        raise PlacementError(f"git did not answer within {repo_list.GIT_TIMEOUT_SECONDS} s in {folder}") from None


def _require_text(value) -> None:
    if not isinstance(value, (str, os.PathLike)) or not os.fspath(value).strip():
        raise PlacementError(f"{value!r}: is empty; give a path")
