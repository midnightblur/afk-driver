import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "skills" / "afk" / "setup" / "scripts" / "install_block.py"


def load_module():
    spec = importlib.util.spec_from_file_location("install_block", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def block(name, text="body", eol="\n"):
    return eol.join(
        [f"<!-- afk:{name}:start -->", text, f"<!-- afk:{name}:end -->"]
    ).encode()


def test_install_migration_covers_h7_h8_h10_and_removes_duplicate_unified_blocks(tmp_path):
    install_block = load_module()
    source = tmp_path / "source.md"
    source.write_bytes(block("behaviors", "new\ncontent"))
    target = tmp_path / "target.md"
    target.write_bytes(
        b"before\r\n"
        + block("plain-language", "h7", "\r\n")
        + b"\r\nmiddle-a\r\n"
        + block("behaviors", "stale-one", "\r\n")
        + b"\r\nmiddle-b\r\n"
        + block("lavish-sessions", "h8", "\r\n")
        + b"\r\nmiddle-c\r\n"
        + block("investigation", "h10", "\r\n")
        + b"\r\nmiddle-d\r\n"
        + block("behaviors", "stale-two", "\r\n")
        + b"\r\nafter\r\n"
    )

    result = install_block.install(source, target)

    installed = target.read_bytes()
    assert result.action == "refreshed"
    assert installed.count(b"<!-- afk:behaviors:start -->") == 1
    assert b"new\r\ncontent" in installed
    assert b"plain-language:start" not in installed
    assert b"lavish-sessions:start" not in installed
    assert b"investigation:start" not in installed
    for outside in (b"before\r\n", b"middle-a\r\n", b"middle-b\r\n", b"middle-c\r\n", b"middle-d\r\n", b"after\r\n"):
        assert outside in installed
    assert b"\n" not in installed.replace(b"\r\n", b"")


def test_install_appends_then_refreshes_without_changing_outside_bytes(tmp_path):
    install_block = load_module()
    source = tmp_path / "source.md"
    target = tmp_path / "target.md"
    source.write_bytes(block("behaviors", "first"))
    original = b"human bytes without final newline"
    target.write_bytes(original)

    install_block.install(source, target)
    assert target.read_bytes().startswith(original + b"\n")

    source.write_bytes(block("behaviors", "second"))
    result = install_block.install(source, target)
    assert result.action == "refreshed"
    assert target.read_bytes().startswith(original + b"\n")
    assert b"first" not in target.read_bytes()
    assert b"second" in target.read_bytes()


def test_teardown_removes_every_named_block_and_preserves_outside_bytes(tmp_path):
    install_block = load_module()
    target = tmp_path / "target.md"
    target.write_bytes(
        b"A\n"
        + block("behaviors")
        + b"\nB\n"
        + block("plain-language")
        + b"\nC\n"
        + block("lavish-sessions")
        + b"\nD\n"
        + block("investigation")
        + b"\nE"
    )

    result = install_block.teardown(target)

    assert result.removed == 4
    assert target.read_bytes() == b"A\n\nB\n\nC\n\nD\n\nE"


@pytest.mark.parametrize(
    "content",
    [
        b"<!-- afk:behaviors:start -->\nbody\n",
        b"body\n<!-- afk:behaviors:end -->\n",
        (
            b"<!-- afk:behaviors:start -->\n"
            b"<!-- afk:plain-language:start -->\n"
            b"<!-- afk:plain-language:end -->\n"
            b"<!-- afk:behaviors:end -->\n"
        ),
        (
            b"<!-- afk:behaviors:start -->\n"
            b"<!-- afk:plain-language:start -->\n"
            b"<!-- afk:behaviors:end -->\n"
            b"<!-- afk:plain-language:end -->\n"
        ),
    ],
)
def test_install_and_teardown_reject_unbalanced_nested_or_crossed_markers(tmp_path, content):
    install_block = load_module()
    source = tmp_path / "source.md"
    source.write_bytes(block("behaviors", "new"))
    target = tmp_path / "target.md"
    target.write_bytes(content)

    with pytest.raises(install_block.InstallError, match="managed sentinel marker"):
        install_block.install(source, target)
    with pytest.raises(install_block.InstallError, match="managed sentinel marker"):
        install_block.teardown(target)
    assert target.read_bytes() == content


def test_install_reuses_legacy_marker_as_consent(tmp_path):
    install_block = load_module()
    source = tmp_path / "source.md"
    source.write_bytes(block("behaviors", "new"))
    target = tmp_path / "target.md"
    target.write_bytes(block("plain-language", "old"))

    result = install_block.install(source, target)

    assert result.action == "installed"
    assert b"afk:behaviors:start" in target.read_bytes()
    assert b"afk:plain-language:start" not in target.read_bytes()


def test_atomic_write_preserves_permissions_and_refuses_concurrent_edit(tmp_path):
    install_block = load_module()
    target = tmp_path / "target.md"
    target.write_bytes(b"before")
    target.chmod(0o640)
    original = target.read_bytes()
    original_mode = target.stat().st_mode & 0o777

    install_block.write_if_unchanged(target, original, b"after")

    assert target.read_bytes() == b"after"
    assert target.stat().st_mode & 0o777 == original_mode

    expected = target.read_bytes()
    target.write_bytes(b"human edit")
    with pytest.raises(install_block.InstallError, match="changed during update"):
        install_block.write_if_unchanged(target, expected, b"agent edit")
    assert target.read_bytes() == b"human edit"


def test_atomic_write_keeps_target_on_interrupted_replace(tmp_path, monkeypatch):
    install_block = load_module()
    target = tmp_path / "target.md"
    target.write_bytes(b"before")

    def fail_replace(_source, _target):
        raise OSError("interrupted")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="interrupted"):
        install_block.write_if_unchanged(target, b"before", b"after")

    assert target.read_bytes() == b"before"
    assert list(tmp_path.glob(".target.md.*.tmp")) == []


