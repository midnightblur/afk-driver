import pytest

from afk_driver.subtask_template import (
    IMPL_NOTES_HEADING,
    SubTaskTemplate,
    emit,
    parse,
)


MINIMAL = """## Goal
Do the thing.

## Scope
- src/**

## Acceptance
- [ ] item one

## Test command
```
pytest
```
"""

FULL = """## Goal
Implement X.

## Scope
- a/**
- b/c.py

## Acceptance
- [ ] one
- [x] two

## Test command
```
pytest tests/
```

## Parent PRD
tasks/foo.md

## Blocked by
None.

## Implementation Notes (auto-maintained)
- prior bullet
"""


def test_parse_minimal_fields():
    t = parse(MINIMAL)
    assert t.goal == "Do the thing."
    assert t.scope == ("src/**",)
    assert t.acceptance == ("- [ ] item one",)
    assert t.test_command == "pytest"
    assert t.parent_prd is None
    assert t.blocked_by is None
    assert t.impl_notes_block == ""
    assert t.extras == ()


def test_round_trip_minimal():
    t = parse(MINIMAL)
    assert parse(emit(t)) == t


def test_round_trip_full():
    t = parse(FULL)
    assert parse(emit(t)) == t
    assert t.parent_prd == "tasks/foo.md"
    assert t.blocked_by == "None."
    assert "prior bullet" in t.impl_notes_block
    assert t.acceptance == ("- [ ] one", "- [x] two")


def test_missing_goal_raises():
    md = MINIMAL.replace("## Goal\nDo the thing.\n\n", "")
    with pytest.raises(ValueError, match="missing required"):
        parse(md)


def test_missing_scope_raises():
    md = MINIMAL.replace("## Scope\n- src/**\n\n", "")
    with pytest.raises(ValueError, match="missing required"):
        parse(md)


def test_missing_acceptance_raises():
    md = MINIMAL.replace("## Acceptance\n- [ ] item one\n\n", "")
    with pytest.raises(ValueError, match="missing required"):
        parse(md)


def test_missing_test_command_raises():
    md = MINIMAL.split("## Test command")[0]
    with pytest.raises(ValueError, match="missing required"):
        parse(md)


def test_no_h2_raises():
    with pytest.raises(ValueError, match="no H2"):
        parse("plain text without any heading\n")


def test_leading_content_before_first_h2_raises():
    md = "preamble text\n\n" + MINIMAL
    with pytest.raises(ValueError, match="before first H2"):
        parse(md)


def test_duplicate_heading_raises():
    md = MINIMAL + "\n## Goal\nsecond goal\n"
    with pytest.raises(ValueError, match="duplicate"):
        parse(md)


def test_extras_section_round_trips():
    md = MINIMAL + "\n## Notes\nsome free-form context\n"
    t = parse(md)
    assert len(t.extras) == 1
    assert t.extras[0][0] == "Notes"
    assert "free-form context" in t.extras[0][1]
    assert parse(emit(t)) == t


def test_impl_notes_block_preserved_round_trip():
    md = MINIMAL + f"\n## {IMPL_NOTES_HEADING}\n- existing bullet from prior run\n"
    t = parse(md)
    assert "existing bullet" in t.impl_notes_block
    assert parse(emit(t)) == t


def test_test_command_missing_fenced_block_raises():
    md = """## Goal
g

## Scope
- s

## Acceptance
- [ ] a

## Test command
just plain text, no fence
"""
    with pytest.raises(ValueError, match="no fenced"):
        parse(md)


def test_emit_canonical_ordering():
    t = SubTaskTemplate(
        goal="g",
        scope=("a/**",),
        acceptance=("- [ ] a",),
        test_command="pytest",
        parent_prd="prd.md",
        blocked_by="None",
        impl_notes_block="",
        extras=(("Notes", "x\n"),),
    )
    out = emit(t)
    headings = [
        out.index("## Goal"),
        out.index("## Scope"),
        out.index("## Acceptance"),
        out.index("## Test command"),
        out.index("## Parent PRD"),
        out.index("## Blocked by"),
        out.index("## Notes"),
        out.index(f"## {IMPL_NOTES_HEADING}"),
    ]
    assert headings == sorted(headings)
