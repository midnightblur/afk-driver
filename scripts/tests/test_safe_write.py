"""Safe writer: one locked read-modify-write that never loses another write."""
from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "safe_write.py"
INSTALLER = ROOT / "skills" / "afk" / "setup" / "scripts" / "install_block.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sw = load(SCRIPT, "afk_safe_write_under_test")


def temps(folder: Path) -> list[Path]:
    return list(folder.glob(".*.tmp"))


def test_the_call_hands_the_current_text_and_writes_back_the_returned_text(tmp_path):
    target = tmp_path / "list.txt"
    target.write_bytes(b"one\r\n")
    seen = []

    def transform(text):
        seen.append(text)
        return text + "two\r\n"

    assert sw.update_locked(target, transform) is True
    assert seen == ["one\r\n"]
    assert target.read_bytes() == b"one\r\ntwo\r\n"
    assert temps(tmp_path) == []


def test_a_missing_file_reads_as_empty_text_and_is_created(tmp_path):
    target = tmp_path / "new" / "file.txt"
    assert sw.update_locked(target, lambda text: text + "first\n") is True
    assert target.read_bytes() == b"first\n"


def test_unchanged_text_writes_nothing(tmp_path):
    target = tmp_path / "file.txt"
    target.write_bytes(b"same\n")
    os.utime(target, (1_000_000, 1_000_000))
    assert sw.update_locked(target, lambda text: text) is False
    assert target.stat().st_mtime == 1_000_000


def test_any_bytes_round_trip_through_the_text(tmp_path):
    target = tmp_path / "file.bin"
    original = b"\xff\xfe latin-1 \xe9 and utf-8 \xc3\xa9\n"
    target.write_bytes(original)
    sw.update_locked(target, lambda text: text + "added\n")
    assert target.read_bytes() == original + b"added\n"


def test_a_transform_error_reaches_the_caller_and_changes_nothing(tmp_path):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")

    def transform(_text):
        raise KeyError("caller refused")

    with pytest.raises(KeyError, match="caller refused"):
        sw.update_locked(target, transform)
    assert target.read_bytes() == b"before"
    assert temps(tmp_path) == []


def test_a_second_process_write_between_hand_out_and_write_back_is_kept(tmp_path):
    target = tmp_path / "settings.yaml"
    target.write_bytes(b"first writer\n")
    other = [sys.executable, "-c", "import sys, pathlib; pathlib.Path(sys.argv[1]).write_bytes(b'second writer\\n')", str(target)]

    def transform(text):
        subprocess.run(other, check=True)
        return text + "lost?\n"

    with pytest.raises(sw.SafeWriteError, match="changed during update") as caught:
        sw.update_locked(target, transform)
    assert caught.value.path == target
    assert str(target) in str(caught.value)
    assert target.read_bytes() == b"second writer\n"
    assert temps(tmp_path) == []


def test_a_lock_held_past_2000_ms_ends_the_wait_naming_the_file(tmp_path):
    assert sw.LOCK_WAIT_SECONDS == 2.0
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    with sw._file_lock(target):
        started = time.monotonic()
        with pytest.raises(sw.SafeWriteError, match="is locked") as caught:
            sw.update_locked(target, lambda text: "after")
        waited = time.monotonic() - started
    assert 2.0 <= waited < 5.0
    assert str(target) in str(caught.value)
    assert target.read_bytes() == b"before"
    assert temps(tmp_path) == []


def test_the_lock_file_stays_and_the_file_keeps_its_mode(tmp_path):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    target.chmod(0o640)
    mode = target.stat().st_mode & 0o777
    sw.update_locked(target, lambda text: "after")
    assert target.stat().st_mode & 0o777 == mode
    assert (tmp_path / ".file.txt.afk.lock").exists()


@pytest.mark.skipif(os.name == "nt", reason="owner-only access is a Linux and macOS file mode")
def test_owner_only_leaves_the_file_to_its_owner_alone(tmp_path):
    existing = tmp_path / "secrets.json"
    existing.write_bytes(b"{}")
    existing.chmod(0o644)
    sw.update_locked(existing, lambda text: '{"k": 1}', owner_only=True)
    assert existing.stat().st_mode & 0o777 == 0o600
    created = tmp_path / "created.json"
    sw.update_locked(created, lambda text: "{}", owner_only=True)
    assert created.stat().st_mode & 0o777 == 0o600
    unchanged = tmp_path / "unchanged.json"
    unchanged.write_bytes(b"{}")
    unchanged.chmod(0o644)
    assert sw.update_locked(unchanged, lambda text: text, owner_only=True) is False
    assert unchanged.stat().st_mode & 0o777 == 0o600


def busy_replace(monkeypatch, failures: int):
    calls, sleeps = [], []
    real_replace = os.replace

    def replace(source, destination):
        calls.append(time.monotonic())
        if len(calls) <= failures:
            raise PermissionError(13, "file in use", str(destination))
        real_replace(source, destination)

    monkeypatch.setattr(sw, "_RETRY_BUSY_SWAP", True)
    monkeypatch.setattr(sw.os, "replace", replace)
    monkeypatch.setattr(sw.time, "sleep", lambda seconds: sleeps.append(seconds))
    return calls, sleeps


