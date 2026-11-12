"""The Claude CLI step and the Fable advisor step, through an in-process fake of the claude program."""

import json

import pytest

import claude_cli
import setup
import tools
from conftest import FakeRunner


class ClaudeRunner(FakeRunner):
    """FakeRunner plus a fake claude program: no test runs the real CLI, an update or a model call."""

    def __init__(self, places):
        super().__init__(places)
        self.paths["claude"] = "/home/me/.local/bin/claude"
        self.version = "2.1.322"
        self.update_to = None
        self.probe = tools.Result(0, "ok\n")

    def __call__(self, argv, env=None, timeout=300):
        if str(argv[0]).endswith("claude"):
            self.calls.append(list(argv))
            if argv[1] == "--version":
                return tools.Result(0, f"{self.version} (Claude Code)\n")
            if argv[1] == "update":
                if self.update_to:
                    old, self.version = self.version, self.update_to
                    return tools.Result(0, f"Successfully updated from {old} to version {self.version}\n")
                return tools.Result(0, "Claude is up to date!\n")
            if argv[1] == "-p":
                return self.probe
        return super().__call__(argv, env, timeout)

    def claude_calls(self, verb):
        return [c for c in self.calls if str(c[0]).endswith("claude") and c[1] == verb]


@pytest.fixture
def claude(places):
    return ClaudeRunner(places)


def releases(latest="2.1.322", stable="2.1.311"):
    return lambda url: {"latest": latest, "stable": stable}[url.rsplit("/", 1)[1]]


def write_settings(places, **values):
    places.claude_user_settings.parent.mkdir(parents=True, exist_ok=True)
    places.claude_user_settings.write_text(json.dumps(values), encoding="utf-8")


def settings(places):
    return json.loads(places.claude_user_settings.read_text(encoding="utf-8"))


# ================================================================== version

def test_a_current_cli_runs_no_update(places, claude, env):
    answer = claude_cli.check_version(places, claude, env, releases())
    assert answer["ok"] and answer["action"] == "current" and answer["channel"] == "latest"
    assert not claude.claude_calls("update")


def test_an_older_cli_is_updated_and_needs_a_new_session(places, claude, env):
    claude.version, claude.update_to = "2.1.300", "2.1.322"
    answer = claude_cli.check_version(places, claude, env, releases())
    assert answer["ok"] and answer["action"] == "updated" and answer["new_session"]
    assert answer["installed"] == "2.1.322"


def test_an_update_that_installs_nothing_is_refused_with_the_commands(places, claude, env):
    claude.version = "2.1.300"
    answer = claude_cli.check_version(places, claude, env, releases())
    assert not answer["ok"] and answer["error"]["code"] == "update-required"
    assert "winget upgrade Anthropic.ClaudeCode" in answer["commands"]


def test_the_stable_channel_is_the_target_of_a_stable_developer(places, claude, env):
    write_settings(places, autoUpdatesChannel="stable")
    claude.version = "2.1.321"
    answer = claude_cli.check_version(places, claude, env, releases(stable="2.1.321"))
    assert answer["ok"] and answer["channel"] == "stable" and answer["action"] == "current"


def test_a_stable_channel_below_the_fable_minimum_is_refused(places, claude, env):
    write_settings(places, autoUpdatesChannel="stable")
    claude.version = "2.1.311"
    answer = claude_cli.check_version(places, claude, env, releases())
    assert answer["error"]["code"] == "channel-too-old" and not claude.claude_calls("update")


def test_an_unreadable_release_pointer_checks_only_the_fable_minimum(places, claude, env):
    def offline(_url):
        raise OSError("no network")
    answer = claude_cli.check_version(places, claude, env, offline)
    assert answer["ok"] and "warning" in answer


def test_no_claude_program_needs_nothing(places, claude, env):
    del claude.paths["claude"]
    assert claude_cli.check_version(places, claude, env, releases()) == {
        "ok": True, "needed": False,
        "reason": "no claude program on the path: Claude Code is not used here"}


# ================================================================== advisor

def test_yes_sets_fable_keeps_other_keys_and_returns_the_consent_steps(places, claude, env, repo):
    write_settings(places, model="opus[1m]", advisorModel="opus", theme="dark")
    answer = claude_cli.set_advisor(places, repo, claude, env, "yes")
    assert answer["ok"] and answer["action"] == "set"
    assert settings(places) == {"model": "opus[1m]", "advisorModel": "fable", "theme": "dark"}
    assert answer["consent"][0] == "/model fable" and answer["consent"][-1] == "/model opus[1m]"
    assert claude_cli.status(places, repo, claude, env) == "consent"
    assert claude.claude_calls("-p")[0][4:6] == ["--advisor", "fable"]


