"""Setup's afk-python transaction, run against a stubbed command runner."""
from __future__ import annotations

import ast
import importlib.util
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN_ROOT / "skills" / "afk" / "setup" / "scripts" / "python_runtime.py"
spec = importlib.util.spec_from_file_location("python_runtime", SCRIPT)
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)
PINS = pr.pins()
FIND_BASH = pr.find_bash

DRIFT = ("Would uninstall 1 package\nWould install 1 package\n - idna==3.6\n + idna==3.20\n"
         "error: The environment is outdated; run `uv sync` to update the environment")


class Machine:
    """Answers each command the way a healthy uv and launcher would, and records it."""

    def __init__(self, paths: dict, *, uv_version: str | None = None, fail: str | None = None,
                 said: str = "error: simulated failure", reported: str | None = None,
                 in_sync: tuple[int, str] = (0, "Checked 41 packages\nWould make no changes")):
        self.paths, self.calls = paths, []
        self.uv_version, self.fail, self.said, self.in_sync = uv_version, fail, said, in_sync
        self.reported = reported or "\t".join([PINS["python"], str(paths["launcher"]), str(paths["env"])])

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
            for windows in (True, False):
                pr.site_packages(self.paths, PINS["python"], windows).mkdir(parents=True, exist_ok=True)
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


def test_the_stamp_spells_the_launcher_the_way_a_posix_shell_finds_it():
    assert pr.shell_command(Path(r"C:\Users\Dev\AppData\Local\afk\python\afk-bin\afk-python.exe"), True) \
        == "/c/Users/Dev/AppData/Local/afk/python/afk-bin/afk-python"
    assert pr.shell_command(Path("/home/dev/.local/share/afk/python/afk-bin/afk-python"), False) \
        == str(Path("/home/dev/.local/share/afk/python/afk-bin/afk-python"))


def test_install_runs_the_transaction_in_order_then_publishes_the_stamp(tmp_path):
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
    assert pr.read_stamp(paths) == {
        "python": PINS["python"], "uv": PINS["uv"], "lock": PINS["lock"], "extras": "",
        "launcher": str(paths["launcher"]), "command": pr.shell_command(paths["launcher"], True)}
    assert not paths["stamp"].with_name(pr.STAMP + ".new").exists()
    report = out.getvalue()
    # Published only after the last shell probe passed.
    assert report.index("ok cmd") < report.index("ok stamp published")
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
    shell_env = next(e for a, e in machine.calls if "update-shell" in str(a))
    probe_envs = [e for a, e in machine.calls if "afk-python -c" in str(a)]
    assert probe_envs and not pr.on_path(paths["bin"], shell_env["PATH"], windows)
    assert all(not pr.on_path(paths["bin"], e["PATH"], windows) for e in probe_envs)


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
            "UV_NATIVE_TLS": "1"}
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


NOTICE = "AFK will switch to afk-python in the next release; run /afk:setup"


def session_notice(tmp_path: Path, *, command: bool, stamp: str | None, stamped_at: str = "same") -> str:
    bash = FIND_BASH()
    if not bash:
        pytest.skip("no POSIX shell")
    root = tmp_path / "plugin"
    (root / "runtime").mkdir(parents=True)
    (root / "runtime" / "pyproject.toml").write_bytes((PLUGIN_ROOT / "runtime" / "pyproject.toml").read_bytes())
    data = tmp_path / "data"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # Git Bash spells a pytest temp dir through its /tmp mount, which a stamp cannot predict.
    shell_path = subprocess.run([bash, "-c", 'cygpath -u "$1" 2>/dev/null || printf %s "$1"', "_", str(bin_dir)],
                                capture_output=True, text=True).stdout.strip()
    named = (shell_path if stamped_at == "same" else shell_path + "-other") + "/afk-python"
    if stamp is not None:
        (data / "afk" / "python").mkdir(parents=True)
        # A CRLF stamp: the notice must read either line ending.
        body = f"python={stamp}\r\ncommand={named}\r\n"
        (data / "afk" / "python" / "AFK-RUNTIME").write_bytes(body.encode())
    if command:
        launcher = bin_dir / "afk-python"
        launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        launcher.chmod(0o755)
    env = dict(os.environ, AFK_PLUGIN_ROOT=str(root), LOCALAPPDATA=str(data), XDG_DATA_HOME=str(data))
    script = PLUGIN_ROOT / "hooks" / "update-notice.sh"
    done = subprocess.run([bash, "-c", f'PATH="{shell_path}:/usr/bin:/bin"; . "$0"', str(script)],
                          env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout


@pytest.mark.parametrize("command, stamp, stamped_at, shown", [
    (False, None, "same", True),
    (True, None, "same", True),
    (True, "3.13.1", "same", True),
    (True, PINS["python"], "elsewhere", True),
    (True, PINS["python"], "same", False),
])
def test_the_session_notice_shows_until_the_stamped_entry_resolves(tmp_path, command, stamp, stamped_at, shown):
    out = session_notice(tmp_path, command=command, stamp=stamp, stamped_at=stamped_at)
    assert (NOTICE in out) is shown
