import json
import os

import plugins
import setup
from conftest import NEW_ID, V1_ID, write_codex_config


def _user_settings(places, data):
    places.claude_user_settings.parent.mkdir(parents=True, exist_ok=True)
    places.claude_user_settings.write_text(json.dumps(data), encoding="utf-8")


def test_claude_switch_writes_only_local_and_reads_back(places, repo, runner):
    _user_settings(places, {"enabledPlugins": {V1_ID: True, NEW_ID: True}})
    shared = repo / ".claude" / "settings.json"
    shared.parent.mkdir()
    shared.write_text('{"enabledPlugins": {"afk@afk-toolkit": true}}\n', encoding="utf-8")
    user_before = places.claude_user_settings.read_bytes()
    shared_before = shared.read_bytes()
    answer = setup._switch_claude(places, repo, runner, "afkv2", with_backup=True)
    assert answer["ok"] and answer["written"]
    assert answer["effective"] == {V1_ID: False, NEW_ID: True}
    assert shared.read_bytes() == shared_before
    assert places.claude_user_settings.read_bytes() == user_before
    local = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert local["enabledPlugins"] == {V1_ID: False, NEW_ID: True}
    assert plugins.claude_effective(places.claude_user_settings, repo) == {V1_ID: False, NEW_ID: True}


def test_equal_value_means_no_write(places, repo, runner):
    _user_settings(places, {"enabledPlugins": {V1_ID: True, NEW_ID: True}})
    setup._switch_claude(places, repo, runner, "afkv2", with_backup=True)
    local = repo / ".claude" / "settings.local.json"
    os.utime(local, (1, 1))
    again = setup._switch_claude(places, repo, runner, "afkv2", with_backup=True)
    assert again["ok"] and not again["written"] and local.stat().st_mtime == 1


