"""End to end on a temporary home and repository through the command line verbs."""

import json
import re

import plugins
import setup
from conftest import NEW_ID, V1_ID, end_marker, fire, hooks_dir, v1_block, v1_stub, write_codex_config

V1_CONFIG = b"tracker: github-issues\nforge: github\ngithub-issues:\n  repo: o/r\ngithub:\n  remote: origin\n"


def _world(places, repo):
    files = {}
    for provider, text in (("claude", "mine\r\n" + v1_block("\r\n") + "more\r\n"),
                           ("codex", v1_block() + "codex\n")):
        path = places.instruction_file(provider)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
        files[path] = path.read_bytes()
    for hook in ("pre-commit", "reference-transaction"):
        (hooks_dir(repo) / hook).write_bytes(v1_stub(hook))
        files[hooks_dir(repo) / hook] = v1_stub(hook)
    (repo / ".afk").mkdir()
    (repo / ".afk" / "config.yaml").write_bytes(V1_CONFIG)
    files[repo / ".afk" / "config.yaml"] = V1_CONFIG
    places.claude_user_settings.write_text(
        json.dumps({"enabledPlugins": {V1_ID: True, NEW_ID: True}}), encoding="utf-8")
    files[places.claude_user_settings] = places.claude_user_settings.read_bytes()
    write_codex_config(places)
    files[places.codex_config] = places.codex_config.read_bytes()
    exclude = repo / ".git" / "info" / "exclude"
    files[exclude] = exclude.read_bytes()
    return files


def _cli(argv, env, system, plugin_root, repo, capsys):
    code = setup.main(argv, env=env, system=system, plugin_root=plugin_root, cwd=repo)
    return code, json.loads(capsys.readouterr().out)


def test_takeover_and_switch_back(env, places, repo, runner, system, plugin_root, capsys):
    files = _world(places, repo)
    runner.paths["python3"] = "/usr/bin/python3"
    places.published_tickets.parent.mkdir(parents=True, exist_ok=True)
    places.published_tickets.write_text(
        "2026-10-30T10:00:00Z PROJ-1 abcd1234\n2026-10-30T11:00:00Z PROJ-1 ef567890\n"
        "2026-10-30T12:00:00Z PROJ-2 00112233\n", encoding="utf-8")

    code, prepared = _cli(["prepare"], env, system, plugin_root, repo, capsys)
    assert code == 0 and prepared["install_record"]["python"] == "/usr/bin/python3 3.12.4"

    code, copied = _cli(["copy-config"], env, system, plugin_root, repo, capsys)
    assert code == 0 and copied["action"] == "copied"

    # The hook fired before setup's install record: no proof, block kept, backup kept.
    code, refused = _cli(["takeover", "--provider", "claude", "--end-marker", end_marker()],
                         env, system, plugin_root, repo, capsys)
    assert code == 1 and refused["v1_block"] == "kept"
    assert any("trust the afkv2 hooks" in r for r in refused["proof"]["reasons"])
    assert (places.backup / "instructions" / "claude" / "original").exists()
    for path, data in files.items():
        assert path.read_bytes() == data, path

    # Both hooks fired in new sessions: takeover.
    fire(places, "claude")
    fire(places, "codex")
    code, done = _cli(["takeover", "--provider", "claude", "--end-marker", end_marker()],
                      env, system, plugin_root, repo, capsys)
    assert code == 0, done
    assert b"afk:behaviors" not in places.instruction_file("claude").read_bytes()
    assert places.instruction_file("claude").read_bytes() == b"mine\r\nmore\r\n"
    assert places.instruction_file("codex").read_bytes() == b"codex\n"
    assert not (hooks_dir(repo) / "pre-commit").exists()
    assert done["plugins"]["claude"]["effective"] == {V1_ID: False, NEW_ID: True}
    assert plugins.claude_effective(places.claude_user_settings, repo) == {V1_ID: False, NEW_ID: True}
    assert done["plugins"]["codex"]["listed"] == {V1_ID: False, NEW_ID: True}
    assert runner.lavish == "0.1.80"
    assert places.claude_user_settings.read_bytes() == files[places.claude_user_settings]
    assert (repo / ".afk" / "config.yaml").read_bytes() == V1_CONFIG

    # A second run changes nothing.
    snapshot = {p: p.read_bytes() for p in (places.instruction_file("claude"),
                                            repo / ".claude" / "settings.local.json",
                                            places.codex_config)}
    code, again = _cli(["takeover", "--provider", "claude", "--end-marker", end_marker()],
                       env, system, plugin_root, repo, capsys)
    assert code == 0 and not again["plugins"]["claude"]["written"]
    assert {p: p.read_bytes() for p in snapshot} == snapshot

    code, back = _cli(["switch-back"], env, system, plugin_root, repo, capsys)
    assert code == 0, back
    assert back["published_tickets"] == ["PROJ-1", "PROJ-2"]
    assert runner.lavish == "0.1.63"
    exclude = repo / ".git" / "info" / "exclude"
    for path, data in files.items():
        if path in (places.codex_config, exclude):
            continue
        assert path.read_bytes() == data, path
    # D-9: only the afkv2 enable value differs, so exactly v1 is on; the local
    # settings file it lives in stays out of git.
    assert exclude.read_bytes() == files[exclude] + b"/.claude/settings.local.json\n"
    codex_now = places.codex_config.read_bytes()
    assert codex_now == re.sub(rb'("afkv2@afk-toolkit"\]\r?\nenabled = )true',
                               rb"\1false", files[places.codex_config])
    local = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert local == {"enabledPlugins": {NEW_ID: False, V1_ID: True}}
    assert plugins.claude_effective(places.claude_user_settings, repo) == {V1_ID: True, NEW_ID: False}
    assert not any((places.backup / sub).exists() and any((places.backup / sub).iterdir())
                   for sub in ("instructions", "git-hooks", "claude-settings", "codex"))


def test_status_reports_without_writing(env, places, repo, system, plugin_root, capsys):
    _world(places, repo)
    code, answer = _cli(["status"], env, system, plugin_root, repo, capsys)
    assert code == 0
    assert answer["v1_blocks"]["claude"]["blocks"] == 1
    assert answer["v1_git_hooks"] == {"pre-commit": True, "reference-transaction": True}
    assert answer["ownership"] == "missing" and answer["v1_config"]["keys"]
    assert not places.data.exists()


def test_bad_arguments_exit_2(env, system, plugin_root, repo, capsys):
    code, answer = _cli(["takeover"], env, system, plugin_root, repo, capsys)
    assert code == 2 and answer["error"]["code"] == "bad-arguments"
