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
    assert answer["ok"] and answer["prior"] == "0.1.63" and runner.lavish == "0.1.80"
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
    assert tools.lavish_record(places).exists() and runner.lavish == "0.1.80"


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
