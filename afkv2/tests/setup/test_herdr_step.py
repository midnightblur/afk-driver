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

    def __call__(self, argv, env=None, timeout=300):
        name = str(argv[0]).split("/")[-1].split("\\")[-1].split(".")[0]
        if name in ("powershell", "sh", "brew"):
            self.calls.append(list(argv))
            self.last_env = env
            if self.installer_code == 0:
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
    tools.install_herdr(herdr_runner, windows=False)
    (call,) = herdr_runner.installer_calls()
    assert call[:2] == ["sh", "-c"] and call[2] == f"curl -fsSL {tools.HERDR_INSTALL_SH} | sh"
    assert tools.HERDR_INSTALL_SH == "https://herdr.dev/install.sh"


def test_unix_with_brew_uses_the_package_manager(herdr_runner):
    herdr_runner.paths["brew"] = "/opt/homebrew/bin/brew"
    tools.install_herdr(herdr_runner, windows=False)
    assert herdr_runner.installer_calls() == [["brew", "install", "herdr"]]


def test_a_failed_installer_answers_its_last_line(herdr_runner):
    herdr_runner.installer_code = 1
    answer = tools.install_herdr(herdr_runner, windows=True)
    assert answer["ok"] is False
    assert answer["error"] == {"code": "install-failed", "reason": "error: no release for this platform"}


def test_no_install_path_writes_a_program_file(herdr_runner):
    """AC-029: each installer streams into a shell or a package manager; none saves a file first."""
    herdr_runner.paths["brew"] = "/opt/homebrew/bin/brew"
    for windows in (True, False):
        tools.install_herdr(herdr_runner, windows=windows)
    del herdr_runner.paths["brew"]
    tools.install_herdr(herdr_runner, windows=False)
    for call in herdr_runner.installer_calls():
        text = " ".join(call).lower()
        assert not any(word in text for word in ("temp", "tmp", "install.cmd", "-o ", "-fsslo", "outfile", ".exe"))
