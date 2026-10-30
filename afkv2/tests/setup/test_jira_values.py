import json
import os
import stat
import sys

import pytest

import jira_values
import setup
from conftest import FakeUserEnv

TOKEN = "tok-secret-123"
OLD_TOKEN = "old-tok-secret-456"
VALUES = {"JIRA_BASE_URL": "https://s.atlassian.net", "JIRA_EMAIL": "dev@example.com", "JIRA_API_TOKEN": TOKEN}


def _claude_entry(places, env_block):
    data = {"mcpServers": {"tracker": {"command": "x", "env": env_block}}, "other": 1}
    places.claude_user_config.write_text(json.dumps(data), encoding="utf-8")


def test_lookup_order_env_then_claude_then_codex(places):
    _claude_entry(places, {"JIRA_EMAIL": "dev@example.com", "JIRA_API_TOKEN": TOKEN})
    places.codex_config.parent.mkdir(parents=True)
    places.codex_config.write_text(
        '[mcp_servers.tracker.env]\nJIRA_BASE_URL = "https://codex.example"\nJIRA_EMAIL = "dev3@example.com"\n',
        encoding="utf-8")
    found = jira_values.lookup(places, {"JIRA_EMAIL": "dev2@example.com"})
    assert found["JIRA_EMAIL"] == ("dev2@example.com", "environment")
    assert found["JIRA_API_TOKEN"] == (TOKEN, "claude user config")
    assert found["JIRA_BASE_URL"] == ("https://codex.example", "codex config")


def test_status_never_carries_a_value(places):
    _claude_entry(places, {"JIRA_BASE_URL": "https://a", "JIRA_EMAIL": "dev@example.com", "JIRA_API_TOKEN": TOKEN})
    answer = jira_values.status(places, {})
    assert answer["complete"] and TOKEN not in json.dumps(answer)


def test_store_into_the_v1_entry_with_backup(places):
    _claude_entry(places, {"JIRA_EMAIL": "dev@example.com"})
    before = places.claude_user_config.read_bytes()
    values = {"JIRA_BASE_URL": "https://s.atlassian.net", "JIRA_EMAIL": "dev@example.com", "JIRA_API_TOKEN": TOKEN}
    answer = jira_values.store_jira_values(places, values, None)
    assert answer["ok"] and answer["stored_in"] == "claude user config"
    assert TOKEN not in json.dumps(answer)
    from pathlib import Path
    assert Path(answer["backup"]).read_bytes() == before
    stored = json.loads(places.claude_user_config.read_text())
    assert stored["mcpServers"]["tracker"]["env"] == values and stored["other"] == 1


def test_store_into_the_user_environment_without_v1_entry(places):
    store = FakeUserEnv()
    answer = jira_values.store_jira_values(places, VALUES, store)
    assert answer == {"ok": True, "stored_in": "user environment"} and store.values == VALUES


def test_secrets_refuses_outside_a_terminal(places, system):
    system.is_terminal = lambda: False
    assert setup.secrets(places, system, {})["error"]["code"] == "not-a-terminal"
    system.is_terminal = lambda: True
    assert setup.secrets(places, system, {"CLAUDECODE": "1"})["error"]["code"] == "not-a-terminal"


def test_secrets_asks_once_and_never_prints_the_token(places, system, capsys):
    answers = iter(["https://s.atlassian.net/", "dev@example.com"])
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return next(answers)

    def ask_secret(prompt):
        prompts.append(prompt)
        return TOKEN

    system.ask, system.ask_secret = ask, ask_secret
    system.user_env = FakeUserEnv()
    answer = setup.secrets(places, system, {})
    assert answer["ok"] and len(prompts) == 3
    assert system.user_env.values == VALUES
    assert TOKEN not in capsys.readouterr().out + json.dumps(answer)


def test_enter_keeps_the_stored_token(places, system):
    _claude_entry(places, {"JIRA_BASE_URL": "https://a", "JIRA_EMAIL": "dev@example.com", "JIRA_API_TOKEN": TOKEN})
    system.ask = lambda _p: ""
    system.ask_secret = lambda _p: ""
    answer = setup.secrets(places, system, {})
    assert answer["ok"]
    assert json.loads(places.claude_user_config.read_text())["mcpServers"]["tracker"]["env"]["JIRA_API_TOKEN"] == TOKEN


