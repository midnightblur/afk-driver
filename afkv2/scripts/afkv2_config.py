"""Read a repository's `.afkv2/config.json` and answer one JSON object.

Command: `afkv2_config.py read [--start DIR]`. Exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path, PurePath
from urllib.parse import urlsplit

CONFIG_DIR = ".afkv2"
CONFIG_FILE = "config.json"
DATA_FOLDER_NAME = "afkv2"
TRACKER_KINDS = ("jira", "github-issues")
OWNERSHIP_GRADES = ("own", "shared")
FORGE_KINDS = ("github", "gitlab")
LIVE_READY_SECONDS = 120
LIVE_FIELDS = ("start", "address", "ready_seconds", "stop", "needs", "proven_at", "proven_head")
VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_UNREADABLE = 2
UNREADABLE_CODES = frozenset({"unreadable", "no-data-folder", "usage"})


class Refusal(Exception):
    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def read_config(start: str | os.PathLike | None = None, *, with_live: bool = True) -> dict:
    """Resolve the `.afkv2` values for the repository that holds `start` (default: cwd).

    `with_live=False` skips the stored `live` block, so a caller can replace a bad one."""
    try:
        config_file = _find_config(Path(start or os.getcwd()).resolve())
        repo_root = config_file.parent.parent
        raw = _load(config_file)
        answer = {
            "ok": True,
            "repo_root": str(repo_root),
            "config_file": str(config_file),
            "spec_folder": _spec_folder(raw, repo_root),
            "tracker": _tracker(raw),
            "ownership": _ownership(raw),
            "forge": _forge(raw),
            "data_folder": str(data_folder()),
        }
        if with_live and raw.get("live") is not None:
            answer["live"] = live_block(raw["live"])
        return answer
    except Refusal as refusal:
        return {"ok": False, "error": {"code": refusal.code, "reason": refusal.reason}}


def data_folder() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise Refusal("no-data-folder", "LOCALAPPDATA is not set; the afkv2 data folder is %LOCALAPPDATA%\\afkv2")
    return Path(base) / DATA_FOLDER_NAME


def exit_code(answer: dict) -> int:
    if answer.get("ok"):
        return EXIT_OK
    return EXIT_UNREADABLE if answer["error"]["code"] in UNREADABLE_CODES else EXIT_REFUSED


def _find_config(start: Path) -> Path:
    for folder in (start, *start.parents):
        candidate = folder / CONFIG_DIR / CONFIG_FILE
        if candidate.is_file():
            return candidate
        if (folder / ".git").exists():
            break
    raise Refusal("no-config", f"no {CONFIG_DIR}/{CONFIG_FILE} between {start} and its repository root")


def _load(config_file: Path) -> dict:
    try:
        raw = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Refusal("unreadable", f"{config_file}: {error}") from error
    if not isinstance(raw, dict):
        raise Refusal("bad-value", "config: the file must hold one JSON object")
    return raw


def _spec_folder(raw: dict, repo_root: Path) -> str:
    value = raw.get("spec_folder")
    if not isinstance(value, str) or not value.strip():
        raise Refusal("bad-value", "spec_folder: a non-empty folder path relative to the repository root is required")
    if PurePath(value).anchor or ".." in PurePath(value).parts:
        raise Refusal("bad-value", f"spec_folder: {value!r} must stay inside the repository root")
    return str(repo_root / value)


def _tracker(raw: dict) -> dict | None:
    value = raw.get("tracker")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise Refusal("bad-value", "tracker: an object with a kind is required")
    if value.get("kind") not in TRACKER_KINDS:
        raise Refusal("bad-value", f"tracker.kind: {value.get('kind')!r} is not one of {', '.join(TRACKER_KINDS)}")
    return value


def _ownership(raw: dict) -> dict | None:
    value = raw.get("ownership")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise Refusal("bad-value", "ownership: an object with own and shared lists is required")
    for grade, globs in value.items():
        if grade not in OWNERSHIP_GRADES:
            raise Refusal("bad-value", f"ownership.{grade}: not one of {', '.join(OWNERSHIP_GRADES)}")
        if not isinstance(globs, list) or not all(isinstance(g, str) and g.strip() for g in globs):
            raise Refusal("bad-value", f"ownership.{grade}: a list of non-empty path globs is required")
    return value


def _forge(raw: dict) -> str | None:
    value = raw.get("forge")
    if value is None:
        return None
    if value not in FORGE_KINDS:
        raise Refusal("bad-value", f"forge: {value!r} is not one of {', '.join(FORGE_KINDS)}")
    return value


def live_block(value: object) -> dict:
    """The `live` block with its defaults; a bad field refuses `bad-value`. `needs` holds variable names, never values."""
    if not isinstance(value, dict):
        raise Refusal("bad-value", "live: an object with start and address is required")
    for name in value:
        if name not in LIVE_FIELDS:
            raise Refusal("bad-value", f"live.{name}: not one of {', '.join(LIVE_FIELDS)}")
    start = value.get("start")
    if not isinstance(start, str) or not start.strip():
        raise Refusal("bad-value", "live.start: a non-empty command line is required")
    address = value.get("address")
    parts = urlsplit(address) if isinstance(address, str) else None
    if parts is None or parts.scheme not in ("http", "https") or not parts.hostname:
        raise Refusal("bad-value", f"live.address: {address!r} is not an http or https URL")
    ready = value.get("ready_seconds", LIVE_READY_SECONDS)
    if not isinstance(ready, int) or isinstance(ready, bool) or ready <= 0:
        raise Refusal("bad-value", f"live.ready_seconds: {ready!r} is not a whole number of seconds above 0")
    stop = value.get("stop")
    if stop is not None and (not isinstance(stop, str) or not stop.strip()):
        raise Refusal("bad-value", "live.stop: a non-empty command line or null is required")
    needs = value.get("needs", [])
    if not isinstance(needs, list) or not all(isinstance(n, str) and VARIABLE_NAME.fullmatch(n) for n in needs):
        raise Refusal("bad-value", "live.needs: a list of variable names is required; a value is never stored")
    for name in ("proven_at", "proven_head"):
        if value.get(name) is not None and not isinstance(value[name], str):
            raise Refusal("bad-value", f"live.{name}: a string or null is required")
    return {"start": start, "address": address, "ready_seconds": ready, "stop": stop, "needs": list(needs),
            "proven_at": value.get("proven_at"), "proven_head": value.get("proven_head")}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise Refusal("usage", message)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(prog="afkv2_config.py", add_help=False)
    parser.add_argument("verb", choices=["read"])
    parser.add_argument("--start", default=None)
    try:
        args = parser.parse_args(argv)
        answer = read_config(args.start)
    except Refusal as refusal:
        answer = {"ok": False, "error": {"code": refusal.code, "reason": refusal.reason}}
    print(json.dumps(answer))
    return exit_code(answer)


if __name__ == "__main__":
    sys.exit(main())
