"""Driver config loader (~/.afk-driver/config.toml) with PRD-default fallback."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Optional


@dataclass(frozen=True)
class DriverConfig:
    project_service_map: Mapping[str, str]
    target_branch_field: str
    target_branch_value_map: Mapping[str, str]
    forbidden_patterns: tuple[str, ...]
    marker_template: str
    wall_clock_cap_seconds: int
    retry_count: int
    worktree_root: Path
    log_root: Path
    digest_root: Path
    # Custom-field IDs and default payloads required by the Jira workflow validator
    # when transitioning a SubTask from Dev-Developing to Dev-CR/Merge. The runner
    # populates these via jira_edit before calling jira_transition. The "merge_request_link"
    # value is computed at runtime from the open MR; everything else uses the default
    # below unless the user overrides via config.toml.
    dev_cr_merge_gate_fields: Mapping[str, str]
    dev_cr_merge_gate_defaults: Mapping[str, object]
    # GitLab username to assign new Draft MRs to. Empty string disables
    # auto-assignment. Default targets the user who owns this driver; override
    # via config.toml when running for someone else.
    mr_assignee: str
    # Single-select "A+ Clarity" custom field on the parent ticket. If empty
    # at runtime, the runner sets it to the configured option (default = green
    # 🟢). Field id and option id come from a Jira admin schema query — change
    # only if the workflow gets reconfigured.
    aplus_clarity_field: str
    aplus_clarity_green_option_id: str


_DEFAULT_FORBIDDEN: tuple[str, ...] = (
    "**/UpgradeGroup*.java",
    "**/PreDbMigration*",
    "**/db/changelog/**",
    "**/changeset*.xml",
)

_DEFAULT_GATE_FIELDS: Mapping[str, str] = {
    "merge_request_link": "customfield_12700",
    "sred_eligibility": "customfield_14005",
    "time_estimation": "customfield_14006",
    "sred_rationale": "customfield_14003",
}

_DEFAULT_GATE_DEFAULTS: Mapping[str, object] = {
    "sred_eligibility": {
        "value": "SRED not eligible",
        "child": {"value": "Straightforward Implementation"},
    },
    "time_estimation": {"value": "Low: 10 and < 80 hours"},
    # Rationale field is a rich-text customfield — Jira validates it as ADF.
    # The runner wraps plain strings into a single-paragraph ADF doc before
    # sending, so this default stays human-readable in config.toml.
    "sred_rationale": ".",
}


def defaults() -> DriverConfig:
    afk_root = Path.home() / ".afk-driver"
    return DriverConfig(
        project_service_map={"P2P": "11700-payable"},
        target_branch_field="customfield_13706",
        target_branch_value_map={"MASTER": "master"},
        forbidden_patterns=_DEFAULT_FORBIDDEN,
        marker_template="{SUBTASK-KEY} {summary}",
        wall_clock_cap_seconds=3600,
        retry_count=3,
        # Worktrees live next to the user's main checkout (~/core-services-worktrees)
        # rather than buried under ~/.afk-driver/, so they're easy to navigate to
        # in a file manager / IDE while AFK is running.
        worktree_root=Path.home() / "core-services-worktrees",
        log_root=afk_root / "logs",
        digest_root=afk_root / "digests",
        dev_cr_merge_gate_fields=dict(_DEFAULT_GATE_FIELDS),
        dev_cr_merge_gate_defaults=dict(_DEFAULT_GATE_DEFAULTS),
        mr_assignee="minh.vu.nakisa",
        aplus_clarity_field="customfield_13894",
        aplus_clarity_green_option_id="13737",
    )


def load(path: Optional[Path] = None) -> DriverConfig:
    base = defaults()
    if path is None:
        user_path = Path.home() / ".afk-driver" / "config.toml"
        if not user_path.is_file():
            return base
        return _merge_from_toml(base, user_path)
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    return _merge_from_toml(base, p)


def _merge_from_toml(base: DriverConfig, path: Path) -> DriverConfig:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    overrides: dict = {}
    if "project_service_map" in data:
        overrides["project_service_map"] = dict(data["project_service_map"])
    if "target_branch_field" in data:
        overrides["target_branch_field"] = str(data["target_branch_field"])
    if "target_branch_value_map" in data:
        overrides["target_branch_value_map"] = dict(data["target_branch_value_map"])
    if "forbidden_patterns" in data:
        overrides["forbidden_patterns"] = tuple(data["forbidden_patterns"])
    if "marker_template" in data:
        overrides["marker_template"] = str(data["marker_template"])
    if "wall_clock_cap_seconds" in data:
        overrides["wall_clock_cap_seconds"] = int(data["wall_clock_cap_seconds"])
    if "retry_count" in data:
        overrides["retry_count"] = int(data["retry_count"])
    if "worktree_root" in data:
        overrides["worktree_root"] = Path(data["worktree_root"]).expanduser()
    if "log_root" in data:
        overrides["log_root"] = Path(data["log_root"]).expanduser()
    if "digest_root" in data:
        overrides["digest_root"] = Path(data["digest_root"]).expanduser()
    if "dev_cr_merge_gate_fields" in data:
        overrides["dev_cr_merge_gate_fields"] = {
            **base.dev_cr_merge_gate_fields,
            **dict(data["dev_cr_merge_gate_fields"]),
        }
    if "mr_assignee" in data:
        overrides["mr_assignee"] = str(data["mr_assignee"])
    if "dev_cr_merge_gate_defaults" in data:
        overrides["dev_cr_merge_gate_defaults"] = {
            **base.dev_cr_merge_gate_defaults,
            **dict(data["dev_cr_merge_gate_defaults"]),
        }
    if "aplus_clarity_field" in data:
        overrides["aplus_clarity_field"] = str(data["aplus_clarity_field"])
    if "aplus_clarity_green_option_id" in data:
        overrides["aplus_clarity_green_option_id"] = str(data["aplus_clarity_green_option_id"])
    return replace(base, **overrides)
