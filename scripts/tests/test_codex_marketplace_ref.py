"""Tests for setup's Codex marketplace pin repair."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN_ROOT / "skills" / "afk" / "setup" / "scripts" / "codex_marketplace_ref.py"


def run(config: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(SCRIPT), "--config", str(config)]
    if check:
        command.append("--check")
    return subprocess.run(command, capture_output=True, text=True, timeout=60)


def test_check_accepts_an_unpinned_marketplace(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text('[marketplaces.afk-toolkit]\nsource = "owner/repo"\n', encoding="utf-8")
    done = run(config, check=True)
    assert done.returncode == 0 and done.stdout == ""


def test_check_reports_a_pin_without_disclosing_its_value(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text('[marketplaces.afk-toolkit]\nref = "private-ref"\n', encoding="utf-8")
    done = run(config, check=True)
    assert done.returncode == 1
    assert done.stdout == ""
    assert "private-ref" not in done.stdout + done.stderr


def test_unpin_changes_only_the_target_line_and_writes_a_backup(tmp_path: Path):
    config = tmp_path / "config.toml"
    original = (
        b'[marketplaces.afk-toolkit]\r\nsource_type = "git"\r\n'
        b'source = "owner/repo"\r\nref = "v1.2.3" # old pin\r\n\r\n'
        b'[marketplaces.other]\r\nref = "keep-me"\r\n'
    )
    config.write_bytes(original)
    done = run(config)
    assert done.returncode == 0
    assert config.read_bytes() == original.replace(b'ref = "v1.2.3" # old pin\r\n', b"")
    backups = list(tmp_path.glob("config.toml.bak-*"))
    assert len(backups) == 1 and backups[0].read_bytes() == original


def test_quoted_table_and_key_are_supported(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text('[marketplaces."afk-toolkit"]\n"ref" = "main"\nsource = "owner/repo"\n', encoding="utf-8")
    done = run(config)
    assert done.returncode == 0
    assert config.read_text(encoding="utf-8") == '[marketplaces."afk-toolkit"]\nsource = "owner/repo"\n'


def test_missing_config_or_marketplace_is_already_unpinned(tmp_path: Path):
    missing = tmp_path / "missing.toml"
    assert run(missing, check=True).returncode == 0
    config = tmp_path / "config.toml"
    config.write_text('[features]\nhooks = true\n', encoding="utf-8")
    assert run(config).returncode == 0
    assert not list(tmp_path.glob("config.toml.bak-*"))


def test_invalid_toml_is_not_changed(tmp_path: Path):
    config = tmp_path / "config.toml"
    original = b"[marketplaces.afk-toolkit\nref = ???\n"
    config.write_bytes(original)
    done = run(config)
    assert done.returncode == 2
    assert config.read_bytes() == original
    assert not list(tmp_path.glob("config.toml.bak-*"))


def test_an_inline_pin_is_refused_instead_of_reformatting_the_file(tmp_path: Path):
    config = tmp_path / "config.toml"
    original = b'[marketplaces]\nafK = "untouched"\nafK-toolkit = { ref = "v1" }\n'
    config.write_bytes(original)
    assert run(config).returncode == 0  # A differently cased marketplace is unrelated.

    original = b'[marketplaces]\nafK = "untouched"\n"afk-toolkit" = { ref = "v1" }\n'
    config.write_bytes(original)
    done = run(config)
    assert done.returncode == 2
    assert config.read_bytes() == original


def test_unpin_is_idempotent(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text('[marketplaces.afk-toolkit]\nref = "v1"\n', encoding="utf-8")
    assert run(config).returncode == 0
    backups = list(tmp_path.glob("config.toml.bak-*"))
    assert run(config).returncode == 0
    assert list(tmp_path.glob("config.toml.bak-*")) == backups
