"""The machine probe: kind resolution from detection and configuration, and the hand-in to the dispatcher."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "team"))

import probe  # noqa: E402

needs_bash = pytest.mark.skipif(probe._bash() is None, reason="no POSIX shell on this machine")
INSIDE = {"PATH": "x", "HERDR_ENV": "1", "HERDR_PANE_ID": "w1:p1"}


class Machine:
    """Fakes `which` and `subprocess.run` for the configuration reader and herdr's detection commands."""

    def __init__(self, *, herdr=True, status="status: running\n", integrations="claude: current (v10)\n",
                 config=None):
        self.herdr, self.status, self.integrations = herdr, status, integrations
        self.config = config or {}

    def which(self, name, path=None):
        if name == "herdr":
            return "herdr" if self.herdr else None
        return name if name in ("claude", "codex") else None

    def run(self, argv, **_):
        if any(str(a).endswith("afk-config.py") for a in argv):
            value = self.config.get(argv[-1])
            return subprocess.CompletedProcess(argv, 0 if value is not None else 1, (value or "") + "\n", "")
        if argv[1:] == ["status"]:
            return subprocess.CompletedProcess(argv, 0 if self.status else 1, self.status or "", "")
        if argv[1:] == ["integration", "status"]:
            return subprocess.CompletedProcess(argv, 0, self.integrations, "")
        raise AssertionError(f"unexpected command {argv}")


def resolve(machine: Machine, env=None, harnesses=("claude",)) -> dict:
    return probe.resolve_kind(REPO, env=INSIDE if env is None else env, harnesses=harnesses,
                              which=machine.which, run=machine.run)


@pytest.mark.parametrize("machine, env, status", [
    (Machine(herdr=False), INSIDE, "absent"),
    (Machine(), {"PATH": "x"}, "outside"),
    (Machine(status=None), INSIDE, "broken"),
    (Machine(integrations=""), INSIDE, "fixable"),
    (Machine(), INSIDE, "usable"),
])
def test_detection_names_each_state_of_the_pane_tool(machine, env, status):
    found = resolve(machine, env)
    assert [t["status"] for t in found["tools"]] == [status]
    assert found["tools"][0]["reason"]


def test_a_usable_pane_tool_resolves_the_multiplexer_kind():
    found = resolve(Machine())
    assert found["kind"] == "multiplexer" and found["source"] == "detected" and "herdr" in found["says"]


@pytest.mark.parametrize("machine, env", [(Machine(herdr=False), INSIDE), (Machine(), {"PATH": "x"}),
                                          (Machine(status=None), INSIDE)])
def test_no_pane_transport_resolves_the_subagent_kind_and_says_so(machine, env):
    found = resolve(machine, env)
    assert found["kind"] == "subagent" and found["conflict"] is None
    assert found["says"].startswith(probe.SUBAGENT_SAYS)


def test_a_fixable_tool_names_the_setting_and_its_fix():
    found = resolve(Machine(integrations="codex: current (v4)\n"), harnesses=("claude", "codex"))
    assert found["kind"] == "subagent"
    assert found["tools"][0]["settings"] == [{"name": "herdr integration for claude",
                                              "fix": "herdr integration install claude"}]
    assert "herdr integration install claude" in found["says"]


def test_a_forced_kind_wins_over_detection():
    found = resolve(Machine(config={"transport.kind": "headless"}))
    assert found["kind"] == "headless" and found["source"] == "config"


@pytest.mark.parametrize("config, env, name", [
    ({"transport.kind": "multiplexer"}, {"PATH": "x"}, "multiplexer forced but not usable"),
    ({"transport.kind": "desktop"}, INSIDE, "desktop forced but not usable"),
    ({"transport.kind": "multiplexer", "transport.pane-switch": "subagent"}, INSIDE,
     "pane switch against forced kind"),
])
def test_a_forced_kind_detection_cannot_serve_is_a_named_conflict(config, env, name):
    found = resolve(Machine(config=config), env)
    assert found["kind"] is None and found["conflict"]["name"] == name and found["conflict"]["detail"]


