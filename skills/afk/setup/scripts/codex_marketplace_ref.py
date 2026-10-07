#!/usr/bin/env afk-python
"""Check or remove the AFK marketplace ref in Codex config.

    codex_marketplace_ref.py [--check] [--config PATH]

Without ``--check``, remove only ``marketplaces.afk-toolkit.ref``. Preserve
all other bytes, write a timestamped backup, and replace the file atomically.
With ``--check``, exit 0 when no pin exists and 1 when one exists. Emit no
output. A missing config or marketplace is already unpinned. Exit 2 when the
target table is malformed or the pin cannot be removed as one whole line.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path


TABLE = re.compile(
    r"^\s*\[\s*marketplaces\s*\.\s*(?:afk-toolkit|\"afk-toolkit\"|'afk-toolkit')\s*\]"
    r"\s*(?:#.*)?$"
)
ANY_TABLE = re.compile(r"^\s*\[")
REF = re.compile(r"^\s*(?:ref|\"ref\"|'ref')\s*=")
INLINE_PIN = re.compile(
    r"^\s*(?:afk-toolkit|\"afk-toolkit\"|'afk-toolkit')\s*=\s*\{[^}]*"
    r"(?:ref|\"ref\"|'ref')\s*=",
)
MARKETPLACES_TABLE = re.compile(r"^\s*\[\s*marketplaces\s*\]\s*(?:#.*)?$")


def fail(message: str) -> "NoReturn":
    print(message, file=sys.stderr)
    raise SystemExit(2)


def default_config() -> Path:
    root = os.environ.get("CODEX_HOME")
    return Path(root) / "config.toml" if root else Path.home() / ".codex" / "config.toml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report a pin without writing")
    parser.add_argument("--config", type=Path, default=default_config(), help="Codex config.toml path")
    return parser.parse_args()


def decode(raw: bytes, path: Path) -> tuple[str, bytes]:
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    try:
        return raw[len(bom):].decode("utf-8"), bom
    except UnicodeDecodeError as error:
        fail(f"not UTF-8 TOML: {path} ({error})")


def ref_lines(text: str) -> list[int]:
    lines = text.splitlines(keepends=True)
    matches: list[int] = []
    in_target = False
    in_marketplaces = False
    for index, line in enumerate(lines):
        content = line.rstrip("\r\n")
        if ANY_TABLE.match(content):
            in_target = bool(TABLE.match(content))
            in_marketplaces = bool(MARKETPLACES_TABLE.match(content))
            if "marketplaces" in content and "afk-toolkit" in content and not in_target:
                if not content.rstrip().endswith("]"):
                    fail("malformed marketplaces.afk-toolkit table; refusing to edit")
            continue
        if in_target and REF.match(content):
            matches.append(index)
        if in_marketplaces and INLINE_PIN.match(content):
            fail("inline marketplaces.afk-toolkit ref cannot be removed as one line; refusing to edit")
    if len(matches) > 1:
        fail("found a pin but not one removable marketplaces.afk-toolkit ref line; refusing to edit")
    return matches


def remove_ref_line(text: str, index: int) -> str:
    lines = text.splitlines(keepends=True)
    del lines[index]
    return "".join(lines)


def backup_path(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d%H%M%SZ", time.gmtime())
    candidate = path.with_name(f"{path.name}.bak-{stamp}")
    suffix = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak-{stamp}-{suffix}")
        suffix += 1
    return candidate


def atomic_write(path: Path, raw: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    path: Path = args.config
    if not path.exists():
        return 0
    try:
        raw = path.read_bytes()
    except OSError as error:
        fail(f"cannot read Codex config: {path} ({error})")
    text, bom = decode(raw, path)
    matches = ref_lines(text)
    if not matches:
        return 0
    if args.check:
        return 1

    updated_text = remove_ref_line(text, matches[0])

    try:
        shutil.copy2(path, backup_path(path))
        atomic_write(path, bom + updated_text.encode("utf-8"))
    except OSError as error:
        fail(f"cannot update Codex config: {path} ({error})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
