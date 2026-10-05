#!/usr/bin/env python3
"""Install or remove sentinel-delimited instruction blocks.

Commands:
  install_block.py install <source.md> <target.md> [options]
  install_block.py teardown <target.md> [options]

Options use ``--sentinel NAME`` for the unified block and repeated
``--remove-sentinel NAME`` values for migration blocks. The default unified
name is ``behaviors``. The default migration names cover H7, H8, and H10.

The legacy form remains available:
``install_block.py <source.md> <target.md> [sentinel]``. It replaces the first
matching block and returns 1 when the target has no matching block.
"""

from __future__ import annotations

import argparse
import contextlib
import pathlib
import re
import os
import stat
import sys
import tempfile
import time
from typing import NamedTuple, Sequence


LEGACY_SENTINELS = ("plain-language", "lavish-sessions", "investigation")
MARKER_RE = re.compile(br"<!-- afk:([a-z0-9-]+):(start|end) -->")


class InstallError(ValueError):
    """A source or target does not satisfy the block contract."""


class Result(NamedTuple):
    action: str
    removed: int
    changed: bool


def sentinel_pattern(name: str) -> re.Pattern[bytes]:
    escaped = re.escape(name).encode("ascii")
    return re.compile(
        b"<!-- afk:" + escaped + b":start -->.*?<!-- afk:" + escaped + b":end -->",
        re.DOTALL,
    )


def _source_block(source: pathlib.Path, sentinel: str) -> bytes:
    matches = sentinel_pattern(sentinel).findall(source.read_bytes())
    if len(matches) != 1:
        raise InstallError(
            f"{source} must carry exactly one {sentinel} block; found {len(matches)}"
        )
    return matches[0].replace(b"\r\n", b"\n")


