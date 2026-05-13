"""Driver config loader (~/.afk-driver/config.toml) with PRD-default fallback.

Also exposes the `[github]` and `[backend_select]` sub-sections consumed by
`backend_select.resolve` (SDD §3, §5 feature-flags table) and the per-repo
`.afk-driver.toml` merge entry point used by the runner when it enters a
cwd that ships repo-local overrides (SDD §4 state table row "Per-repo
overrides"). Unknown keys are ignored (forward-compat); missing keys fall
back to the built-in default — the same posture as the global file.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping, Optional


@dataclass(frozen=True)
class GithubConfig:
    """`[github]` config section consumed by `backend_select` (SDD §3 row
    "backend_select", §5 feature-flags table).

    * `mode` — `"cwd"` (auto-detect from `git remote get-url origin`) or
      `"all-repos"` (short-circuit cwd inspection and always return the
      GitHub backend; queue is discovered via `gh search issues` per
      ADR-0003).
    * `auto_clone_root` — when `mode == "all-repos"` the runner ensures each
      `owner/repo` from the queue is cloned under this directory. Empty
      string means "use `{worktree_root}/github`" (the default per SDD §4
      state table row "Cloned repos (GitHub)").
    * `default_target_branch_fallback` — list of branch names tried in
      order if a GitHub parent issue does not declare an explicit target
      branch. Empty string entries map to "the repo's default branch"
      (resolved lazily by the runner).
    """

    mode: str = "cwd"
    auto_clone_root: str = ""
    default_target_branch_fallback: tuple[str, ...] = ()


@dataclass(frozen=True)
class BackendSelectConfig:
    """`[backend_select]` config section — composition-root knobs (SDD §3
    auto-detect rule + §5 feature-flags table).

    * `force_backend` — when non-empty, overrides auto-detection. Must be
      one of `"github"`, `"jira"`, `"" `; anything else raises at resolve
      time.
    * `gitlab_host` — host substring that, when present in the cwd's
      `origin` URL, selects the Jira+GitLab backend. Defaults to the
      Nakisa internal host so the existing single-user setup keeps
      working with zero config.
    """

    force_backend: str = ""
    gitlab_host: str = "gitlab"


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
    # GitHub backend config + composition-root knobs (SDD §3 + §5). These
    # are defaulted at construction time (see ``defaults()``) so existing
    # callers that never touch GitHub keep working unchanged.
    github: GithubConfig = field(default_factory=GithubConfig)
    backend_select: BackendSelectConfig = field(default_factory=BackendSelectConfig)


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
        github=GithubConfig(),
        backend_select=BackendSelectConfig(),
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
    if "github" in data and isinstance(data["github"], Mapping):
        overrides["github"] = _merge_github(base.github, data["github"])
    if "backend_select" in data and isinstance(data["backend_select"], Mapping):
        overrides["backend_select"] = _merge_backend_select(
            base.backend_select, data["backend_select"]
        )
    return replace(base, **overrides)


def _merge_github(base: GithubConfig, data: Mapping) -> GithubConfig:
    """Merge a parsed `[github]` table onto a `GithubConfig` baseline.

    Unknown keys are silently ignored (forward-compat per SDD §4 state
    table row "Driver config"). Missing keys keep the baseline value, so
    repeated calls compose cleanly across global + per-repo files.
    """
    overrides: dict = {}
    if "mode" in data:
        overrides["mode"] = str(data["mode"])
    if "auto_clone_root" in data:
        overrides["auto_clone_root"] = str(data["auto_clone_root"])
    if "default_target_branch_fallback" in data:
        overrides["default_target_branch_fallback"] = tuple(
            str(x) for x in data["default_target_branch_fallback"]
        )
    return replace(base, **overrides)


def _merge_backend_select(
    base: BackendSelectConfig, data: Mapping
) -> BackendSelectConfig:
    """Merge a parsed `[backend_select]` table onto a `BackendSelectConfig`."""
    overrides: dict = {}
    if "force_backend" in data:
        overrides["force_backend"] = str(data["force_backend"])
    if "gitlab_host" in data:
        overrides["gitlab_host"] = str(data["gitlab_host"])
    return replace(base, **overrides)


def load_per_repo(repo_root: Path, base: DriverConfig) -> DriverConfig:
    """Merge `<repo_root>/.afk-driver.toml` over a base `DriverConfig`.

    Precedence chain (high → low): per-repo TOML > global TOML > built-in
    defaults. Per SDD §4 state table row "Per-repo overrides", unknown
    keys are silently ignored (forward-compat) and a missing file returns
    `base` unchanged — repos without per-repo overrides are the common
    case.

    The merge re-uses `_merge_from_toml` so the per-repo schema mirrors
    the global one exactly; this keeps documentation single-sourced and
    prevents the per-repo loader from drifting behind new global keys.
    """
    p = Path(repo_root) / ".afk-driver.toml"
    if not p.is_file():
        return base
    return _merge_from_toml(base, p)
