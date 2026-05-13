from pathlib import Path

import pytest

from afk_driver.config import (
    BackendSelectConfig,
    DriverConfig,
    GithubConfig,
    defaults,
    load,
    load_per_repo,
)


def test_defaults_match_prd():
    d = defaults()
    assert d.project_service_map == {"P2P": "11700-payable"}
    assert d.target_branch_field == "customfield_13706"
    assert d.target_branch_value_map == {"MASTER": "master"}
    assert d.marker_template == "{SUBTASK-KEY} {summary}"
    assert d.wall_clock_cap_seconds == 3600
    assert d.retry_count == 3
    assert "**/UpgradeGroup*.java" in d.forbidden_patterns
    assert "**/PreDbMigration*" in d.forbidden_patterns
    assert "**/db/changelog/**" in d.forbidden_patterns
    assert d.worktree_root.name == "core-services-worktrees"
    assert d.worktree_root.parent == Path.home()
    assert d.log_root.name == "logs"
    assert d.digest_root.name == "digests"


def test_load_partial_overrides_defaults(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("wall_clock_cap_seconds = 600\nretry_count = 1\n", encoding="utf-8")
    d = load(cfg)
    assert d.wall_clock_cap_seconds == 600
    assert d.retry_count == 1
    # untouched fields keep defaults
    assert d.target_branch_field == "customfield_13706"
    assert d.project_service_map == {"P2P": "11700-payable"}
    assert d.marker_template == "{SUBTASK-KEY} {summary}"


def test_load_target_branch_value_map_override(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[target_branch_value_map]\n'
        'MASTER = "main"\n'
        'FINCORE_RELEASE = "fin-core/release"\n',
        encoding="utf-8",
    )
    d = load(cfg)
    assert d.target_branch_value_map == {
        "MASTER": "main",
        "FINCORE_RELEASE": "fin-core/release",
    }


def test_load_forbidden_patterns_override(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        'forbidden_patterns = ["**/Something.java", "**/other.xml"]\n',
        encoding="utf-8",
    )
    d = load(cfg)
    assert d.forbidden_patterns == ("**/Something.java", "**/other.xml")


def test_load_missing_file_when_path_given_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "does-not-exist.toml")


