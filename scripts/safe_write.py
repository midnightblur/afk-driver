#!/usr/bin/env afk-python
"""Safe writer: one locked read-modify-write of one file. Standard library only.

    update_locked(path, transform, *, owner_only=False) -> bool

The call takes the file's lock (`.<name>.afk.lock` beside the real file), reads
the file, calls `transform(current_text)`, and writes back the text it returns
through a temp file and one replace. A missing file reads as "". It refuses
with `SafeWriteError` naming the file when the lock stays held past
`LOCK_WAIT_SECONDS`, when the file changed between the read and the write, or
when a busy replace on Windows outlasts `SWAP_RETRIES` retries. A refusal or
failure deletes the temp file and leaves the file unchanged. The written file
keeps its previous mode; `owner_only=True` sets read and write for its owner
alone, also on an unchanged file. Returns False and writes nothing when the
text did not change.
Text is UTF-8 with `surrogateescape`, so any bytes round-trip unchanged.
"""
from __future__ import annotations

import contextlib
import os
import pathlib
import stat
import tempfile
import time
from typing import Callable, Iterator

LOCK_WAIT_SECONDS = 2.0
SWAP_RETRIES = 10
SWAP_RETRY_SECONDS = 0.05
OWNER_ONLY_MODE = 0o600
_LOCK_POLL_SECONDS = 0.05
_RETRY_BUSY_SWAP = os.name == "nt"
ENCODING = "utf-8"
ERRORS = "surrogateescape"


class SafeWriteError(Exception):
    """The safe writer refused a write; `reason` says why, `path` names the file."""

    def __init__(self, reason: str, path: pathlib.Path | str) -> None:
        self.reason = reason
        self.path = pathlib.Path(path)
        super().__init__(f"{reason}: {path}")


def update_locked(
    path: pathlib.Path | str,
    transform: Callable[[str], str],
    *,
    owner_only: bool = False,
) -> bool:
    """Lock `path`, hand `transform` its text, write back the text it returns."""
    target = pathlib.Path(path)
    with _file_lock(target):
        before = _read(target)
        after = transform(before.decode(ENCODING, ERRORS))
        if not isinstance(after, str):
            raise TypeError(f"transform must return str, got {type(after).__name__}")
        updated = after.encode(ENCODING, ERRORS)
        if updated == before:
            if owner_only and target.exists():
                os.chmod(_real(target), OWNER_ONLY_MODE)
            return False
        _replace_if_unchanged(target, before, updated, owner_only)
    return True


def _read(target: pathlib.Path) -> bytes:
    return target.read_bytes() if target.exists() else b""


def _require_unchanged(target: pathlib.Path, expected: bytes) -> None:
    if _read(target) != expected:
        raise SafeWriteError("changed during update", target)


def _real(target: pathlib.Path) -> pathlib.Path:
    # Lock and write the file a symlink points at; the symlink entry is never replaced.
    return target.resolve() if target.is_symlink() else target


def _acquire_os_lock(handle) -> bool:
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
def _file_lock(target: pathlib.Path) -> Iterator[None]:
    """Hold the OS lock on the file's lock file; the OS drops it when the process ends."""
    target.parent.mkdir(parents=True, exist_ok=True)
    real = _real(target)
    real.parent.mkdir(parents=True, exist_ok=True)
    # Never delete the lock file: only its OS lock state counts, never its content.
    handle = open(real.with_name(f".{real.name}.afk.lock"), "a+b")
    try:
        if os.name == "nt" and os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"\0")  # msvcrt.locking needs one byte to lock.
            handle.flush()
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while not _acquire_os_lock(handle):
            if time.monotonic() >= deadline:
                raise SafeWriteError("is locked", target)
            time.sleep(_LOCK_POLL_SECONDS)
        try:
            yield
        finally:
            _release_os_lock(handle)
    finally:
        handle.close()


def _mode(target: pathlib.Path, owner_only: bool) -> int:
    if owner_only:
        return OWNER_ONLY_MODE
    if target.exists():
        return stat.S_IMODE(target.stat().st_mode)
    current_umask = os.umask(0)
    os.umask(current_umask)
    return 0o666 & ~current_umask


def _swap(temporary: pathlib.Path, write_target: pathlib.Path, target: pathlib.Path, expected: bytes) -> None:
    for attempt in range(SWAP_RETRIES + 1):
        try:
            os.replace(temporary, write_target)
            return
        except PermissionError as exc:
            if not _RETRY_BUSY_SWAP:
                raise
            if attempt == SWAP_RETRIES:
                raise SafeWriteError("file swap stayed busy", target) from exc
        time.sleep(SWAP_RETRY_SECONDS)
        _require_unchanged(target, expected)


def _replace_if_unchanged(target: pathlib.Path, expected: bytes, updated: bytes, owner_only: bool) -> None:
    _require_unchanged(target, expected)
    write_target = _real(target)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=write_target.parent,
        prefix=f".{write_target.name}.",
        suffix=".tmp",
    )
    temporary = pathlib.Path(temporary_name)
    try:
        os.chmod(temporary, _mode(target, owner_only))
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        _require_unchanged(target, expected)
        _swap(temporary, write_target, target, expected)
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
