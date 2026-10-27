#!/usr/bin/env afk-python
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
import importlib.util
import pathlib
import re
import sys
from typing import NamedTuple, Sequence

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[4]


def _load_safe_writer():
    name = "afk_safe_write"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, PLUGIN_ROOT / "scripts" / "safe_write.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
    return sys.modules[name]


safe_write = _load_safe_writer()

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


def _update(target: pathlib.Path, transform) -> bool:
    try:
        return safe_write.update_locked(target, transform)
    except safe_write.SafeWriteError as exc:
        raise InstallError(f"target {exc}") from exc


def _text(data: bytes) -> str:
    return data.decode(safe_write.ENCODING, safe_write.ERRORS)


def _bytes(text: str) -> bytes:
    return text.encode(safe_write.ENCODING, safe_write.ERRORS)


@contextlib.contextmanager
def _target_lock(target: pathlib.Path):
    stack = contextlib.ExitStack()
    try:
        stack.enter_context(safe_write._file_lock(pathlib.Path(target)))
    except safe_write.SafeWriteError as exc:
        raise InstallError(f"target {exc}") from exc
    with stack:
        yield


def write_if_unchanged(
    target_path: pathlib.Path | str,
    expected: bytes,
    updated: bytes,
) -> None:
    """Atomically replace one target when its bytes still match the snapshot."""
    target = pathlib.Path(target_path)

    def transform(text: str) -> str:
        if _bytes(text) != expected:
            raise InstallError(f"target changed during update: {target}")
        return _text(updated)

    _update(target, transform)


def install(
    source_path: pathlib.Path | str,
    target_path: pathlib.Path | str,
    *,
    sentinel: str = "behaviors",
    remove_sentinels: Sequence[str] = LEGACY_SENTINELS,
) -> Result:
    source = pathlib.Path(source_path)
    target_path = pathlib.Path(target_path)
    seen: dict[str, object] = {}

    def transform(text: str) -> str:
        target = _bytes(text)
        eol = _target_eol(target)
        replacement = _source_block(source, sentinel).replace(b"\n", eol)
        matches = _matches(target, (sentinel, *remove_sentinels))
        seen["matches"] = matches
        seen["had_unified"] = any(name == sentinel for _, _, name in matches)
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
            return _text(b"".join(chunks))
        separator = b"" if not target or target.endswith((b"\n", b"\r")) else eol
        return _text(target + separator + replacement + eol)

    changed = _update(target_path, transform)
    if not changed:
        action = "already-current"
    elif seen["had_unified"]:
        action = "refreshed"
    else:
        action = "installed"
    return Result(action, max(0, len(seen["matches"]) - 1), changed)


def teardown(
    target_path: pathlib.Path | str,
    *,
    sentinel: str = "behaviors",
    remove_sentinels: Sequence[str] = LEGACY_SENTINELS,
) -> Result:
    target_path = pathlib.Path(target_path)
    seen: dict[str, int] = {}

    def transform(text: str) -> str:
        target = _bytes(text)
        matches = _matches(target, (sentinel, *remove_sentinels))
        seen["removed"] = len(matches)
        chunks: list[bytes] = []
        cursor = 0
        for start, end, _name in matches:
            chunks.append(target[cursor:start])
            cursor = end
        chunks.append(target[cursor:])
        return _text(b"".join(chunks))

    changed = _update(target_path, transform)
    return Result("removed" if changed else "absent", seen["removed"], changed)


def _legacy(argv: Sequence[str]) -> int:
    if len(argv) not in (2, 3):
        return 2
    source, target = pathlib.Path(argv[0]), pathlib.Path(argv[1])
    name = argv[2] if len(argv) == 3 else "plain-language"
    replacement = _source_block(source, name)
    pattern = sentinel_pattern(name)
    found: list[bool] = []

    def transform(text: str) -> str:
        target.stat()
        data = _bytes(text)
        found.append(bool(pattern.search(data)))
        if not found[0]:
            return text
        block = replacement.replace(b"\n", _target_eol(data))
        return _text(pattern.sub(lambda _match: block, data, count=1))

    changed = _update(target, transform)
    if not found[0]:
        return 1
    if changed:
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
