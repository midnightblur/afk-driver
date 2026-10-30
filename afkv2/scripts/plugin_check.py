"""Build and check the afkv2 plugin tree; answer one JSON object.

Command: `plugin_check.py [check|build] [--root DIR]`. Exit 0 ok, 1 problems found, 2 usage.
`build` regenerates the prebuilt hook outputs from the core-behaviors source, then checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE = Path("core") / "CORE-BEHAVIORS.md"
BUILT_DIR = Path("hooks") / "built"
MANIFESTS = (Path(".claude-plugin") / "plugin.json", Path(".codex-plugin") / "plugin.json")
HOOKS_FILE = Path("hooks") / "hooks.json"
HOOK_EVENTS = ("SessionStart", "SubagentStart")
PLUGIN_NAME = "afkv2"
CORE_LIMIT = 8000

MARKER = "afkv2-core-behaviors"
PLAIN_VARIANT = MARKER + ".txt"
CLAUDE_SUBAGENT_VARIANT = MARKER + ".claude-subagent.json"

SKIPPED_DIRS = frozenset({"__pycache__", ".pytest_cache"})
PROSE_SUFFIXES = frozenset({".md", ".txt", ".json"})
BINARY_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".woff", ".woff2", ".pdf", ".zip"})
NOT_TEXT = "not UTF-8 text; the check cannot read it"

V1_FILE_PART = re.compile(r"af[k](?!v2)", re.IGNORECASE)
V1_NAME = re.compile(r"(?<![a-z0-9])af[k](?!v2)", re.IGNORECASE)
V1_PROSE_WORD = re.compile(r"(?:^|(?<=[\s(`\"']))af[k](?=$|[\s)`,;!?]|[.:](?:\s|$))", re.IGNORECASE)
V1_CSS_CLASS = re.compile(r"class(?:Name)?\s*=\s*[\"'][^\"']*(?<![a-z0-9-])af[k](?![a-z0-9-])", re.IGNORECASE)
URL = re.compile(r"https?://[^\s\"'`,;()<>{}$]+")

MARKER_TOKEN = re.compile(r"(?<![a-z0-9])af[k](?:v2)?[-:][a-z0-9][a-z0-9:-]*", re.IGNORECASE)
SUBSTRING_MATCH = re.compile(
    r"\.(?:startswith|endswith|rfind|findall|finditer|index|rindex|count|search|match|matchall|exec|test"
    r"|sub|subn|split|rsplit|partition|rpartition|replace|replaceall|removeprefix|removesuffix"
    r"|includes|indexof|lastindexof|contains|slice|substring|substr)\("
    r"|\[(?:[^\]\"':{}]|\"[^\"]*\"|'[^']*')*:"
    r"|[%!]\w+:\S"
    r"|=~"
    r"|\$\{\w+[:#%]"
    r"|(?<![\w-])-[ci]?(?:not)?(?:like|match|contains|replace|split|in)\b"
    r"|(?<![a-z0-9])af[k](?:v2)?[-:][a-z0-9:-]*\*"
    r"|(?<![\w:])(?<![a-z0-9]-)(?:select-string|in|findstr|find|grep|strstr|sed|awk|sls)(?![\w:-])",
    re.IGNORECASE,
)


def marker_hash(body: str) -> str:
    """First 12 hex characters of SHA-256 over the lines between the marker lines.

    `body` joins those lines with LF and has no line break at its end.
    """
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def build_hook_outputs(source_text: str) -> dict[str, str]:
    """Provider variants of the core-behaviors text: plain stdout, and Claude's subagent JSON."""
    body = source_text.replace("\r\n", "\n").rstrip("\n")
    sha = marker_hash(body)
    plain = f"{MARKER} begin {sha}\n{body}\n{MARKER} end {sha}\n"
    subagent = {"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": plain}}
    return {PLAIN_VARIANT: plain, CLAUDE_SUBAGENT_VARIANT: json.dumps(subagent) + "\n"}


def check_core_size(source_text: str) -> list[str]:
    count = len(source_text.replace("\r\n", "\n"))
    if count > CORE_LIMIT:
        return [f"{CORE_SOURCE.as_posix()}: {count} characters; the limit is {CORE_LIMIT}"]
    return []


def check_no_v1_names(root: Path) -> list[str]:
    problems = []
    for path in _files(root):
        relative = path.relative_to(root)
        if any(V1_FILE_PART.search(part) for part in relative.parts):
            problems.append(f"{relative.as_posix()}: file name uses a v1 name")
        lines, problem = _read_lines(path)
        if problem:
            problems.append(f"{relative.as_posix()}: {problem}")
        for number, line in lines:
            if _holds_v1_name(URL.sub("", line), _is_prose(relative)):
                problems.append(f"{relative.as_posix()}:{number}: v1 name: {line.strip()}")
    return problems


def check_marker_matching(root: Path) -> list[str]:
    problems = []
    for path in _files(root):
        relative = path.relative_to(root)
        if _is_prose(relative):
            continue
        lines, _ = _read_lines(path)
        for number, line in lines:
            if MARKER_TOKEN.search(line) and SUBSTRING_MATCH.search(line):
                problems.append(
                    f"{relative.as_posix()}:{number}: marker matched by prefix or substring; compare the full line"
                )
    return problems


