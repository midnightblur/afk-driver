import json
import os
import stat
import sys
from pathlib import Path

import pytest

import tools


def test_python_3_found_and_recorded(runner):
    runner.paths["python"] = "/usr/bin/python"
    answer = tools.find_python(runner, {})
    assert answer == {"ok": True, "command": "python", "path": "/usr/bin/python", "version": "3.12.4"}


def test_no_python_is_refused(runner):
    assert tools.find_python(runner, {})["error"]["code"] == "no-python"


def _probes(runner, windows=False):
    return tools.shell_probes(windows, lambda n: runner.which(n))


def test_rg_present_on_every_shell(runner):
    answer = tools.ensure_rg(runner, lambda: {}, _probes(runner), lambda _f: False, windows=False)
    assert answer["ok"] and answer["action"] == "present"


def test_rg_folder_is_added_to_the_path_for_a_shell_without_it(runner):
    runner.paths["sh"] = "/bin/sh"
    runner.shell_has_rg["sh"] = False
    added = []

    def add(folder):
        added.append(folder)
        runner.shell_has_rg["sh"] = True
        return True

    answer = tools.ensure_rg(runner, lambda: {}, _probes(runner), add, windows=False)
    assert answer["ok"] and answer["path_added"] and added == [Path("/tools/rg")]


def test_rg_is_installed_on_windows_when_no_shell_has_it(runner):
    del runner.paths["rg"]
    runner.paths["cmd"] = "cmd"
    runner.shell_has_rg.update({"bash": False, "cmd": False})

    def add(_folder):
        runner.shell_has_rg.update({"bash": True, "cmd": True})
        return True

    answer = tools.ensure_rg(runner, lambda: {}, _probes(runner, windows=True), add, windows=True)
    assert answer["ok"] and answer["action"] == "installed" and answer["rg"] == "/winget/links/rg"
    assert any(c[0] == "winget" for c in runner.calls)


def test_rg_missing_off_windows_is_reported(runner):
    del runner.paths["rg"]
    runner.shell_has_rg["bash"] = False
    answer = tools.ensure_rg(runner, lambda: {}, _probes(runner), lambda _f: False, windows=False)
    assert not answer["ok"] and answer["error"]["code"] == "no-rg"


def test_lavish_records_prior_then_installs_pin(places, runner):
    answer = tools.install_lavish_pin(places, runner, {})
    assert answer["ok"] and answer["prior"] == "0.1.63" and runner.lavish == "0.1.81"
    again = tools.install_lavish_pin(places, runner, {})
    assert again["action"] == "present"
    assert tools.lavish_record(places).read_text().strip() == "0.1.63"
    back = tools.restore_lavish(places, runner, {})
    assert back["ok"] and runner.lavish == "0.1.63" and not tools.lavish_record(places).exists()


def test_lavish_absent_before_is_uninstalled_on_restore(places, runner):
    runner.lavish = None
    tools.install_lavish_pin(places, runner, {})
    tools.restore_lavish(places, runner, {})
    assert runner.lavish is None


def test_lavish_install_failure_is_reported(places, runner):
    runner.npm_fails = True
    answer = tools.install_lavish_pin(places, runner, {})
    assert not answer["ok"] and answer["error"]["code"] == "lavish-install-failed"


def test_windows_probes_skip_the_wsl_launcher():
    paths = {"bash": r"C:\Windows\System32\bash.exe", "cmd": r"C:\Windows\system32\cmd.exe"}
    probes = dict(tools.shell_probes(True, paths.get))
    assert "bash" not in probes and probes["cmd"][0] == paths["cmd"]
    paths["bash"] = r"C:\Program Files\Git\usr\bin\bash.exe"
    assert dict(tools.shell_probes(True, paths.get))["bash"][0] == paths["bash"]


def test_rg_install_failure_is_reported(runner):
    del runner.paths["rg"]
    runner.winget_installs = False
    runner.shell_has_rg["bash"] = False
    answer = tools.ensure_rg(runner, lambda: {}, _probes(runner, windows=True), lambda _f: False, windows=True)
    assert not answer["ok"] and answer["error"]["code"] == "rg-install-failed"
    assert answer["shells"]["bash"] is False


def test_a_shell_still_without_rg_is_reported_by_name(runner):
    runner.shell_has_rg["bash"] = False
    answer = tools.ensure_rg(runner, lambda: {}, _probes(runner), lambda _f: True, windows=False)
    assert not answer["ok"] and answer["error"]["code"] == "rg-not-on-every-shell"
    assert answer["shells"] == {"bash": False} and answer["path_added"]


