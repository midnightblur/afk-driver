"""Team — a read-only view of the feature's team run: each agent's role, model and state.

Source: `<main checkout>/.claude/afk-team/<spec folder name>/manifest.json` (plan D-128), read
through `scripts/team/manifest.py` `read_manifest`, the format's owner. A parked agent shows its
reason and its park-until time as the manifest holds it (UTC, ISO 8601), never a time relative to
now, so a re-render of the same manifest is byte-identical. The one-time render shows this section
Absent (`parse_snapshot`, plan D-129).
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..vm import KIND_LIVE, Absent, SectionVM

_PLUGIN_SCRIPTS = Path(__file__).resolve().parents[6] / "scripts"
if str(_PLUGIN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_SCRIPTS))
from team import manifest  # noqa: E402

SECTION_ID = "team"
SECTION_TITLE = "Team"
SNAPSHOT_REASON = ("a one-time render is a snapshot, and a team run's agents change after it; "
                   "launch watch mode to follow the run")

_AGENT_FIELDS = ("agent_id", "role", "model", "state", "stage", "pattern_step", "lifespan",
                 "pane_label", "agent_name", "transport_kind", "started_at", "park_reason", "park_until")


def main_checkout(spec_dir: Path):
    """The main checkout holding `spec_dir`, read from `.git` files with no git call; None outside one."""
    current = spec_dir.resolve()
    while True:
        dot_git = current / ".git"
        if dot_git.is_dir():
            return current
        if dot_git.is_file():
            return _main_of_worktree(dot_git)
        if current.parent == current:
            return None
        current = current.parent


def _main_of_worktree(dot_git: Path):
    try:
        line = dot_git.read_text(encoding="utf-8").strip()
        if not line.startswith("gitdir:"):
            return None
        gitdir = (dot_git.parent / line[len("gitdir:"):].strip()).resolve()
        commondir = gitdir / "commondir"
        common = (gitdir / commondir.read_text(encoding="utf-8").strip()).resolve() if commondir.is_file() else gitdir
    except (OSError, UnicodeDecodeError):
        return None
    return common.parent if common.name == ".git" else None


def _team_root(spec_dir: Path):
    main = main_checkout(spec_dir)
    return None if main is None else main / ".claude" / "afk-team"


def manifest_file(spec_dir: Path):
    """The manifest file watch mode also watches; None when no git checkout holds `spec_dir`."""
    root = _team_root(spec_dir)
    return None if root is None else root / spec_dir.name / "manifest.json"


def parse_team_section(spec_dir: Path):
    """The team section over the run manifest: SectionVM, or Absent naming why; never raises."""
    root = _team_root(spec_dir)
    if root is None:
        return Absent(SECTION_ID, "no git checkout holds the spec folder, so no team run can be found")
    try:
        data = manifest.read_manifest(root, spec_dir.name)
    except Exception as exc:  # RecursionError escapes ManifestError; one bad file degrades one section
        return Absent(SECTION_ID, f"the run manifest could not be read: {exc}")
    if data is None:
        return Absent(SECTION_ID, f"no team run for this feature: {root / spec_dir.name / 'manifest.json'} not found")

    agents = [{field: entry.get(field) or "" for field in _AGENT_FIELDS} for entry in data["agents"]]
    counts = {}
    for agent in agents:
        counts[agent["state"]] = counts.get(agent["state"], 0) + 1
    park_times = sorted(a["park_until"] for a in agents if a["state"] == "parked" and a["park_until"])
    return SectionVM(SECTION_ID, SECTION_TITLE, KIND_LIVE, {
        "feature": data["feature"],
        "owning_session": data["owning_session"],
        "owner_generation": data["owner_generation"],
        "states": list(manifest.STATES),
        "counts": counts,
        "earliest_park_until": park_times[0] if park_times else "",
        "agents": agents,
        "processes": [{"pid": p["pid"], "owner": p["owner"], "label": p["label"]} for p in data["processes"]],
    })


def parse_snapshot(spec_dir: Path):
    """The one-time render's team entry: Absent, with one line saying why."""
    return Absent(SECTION_ID, SNAPSHOT_REASON)
