"""The browser driver, the judge model and the gh floor, through the setup verbs, with in-process fakes."""

from __future__ import annotations

import base64
import json
import socket
import tomllib
from pathlib import Path

import pytest

import other_provider
import setup
import mcp_entries
import tools
from conftest import FakeRunner

PIN = tools.DRIVER_VERSION
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode("ascii")


class DriverRunner(FakeRunner):
    """npm knows the driver package; node, gh, claude and codex are on the path."""

    def __init__(self, places, npm_root: Path):
        super().__init__(places)
        self.npm_root = npm_root
        self.driver: str | None = None
        self.driver_install_fails = False
        self.driver_env = None
        self.exe_in_package = False
        self.gh = "gh version 2.103.3 (2026-10-26)\n"
        self.paths.update({"node": "/node/node", "npm": "/node/npm", "gh": "/bin/gh", "claude": "/bin/claude",
                           "codex": "/bin/codex"})

    def __call__(self, argv, env=None, timeout=300):
        argv = list(argv)
        if argv[0] == "gh":
            self.calls.append(argv)
            return tools.Result(0, self.gh)
        if argv[0] != "npm" or not any(tools.DRIVER_PACKAGE in a for a in argv) and argv[1:3] != ["root", "-g"]:
            return super().__call__(argv, env, timeout)
        self.calls.append(argv)
        if argv[1:3] == ["root", "-g"]:
            return tools.Result(0, f"{self.npm_root}\n")
        if argv[1] == "ls":
            if not self.driver:
                return tools.Result(1, "{}")
            return tools.Result(0, json.dumps({"dependencies": {tools.DRIVER_PACKAGE: {"version": self.driver}}}))
        if self.driver_install_fails:
            return tools.Result(1, "", "npm ERR! network")
        self.driver = argv[3].rsplit("@", 1)[1]
        self.driver_env = env
        package = self.npm_root / tools.DRIVER_PACKAGE
        (package / "build" / "bin").mkdir(parents=True, exist_ok=True)
        (package / "build" / "bin" / "mcp.js").write_text("// server", encoding="utf-8")
        (package / "package.json").write_text(json.dumps(
            {"version": self.driver, "bin": {tools.DRIVER_PACKAGE: "./build/bin/mcp.js"}}), encoding="utf-8")
        if self.exe_in_package:
            (package / "helper.exe").write_bytes(b"MZ")
        return tools.Result(0)


class FakeSession:
    """An MCP server over stdio: each tool answers what Chrome DevTools MCP answers, unless broken."""

    started: list[list[str]] = []
    broken: str | None = None
    attach_fails = False

    def __init__(self, argv):
        FakeSession.started.append(list(argv))
        self.argv = list(argv)
        if FakeSession.broken == "start":
            raise tools.DriverError("the server exited: node: bad option")

    def call(self, tool, arguments):
        if tool == FakeSession.broken:
            return True, f"{tool} failed in the browser"
        if tool == "list_pages" and FakeSession.attach_fails:
            return True, "Could not connect to Chrome"
        answers = {
            "new_page": f"## Pages\n1: about:blank\n2: afkv2 proof ({arguments.get('url')}) [selected]",
            "list_pages": "## Pages\n1: Inbox (https://mail.example/) [selected]",
            "take_snapshot": '## Latest page snapshot\nuid=1_0 RootWebArea "afkv2 proof"\n  uid=1_1 button "Prove"\n',
            "click": "Successfully clicked on the element",
            "take_screenshot": [{"type": "text", "text": "Took a screenshot"}, {"type": "image", "data": PNG}],
            "list_console_messages": "## Console messages\nmsgid=1 [log] afkv2-proof-clicked (1 args)",
        }
        return False, answers[tool]

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fresh_session():
    FakeSession.started, FakeSession.broken, FakeSession.attach_fails = [], None, False


@pytest.fixture
def browsers(tmp_path):
    root = tmp_path / "pf"
    for parts in (("Google", "Chrome", "Application", "chrome.exe"), ("Microsoft", "Edge", "Application", "msedge.exe")):
        path = root.joinpath(*parts)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"")
    return root