def run_checks(root: Path = PLUGIN_ROOT) -> list[str]:
    root = Path(root)
    problems = _check_manifests(root)
    source = _read_source(root)
    if source is None:
        problems.append(f"{CORE_SOURCE.as_posix()}: missing or unreadable")
    else:
        problems += check_core_size(source)
        problems += _check_built(root, source)
    problems += check_no_v1_names(root)
    problems += check_marker_matching(root)
    return problems


def build(root: Path = PLUGIN_ROOT) -> list[str]:
    root = Path(root)
    source = _read_source(root)
    if source is None:
        return [f"{CORE_SOURCE.as_posix()}: missing or unreadable"]
    problems = check_core_size(source)
    if problems:
        return problems
    built = root / BUILT_DIR
    try:
        built.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return [f"{BUILT_DIR.as_posix()}: cannot write: {error}"]
    for name, text in build_hook_outputs(source).items():
        try:
            (built / name).write_text(text, encoding="utf-8", newline="")
        except OSError as error:
            problems.append(f"{(BUILT_DIR / name).as_posix()}: cannot write: {error}")
    return problems or run_checks(root)


def _check_built(root: Path, source: str) -> list[str]:
    built = root / BUILT_DIR
    expected = build_hook_outputs(source)
    problems = []
    for name, text in expected.items():
        path = built / name
        if not path.is_file():
            problems.append(f"{(BUILT_DIR / name).as_posix()}: missing; run plugin_check.py build")
        elif _read_bytes(path) != text.encode("utf-8"):
            problems.append(f"{(BUILT_DIR / name).as_posix()}: stale; run plugin_check.py build")
    if built.is_dir():
        for path in sorted(built.iterdir()):
            if path.name not in expected:
                problems.append(f"{(BUILT_DIR / path.name).as_posix()}: not a build output")
    return problems


def _check_manifests(root: Path) -> list[str]:
    problems = []
    for relative in MANIFESTS:
        data = _load_json(root / relative, problems)
        if data is not None and data.get("name") != PLUGIN_NAME:
            problems.append(f"{relative.as_posix()}: name must be {PLUGIN_NAME}")
    hooks = _load_json(root / HOOKS_FILE, problems)
    if hooks is not None:
        events = hooks.get("hooks", {})
        if not isinstance(events, dict):
            problems.append(f"{HOOKS_FILE.as_posix()}: hooks must be one JSON object")
            return problems
        for event in HOOK_EVENTS:
            if not _has_handler(events.get(event)):
                problems.append(f"{HOOKS_FILE.as_posix()}: no {event} registration")
    return problems


def _load_json(path: Path, problems: list[str]) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        problems.append(f"{path.name} ({path.parent.name}): unreadable: {error}")
        return None
    if not isinstance(data, dict):
        problems.append(f"{path.name} ({path.parent.name}): must hold one JSON object")
        return None
    return data


def _read_source(root: Path) -> str | None:
    return _read_text(root / CORE_SOURCE)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and not SKIPPED_DIRS.intersection(path.relative_to(root).parts):
            yield path


def _read_lines(path: Path) -> tuple[list[tuple[int, str]], str | None]:
    """Numbered lines of `path`, and the reason when the check cannot read a file it must read."""
    if path.suffix.lower() in BINARY_SUFFIXES:
        return [], None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return [], f"cannot read: {error}"
    except UnicodeDecodeError:
        return [], NOT_TEXT
    if "\x00" in text:
        return [], NOT_TEXT
    return list(enumerate(text.splitlines(), start=1)), None


def _is_prose(relative: Path) -> bool:
    """The hook registration holds commands, so it is code although its suffix is prose."""
    return relative.suffix.lower() in PROSE_SUFFIXES and relative != HOOKS_FILE


def _holds_v1_name(line: str, is_prose: bool) -> bool:
    if not is_prose:
        return V1_NAME.search(line) is not None
    if V1_CSS_CLASS.search(line):
        return True
    return any(not V1_PROSE_WORD.match(line, hit.start()) for hit in V1_NAME.finditer(line))


def _has_handler(registration: object) -> bool:
    if not isinstance(registration, list):
        return False
    for entry in registration:
        handlers = entry.get("hooks") if isinstance(entry, dict) else None
        if isinstance(handlers, list) and any(isinstance(h, dict) and h.get("command") for h in handlers):
            return True
    return False


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _UsageError(message)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(prog="plugin_check.py", add_help=False)
    parser.add_argument("verb", nargs="?", default="check", choices=["check", "build"])
    parser.add_argument("--root", default=str(PLUGIN_ROOT))
    try:
        args = parser.parse_args(argv)
    except _UsageError as error:
        print(json.dumps({"ok": False, "error": {"code": "usage", "reason": str(error)}}))
        return 2
    root = Path(args.root)
    problems = build(root) if args.verb == "build" else run_checks(root)
    if problems:
        reason = f"{len(problems)} problem(s) in {root}"
        print(json.dumps({"ok": False, "error": {"code": "check-failed", "reason": reason}, "problems": problems}))
        return 1
    print(json.dumps({"ok": True, "verb": args.verb, "root": str(root)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
