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
CODE_SUFFIXES = frozenset({".py", ".cmd", ".bat", ".ps1", ".sh", ".js", ".mjs", ".cjs", ".ts"})

V1_FILE_PART = re.compile(r"afk(?!v2)", re.IGNORECASE)
V1_TEXT = (
    re.compile(r"(?<![A-Za-z0-9_])AFK[_]"),
    re.compile(r"(?<![a-z0-9])afk(?!v2)(?=[-_:./a-z0-9])", re.IGNORECASE),
    re.compile(r"[.]afk(?![a-z0-9])", re.IGNORECASE),
)
URL = re.compile(r"https?://\S+")

MARKER_TOKEN = re.compile(r"(?<![a-z0-9])afk(?:v2)?[-:][a-z0-9][a-z0-9:-]*", re.IGNORECASE)
SUBSTRING_MATCH = re.compile(
    r"\.(?:startswith|endswith|find|rfind|index|rindex|count|search|match|split|partition|replace"
    r"|includes|indexOf|lastIndexOf|contains)\("
    r"|\bre\.(?:findall|finditer|sub)\("
    r"|(?<![=!<>])\bin\b"
    r"|\b(?:findstr|find|grep|strstr)\b"
    r"|-(?:like|match|contains)\b"
)


def marker_hash(body: str) -> str:
    """First 12 hex characters of SHA-256 over the text between the marker lines."""
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
        for number, line in _text_lines(path):
            scrubbed = URL.sub("", line)
            if any(pattern.search(scrubbed) for pattern in V1_TEXT):
                problems.append(f"{relative.as_posix()}:{number}: v1 name: {line.strip()}")
    return problems


def check_marker_matching(root: Path) -> list[str]:
    problems = []
    for path in _files(root):
        if path.suffix.lower() not in CODE_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        for number, line in _text_lines(path):
            if MARKER_TOKEN.search(line) and SUBSTRING_MATCH.search(line):
                problems.append(f"{relative}:{number}: marker matched by prefix or substring; compare the full line")
    return problems


def run_checks(root: Path = PLUGIN_ROOT) -> list[str]:
    root = Path(root)
    problems = _check_manifests(root)
    source = _read_source(root)
    if source is None:
        problems.append(f"{CORE_SOURCE.as_posix()}: missing")
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
        return [f"{CORE_SOURCE.as_posix()}: missing"]
    problems = check_core_size(source)
    if problems:
        return problems
    built = root / BUILT_DIR
    built.mkdir(parents=True, exist_ok=True)
    for name, text in build_hook_outputs(source).items():
        (built / name).write_text(text, encoding="utf-8", newline="")
    return run_checks(root)


def _check_built(root: Path, source: str) -> list[str]:
    built = root / BUILT_DIR
    expected = build_hook_outputs(source)
    problems = []
    for name, text in expected.items():
        path = built / name
        if not path.is_file():
            problems.append(f"{(BUILT_DIR / name).as_posix()}: missing; run plugin_check.py build")
        elif path.read_text(encoding="utf-8") != text:
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
        for event in HOOK_EVENTS:
            if event not in events:
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
    path = root / CORE_SOURCE
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and not SKIPPED_DIRS.intersection(path.relative_to(root).parts):
            yield path


def _text_lines(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    yield from enumerate(text.splitlines(), start=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="plugin_check.py")
    parser.add_argument("verb", nargs="?", default="check", choices=["check", "build"])
    parser.add_argument("--root", default=str(PLUGIN_ROOT))
    args = parser.parse_args(argv)
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