def test_a_busy_swap_retries_10_times_at_50_ms_then_fails_naming_the_file(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    calls, sleeps = busy_replace(monkeypatch, failures=100)
    with pytest.raises(sw.SafeWriteError, match="file swap stayed busy") as caught:
        sw.update_locked(target, lambda text: "after")
    assert len(calls) == 11
    assert sleeps == [0.05] * 10
    assert str(target) in str(caught.value)
    assert isinstance(caught.value.__cause__, PermissionError)
    assert target.read_bytes() == b"before"
    assert temps(tmp_path) == []


def test_a_busy_swap_that_clears_within_the_retries_writes(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    calls, _sleeps = busy_replace(monkeypatch, failures=3)
    assert sw.update_locked(target, lambda text: "after") is True
    assert len(calls) == 4
    assert target.read_bytes() == b"after"


def test_a_busy_swap_refuses_when_the_file_changed_during_a_retry(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    monkeypatch.setattr(sw, "_RETRY_BUSY_SWAP", True)

    def replace(_source, destination):
        Path(destination).write_bytes(b"other writer")
        raise PermissionError(13, "file in use", str(destination))

    monkeypatch.setattr(sw.os, "replace", replace)
    monkeypatch.setattr(sw.time, "sleep", lambda _seconds: None)
    with pytest.raises(sw.SafeWriteError, match="changed during update"):
        sw.update_locked(target, lambda text: "after")
    assert target.read_bytes() == b"other writer"
    assert temps(tmp_path) == []


def test_a_permission_error_off_windows_is_not_retried(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    calls, _sleeps = busy_replace(monkeypatch, failures=100)
    monkeypatch.setattr(sw, "_RETRY_BUSY_SWAP", False)
    with pytest.raises(PermissionError):
        sw.update_locked(target, lambda text: "after")
    assert len(calls) == 1
    assert target.read_bytes() == b"before"


@pytest.mark.skipif(os.name != "nt", reason="an open handle blocks a file swap only on Windows")
def test_a_real_busy_swap_on_windows_retries_until_the_handle_closes(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    handle = open(target, "rb")
    attempts = []
    real_replace = os.replace

    def replace(source, destination):
        attempts.append(destination)
        try:
            real_replace(source, destination)
        except PermissionError:
            handle.close()
            raise

    monkeypatch.setattr(sw.os, "replace", replace)
    try:
        assert sw.update_locked(target, lambda text: "after") is True
    finally:
        handle.close()
    assert len(attempts) == 2
    assert target.read_bytes() == b"after"


def test_a_change_during_the_temp_file_write_is_refused(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    real_fsync = os.fsync

    def fsync(descriptor):
        real_fsync(descriptor)
        if not target.read_bytes().startswith(b"other"):
            target.write_bytes(b"other writer")

    monkeypatch.setattr(sw.os, "fsync", fsync)
    with pytest.raises(sw.SafeWriteError, match="changed during update"):
        sw.update_locked(target, lambda text: "after")
    assert target.read_bytes() == b"other writer"
    assert temps(tmp_path) == []


def track_descriptors(monkeypatch):
    events = []
    real_open, real_close = os.open, os.close

    def open_(path, *args, **kwargs):
        descriptor = real_open(path, *args, **kwargs)
        events.append(("open", str(path), descriptor))
        return descriptor

    def close(descriptor):
        events.append(("close", "", descriptor))
        real_close(descriptor)

    monkeypatch.setattr(sw.os, "open", open_)
    monkeypatch.setattr(sw.os, "close", close)
    return events


def temp_descriptor_closes(events) -> int:
    """Count os.close calls on the temp file's descriptor before its number is reused."""
    start = next(i for i, (kind, path, _) in enumerate(events) if kind == "open" and path.endswith(".tmp"))
    descriptor, closes = events[start][2], 0
    for kind, _path, number in events[start + 1:]:
        if number != descriptor:
            continue
        if kind == "open":
            break
        closes += 1
    return closes


def test_the_temp_file_descriptor_is_closed_exactly_once(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    events = track_descriptors(monkeypatch)
    assert sw.update_locked(target, lambda text: "after") is True
    temp_descriptor = next(number for kind, path, number in events if kind == "open" and path.endswith(".tmp"))
    assert temp_descriptor_closes(events) == 0
    with pytest.raises(OSError):
        os.fstat(temp_descriptor)


def test_the_temp_file_descriptor_is_closed_when_the_handle_never_opens(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    events = track_descriptors(monkeypatch)

    def fdopen(*_args, **_kwargs):
        raise OSError("no handle")

    monkeypatch.setattr(sw.os, "fdopen", fdopen)
    with pytest.raises(OSError, match="no handle"):
        sw.update_locked(target, lambda text: "after")
    assert temp_descriptor_closes(events) == 1
    assert target.read_bytes() == b"before"
    assert temps(tmp_path) == []


def forbid_umask(monkeypatch):
    def umask(_mask):
        raise AssertionError("the process umask must not change")

    monkeypatch.setattr(sw.os, "umask", umask)


def test_a_new_file_is_created_without_touching_the_umask(tmp_path, monkeypatch):
    forbid_umask(monkeypatch)
    target = tmp_path / "created.txt"
    assert sw.update_locked(target, lambda text: "new") is True
    assert target.read_bytes() == b"new"


@pytest.mark.skipif(os.name == "nt", reason="the umask shapes file modes only on Linux and macOS")
def test_a_new_file_takes_the_default_mode_under_the_process_umask(tmp_path, monkeypatch):
    previous = os.umask(0o002)
    try:
        forbid_umask(monkeypatch)
        target = tmp_path / "created.txt"
        assert sw.update_locked(target, lambda text: "new") is True
    finally:
        monkeypatch.undo()
        os.umask(previous)
    assert target.stat().st_mode & 0o777 == 0o664


def collide(monkeypatch, names):
    tokens = iter(names)
    monkeypatch.setattr(sw.secrets, "token_hex", lambda _size: next(tokens))


def test_a_taken_temp_file_name_is_skipped_and_left_alone(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    taken = tmp_path / ".file.txt.aaaaaaaaaaaa.tmp"
    taken.write_bytes(b"someone else's")
    collide(monkeypatch, ["aaaaaaaaaaaa", "bbbbbbbbbbbb"])
    assert sw.update_locked(target, lambda text: "after") is True
    assert target.read_bytes() == b"after"
    assert taken.read_bytes() == b"someone else's"
    assert temps(tmp_path) == [taken]


def test_no_free_temp_file_name_refuses_naming_the_file(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    taken = tmp_path / ".file.txt.aaaaaaaaaaaa.tmp"
    taken.write_bytes(b"someone else's")
    collide(monkeypatch, ["aaaaaaaaaaaa"] * sw._TEMP_NAME_ATTEMPTS)
    with pytest.raises(sw.SafeWriteError, match="no free temp file name") as caught:
        sw.update_locked(target, lambda text: "after")
    assert caught.value.path == target
    assert target.read_bytes() == b"before"
    assert temps(tmp_path) == [taken]


def test_no_free_temp_file_name_names_the_symlink_the_caller_passed(tmp_path, monkeypatch):
    real = tmp_path / "real.txt"
    real.write_bytes(b"before")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("this account cannot create symlinks")
    collide(monkeypatch, ["aaaaaaaaaaaa"] * sw._TEMP_NAME_ATTEMPTS)
    (tmp_path / ".real.txt.aaaaaaaaaaaa.tmp").write_bytes(b"taken")
    with pytest.raises(sw.SafeWriteError, match="no free temp file name") as caught:
        sw.update_locked(link, lambda text: "after")
    assert caught.value.path == link


def test_a_failed_temp_file_delete_keeps_the_original_refusal(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    busy_replace(monkeypatch, failures=100)
    real_unlink = os.unlink

    def unlink(path, *args, **kwargs):
        if str(path).endswith(".tmp"):
            raise PermissionError(32, "file in use by another process", str(path))
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(sw.os, "unlink", unlink)
    with pytest.raises(sw.SafeWriteError, match="file swap stayed busy"):
        sw.update_locked(target, lambda text: "after")
    monkeypatch.undo()
    assert target.read_bytes() == b"before"


@pytest.mark.skipif(os.name != "nt", reason="a read-only file blocks its own replacement only on Windows")
def test_a_read_only_file_is_refused_at_once_and_the_temp_file_deleted(tmp_path, monkeypatch):
    target = tmp_path / "file.txt"
    target.write_bytes(b"before")
    target.chmod(stat.S_IREAD)
    sleeps = []
    monkeypatch.setattr(sw.time, "sleep", lambda seconds: sleeps.append(seconds))
    try:
        with pytest.raises(sw.SafeWriteError, match="is read-only") as caught:
            sw.update_locked(target, lambda text: "after")
        assert caught.value.path == target
        assert sleeps == []
        assert target.read_bytes() == b"before"
        assert temps(tmp_path) == []
    finally:
        target.chmod(stat.S_IREAD | stat.S_IWRITE)
        for leftover in temps(tmp_path):
            leftover.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_the_installer_reports_a_safe_writer_refusal_as_its_own_error(tmp_path):
    installer = load(INSTALLER, "afk_install_block_under_test")
    target = tmp_path / "CLAUDE.md"
    target.write_bytes(b"before")
    with installer.safe_write._file_lock(target):
        with pytest.raises(installer.InstallError, match="target is locked") as caught:
            installer.write_if_unchanged(target, b"before", b"after")
    assert isinstance(caught.value.__cause__, installer.safe_write.SafeWriteError)
    assert target.read_bytes() == b"before"
