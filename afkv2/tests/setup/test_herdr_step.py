"""The herdr step: present, ask, declined, and the consented install through a fake installer."""

import json

import pytest

import setup
import tools
from conftest import FakeRunner


class HerdrRunner(FakeRunner):
    """FakeRunner plus a fake herdr installer: no test runs a real installer or a download."""

    def __init__(self, places):
        super().__init__(places)
        self.installer_code = 0
        self.installer_out = "herdr installed to ~/.local/bin\n"
        self.installer_leaves_path = True

    def __call__(self, argv, env=None, timeout=300):
        name = str(argv[0]).split("/")[-1].split("\\")[-1].split(".")[0]
        if name in ("powershell", "sh", "brew"):
            self.calls.append(list(argv))
            self.last_env = env
            if self.installer_code == 0:
                if self.installer_leaves_path:
                    self.paths["herdr"] = "/home/me/.local/bin/herdr"
                return tools.Result(0, self.installer_out)
            return tools.Result(self.installer_code, "", "downloading\nerror: no release for this platform\n")
        return super().__call__(argv, env, timeout)

    def installer_calls(self):
        return [c for c in self.calls if c[0] in ("powershell", "sh", "brew")]


@pytest.fixture
def herdr_runner(places):
    runner = HerdrRunner(places)
    runner.paths.update({"powershell": "powershell", "sh": "/bin/sh"})
    return runner


# ------------------------------------------------------------------ status

def test_herdr_on_the_path_is_present(herdr_runner):
    herdr_runner.paths["herdr"] = "/usr/local/bin/herdr"
    assert tools.herdr_status(herdr_runner, {"herdr": "declined"}) == "present"


def test_herdr_missing_with_no_answer_asks(herdr_runner):
    assert tools.herdr_status(herdr_runner, {}) == "ask"


def test_herdr_missing_after_a_no_is_declined(herdr_runner):
    assert tools.herdr_status(herdr_runner, {"herdr": "declined"}) == "declined"


# ----------------------------------------------------------------- install

def test_windows_runs_the_official_powershell_installer(herdr_runner):
    answer = tools.install_herdr(herdr_runner, windows=True)
    assert answer == {"ok": True, "herdr": "installed", "path": "/home/me/.local/bin/herdr"}
    (call,) = herdr_runner.installer_calls()
    assert call[0] == "powershell" and call[-1] == f"irm {tools.HERDR_INSTALL_PS1} | iex"
    assert tools.HERDR_INSTALL_PS1 == "https://herdr.dev/install.ps1"


def test_unix_runs_the_official_shell_installer(herdr_runner):
    assert tools.install_herdr(herdr_runner, windows=False)["herdr"] == "installed"
    (call,) = herdr_runner.installer_calls()
    assert call[:2] == ["sh", "-c"] and call[2] == f"curl -fsSL {tools.HERDR_INSTALL_SH} | sh"
    assert tools.HERDR_INSTALL_SH == "https://herdr.dev/install.sh"


def test_unix_with_brew_uses_the_package_manager(herdr_runner):
    herdr_runner.paths["brew"] = "/opt/homebrew/bin/brew"
    assert tools.install_herdr(herdr_runner, windows=False)["ok"] is True
    assert herdr_runner.installer_calls() == [["brew", "install", "herdr"]]


def test_a_failed_installer_answers_its_last_line(herdr_runner):
    herdr_runner.installer_code = 1
    answer = tools.install_herdr(herdr_runner, windows=True)
    assert answer["ok"] is False
    assert answer["error"] == {"code": "install-failed", "reason": "error: no release for this platform"}


def test_no_install_path_writes_a_program_file(herdr_runner):
    """AC-029, our side only: no command saves a file first. The vendor scripts download into a
    temporary folder; the setup-folder test below covers that."""
    herdr_runner.paths["brew"] = "/opt/homebrew/bin/brew"
    for windows in (True, False):
        tools.install_herdr(herdr_runner, windows=windows)
    del herdr_runner.paths["brew"]
    tools.install_herdr(herdr_runner, windows=False)
    for call in herdr_runner.installer_calls():
        text = " ".join(call).lower()
        assert not any(word in text for word in ("temp", "tmp", "install.cmd", "-o ", "-fsslo", "outfile", ".exe"))


# ----------------------------------------------------------- the setup verb

@pytest.fixture
def herdr_system(herdr_runner):
    return setup.System(run=herdr_runner, windows=False, add_to_user_path=lambda _f: False,
                        is_terminal=lambda: True)


def _run(argv, env, system, capsys, repo=None):
    code = setup.main(argv + (["--repo", str(repo)] if repo else []), env=env, system=system)
    return code, json.loads(capsys.readouterr().out)


def _prepared(places):
    setup.write_install_record(places, {"path": "/py", "version": "3.12"}, "/rg")


def test_status_asks_when_herdr_is_missing_and_unanswered(env, places, repo, herdr_system, capsys):
    code, answer = _run(["status"], env, herdr_system, capsys, repo)
    assert code == 0 and answer["herdr"] == "ask"


