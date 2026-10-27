from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from glossary_lifecycle.domain import (
    AttestedTerm,
    AuditRecord,
    ConsultationRecord,
    FeatureVocabularyScope,
    Finding,
    FindingResolution,
    EditedRecordError,
    GlossaryRoute,
    GlossaryDomainRules,
    LedgerGapError,
    DuplicateOperationError,
    InvalidFindingResolutionError,
    MergeRequestRecord,
    SoloOwnerAttestation,
    SurfaceEntry,
    SurfaceInventory,
    ToolFailureOverride,
    MissingOwnerChainError,
    PublicationRecordCodecError,
    SelectedTerm,
    UnresolvedDomainAreaError,
    UnknownGlossaryTargetError,
    UnknownFindingResolutionError,
)


def record(
    sequence: int,
    operation_id: str,
    *,
    findings: tuple[Finding, ...] = (),
    resolutions: tuple[FindingResolution, ...] = (),
    outcome: str = "pass",
    recorded_digest: str | None = None,
) -> MergeRequestRecord:
    return MergeRequestRecord(
        sequence=sequence,
        operation_id=operation_id,
        head_sha="head-1",
        glossary_paths=("GLOSSARY.md",),
        term_ids=("payable.invoice",),
        findings=findings,
        resolutions=resolutions,
        outcome=outcome,
        author="author",
        auditors=("auditor",),
        consultation_fingerprint="consult",
        audit_fingerprint="audit",
        recorded_digest=recorded_digest,
    )


def test_consultation_fingerprint_is_canonical_and_input_sensitive() -> None:
    left = {
        "scope": {"declared_terms": ["invoice"], "exclusions": [], "areas": {"payable": "owned"}},
        "routed_paths": ["11700-payable/GLOSSARY.md"],
        "selected_terms": [SelectedTerm("payable.invoice", "Money owed.", "payable-team")],
        "owners": {"payable.invoice": ["payable-team"]},
        "routes": {"11700-payable/**": "11700-payable/GLOSSARY.md"},
        "mappings": {"payable": "11700-payable/GLOSSARY.md"},
        "target_state": {"ref": "abc123"},
        "semantic_evidence": {"method": "exact", "roots": ["11700-payable"]},
    }
    reordered = {
        **dict(reversed(list(left.items()))),
        "scope": {"areas": {"payable": "owned"}, "exclusions": [], "declared_terms": ["invoice"]},
    }

    assert GlossaryDomainRules.consultation_fingerprint(**left) == (
        GlossaryDomainRules.consultation_fingerprint(**reordered)
    )

    baseline = GlossaryDomainRules.consultation_fingerprint(**left)
    changes = {
        "scope": {"declared_terms": ["credit memo"]},
        "routed_paths": ["other/GLOSSARY.md"],
        "selected_terms": [SelectedTerm("payable.invoice", "Changed.", "payable-team")],
        "owners": {"payable.invoice": ["other-team"]},
        "routes": {"other/**": "other/GLOSSARY.md"},
        "mappings": {"payable": "other/GLOSSARY.md"},
        "target_state": {"ref": "def456"},
        "semantic_evidence": {"method": "semantic", "roots": ["11700-payable"]},
    }
    for field, changed_value in changes.items():
        assert GlossaryDomainRules.consultation_fingerprint(**{**left, field: changed_value}) != baseline


def test_confirmed_nonsemantic_definition_edit_keeps_consultation_fingerprint() -> None:
    common = {
        "scope": {},
        "routed_paths": (),
        "owners": {},
        "routes": {},
        "mappings": {},
        "target_state": {},
        "semantic_evidence": {},
    }
    original = SelectedTerm("term-1", "Money owed.", "owner")
    confirmed = SelectedTerm(
        "term-1",
        "**Money** owed. ",
        "owner",
        confirmed_semantic_definition="Money owed.",
    )
    unconfirmed = SelectedTerm("term-1", "**Money** owed. ", "owner")

    baseline = GlossaryDomainRules.consultation_fingerprint(selected_terms=(original,), **common)
    assert GlossaryDomainRules.consultation_fingerprint(selected_terms=(confirmed,), **common) == baseline
    assert GlossaryDomainRules.consultation_fingerprint(selected_terms=(unconfirmed,), **common) != baseline


def test_audit_fingerprint_binds_consultation_inventory_evidence_and_head() -> None:
    inputs = {
        "consultation_fingerprint": "consulted",
        "surface_inventory": [{"path": "service/api.py", "kind": "contract"}],
        "changed_vocabulary": ["invoice"],
        "semantic_evidence": {"method": "exact", "truncated": False},
        "head_sha": "abc123",
    }

    baseline = GlossaryDomainRules.audit_fingerprint(**inputs)
    assert baseline == GlossaryDomainRules.audit_fingerprint(**dict(reversed(list(inputs.items()))))
    for field in inputs:
        changed = {**inputs, field: f"changed-{field}"}
        assert GlossaryDomainRules.audit_fingerprint(**changed) != baseline


