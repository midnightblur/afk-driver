import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "hooks" / "lib" / "providers" / "codex_resolve.py"


def load_module():
    spec = importlib.util.spec_from_file_location("codex_resolve", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_root(tmp_path, name="plugin-root"):
    root = tmp_path / name
    root.mkdir()
    (root / "BEHAVIORS.md").write_text("# Behaviors\n", encoding="utf-8")
    return root


# Real `codex plugin list` output (captured from a live install): two
# marketplace sections, each with its own header and its own column widths,
# one row with empty VERSION/SOURCE cells (a not-installed plugin).
CODEX_TABLE_FIXTURE = (
    "Marketplace `openai-bundled`\n"
    "C:\\Users\\{user}\\.codex\\.tmp\\bundled-marketplaces\\openai-bundled\\.agents\\plugins\\marketplace.json\n"
    "\n"
    "PLUGIN                               STATUS              VERSION       SOURCE\n"
    "browser@openai-bundled               installed, enabled  26.924.22138  C:\\bundled\\browser\n"
    "chrome@openai-bundled                not installed                     C:\\bundled\\chrome\n"
    "\n"
    "Marketplace `afk-toolkit`\n"
    "C:\\Users\\{user}\\.codex\\.tmp\\marketplaces\\afk-toolkit\\.agents\\plugins\\marketplace.json\n"
    "\n"
    "PLUGIN           STATUS              VERSION  SOURCE\n"
    "afk@afk-toolkit  installed, enabled  1.7.0    C:\\Users\\{user}\\.codex\\.tmp\\marketplaces\\afk-toolkit\n"
)

CODEX_TABLE_FIXTURE_DISABLED = (
    "PLUGIN           STATUS               VERSION  SOURCE\n"
    "afk@afk-toolkit  installed, disabled  1.7.0    C:\\Users\\{user}\\.codex\\.tmp\\marketplaces\\afk-toolkit\n"
)

CODEX_TABLE_FIXTURE_NOT_INSTALLED = (
    "PLUGIN           STATUS         VERSION  SOURCE\n"
    "afk@afk-toolkit  not installed                    \n"
)


def _fake_codex_cli(module, monkeypatch, *, table_output, returncode=0, present=True):
    monkeypatch.setattr(
        module.shutil, "which", lambda name: "codex" if present and name == "codex" else None
    )

    class FakeCompleted:
        def __init__(self):
            self.returncode = returncode
            self.stdout = table_output

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: FakeCompleted())


def test_resolves_from_native_env_var_when_it_is_a_verified_root(tmp_path, monkeypatch):
    module = load_module()
    root = make_root(tmp_path)
    monkeypatch.setenv("PLUGIN_ROOT", str(root))
    assert module.resolve() == str(root)


def test_resolves_from_the_installed_version_cache_directory(tmp_path, monkeypatch):
    """The live `config.toml` table under `[plugins."afk@afk-toolkit"]` holds
    only `enabled = true` — no path field to read, guessed or not. Resolution
    instead reads the VERSION column of the `afk@afk-toolkit` row in `codex
    plugin list`'s own table (located by header column name, since column
    widths differ per marketplace section — this fixture has two) and looks
    up Codex's own version-cache directory for it."""
    module = load_module()
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    codex_home = tmp_path / "codex-home"
    version_dir = codex_home / "plugins" / "cache" / "afk-toolkit" / "afk" / "1.7.0"
    version_dir.mkdir(parents=True)
    (version_dir / "BEHAVIORS.md").write_text("# Behaviors\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    _fake_codex_cli(module, monkeypatch, table_output=CODEX_TABLE_FIXTURE)
    assert module.resolve() == str(version_dir)


def test_reports_unresolved_when_cli_is_absent(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    _fake_codex_cli(module, monkeypatch, table_output=CODEX_TABLE_FIXTURE, present=False)
    assert module.resolve() is None


def test_reports_unresolved_when_the_row_is_missing(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    table_without_afk = (
        "PLUGIN                 STATUS              VERSION       SOURCE\n"
        "browser@openai-bundled installed, enabled  26.924.22138  C:\\bundled\\browser\n"
    )
    _fake_codex_cli(module, monkeypatch, table_output=table_without_afk)
    assert module.resolve() is None


def test_reports_unresolved_when_the_version_directory_is_absent(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    _fake_codex_cli(module, monkeypatch, table_output=CODEX_TABLE_FIXTURE)
    assert module.resolve() is None


def test_own_resolution_is_unaffected_by_the_claude_compatibility_alias(tmp_path, monkeypatch):
    """Codex's own native `PLUGIN_ROOT` is unambiguous (Claude never sets
    it), so resolution needs no guard and must keep resolving from it
    regardless of `CLAUDE_PLUGIN_ROOT` also being set."""
    module = load_module()
    codex_root = make_root(tmp_path, "codex-root")
    claude_root = make_root(tmp_path, "claude-root")
    monkeypatch.setenv("PLUGIN_ROOT", str(codex_root))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(claude_root))
    assert module.resolve() == str(codex_root)


def test_cli_prints_resolved_root_and_exits_1_when_unresolved(tmp_path, monkeypatch, capsys):
    module = load_module()
    root = make_root(tmp_path)
    monkeypatch.setenv("PLUGIN_ROOT", str(root))
    assert module.main([]) == 0
    assert capsys.readouterr().out.strip() == str(root)

    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    _fake_codex_cli(module, monkeypatch, table_output=CODEX_TABLE_FIXTURE, present=False)
    assert module.main([]) == 1
    assert capsys.readouterr().out == ""


def test_enablement_reads_enabled_from_the_status_column(tmp_path, monkeypatch):
    module = load_module()
    _fake_codex_cli(module, monkeypatch, table_output=CODEX_TABLE_FIXTURE)
    assert module.enablement() == "enabled"


def test_enablement_reads_disabled_from_the_status_column(tmp_path, monkeypatch):
    """A row with `installed, disabled` and a real version must still report
    `disabled` — the resolver must not stop at the VERSION cell and silently
    drop the STATUS cell it sits next to."""
    module = load_module()
    _fake_codex_cli(module, monkeypatch, table_output=CODEX_TABLE_FIXTURE_DISABLED)
    assert module.enablement() == "disabled"


def test_enablement_is_absent_when_not_installed_or_cli_missing_or_row_missing(tmp_path, monkeypatch):
    module = load_module()
    _fake_codex_cli(module, monkeypatch, table_output=CODEX_TABLE_FIXTURE_NOT_INSTALLED)
    assert module.enablement() == "absent"

    _fake_codex_cli(module, monkeypatch, table_output=CODEX_TABLE_FIXTURE, present=False)
    assert module.enablement() == "absent"

    table_without_afk = (
        "PLUGIN                 STATUS              VERSION       SOURCE\n"
        "browser@openai-bundled installed, enabled  26.924.22138  C:\\bundled\\browser\n"
    )
    _fake_codex_cli(module, monkeypatch, table_output=table_without_afk)
    assert module.enablement() == "absent"


def test_cli_enablement_flag_prints_the_classification_and_always_exits_0(tmp_path, monkeypatch, capsys):
    module = load_module()
    _fake_codex_cli(module, monkeypatch, table_output=CODEX_TABLE_FIXTURE_DISABLED)

    assert module.main(["--enablement"]) == 0
    assert capsys.readouterr().out.strip() == "disabled"
