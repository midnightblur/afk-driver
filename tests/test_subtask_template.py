import pytest

from afk_driver.subtask_template import (
    CONFLICT_PROCEDURE_HEADING,
    CONSUMES_HEADING,
    DESIGN_REFS_HEADING,
    IMPL_NOTES_HEADING,
    PARENT_SDD_HEADING,
    PRODUCES_HEADING,
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
    assert t.parent_sdd is None
    assert t.blocked_by is None
    assert t.design_refs == ()
    assert t.produces == ()
    assert t.consumes == ()
    assert t.conflict_procedure is None
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


CITED = """## Goal
Implement TemplateRegistry.

## Design refs
- SDD: SDD.md#l7-modules — TemplateRegistry interface lives in §8 module table
- ADR: adr/0002-template-strategy-registry.md — registry-keyed Strategy

## Scope
- src/main/java/com/x/export/**
- src/test/java/com/x/export/**

## Acceptance
- [ ] one
- [ ] Implements the public interface in SDD §8 without modification
- [ ] Conforms to ADR-0002 (no silent pattern substitution)
- [ ] Tests pass via `mvn -pl 11700-payable test`

## Produces
- src/main/java/com/x/export/TemplateRegistry.java#class TemplateRegistry — registry-keyed Strategy lookup
- src/main/java/com/x/export/TemplateRegistry.java#register(format: String, strategy: ExportStrategy) — write API for downstream loaders

## Test command
```
mvn -pl 11700-payable test
```

## Parent PRD
11700-payable/src/main/resources/specs/2026r2/P2P-1234/PRD.md

## Parent SDD
11700-payable/src/main/resources/specs/2026r2/P2P-1234/SDD.md

## Blocked by
P2P-100

## Consumes
- P2P-100 src/main/java/com/x/export/ExportStrategy.java#interface ExportStrategy<E> — base abstraction must exist

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, exit with `design-conflict` status quoting the SDD
section + the conflict. Do NOT override silently. Route back to
`architect-grill` for a superseding ADR.

## Implementation Notes (auto-maintained)
"""


def test_round_trip_cited():
    t = parse(CITED)
    assert parse(emit(t)) == t


def test_cited_mode_design_refs_parsed():
    t = parse(CITED)
    assert len(t.design_refs) == 2
    assert t.design_refs[0].startswith("SDD: SDD.md#l7-modules")
    assert t.design_refs[1].startswith("ADR: adr/0002-")


def test_cited_mode_parent_sdd_parsed():
    t = parse(CITED)
    assert t.parent_sdd is not None
    assert t.parent_sdd.endswith("SDD.md")


def test_cited_mode_conflict_procedure_parsed():
    t = parse(CITED)
    assert t.conflict_procedure is not None
    assert "design-conflict" in t.conflict_procedure
    assert "architect-grill" in t.conflict_procedure


def test_design_refs_omitted_when_empty():
    t = parse(MINIMAL)
    assert DESIGN_REFS_HEADING not in emit(t)


def test_parent_sdd_omitted_when_none():
    t = parse(MINIMAL)
    assert PARENT_SDD_HEADING not in emit(t)


def test_conflict_procedure_omitted_when_none():
    t = parse(MINIMAL)
    assert CONFLICT_PROCEDURE_HEADING not in emit(t)


def test_produces_omitted_when_empty():
    t = parse(MINIMAL)
    assert PRODUCES_HEADING not in emit(t)


def test_consumes_omitted_when_empty():
    t = parse(MINIMAL)
    assert CONSUMES_HEADING not in emit(t)


def test_cited_mode_produces_parsed():
    t = parse(CITED)
    assert len(t.produces) == 2
    assert t.produces[0].startswith("src/main/java/com/x/export/TemplateRegistry.java#class TemplateRegistry")
    assert "register(format: String" in t.produces[1]


def test_cited_mode_consumes_parsed():
    t = parse(CITED)
    assert len(t.consumes) == 1
    assert t.consumes[0].startswith("P2P-100 ")
    assert "interface ExportStrategy<E>" in t.consumes[0]


def test_emit_canonical_ordering_cited():
    t = parse(CITED)
    out = emit(t)
    headings = [
        out.index("## Goal"),
        out.index(f"## {DESIGN_REFS_HEADING}"),
        out.index("## Scope"),
        out.index("## Acceptance"),
        out.index(f"## {PRODUCES_HEADING}"),
        out.index("## Test command"),
        out.index("## Parent PRD"),
        out.index(f"## {PARENT_SDD_HEADING}"),
        out.index("## Blocked by"),
        out.index(f"## {CONSUMES_HEADING}"),
        out.index(f"## {CONFLICT_PROCEDURE_HEADING}"),
        out.index(f"## {IMPL_NOTES_HEADING}"),
    ]
    assert headings == sorted(headings)


def test_produces_only_no_consumes_round_trips():
    """An independent SubTask (no Blocked by) emits Produces but no Consumes —
    the typed-output contract still applies even when nothing downstream
    consumes it yet (reviewer cheat-sheet)."""
    md = """## Goal
g

## Scope
- s

## Acceptance
- [ ] a

## Produces
- src/Foo.java#class Foo — entry point

## Test command
```
pytest
```
"""
    t = parse(md)
    assert t.produces == ("src/Foo.java#class Foo — entry point",)
    assert t.consumes == ()
    assert parse(emit(t)) == t


def test_design_refs_only_no_sdd_or_conflict():
    md = """## Goal
g

## Design refs
- ADR: adr/0001-foo.md — orphan ref

## Scope
- s

## Acceptance
- [ ] a

## Test command
```
pytest
```
"""
    t = parse(md)
    assert t.design_refs == ("ADR: adr/0001-foo.md — orphan ref",)
    assert t.parent_sdd is None
    assert t.conflict_procedure is None
    assert parse(emit(t)) == t
