"""Pure values and rules for the glossary lifecycle."""

from __future__ import annotations

import hashlib
import json
from fnmatch import fnmatchcase
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any, ClassVar


class GlossaryDomainError(ValueError):
    """Base class for invalid lifecycle state."""


class LedgerGapError(GlossaryDomainError):
    """A publication sequence has an interior gap."""


class EditedRecordError(GlossaryDomainError):
    """A publication record does not match its recorded digest."""


class UnknownGlossaryTargetError(GlossaryDomainError):
    """A delivery route points outside the glossary ownership map."""


class DuplicateOperationError(GlossaryDomainError):
    """One publication operation appears more than once."""


class UnknownFindingResolutionError(GlossaryDomainError):
    """A resolution names no earlier confirmed finding."""


class InvalidFindingResolutionError(GlossaryDomainError):
    """A finding resolution lacks accepted closure evidence."""


class UnresolvedDomainAreaError(GlossaryDomainError):
    """A declared domain area has no delivery route."""


class MissingOwnerChainError(GlossaryDomainError):
    """A selected delivery route has no human owner chain."""


class PublicationRecordCodecError(GlossaryDomainError):
    """A publication record does not match the closed codec."""


@dataclass(frozen=True, slots=True)
class FeatureVocabularyScope:
    record_type: ClassVar[str] = "RE-01"
    feature_id: str
    declared_terms: tuple[str, ...]
    inherited_terms: tuple[str, ...]
    routed_glossaries: tuple[str, ...]
    changed_surfaces: tuple[str, ...]
    exclusions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SurfaceEntry:
    path: str
    kind: str


@dataclass(frozen=True, slots=True)
class SurfaceInventory:
    record_type: ClassVar[str] = "RE-02"
    feature_id: str
    entries: tuple[SurfaceEntry, ...]


@dataclass(frozen=True, slots=True)
class ConsultationRecord:
    record_type: ClassVar[str] = "RE-03"
    operation_id: str
    feature_id: str
    fingerprint: str
    head_sha: str
    selected_term_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SelectedTerm:
    id: str
    definition: str
    owner: str
    aliases: tuple[str, ...] = ()
    replaces: tuple[str, ...] = ()
    confirmed_semantic_definition: str | None = None


@dataclass(frozen=True, slots=True)
class AuditRecord:
    record_type: ClassVar[str] = "RE-04"
    operation_id: str
    feature_id: str
    fingerprint: str
    consultation_fingerprint: str
    head_sha: str
    finding_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Finding:
    record_type: ClassVar[str] = "RE-05"
    id: str
    finding_class: str
    evidence: str
    affected: str
    owner: str
    closure_test: str
    status: str = "confirmed"
    resolution_id: str | None = None


@dataclass(frozen=True, slots=True)
class FindingResolution:
    finding_id: str
    resolution_id: str
    kind: str
    evidence: str
    closure_test_satisfied: bool


@dataclass(frozen=True, slots=True)
class ToolFailureOverride:
    record_type: ClassVar[str] = "RE-06"
    operation_id: str
    failed_check: str
    scope: str
    reason: str
    owner_act: str
    expiry_gate: str
    utc_expiry: str
    consultation_fingerprint: str
    audit_fingerprint: str


@dataclass(frozen=True, slots=True)
class SoloOwnerAttestation:
    record_type: ClassVar[str] = "RE-07"
    operation_id: str
    decision_maker: str
    publisher: str
    harness: str
    session_id: str
    utc_timestamp: str
    prompt: str
    answer: str
    terms: tuple["AttestedTerm", ...]
    consultation_fingerprint: str
    audit_fingerprint: str
    head_sha: str


@dataclass(frozen=True, slots=True)
class AttestedTerm:
    id: str
    definition_hash: str


@dataclass(frozen=True, slots=True)
class MergeRequestRecord:
    record_type: ClassVar[str] = "RE-08"
    sequence: int
    operation_id: str
    head_sha: str
    glossary_paths: tuple[str, ...]
    term_ids: tuple[str, ...]
    findings: tuple[Finding, ...]
    resolutions: tuple[FindingResolution, ...]
    outcome: str
    author: str
    auditors: tuple[str, ...]
    consultation_fingerprint: str
    audit_fingerprint: str
    recorded_digest: str | None = None


