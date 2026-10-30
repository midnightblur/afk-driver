"""Fixtures: a temporary home, data folder, repository and plugin tree, and an
in-process fake for every outside command except git."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "setup" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import plugins  # noqa: E402
import tools  # noqa: E402
from places import Places  # noqa: E402
import setup  # noqa: E402

SHA = "0123456789ab"
V1_ID = "afk@afk-toolkit"
NEW_ID = "afkv2@afk-toolkit"


def git_env(home: Path) -> dict:
    """git with no user or system config, so a developer's ignore rules stay out."""
    env = dict(os.environ)
    env.update({"HOME": str(home), "USERPROFILE": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(home / ".gitconfig-test")})
    return env


class FakeRunner(tools.Runner):
    """git runs for real; codex, npm, winget and the shell probes are fakes."""

    def __init__(self, places: Places):
        self.places = places
        self.calls: list[list[str]] = []
        self.paths: dict[str, str] = {"bash": "/bin/bash", "rg": "/tools/rg/rg"}
        self.shell_has_rg: dict[str, bool] = {"bash": True}
        self.lavish: str | None = "0.1.63"
        self.codex_cli = True
        self.winget_installs = True
        self.npm_fails = False

    def which(self, name, env=None):
        if name == "git":
            return super().which(name, env)
        return self.paths.get(name)

    def __call__(self, argv, env=None, timeout=300):
        argv = list(argv)
        self.calls.append(argv)
        name = os.path.basename(argv[0]).split(".")[0]
        if name == "git":
            done = subprocess.run(argv, capture_output=True, text=True, env=git_env(self.places.home))
            return tools.Result(done.returncode, done.stdout, done.stderr)
        if name == "codex":
            return self._codex()
        if name == "npm":
            return self._npm(argv)
        if name == "winget":
            if self.winget_installs:
                self.paths["rg"] = "/winget/links/rg"
                return tools.Result(0, "installed")
            return tools.Result(1, "", "winget failed")
        if name in self.shell_has_rg:
            return tools.Result(0 if self.shell_has_rg[name] else 1)
        if name in ("python3", "python", "py"):
            return tools.Result(0, "Python 3.12.4\n") if name in self.paths else tools.Result(127)
        return tools.Result(127, "", f"{name} not faked")

    def _codex(self):
        if not self.codex_cli or not self.places.codex_config.exists():
            return tools.Result(127, "", "codex not found")
        state = plugins.codex_config_state(self.places.codex_config.read_text(encoding="utf-8"))
        rows = ["PLUGIN              STATUS               VERSION  SOURCE"]
        for plugin_id, on in sorted(state.items()):
            status = "installed, enabled" if on else "installed, disabled"
            rows.append(f"{plugin_id:<20}{status:<21}1.0.0    local")
        return tools.Result(0, "\n".join(rows) + "\n")

    def _npm(self, argv):
        if argv[1] == "ls":
            body = {"dependencies": {"lavish-axi": {"version": self.lavish}}} if self.lavish else {}
            import json
            return tools.Result(0, json.dumps(body))
        if self.npm_fails:
            return tools.Result(1, "", "npm failed")
        if argv[1] == "install":
            self.lavish = argv[3].split("@", 1)[1]
        elif argv[1] == "uninstall":
            self.lavish = None
        return tools.Result(0)


@pytest.fixture
def env(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {"USERPROFILE": str(home), "HOME": str(home), "LOCALAPPDATA": str(tmp_path / "local"),
            "PATH": os.environ.get("PATH", "")}


@pytest.fixture
def places(env):
    return Places.from_env(env)


@pytest.fixture
def runner(places):
    return FakeRunner(places)


@pytest.fixture
def system(runner):
    return setup.System(run=runner, windows=False, add_to_user_path=lambda _f: False,
                        is_terminal=lambda: True)


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=git_env(tmp_path / "home"))
    return path


@pytest.fixture
def plugin_root(tmp_path):
    root = tmp_path / "plugin"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks" / "core-behaviors.txt").write_text(
        f"afkv2-core-behaviors begin {SHA}\nrule one\nafkv2-core-behaviors end {SHA}\n",
        encoding="utf-8")
    return root


def end_marker(sha: str = SHA) -> str:
    return f"afkv2-core-behaviors end {sha}"


def v1_block(eol: str = "\n") -> str:
    return eol.join(["<!-- afk:behaviors:start -->", "v1 rule", "<!-- afk:behaviors:end -->"]) + eol


def v1_stub(hook: str) -> bytes:
    marker = "afk-precommit-gates" if hook == "pre-commit" else "afk-branch-name-gate"
    return (f"#!/usr/bin/env bash\n# {marker} (installed by afk-toolkit install-git-hooks.sh).\n"
            "# afk-plugin-root: /v1\nexec bash /v1/hooks/gate \"$@\"\n").encode("utf-8")


def hooks_dir(repo: Path) -> Path:
    return repo / ".git" / "hooks"


def write_codex_config(places: Places, afk_on: bool = True, new_on: bool = True) -> str:
    text = ("model = \"x\"\n\n"
            f"[plugins.\"{V1_ID}\"]\nenabled = {str(afk_on).lower()}\n\n"
            f"[plugins.\"{NEW_ID}\"]\nenabled = {str(new_on).lower()}\n")
    places.codex_config.parent.mkdir(parents=True, exist_ok=True)
    places.codex_config.write_text(text, encoding="utf-8")
    return text


def fire(places: Places, provider: str, later: float = 5.0) -> None:
    """Write a fired record newer than the install record."""
    record = places.fired_record(provider)
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text("fired\n", encoding="utf-8")
    installed = setup.read_install_record(places).get("installed")
    if installed:
        from datetime import datetime
        stamp = datetime.fromisoformat(installed).timestamp() + later
        os.utime(record, (stamp, stamp))