@pytest.fixture
def driver_env(env, browsers):
    return {**env, "ProgramFiles": str(browsers)}


@pytest.fixture
def driver_runner(places, tmp_path):
    return DriverRunner(places, tmp_path / "npm-global")


@pytest.fixture
def driver_system(driver_runner):
    return setup.System(run=driver_runner, windows=False, add_to_user_path=lambda _f: False,
                        is_terminal=lambda: True, mcp_session=FakeSession)


def _cli(argv, env, system, repo, capsys, tmp_path):
    code = setup.main(argv, env=env, system=system, plugin_root=tmp_path / "plugin", cwd=repo)
    return code, json.loads(capsys.readouterr().out)


def _harness_files(places):
    places.claude_dir.mkdir(parents=True, exist_ok=True)
    places.claude_user_config.write_text(json.dumps({"numStartups": 3, "mcpServers": {"other": {"command": "x"}}}),
                                         encoding="utf-8")
    places.codex_config.parent.mkdir(parents=True, exist_ok=True)
    places.codex_config.write_text('model = "gpt-x"\n\n[mcp_servers.other]\ncommand = "y"\n', encoding="utf-8")


# ------------------------------------------------------------ browser-driver

def test_browser_driver_installs_the_pin_registers_both_harnesses_and_proves_4_runs(
        driver_env, places, repo, driver_runner, driver_system, capsys, tmp_path):
    _harness_files(places)
    code, answer = _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)
    assert code == 0, answer
    assert ["npm", "install", "-g", f"{tools.DRIVER_PACKAGE}@{PIN}"] in driver_runner.calls
    assert driver_runner.driver_env["PUPPETEER_SKIP_DOWNLOAD"] == "true"
    script = str(tmp_path / "npm-global" / tools.DRIVER_PACKAGE / "build" / "bin" / "mcp.js")
    claude = json.loads(places.claude_user_config.read_text(encoding="utf-8"))
    entry = claude["mcpServers"][tools.DRIVER_ENTRY]
    assert entry["command"] == "/node/node" and entry["args"][0] == script
    assert "--no-usage-statistics" in entry["args"]
    assert claude["numStartups"] == 3 and claude["mcpServers"]["other"] == {"command": "x"}
    codex = tomllib.loads(places.codex_config.read_text(encoding="utf-8"))
    assert codex["mcp_servers"][tools.DRIVER_ENTRY]["args"] == entry["args"]
    assert codex["model"] == "gpt-x" and codex["mcp_servers"]["other"] == {"command": "y"}
    runs = [(p["browser"], p["headless"], p["ok"]) for p in answer["proofs"]]
    assert sorted(runs) == [("chrome", False, True), ("chrome", True, True), ("edge", False, True), ("edge", True, True)]
    assert sum("--headless" in argv for argv in FakeSession.started) == 2
    assert setup.read_install_record(places)["browser_driver"].startswith(PIN + " ")


def test_browser_driver_backs_up_each_harness_file_before_the_write(
        driver_env, places, repo, driver_system, capsys, tmp_path):
    _harness_files(places)
    before = {p: p.read_bytes() for p in (places.claude_user_config, places.codex_config)}
    code, answer = _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)
    assert code == 0, answer
    for provider, path in (("claude", places.claude_user_config), ("codex", places.codex_config)):
        saved = Path(answer["register"][provider]["backup"])
        assert saved.read_bytes() == before[path], provider


def test_a_second_run_changes_no_entry_and_installs_nothing(
        driver_env, places, repo, driver_runner, driver_system, capsys, tmp_path):
    _harness_files(places)
    assert _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)[0] == 0
    after = {p: p.read_bytes() for p in (places.claude_user_config, places.codex_config)}
    driver_runner.calls.clear()
    code, answer = _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)
    assert code == 0 and answer["install"]["action"] == "present"
    assert not any(call[:2] == ["npm", "install"] for call in driver_runner.calls)
    assert {p: p.read_bytes() for p in after} == after


