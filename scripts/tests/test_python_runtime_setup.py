"""Setup's afk-python transaction, run against a stubbed command runner."""
from __future__ import annotations

import ast
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN_ROOT / "skills" / "afk" / "setup" / "scripts" / "python_runtime.py"
spec = importlib.util.spec_from_file_location("python_runtime", SCRIPT)
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)
PINS = pr.pins()
FIND_BASH = pr.find_bash
FRESH_PATH = pr.fresh_path

DRIFT = ("Would uninstall 1 package\nWould install 1 package\n - idna==3.6\n + idna==3.20\n"
         "error: The environment is outdated; run `uv sync` to update the environment")


class Machine:
    """Answers each command the way a healthy uv and launcher would, and records it."""

    def __init__(self, paths: dict, *, uv_version: str | None = None, fail: str | None = None,
                 said: str = "error: simulated failure", reported: str | None = None,
                 in_sync: tuple[int, str] = (0, "Checked 41 packages\nWould make no changes"),
                 lookup=None):
        self.paths, self.calls = paths, []
        self.uv_version, self.fail, self.said, self.in_sync = uv_version, fail, said, in_sync
        self.reported = reported or "\t".join([PINS["python"], str(paths["launcher"]), str(paths["env"])])
        # The hook bash's lookup half: what it prints, or a real run when `lookup` is given; the
        # interpreter half answers `reported`, as every other shell does here.
        self.lookup = lookup or (lambda argv, env: (
            0, f"afk-command\t/spelled/afk-python\t/spelled/{paths['launcher'].name}\tentry"))

    def __call__(self, argv, env):
        self.calls.append((argv, dict(env)))
        line = argv if isinstance(argv, str) else " ".join(map(str, argv))
        if self.fail and self.fail in line:
            return 1, self.said
        if line.endswith("--version") and str(self.paths["uv"]) in line:
            return (0, f"uv {self.uv_version} (abc)") if self.uv_version else (127, "not found")
        if " sync " in line and "--check" in line:
            return self.in_sync
        if " sync " in line:
            self.paths["interpreter"].parent.mkdir(parents=True, exist_ok=True)
            self.paths["interpreter"].write_text("interpreter", encoding="utf-8")
            self.paths["interpreter"].chmod(0o755)
            for windows in (True, False):
                pr.site_packages(self.paths, PINS["python"], windows).mkdir(parents=True, exist_ok=True)
        if "afk-command" in line:
            code, said = self.lookup(argv, env)
            return (0, said.strip() + "\n" + self.reported) if "afk-command" in said else (code or 127, said)
        if "afk-python -c" in line:
            return 0, self.reported
        return 0, ""

    def lines(self) -> list[str]:
        return [a if isinstance(a, str) else " ".join(map(str, a)) for a, _ in self.calls]


@pytest.fixture(autouse=True)
def windows_shells_anywhere(monkeypatch):
    # Windows-layout cases run on any host: no registry read, no Git Bash lookup.
    monkeypatch.setattr(pr, "fresh_path", lambda env, windows: env.get("PATH", ""))
    monkeypatch.setattr(pr, "find_bash", lambda: None)


def machine_env(tmp_path: Path) -> dict:
    return {"HOME": str(tmp_path / "home"), "LOCALAPPDATA": str(tmp_path / "local"),
            "PATH": os.environ.get("PATH", ""), "SHELL": "/bin/bash"}


