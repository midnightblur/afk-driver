"""End to end on a temporary home and repository through the command line verbs."""

import errno
import json
import os
import re
import shutil
import stat
from pathlib import Path

import pytest

import plugins
import recorded_config_reader
import setup
import tools
from conftest import FakeUserEnv, NEW_ID, V1_CONFIG, V1_ID, end_marker, fire, hooks_dir, make_world, prepared_world
from places import write_atomic


def _cli(argv, env, system, plugin_root, repo, capsys):
    code = setup.main(argv, env=env, system=system, plugin_root=plugin_root, cwd=repo)
    return code, json.loads(capsys.readouterr().out)


def _takeover(env, system, plugin_root, repo, capsys):
    return _cli(["takeover", "--provider", "claude", "--end-marker", end_marker()],
                env, system, plugin_root, repo, capsys)


def _writable(function, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    function(path)


def _refuse_writes(patch, module, path):
    """The module's writes to `path` raise, as on a locked file."""
    real = module.write_atomic

    def write(target, data):
        if Path(target) == path:
            raise OSError(f"locked: {path}")
        real(target, data)

    patch.setattr(module, "write_atomic", write)


@pytest.fixture
def world(places, repo, runner):
    runner.paths["python3"] = "/usr/bin/python3"
    return make_world(places, repo)


@pytest.fixture
def taken_over(world, env, places, repo, runner, system, plugin_root, capsys):
    """Setup ran, both hooks fired since, and the takeover passed."""
    assert _cli(["prepare"], env, system, plugin_root, repo, capsys)[0] == 0
    fire(places, "claude")
    fire(places, "codex")
    code, done = _takeover(env, system, plugin_root, repo, capsys)
    assert code == 0, done
    return done


# ---------------------------------------------------------- the hook proof

def test_a_hook_that_never_fired_keeps_the_block_and_names_the_trust_review(
        world, env, places, repo, system, plugin_root, capsys):
    assert _cli(["prepare"], env, system, plugin_root, repo, capsys)[0] == 0
    code, refused = _takeover(env, system, plugin_root, repo, capsys)
    assert code == 1 and refused["v1_block"] == "kept"
    assert any("trust the afkv2 hooks" in r for r in refused["proof"]["reasons"])
    assert "hook trust review" in refused["next"]
    assert (places.backup / "instructions" / "claude" / "original").exists()
    for path, data in world.items():
        assert path.read_bytes() == data, path


def test_a_hook_that_fired_before_the_install_record_is_no_proof(
        world, env, places, repo, system, plugin_root, capsys):
    assert _cli(["prepare"], env, system, plugin_root, repo, capsys)[0] == 0
    fire(places, "claude", later=-60)
    fire(places, "codex", later=-60)
    code, refused = _takeover(env, system, plugin_root, repo, capsys)
    assert code == 1 and refused["v1_block"] == "kept"
    reasons = refused["proof"]["reasons"]
    assert [r.split(":")[0] for r in reasons] == ["claude", "codex"]
    assert all("before setup's install record" in r for r in reasons)
    assert places.instruction_file("claude").read_bytes() == world[places.instruction_file("claude")]


# ----------------------------------------------------------- the takeover

def test_takeover_changes_every_v1_place(taken_over, world, places, repo, runner):
    assert places.instruction_file("claude").read_bytes() == b"mine\r\nmore\r\n"
    assert places.instruction_file("codex").read_bytes() == b"codex\n"
    assert not (hooks_dir(repo) / "pre-commit").exists()
    assert taken_over["plugins"]["claude"]["effective"] == {V1_ID: False, NEW_ID: True}
    assert plugins.claude_effective(places.claude_user_settings, repo) == {V1_ID: False, NEW_ID: True}
    assert taken_over["plugins"]["codex"]["listed"] == {V1_ID: False, NEW_ID: True}
    assert runner.lavish == "0.1.80"
    assert places.claude_user_settings.read_bytes() == world[places.claude_user_settings]
    assert (repo / ".afk" / "config.yaml").read_bytes() == V1_CONFIG


def test_a_second_takeover_changes_nothing(taken_over, env, places, repo, system, plugin_root, capsys):
    watched = (places.instruction_file("claude"), repo / ".claude" / "settings.local.json", places.codex_config)
    snapshot = {p: p.read_bytes() for p in watched}
    code, again = _takeover(env, system, plugin_root, repo, capsys)
    assert code == 0 and not again["plugins"]["claude"]["written"]
    assert {p: p.read_bytes() for p in watched} == snapshot


def test_a_bad_block_stops_the_takeover_before_any_change(
        env, places, repo, runner, system, plugin_root, capsys):
    files = prepared_world(places, repo)
    codex_file = places.instruction_file("codex")
    codex_file.write_bytes(b"<!-- afk:behaviors:start -->\nno end\n")
    code, answer = _takeover(env, system, plugin_root, repo, capsys)
    assert code == 1 and answer["error"]["code"] == "bad-block"
    assert "git_hooks" not in answer and "plugins" not in answer
    assert (hooks_dir(repo) / "pre-commit").exists()
    assert places.instruction_file("claude").read_bytes() == files[places.instruction_file("claude")]


def test_an_unreadable_plugin_input_stops_the_takeover_before_any_change(
        env, places, repo, runner, system, plugin_root, capsys):
    files = prepared_world(places, repo)
    runner._codex = lambda: tools.Result(0, "PLUGIN  STATUS\n")
    places.codex_config.write_bytes(b'model = "\xff"\n')
    code, answer = _takeover(env, system, plugin_root, repo, capsys)
    assert code == 1 and answer["error"]["code"] == "unreadable-input"
    assert "v1_block" not in answer
    assert places.instruction_file("claude").read_bytes() == files[places.instruction_file("claude")]
    assert (hooks_dir(repo) / "pre-commit").exists()


def test_a_failed_last_step_reports_the_steps_done_and_a_rerun_finishes(
        env, places, repo, runner, system, plugin_root, capsys):
    prepared_world(places, repo)
    runner.npm_fails = True
    code, stopped = _takeover(env, system, plugin_root, repo, capsys)
    assert code == 1 and stopped["error"]["code"] == "lavish-install-failed"
    assert stopped["v1_block"]["ok"] and stopped["git_hooks"]["ok"] and stopped["plugins"]["ok"]
    runner.npm_fails = False
    code, done = _takeover(env, system, plugin_root, repo, capsys)
    assert code == 0, done
    assert {f["action"] for f in done["v1_block"]["files"]} == {"absent"}
    assert set(done["git_hooks"]["hooks"].values()) == {"already-moved"}
    assert not done["plugins"]["claude"]["written"]
    assert done["lavish"]["version"] == "0.1.80"


def test_an_error_inside_a_step_names_that_step(
        env, places, repo, runner, system, plugin_root, capsys, monkeypatch):
    prepared_world(places, repo)

    def locked(*_args):
        raise OSError("locked")

    monkeypatch.setattr(setup, "move_v1_git_hooks", locked)
    code, answer = _takeover(env, system, plugin_root, repo, capsys)
    assert code == 1 and answer["v1_block"]["ok"]
    assert answer["git_hooks"]["error"]["code"] == "unreadable-input"
    assert answer["error"] == answer["git_hooks"]["error"] and "plugins" not in answer


# ---------------------------------------------------------- the switch back

def test_switch_back_restores_every_file(taken_over, world, env, places, repo, runner, system, plugin_root, capsys):
    places.published_tickets.parent.mkdir(parents=True, exist_ok=True)
    places.published_tickets.write_text(
        "2026-10-30T10:00:00Z PROJ-1 abcd1234\n2026-10-30T11:00:00Z PROJ-1 ef567890\n"
        "2026-10-30T12:00:00Z PROJ-2 00112233\n", encoding="utf-8")
    code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 0, back
    assert back["published_tickets"] == ["PROJ-1", "PROJ-2"]
    assert runner.lavish == "0.1.63"
    unchanged = set(world) - {places.codex_config}
    assert {p: p.read_bytes() for p in unchanged} == {p: world[p] for p in unchanged}
    assert not any((places.backup / sub).exists() and any((places.backup / sub).iterdir())
                   for sub in ("instructions", "git-hooks", "claude-settings", "codex"))


def _secrets(env, system, plugin_root, repo, capsys):
    answers = iter(["https://new.atlassian.net", "new@example.com"])
    system.ask = lambda _p: next(answers)
    system.ask_secret = lambda _p: "new-token-secret"
    return _cli(["secrets"], env, system, plugin_root, repo, capsys)


def test_switch_back_restores_the_claude_jira_values_and_keeps_later_harness_writes(
        taken_over, env, places, repo, system, plugin_root, capsys):
    old = {"JIRA_BASE_URL": "https://old.atlassian.net", "JIRA_EMAIL": "old@example.com", "JIRA_API_TOKEN": "old-token-secret"}
    places.claude_user_config.write_text(json.dumps({"mcpServers": {"tracker": {"env": old}}}), encoding="utf-8")
    assert _secrets(env, system, plugin_root, repo, capsys)[0] == 0
    later = json.loads(places.claude_user_config.read_text(encoding="utf-8"))
    later["numStartups"] = 7
    places.claude_user_config.write_text(json.dumps(later), encoding="utf-8")
    code = setup.main(["switch-back"], env=env, system=system, plugin_root=plugin_root, cwd=repo)
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert json.loads(printed)["jira_values"]["claude_user_config"] == {"action": "merged"}
    now = json.loads(places.claude_user_config.read_text(encoding="utf-8"))
    assert now == {"mcpServers": {"tracker": {"env": old}}, "numStartups": 7}
    assert "secret" not in printed
    assert not (places.backup / "claude-user-config").exists()


def test_switch_back_restores_the_user_environment(taken_over, env, places, repo, system, plugin_root, capsys):
    system.user_env = FakeUserEnv(JIRA_EMAIL="old@example.com")
    assert _secrets(env, system, plugin_root, repo, capsys)[0] == 0
    assert system.user_env.values["JIRA_API_TOKEN"] == "new-token-secret"
    code = setup.main(["switch-back"], env=env, system=system, plugin_root=plugin_root, cwd=repo)
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert json.loads(printed)["jira_values"]["user_environment"]["keys"]["JIRA_EMAIL"] == "restored"
    assert system.user_env.values == {"JIRA_EMAIL": "old@example.com"}
    assert "secret" not in printed and not (places.backup / "user-env").exists()


def test_a_failed_user_environment_restore_fails_switch_back_and_a_rerun_finishes(
        taken_over, env, places, repo, system, plugin_root, capsys):
    system.user_env = FakeUserEnv()
    assert _secrets(env, system, plugin_root, repo, capsys)[0] == 0
    system.user_env.broken = True
    code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 1 and back["jira_values"]["user_environment"]["action"] == "failed"
    assert (places.backup / "user-env" / "values.json").exists()
    system.user_env.broken = False
    code, again = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 0 and again["jira_values"]["user_environment"]["action"] == "restored"
    assert system.user_env.values == {}


def test_switch_back_with_no_jira_backup_reports_it(taken_over, env, repo, system, plugin_root, capsys):
    _, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert back["jira_values"] == {"claude_user_config": {"action": "no-backup"},
                                   "user_environment": {"action": "no-backup"}}


def test_switch_back_leaves_only_v1_on(taken_over, world, env, places, repo, runner, system, plugin_root, capsys):
    assert _cli(["switch-back"], env, system, plugin_root, repo, capsys)[0] == 0
    assert places.codex_config.read_bytes() == re.sub(rb'("afkv2@afk-toolkit"\]\r?\nenabled = )true',
                                                      rb"\1false", world[places.codex_config])
    local = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert local == {"enabledPlugins": {NEW_ID: False, V1_ID: True}}
    assert plugins.claude_effective(places.claude_user_settings, repo) == {V1_ID: True, NEW_ID: False}
    status = runner(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all", "--", ".claude"])
    assert status.out == ""


def test_switch_back_with_v1_alone_on_leaves_no_trace_in_the_repository(
        env, places, repo, runner, system, plugin_root, capsys):
    files = prepared_world(places, repo)
    places.claude_user_settings.write_text(json.dumps({"enabledPlugins": {V1_ID: True}}), encoding="utf-8")
    exclude = repo / ".git" / "info" / "exclude"
    before = exclude.read_bytes()
    assert _takeover(env, system, plugin_root, repo, capsys)[0] == 0
    assert b"settings.local.json" in exclude.read_bytes()
    code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 0, back
    assert not (repo / ".claude" / "settings.local.json").exists()
    assert exclude.read_bytes() == before
    assert places.instruction_file("codex").read_bytes() == files[places.instruction_file("codex")]


def test_switch_back_keeps_what_the_harnesses_wrote_since(
        taken_over, env, places, repo, system, plugin_root, capsys):
    local = repo / ".claude" / "settings.local.json"
    data = json.loads(local.read_text(encoding="utf-8"))
    data["permissions"] = {"allow": ["Read"]}
    local.write_text(json.dumps(data), encoding="utf-8")
    with places.codex_config.open("ab") as handle:
        handle.write(b'\n[projects."C:/w"]\ntrust_level = "trusted"\n')
    code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 0, back
    assert back["claude_settings"][0]["settings"] == "merged" and back["codex_config"] == "merged"
    assert json.loads(local.read_text(encoding="utf-8")) == {
        "enabledPlugins": {NEW_ID: False, V1_ID: True}, "permissions": {"allow": ["Read"]}}
    text = places.codex_config.read_bytes().decode("utf-8")
    assert 'trust_level = "trusted"' in text
    assert plugins.codex_config_state(text) == {V1_ID: True, NEW_ID: False}


def test_switch_back_with_a_deleted_repository_restores_the_rest(
        taken_over, world, env, tmp_path, places, repo, runner, system, plugin_root, capsys, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    shutil.rmtree(repo, onerror=_writable)
    code, back = _cli(["switch-back"], env, system, plugin_root, elsewhere, capsys)
    assert code == 0, back
    assert back["claude_settings"] == [{"repo": str(repo), "settings": "repo-missing"}]
    assert {h["action"] for h in back["git_hooks"]} == {"repo-missing"}
    assert not repo.exists() and not any(elsewhere.iterdir())
    assert places.instruction_file("claude").read_bytes() == world[places.instruction_file("claude")]
    assert runner.lavish == "0.1.63"
    assert not places.install_record.exists()


def test_a_hook_conflict_keeps_the_install_record_and_the_backup(
        taken_over, env, places, repo, system, plugin_root, capsys):
    (hooks_dir(repo) / "pre-commit").write_bytes(b"#!/bin/sh\nnew\n")
    code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 1
    assert [h["action"] for h in back["git_hooks"]].count("conflict") == 1
    assert places.install_record.exists()
    assert len(list((places.backup / "git-hooks").rglob("pre-commit"))) == 1


def test_a_failed_lavish_restore_keeps_the_install_record(
        taken_over, env, places, repo, runner, system, plugin_root, capsys):
    runner.npm_fails = True
    code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 1 and back["lavish"]["error"]["code"] == "lavish-restore-failed"
    assert places.install_record.exists() and tools.lavish_record(places).exists()


def test_a_failed_instruction_restore_keeps_its_backup_and_a_rerun_finishes(
        taken_over, world, env, places, repo, system, plugin_root, capsys, monkeypatch):
    target = places.instruction_file("claude")
    with monkeypatch.context() as patch:
        _refuse_writes(patch, setup, target)
        code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 1 and places.install_record.exists()
    failed = [b for b in back["blocks"] if b["action"] == "failed"]
    assert [b["path"] for b in failed] == [str(target)]
    assert Path(failed[0]["backup"], "original").read_bytes() == world[target]
    assert _cli(["switch-back"], env, system, plugin_root, repo, capsys)[0] == 0
    assert target.read_bytes() == world[target]


def test_a_failed_settings_restore_keeps_its_backup_and_a_rerun_finishes(
        taken_over, env, places, repo, system, plugin_root, capsys):
    local = repo / ".claude" / "settings.local.json"
    written = local.read_bytes()
    local.write_text("{", encoding="utf-8")
    code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 1 and places.install_record.exists()
    answer = back["claude_settings"][0]
    assert answer["settings"] == "failed"
    assert Path(answer["backup"], "settings.local.json.absent").exists()
    local.write_bytes(written)
    assert _cli(["switch-back"], env, system, plugin_root, repo, capsys)[0] == 0
    assert plugins.claude_effective(places.claude_user_settings, repo) == {V1_ID: True, NEW_ID: False}
    assert not any((places.backup / "claude-settings").iterdir())


def test_a_failed_codex_restore_keeps_its_backup_and_a_rerun_finishes(
        taken_over, env, places, repo, system, plugin_root, capsys, monkeypatch):
    with monkeypatch.context() as patch:
        _refuse_writes(patch, setup, places.codex_config)
        code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 1 and places.install_record.exists()
    assert back["codex_config"] == "failed" and back["backup_dir"] == str(places.backup)
    assert (places.backup / "codex" / "config.toml").exists()
    assert _cli(["switch-back"], env, system, plugin_root, repo, capsys)[0] == 0
    assert not (places.backup / "codex" / "config.toml").exists()
    assert plugins.only_one_on(plugins.codex_config_state(places.codex_config.read_text(encoding="utf-8"))) == "afk"


def test_a_git_failure_on_a_live_repository_still_restores_its_settings(
        taken_over, env, places, repo, runner, system, plugin_root, capsys):
    runner.git_common_dir_fails = True
    code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 0, back
    assert back["claude_settings"][0]["settings"] == "removed"
    assert plugins.claude_effective(places.claude_user_settings, repo) == {V1_ID: True, NEW_ID: False}


def _v1_alone_taken_over(env, places, repo, system, plugin_root, capsys):
    """After this takeover the ignore line is setup's, and switch-back leaves no settings file."""
    prepared_world(places, repo)
    places.claude_user_settings.write_text(json.dumps({"enabledPlugins": {V1_ID: True}}), encoding="utf-8")
    exclude = repo / ".git" / "info" / "exclude"
    before = exclude.read_bytes()
    assert _takeover(env, system, plugin_root, repo, capsys)[0] == 0
    return exclude, before


def test_a_git_failure_keeps_the_marker_until_the_ignore_line_is_gone(
        env, places, repo, runner, system, plugin_root, capsys):
    exclude, before = _v1_alone_taken_over(env, places, repo, system, plugin_root, capsys)
    runner.git_common_dir_fails = True
    code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 1 and places.install_record.exists()
    answer = back["claude_settings"][0]
    assert answer["settings"] == "failed" and Path(answer["backup"], setup.IGNORE_ADDED).exists()
    assert "git cannot read this repository" in answer["reason"]
    runner.git_common_dir_fails = False
    assert _cli(["switch-back"], env, system, plugin_root, repo, capsys)[0] == 0
    assert exclude.read_bytes() == before


def test_a_repository_folder_with_no_git_has_no_ignore_line_to_remove(
        env, tmp_path, places, repo, system, plugin_root, capsys):
    _v1_alone_taken_over(env, places, repo, system, plugin_root, capsys)
    shutil.rmtree(repo / ".git", onerror=_writable)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    code, back = _cli(["switch-back"], env, system, plugin_root, elsewhere, capsys)
    assert code == 0, back
    assert back["claude_settings"][0]["ignore_line"] == "absent"
    assert not any((places.backup / "claude-settings").iterdir())


def test_a_failed_v1_only_switch_keeps_the_settings_backup_and_a_rerun_finishes(
        taken_over, env, places, repo, system, plugin_root, capsys, monkeypatch):
    with monkeypatch.context() as patch:
        _refuse_writes(patch, plugins, repo / ".claude" / "settings.local.json")
        code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 1 and not back["plugins"]["ok"]
    assert any((places.backup / "claude-settings").iterdir())
    assert _cli(["switch-back"], env, system, plugin_root, repo, capsys)[0] == 0
    assert plugins.claude_effective(places.claude_user_settings, repo) == {V1_ID: True, NEW_ID: False}
    assert not any((places.backup / "claude-settings").iterdir())


def test_a_backup_folder_a_crash_left_empty_does_not_stop_switch_back(
        taken_over, env, places, repo, system, plugin_root, capsys):
    crashed = [places.backup / "claude-settings" / "crashed", places.backup / "git-hooks" / "crashed"]
    for folder in crashed:
        folder.mkdir(parents=True)
    code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 0, back
    assert not any(folder.exists() for folder in crashed)


@pytest.mark.parametrize("sub", ["claude-settings", "git-hooks"])
def test_a_backup_that_cannot_be_deleted_is_reported_with_its_path(
        taken_over, sub, env, places, repo, system, plugin_root, capsys, monkeypatch):
    real = shutil.rmtree
    locked = places.backup / sub

    def rmtree(path, *args, **kwargs):
        if Path(path).parent == locked:
            raise OSError("locked")
        real(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(setup.shutil, "rmtree", rmtree)
        code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 1 and places.install_record.exists()
    entries = back["claude_settings"] if sub == "claude-settings" else back["git_hooks"]
    backups = [e["backup"] for e in entries if "failed" in (e.get("settings"), e.get("action"))]
    assert [Path(b).parent for b in backups] == [locked]


def test_the_install_record_ends_at_switch_back(taken_over, env, places, repo, system, plugin_root, capsys):
    assert _cli(["switch-back"], env, system, plugin_root, repo, capsys)[0] == 0
    assert not places.install_record.exists()
    code, later = _takeover(env, system, plugin_root, repo, capsys)
    assert code == 1 and later["error"]["code"] == "no-install-record"


# ------------------------------------------------------------- command line

def test_prepare_records_the_python_it_found(world, env, places, repo, system, plugin_root, capsys):
    code, prepared = _cli(["prepare"], env, system, plugin_root, repo, capsys)
    assert code == 0 and prepared["install_record"]["python"] == "/usr/bin/python3 3.12.4"
    assert setup.read_install_record(places)["python"] == "/usr/bin/python3 3.12.4"


def test_copy_config_verb_copies_once_and_keeps_the_v1_config(world, env, repo, system, plugin_root, capsys):
    code, copied = _cli(["copy-config"], env, system, plugin_root, repo, capsys)
    assert code == 0 and copied["action"] == "copied"
    config = recorded_config_reader.read_config(repo / ".afkv2" / "config.json")
    assert config["spec_folder"] == str(repo / "docs/specs")
    assert config["tracker"] == {"kind": "github-issues", "repo": "o/r"}
    assert (repo / ".afk" / "config.yaml").read_bytes() == V1_CONFIG
    code, again = _cli(["copy-config"], env, system, plugin_root, repo, capsys)
    assert code == 0 and again["action"] == "exists"


def test_copy_config_with_no_spec_folder_refuses_and_writes_nothing(env, repo, system, plugin_root, capsys):
    code, answer = _cli(["copy-config"], env, system, plugin_root, repo, capsys)
    assert code == 1 and answer["error"]["code"] == "no-spec-folder"
    assert not (repo / ".afkv2").exists()


def test_copy_config_takes_the_developers_spec_folder(env, repo, system, plugin_root, capsys):
    code, answer = _cli(["copy-config", "--spec-folder", "specs"], env, system, plugin_root, repo, capsys)
    assert code == 0 and answer["action"] == "written" and answer["spec_folder_source"] == "developer"
    assert recorded_config_reader.read_config(repo / ".afkv2" / "config.json")["spec_folder"] == str(repo / "specs")


def test_copy_config_can_decline_the_v1_values(world, env, repo, system, plugin_root, capsys):
    code, answer = _cli(["copy-config", "--no-v1-values"], env, system, plugin_root, repo, capsys)
    assert code == 0 and answer["action"] == "written"
    assert json.loads((repo / ".afkv2" / "config.json").read_text(encoding="utf-8")) == {"spec_folder": "docs/specs"}


def test_prepare_exits_1_on_a_red_shell(env, repo, runner, system, plugin_root, capsys):
    runner.paths["python3"] = "/usr/bin/python3"
    runner.shell_has_rg["bash"] = False
    code, answer = _cli(["prepare"], env, system, plugin_root, repo, capsys)
    assert code == 1 and answer["error"]["code"] == "rg-not-on-every-shell"
    assert answer["rg"]["shells"] == {"bash": False}


def test_prepare_exits_1_with_no_python(env, repo, system, plugin_root, capsys):
    code, answer = _cli(["prepare"], env, system, plugin_root, repo, capsys)
    assert code == 1 and answer["error"]["code"] == "no-python"


def test_ownership_verb_writes_both_grades(env, places, repo, system, plugin_root, capsys):
    assert _cli(["copy-config", "--spec-folder", "specs"], env, system, plugin_root, repo, capsys)[0] == 0
    code, answer = _cli(["ownership", "--own", "a/**", "b/**", "--shared", "c/**"],
                        env, system, plugin_root, repo, capsys)
    assert code == 0 and answer["action"] == "written"
    config = recorded_config_reader.read_config(repo / ".afkv2" / "config.json")
    assert config["ownership"] == {"own": ["a/**", "b/**"], "shared": ["c/**"]}


def test_ownership_verb_records_a_skip(env, places, repo, system, plugin_root, capsys):
    code, answer = _cli(["ownership", "--skip"], env, system, plugin_root, repo, capsys)
    assert code == 0 and answer["action"] == "skipped"
    assert str(repo.resolve()) in places.ownership_skips.read_text(encoding="utf-8")


def test_ownership_verb_with_no_paths_exits_1(env, repo, system, plugin_root, capsys):
    code, answer = _cli(["ownership"], env, system, plugin_root, repo, capsys)
    assert code == 1 and answer["error"]["code"] == "empty"


def test_outside_a_repository_exits_2(env, tmp_path, system, plugin_root, capsys):
    outside = tmp_path / "outside"
    outside.mkdir()
    code, answer = _cli(["status"], env, system, plugin_root, outside, capsys)
    assert code == 2 and answer["error"]["code"] == "not-a-repo"


def test_unreadable_settings_exit_2(env, places, repo, system, plugin_root, capsys):
    places.claude_user_settings.parent.mkdir(parents=True)
    places.claude_user_settings.write_text("{not json", encoding="utf-8")
    code, answer = _cli(["status"], env, system, plugin_root, repo, capsys)
    assert code == 2 and answer["error"]["code"] == "unreadable-input"


def test_status_reports_without_writing(world, env, places, repo, system, plugin_root, capsys):
    code, answer = _cli(["status"], env, system, plugin_root, repo, capsys)
    assert code == 0
    assert answer["v1_blocks"]["claude"]["blocks"] == 1
    assert answer["v1_git_hooks"] == {"pre-commit": True, "reference-transaction": True}
    assert answer["ownership"] == "missing" and answer["v1_config"]["keys"]
    assert answer["config_file"] is False
    assert answer["spec_folder"] == {"value": "docs/specs", "source": "v1"}
    assert not places.data.exists()


def test_bad_arguments_exit_2(env, system, plugin_root, repo, capsys):
    code, answer = _cli(["takeover"], env, system, plugin_root, repo, capsys)
    assert code == 2 and answer["error"]["code"] == "bad-arguments"


# --------------------------------------------------------------- safe writes

@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_write_atomic_keeps_the_file_mode(tmp_path):
    secret = tmp_path / "config"
    secret.write_bytes(b"old")
    secret.chmod(0o600)
    write_atomic(secret, b"new")
    assert stat.S_IMODE(secret.stat().st_mode) == 0o600


def test_write_atomic_replaces_a_read_only_file_and_keeps_it_read_only(tmp_path):
    secret = tmp_path / "secret"
    secret.write_bytes(b"old")
    secret.chmod(stat.S_IREAD)
    before = secret.stat().st_mode
    write_atomic(secret, b"new")
    assert secret.read_bytes() == b"new" and secret.stat().st_mode == before


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_write_atomic_keeps_the_data_private_until_the_mode_is_copied(tmp_path, monkeypatch):
    target = tmp_path / "config"
    target.write_bytes(b"old")
    target.chmod(0o644)
    real = shutil.copymode
    at_copy = []

    def copymode(source, temp, **kwargs):
        at_copy.append((stat.S_IMODE(os.stat(temp).st_mode), Path(temp).read_bytes()))
        real(source, temp, **kwargs)

    monkeypatch.setattr(shutil, "copymode", copymode)
    write_atomic(target, b"token")
    assert at_copy == [(0o600, b"token")]
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_write_atomic_gives_a_new_file_the_umask_mode(tmp_path):
    target = tmp_path / "config"
    old = os.umask(0o027)
    try:
        write_atomic(target, b"new")
    finally:
        os.umask(old)
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_write_atomic_survives_a_read_only_temp_file_a_crash_left(tmp_path):
    target = tmp_path / "config"
    stale = tmp_path / "config.afkv2-tmp"
    stale.write_bytes(b"stale")
    stale.chmod(stat.S_IREAD)
    write_atomic(target, b"new")
    assert target.read_bytes() == b"new" and not stale.exists()


@pytest.mark.parametrize("mode", [stat.S_IREAD, stat.S_IREAD | stat.S_IWRITE])
def test_write_atomic_failure_leaves_the_target_and_no_temp_file(tmp_path, monkeypatch, mode):
    target = tmp_path / "config"
    target.write_bytes(b"old")
    target.chmod(mode)
    before = target.stat().st_mode

    def locked(_source, _target):
        raise PermissionError("locked")

    monkeypatch.setattr(os, "replace", locked)
    with pytest.raises(PermissionError):
        write_atomic(target, b"new")
    assert target.read_bytes() == b"old" and target.stat().st_mode == before
    assert [p.name for p in tmp_path.iterdir()] == ["config"]


def _lock_replace_and_unlink(monkeypatch):
    def replace(*_args):
        raise PermissionError("replace locked")

    def unlink(*_args):
        raise PermissionError("unlink locked")

    monkeypatch.setattr(os, "replace", replace)
    monkeypatch.setattr(Path, "unlink", unlink)


@pytest.mark.skipif(os.name != "nt", reason="the read-only unlock runs on Windows only")
def test_a_temp_file_that_cannot_be_dropped_still_restores_the_mode(tmp_path, monkeypatch):
    target = tmp_path / "config"
    target.write_bytes(b"old")
    target.chmod(stat.S_IREAD)
    before = target.stat().st_mode
    _lock_replace_and_unlink(monkeypatch)
    with pytest.raises(PermissionError):
        write_atomic(target, b"new")
    assert target.stat().st_mode == before


def test_a_temp_file_that_cannot_be_dropped_keeps_the_first_error(tmp_path, monkeypatch):
    target = tmp_path / "config"
    target.write_bytes(b"old")
    _lock_replace_and_unlink(monkeypatch)
    with pytest.raises(PermissionError, match="replace locked"):
        write_atomic(target, b"new")
    assert target.read_bytes() == b"old"


@pytest.mark.skipif(os.name != "nt", reason="the read-only unlock runs on Windows only")
def test_a_mode_that_cannot_be_restored_keeps_the_first_error_and_drops_the_temp(
    tmp_path, monkeypatch
):
    target = tmp_path / "config"
    target.write_bytes(b"old")
    target.chmod(stat.S_IREAD)
    read_only = stat.S_IMODE(target.stat().st_mode)
    refused = []
    real_chmod = os.chmod

    def chmod(path, mode, **kwargs):
        if Path(path) == target and mode != stat.S_IWRITE:
            refused.append(mode)
            raise PermissionError("restore locked")
        real_chmod(path, mode, **kwargs)

    def replace(*_args):
        raise PermissionError("replace locked")

    monkeypatch.setattr(os, "chmod", chmod)
    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(PermissionError, match="replace locked"):
        write_atomic(target, b"new")
    assert refused == [read_only]
    assert target.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["config"]


def test_write_atomic_on_a_full_disk_leaves_no_temp_file(tmp_path, monkeypatch):
    target = tmp_path / "config"
    target.write_bytes(b"old")
    real = os.fdopen

    class FullDisk:
        def __init__(self, descriptor, mode):
            self.stream = real(descriptor, mode)

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            self.stream.close()

        def write(self, _data):
            raise OSError(errno.ENOSPC, "no space left")

    monkeypatch.setattr(os, "fdopen", FullDisk)
    with pytest.raises(OSError):
        write_atomic(target, b"token")
    assert target.read_bytes() == b"old" and [p.name for p in tmp_path.iterdir()] == ["config"]


def test_write_atomic_writes_through_a_symlink(tmp_path):
    real = tmp_path / "dotfiles" / "CLAUDE.md"
    real.parent.mkdir()
    real.write_bytes(b"old")
    link = tmp_path / "CLAUDE.md"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("this account cannot make a symbolic link")
    write_atomic(link, b"new")
    assert link.is_symlink() and real.read_bytes() == b"new"