@dataclass(frozen=True, slots=True)
class ReplayState:
    highest_sequence: int
    open_findings: tuple[Finding, ...]


@dataclass(frozen=True, slots=True)
class GlossaryRoute:
    id: str
    path_patterns: tuple[str, ...]
    domain_areas: tuple[str, ...]
    glossary_path: str
    owner_chain: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RouteSelection:
    route_ids: tuple[str, ...]
    glossary_paths: tuple[str, ...]
    owner_chains: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class GateResult:
    allowed: bool
    blockers: tuple[str, ...]


def _canonical(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _canonical(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items(), key=lambda row: str(row[0]))}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonical(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(f"unsupported fingerprint value: {type(value).__name__}")


def _digest(value: Any) -> str:
    payload = json.dumps(_canonical(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GlossaryDomainRules:
    """Stable public entry point for pure glossary lifecycle operations."""

    @staticmethod
    def consultation_fingerprint(
        *,
        scope: Any,
        routed_paths: Any,
        selected_terms: Any,
        owners: Any,
        routes: Any,
        mappings: Any,
        target_state: Any,
        semantic_evidence: Any,
    ) -> str:
        return _digest(
            {
                "scope": scope,
                "routed_paths": routed_paths,
                "selected_terms": GlossaryDomainRules._consultation_terms(selected_terms),
                "owners": owners,
                "routes": routes,
                "mappings": mappings,
                "target_state": target_state,
                "semantic_evidence": semantic_evidence,
            }
        )

    @staticmethod
    def _consultation_terms(selected_terms: Any) -> Any:
        if not isinstance(selected_terms, Sequence) or isinstance(selected_terms, (str, bytes, bytearray)):
            return selected_terms
        projected: list[Any] = []
        for term in selected_terms:
            if isinstance(term, SelectedTerm):
                projected.append(
                    {
                        "id": term.id,
                        "definition": term.confirmed_semantic_definition or term.definition,
                        "owner": term.owner,
                        "aliases": term.aliases,
                        "replaces": term.replaces,
                    }
                )
            else:
                projected.append(term)
        return projected

    @staticmethod
    def audit_fingerprint(
        *,
        consultation_fingerprint: str,
        surface_inventory: Any,
        changed_vocabulary: Any,
        semantic_evidence: Any,
        head_sha: str,
    ) -> str:
        return _digest(
            {
                "consultation_fingerprint": consultation_fingerprint,
                "surface_inventory": surface_inventory,
                "changed_vocabulary": changed_vocabulary,
                "semantic_evidence": semantic_evidence,
                "head_sha": head_sha,
            }
        )

    @staticmethod
    def replay(records: Sequence[MergeRequestRecord]) -> ReplayState:
        open_findings: dict[str, Finding] = {}
        known_findings: set[str] = set()
        operation_ids: set[str] = set()
        expected_sequence = 1
        for record in records:
            if record.sequence != expected_sequence:
                raise LedgerGapError(f"publication sequence gap: expected {expected_sequence}, got {record.sequence}")
            if record.recorded_digest is not None and record.recorded_digest != GlossaryDomainRules.record_digest(record):
                raise EditedRecordError(f"publication record {record.operation_id} does not match its digest")
            if record.operation_id in operation_ids:
                raise DuplicateOperationError(f"duplicate publication operation: {record.operation_id}")
            operation_ids.add(record.operation_id)
            expected_sequence += 1
            for finding in record.findings:
                if finding.status == "confirmed":
                    known_findings.add(finding.id)
                    open_findings[finding.id] = finding
            for resolution in record.resolutions:
                if resolution.finding_id not in known_findings:
                    raise UnknownFindingResolutionError(
                        f"resolution {resolution.resolution_id} names unknown finding {resolution.finding_id}"
                    )
                GlossaryDomainRules._validate_resolution(resolution)
                open_findings.pop(resolution.finding_id, None)
        return ReplayState(expected_sequence - 1, tuple(open_findings.values()))

    @staticmethod
    def _validate_resolution(resolution: FindingResolution) -> None:
        allowed = {
            "term-change",
            "work-change",
            "ownership-route-correction",
            "false-positive-dismissal",
        }
        if (
            not resolution.resolution_id.strip()
            or resolution.kind not in allowed
            or not resolution.evidence.strip()
            or resolution.closure_test_satisfied is not True
        ):
            raise InvalidFindingResolutionError(
                f"resolution for {resolution.finding_id} does not satisfy the closure contract"
            )

    @staticmethod
    def record_digest(record: MergeRequestRecord) -> str:
        fields = asdict(record)
        fields.pop("recorded_digest", None)
        return _digest(fields)

    @staticmethod
    def encode_record(record: MergeRequestRecord) -> str:
        fields = asdict(record)
        fields.pop("recorded_digest", None)
        envelope = {
            "version": 1,
            "record": fields,
            "digest": GlossaryDomainRules.record_digest(record),
        }
        return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def decode_record(payload: str) -> MergeRequestRecord:
        try:
            envelope = json.loads(payload)
        except (json.JSONDecodeError, TypeError) as problem:
            raise PublicationRecordCodecError("publication record is not valid JSON") from problem
        GlossaryDomainRules._expect_keys(envelope, {"version", "record", "digest"}, "envelope")
        GlossaryDomainRules._expect_type(envelope["version"], int, "version")
        GlossaryDomainRules._expect_type(envelope["digest"], str, "digest")
        if envelope["version"] != 1:
            raise PublicationRecordCodecError(
                f"unsupported publication record version: {envelope['version']}"
            )
        values = envelope["record"]
        GlossaryDomainRules._expect_keys(
            values,
            {
                "sequence",
                "operation_id",
                "head_sha",
                "glossary_paths",
                "term_ids",
                "findings",
                "resolutions",
                "outcome",
                "author",
                "auditors",
                "consultation_fingerprint",
                "audit_fingerprint",
            },
            "record",
        )
        GlossaryDomainRules._expect_type(values["sequence"], int, "record.sequence")
        for field in (
            "operation_id",
            "head_sha",
            "outcome",
            "author",
            "consultation_fingerprint",
            "audit_fingerprint",
        ):
            GlossaryDomainRules._expect_type(values[field], str, f"record.{field}")
        for field in ("glossary_paths", "term_ids", "auditors"):
            GlossaryDomainRules._expect_string_list(values[field], f"record.{field}")
        GlossaryDomainRules._expect_type(values["findings"], list, "record.findings")
        GlossaryDomainRules._expect_type(values["resolutions"], list, "record.resolutions")
        findings: list[Finding] = []
        for item in values["findings"]:
            GlossaryDomainRules._expect_keys(
                item,
                {
                    "id",
                    "finding_class",
                    "evidence",
                    "affected",
                    "owner",
                    "closure_test",
                    "status",
                    "resolution_id",
                },
                "finding",
            )
            for field in (
                "id",
                "finding_class",
                "evidence",
                "affected",
                "owner",
                "closure_test",
                "status",
            ):
                GlossaryDomainRules._expect_type(item[field], str, f"finding.{field}")
            if item["resolution_id"] is not None:
                GlossaryDomainRules._expect_type(item["resolution_id"], str, "finding.resolution_id")
            findings.append(Finding(**item))
        resolutions: list[FindingResolution] = []
        for item in values["resolutions"]:
            GlossaryDomainRules._expect_keys(
                item,
                {"finding_id", "resolution_id", "kind", "evidence", "closure_test_satisfied"},
                "resolution",
            )
            for field in ("finding_id", "resolution_id", "kind", "evidence"):
                GlossaryDomainRules._expect_type(item[field], str, f"resolution.{field}")
            GlossaryDomainRules._expect_type(
                item["closure_test_satisfied"], bool, "resolution.closure_test_satisfied"
            )
            resolutions.append(FindingResolution(**item))
        record = MergeRequestRecord(
            sequence=values["sequence"],
            operation_id=values["operation_id"],
            head_sha=values["head_sha"],
            glossary_paths=tuple(values["glossary_paths"]),
            term_ids=tuple(values["term_ids"]),
            findings=tuple(findings),
            resolutions=tuple(resolutions),
            outcome=values["outcome"],
            author=values["author"],
            auditors=tuple(values["auditors"]),
            consultation_fingerprint=values["consultation_fingerprint"],
            audit_fingerprint=values["audit_fingerprint"],
            recorded_digest=envelope["digest"],
        )
        if record.recorded_digest != GlossaryDomainRules.record_digest(record):
            raise EditedRecordError(f"publication record {record.operation_id} does not match its digest")
        return record

    @staticmethod
    def _expect_keys(value: Any, expected: set[str], label: str) -> None:
        if not isinstance(value, dict):
            raise PublicationRecordCodecError(f"publication {label} must be an object")
        actual = set(value)
        if actual != expected:
            missing = sorted(expected - actual)
            unknown = sorted(actual - expected)
            raise PublicationRecordCodecError(
                f"publication {label} fields differ: missing={missing}, unknown={unknown}"
            )

    @staticmethod
    def _expect_type(value: Any, expected: type, label: str) -> None:
        if type(value) is not expected:
            raise PublicationRecordCodecError(
                f"publication {label} must be {expected.__name__}"
            )

    @staticmethod
    def _expect_string_list(value: Any, label: str) -> None:
        GlossaryDomainRules._expect_type(value, list, label)
        if any(type(item) is not str for item in value):
            raise PublicationRecordCodecError(f"publication {label} must contain strings")

    @staticmethod
    def resolve_routes(
        changed_paths: Sequence[str],
        domain_areas: Sequence[str],
        routes: Sequence[GlossaryRoute],
        glossary_owners: Mapping[str, str],
    ) -> RouteSelection:
        areas = set(domain_areas)
        matched_areas: set[str] = set()
        matched: list[GlossaryRoute] = []
        for route in sorted(routes, key=lambda item: item.id):
            path_match = any(
                fnmatchcase(path.replace("\\", "/"), pattern)
                for path in changed_paths
                for pattern in route.path_patterns
            )
            route_areas = areas.intersection(route.domain_areas)
            if not path_match and not route_areas:
                continue
            if route.glossary_path not in glossary_owners:
                raise UnknownGlossaryTargetError(
                    f"route {route.id} targets unmapped glossary {route.glossary_path}"
                )
            if not route.owner_chain:
                raise MissingOwnerChainError(f"route {route.id} has no owner chain")
            matched_areas.update(route_areas)
            matched.append(route)
        unresolved = sorted(areas - matched_areas)
        if unresolved:
            raise UnresolvedDomainAreaError(
                "unresolved domain areas: " + ", ".join(unresolved)
            )
        return RouteSelection(
            tuple(route.id for route in matched),
            tuple(dict.fromkeys(route.glossary_path for route in matched)),
            tuple(route.owner_chain for route in matched),
        )

    @staticmethod
    def evaluate_gate(
        gate: str,
        replay_state: ReplayState,
        consultation_fingerprint: str,
        audit_fingerprint: str,
        required_consultation_fingerprint: str,
        required_audit_fingerprint: str,
        active_overrides: Sequence[ToolFailureOverride] = (),
        provisional_term_ids: Sequence[str] = (),
    ) -> GateResult:
        if gate not in {"intermediate", "ready", "settlement"}:
            raise GlossaryDomainError(f"unknown glossary gate: {gate}")
        blockers: list[str] = []
        if consultation_fingerprint != required_consultation_fingerprint:
            blockers.append("stale:consultation")
        if audit_fingerprint != required_audit_fingerprint:
            blockers.append("stale:audit")
        blockers.extend(f"finding:{finding.id}" for finding in sorted(replay_state.open_findings, key=lambda item: item.id))
        if gate in {"ready", "settlement"}:
            blockers.extend(f"override:{override.operation_id}" for override in sorted(active_overrides, key=lambda item: item.operation_id))
        if gate == "settlement":
            blockers.extend(f"provisional:{term_id}" for term_id in sorted(set(provisional_term_ids)))
        return GateResult(not blockers, tuple(blockers))
