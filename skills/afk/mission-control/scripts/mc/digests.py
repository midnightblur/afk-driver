"""Digest layer: load, structurally validate, and staleness-check the
LLM-authored design digests under `{spec_dir}/plan/digests/`.

Contract one-home: the skill's `DIGEST-FORMAT.md` (schemas, digestibility
instructions, manifest grammar, build protocol). This module is the *parsing*
half of that lockstep pair — a schema change there is a same-commit change
here.

The renderer never builds digests (explicit-build-only policy): a missing
digest renders a `missing` state, a hash-drifted one renders `stale` with the
drifted sources named, a malformed one renders `invalid`. All are values,
never exceptions, and never block the live layer.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .vm import (
    KIND_DIGEST,
    STATE_INVALID,
    STATE_MISSING,
    STATE_OK,
    STATE_STALE,
    SectionVM,
)

DIGESTS_SUBDIR = ("plan", "digests")
MANIFEST_NAME = "manifest.json"

# digest name -> (top-level required key, item-required string fields).
# Structural floor only — richness rules live in DIGEST-FORMAT.md; the shell
# tolerates optional fields being absent.
DIGEST_SPECS = {
    "architecture": ("modules", ("id", "name", "responsibility")),
    "flows": ("flows", ("id", "title", "kind")),
    "entities": ("entities", ("id", "name", "essence")),
    "adrs": ("adrs", ("id", "tier", "title", "essence")),
    "critical-logic": ("items", ("id", "kind", "title", "statement")),
    "legend": ("terms", ("term", "definition")),
}


def digests_dir(spec_dir: Path) -> Path:
    return spec_dir.joinpath(*DIGESTS_SUBDIR)


def _sha256(path: Path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _manifest_entry(spec_dir: Path, name: str):
    manifest = _load_json(digests_dir(spec_dir) / MANIFEST_NAME)
    if not isinstance(manifest, dict):
        return None
    entry = manifest.get(name)
    return entry if isinstance(entry, dict) else None


def _stale_sources(spec_dir: Path, entry: dict) -> list:
    """Manifest-listed sources whose current content hash no longer matches
    (or which disappeared). Paths are spec_dir-relative; anything resolving
    outside the spec folder counts as drifted rather than being followed
    (SDD §5: parsers never follow references outside the folder)."""
    stale = []
    sources = entry.get("sources") if isinstance(entry.get("sources"), list) else []
    for source in sources:
        if not isinstance(source, dict):
            continue
        rel = str(source.get("path", ""))
        recorded = str(source.get("sha256", ""))
        candidate = (spec_dir / rel).resolve()
        try:
            candidate.relative_to(spec_dir.resolve())
        except ValueError:
            stale.append(rel)
            continue
        if _sha256(candidate) != recorded:
            stale.append(rel)
    return stale


def _validate(name: str, payload) -> str:
    """'' when structurally sound, else a one-line reason."""
    top_key, item_fields = DIGEST_SPECS[name]
    if not isinstance(payload, dict):
        return "digest root is not a JSON object"
    items = payload.get(top_key)
    if not isinstance(items, list) or not items:
        return f"digest has no non-empty '{top_key}' array"
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            return f"'{top_key}[{index}]' is not an object"
        for fld in item_fields:
            value = item.get(fld)
            if not isinstance(value, str) or not value.strip():
                return f"'{top_key}[{index}]' missing required string field '{fld}'"
    return ""


def status(spec_dir: Path) -> dict:
    """Per-digest freshness map for `--check-digests` and the skill's build
    mode: {name: {state, reason, built_at, stale_sources}}."""
    report = {}
    for name in DIGEST_SPECS:
        vm = load(spec_dir, name, name, name)
        report[name] = {
            "state": vm.state,
            "reason": vm.reason,
            "built_at": vm.freshness.get("built_at", ""),
            "stale_sources": vm.freshness.get("stale_sources", []),
        }
    return report


def load(spec_dir: Path, name: str, section_id: str, title: str) -> SectionVM:
    """Digest file + manifest -> SectionVM with state ok|stale|missing|invalid.

    `stale` still carries the (old) data — the shell shows it behind an amber
    banner naming the drifted sources; honesty over blankness.
    """
    path = digests_dir(spec_dir) / f"{name}.json"
    if not path.is_file():
        return SectionVM(
            section_id, title, KIND_DIGEST, None, STATE_MISSING,
            f"plan/digests/{name}.json not built yet",
        )

    payload = _load_json(path)
    invalid_reason = _validate(name, payload) if payload is not None else "digest is not valid JSON"
    if invalid_reason:
        return SectionVM(
            section_id, title, KIND_DIGEST, None, STATE_INVALID,
            f"plan/digests/{name}.json: {invalid_reason}",
        )

    entry = _manifest_entry(spec_dir, name)
    if entry is None:
        return SectionVM(
            section_id, title, KIND_DIGEST, payload, STATE_STALE,
            f"no manifest entry for '{name}' — freshness unknown",
            {"built_at": "", "stale_sources": []},
        )

    stale_sources = _stale_sources(spec_dir, entry)
    built_at = str(entry.get("built_at", ""))
    freshness = {"built_at": built_at, "stale_sources": stale_sources}
    if stale_sources:
        return SectionVM(
            section_id, title, KIND_DIGEST, payload, STATE_STALE,
            "digest built from older sources: " + ", ".join(stale_sources),
            freshness,
        )
    return SectionVM(section_id, title, KIND_DIGEST, payload, STATE_OK, "", freshness)
