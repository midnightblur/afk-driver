"""A recorded fake of the S1 config reader's rules, from `afkv2/scripts/afkv2_config.py` of `origin/feat/afkv2-s1` at ab931ae0.

S1 is not merged, so nothing imports from that branch. Plan-s4 0016 runs setup against the real reader.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePath

TRACKER_KINDS = ("jira", "github-issues")
OWNERSHIP_GRADES = ("own", "shared")


class Refusal(Exception):
    pass


def read_config(config_file: Path) -> dict:
    raw = json.loads(config_file.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise Refusal("config: the file must hold one JSON object")
    repo_root = config_file.parent.parent
    return {"spec_folder": _spec_folder(raw, repo_root), "tracker": _tracker(raw), "ownership": _ownership(raw)}


def _spec_folder(raw, repo_root):
    value = raw.get("spec_folder")
    if not isinstance(value, str) or not value.strip():
        raise Refusal("spec_folder: a non-empty folder path relative to the repository root is required")
    if PurePath(value).anchor or ".." in PurePath(value).parts:
        raise Refusal(f"spec_folder: {value!r} must stay inside the repository root")
    return str(repo_root / value)


def _tracker(raw):
    value = raw.get("tracker")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise Refusal("tracker: an object with a kind is required")
    if value.get("kind") not in TRACKER_KINDS:
        raise Refusal(f"tracker.kind: {value.get('kind')!r} is not accepted")
    return value


def _ownership(raw):
    value = raw.get("ownership")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise Refusal("ownership: an object with own and shared lists is required")
    for grade, globs in value.items():
        if grade not in OWNERSHIP_GRADES:
            raise Refusal(f"ownership.{grade}: not accepted")
        if not isinstance(globs, list) or not all(isinstance(g, str) and g.strip() for g in globs):
            raise Refusal(f"ownership.{grade}: a list of non-empty path globs is required")
    return value