def test_a_harness_that_is_not_installed_gets_no_entry(driver_env, places, repo, driver_system, capsys, tmp_path):
    places.claude_dir.mkdir(parents=True)
    code, answer = _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)
    assert code == 0, answer
    assert answer["register"]["codex"]["action"] == "not-installed"
    assert not places.codex_config.exists()
    assert tools.DRIVER_ENTRY in json.loads(places.claude_user_config.read_text(encoding="utf-8"))["mcpServers"]


def test_no_browser_refuses_and_installs_nothing(env, places, repo, driver_runner, driver_system, capsys, tmp_path):
    code, answer = _cli(["browser-driver"], {**env, "ProgramFiles": str(tmp_path / "none")}, driver_system, repo,
                        capsys, tmp_path)
    assert (code, answer["error"]["code"]) == (1, "no-browser")
    assert not any(call[0] == "npm" for call in driver_runner.calls)


def test_a_failed_npm_install_refuses_driver_install_failed(
        driver_env, places, repo, driver_runner, driver_system, capsys, tmp_path):
    driver_runner.driver_install_fails = True
    code, answer = _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)
    assert (code, answer["error"]["code"]) == (1, "driver-install-failed")
    assert "network" in answer["error"]["reason"]


def test_an_executable_in_the_package_refuses_driver_install_failed(
        driver_env, places, repo, driver_runner, driver_system, capsys, tmp_path):
    driver_runner.exe_in_package = True
    code, answer = _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)
    assert (code, answer["error"]["code"]) == (1, "driver-install-failed")
    assert "helper.exe" in answer["error"]["reason"]


def test_a_global_folder_that_npm_masks_refuses_driver_install_failed(
        driver_env, places, repo, driver_runner, driver_system, capsys, tmp_path):
    driver_runner.driver = PIN
    driver_runner.npm_root = Path("C:/Users/x/***/npm")
    code, answer = _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)
    assert (code, answer["error"]["code"]) == (1, "driver-install-failed")
    assert answer["error"]["reason"].startswith("npm hid part of its global folder")


def test_the_install_puts_nothing_in_a_temp_folder(driver_env, places, repo, driver_runner, driver_system, capsys,
                                                   tmp_path):
    assert _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)[0] == 0
    install = next(c for c in driver_runner.calls if c[:2] == ["npm", "install"])
    assert install == ["npm", "install", "-g", f"{tools.DRIVER_PACKAGE}@{PIN}"]
    assert not any(k in driver_runner.driver_env for k in ("TMP", "TEMP", "TMPDIR")
                   if driver_runner.driver_env.get(k) != driver_env.get(k))


def test_an_unwritable_harness_file_refuses_register_failed_and_restores_the_backup(
        driver_env, places, repo, driver_system, capsys, tmp_path, monkeypatch):
    _harness_files(places)
    before = places.codex_config.read_bytes()
    real = mcp_entries.tomllib.loads

    def broken(text):
        if tools.DRIVER_ENTRY in text:
            raise mcp_entries.tomllib.TOMLDecodeError("bad table", text, 0)
        return real(text)

    monkeypatch.setattr(mcp_entries.tomllib, "loads", broken)
    code, answer = _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)
    assert (code, answer["error"]["code"]) == (1, "register-failed")
    assert places.codex_config.read_bytes() == before


def test_a_failed_proof_step_refuses_proof_failed_and_names_the_step(
        driver_env, places, repo, driver_system, capsys, tmp_path):
    _harness_files(places)
    FakeSession.broken = "take_screenshot"
    code, answer = _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)
    assert (code, answer["error"]["code"]) == (1, "proof-failed")
    assert {p["failed"] for p in answer["proofs"]} == {"screenshot"}
    assert "screenshot" in answer["error"]["reason"]
    assert "browser_driver" not in setup.read_install_record(places)