def test_bad_value_writes_nothing(places, system):
    system.ask = lambda _p: "http://plain"
    system.ask_secret = lambda _p: TOKEN
    answer = setup.secrets(places, system, {})
    assert answer["error"]["code"] == "bad-value" and not places.claude_user_config.exists()


def test_second_secrets_run_keeps_the_first_backup(places, system):
    first = {"JIRA_BASE_URL": "https://a", "JIRA_EMAIL": "dev@example.com", "JIRA_API_TOKEN": TOKEN}
    _claude_entry(places, first)
    before = places.claude_user_config.read_bytes()
    answers = iter(["https://b.atlassian.net", "", "https://c.atlassian.net", ""])
    system.ask = lambda _p: next(answers)
    system.ask_secret = lambda _p: ""
    setup.secrets(places, system, {})
    setup.secrets(places, system, {})
    assert (places.backup / "claude-user-config" / "claude.json").read_bytes() == before


@pytest.fixture
def fake_registry(monkeypatch):
    """`winreg` as a dict; returns the dict and the list of broadcasts."""
    written = {}
    told = []

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    def query(_key, name):
        if name not in written:
            raise FileNotFoundError(name)
        return written[name]

    def delete(_key, name):
        if name not in written:
            raise FileNotFoundError(name)
        del written[name]

    class Fake:
        HKEY_CURRENT_USER, KEY_SET_VALUE, REG_SZ, KEY_QUERY_VALUE = 1, 2, 3, 4
        OpenKey = staticmethod(lambda *_a: Key())
        SetValueEx = staticmethod(lambda _k, name, _r, kind, value: written.update({name: (value, kind)}))
        QueryValueEx = staticmethod(query)
        DeleteValue = staticmethod(delete)

    monkeypatch.setitem(sys.modules, "winreg", Fake)
    monkeypatch.setattr(jira_values, "broadcast_environment_change", lambda: told.append(1))
    return written, told


def test_user_env_setter_writes_one_plain_value(fake_registry):
    written, _ = fake_registry
    jira_values.windows_user_env_setter("JIRA_EMAIL", "dev@example.com")
    assert written == {"JIRA_EMAIL": ("dev@example.com", 3)}


def test_user_env_getter_reads_a_value_or_absent(fake_registry):
    written, _ = fake_registry
    assert jira_values.windows_user_env_getter("JIRA_EMAIL") is None
    written["JIRA_EMAIL"] = ("dev@example.com", 3)
    assert jira_values.windows_user_env_getter("JIRA_EMAIL") == "dev@example.com"


def test_user_env_deleter_removes_a_value_and_accepts_absent(fake_registry):
    written, told = fake_registry
    written["JIRA_EMAIL"] = ("dev@example.com", 3)
    jira_values.windows_user_env_deleter("JIRA_EMAIL")
    jira_values.windows_user_env_deleter("JIRA_EMAIL")
    assert written == {} and told


def _claude_saved(places):
    return places.backup / "claude-user-config" / "claude.json"


def _env_saved(places):
    return places.backup / "user-env" / "values.json"


def _claude_world(places):
    """A v1 tracker entry with an old token and no email, in a form the harness wrote."""
    data = {"mcpServers": {"tracker": {"command": "x", "env": {"JIRA_API_TOKEN": OLD_TOKEN, "OTHER": "kept"}}}, "other": 1}
    places.claude_user_config.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    before = places.claude_user_config.read_bytes()
    assert jira_values.store_jira_values(places, VALUES, None)["ok"]
    return before


def test_claude_restore_with_nothing_else_changed_writes_the_backup_bytes(places):
    before = _claude_world(places)
    assert places.claude_user_config.read_bytes() != before
    assert jira_values.restore_claude_user_config(places) == {"action": "restored"}
    assert places.claude_user_config.read_bytes() == before
    assert not _claude_saved(places).exists() and not _claude_saved(places).parent.exists()


