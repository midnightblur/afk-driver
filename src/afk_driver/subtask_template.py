"""Parser/emitter for the AFK SubTask description Markdown contract.

Required H2 sections: Goal, Scope, Acceptance, Test command.
Optional: Design refs, Produces, Consumes, Parent PRD, Parent SDD, Blocked by,
Conflict procedure, Implementation Notes (auto-maintained), extras.

Design refs / Parent SDD / Conflict procedure / Produces / Consumes are emitted
by `/to-subtasks` in **cited mode** (when an SDD accompanies the parent PRD).
Produces is emitted on every cited SubTask (the contract for downstream
consumers + reviewer). Consumes is emitted only when ``Blocked by`` is
non-empty (typed handoff from upstream Produces). Both are also valid in
uncited mode but typically absent there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

REQUIRED_HEADINGS: tuple[str, ...] = ("Goal", "Scope", "Acceptance", "Test command")
IMPL_NOTES_HEADING = "Implementation Notes (auto-maintained)"
DESIGN_REFS_HEADING = "Design refs"
PRODUCES_HEADING = "Produces"
CONSUMES_HEADING = "Consumes"
PARENT_SDD_HEADING = "Parent SDD"
CONFLICT_PROCEDURE_HEADING = "Conflict procedure"
KNOWN_HEADINGS: frozenset[str] = frozenset(
    (
        *REQUIRED_HEADINGS,
        DESIGN_REFS_HEADING,
        PRODUCES_HEADING,
        CONSUMES_HEADING,
        "Parent PRD",
        PARENT_SDD_HEADING,
        "Blocked by",
        CONFLICT_PROCEDURE_HEADING,
        IMPL_NOTES_HEADING,
    )
)

_H2_SPLIT = re.compile(r"(?m)^## (.+)$\n?")
_FENCED_BLOCK = re.compile(r"```[^\n]*\n(.*?)\n?```", re.DOTALL)


@dataclass(frozen=True)
class SubTaskTemplate:
    goal: str
    scope: tuple[str, ...]
    acceptance: tuple[str, ...]
    test_command: str
    design_refs: tuple[str, ...] = field(default_factory=tuple)
    produces: tuple[str, ...] = field(default_factory=tuple)
    consumes: tuple[str, ...] = field(default_factory=tuple)
    parent_prd: Optional[str] = None
    parent_sdd: Optional[str] = None
    blocked_by: Optional[str] = None
    conflict_procedure: Optional[str] = None
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
        design_refs=_parse_bullet_list(by_heading.get(DESIGN_REFS_HEADING)),
        produces=_parse_bullet_list(by_heading.get(PRODUCES_HEADING)),
        consumes=_parse_bullet_list(by_heading.get(CONSUMES_HEADING)),
        parent_prd=_strip_or_none(by_heading.get("Parent PRD")),
        parent_sdd=_strip_or_none(by_heading.get(PARENT_SDD_HEADING)),
        blocked_by=_strip_or_none(by_heading.get("Blocked by")),
        conflict_procedure=_strip_or_none(by_heading.get(CONFLICT_PROCEDURE_HEADING)),
        impl_notes_block=by_heading.get(IMPL_NOTES_HEADING, "").rstrip("\n"),
        extras=extras,
    )


def emit(t: SubTaskTemplate) -> str:
    out: list[str] = [f"## Goal\n{t.goal}\n"]
    if t.design_refs:
        out.append(
            f"## {DESIGN_REFS_HEADING}\n" + "".join(f"- {r}\n" for r in t.design_refs)
        )
    out.append("## Scope\n" + "".join(f"- {g}\n" for g in t.scope))
    out.append("## Acceptance\n" + "".join(f"{a}\n" for a in t.acceptance))
    if t.produces:
        out.append(
            f"## {PRODUCES_HEADING}\n" + "".join(f"- {p}\n" for p in t.produces)
        )
    out.append(f"## Test command\n```\n{t.test_command}\n```\n")
    if t.parent_prd is not None:
        out.append(f"## Parent PRD\n{t.parent_prd}\n")
    if t.parent_sdd is not None:
        out.append(f"## {PARENT_SDD_HEADING}\n{t.parent_sdd}\n")
    if t.blocked_by is not None:
        out.append(f"## Blocked by\n{t.blocked_by}\n")
    if t.consumes:
        out.append(
            f"## {CONSUMES_HEADING}\n" + "".join(f"- {c}\n" for c in t.consumes)
        )
    if t.conflict_procedure is not None:
        out.append(f"## {CONFLICT_PROCEDURE_HEADING}\n{t.conflict_procedure}\n")
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


def _parse_bullet_list(body: Optional[str]) -> tuple[str, ...]:
    if body is None:
        return ()
    out: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and not stripped.startswith("- ["):
            out.append(stripped[2:].strip())
    return tuple(out)


def _parse_fenced(body: str) -> str:
    m = _FENCED_BLOCK.search(body)
    if not m:
        raise ValueError(f"no fenced code block found in Test command body: {body!r}")
    return m.group(1).strip("\n")
