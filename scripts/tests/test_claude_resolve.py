import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hooks" / "lib" / "providers" / "claude_resolve.py"


def load_module():
    spec = importlib.util.spec_from_file_location("claude_resolve", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_root(tmp_path, name="plugin-root"):
    root = tmp_path / name
    root.mkdir()
    (root / "BEHAVIORS.md").write_text("# Behaviors\n", encoding="utf-8")
    return root


def test_resolves_from_native_env_var_when_it_is_a_verified_root(tmp_path, monkeypatch):
    module = load_module()
    root = make_root(tmp_path)
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(root))
    assert module.resolve() == str(root)


def test_ignores_native_env_var_pointing_at_an_unverified_root(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path / "does-not-exist"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
    assert module.resolve() is None


def test_does_not_trust_the_codex_compatibility_alias(tmp_path, monkeypatch):
    """A native Codex hook environment sets both `PLUGIN_ROOT` (its own
    native signal) and `CLAUDE_PLUGIN_ROOT` (a compatibility alias, same
    value) to the Codex cache. `CLAUDE_PLUGIN_ROOT` alone is not proof of a
    Claude install — PLUGIN_ROOT's presence means Codex is the active
    provider, so the alias is never trusted, verified root or not."""
    module = load_module()
    codex_root = make_root(tmp_path, "codex-root")
    monkeypatch.setenv("PLUGIN_ROOT", str(codex_root))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(codex_root))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
    assert module.resolve() is None


def test_still_falls_back_to_installed_plugins_json_when_the_alias_is_distrusted(tmp_path, monkeypatch):
    """Distrusting the Codex-active compatibility alias must not also break
    the json fallback: a genuinely separate Claude install still resolves."""
    module = load_module()
    codex_root = make_root(tmp_path, "codex-root")
    claude_root = make_root(tmp_path, "claude-root")
    monkeypatch.setenv("PLUGIN_ROOT", str(codex_root))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(codex_root))
    config_dir = tmp_path / "claude-config"
    (config_dir / "plugins").mkdir(parents=True)
    (config_dir / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"plugins": {"afk@afk-toolkit": [{"installPath": str(claude_root)}]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    assert module.resolve() == str(claude_root)


def test_resolves_from_installed_plugins_json_nested_under_plugins_key(tmp_path, monkeypatch):
    """The live shape: top-level keys are `plugins` and `version`; the AFK
    entry sits under `plugins["afk@afk-toolkit"]`."""
    module = load_module()
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    config_dir = tmp_path / "claude-config"
    (config_dir / "plugins").mkdir(parents=True)
    root = make_root(tmp_path)
    (config_dir / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 3, "plugins": {"afk@afk-toolkit": [{"installPath": str(root)}]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    assert module.resolve() == str(root)


def test_resolves_from_installed_plugins_json_flat_shape(tmp_path, monkeypatch):
    """A defensive second shape: the AFK entry at the top level, no `plugins`
    wrapper — kept in case an older or different install writes this."""
    module = load_module()
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    config_dir = tmp_path / "claude-config"
    (config_dir / "plugins").mkdir(parents=True)
    root = make_root(tmp_path)
    (config_dir / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"afk@afk-toolkit": [{"installPath": str(root)}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    assert module.resolve() == str(root)


def test_reports_unresolved_when_installed_path_does_not_verify(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    config_dir = tmp_path / "claude-config"
    (config_dir / "plugins").mkdir(parents=True)
    (config_dir / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"plugins": {"afk@afk-toolkit": [{"installPath": str(tmp_path / "ghost")}]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    assert module.resolve() is None


def test_reports_unresolved_when_registry_file_is_absent(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "no-such-config-dir"))
    assert module.resolve() is None


def test_cli_prints_resolved_root_and_exits_1_when_unresolved(tmp_path, monkeypatch, capsys):
    module = load_module()
    root = make_root(tmp_path)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(root))
    assert module.main([]) == 0
    assert capsys.readouterr().out.strip() == str(root)

    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
    assert module.main([]) == 1
    assert capsys.readouterr().out == ""


def test_enablement_reads_true_and_false_from_settings_json(tmp_path, monkeypatch):
    module = load_module()
    config_dir = tmp_path / "claude-config"
    config_dir.mkdir()
    settings = config_dir / "settings.json"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))

    settings.write_text(json.dumps({"enabledPlugins": {"afk@afk-toolkit": True}}), encoding="utf-8")
    assert module.enablement() == "enabled"

    settings.write_text(json.dumps({"enabledPlugins": {"afk@afk-toolkit": False}}), encoding="utf-8")
    assert module.enablement() == "disabled"


def test_enablement_is_absent_when_key_or_file_is_missing(tmp_path, monkeypatch):
    module = load_module()
    config_dir = tmp_path / "claude-config"
    config_dir.mkdir()
    settings = config_dir / "settings.json"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "no-such-config-dir"))
    assert module.enablement() == "absent"

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    settings.write_text(json.dumps({"enabledPlugins": {"other@plugin": True}}), encoding="utf-8")
    assert module.enablement() == "absent"


def test_cli_enablement_flag_prints_the_classification_and_always_exits_0(tmp_path, monkeypatch, capsys):
    module = load_module()
    config_dir = tmp_path / "claude-config"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text(
        json.dumps({"enabledPlugins": {"afk@afk-toolkit": False}}), encoding="utf-8"
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))

    assert module.main(["--enablement"]) == 0
    assert capsys.readouterr().out.strip() == "disabled"