def test_claude_restore_keeps_what_the_harness_wrote_later(places):
    _claude_world(places)
    later = json.loads(places.claude_user_config.read_text(encoding="utf-8"))
    later["numStartups"] = 99
    later["projects"] = {"/work": {"trust": True}}
    later["mcpServers"]["other-server"] = {"command": "y"}
    places.claude_user_config.write_text(json.dumps(later), encoding="utf-8")
    assert jira_values.restore_claude_user_config(places) == {"action": "merged"}
    now = json.loads(places.claude_user_config.read_text(encoding="utf-8"))
    assert now["numStartups"] == 99 and now["projects"] == {"/work": {"trust": True}}
    assert now["mcpServers"]["other-server"] == {"command": "y"}
    assert now["mcpServers"]["tracker"]["env"] == {"JIRA_API_TOKEN": OLD_TOKEN, "OTHER": "kept"}
    assert not _claude_saved(places).exists()


def test_claude_restore_after_a_later_setup_run_uses_the_first_backup(places):
    before = _claude_world(places)
    jira_values.store_jira_values(places, {**VALUES, "JIRA_API_TOKEN": "third"}, None)
    assert _claude_saved(places).read_bytes() == before
    jira_values.restore_claude_user_config(places)
    assert places.claude_user_config.read_bytes() == before


def test_claude_restore_with_no_backup_changes_nothing(places):
    _claude_entry(places, {"JIRA_EMAIL": "dev@example.com"})
    before = places.claude_user_config.read_bytes()
    assert jira_values.restore_claude_user_config(places) == {"action": "no-backup"}
    assert places.claude_user_config.read_bytes() == before


def test_claude_restore_when_the_harness_removed_the_entry_adds_no_entry(places):
    _claude_world(places)
    places.claude_user_config.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    assert jira_values.restore_claude_user_config(places) == {"action": "no-entry"}
    assert json.loads(places.claude_user_config.read_text(encoding="utf-8")) == {"mcpServers": {}}
    assert not _claude_saved(places).exists()


def test_claude_restore_of_a_deleted_file_writes_the_backup(places):
    before = _claude_world(places)
    places.claude_user_config.unlink()
    assert jira_values.restore_claude_user_config(places) == {"action": "restored"}
    assert places.claude_user_config.read_bytes() == before


def test_claude_restore_of_an_unreadable_file_keeps_the_backup_and_says_no_value(places):
    before = _claude_world(places)
    places.claude_user_config.write_text('{"half": "' + TOKEN, encoding="utf-8")
    answer = jira_values.restore_claude_user_config(places)
    assert answer["action"] == "failed" and answer["backup"] == str(_claude_saved(places))
    assert TOKEN not in json.dumps(answer) and OLD_TOKEN not in json.dumps(answer)
    assert _claude_saved(places).read_bytes() == before
    places.claude_user_config.write_bytes(before)
    assert jira_values.restore_claude_user_config(places) == {"action": "restored"}


def test_env_store_records_each_previous_value_or_absent(places):
    store = FakeUserEnv(JIRA_API_TOKEN=OLD_TOKEN)
    jira_values.store_jira_values(places, VALUES, store)
    assert json.loads(_env_saved(places).read_text(encoding="utf-8")) == {
        "JIRA_BASE_URL": {"absent": True}, "JIRA_EMAIL": {"absent": True}, "JIRA_API_TOKEN": {"value": OLD_TOKEN}}


def test_env_backup_is_written_before_the_first_value(places):
    seen = []

    class Watching(FakeUserEnv):
        def set(self, name, value):
            seen.append(_env_saved(places).exists())
            super().set(name, value)

    jira_values.store_jira_values(places, VALUES, Watching())
    assert seen == [True, True, True]


def test_a_second_env_store_keeps_the_first_backup(places):
    store = FakeUserEnv(JIRA_API_TOKEN=OLD_TOKEN)
    jira_values.store_jira_values(places, VALUES, store)
    first = _env_saved(places).read_bytes()
    jira_values.store_jira_values(places, {**VALUES, "JIRA_API_TOKEN": "third"}, store)
    assert _env_saved(places).read_bytes() == first