def test_plan_names_the_pinned_steps_and_changes_nothing(tmp_path):
    env = dict(os.environ, LOCALAPPDATA=str(tmp_path / "local"), HOME=str(tmp_path / "home"),
               XDG_DATA_HOME=str(tmp_path / "data"))
    done = subprocess.run([sys.executable, str(SCRIPT), "plan"], env=env, capture_output=True,
                          text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert f"/download/{PINS['uv']}/uv-installer." in done.stdout
    assert f"python install {PINS['python']} --no-bin" in done.stdout
    sync = next(l for l in done.stdout.splitlines() if "sync --project" in l)
    assert "--frozen --no-build" in sync and "--compile-bytecode" in sync
    assert "--extra test" not in done.stdout
    assert list(tmp_path.iterdir()) == []
    with_test = subprocess.run([sys.executable, str(SCRIPT), "plan", "--test"], env=env,
                               capture_output=True, text=True, timeout=60)
    assert "--extra test" in with_test.stdout


@pytest.mark.parametrize("windows", [True, False])
def test_layout_keeps_everything_under_one_private_home(tmp_path, windows):
    env = machine_env(tmp_path)
    paths = pr.layout(env, windows)
    if windows:
        assert paths["env"] == tmp_path / "local" / "afk" / "python"
        assert paths["launcher"] == paths["env"] / "afk-bin" / "afk-python.exe"
        assert paths["interpreter"] == paths["env"] / "Scripts" / "python.exe"
    else:
        assert paths["env"] == tmp_path / "home" / ".local" / "share" / "afk" / "python"
        assert paths["launcher"] == paths["env"] / "afk-bin" / "afk-python"
        xdg = pr.layout(dict(env, XDG_DATA_HOME=str(tmp_path / "d")), False)
        assert xdg["env"] == tmp_path / "d" / "afk" / "python"
    # The entry finds pyvenv.cfg one level up, which makes sys.prefix the environment.
    assert paths["bin"].parent == paths["env"] and paths["launcher"].parent == paths["bin"]


def test_install_runs_the_transaction_in_order_then_publishes_the_stamp(tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "find_bash", lambda: "/git/bin/bash")
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    machine, out = Machine(paths), io.StringIO()
    code = pr.install(env, True, False, machine, out)
    assert code == 0, out.getvalue()
    lines = machine.lines()
    order = [next(i for i, l in enumerate(lines) if marker in l) for marker in
             ("uv-installer.ps1", "python install", " sync ", "tool update-shell", "--check", "afk-python -c")]
    assert order == sorted(order)
    installer_env = next(e for a, e in machine.calls if "uv-installer" in str(a))
    assert installer_env["UV_UNMANAGED_INSTALL"] == str(paths["uv"].parent)
    sync_env = next(e for a, e in machine.calls if "sync" in str(a))
    assert sync_env["UV_PROJECT_ENVIRONMENT"] == str(paths["env"])
    assert sync_env["UV_PYTHON_INSTALL_DIR"] == str(paths["pythons"])
    assert sync_env["UV_TOOL_BIN_DIR"] == str(paths["bin"])
    assert "VIRTUAL_ENV" not in sync_env
    assert paths["launcher"].read_text(encoding="utf-8") == "interpreter"
    pth = pr.site_packages(paths, PINS["python"], True) / pr.PTH
    assert pth.read_bytes() == b'import os, sys; os.environ.setdefault("AFK_PYTHON", sys.executable)\n'
    # The hook shell's own spelling, verbatim: setup never derives it from the launcher path.
    assert pr.read_stamp(paths) == {
        "python": PINS["python"], "uv": PINS["uv"], "lock": PINS["lock"], "extras": "",
        "launcher": str(paths["launcher"]), "command": "/spelled/afk-python", "file": "/spelled/afk-python.exe"}
    # One identity probe, in the hooks' bash, after every interpreter probe.
    hook = [a for a, _ in machine.calls if "afk-command" in str(a)]
    assert len(hook) == 1 and hook[0][:2] == ["/git/bin/bash", "-c"]
    # Lookup, then the interpreter probe, with the installed entry as $1 for `-ef`.
    assert hook[0][2].startswith(pr.RESOLVE + "; afk-python -c ") and hook[0][3:] == ["afk-hook", str(paths["launcher"])]
    others = [i for i, l in enumerate(lines) if "afk-python -c" in l and "afk-command" not in l]
    assert lines.index(" ".join(hook[0])) > max(others)
    assert not paths["stamp"].with_name(pr.STAMP + ".new").exists()
    report = out.getvalue()
    # Published only after the last shell probe passed.
    assert report.index("ok hook bash") < report.index("ok stamp published")
    assert "Restart the harness" in report


def test_install_skips_the_uv_installer_when_the_pinned_uv_is_present(tmp_path):
    env = machine_env(tmp_path)
    machine = Machine(pr.layout(env, True), uv_version=PINS["uv"])
    assert pr.install(env, True, False, machine, io.StringIO()) == 0
    assert not any("uv-installer" in l for l in machine.lines())


@pytest.mark.parametrize("windows", [True, False])
def test_a_bin_directory_the_startup_files_already_add_is_not_added_again(tmp_path, monkeypatch, windows):
    if not windows and os.name == "nt":
        pytest.skip("the POSIX layout symlinks the launcher, which needs privileges here")
    env = machine_env(tmp_path)
    paths = pr.layout(env, windows)
    # Spelled the way PATH entries drift: case on Windows, a trailing separator anywhere.
    entry = str(paths["bin"]).upper() + "\\" if windows else str(paths["bin"]) + "/"
    sep = ";" if windows else ":"
    monkeypatch.setattr(pr, "fresh_path", lambda env, windows: sep.join([entry, env.get("PATH", "")]))
    machine, out = Machine(paths), io.StringIO()
    assert pr.install(env, windows, False, machine, out) == 0, out.getvalue()
    assert "ok path already set" in out.getvalue()
    assert not any("update-shell" in l for l in machine.lines())


@pytest.mark.parametrize("windows", [True, False])
def test_an_entry_only_this_process_has_on_path_is_still_persisted(tmp_path, windows):
    if not windows and os.name == "nt":
        pytest.skip("the POSIX layout symlinks the launcher, which needs privileges here")
    env = machine_env(tmp_path)
    paths = pr.layout(env, windows)
    sep = ";" if windows else ":"
    env["PATH"] = sep.join([str(paths["bin"]), env["PATH"]])
    machine, out = Machine(paths), io.StringIO()
    assert pr.install(env, windows, False, machine, out) == 0, out.getvalue()
    assert "ok path\n" in out.getvalue()
    probe_envs = [e for a, e in machine.calls if "afk-python -c" in str(a)]
    if windows:
        shell_env = next(e for a, e in machine.calls if "update-shell" in str(a))
        assert not pr.on_path(paths["bin"], shell_env["PATH"], windows)
    else:
        assert pr.path_line(paths) in (tmp_path / "home" / ".bashrc").read_text(encoding="utf-8")
    assert probe_envs and all(not pr.on_path(paths["bin"], e["PATH"], windows) for e in probe_envs)


def posix_entry(monkeypatch):
    def entry_only(paths, python, windows):
        paths["launcher"].parent.mkdir(parents=True, exist_ok=True)
        paths["launcher"].write_text("", encoding="utf-8")

    monkeypatch.setattr(pr, "place_entry", entry_only)


@pytest.mark.parametrize("shell, existing, written", [
    ("/bin/bash", [], [".bash_profile", ".bashrc"]),
    ("/bin/bash", [".profile"], [".profile", ".bashrc"]),
    ("/usr/bin/zsh", [], [".zshenv"]),
    ("/bin/ksh", [], [".profile", ".kshrc"]),
    ("/bin/dash", [], [".profile"]),
    (None, [], [".profile"]),
])
def test_posix_setup_writes_the_login_shells_startup_files_itself(tmp_path, monkeypatch, shell, existing, written):
    posix_entry(monkeypatch)
    env = dict(machine_env(tmp_path), XDG_DATA_HOME=str(tmp_path / "data"))
    env.pop("SHELL")
    if shell:
        env["SHELL"] = shell
    # The parent shell's markers, as a runner with pwsh installed exports them: uv would guess PowerShell.
    env.update(PSModulePath="/opt/microsoft/powershell/7/Modules", BASH_VERSION="5.2")
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    for name in existing:
        (home_dir / name).write_text("umask 022", encoding="utf-8")
    paths = pr.layout(env, False)
    for _ in range(2):
        machine, out = Machine(paths), io.StringIO()
        assert pr.install(env, False, False, machine, out) == 0, out.getvalue()
        assert not any("update-shell" in l for l in machine.lines())
    line = pr.path_line(paths)
    assert sorted(p.name for p in home_dir.iterdir()) == sorted(set(existing) | set(written))
    for name in written:
        text = (home_dir / name).read_text(encoding="utf-8")
        assert text.splitlines().count(line) == 1, text
        if name in existing:
            assert text.startswith("umask 022\n")


def test_zsh_setup_writes_an_existing_zdotdir_zshenv(tmp_path, monkeypatch):
    posix_entry(monkeypatch)
    zdot = tmp_path / "zdot"
    zdot.mkdir()
    (zdot / ".zshenv").write_text("", encoding="utf-8")
    env = dict(machine_env(tmp_path), SHELL="/bin/zsh", ZDOTDIR=str(zdot))
    paths = pr.layout(env, False)
    assert pr.install(env, False, False, Machine(paths), io.StringIO()) == 0
    assert pr.path_line(paths) in (zdot / ".zshenv").read_text(encoding="utf-8")
    assert not (tmp_path / "home" / ".zshenv").exists()


@pytest.mark.parametrize("windows", [True, False])
def test_uv_writes_only_for_the_shell_setup_names(tmp_path, monkeypatch, windows):
    if not windows:
        posix_entry(monkeypatch)
    hints = {"PSModulePath": "/m", "BASH_VERSION": "5", "ZSH_VERSION": "5", "NU_VERSION": "1"}
    env = dict(machine_env(tmp_path), SHELL="/usr/bin/fish", **hints)
    paths = pr.layout(env, windows)
    machine = Machine(paths)
    assert pr.install(env, windows, False, machine, io.StringIO()) == 0
    seen = next(e for a, e in machine.calls if "update-shell" in str(a))
    if windows:
        # PowerShell or cmd: both write the user PATH in the registry, which a new terminal reads.
        assert seen["PSModulePath"] == "/m" and not {"SHELL", "BASH_VERSION", "ZSH_VERSION", "NU_VERSION"} & set(seen)
    else:
        assert seen["SHELL"] == "/usr/bin/fish" and not set(hints) & set(seen)


@pytest.mark.skipif(os.name == "nt", reason="a POSIX login shell reading POSIX startup files")
@pytest.mark.parametrize("shell", ["/bin/sh", "/bin/bash"])
def test_a_new_login_shell_finds_the_written_line(tmp_path, shell):
    if not Path(shell).exists():
        pytest.skip(f"{shell} absent")
    env = {"HOME": str(tmp_path), "SHELL": shell, "PATH": "/usr/bin:/bin"}
    paths = pr.layout(env, False)
    pr.add_to_startup(pr.startup_files(env), pr.path_line(paths))
    assert pr.on_path(paths["bin"], FRESH_PATH(env, False), False)


def test_the_installer_and_uv_never_see_the_users_source_overrides(tmp_path):
    env = machine_env(tmp_path)
    hostile = {
        "UV_DOWNLOAD_URL": "https://evil.example/uv.zip", "INSTALLER_DOWNLOAD_URL": "https://evil.example",
        "UV_INSTALLER_GITHUB_BASE_URL": "https://evil.example", "UV_INSTALLER_GHE_BASE_URL": "https://evil.example",
        "UV_GITHUB_TOKEN": "t", "UV_INSTALL_DIR": "/elsewhere", "CARGO_DIST_FORCE_INSTALL_DIR": "/elsewhere",
        "UV_INDEX_URL": "https://evil.example/simple", "UV_DEFAULT_INDEX": "https://evil.example/simple",
        "UV_EXTRA_INDEX_URL": "https://evil.example/simple", "UV_INDEX": "evil=https://evil.example/simple",
        "UV_FIND_LINKS": "https://evil.example/wheels", "UV_PYTHON_INSTALL_MIRROR": "https://evil.example/py",
        "UV_PYTHON_DOWNLOADS_JSON_URL": "https://evil.example/py.json", "UV_PYTHON": "3.9",
        "UV_INSECURE_HOST": "evil.example", "UV_CONFIG_FILE": "/evil/uv.toml", "UV_OVERRIDE": "/evil/o.txt",
        "UV_CACHE_DIR": "/shared/cache", "VIRTUAL_ENV": "/some/venv",
    }
    kept = {"HTTPS_PROXY": "http://proxy:3128", "HTTP_PROXY": "http://proxy:3128", "NO_PROXY": "corp",
            "SSL_CERT_FILE": "/corp/ca.pem", "SSL_CERT_DIR": "/corp/certs", "REQUESTS_CA_BUNDLE": "/corp/ca.pem",
            "UV_NATIVE_TLS": "1", "UV_SYSTEM_CERTS": "1",
            # Transport only: how long and how often uv talks to the sources the lock names.
            "UV_HTTP_TIMEOUT": "300", "UV_HTTP_CONNECT_TIMEOUT": "60", "UV_REQUEST_TIMEOUT": "300",
            "UV_HTTP_RETRIES": "8", "UV_CONCURRENT_DOWNLOADS": "2"}
    env.update(hostile, **kept)
    paths = pr.layout(env, True)
    machine = Machine(paths)
    assert pr.install(env, True, False, machine, io.StringIO()) == 0
    uv_calls = [e for a, e in machine.calls if "afk-python -c" not in str(a)]
    assert any("uv-installer" in str(a) for a, _ in machine.calls)
    for seen in uv_calls:
        assert not {k for k in hostile if k != "UV_CACHE_DIR"} & set(seen), sorted(set(hostile) & set(seen))
        assert seen["UV_CACHE_DIR"] == str(paths["cache"])
        assert {k: seen.get(k) for k in kept} == kept


def test_a_platform_without_wheels_fails_the_sync_with_a_plain_reason(tmp_path):
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    said = ("error: Distribution `cryptography==50.0.2 @ registry+https://pypi.org/simple` can't be "
            "installed because it is marked as `--no-build` but has no binary distribution")
    machine, out = Machine(paths, fail=" sync ", said=said), io.StringIO()
    assert pr.install(env, True, False, machine, out) == 1
    assert "fail environment: error: Distribution `cryptography==50.0.2" in out.getvalue()
    assert "afk-python is not supported here yet" in out.getvalue()
    assert any(" sync " in l and "--no-build" in l for l in machine.lines())


def previous_install(paths: dict) -> None:
    paths["env"].mkdir(parents=True, exist_ok=True)
    paths["stamp"].write_text(f"python={PINS['python']}\nlock={PINS['lock']}\nextras=\n", encoding="utf-8")


def test_a_repair_that_fails_part_way_leaves_no_stamp(tmp_path):
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    previous_install(paths)
    machine, out = Machine(paths, fail=" sync "), io.StringIO()
    assert pr.install(env, True, False, machine, out) == 1
    assert "fail environment: error: simulated failure" in out.getvalue()
    assert not any("update-shell" in l for l in machine.lines())
    assert not paths["stamp"].exists()


@pytest.mark.parametrize("machine_kwargs, reason", [
    ({"reported": "3.12.1\t/x/afk-python\t{env}"}, "runs Python 3.12.1"),
    ({"in_sync": (1, DRIFT)}, "fail packages"),
])
def test_a_repair_whose_final_probe_fails_leaves_no_stamp(tmp_path, machine_kwargs, reason):
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    previous_install(paths)
    if "reported" in machine_kwargs:
        machine_kwargs = {"reported": machine_kwargs["reported"].replace("{env}", str(paths["env"]))}
    machine, out = Machine(paths, **machine_kwargs), io.StringIO()
    assert pr.install(env, True, False, machine, out) == 1
    assert reason in out.getvalue()
    assert "ok stamp published" not in out.getvalue()
    assert not paths["stamp"].exists()
    assert not paths["stamp"].with_name(pr.STAMP + ".new").exists()


def test_a_failed_repair_does_not_cost_the_test_extra(tmp_path):
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    assert pr.install(env, True, True, Machine(paths), io.StringIO()) == 0
    # The repair dies in the sync, the environment keeps nothing of pytest, and the stamp is gone.
    failing = Machine(paths, fail="uv-installer")
    first_call = failing.__call__

    def records_intent_first(argv, env):
        if not failing.calls:
            assert paths["intent"].read_text(encoding="utf-8").strip() == "test"
        return first_call(argv, env)

    assert pr.install(env, True, False, records_intent_first, io.StringIO()) == 1
    assert pr.install(env, True, False, Machine(paths, fail=" sync "), io.StringIO()) == 1
    site = pr.site_packages(paths, PINS["python"], True)
    assert not paths["stamp"].exists() and not list(site.glob("pytest*"))
    machine = Machine(paths)
    assert pr.install(env, True, False, machine, io.StringIO()) == 0
    syncs = [l for l in machine.lines() if " sync " in l]
    assert syncs and all("--extra test" in l for l in syncs)
    assert pr.read_stamp(paths)["extras"] == "test"


@pytest.mark.parametrize("unreadable", [
    "a directory",
    pytest.param("mode 000", marks=pytest.mark.skipif(
        os.name == "nt" or os.geteuid() == 0, reason="needs POSIX permissions and a non-root user")),
])
def test_an_unreadable_intent_file_stops_setup_before_it_changes_anything(tmp_path, unreadable):
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    previous_install(paths)
    if unreadable == "a directory":
        paths["intent"].mkdir(parents=True)
    else:
        paths["intent"].write_text("test\n", encoding="utf-8")
        paths["intent"].chmod(0)
    machine, out = Machine(paths), io.StringIO()
    try:
        assert pr.install(env, True, False, machine, out) == 1
    finally:
        if unreadable == "mode 000":
            paths["intent"].chmod(0o644)
    assert f"fail extras: cannot read {paths['intent']}" in out.getvalue()
    assert machine.calls == [] and paths["stamp"].exists()
    if unreadable == "a directory":
        assert paths["intent"].is_dir()
    else:
        assert paths["intent"].read_text(encoding="utf-8") == "test\n"


def test_a_runtime_that_has_the_test_extra_keeps_it(tmp_path):
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    paths["env"].mkdir(parents=True)
    paths["stamp"].write_text("extras=test\n", encoding="utf-8")
    machine = Machine(paths)
    assert pr.install(env, True, False, machine, io.StringIO()) == 0
    syncs = [l for l in machine.lines() if " sync " in l]
    assert syncs and all("--extra test" in l for l in syncs)
    assert any("import pytest" in l for l in machine.lines())
    assert pr.read_stamp(paths)["extras"] == "test"


def stamped(tmp_path: Path, **override) -> tuple[dict, dict]:
    env = machine_env(tmp_path)
    paths = pr.layout(env, False)
    paths["env"].mkdir(parents=True)
    paths["launcher"].parent.mkdir(parents=True)
    paths["launcher"].write_text("", encoding="utf-8")
    values = {"python": PINS["python"], "uv": PINS["uv"], "lock": PINS["lock"], "extras": ""}
    values.update(override)
    paths["stamp"].write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    return env, paths


def test_check_passes_a_healthy_runtime_from_every_shell(tmp_path):
    env, paths = stamped(tmp_path)
    machine, out = Machine(paths), io.StringIO()
    assert pr.check(env, False, False, machine, out) == 0, out.getvalue()
    probes = [l for l in machine.lines() if "afk-python -c" in l]
    assert len(probes) == 2
    for module in PINS["imports"]:
        assert all(f"import {module};" in l for l in probes)
    assert all(e.get("AFK_PYTHON") is None for a, e in machine.calls)
    in_sync = next(a for a, e in machine.calls if "--check" in str(a))
    assert {"--frozen", "--no-build", "--offline", "--check"} <= set(in_sync)
    assert "--extra" not in in_sync


def test_check_compares_the_test_extra_too_when_the_runtime_has_it(tmp_path):
    env, paths = stamped(tmp_path, extras="test")
    machine = Machine(paths)
    assert pr.check(env, False, False, machine, io.StringIO()) == 0
    in_sync = next(a for a, e in machine.calls if "--check" in str(a))
    assert in_sync[in_sync.index("--extra") + 1] == "test"


def test_check_after_a_failed_install_compares_the_requested_extra(tmp_path):
    env, paths = stamped(tmp_path)
    paths["stamp"].unlink()
    paths["intent"].write_text("test\n", encoding="utf-8")
    machine = Machine(paths)
    assert pr.check(env, False, False, machine, io.StringIO()) == 1
    in_sync = next(a for a, e in machine.calls if "--check" in str(a))
    assert in_sync[in_sync.index("--extra") + 1] == "test"


@pytest.mark.parametrize("override, reported, expected", [
    ({"lock": "0" * 64}, None, "fail lock"),
    ({"python": "3.13.0"}, None, "fail stamp: want Python"),
    ({}, "3.12.1\t/x/afk-python\t{env}", "runs Python 3.12.1"),
    ({}, f"{PINS['python']}\t/x/afk-python\t/usr", "want the environment"),
    ({}, f"{PINS['python']}\t-\t{{env}}", "afk_python.pth is missing"),
    ({}, f"{PINS['python']}\t/old/bin/afk-python\t{{env}}", "resolves to /old/bin/afk-python"),
    ({}, "Python 3.14.8", "fail sh: Python 3.14.8"),
])
def test_check_names_each_kind_of_drift(tmp_path, override, reported, expected):
    env, paths = stamped(tmp_path, **override)
    reported = reported and reported.replace("{env}", str(paths["env"]))
    machine, out = Machine(paths, reported=reported), io.StringIO()
    assert pr.check(env, False, False, machine, out) == 1
    assert expected in out.getvalue()


def test_check_fails_when_the_hooks_bash_finds_another_file_than_the_stamp_names(tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "find_bash", lambda: "/usr/bin/bash")
    env, paths = stamped(tmp_path, command="/old/afk-python", file="/old/afk-python")
    machine, out = Machine(paths), io.StringIO()
    assert pr.check(env, False, False, machine, out) == 1
    assert "fail hook bash: the stamp names /old/afk-python, the hooks' bash finds /spelled/afk-python" \
        in out.getvalue()
    assert "ok sh" in out.getvalue() and "ok bash login" in out.getvalue()


def test_check_fails_when_the_hooks_bash_finds_no_afk_python(tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "find_bash", lambda: "/usr/bin/bash")
    env, paths = stamped(tmp_path)
    machine, out = Machine(paths, lookup=lambda argv, env: (1, "")), io.StringIO()
    assert pr.check(env, False, False, machine, out) == 1
    assert "fail hook bash: /usr/bin/bash finds no afk-python" in out.getvalue()


@pytest.mark.parametrize("said, expected", [
    (f"afk-command\t/spelled/afk-python\t/elsewhere/afk-python\tother",
     "fail hook bash: resolves /elsewhere/afk-python, not the installed entry"),
    (f"afk-command\t/spelled/afk-python\t/spelled/afk-python\tentry\n3.12.1\t/x\t/usr",
     "fail hook bash: afk-python runs Python 3.12.1"),
])
def test_a_hook_bash_lookup_that_is_not_the_validated_entry_never_reaches_the_stamp(tmp_path, monkeypatch,
                                                                                    said, expected):
    monkeypatch.setattr(pr, "find_bash", lambda: "/git/bin/bash")
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    machine, out = Machine(paths), io.StringIO()
    hook_said = said if "\n" in said else said + "\n" + machine.reported

    def hook_answers(argv, env):
        return (0, hook_said) if "afk-command" in str(argv) else machine(argv, env)

    assert pr.install(env, True, False, hook_answers, out) == 1
    assert expected in out.getvalue()
    assert "ok cmd" in out.getvalue() and "ok git-bash" in out.getvalue()
    assert not paths["stamp"].exists()


def test_a_login_shell_that_is_not_posix_still_gets_a_published_stamp(tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "find_bash", lambda: "/usr/bin/bash")

    def entry_only(paths, python, windows):
        paths["launcher"].parent.mkdir(parents=True, exist_ok=True)
        paths["launcher"].write_text("", encoding="utf-8")

    monkeypatch.setattr(pr, "place_entry", entry_only)
    env = dict(machine_env(tmp_path), SHELL="/usr/bin/fish")
    paths = pr.layout(env, False)
    machine, out = Machine(paths), io.StringIO()

    def fish(argv, env):
        # fish rejects a statement that starts with a bash assignment such as `p=$(...)`.
        if isinstance(argv, list) and argv[0] == "/usr/bin/fish" and re.match(r"\w+=", argv[-1]):
            return 127, "fish: Unsupported use of '='. In fish, please use 'set p ...'."
        return machine(argv, env)

    assert pr.install(env, False, False, fish, out) == 0, out.getvalue()
    assert "ok fish login" in out.getvalue() and "ok hook bash" in out.getvalue()
    assert pr.read_stamp(paths)["command"] == "/spelled/afk-python"
    hook = [a for a, _ in machine.calls if "afk-command" in str(a)]
    assert len(hook) == 1 and hook[0][0] == "/usr/bin/bash" and hook[0][2].startswith(pr.RESOLVE)


def test_check_fails_when_a_package_drifts_after_the_stamp(tmp_path):
    env, paths = stamped(tmp_path)
    machine, out = Machine(paths, in_sync=(1, DRIFT)), io.StringIO()
    assert pr.check(env, False, False, machine, out) == 1
    assert "fail packages: differ from runtime/uv.lock: - idna==3.6, + idna==3.20" in out.getvalue()
    assert "ok lock" in out.getvalue()


def test_check_fails_when_the_command_does_not_resolve(tmp_path):
    env, paths = stamped(tmp_path)
    paths["launcher"].unlink()

    def missing(argv, env):
        return 127, "sh: afk-python: not found"

    out = io.StringIO()
    assert pr.check(env, False, False, missing, out) == 1
    assert "fail launcher" in out.getvalue() and "afk-python: not found" in out.getvalue()


def imported_modules(source: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
    return found


def test_the_probe_imports_the_modules_the_tracker_server_imports():
    probed = PINS["imports"]
    roots = {module.split(".")[0] for module in probed}
    needed = {m for m in imported_modules(PLUGIN_ROOT / "mcp-servers" / "tracker" / "server.py")
              if m.split(".")[0] in roots}
    assert needed, "the tracker server imports no runtime package"
    for module in needed:
        assert any(p == module or p.startswith(module + ".") for p in probed), module
    assert f"import {'mcp.server.fastmcp'};" in pr.probe_code(probed)


WINDOWS = os.name == "nt"


def real_lookup(bash: str):
    """The hook probe's lookup half, run for real: the same env and `$1`, interpreter half left out."""
    return lambda argv, env: pr.run([bash, "-c", pr.RESOLVE, *argv[3:]], env)


def bash_path(bash: str, flag: str, path: str) -> str:
    """Git Bash's own mount table, independent of the probe under test: `cygpath -u` or `-w`."""
    done = subprocess.run([bash, "-c", f'cygpath {flag} "$1"', "_", path], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def installed_stamp(base: Path, monkeypatch) -> tuple[dict, dict]:
    """Install with the hooks' real bash answering the identity probe; the stamp and layout."""
    bash = FIND_BASH()
    if not bash:
        pytest.skip("no POSIX shell")
    monkeypatch.setattr(pr, "find_bash", lambda: bash)
    env = machine_env(base)
    paths = pr.layout(env, WINDOWS)
    sep = ";" if WINDOWS else ":"
    # A new terminal's PATH carries the entry, as the startup files or the registry give it.
    monkeypatch.setattr(pr, "fresh_path", lambda env, windows: sep.join([str(paths["bin"]), env.get("PATH", "")]))
    out = io.StringIO()
    assert pr.install(env, WINDOWS, False, Machine(paths, lookup=real_lookup(bash)), out) == 0, out.getvalue()
    return pr.read_stamp(paths), paths


ONLY_GIT_BASH = pytest.mark.skipif(not WINDOWS, reason="only Git Bash drops .exe and has mount aliases")


@pytest.mark.parametrize("place", ["tmp_path", pytest.param("/tmp mount", marks=ONLY_GIT_BASH)])
def test_the_stamp_holds_the_hooks_bash_spelling_of_the_entry(tmp_path, monkeypatch, place):
    base = tmp_path
    if place == "/tmp mount":
        # Deliberately under Git Bash's /tmp mount, wherever --basetemp put tmp_path.
        base = Path(tempfile.mkdtemp(prefix="afk-alias-", dir=bash_path(FIND_BASH(), "-w", "/tmp")))
    try:
        stamp, paths = installed_stamp(base, monkeypatch)
        if WINDOWS:
            # The stamp holds what bash's mount table makes of the entry's directory, never a made-up /c/...
            assert stamp["command"] == bash_path(FIND_BASH(), "-u", str(paths["bin"])) + "/afk-python"
            assert stamp["file"] == stamp["command"] + ".exe"
            if place == "/tmp mount":
                assert stamp["command"].startswith("/tmp/afk-alias-")
        else:
            assert stamp["command"] == stamp["file"] == str(paths["launcher"])
    finally:
        if base != tmp_path:
            shutil.rmtree(base, ignore_errors=True)


@pytest.mark.skipif(not WINDOWS, reason="run-hook's shell_env prepends a toolchain only on Windows")
def test_a_shadow_in_the_toolchain_the_hook_launcher_prepends_fails_install(tmp_path, monkeypatch):
    bash = FIND_BASH()
    if not bash:
        pytest.skip("no POSIX shell")
    # A bash whose toolchain dirs are not on PATH yet: shell_env prepends them, shadow and all.
    toolchain = tmp_path / "git"
    for sub_dir in ("bin", "usr/bin"):
        (toolchain / sub_dir).mkdir(parents=True)
    hook_bash = toolchain / "bin" / "bash.exe"
    hook_bash.write_bytes(b"")
    (toolchain / "usr" / "bin" / "afk-python.exe").write_bytes(b"shadow")
    monkeypatch.setattr(pr, "find_bash", lambda: str(hook_bash))
    env = machine_env(tmp_path)
    paths = pr.layout(env, True)
    monkeypatch.setattr(pr, "fresh_path", lambda env, windows: ";".join([str(paths["bin"]), env.get("PATH", "")]))
    hook_envs = []

    def lookup(argv, env):
        hook_envs.append(env)
        return real_lookup(bash)(argv, env)

    machine, out = Machine(paths, lookup=lookup), io.StringIO()
    assert pr.install(env, True, False, machine, out) == 1, out.getvalue()
    assert hook_envs and hook_envs[0]["PATH"].startswith(str(toolchain / "bin"))
    assert f"fail hook bash: resolves {bash_path(bash, '-u', str(toolchain / 'usr' / 'bin'))}/afk-python.exe, " \
           "not the installed entry" in out.getvalue()
    assert "ok git-bash" in out.getvalue()
    assert not paths["stamp"].exists()