def test_headless_forced_with_no_harness_is_a_named_conflict():
    found = resolve(Machine(config={"transport.kind": "headless"}), harnesses=())
    assert found["kind"] is None and found["conflict"]["name"] == "headless forced but no harness"


def test_the_pane_switch_set_to_subagent_keeps_agents_out_of_panes():
    found = resolve(Machine(config={"transport.pane-switch": "subagent"}))
    assert found["kind"] == "subagent" and found["source"] == "config"


def test_an_empty_configured_value_reads_as_absent():
    found = resolve(Machine(config={"transport.kind": ""}))
    assert found["kind"] == "multiplexer" and found["source"] == "detected"


# ---- the hand-in to the dispatcher ---------------------------------------------------------------------

def repo_with(tmp_path: Path, config: str) -> Path:
    root = tmp_path / "repo"
    (root / ".afk").mkdir(parents=True)
    (root / ".afk" / "config.yaml").write_text(config, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def child_env(**extra) -> dict:
    import os
    env = {k: v for k, v in os.environ.items() if not k.startswith("AFK_")}
    return {**env, "AFK_PYTHON": sys.executable, **extra}


@needs_bash
@pytest.mark.parametrize("config", ["schema: 1\ntransport:\n", "schema: 1\n",
                                    "schema: 1\ntransport:\n  kind: multiplexer\n"])
def test_a_configuration_load_never_blanks_the_handed_in_kind(tmp_path, config):
    code, out, err = probe.dispatch("subagent", "agent-send", {}, root=repo_with(tmp_path, config),
                                    env=child_env())
    assert code == 3, err
    assert json.loads(out.strip().splitlines()[-1])["unsupported"] is True


@pytest.fixture
def echo_plugin(tmp_path):
    """A plugin copy whose subagent kind prints the variables its shell inherited."""
    plugin = tmp_path / "plugin"
    for part in ("hooks/lib/adapter.sh", "hooks/lib/config.sh", "scripts/afk-config.py"):
        (plugin / part).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / part, plugin / part)
    for family in ("forge", "tracker"):
        shutil.copytree(REPO / "adapters" / family, plugin / "adapters" / family)
    kind = plugin / "adapters" / "transport" / "subagent"
    kind.mkdir(parents=True)
    (kind / "adapter.json").write_text(json.dumps({"runner": {"type": "cli", "entry": "transport.sh"}}),
                                       encoding="utf-8")
    (kind / "transport.sh").write_text(
        '"$AFK_PYTHON" -c \'import json,os; print(json.dumps({k: os.environ.get(k) for k in '
        '("AFK_CFG_LOADED", "AFK_CONFIG", "AFK_CFG_TRANSPORT")}))\'\n', encoding="utf-8")
    return plugin


@needs_bash
def test_the_child_shell_inherits_no_loaded_flag_and_no_config_override(tmp_path, echo_plugin):
    code, out, err = probe.dispatch("subagent", "agent-list", {}, root=repo_with(tmp_path, "schema: 1\n"),
                                    env=child_env(AFK_CFG_LOADED="1"), plugin=echo_plugin)
    assert code == 0, err
    assert json.loads(out.strip().splitlines()[-1]) == {"AFK_CFG_LOADED": None, "AFK_CONFIG": None,
                                                        "AFK_CFG_TRANSPORT": None}


@needs_bash
def test_an_unresolvable_kind_exits_2_naming_the_configuration(tmp_path, echo_plugin):
    shutil.rmtree(echo_plugin / "adapters" / "transport" / "subagent")
    code, out, err = probe.dispatch("subagent", "agent-list", {}, root=repo_with(tmp_path, "schema: 1\n"),
                                    env=child_env(), plugin=echo_plugin)
    assert code == 2 and ".afk/config.yaml" in err and out == ""


def test_dispatch_refuses_a_kind_outside_the_enum():
    with pytest.raises(ValueError, match="unknown transport kind"):
        probe.dispatch("pigeon", "agent-list", {})
