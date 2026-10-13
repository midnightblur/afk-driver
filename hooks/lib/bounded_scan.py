"""Bounded repository scanner: the one route for a repository-wide content scan in a Stop-path gate.

Answers one question per candidate artifact: does some OTHER file mention its
name token? Cost is bounded three ways: a deadline, one kernel lock so two
Stops never scan at once, and a two-stage search (the changed files first,
in-process; the whole tree only for the tokens still unresolved, with
`git grep -l` so output is one path per matching file, never one line per match).

    afk-python bounded_scan.py --repo <root> --candidates <file> --local <file>
        --result <json> [--exclude <pathspec>]... [--deadline <s>] [--lock <path>]

    --candidates  NUL-separated `path\\0token\\0` pairs
    --local       NUL-separated paths searched before the whole tree
    --result      JSON verdict, written atomically
    --deadline    seconds; default AFK_SCAN_DEADLINE, else 120
    --lock        lock file; default <git common dir>/afk/locks/repository-scan.lock

Exit 0: a complete verdict is in the result file. Exit 75: unknown, with
`detail` one of lock_busy | timeout | scan_failure | bad_input. A caller must
treat every other exit as unknown too, and never as an orphan.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

EXIT_UNKNOWN = 75
DEFAULT_DEADLINE = 120.0
RESTART_AFTER_FILES = 200
MAX_RESTARTS = 3
LEDGER = ".claude/wiring-ious.md"
HOOKS_PREFIX = ".claude/hooks/"
BINARY_PROBE = 8000


class Unknown(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def read_nul_file(path: str) -> list[str]:
    raw = Path(path).read_bytes()
    parts = raw.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    return [p.decode("utf-8", "surrogateescape") for p in parts]


def parse_candidates(path: str) -> list[tuple[str, str]]:
    try:
        items = read_nul_file(path)
    except OSError as problem:
        raise Unknown("bad_input") from problem
    if len(items) % 2:
        raise Unknown("bad_input")
    pairs = [(items[i], items[i + 1]) for i in range(0, len(items), 2)]
    seen: set[str] = set()
    for candidate, token in pairs:
        if not candidate or not token or "\n" in token or candidate in seen:
            raise Unknown("bad_input")
        seen.add(candidate)
    return pairs


class Resolver:
    """Per token: its candidate paths and up to two distinct paths seen holding it."""

    def __init__(self, pairs: list[tuple[str, str]]):
        self.candidates: dict[str, set[str]] = {}
        for candidate, token in pairs:
            self.candidates.setdefault(token, set()).add(candidate)
        self.seen: dict[str, set[str]] = {token: set() for token in self.candidates}
        self.bytes_of = {t: t.encode("utf-8", "surrogateescape") for t in self.candidates}
        self.residue: set[str] = set(self.candidates)

    def record(self, path: str, data: bytes) -> None:
        for token in tuple(self.residue):
            if self.bytes_of[token] in data:
                held = self.seen[token]
                if len(held) < 2:
                    held.add(path)
                self._settle(token)

    def _settle(self, token: str) -> None:
        held = self.seen[token]
        if all(held - {c} for c in self.candidates[token]):
            self.residue.discard(token)

    def wired(self, candidate: str, token: str) -> bool:
        return bool(self.seen[token] - {candidate})


def excluded(path: str, excludes: list[str]) -> bool:
    if path == LEDGER or path.startswith(HOOKS_PREFIX):
        return True
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in excludes)


def kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
            )
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.SubprocessError:
        pass


class LockFile:
    """Non-blocking kernel lock; the kernel drops it when the holder dies."""

    def __init__(self, path: str):
        self.path = path
        self.handle = None

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        handle = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self.handle = handle
        return True

    def release(self) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None


def default_lock(repo: str, git_cmd: list[str]) -> str:
    out = subprocess.run(
        [*git_cmd, "rev-parse", "--git-common-dir"], cwd=repo,
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    common = out.stdout.strip()
    if out.returncode != 0 or not common:
        raise Unknown("scan_failure")
    return os.path.join(os.path.abspath(os.path.join(repo, common)), "afk", "locks", "repository-scan.lock")


def pump(stream, sink: "queue.Queue[bytes | None]") -> None:
    """Split a NUL-separated stream into paths; None marks the end."""
    tail = b""
    try:
        while True:
            chunk = stream.read1(65536) if hasattr(stream, "read1") else stream.read(65536)
            if not chunk:
                break
            tail += chunk
            *whole, tail = tail.split(b"\0")
            for item in whole:
                sink.put(item)
    except (OSError, ValueError):
        pass
    if tail:
        sink.put(tail)
    sink.put(None)


def tree_pass(repo: str, resolver: Resolver, excludes: list[str], remaining, git_cmd: list[str],
              stats: dict, allow_restart: bool, read_paths: set[str]) -> str:
    """One `git grep -l` run over the residue. Returns done | restart."""
    tokens = sorted(resolver.residue)
    pattern_file = tempfile.NamedTemporaryFile(prefix="afk-scan-", suffix=".pat", delete=False)
    try:
        with pattern_file:
            pattern_file.write(b"\n".join(resolver.bytes_of[t] for t in tokens) + b"\n")
        args = [
            *git_cmd, "grep", "-l", "-z", "-I", "--untracked", "-F", "-f", pattern_file.name,
            "--", ".", f":(exclude){LEDGER}", ":(exclude).claude/hooks/*",
            *[f":(exclude){e}" for e in excludes],
        ]
        popen_kwargs = {"start_new_session": True} if os.name != "nt" else {}
        proc = subprocess.Popen(
            args, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, **popen_kwargs,
        )
        sink: "queue.Queue[bytes | None]" = queue.Queue()
        reader = threading.Thread(target=pump, args=(proc.stdout, sink), daemon=True)
        reader.start()
        size_at_start = len(resolver.residue)
        read_since_start = 0
        try:
            while True:
                left = remaining()
                if left <= 0:
                    raise Unknown("timeout")
                try:
                    item = sink.get(timeout=min(left, 1.0))
                except queue.Empty:
                    continue
                if item is None:
                    break
                path = item.decode("utf-8", "surrogateescape")
                if not path or path in read_paths:
                    continue
                try:
                    data = Path(repo, path).read_bytes()
                except OSError as problem:
                    raise Unknown("scan_failure") from problem
                read_paths.add(path)
                stats["files_read"] += 1
                read_since_start += 1
                resolver.record(path, data)
                if not resolver.residue:
                    return "done"
                if (allow_restart and read_since_start >= RESTART_AFTER_FILES
                        and len(resolver.residue) < size_at_start):
                    return "restart"
            proc.wait(timeout=max(remaining(), 0.1))
            if proc.returncode not in (0, 1):
                raise Unknown("scan_failure")
            return "done"
        except subprocess.TimeoutExpired as problem:
            raise Unknown("timeout") from problem
        finally:
            kill_tree(proc)
            reader.join(timeout=5)
    finally:
        try:
            os.unlink(pattern_file.name)
        except OSError:
            pass


def scan(repo: str, pairs: list[tuple[str, str]], local: list[str], excludes: list[str],
         deadline: float, git_cmd: list[str] | None = None, max_restarts: int = MAX_RESTARTS) -> dict:
    git_cmd = git_cmd or ["git"]
    started = time.monotonic()

    def remaining() -> float:
        return deadline - (time.monotonic() - started)

    resolver = Resolver(pairs)
    stats = {"files_read": 0, "restarts": 0}
    tokens_total = len(resolver.candidates)

    tried: set[str] = set()
    read_paths: set[str] = set()
    for path in local:
        if remaining() <= 0:
            raise Unknown("timeout")
        if path in tried or not resolver.residue:
            continue
        tried.add(path)
        if excluded(path, excludes):
            continue
        try:
            data = Path(repo, path).read_bytes()
        except OSError:
            continue
        if b"\0" in data[:BINARY_PROBE]:
            continue
        stats["files_read"] += 1
        read_paths.add(path)
        resolver.record(path, data)
    tokens_tree = len(resolver.residue)

    while resolver.residue:
        outcome = tree_pass(repo, resolver, excludes, remaining, git_cmd, stats,
                            stats["restarts"] < max_restarts, read_paths)
        if outcome == "restart":
            stats["restarts"] += 1
            continue
        break

    wired = [c for c, token in pairs if resolver.wired(c, token)]
    wired_set = set(wired)
    return {
        "status": "complete", "detail": "",
        "wired": wired, "unresolved": [c for c, _ in pairs if c not in wired_set],
        "scan_ms": int((time.monotonic() - started) * 1000), "lock_wait_ms": 0,
        "tokens_total": tokens_total, "tokens_local_resolved": tokens_total - tokens_tree,
        "tokens_tree": tokens_tree, "restarts": stats["restarts"], "files_read": stats["files_read"],
    }


def write_result(path: str, payload: dict) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    handle, temp = tempfile.mkstemp(prefix=".scan-result-", dir=directory)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            json.dump(payload, out)
        os.replace(temp, path)
    except OSError:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def unknown_payload(detail: str, started: float) -> dict:
    return {
        "status": "unknown", "detail": detail, "wired": [], "unresolved": [],
        "scan_ms": int((time.monotonic() - started) * 1000), "lock_wait_ms": 0,
        "tokens_total": 0, "tokens_local_resolved": 0, "tokens_tree": 0, "restarts": 0, "files_read": 0,
    }


def run(argv: list[str], git_cmd: list[str] | None = None) -> int:
    started = time.monotonic()
    parser = argparse.ArgumentParser(prog="bounded_scan.py")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--local", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--deadline", type=float)
    parser.add_argument("--lock")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return EXIT_UNKNOWN
    deadline = args.deadline
    if deadline is None:
        try:
            deadline = float(os.environ.get("AFK_SCAN_DEADLINE", DEFAULT_DEADLINE))
        except ValueError:
            deadline = DEFAULT_DEADLINE
    lock = None
    try:
        try:
            pairs = parse_candidates(args.candidates)
            local = read_nul_file(args.local)
        except OSError as problem:
            raise Unknown("bad_input") from problem
        lock_path = args.lock or default_lock(args.repo, git_cmd or ["git"])
        lock = LockFile(lock_path)
        if not lock.acquire():
            raise Unknown("lock_busy")
        payload = scan(args.repo, pairs, local, args.exclude, deadline, git_cmd)
        write_result(args.result, payload)
        return 0
    except Unknown as unknown:
        verdict = unknown.detail
    except (OSError, subprocess.SubprocessError):
        verdict = "scan_failure"
    finally:
        if lock is not None:
            lock.release()
    try:
        write_result(args.result, unknown_payload(verdict, started))
    except OSError:
        pass
    return EXIT_UNKNOWN


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
