from pathlib import Path

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