def test_atomic_write_updates_through_a_symlink_without_replacing_it(tmp_path):
    """A2-006: a user instruction file that is a symlink (e.g. into a dotfiles
    checkout) must keep pointing at its real file after an install — the real
    file's content changes, the symlink entry itself is never replaced."""
    install_block = load_module()
    real = tmp_path / "real.md"
    real.write_bytes(b"before")
    link = tmp_path / "target.md"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlinks are not permitted in this environment")

    install_block.write_if_unchanged(link, b"before", b"after")

    assert link.is_symlink()
    assert link.resolve() == real.resolve()
    assert real.read_bytes() == b"after"
    assert link.read_bytes() == b"after"


def test_lock_ignores_a_leftover_lock_file_regardless_of_content(tmp_path):
    """A3-004: only the OS lock state on the lock file is ever checked — its
    content is never read or trusted. An empty lock (a crash before any write
    under the old PID scheme) or a garbage/partial one (a crash mid-write, or
    a file from an older scheme) must never block a new install."""
    install_block = load_module()
    target = tmp_path / "target.md"
    target.write_bytes(b"before")
    lock = target.with_name(f".{target.name}.afk.lock")

    lock.write_bytes(b"")
    install_block.write_if_unchanged(target, b"before", b"after (empty lock)")
    assert target.read_bytes() == b"after (empty lock)"

    lock.write_bytes(b"not a pid, garbage \x00\x01 content")
    install_block.write_if_unchanged(target, b"after (empty lock)", b"after (garbage lock)")
    assert target.read_bytes() == b"after (garbage lock)"


_HOLDER_WORKER = '''
import importlib.util
import pathlib
import sys
import time

module_path, target_path, signal_dir = sys.argv[1:4]
spec = importlib.util.spec_from_file_location("install_block", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

signal_dir = pathlib.Path(signal_dir)
target = pathlib.Path(target_path)
with module._target_lock(target):
    (signal_dir / "holder-locked").write_text("1", encoding="utf-8")
    deadline = time.monotonic() + 10
    while not (signal_dir / "release").exists():
        if time.monotonic() > deadline:
            sys.exit(1)
        time.sleep(0.01)
'''

_CONTENDER_WORKER = '''
import importlib.util
import pathlib
import sys
import time

module_path, target_path, signal_dir = sys.argv[1:4]
spec = importlib.util.spec_from_file_location("install_block", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

signal_dir = pathlib.Path(signal_dir)
deadline = time.monotonic() + 10
while not (signal_dir / "holder-locked").exists():
    if time.monotonic() > deadline:
        sys.exit(1)
    time.sleep(0.01)

target = pathlib.Path(target_path)
(signal_dir / "contender-ready").write_text("1", encoding="utf-8")
with module._target_lock(target):
    (signal_dir / "contender-entered").write_text("1", encoding="utf-8")
'''