def test_load_no_path_falls_back_to_defaults_when_user_file_absent(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    d = load()
    assert d == defaults()
    assert not (tmp_path / ".afk-driver" / "config.toml").exists()


def test_defaults_dev_cr_merge_gate_fields():
    d = defaults()
    assert d.dev_cr_merge_gate_fields == {
        "merge_request_link": "customfield_12700",
        "sred_eligibility": "customfield_14005",
        "time_estimation": "customfield_14006",
        "sred_rationale": "customfield_14003",
    }
    # merge_request_link has no default — it's filled from the live MR URL
    assert "merge_request_link" not in d.dev_cr_merge_gate_defaults
    assert d.dev_cr_merge_gate_defaults["sred_eligibility"] == {
        "value": "SRED not eligible",
        "child": {"value": "Straightforward Implementation"},
    }
    assert d.dev_cr_merge_gate_defaults["time_estimation"] == {
        "value": "Low: 10 and < 80 hours"
    }
    assert d.dev_cr_merge_gate_defaults["sred_rationale"] == "."


def test_load_dev_cr_merge_gate_field_id_override(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[dev_cr_merge_gate_fields]\nmerge_request_link = "customfield_99999"\n',
        encoding="utf-8",
    )
    d = load(cfg)
    assert d.dev_cr_merge_gate_fields["merge_request_link"] == "customfield_99999"
    # other field ids untouched
    assert d.dev_cr_merge_gate_fields["sred_eligibility"] == "customfield_14005"


def test_defaults_mr_assignee():
    assert defaults().mr_assignee == "minh.vu.nakisa"


def test_load_mr_assignee_override(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('mr_assignee = "other.user"\n', encoding="utf-8")
    assert load(cfg).mr_assignee == "other.user"


def test_load_dev_cr_merge_gate_default_override(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[dev_cr_merge_gate_defaults]\nsred_rationale = "Custom rationale here."\n',
        encoding="utf-8",
    )
    d = load(cfg)
    assert d.dev_cr_merge_gate_defaults["sred_rationale"] == "Custom rationale here."
    # untouched defaults stay
    assert d.dev_cr_merge_gate_defaults["time_estimation"] == {
        "value": "Low: 10 and < 80 hours"
    }


# ---------------------------------------------------------------------------
# [github] + [backend_select] sub-sections (ST06 — SDD §3 / §5 feature flags)
# ---------------------------------------------------------------------------


def test_defaults_github_section():
    d = defaults()
    assert d.github == GithubConfig()
    assert d.github.mode == "cwd"
    assert d.github.auto_clone_root == ""
    assert d.github.default_target_branch_fallback == ()


def test_defaults_backend_select_section():
    d = defaults()
    assert d.backend_select == BackendSelectConfig()
    assert d.backend_select.force_backend == ""
    assert d.backend_select.gitlab_host == "gitlab"


def test_load_github_mode_override(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[github]\n'
        'mode = "all-repos"\n'
        'auto_clone_root = "/srv/clones"\n'
        'default_target_branch_fallback = ["main", "master"]\n',
        encoding="utf-8",
    )
    d = load(cfg)
    assert d.github.mode == "all-repos"
    assert d.github.auto_clone_root == "/srv/clones"
    assert d.github.default_target_branch_fallback == ("main", "master")


def test_load_backend_select_overrides(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[backend_select]\n'
        'force_backend = "github"\n'
        'gitlab_host = "git.example.org"\n',
        encoding="utf-8",
    )
    d = load(cfg)
    assert d.backend_select.force_backend == "github"
    assert d.backend_select.gitlab_host == "git.example.org"


def test_unknown_top_level_keys_are_tolerated(tmp_path: Path):
    """Forward-compat per SDD §4 state table row "Driver config"."""
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        'wall_clock_cap_seconds = 42\n'
        'this_is_a_future_key = "ignored"\n'
        '[some_future_section]\n'
        'whatever = true\n',
        encoding="utf-8",
    )
    d = load(cfg)
    assert d.wall_clock_cap_seconds == 42
    # No error; known fields override, unknown silently dropped.


def test_unknown_github_section_keys_are_tolerated(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[github]\n'
        'mode = "cwd"\n'
        'someday_key = "value"\n',
        encoding="utf-8",
    )
    d = load(cfg)
    assert d.github.mode == "cwd"


# ---------------------------------------------------------------------------
# load_per_repo — SDD §4 state table row "Per-repo overrides"
# ---------------------------------------------------------------------------


def test_load_per_repo_missing_file_returns_base_unchanged(tmp_path: Path):
    base = defaults()
    merged = load_per_repo(tmp_path, base)
    assert merged == base


def test_load_per_repo_overrides_global(tmp_path: Path):
    # Build a non-default global config first.
    global_cfg = tmp_path / "global.toml"
    global_cfg.write_text(
        'wall_clock_cap_seconds = 1800\n'
        '[github]\n'
        'mode = "cwd"\n',
        encoding="utf-8",
    )
    global_loaded = load(global_cfg)
    assert global_loaded.wall_clock_cap_seconds == 1800
    assert global_loaded.github.mode == "cwd"

    # Per-repo file flips mode and bumps the cap.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".afk-driver.toml").write_text(
        'wall_clock_cap_seconds = 600\n'
        '[github]\n'
        'mode = "all-repos"\n',
        encoding="utf-8",
    )
    merged = load_per_repo(repo_root, global_loaded)
    assert merged.wall_clock_cap_seconds == 600  # per-repo wins
    assert merged.github.mode == "all-repos"  # per-repo wins


def test_load_per_repo_tolerates_unknown_keys(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".afk-driver.toml").write_text(
        'experimental_flag = true\n'
        '[github]\n'
        'auto_clone_root = "/tmp/clones"\n'
        'totally_made_up = 1\n',
        encoding="utf-8",
    )
    base = defaults()
    merged = load_per_repo(repo_root, base)
    assert merged.github.auto_clone_root == "/tmp/clones"
    # Other defaults untouched.
    assert merged.github.mode == "cwd"


def test_load_per_repo_partial_keeps_global_for_unmentioned_fields(tmp_path: Path):
    # Global sets gitlab_host; per-repo only sets force_backend.
    global_cfg = tmp_path / "global.toml"
    global_cfg.write_text(
        '[backend_select]\n'
        'gitlab_host = "git.example.org"\n',
        encoding="utf-8",
    )
    global_loaded = load(global_cfg)
    assert global_loaded.backend_select.gitlab_host == "git.example.org"

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".afk-driver.toml").write_text(
        '[backend_select]\n'
        'force_backend = "github"\n',
        encoding="utf-8",
    )
    merged = load_per_repo(repo_root, global_loaded)
    assert merged.backend_select.force_backend == "github"  # per-repo
    assert merged.backend_select.gitlab_host == "git.example.org"  # global kept