def test_a_server_that_does_not_start_fails_the_start_step(driver_env, places, repo, driver_system, capsys, tmp_path):
    FakeSession.broken = "start"
    code, answer = _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)
    assert (code, answer["error"]["code"]) == (1, "proof-failed")
    assert answer["proofs"][0]["failed"] == "start" and "bad option" in answer["proofs"][0]["reason"]


def test_prove_driver_reports_each_step_green():
    proof = tools.prove_driver({"command": "/node/node", "args": ["mcp.js", "--no-usage-statistics"]},
                               Path("/b/msedge.exe"), True, FakeSession, url="http://127.0.0.1:1/")
    assert proof["ok"] and proof["steps"] == {"open": "green", "click": "green", "screenshot": "green",
                                              "console": "green"}
    argv = FakeSession.started[-1]
    assert argv[:2] == ["/node/node", "mcp.js"] and "--headless" in argv and "--isolated" in argv
    assert argv[argv.index("--executablePath") + 1] == str(Path("/b/msedge.exe"))


def test_a_console_without_the_click_message_fails_the_console_step(monkeypatch):
    real = FakeSession.call

    def no_message(self, tool, arguments):
        return (False, "## Console messages\n<no console messages found>") if tool == "list_console_messages" \
            else real(self, tool, arguments)

    monkeypatch.setattr(FakeSession, "call", no_message)
    proof = tools.prove_driver({"command": "n", "args": []}, Path("c.exe"), False, FakeSession, url="http://h/")
    assert (proof["ok"], proof["failed"]) == (False, "console")


# -------------------------------------------------------------------- attach

@pytest.fixture
def debug_port():
    """A port on 127.0.0.1 that accepts connections, as a browser with remote debugging on."""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        yield server.getsockname()[1]


def _closed_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return server.getsockname()[1]


def _active_port(profile: Path, port: int) -> None:
    profile.mkdir(parents=True)
    (profile / "DevToolsActivePort").write_text(f"{port}\n/devtools/browser/x\n", encoding="utf-8")


def test_attach_with_remote_debugging_off_says_why_and_offers_the_fallbacks(
        driver_env, places, repo, driver_system, capsys, tmp_path):
    _harness_files(places)
    local = tmp_path / "local"
    code, answer = _cli(["browser-driver", "--attach", "edge"], {**driver_env, "LOCALAPPDATA": str(local)},
                        driver_system, repo, capsys, tmp_path)
    assert code == 0, answer
    attach = answer["attach"]
    assert attach["ok"] is False and "edge://inspect/#remote-debugging" in attach["why"]
    assert attach["offer"] == list(tools.ATTACH_FALLBACKS)
    assert not any("--autoConnect" in argv for argv in FakeSession.started)


def test_attach_to_a_debuggable_browser_registers_the_attach_entry(
        driver_env, places, repo, driver_system, capsys, tmp_path, debug_port):
    _harness_files(places)
    profile = tmp_path / "local" / "Google" / "Chrome" / "User Data"
    _active_port(profile, debug_port)
    code, answer = _cli(["browser-driver", "--attach", "chrome"], driver_env, driver_system, repo, capsys, tmp_path)
    assert code == 0 and answer["attach"]["ok"] is True, answer
    argv = FakeSession.started[-1]
    assert "--autoConnect" in argv and argv[argv.index("--userDataDir") + 1] == str(profile)
    entry = json.loads(places.claude_user_config.read_text(encoding="utf-8"))["mcpServers"][tools.ATTACH_ENTRY]
    assert "--autoConnect" in entry["args"] and "--no-usage-statistics" in entry["args"]
    assert tools.ATTACH_ENTRY in tomllib.loads(places.codex_config.read_text(encoding="utf-8"))["mcp_servers"]


def test_a_failed_attach_names_the_server_answer(driver_env, places, repo, driver_system, capsys, tmp_path,
                                                 debug_port):
    _harness_files(places)
    FakeSession.attach_fails = True
    _active_port(tmp_path / "local" / "Microsoft" / "Edge" / "User Data", debug_port)
    code, answer = _cli(["browser-driver", "--attach", "edge"], driver_env, driver_system, repo, capsys, tmp_path)
    assert code == 0
    assert answer["attach"]["ok"] is False and "Could not connect" in answer["attach"]["why"]
    assert tools.ATTACH_ENTRY not in json.loads(places.claude_user_config.read_text(encoding="utf-8"))["mcpServers"]