def _run_holder_contender(tmp_path, holder_target, contender_target):
    """Prove real cross-process mutual exclusion by protocol, not by timing
    luck. A holder subprocess acquires `_target_lock` on `holder_target` and
    blocks — not on a fixed sleep, but on an explicit `release` marker file
    the parent controls — so the parent can positively confirm the holder is
    *actually holding* (via its own `holder-locked` marker) before starting
    the contender. The parent then observes a real window with the holder
    still holding and asserts the contender has NOT yet entered its critical
    section; only then does it release the holder and confirm the contender
    completes afterward. A timing-only race (fixed sleeps, compared
    enter/exit stamps) cannot distinguish real exclusion from the scheduler
    happening to run the two sequentially — this protocol can, because the
    contender's non-entry is checked while the holder is provably still
    inside the lock, not merely likely to be.

    `_target_lock` itself polls for up to ~2s (`_LOCK_MAX_ATTEMPTS *
    _LOCK_POLL_SECONDS` in install_block.py) before giving up, so the
    contender's single `with module._target_lock(...)` call blocks-by-retry
    on its own; the parent's observation window only needs to stay well
    inside that budget.

    `procs` starts empty before the `try` so that a `Popen` failure on the
    *second* process still leaves the first, already-started process
    reachable by `finally` — a list comprehension built entirely before
    `try` would strand it."""
    signal_dir = tmp_path / "signal"
    signal_dir.mkdir()
    holder_script = tmp_path / "holder.py"
    holder_script.write_text(_HOLDER_WORKER, encoding="utf-8")
    contender_script = tmp_path / "contender.py"
    contender_script.write_text(_CONTENDER_WORKER, encoding="utf-8")

    procs = []
    try:
        holder_proc = subprocess.Popen(
            [sys.executable, str(holder_script), str(MODULE_PATH), str(holder_target), str(signal_dir)]
        )
        procs.append(holder_proc)

        deadline = time.monotonic() + 10
        while not (signal_dir / "holder-locked").exists():
            assert time.monotonic() < deadline, "holder never signaled it acquired the lock"
            time.sleep(0.01)

        contender_proc = subprocess.Popen(
            [sys.executable, str(contender_script), str(MODULE_PATH), str(contender_target), str(signal_dir)]
        )
        procs.append(contender_proc)

        # Interpreter start-up and module exec cost time before the
        # contender even reaches its lock request — sleeping a fixed window
        # right after `Popen` could elapse entirely before the contender has
        # tried the lock at all, making the non-entry check pass on a
        # delayed contender rather than on real exclusion. Wait for the
        # contender's own `contender-ready` marker, written immediately
        # before its lock request, so the observation window only starts
        # once the contender is genuinely about to attempt the lock.
        deadline = time.monotonic() + 10
        while not (signal_dir / "contender-ready").exists():
            assert time.monotonic() < deadline, "contender never signaled it was ready to request the lock"
            time.sleep(0.01)

        time.sleep(0.3)
        assert not (signal_dir / "contender-entered").exists(), (
            "contender entered its critical section while the holder still held the lock"
        )

        (signal_dir / "release").write_text("1", encoding="utf-8")
        assert holder_proc.wait(timeout=15) == 0
        assert contender_proc.wait(timeout=15) == 0
        assert (signal_dir / "contender-entered").exists(), (
            "contender never entered its critical section after the holder released"
        )
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


def test_lock_serializes_a_symlink_and_its_real_file_through_the_same_lock(tmp_path):
    """A symlink and the real file it points at must derive the same lock
    path — locking through the alias must exclude locking through the
    referent, or two writers using different aliases of the same file can
    both enter the critical section at once (a prior scheme derived the lock
    name from whichever path was passed in, giving `link.md` and `real.md`
    two different lock files for one real target). Proven with a holder
    (locking via the symlink) and a contender (locking via the real file)
    under the holder/contender protocol."""
    real = tmp_path / "real.md"
    real.write_bytes(b"before")
    link = tmp_path / "link.md"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlinks are not permitted in this environment")

    _run_holder_contender(tmp_path, link, real)
    assert (tmp_path / ".real.md.afk.lock").exists()
    assert not (tmp_path / ".link.md.afk.lock").exists()


def test_lock_serializes_two_separate_processes_never_letting_two_enter_together(tmp_path):
    """An OS advisory lock must serialize across process boundaries, not
    merely across threads sharing one interpreter's GIL — a thread-only test
    cannot tell the two apart. A holder and a contender race for the same
    lock file under the holder/contender protocol, which proves the
    contender is blocked *while the holder is provably still holding*
    rather than inferring exclusion from timing alone."""
    target = tmp_path / "target.md"
    target.write_bytes(b"before")

    _run_holder_contender(tmp_path, target, target)
