"""Parser/emitter for the AFK SubTask description Markdown contract.

Required H2 sections: Goal, Scope, Acceptance, Test command.
Optional: Parent PRD, Blocked by, Implementation Notes (auto-maintained), extras.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

REQUIRED_HEADINGS: tuple[str, ...] = ("Goal", "Scope", "Acceptance", "Test command")
IMPL_NOTES_HEADING = "Implementation Notes (auto-maintained)"
KNOWN_HEADINGS: frozenset[str] = frozenset(
    (*REQUIRED_HEADINGS, "Parent PRD", "Blocked by", IMPL_NOTES_HEADING)
)

_H2_SPLIT = re.compile(r"(?m)^## (.+)$\n?")
_FENCED_BLOCK = re.compile(r"```[^\n]*\n(.*?)\n?```", re.DOTALL)


@dataclass(frozen=True)
class SubTaskTemplate:
    goal: str
    scope: tuple[str, ...]
    acceptance: tuple[str, ...]
    test_command: str
    parent_prd: Optional[str] = None
    blocked_by: Optional[str] = None
    impl_notes_block: str = ""
    extras: tuple[tuple[str, str], ...] = ()


def parse(markdown: str) -> SubTaskTemplate:
    parts = _H2_SPLIT.split(markdown)
    if len(parts) == 1:
        raise ValueError("no H2 (## ...) headings found")
    if parts[0].strip():
        raise ValueError(f"unexpected content before first H2: {parts[0]!r}")

    sections: list[tuple[str, str]] = []
    seen: set[str] = set()
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if heading in seen:
            raise ValueError(f"duplicate H2 heading: {heading!r}")
        seen.add(heading)
        sections.append((heading, body))

    by_heading = dict(sections)
    missing = [r for r in REQUIRED_HEADINGS if r not in by_heading]
    if missing:
        raise ValueError(f"missing required H2(s): {missing}")

    extras = tuple(
        (h, b.rstrip("\n")) for h, b in sections if h not in KNOWN_HEADINGS
    )

    return SubTaskTemplate(
        goal=by_heading["Goal"].strip(),
        scope=_parse_scope_bullets(by_heading["Scope"]),
        acceptance=_parse_acceptance_items(by_heading["Acceptance"]),
        test_command=_parse_fenced(by_heading["Test command"]),
        parent_prd=_strip_or_none(by_heading.get("Parent PRD")),
        blocked_by=_strip_or_none(by_heading.get("Blocked by")),
        impl_notes_block=by_heading.get(IMPL_NOTES_HEADING, "").rstrip("\n"),
        extras=extras,
    )


def emit(t: SubTaskTemplate) -> str:
    out: list[str] = [f"## Goal\n{t.goal}\n"]
    out.append("## Scope\n" + "".join(f"- {g}\n" for g in t.scope))
    out.append("## Acceptance\n" + "".join(f"{a}\n" for a in t.acceptance))
    out.append(f"## Test command\n```\n{t.test_command}\n```\n")
    if t.parent_prd is not None:
        out.append(f"## Parent PRD\n{t.parent_prd}\n")
    if t.blocked_by is not None:
        out.append(f"## Blocked by\n{t.blocked_by}\n")
    for heading, body in t.extras:
        out.append(f"## {heading}\n{body}\n" if body else f"## {heading}\n")
    if t.impl_notes_block:
        out.append(f"## {IMPL_NOTES_HEADING}\n{t.impl_notes_block}\n")
    else:
        out.append(f"## {IMPL_NOTES_HEADING}\n")
    return "\n".join(out)


def _strip_or_none(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    stripped = s.strip()
    return stripped or None


def _parse_scope_bullets(body: str) -> tuple[str, ...]:
    out: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and not stripped.startswith("- ["):
            out.append(stripped[2:].strip())
    return tuple(out)


def _parse_acceptance_items(body: str) -> tuple[str, ...]:
    out: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if (
            stripped.startswith("- [ ]")
            or stripped.startswith("- [x]")
            or stripped.startswith("- [X]")
        ):
            out.append(stripped)
    return tuple(out)


def _parse_fenced(body: str) -> str:
    m = _FENCED_BLOCK.search(body)
    if not m:
        raise ValueError(f"no fenced code block found in Test command body: {body!r}")
    return m.group(1).strip("\n")
