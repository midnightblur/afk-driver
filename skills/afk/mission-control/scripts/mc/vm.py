"""Section view-model contract (ADR-0007, extended by the two-layer rebuild):
parse(spec_dir) -> SectionVM | Absent.

A missing or unparseable source is a *value*, never an exception, so one
drifted artifact format degrades exactly one section while the rest still
render. SectionVM carries JSON-serializable *data*, not HTML — the shell
asset renders data -> DOM client-side; parsing stays here, tested.
"""
from __future__ import annotations

from dataclasses import dataclass, field

KIND_LIVE = "live"
KIND_DIGEST = "digest"

# Section states surfaced to the shell (freshness dot + banners):
#   ok      — parsed / digest fresh
#   stale   — digest present but a manifest source hash no longer matches
#   missing — digest never built
#   invalid — digest file present but fails the structural schema
#   absent  — live source artifact missing/unparseable (legacy Absent card)
STATE_OK = "ok"
STATE_STALE = "stale"
STATE_MISSING = "missing"
STATE_INVALID = "invalid"
STATE_ABSENT = "absent"


@dataclass(frozen=True)
class SectionVM:
    """One dashboard section, ready to be embedded into `window.MC_DATA`.

    `data` must be JSON-serializable (dict/list/str/num/bool/None) and free
    of wall-clock values — the page must stay a pure function of the source
    artifacts (requirement ADR-0005; idempotent re-render, SDD §5).
    """

    section_id: str
    title: str
    kind: str  # KIND_LIVE | KIND_DIGEST
    data: object = None
    state: str = STATE_OK
    reason: str = ""
    freshness: dict = field(default_factory=dict)  # digest: built_at, stale_sources

    def to_json(self) -> dict:
        return {
            "id": self.section_id,
            "title": self.title,
            "kind": self.kind,
            "state": self.state,
            "reason": self.reason,
            "freshness": self.freshness,
            "data": self.data,
        }


@dataclass(frozen=True)
class Absent:
    """A live section whose source artifact is missing or unparseable.

    Never raised as an exception — always returned as a value so the shell
    renders an explicit empty-state (AC-010).
    """

    section_id: str
    reason: str


def absent_json(section_id: str, title: str, kind: str, reason: str) -> dict:
    return SectionVM(section_id, title, kind, None, STATE_ABSENT, reason).to_json()