def test_re01_through_re08_have_provider_neutral_stable_values() -> None:
    scope = FeatureVocabularyScope("feature-1", ("invoice",), (), ("payable",), ("api",), ())
    inventory = SurfaceInventory("feature-1", (SurfaceEntry("service/api.py", "contract"),))
    consultation = ConsultationRecord("op-3", "feature-1", "fp-3", "head-1", ("payable.invoice",))
    finding = Finding("finding-1", "missing-term", "service/api.py:10", "payable.invoice", "owner", "add term")
    audit = AuditRecord("op-4", "feature-1", "fp-4", "fp-3", "head-1", (finding.id,))
    override = ToolFailureOverride("op-6", "semantic-search", "payable", "offline", "owner approved", "gate-2", "2099-01-01T00:00:00Z", "fp-3", "fp-4")
    attestation = SoloOwnerAttestation(
        "op-7",
        "owner",
        "owner",
        "lavish",
        "session-1",
        "2099-01-01T00:00:00Z",
        "Finalize payable.invoice?",
        "final",
        (AttestedTerm("payable.invoice", "hash-1"),),
        "fp-3",
        "fp-4",
        "head-1",
    )
    merge_record = record(1, "op-8", findings=(finding,), outcome="blocked")

    assert [value.record_type for value in (scope, inventory, consultation, audit, finding, override, attestation, merge_record)] == [
        "RE-01", "RE-02", "RE-03", "RE-04", "RE-05", "RE-06", "RE-07", "RE-08"
    ]


def test_replay_keeps_confirmed_findings_open_until_named_resolution() -> None:
    finding = Finding("finding-1", "missing-term", "api.py:10", "payable.invoice", "owner", "add term")
    first = record(1, "op-1", findings=(finding,), outcome="blocked")
    later_pass = record(2, "op-2")

    still_open = GlossaryDomainRules.replay((first, later_pass))
    assert still_open.open_findings == (finding,)

    resolution = FindingResolution("finding-1", "resolution-1", "term-change", "commit:abc", True)
    resolved = record(3, "op-3", resolutions=(resolution,))
    assert GlossaryDomainRules.replay((first, later_pass, resolved)).open_findings == ()


def test_replay_surfaces_sequence_gaps_and_edited_records_as_typed_errors() -> None:
    first = record(1, "op-1")
    third = record(3, "op-3")
    with pytest.raises(LedgerGapError, match="expected 2, got 3"):
        GlossaryDomainRules.replay((first, third))

    edited = record(1, "op-1", recorded_digest="wrong-digest")
    with pytest.raises(EditedRecordError, match="op-1"):
        GlossaryDomainRules.replay((edited,))


def test_routes_resolve_deterministically_and_only_to_mapped_glossaries() -> None:
    payable = GlossaryRoute("payable", ("11700-payable/**",), ("accounts-payable",), "11700-payable/GLOSSARY.md", ("payable-team",))
    shared = GlossaryRoute("shared", ("11999-common/**",), (), "11999-common/GLOSSARY.md", ("fin-core",))
    owners = {
        "11700-payable/GLOSSARY.md": "payable",
        "11999-common/GLOSSARY.md": "fin-core",
    }

    left = GlossaryDomainRules.resolve_routes(("11700-payable/api.py",), ("accounts-payable",), (shared, payable), owners)
    right = GlossaryDomainRules.resolve_routes(("11700-payable/api.py",), ("accounts-payable",), (payable, shared), owners)
    assert left == right
    assert left.glossary_paths == ("11700-payable/GLOSSARY.md",)
    assert left.owner_chains == (("payable-team",),)

    broken = GlossaryRoute("broken", ("11700-payable/**",), (), "missing/GLOSSARY.md", ("owner",))
    with pytest.raises(UnknownGlossaryTargetError, match="missing/GLOSSARY.md"):
        GlossaryDomainRules.resolve_routes(("11700-payable/api.py",), (), (broken,), owners)

    with pytest.raises(UnresolvedDomainAreaError, match="unrouted"):
        GlossaryDomainRules.resolve_routes((), ("unrouted",), (payable,), owners)

    unowned = GlossaryRoute("unowned", ("11700-payable/**",), (), "11700-payable/GLOSSARY.md", ())
    with pytest.raises(MissingOwnerChainError, match="unowned"):
        GlossaryDomainRules.resolve_routes(("11700-payable/api.py",), (), (unowned,), owners)


def test_gate_specification_orders_blockers_and_never_allows_override_at_ready() -> None:
    finding = Finding("finding-b", "drift", "api.py:2", "term-b", "owner", "fix")
    earlier = Finding("finding-a", "missing", "api.py:1", "term-a", "owner", "add")
    state = GlossaryDomainRules.replay(
        (record(1, "op-1", findings=(finding, earlier), outcome="blocked"),)
    )
    override = ToolFailureOverride(
        "op-6", "semantic-search", "payable", "offline", "owner approved", "ready", "2099-01-01T00:00:00Z", "consult", "audit"
    )

    result = GlossaryDomainRules.evaluate_gate(
        "ready", state, "consult", "audit", "consult", "audit", (override,), ("term-z",)
    )
    assert not result.allowed
    assert result.blockers == (
        "finding:finding-a",
        "finding:finding-b",
        "override:op-6",
    )

    settlement = GlossaryDomainRules.evaluate_gate(
        "settlement", GlossaryDomainRules.replay(()), "consult", "audit", "consult", "audit", (), ("term-z",)
    )
    assert settlement.blockers == ("provisional:term-z",)


