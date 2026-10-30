import json
import sys

import jira_values
import setup

TOKEN = "tok-secret-123"


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
    written = {}
    values = {"JIRA_BASE_URL": "https://s", "JIRA_EMAIL": "dev@example.com", "JIRA_API_TOKEN": TOKEN}
    answer = jira_values.store_jira_values(places, values, written.__setitem__)
    assert answer == {"ok": True, "stored_in": "user environment"} and written == values


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
    stored = {}
    system.set_user_env = stored.__setitem__
    answer = setup.secrets(places, system, {})
    assert answer["ok"] and len(prompts) == 3
    assert stored == {"JIRA_BASE_URL": "https://s.atlassian.net", "JIRA_EMAIL": "dev@example.com",
                      "JIRA_API_TOKEN": TOKEN}
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


def test_user_env_setter_writes_one_plain_value(monkeypatch):
    written = {}

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    class Fake:
        HKEY_CURRENT_USER, KEY_SET_VALUE, REG_SZ = 1, 2, 3
        OpenKey = staticmethod(lambda *_a: Key())
        SetValueEx = staticmethod(lambda _k, name, _r, kind, value: written.update({name: (value, kind)}))

    monkeypatch.setitem(sys.modules, "winreg", Fake)
    monkeypatch.setattr(jira_values, "broadcast_environment_change", lambda: None)
    jira_values.windows_user_env_setter("JIRA_EMAIL", "dev@example.com")
    assert written == {"JIRA_EMAIL": ("dev@example.com", 3)}