def _target_eol(target: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in target else b"\n"


def _matches(target: bytes, names: Sequence[str]) -> list[tuple[int, int, str]]:
    accepted = set(names)
    found: list[tuple[int, int, str]] = []
    issues: list[str] = []
    opened: tuple[int, str] | None = None
    for event in MARKER_RE.finditer(target):
        name = event.group(1).decode("ascii")
        kind = event.group(2).decode("ascii")
        if name not in accepted:
            continue
        if kind == "start":
            if opened is not None:
                issues.append(
                    f"nested start {name} at byte {event.start()} inside {opened[1]}"
                )
                continue
            opened = (event.start(), name)
            continue
        if opened is None:
            issues.append(f"unmatched end {name} at byte {event.start()}")
            continue
        if opened[1] != name:
            issues.append(
                f"crossed end {name} at byte {event.start()} while {opened[1]} is open"
            )
            continue
        found.append((opened[0], event.end(), name))
        opened = None
    if opened is not None:
        issues.append(f"unmatched start {opened[1]} at byte {opened[0]}")
    if issues:
        raise InstallError("managed sentinel marker errors: " + "; ".join(issues))
    return found


_LOCK_POLL_SECONDS = 0.05
_LOCK_MAX_ATTEMPTS = 40  # ~2s of contention before giving up.


def _acquire_os_lock(handle) -> bool:
    """Try once to take the OS advisory lock. True on success.

    The OS releases the lock when the process exits, crash or not — no PID to
    record and no stale-lock state to detect or reclaim."""
    if os.name == "nt":
        import msvcrt

        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _release_os_lock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        return
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextlib.contextmanager
def _target_lock(target: pathlib.Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    # Lock the real file a symlink points at, not the symlink path itself —
    # two different aliases of the same file (a symlink and its referent, or
    # two symlinks to the same referent) must derive the same lock path, or
    # each takes its own lock and both critical sections run at once.
    real = target.resolve() if target.is_symlink() else target
    real.parent.mkdir(parents=True, exist_ok=True)
    lock = real.with_name(f".{real.name}.afk.lock")
    # The lock file itself is never deleted: only its OS lock state matters,
    # never its content or its existence. An empty or garbage-content lock
    # file (e.g. left by a crash, or by an older scheme) is never read or
    # interpreted — acquiring the OS lock on it is all that is checked.
    handle = open(lock, "a+b")
    try:
        if os.name == "nt" and os.fstat(handle.fileno()).st_size == 0:
            # msvcrt.locking needs at least 1 byte to lock a region against;
            # the byte's value is never read back.
            handle.write(b"\0")
            handle.flush()
        acquired = False
        for _ in range(_LOCK_MAX_ATTEMPTS):
            if _acquire_os_lock(handle):
                acquired = True
                break
            time.sleep(_LOCK_POLL_SECONDS)
        if not acquired:
            raise InstallError(f"target is locked: {target}")
        try:
            yield
        finally:
            _release_os_lock(handle)
    finally:
        handle.close()


def _atomic_write_locked(target: pathlib.Path, expected: bytes, updated: bytes) -> None:
    current = target.read_bytes() if target.exists() else b""
    if current != expected:
        raise InstallError(f"target changed during update: {target}")
    # Write through a symlink to the real file it targets; the symlink entry
    # itself is never replaced or touched.
    write_target = target.resolve() if target.is_symlink() else target
    descriptor, temporary_name = tempfile.mkstemp(
        dir=write_target.parent,
        prefix=f".{write_target.name}.",
        suffix=".tmp",
    )
    temporary = pathlib.Path(temporary_name)
    try:
        if target.exists():
            mode = stat.S_IMODE(target.stat().st_mode)
        else:
            current_umask = os.umask(0)
            os.umask(current_umask)
            mode = 0o666 & ~current_umask
        os.chmod(temporary, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        current = target.read_bytes() if target.exists() else b""
        if current != expected:
            raise InstallError(f"target changed during update: {target}")
        os.replace(temporary, write_target)
        if hasattr(os, "O_DIRECTORY"):
            directory = os.open(write_target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)


def write_if_unchanged(
    target_path: pathlib.Path | str,
    expected: bytes,
    updated: bytes,
) -> None:
    """Atomically replace one target when its bytes still match the snapshot."""
    target = pathlib.Path(target_path)
    with _target_lock(target):
        _atomic_write_locked(target, expected, updated)


def install(
    source_path: pathlib.Path | str,
    target_path: pathlib.Path | str,
    *,
    sentinel: str = "behaviors",
    remove_sentinels: Sequence[str] = LEGACY_SENTINELS,
) -> Result:
    source = pathlib.Path(source_path)
    target_path = pathlib.Path(target_path)
    with _target_lock(target_path):
        target = target_path.read_bytes() if target_path.exists() else b""
        eol = _target_eol(target)
        replacement = _source_block(source, sentinel).replace(b"\n", eol)
        matches = _matches(target, (sentinel, *remove_sentinels))
        had_unified = any(name == sentinel for _, _, name in matches)
        if matches:
            chunks: list[bytes] = []
            cursor = 0
            inserted = False
            for start, end, _name in matches:
                chunks.append(target[cursor:start])
                if not inserted:
                    chunks.append(replacement)
                    inserted = True
                cursor = end
            chunks.append(target[cursor:])
            updated = b"".join(chunks)
        else:
            separator = b"" if not target or target.endswith((b"\n", b"\r")) else eol
            updated = target + separator + replacement + eol
        changed = updated != target
        if changed:
            _atomic_write_locked(target_path, target, updated)
    if not changed:
        action = "already-current"
    elif had_unified:
        action = "refreshed"
    else:
        action = "installed"
    return Result(action, max(0, len(matches) - 1), changed)


def teardown(
    target_path: pathlib.Path | str,
    *,
    sentinel: str = "behaviors",
    remove_sentinels: Sequence[str] = LEGACY_SENTINELS,
) -> Result:
    target_path = pathlib.Path(target_path)
    with _target_lock(target_path):
        target = target_path.read_bytes() if target_path.exists() else b""
        matches = _matches(target, (sentinel, *remove_sentinels))
        chunks: list[bytes] = []
        cursor = 0
        for start, end, _name in matches:
            chunks.append(target[cursor:start])
            cursor = end
        chunks.append(target[cursor:])
        updated = b"".join(chunks)
        changed = updated != target
        if changed:
            _atomic_write_locked(target_path, target, updated)
    return Result("removed" if changed else "absent", len(matches), changed)


def _legacy(argv: Sequence[str]) -> int:
    if len(argv) not in (2, 3):
        return 2
    source, target = pathlib.Path(argv[0]), pathlib.Path(argv[1])
    name = argv[2] if len(argv) == 3 else "plain-language"
    replacement = _source_block(source, name)
    with _target_lock(target):
        data = target.read_bytes()
        pattern = sentinel_pattern(name)
        if not pattern.search(data):
            return 1
        replacement = replacement.replace(b"\n", _target_eol(data))
        updated = pattern.sub(lambda _match: replacement, data, count=1)
        if updated != data:
            _atomic_write_locked(target, data, updated)
            print(f"refreshed {name} block in {target}")
        else:
            print(f"{name} block in {target} is already current")
    return 0


def _options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sentinel", default="behaviors")
    parser.add_argument("--remove-sentinel", action="append", dest="remove_sentinels")


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    commands = {"install", "teardown", "-h", "--help"}
    if args_list and args_list[0] not in commands:
        try:
            return _legacy(args_list)
        except (OSError, InstallError) as exc:
            print(f"install_block: {exc}", file=sys.stderr)
            return 2

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("source", type=pathlib.Path)
    install_parser.add_argument("target", type=pathlib.Path)
    _options(install_parser)
    remove_parser = subparsers.add_parser("teardown")
    remove_parser.add_argument("target", type=pathlib.Path)
    _options(remove_parser)
    args = parser.parse_args(args_list)
    remove = tuple(args.remove_sentinels or LEGACY_SENTINELS)
    try:
        if args.command == "teardown":
            result = teardown(args.target, sentinel=args.sentinel, remove_sentinels=remove)
        else:
            result = install(
                args.source,
                args.target,
                sentinel=args.sentinel,
                remove_sentinels=remove,
            )
    except (OSError, InstallError) as exc:
        print(f"install_block: {exc}", file=sys.stderr)
        return 2
    print(f"{result.action}: {args.target}; removed={result.removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
