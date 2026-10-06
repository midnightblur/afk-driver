"""Setup's afk-python transaction, run against a stubbed command runner."""
from __future__ import annotations

import ast
import importlib.util
import io
import os
import re
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
                 in_sync: tuple[int, str] = (0, "Checked 41 packages\nWould make no changes"),
                 lookup=None):
        self.paths, self.calls = paths, []
        self.uv_version, self.fail, self.said, self.in_sync = uv_version, fail, said, in_sync
        self.reported = reported or "\t".join([PINS["python"], str(paths["launcher"]), str(paths["env"])])
        # What the hook shell's `command -v` prints; a real shell's answer when `lookup` is given.
        self.lookup = lookup or (lambda: f"afk-command\t/spelled/afk-python\t/spelled/{paths['launcher'].name}")

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
        if "afk-python -c" in line:
            return 0, (self.lookup() + "\n" if "afk-command" in line else "") + self.reported
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
    probes = {a[0]: a[-1] for a, _ in machine.calls if "afk-python -c" in str(a) and isinstance(a, list)}
    assert probes["/git/bin/bash"].startswith(pr.RESOLVE + "; ")
    assert "afk-command" not in probes["powershell"]
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


def test_check_fails_when_the_hook_shell_finds_another_file_than_the_stamp_names(tmp_path):
    env, paths = stamped(tmp_path, command="/old/afk-python", file="/old/afk-python")
    machine, out = Machine(paths), io.StringIO()
    assert pr.check(env, False, False, machine, out) == 1
    assert "fail bash login spelling: the stamp names /old/afk-python, the shell finds /spelled/afk-python" \
        in out.getvalue()
    assert "ok sh" in out.getvalue()


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
WINDOWS = os.name == "nt"


def shell_script(path: Path, text: str) -> None:
    # A native write: Git Bash's own redirection into `afk-python` would land in `afk-python.exe`.
    path.write_bytes(text.encode())
    path.chmod(0o755)


def session_notice(tmp_path: Path, monkeypatch, *, setup: bool, after: str = "") -> tuple[str, dict]:
    """Run setup's install with the real hook shell answering its lookup, alter the PATH per `after`,
    then run the SessionStart hook in that same shell and PATH."""
    bash = FIND_BASH()
    if not bash:
        pytest.skip("no POSIX shell")
    monkeypatch.setattr(pr, "find_bash", lambda: bash)
    root = tmp_path / "plugin"
    (root / "runtime").mkdir(parents=True)
    (root / "runtime" / "pyproject.toml").write_bytes((PLUGIN_ROOT / "runtime" / "pyproject.toml").read_bytes())
    env = machine_env(tmp_path)
    paths = pr.layout(env, WINDOWS)
    decoys = tmp_path / "decoys"
    decoys.mkdir()
    sep = ";" if WINDOWS else ":"
    shell_env = {k: v for k, v in os.environ.items() if not k.startswith(("XDG_", "AFK_"))}
    shell_env.update(HOME=env["HOME"], LOCALAPPDATA=env["LOCALAPPDATA"], AFK_PLUGIN_ROOT=str(root),
                     PATH=sep.join([str(paths["bin"])] + ([] if WINDOWS else ["/usr/bin", "/bin"])))

    def lookup() -> str:
        done = subprocess.run([bash, "-c", pr.RESOLVE], env=shell_env, capture_output=True, text=True, timeout=60)
        return done.stdout.strip()

    if setup:
        out = io.StringIO()
        assert pr.install(env, WINDOWS, False, Machine(paths, lookup=lookup), out) == 0, out.getvalue()
    stamp = pr.read_stamp(paths)
    if after == "old python":
        paths["stamp"].write_text(paths["stamp"].read_text(encoding="utf-8").replace(
            f"python={PINS['python']}", "python=3.13.1"), encoding="utf-8")
    elif after == "unstamped":
        paths["stamp"].unlink()
    elif after == "elsewhere":
        shell_script(decoys / "afk-python", "#!/bin/sh\nexit 0\n")
        shell_env["PATH"] = sep.join([str(decoys), shell_env["PATH"]])
    elif after == "replaced":
        paths["launcher"].unlink()
        shell_script(paths["bin"] / "afk-python", "#!/bin/sh\nexit 0\n")
    elif after == "beside":
        shell_script(paths["bin"] / "afk-python", "#!/bin/sh\nexit 0\n")
    script = PLUGIN_ROOT / "hooks" / "update-notice.sh"
    done = subprocess.run([bash, str(script)], env=shell_env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout, stamp


@pytest.mark.parametrize("setup, after, shown", [
    (False, "", True),
    (True, "unstamped", True),
    (True, "old python", True),
    (True, "elsewhere", True),
    pytest.param(True, "replaced", True, marks=pytest.mark.skipif(
        not WINDOWS, reason="only Git Bash drops .exe, so only there can a script take the entry's spelling")),
    pytest.param(True, "beside", True, marks=pytest.mark.skipif(not WINDOWS, reason="as above")),
    (True, "", False),
])
def test_the_session_notice_shows_until_the_stamped_file_resolves(tmp_path, monkeypatch, setup, after, shown):
    out, stamp = session_notice(tmp_path, monkeypatch, setup=setup, after=after)
    assert (NOTICE in out) is shown
    if setup and WINDOWS:
        # pytest's temp dir sits under Git Bash's /tmp mount: the stamp holds the alias, not /c/...
        assert stamp["command"].startswith("/tmp/") and not re.match(r"/[a-z]/", stamp["command"])
        assert stamp["file"] == stamp["command"] + ".exe"
    elif setup:
        assert stamp["command"] == stamp["file"] == str(pr.layout(machine_env(tmp_path), False)["launcher"])