def test_attach_with_no_answer_names_the_permission_prompt_of_the_browser(
        driver_env, places, repo, driver_system, capsys, tmp_path, debug_port, monkeypatch):
    _harness_files(places)

    real = FakeSession.call

    def hang(self, tool, arguments):
        if tool == "list_pages":
            raise tools.DriverError("no answer to tools/call in 90 s")
        return real(self, tool, arguments)

    monkeypatch.setattr(FakeSession, "call", hang)
    _active_port(tmp_path / "local" / "Microsoft" / "Edge" / "User Data", debug_port)
    code, answer = _cli(["browser-driver", "--attach", "edge"], driver_env, driver_system, repo, capsys, tmp_path)
    attach = answer["attach"]
    assert attach["ok"] is False and "no answer" in attach["why"]
    assert "allow the connection in the edge window" in attach["why"]


def test_attach_with_a_port_file_of_a_closed_debug_session_says_remote_debugging_is_off(
        driver_env, places, repo, driver_system, capsys, tmp_path):
    _harness_files(places)
    _active_port(tmp_path / "local" / "Microsoft" / "Edge" / "User Data", _closed_port())
    code, answer = _cli(["browser-driver", "--attach", "edge"], driver_env, driver_system, repo, capsys, tmp_path)
    assert code == 0
    assert answer["attach"]["ok"] is False and "remote debugging is off" in answer["attach"]["why"]
    assert not any("--autoConnect" in argv for argv in FakeSession.started)


def test_switch_back_removes_the_driver_entries_and_keeps_the_rest(
        driver_env, places, repo, driver_system, capsys, tmp_path):
    _harness_files(places)
    assert _cli(["browser-driver"], driver_env, driver_system, repo, capsys, tmp_path)[0] == 0
    code, back = _cli(["switch-back"], driver_env, driver_system, repo, capsys, tmp_path)
    assert back["browser_driver"] == {"claude": "removed", "codex": "removed"}
    claude = json.loads(places.claude_user_config.read_text(encoding="utf-8"))
    assert claude["mcpServers"] == {"other": {"command": "x"}} and claude["numStartups"] == 3
    assert tomllib.loads(places.codex_config.read_text(encoding="utf-8")) == {
        "model": "gpt-x", "mcp_servers": {"other": {"command": "y"}}}


# --------------------------------------------------------------------- judge

class JudgeRunner:
    """The other-provider runner: auth status and the proving call."""

    def __init__(self, exit_code=0, signed_in=True):
        self.exit_code, self.signed_in, self.calls = exit_code, signed_in, []

    def __call__(self, argv, *, stdin, cwd, timeout):
        self.calls.append(list(argv))
        if "status" in argv:
            return other_provider.Ran(0 if self.signed_in else 1, "", False)
        if "-p" in argv:
            out = json.dumps({"type": "result", "structured_output": {"ok": True},
                              "modelUsage": {"claude-fable-5": {}}})
        else:
            out = json.dumps({"ok": True})
        return other_provider.Ran(self.exit_code, out if self.exit_code == 0 else "", False, "boom")


@pytest.fixture
def judge_system(driver_system, monkeypatch, env):
    monkeypatch.setenv("LOCALAPPDATA", env["LOCALAPPDATA"])
    driver_system.judge_runner = JudgeRunner()
    return driver_system


