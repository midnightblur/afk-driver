"""Diff-vs-scope safety check for AFK SubTask runs.

Pure function over a unified git diff plus the SubTask Scope globs, the driver's
forbidden-pattern list, the parent Enhancement's home module, and a regex for
cross-module marker comments. Returns a list of violations (empty if clean).
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from typing import Iterable, Literal, Optional

ViolationReason = Literal[
    "out-of-scope",
    "forbidden-pattern",
    "cross-module-no-marker",
]

_MODULE_RE = re.compile(r"^(\d{5}-[a-z0-9-]+)/")
_DIFF_HEADER_RE = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.MULTILINE)


@dataclass(frozen=True)
class Violation:
    path: str
    reason: ViolationReason
    detail: str


def enforce(
    git_diff: str,
    scope_globs: Iterable[str],
    forbidden_patterns: Iterable[str],
    home_module: Optional[str],
    marker_pattern: re.Pattern,
) -> list[Violation]:
    scope = tuple(scope_globs)
    forbidden = tuple(forbidden_patterns)
    violations: list[Violation] = []

    for path in extract_changed_paths(git_diff):
        forbidden_hit = _first_match(path, forbidden)
        if forbidden_hit is not None:
            violations.append(
                Violation(path=path, reason="forbidden-pattern", detail=f"matched pattern {forbidden_hit!r}")
            )
            continue

        if not any(_matches_glob(path, g) for g in scope):
            violations.append(
                Violation(path=path, reason="out-of-scope", detail="no scope glob matched")
            )
            continue

        path_module = module_of(path)
        if (
            home_module is not None
            and path_module is not None
            and path_module != home_module
        ):
            if not _has_marker_comment_for_path(git_diff, path, marker_pattern):
                violations.append(
                    Violation(
                        path=path,
                        reason="cross-module-no-marker",
                        detail=(
                            f"cross-module edit ({path_module!r} != home {home_module!r}) "
                            "without marker comment in added lines"
                        ),
                    )
                )

    return violations


def extract_changed_paths(git_diff: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _DIFF_HEADER_RE.finditer(git_diff):
        post = m.group(2)
        if post not in seen:
            seen.add(post)
            out.append(post)
    return out


def module_of(path: str) -> Optional[str]:
    norm = path.replace("\\", "/")
    m = _MODULE_RE.match(norm)
    return m.group(1) if m else None


def _first_match(path: str, patterns: Iterable[str]) -> Optional[str]:
    for p in patterns:
        if _matches_glob(path, p):
            return p
    return None


def _matches_glob(path: str, pattern: str) -> bool:
    norm = path.replace("\\", "/")
    if re.match(_glob_to_regex(pattern), norm) is not None:
        return True
    if "/" not in pattern:
        return fnmatch.fnmatchcase(os.path.basename(norm), pattern)
    return False


def _glob_to_regex(pattern: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern[i:i + 3] == "**/":
            out.append(r"(?:.*/)?")
            i += 3
        elif pattern[i:i + 2] == "**":
            out.append(r".*")
            i += 2
        elif pattern[i] == "*":
            out.append(r"[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append(r"[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "^" + "".join(out) + "$"


def _hunks_for_path(git_diff: str, path: str) -> str:
    headers = list(_DIFF_HEADER_RE.finditer(git_diff))
    for idx, m in enumerate(headers):
        if m.group(2) == path:
            start = m.start()
            end = headers[idx + 1].start() if idx + 1 < len(headers) else len(git_diff)
            return git_diff[start:end]
    return ""


def _has_marker_comment_for_path(
    git_diff: str, path: str, marker_pattern: re.Pattern
) -> bool:
    section = _hunks_for_path(git_diff, path)
    for line in section.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            if marker_pattern.search(line):
                return True
    return False