def test_a_second_store_adds_only_a_key_the_first_did_not_record(places):
    saved = _env_saved(places)
    saved.parent.mkdir(parents=True)
    saved.write_text(json.dumps({"JIRA_API_TOKEN": {"value": OLD_TOKEN}}), encoding="utf-8")
    jira_values.store_jira_values(places, VALUES, FakeUserEnv(JIRA_API_TOKEN="newer", JIRA_EMAIL="old@example.com"))
    kept = json.loads(saved.read_text(encoding="utf-8"))
    assert kept["JIRA_API_TOKEN"] == {"value": OLD_TOKEN} and kept["JIRA_EMAIL"] == {"value": "old@example.com"}


def test_env_restore_puts_back_values_and_deletes_absent_keys(places):
    store = FakeUserEnv(JIRA_API_TOKEN=OLD_TOKEN, UNRELATED="stays")
    jira_values.store_jira_values(places, VALUES, store)
    store.values["ADDED_LATER"] = "stays too"
    answer = jira_values.restore_user_env(places, store)
    assert answer == {"action": "restored", "keys": {
        "JIRA_BASE_URL": "deleted", "JIRA_EMAIL": "deleted", "JIRA_API_TOKEN": "restored"}}
    assert store.values == {"JIRA_API_TOKEN": OLD_TOKEN, "UNRELATED": "stays", "ADDED_LATER": "stays too"}
    assert not _env_saved(places).exists() and not _env_saved(places).parent.exists()


def test_env_restore_with_no_backup_changes_nothing(places):
    store = FakeUserEnv(JIRA_API_TOKEN=OLD_TOKEN)
    assert jira_values.restore_user_env(places, store) == {"action": "no-backup"}
    assert store.values == {"JIRA_API_TOKEN": OLD_TOKEN}


def test_a_failed_env_restore_keeps_the_backup_and_a_rerun_finishes(places):
    store = FakeUserEnv(JIRA_API_TOKEN=OLD_TOKEN)
    jira_values.store_jira_values(places, VALUES, store)
    store.broken = True
    answer = jira_values.restore_user_env(places, store)
    assert answer["action"] == "failed" and answer["backup"] == str(_env_saved(places))
    assert TOKEN not in json.dumps(answer) and OLD_TOKEN not in json.dumps(answer)
    store.broken = False
    assert jira_values.restore_user_env(places, store)["action"] == "restored"
    assert store.values == {"JIRA_API_TOKEN": OLD_TOKEN}


def test_env_restore_with_no_store_on_this_system_keeps_the_backup(places):
    jira_values.store_jira_values(places, VALUES, FakeUserEnv())
    answer = jira_values.restore_user_env(places, None)
    assert answer["action"] == "failed" and _env_saved(places).exists()


@pytest.mark.parametrize("text", ["{bad", "[1]", '{"JIRA_EMAIL": 3}', '{"JIRA_EMAIL": {"value": 3}}', '{"JIRA_EMAIL": {}}'])
def test_a_bad_env_backup_refuses_with_no_value_in_the_answer(places, text):
    saved = _env_saved(places)
    saved.parent.mkdir(parents=True)
    saved.write_text(text, encoding="utf-8")
    store = FakeUserEnv()
    answer = jira_values.restore_user_env(places, store)
    assert answer["action"] == "failed" and answer["backup"] == str(saved) and store.values == {}


def test_a_bad_env_backup_stops_a_store_before_any_write(places):
    saved = _env_saved(places)
    saved.parent.mkdir(parents=True)
    saved.write_text("{bad", encoding="utf-8")
    store = FakeUserEnv()
    with pytest.raises(ValueError):
        jira_values.store_jira_values(places, VALUES, store)
    assert store.values == {} and saved.read_text(encoding="utf-8") == "{bad"


@pytest.mark.skipif(os.name == "nt", reason="Windows file modes do not carry this protection")
def test_the_env_backup_is_private_on_posix(places):
    jira_values.store_jira_values(places, VALUES, FakeUserEnv())
    assert stat.S_IMODE(_env_saved(places).stat().st_mode) == 0o600