def test_fable_already_set_leaves_the_file_bytes_alone(places, claude, env, repo):
    write_settings(places, advisorModel="fable")
    before = places.claude_user_settings.read_bytes()
    assert claude_cli.set_advisor(places, repo, claude, env, "yes")["action"] == "already-set"
    assert places.claude_user_settings.read_bytes() == before


def test_no_is_recorded_and_writes_no_setting(places, claude, env, repo):
    assert claude_cli.set_advisor(places, repo, claude, env, "no")["action"] == "declined"
    assert not places.claude_user_settings.exists()
    assert claude_cli.status(places, repo, claude, env) == "declined"


@pytest.mark.parametrize("probe", [tools.Result(1, "", "Fable needs your consent: run /model fable"),
                                   tools.Result(0, '"fable" cannot advise this model. The advisor will not be used\nok')])
def test_a_refused_advisor_fails_the_proof(places, claude, env, repo, probe):
    claude.probe = probe
    write_settings(places, advisorModel="opus")
    before = places.claude_user_settings.read_bytes()
    answer = claude_cli.set_advisor(places, repo, claude, env, "yes")
    assert answer["error"]["code"] == "proof-failed"
    assert places.claude_user_settings.read_bytes() == before
    assert claude_cli.status(places, repo, claude, env) == "ask"


def test_a_re_run_keeps_the_main_model_recorded_first(places, claude, env, repo):
    write_settings(places, model="opus[1m]")
    claude_cli.set_advisor(places, repo, claude, env, "yes")
    places.claude_user_settings.write_text(json.dumps(settings(places) | {"model": "claude-fable-5-2"}),
                                           encoding="utf-8")
    assert claude_cli.set_advisor(places, repo, claude, env, "yes")["consent"][-1] == "/model opus[1m]"
    assert claude_cli.consent_done(places)["error"]["code"] == "model-not-restored"


def test_an_environment_blocker_writes_nothing(places, claude, env, repo):
    answer = claude_cli.set_advisor(places, repo, claude, {**env, "CLAUDE_CODE_DISABLE_ADVISOR_TOOL": "1"}, "yes")
    assert answer["error"]["code"] == "advisor-blocked" and not places.claude_user_settings.exists()


def test_a_project_value_that_outranks_the_user_file_is_reported(places, claude, env, repo):
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.json").write_text('{"advisorModel": "opus"}', encoding="utf-8")
    assert "outranks" in claude_cli.set_advisor(places, repo, claude, env, "yes")["overrides"][0]


def test_consent_done_refuses_while_the_main_model_is_still_fable(places, claude, env, repo):
    write_settings(places, model="opus[1m]")
    claude_cli.set_advisor(places, repo, claude, env, "yes")
    data = settings(places) | {"model": "fable"}
    places.claude_user_settings.write_text(json.dumps(data), encoding="utf-8")
    assert claude_cli.consent_done(places)["error"]["code"] == "model-not-restored"
    places.claude_user_settings.write_text(json.dumps(data | {"model": "opus[1m]"}), encoding="utf-8")
    assert claude_cli.consent_done(places)["ok"]
    assert claude_cli.status(places, repo, claude, env) == "done"
    assert claude_cli.set_advisor(places, repo, claude, env, "yes")["consent"] == "done"


def test_switch_back_puts_back_only_the_advisor_value(places, claude, env, repo):
    write_settings(places, advisorModel="opus")
    claude_cli.set_advisor(places, repo, claude, env, "yes")
    places.claude_user_settings.write_text(json.dumps(settings(places) | {"theme": "light"}), encoding="utf-8")
    assert claude_cli.restore(places) == "restored"
    assert settings(places) == {"advisorModel": "opus", "theme": "light"}
    assert claude_cli.restore(places) == "no-backup"


def test_switch_back_drops_a_key_the_developer_never_had(places, claude, env, repo):
    write_settings(places, model="sonnet")
    claude_cli.set_advisor(places, repo, claude, env, "yes")
    assert claude_cli.restore(places) == "restored" and settings(places) == {"model": "sonnet"}


def test_the_advisor_step_writes_nothing_for_codex(places, claude, env, repo):
    claude_cli.set_advisor(places, repo, claude, env, "yes")
    assert not places.codex_dir.exists()


def test_the_verbs_answer_through_main(places, claude, env, repo, capsys):
    system = setup.System(run=claude, windows=False, is_terminal=lambda: True)
    assert setup.main(["advisor", "--repo", str(repo)], env=env, system=system) == 2
    assert setup.main(["advisor", "--answer", "yes", "--repo", str(repo)], env=env, system=system) == 0
    capsys.readouterr()
    assert setup.main(["status", "--repo", str(repo)], env=env, system=system) == 0
    assert json.loads(capsys.readouterr().out)["advisor"] == "consent"