def test_local_settings_file_is_ignored_by_git(places, repo, runner):
    _user_settings(places, {"enabledPlugins": {V1_ID: True}})
    answer = setup._switch_claude(places, repo, runner, "afkv2", with_backup=True)
    assert answer["exclude_added"]
    status = runner(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"])
    assert ".claude" not in status.out


def test_both_enabled_after_the_write_is_refused(places, repo, runner, monkeypatch):
    _user_settings(places, {"enabledPlugins": {V1_ID: True, NEW_ID: True}})
    monkeypatch.setattr(plugins, "write_claude_local", lambda _r, _w: False)
    answer = setup._switch_claude(places, repo, runner, "afkv2", with_backup=True)
    assert not answer["ok"] and answer["error"]["code"] == "both-enabled"


def test_codex_switch_edits_config_with_backup_and_lists_state(places, runner):
    before = write_codex_config(places)
    answer = setup._switch_codex(places, runner, "afkv2", with_backup=True)
    assert answer["ok"] and answer["written"]
    assert answer["listed"] == {V1_ID: False, NEW_ID: True}
    assert answer["listed_by"] == "codex plugin list"
    assert (places.backup / "codex" / "config.toml").read_text(encoding="utf-8") == before
    after = places.codex_config.read_text(encoding="utf-8")
    assert after.replace("enabled = false", "enabled = true", 1) == before
    again = setup._switch_codex(places, runner, "afkv2", with_backup=True)
    assert not again["written"]


def test_codex_without_cli_lists_from_config(places, runner):
    write_codex_config(places)
    runner.codex_cli = False
    answer = setup._switch_codex(places, runner, "afkv2", with_backup=True)
    assert answer["ok"] and answer["listed_by"] == "config"


def test_codex_without_afkv2_is_left_alone(places, runner):
    places.codex_config.parent.mkdir(parents=True)
    places.codex_config.write_text(f'[plugins."{V1_ID}"]\nenabled = true\n', encoding="utf-8")
    answer = setup._switch_codex(places, runner, "afkv2", with_backup=True)
    assert answer == {"ok": True, "action": "not-installed", "reason": "Codex has no afkv2 plugin"}


def test_codex_edit_adds_a_missing_enabled_line():
    text = f'[plugins."{NEW_ID}"]\nsource = "x"\n'
    assert plugins.codex_edit(text, {NEW_ID: True}) == f'[plugins."{NEW_ID}"]\nenabled = true\nsource = "x"\n'


def test_parse_codex_list_reads_the_real_layout():
    # Layout recorded from `codex plugin list`, codex-cli 0.164.0; plugin names replaced.
    table = ("Marketplace `other`\n"
             "C:\\cache\\plugins\\other\\marketplace.json\n"
             "\n"
             "PLUGIN                                   STATUS              VERSION        SOURCE\n"
             "doc@other                                installed, enabled  26.1020.11348  C:\\cache\\doc\n"
             "\n"
             "Marketplace `afk-toolkit`\n"
             "C:\\cache\\afk-toolkit\\marketplace.json\n"
             "\n"
             "PLUGIN             STATUS               VERSION  SOURCE\n"
             "afk@afk-toolkit    installed, disabled  1.16.0   C:\\cache\\afk\n"
             "afkv2@afk-toolkit  installed, enabled   0.1.0    C:\\cache\\afkv2\n")
    assert plugins.parse_codex_list(table) == {V1_ID: False, NEW_ID: True}


def test_codex_both_listed_after_the_write_is_refused(places, runner, monkeypatch):
    write_codex_config(places)
    monkeypatch.setattr(plugins, "codex_edit", lambda text, _wanted: text)
    answer = setup._switch_codex(places, runner, "afkv2", with_backup=True)
    assert not answer["ok"] and answer["error"]["code"] == "both-enabled"
    assert answer["listed"] == {V1_ID: True, NEW_ID: True}


def test_a_rerun_after_a_crash_still_adds_the_ignore_line(places, repo, runner):
    _user_settings(places, {"enabledPlugins": {V1_ID: True, NEW_ID: True}})
    plugins.write_claude_local(repo, {V1_ID: False, NEW_ID: True})
    answer = setup._switch_claude(places, repo, runner, "afkv2", with_backup=True)
    assert not answer["written"] and answer["exclude_added"]
    status = runner(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"])
    assert ".claude" not in status.out


def test_restore_local_settings_keeps_what_the_harness_wrote_since(tmp_path):
    local, saved = tmp_path / "local.json", tmp_path / "saved.json"
    saved.write_text('{"enabledPlugins": {"%s": true}, "model": "a"}\n' % V1_ID, encoding="utf-8")
    local.write_text(json.dumps({"enabledPlugins": {V1_ID: False, NEW_ID: True, "x@y": True},
                                 "model": "a", "permissions": {"allow": ["Read"]}}), encoding="utf-8")
    assert plugins.restore_claude_local(local, saved) == "merged"
    assert json.loads(local.read_text(encoding="utf-8")) == {
        "enabledPlugins": {V1_ID: True, "x@y": True}, "model": "a", "permissions": {"allow": ["Read"]}}
    assert not saved.exists()


def test_restore_local_settings_with_no_later_change_is_byte_identical(tmp_path):
    local, saved = tmp_path / "local.json", tmp_path / "saved.json"
    body = '{ "model":"a",  "enabledPlugins":{"%s":true} }\r\n' % V1_ID
    saved.write_bytes(body.encode())
    local.write_text(json.dumps({"model": "a", "enabledPlugins": {V1_ID: False, NEW_ID: True}}), encoding="utf-8")
    assert plugins.restore_claude_local(local, saved) == "restored"
    assert local.read_bytes() == body.encode()


def test_restore_local_settings_absent_before(tmp_path):
    local, saved = tmp_path / "local.json", tmp_path / "saved.json"
    (tmp_path / "saved.json.absent").write_bytes(b"")
    local.write_text(json.dumps({"enabledPlugins": {V1_ID: False, NEW_ID: True}}), encoding="utf-8")
    assert plugins.restore_claude_local(local, saved) == "removed"
    assert not local.exists()
    (tmp_path / "saved.json.absent").write_bytes(b"")
    local.write_text(json.dumps({"enabledPlugins": {NEW_ID: True}, "model": "a"}), encoding="utf-8")
    assert plugins.restore_claude_local(local, saved) == "merged"
    assert json.loads(local.read_text(encoding="utf-8")) == {"model": "a"}


def test_codex_restore_with_no_later_change_returns_the_backup():
    before = f'model = "x"\r\n\r\n[plugins."{NEW_ID}"]\r\nsource = "s"\r\n'
    now = f'model = "x"\r\n\r\n[plugins."{NEW_ID}"]\r\nenabled = false\r\nsource = "s"\r\n'
    assert plugins.codex_restore(now, before) == before


def test_codex_restore_keeps_lines_written_since():
    before = f'[plugins."{V1_ID}"]\nenabled = true\n\n[plugins."{NEW_ID}"]\nenabled = false\n'
    now = (f'[plugins."{V1_ID}"]\nenabled = false\n\n[plugins."{NEW_ID}"]\nenabled = true\n\n'
           '[projects."C:/w"]\ntrust_level = "trusted"\n')
    assert plugins.codex_restore(now, before) == (
        f'[plugins."{V1_ID}"]\nenabled = true\n\n[plugins."{NEW_ID}"]\nenabled = false\n\n'
        '[projects."C:/w"]\ntrust_level = "trusted"\n')