def test_python_2_is_not_python_3(runner):
    runner.paths["python"] = "/usr/bin/python"
    runner.python_version = "Python 2.7.18\n"
    assert tools.find_python(runner, {})["error"]["code"] == "no-python"


def test_npm_with_no_answer_writes_no_lavish_record(places, runner):
    runner.npm_ls_fails = True
    answer = tools.install_lavish_pin(places, runner, {})
    assert not answer["ok"] and answer["error"]["code"] == "npm-unavailable"
    assert not tools.lavish_record(places).exists()


def test_a_real_absence_is_recorded(places, runner):
    runner.lavish = None
    assert tools.lavish_version(runner, {}) is None
    tools.install_lavish_pin(places, runner, {})
    assert tools.lavish_record(places).read_text().strip() == "none"


def test_restore_with_npm_unavailable_keeps_the_record_and_the_package(places, runner):
    tools.install_lavish_pin(places, runner, {})
    runner.npm_ls_fails = True
    answer = tools.restore_lavish(places, runner, {})
    assert not answer["ok"] and answer["error"]["code"] == "npm-unavailable"
    assert tools.lavish_record(places).exists() and runner.lavish == "0.1.81"


class _FakeWinreg:
    """The winreg calls the writers use, over one Environment key in memory."""

    HKEY_CURRENT_USER, KEY_READ, KEY_WRITE, KEY_SET_VALUE = 1, 2, 4, 8
    REG_SZ, REG_EXPAND_SZ = 1, 2

    def __init__(self, values=None):
        self.values = dict(values or {})

    def OpenKey(self, *_args):
        return self

    def CloseKey(self, _key):
        pass

    def QueryValueEx(self, _key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name]

    def SetValueEx(self, _key, name, _reserved, kind, value):
        self.values[name] = (value, kind)


@pytest.fixture
def registry(monkeypatch):
    def install(values=None):
        fake = _FakeWinreg(values)
        monkeypatch.setitem(sys.modules, "winreg", fake)
        monkeypatch.setattr(tools, "broadcast_environment_change", lambda: None)
        return fake
    return install


def test_path_adder_appends_and_keeps_the_expandable_kind(registry):
    fake = registry({"Path": ("/one;%TOOLS%/two", _FakeWinreg.REG_EXPAND_SZ)})
    assert tools.windows_user_path_adder(Path("/rg"))
    value, kind = fake.values["Path"]
    assert value.split(";") == ["/one", "%TOOLS%/two", str(Path("/rg"))]
    assert kind == _FakeWinreg.REG_EXPAND_SZ


def test_path_adder_writes_nothing_when_the_folder_is_there(registry, monkeypatch):
    monkeypatch.setenv("AFKV2_TEST_TOOLS", str(Path("/tools")))
    before = (f"/other;$AFKV2_TEST_TOOLS{os.sep}rg", _FakeWinreg.REG_EXPAND_SZ)
    fake = registry({"Path": before})
    assert not tools.windows_user_path_adder(Path("/tools/rg"))
    assert fake.values["Path"] == before


def test_path_adder_creates_an_absent_value(registry):
    fake = registry()
    assert tools.windows_user_path_adder(Path("/tools/rg"))
    assert fake.values["Path"] == (str(Path("/tools/rg")), _FakeWinreg.REG_EXPAND_SZ)


def test_lock_removes_inherited_rights_and_grants_only_the_user(tmp_path, runner):
    folder = tmp_path / "data" / "backup"
    tools.lock_to_current_user(folder, runner, True, {"USERNAME": "dev", "USERDOMAIN": "CORP"})
    assert folder.is_dir()
    assert runner.calls == [["icacls", str(folder), "/inheritance:r", "/grant:r", "CORP\\dev:(OI)(CI)F"]]


def test_lock_without_a_domain_uses_the_bare_user_name(tmp_path, runner):
    tools.lock_to_current_user(tmp_path, runner, True, {"USERNAME": "dev"})
    assert runner.calls[0][-1] == "dev:(OI)(CI)F"


def test_lock_raises_when_icacls_fails(tmp_path, runner):
    runner.icacls_fails = True
    with pytest.raises(OSError, match="Access is denied"):
        tools.lock_to_current_user(tmp_path, runner, True, {"USERNAME": "dev"})


def test_lock_without_a_user_name_raises_and_runs_nothing(tmp_path, runner):
    with pytest.raises(OSError, match="USERNAME"):
        tools.lock_to_current_user(tmp_path, runner, True, {})
    assert runner.calls == []