def test_status_with_herdr_present_asks_nothing(env, places, repo, herdr_system, herdr_runner, capsys):
    herdr_runner.paths["herdr"] = "/usr/local/bin/herdr"
    _, answer = _run(["status"], env, herdr_system, capsys, repo)
    assert answer["herdr"] == "present"
    assert herdr_runner.installer_calls() == []


def test_answer_yes_installs_and_records(env, places, herdr_system, herdr_runner, capsys):
    _prepared(places)
    code, answer = _run(["herdr", "--answer", "yes"], env, herdr_system, capsys)
    assert code == 0 and answer["herdr"] == "installed"
    assert len(herdr_runner.installer_calls()) == 1
    record = setup.read_install_record(places)
    assert record["herdr"] == "installed" and record["python"] == "/py 3.12"


def test_answer_no_records_declined_and_is_never_asked_again(env, places, repo, herdr_system, herdr_runner,
                                                             capsys):
    _prepared(places)
    code, answer = _run(["herdr", "--answer", "no"], env, herdr_system, capsys)
    assert code == 0 and answer == {"ok": True, "herdr": "declined"}
    assert herdr_runner.installer_calls() == []
    _, status = _run(["status"], env, herdr_system, capsys, repo)
    assert status["herdr"] == "declined"
    setup.write_install_record(places, {"path": "/py", "version": "3.13"}, "/rg")
    assert setup.read_install_record(places)["herdr"] == "declined"


def test_answer_yes_with_herdr_present_runs_nothing(env, places, herdr_system, herdr_runner, capsys):
    herdr_runner.paths["herdr"] = "/usr/local/bin/herdr"
    code, answer = _run(["herdr", "--answer", "yes"], env, herdr_system, capsys)
    assert code == 0 and answer["herdr"] == "present"
    assert herdr_runner.installer_calls() == []


def test_a_failed_install_records_nothing(env, places, herdr_system, herdr_runner, capsys):
    _prepared(places)
    herdr_runner.installer_code = 2
    code, answer = _run(["herdr", "--answer", "yes"], env, herdr_system, capsys)
    assert code == 1 and answer["error"]["code"] == "install-failed"
    assert "herdr" not in setup.read_install_record(places)


def test_the_verb_needs_an_answer(env, herdr_system, capsys):
    code, answer = _run(["herdr"], env, herdr_system, capsys)
    assert code == 2 and answer["error"]["code"] == "bad-arguments"


def test_a_yes_that_leaves_herdr_off_the_path_is_not_asked_again(env, places, repo, herdr_system, herdr_runner,
                                                                  capsys):
    _prepared(places)
    herdr_runner.installer_leaves_path = False
    code, answer = _run(["herdr", "--answer", "yes"], env, herdr_system, capsys)
    assert code == 0 and answer["herdr"] == "installed" and answer["on_path"] is False
    _, status = _run(["status"], env, herdr_system, capsys, repo)
    assert status["herdr"] == "installed"
    assert len(herdr_runner.installer_calls()) == 1


def test_the_installed_path_is_read_from_a_fresh_environment(env, places, herdr_runner, capsys):
    """The installer changes the user path; only a newly read environment shows it."""
    _prepared(places)
    reads = []

    def fresh():
        reads.append(1)
        return {"PATH": f"fresh-{len(reads)}"}

    seen = []
    base_which = herdr_runner.which

    def which(name, env=None):
        seen.append((name, (env or {}).get("PATH")))
        return base_which(name, env)

    herdr_runner.which = which
    system = setup.System(run=herdr_runner, windows=False, fresh_env=fresh, is_terminal=lambda: True)
    code, answer = _run(["herdr", "--answer", "yes"], env, system, capsys)
    assert code == 0 and answer["on_path"] is True
    assert seen[-1] == ("herdr", f"fresh-{len(reads)}") and len(reads) >= 2


def test_the_installer_downloads_into_the_setup_folder_not_a_temporary_folder(env, places, herdr_system,
                                                                               herdr_runner, capsys):
    """AC-029, D-11: the official installers download into GetTempPath() or mktemp -d, so setup points
    TMP, TEMP and TMPDIR at its own folder for the installer process only, and removes it after."""
    _prepared(places)
    seen = {}

    original = herdr_runner.__class__.__call__

    def spy(argv, env=None, timeout=300):
        if argv[0] in ("powershell", "sh", "brew"):
            seen.update(env or {})
            seen["exists"] = places.data.joinpath("herdr-download").is_dir()
        return original(herdr_runner, argv, env, timeout)

    herdr_system.run = lambda argv, env=None, timeout=300: spy(argv, env, timeout)
    herdr_system.run.which = herdr_runner.which
    code, _ = _run(["herdr", "--answer", "yes"], env, herdr_system, capsys)
    folder = str(places.data / "herdr-download")
    assert code == 0 and seen["exists"]
    assert seen["TMP"] == seen["TEMP"] == seen["TMPDIR"] == folder
    assert "PATH" in seen
    assert not (places.data / "herdr-download").exists()
