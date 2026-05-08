from pathlib import Path

import pytest

from afk_driver.config import DriverConfig, defaults, load


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