@pytest.mark.parametrize(
    ("gate", "consultation", "audit", "overrides", "provisional", "expected"),
    [
        ("ready", "consult", "audit", (), ("term-z",), ()),
        ("ready", "stale", "audit", (), (), ("stale:consultation",)),
        ("ready", "consult", "stale", (), (), ("stale:audit",)),
        ("intermediate", "consult", "audit", ("override",), (), ()),
        ("settlement", "consult", "audit", (), ("term-z",), ("provisional:term-z",)),
    ],
)
def test_gate_admission_and_freshness(
    gate: str,
    consultation: str,
    audit: str,
    overrides: tuple[str, ...],
    provisional: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    active = (
        ToolFailureOverride(
            "op-6",
            "semantic-search",
            "payable",
            "offline",
            "owner approved",
            "next",
            "2099-01-01T00:00:00Z",
            "consult",
            "audit",
        ),
    ) if overrides else ()
    result = GlossaryDomainRules.evaluate_gate(
        gate,
        GlossaryDomainRules.replay(()),
        consultation,
        audit,
        "consult",
        "audit",
        active,
        provisional,
    )
    assert result.allowed is (not expected)
    assert result.blockers == expected


def test_replay_rejects_duplicate_operations_and_unknown_resolutions() -> None:
    first = record(1, "op-1")
    duplicate = record(2, "op-1")
    with pytest.raises(DuplicateOperationError, match="op-1"):
        GlossaryDomainRules.replay((first, duplicate))

    unknown = FindingResolution("missing", "resolution-1", "false-positive-dismissal", "evidence", True)
    second = record(2, "op-2", resolutions=(unknown,))
    with pytest.raises(UnknownFindingResolutionError, match="missing"):
        GlossaryDomainRules.replay((first, second))


@pytest.mark.parametrize(
    "resolution",
    [
        FindingResolution("finding-1", "", "term-change", "evidence", True),
        FindingResolution("finding-1", "resolution-1", "unsupported", "evidence", True),
        FindingResolution("finding-1", "resolution-1", "term-change", "", True),
        FindingResolution("finding-1", "resolution-1", "term-change", "evidence", False),
    ],
)
def test_replay_rejects_incomplete_finding_resolution(resolution: FindingResolution) -> None:
    finding = Finding("finding-1", "missing", "api.py:1", "term", "owner", "add term")
    with pytest.raises(InvalidFindingResolutionError, match="finding-1"):
        GlossaryDomainRules.replay(
            (record(1, "op-1", findings=(finding,)), record(2, "op-2", resolutions=(resolution,)))
        )


def test_publication_codec_is_versioned_closed_and_digest_verified() -> None:
    finding = Finding("finding-1", "missing", "api.py:1", "term", "owner", "add term")
    original = record(1, "op-1", findings=(finding,), outcome="blocked")
    payload = GlossaryDomainRules.encode_record(original)

    parsed = GlossaryDomainRules.decode_record(payload)
    assert parsed.recorded_digest == GlossaryDomainRules.record_digest(parsed)
    assert parsed.findings == (finding,)
    assert GlossaryDomainRules.replay((parsed,)).open_findings == (finding,)

    with pytest.raises(PublicationRecordCodecError, match="unknown"):
        GlossaryDomainRules.decode_record(payload.replace('"version":1', '"unknown":1,"version":1'))
    with pytest.raises(PublicationRecordCodecError, match="version"):
        GlossaryDomainRules.decode_record(payload.replace('"version":1', '"version":2'))
    with pytest.raises(EditedRecordError, match="op-1"):
        GlossaryDomainRules.decode_record(payload.replace('"outcome":"blocked"', '"outcome":"pass"'))


def test_publication_codec_rejects_digest_valid_non_boolean_closure_evidence() -> None:
    finding = Finding("finding-1", "missing", "api.py:1", "term", "owner", "add term")
    resolution = FindingResolution("finding-1", "resolution-1", "term-change", "commit:abc", True)
    envelope = json.loads(
        GlossaryDomainRules.encode_record(
            record(1, "op-1", findings=(finding,), resolutions=(resolution,))
        )
    )
    envelope["record"]["resolutions"][0]["closure_test_satisfied"] = "false"
    canonical_record = json.dumps(
        envelope["record"],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    envelope["digest"] = hashlib.sha256(canonical_record).hexdigest()
    payload = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    with pytest.raises(PublicationRecordCodecError, match="resolution.closure_test_satisfied"):
        GlossaryDomainRules.decode_record(payload)