@pytest.mark.skipif(os.name == "nt", reason="Windows file modes do not carry this protection")
def test_lock_on_posix_is_mode_0700_with_no_command(tmp_path, runner):
    folder = tmp_path / "backup"
    tools.lock_to_current_user(folder, runner, False, {})
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700 and runner.calls == []


def _edge(tmp_path, root="ProgramFiles"):
    """An environment whose one known install path holds a file named as Edge."""
    edge = tmp_path / root / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    edge.parent.mkdir(parents=True)
    edge.write_bytes(b"")
    return {root: str(tmp_path / root)}, edge


@pytest.mark.parametrize("root", ["ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"])
def test_edge_is_found_at_each_known_install_path(tmp_path, root):
    env, edge = _edge(tmp_path, root)
    assert tools.find_edge(env) == edge


def test_a_path_with_no_edge_file_finds_no_edge(tmp_path):
    assert tools.find_edge({"ProgramFiles": str(tmp_path), "PATH": str(tmp_path)}) is None


def test_no_edge_refuses_and_neither_installs_nor_downloads(places, runner, tmp_path):
    answer = tools.ensure_diagram_renderer(places, runner, {"ProgramFiles": str(tmp_path)})
    assert answer["error"]["code"] == "no-edge"
    assert runner.calls == [] and not places.puppeteer_config.exists()


def test_the_package_installs_with_the_browser_download_off_and_the_config_names_edge(places, runner, tmp_path):
    env, edge = _edge(tmp_path)
    answer = tools.ensure_diagram_renderer(places, runner, env)
    assert answer["ok"] and answer["action"] == "installed" and answer["edge"] == str(edge)
    assert ["npm", "install", "-g", f"{tools.MERMAID_PACKAGE}@12.0.0"] in runner.calls and answer["version"] == "12.0.0"
    assert runner.mermaid_install_env["PUPPETEER_SKIP_DOWNLOAD"] == "true"
    assert json.loads(places.puppeteer_config.read_text(encoding="utf-8"))["executablePath"] == str(edge)
    assert answer["config"] == str(places.puppeteer_config)


def test_the_config_file_is_in_the_setup_data_folder(places):
    assert places.puppeteer_config == places.data / "puppeteer-config.json"


def test_the_renderer_pin_is_12_0_0():
    assert tools.MERMAID_VERSION == "12.0.0"


def test_a_present_package_is_kept_and_the_config_is_written_again(places, runner, tmp_path):
    runner.mermaid = "12.0.0"
    runner.paths["mmdc"] = "/npm/mmdc"
    env, edge = _edge(tmp_path)
    places.puppeteer_config.parent.mkdir(parents=True, exist_ok=True)
    places.puppeteer_config.write_text('{"executablePath": "old"}', encoding="utf-8")
    answer = tools.ensure_diagram_renderer(places, runner, env)
    assert answer["ok"] and answer["action"] == "present" and answer["version"] == "12.0.0"
    assert not any("install" in call for call in runner.calls)
    assert json.loads(places.puppeteer_config.read_text(encoding="utf-8"))["executablePath"] == str(edge)


def test_a_present_package_of_another_version_is_replaced_by_the_pin(places, runner, tmp_path):
    runner.mermaid = "10.0.0"
    runner.paths["mmdc"] = "/npm/mmdc"
    env, _ = _edge(tmp_path)
    answer = tools.ensure_diagram_renderer(places, runner, env)
    assert ["npm", "install", "-g", f"{tools.MERMAID_PACKAGE}@12.0.0"] in runner.calls
    assert answer["ok"] and answer["action"] == "installed" and answer["version"] == "12.0.0"
    assert runner.mermaid_install_env["PUPPETEER_SKIP_DOWNLOAD"] == "true"


def test_a_failed_install_is_named_and_writes_no_config(places, runner, tmp_path):
    runner.npm_fails = True
    env, _ = _edge(tmp_path)
    answer = tools.ensure_diagram_renderer(places, runner, env)
    assert answer["error"]["code"] == "renderer-install-failed" and not places.puppeteer_config.exists()


def test_no_answer_from_npm_is_named(places, runner, tmp_path):
    runner.npm_ls_fails = True
    env, _ = _edge(tmp_path)
    assert tools.ensure_diagram_renderer(places, runner, env)["error"]["code"] == "npm-unavailable"


def test_an_installed_package_with_no_command_on_the_path_is_named(places, runner, tmp_path):
    runner.mermaid = "12.0.0"
    env, _ = _edge(tmp_path)
    assert tools.ensure_diagram_renderer(places, runner, env)["error"]["code"] == "mmdc-not-found"