def test_judge_proves_the_model_with_1_call_and_writes_its_line(
        env, places, repo, judge_system, capsys, tmp_path):
    setup.write_install_record(places, {"path": "/py", "version": "3.12"}, "/rg")
    code, answer = _cli(["judge", "--provider", "claude"], env, judge_system, repo, capsys, tmp_path)
    assert code == 0, answer
    proving = [c for c in judge_system.judge_runner.calls if "-p" in c]
    assert len(proving) == 1
    assert proving[0][proving[0].index("--model") + 1] == tools.JUDGE_MODELS["claude"]
    assert proving[0][proving[0].index("--effort") + 1] == other_provider.EFFORT
    record = setup.read_install_record(places)
    assert record["judge_claude"] == tools.JUDGE_MODELS["claude"] and record["python"] == "/py"
    assert answer["which"]["codex"]["provider"] == "claude"
    assert answer["which"]["codex"]["model"] == tools.JUDGE_MODELS["claude"]


def test_judge_codex_takes_the_model_the_developer_names(env, places, repo, judge_system, capsys, tmp_path):
    code, answer = _cli(["judge", "--provider", "codex", "--model", "gpt-big"], env, judge_system, repo, capsys,
                        tmp_path)
    assert code == 0, answer
    proving = [c for c in judge_system.judge_runner.calls if "exec" in c]
    assert len(proving) == 1 and proving[0][proving[0].index("-m") + 1] == "gpt-big"
    assert setup.read_install_record(places)["judge_codex"] == "gpt-big"


def test_judge_with_no_cli_refuses_no_provider(env, places, repo, judge_system, driver_runner, capsys, tmp_path):
    del driver_runner.paths["codex"]
    code, answer = _cli(["judge", "--provider", "codex", "--model", "m"], env, judge_system, repo, capsys, tmp_path)
    assert (code, answer["error"]["code"]) == (1, "no-provider")
    assert "judge_codex" not in setup.read_install_record(places)


def test_judge_with_a_failed_proving_call_refuses_proof_failed(env, places, repo, judge_system, capsys, tmp_path):
    judge_system.judge_runner.exit_code = 1
    code, answer = _cli(["judge", "--provider", "claude"], env, judge_system, repo, capsys, tmp_path)
    assert (code, answer["error"]["code"]) == (1, "proof-failed")
    assert "judge_claude" not in setup.read_install_record(places)


# ------------------------------------------------------------------ gh floor

def _github_tracker(repo):
    (repo / ".afkv2").mkdir()
    (repo / ".afkv2" / "config.json").write_text(json.dumps({"tracker": {"kind": "github-issues"}}),
                                                 encoding="utf-8")


def test_status_reports_an_old_gh_with_the_fix(env, repo, driver_runner, driver_system, capsys, tmp_path):
    _github_tracker(repo)
    driver_runner.gh = "gh version 2.92.0 (2026-05-01)\n"
    code, answer = _cli(["status"], env, driver_system, repo, capsys, tmp_path)
    assert code == 0
    gh = answer["gh"]
    assert (gh["needed"], gh["ok"], gh["version"]) == (True, False, "2.92.0")
    assert "2.99.0" in gh["fix"]
    assert "winget upgrade --id GitHub.cli" in tools.check_gh(driver_runner, env, windows=True)["fix"]


def test_status_passes_a_gh_at_the_floor(env, repo, driver_runner, driver_system, capsys, tmp_path):
    _github_tracker(repo)
    driver_runner.gh = "gh version 2.99.0 (2026-09-01)\n"
    gh = _cli(["status"], env, driver_system, repo, capsys, tmp_path)[1]["gh"]
    assert (gh["needed"], gh["ok"]) == (True, True) and "fix" not in gh


def test_status_skips_gh_without_a_github_tracker(env, repo, driver_runner, driver_system, capsys, tmp_path):
    gh = _cli(["status"], env, driver_system, repo, capsys, tmp_path)[1]["gh"]
    assert gh == {"needed": False}
    assert not any(call[0] == "gh" for call in driver_runner.calls)


def test_the_floor_is_the_one_the_tracker_port_enforces():
    port = Path(__file__).resolve().parents[2] / "ports" / "tracker" / "github_issues.py"
    assert f"GH_FLOOR = {tools.GH_FLOOR!r}" in port.read_text(encoding="utf-8")
