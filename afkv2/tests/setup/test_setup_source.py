"""The source verb of setup: suggest, write and refuse with real git; the status field; the record readers; the step."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

import other_provider
import setup
from conftest import git_env

PLUGIN = Path(__file__).resolve().parents[2]
SKILL_MD = PLUGIN / "skills" / "setup" / "SKILL.md"
STEP = re.compile(r"^ *```sh step=([\w-]+)\n *(.*?)\n *```", re.S | re.M)


def _git(home, *args):
    subprocess.run(["git", *args], check=True, capture_output=True, env=git_env(home))


def _repo(path, home):
    path.mkdir(parents=True)
    _git(home, "init", "-q", str(path))
    return path


def _plugin(path, home):
    """A main checkout of the plugin source: the plugin manifest and the root marketplace entry, committed."""
    _repo(path, home)
    (path / "afkv2" / ".claude-plugin").mkdir(parents=True)
    (path / "afkv2" / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "afkv2"}), encoding="utf-8")
    (path / ".claude-plugin").mkdir()
    (path / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "afkv2", "source": "./afkv2"}, {"name": "afk", "source": "./"}]}),
        encoding="utf-8")
    _git(home, "-C", str(path), "add", "-A")
    _git(home, "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "x")
    return path


def _cli(argv, env, system, cwd, capsys):
    code = setup.main(argv, env=env, system=system, cwd=cwd)
    return code, json.loads(capsys.readouterr().out)


@pytest.fixture
def home(places):
    return places.home


@pytest.fixture
def area(tmp_path):
    """The parent folder of the current repository."""
    path = tmp_path / "area"
    path.mkdir()
    return path


@pytest.fixture
def work(area, home):
    return _repo(area / "work", home)


def _record_bytes(places):
    return places.install_record.read_bytes() if places.install_record.exists() else None


# ------------------------------------------------------------ suggest (VR-058)

def test_source_suggests_a_checkout_two_levels_under_the_parent(area, work, home, env, system, places, capsys):
    plugin = _plugin(area / "group" / "afk src", home)
    code, answer = _cli(["source"], env, system, work, capsys)
    assert code == 0
    assert answer == {"ok": True, "status": "suggested", "path": str(plugin)}
    assert not places.install_record.exists()


def test_source_suggests_a_checkout_two_levels_under_the_home_folder(tmp_path, home, env, system, capsys):
    plugin = _plugin(home / "code" / "afk", home)
    outside = tmp_path / "plain"
    outside.mkdir()
    code, answer = _cli(["source"], env, system, outside, capsys)
    assert (code, answer["status"], answer["path"]) == (0, "suggested", str(plugin))


def test_source_suggests_the_main_checkout_of_the_current_worktree(area, home, env, system, capsys):
    plugin = _plugin(area / "deep" / "er" / "plugin", home)
    linked = area / "deep" / "er" / "linked"
    _git(home, "-C", str(plugin), "worktree", "add", "-q", "-b", "side", str(linked))
    code, answer = _cli(["source"], env, system, linked, capsys)
    assert Path(answer["path"]).resolve() == plugin.resolve() and answer["status"] == "suggested"


def test_source_answers_none_for_a_checkout_three_levels_deep(area, work, home, env, system, capsys):
    _plugin(area / "a" / "b" / "plugin", home)
    code, answer = _cli(["source"], env, system, work, capsys)
    assert (code, answer) == (0, {"ok": True, "status": "none", "path": None})


def test_source_answers_none_when_no_checkout_exists(area, work, home, env, system, capsys):
    _repo(area / "other", home)
    code, answer = _cli(["source"], env, system, work, capsys)
    assert (code, answer["status"], answer["path"]) == (0, "none", None)


def test_source_lists_only_the_bounded_search_roots(area, work, home, env, system, monkeypatch, capsys):
    (area / "a" / "b" / "c").mkdir(parents=True)
    (home / "h1" / "h2" / "h3").mkdir(parents=True)
    listed = []
    real = setup._child_folders

    def record(folder):
        listed.append(Path(folder).resolve())
        return real(folder)

    monkeypatch.setattr(setup, "_child_folders", record)
    _cli(["source"], env, system, work, capsys)
    allowed = {area.resolve(), home.resolve()}
    allowed |= {child.resolve() for root in (area, home) for child in root.iterdir() if child.is_dir()}
    assert listed and set(listed) <= allowed
    assert area.resolve() in listed and home.resolve() in listed


# ------------------------------------------------------------ write and refuse (VR-059)

def test_source_writes_one_line_and_the_same_path_again_changes_nothing(tmp_path, work, home, env, system, places,
                                                                       capsys):
    plugin = _plugin(tmp_path / "src" / "plugin", home)
    code, answer = _cli(["source", "--path", str(plugin)], env, system, work, capsys)
    assert (code, answer) == (0, {"ok": True, "status": "written", "path": str(plugin), "changed": True})
    first = places.install_record.read_bytes()
    code, again = _cli(["source", "--path", str(plugin)], env, system, work, capsys)
    assert (code, again["status"], again["changed"]) == (0, "written", False)
    assert places.install_record.read_bytes() == first
    lines = [line for line in first.decode("utf-8").splitlines() if line.startswith("source ")]
    assert lines == [f"source {plugin}"]


def test_source_keeps_a_path_with_spaces_whole(tmp_path, home, env, system, places, capsys):
    plugin = _plugin(tmp_path / "my plugins" / "afk src", home)
    code, answer = _cli(["source", "--path", str(plugin)], env, system, tmp_path, capsys)
    assert code == 0 and answer["status"] == "written"
    assert setup.read_install_record(places)["source"] == str(plugin)


@pytest.mark.parametrize("kind, code_name", [
    ("linked", "not-main-checkout"),
    ("other", "not-plugin-source"),
    ("no-marketplace", "not-plugin-source"),
    ("plain", "not-a-repo"),
    ("inside", "not-a-repo"),
    ("absent", "not-a-repo"),
])
def test_source_refuses_and_leaves_the_record(kind, code_name, tmp_path, home, env, system, places, capsys):
    setup.write_install_record(places, {"path": "/py", "version": "3.12"}, "/rg")
    before = _record_bytes(places)
    plugin = _plugin(tmp_path / "plugin", home)
    target = {"linked": tmp_path / "linked", "other": tmp_path / "other", "no-marketplace": tmp_path / "half",
              "plain": tmp_path / "plain", "inside": plugin / "afkv2", "absent": tmp_path / "gone"}[kind]
    if kind == "linked":
        _git(home, "-C", str(plugin), "worktree", "add", "-q", "-b", "side", str(target))
    elif kind == "other":
        _repo(target, home)
    elif kind == "no-marketplace":
        _plugin(target, home)
        (target / ".claude-plugin" / "marketplace.json").write_text(json.dumps({"plugins": []}), encoding="utf-8")
    elif kind == "plain":
        target.mkdir()
    code, answer = _cli(["source", "--path", str(target)], env, system, tmp_path, capsys)
    assert code == 1 and answer["ok"] is False and answer["error"]["code"] == code_name
    assert _record_bytes(places) == before


def test_source_refuses_a_relative_path(tmp_path, home, env, system, places, capsys):
    _plugin(tmp_path / "plugin", home)
    code, answer = _cli(["source", "--path", "plugin"], env, system, tmp_path, capsys)
    assert code == 2 and answer["error"]["code"] == "bad-arguments" and "absolute" in answer["error"]["reason"]
    assert not places.install_record.exists()


# ------------------------------------------------------------ prepare keeps the line (VR-060)

def test_prepare_keeps_the_source_line(tmp_path, work, home, env, system, runner, places, capsys):
    plugin = _plugin(tmp_path / "src" / "plugin", home)
    assert _cli(["source", "--path", str(plugin)], env, system, work, capsys)[0] == 0
    runner.paths["python3"] = "/usr/bin/python3"
    assert _cli(["prepare"], env, system, work, capsys)[0] == 0
    assert setup.read_install_record(places)["source"] == str(plugin)


# ------------------------------------------------------------ status (VR-061)

def test_status_reads_the_source_field(tmp_path, work, home, env, system, places, capsys):
    plugin = _plugin(tmp_path / "src" / "plugin", home)
    assert _cli(["status"], env, system, work, capsys)[1]["source"] == "missing"
    assert _cli(["source", "--path", str(plugin)], env, system, work, capsys)[0] == 0
    assert _cli(["status"], env, system, work, capsys)[1]["source"] == "ok"
    (plugin / "afkv2" / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "other"}), encoding="utf-8")
    assert _cli(["status"], env, system, work, capsys)[1]["source"] == "broken"
    record = setup.read_install_record(places)
    record["source"] = str(tmp_path / "gone")
    setup._write_record(places, record)
    assert _cli(["status"], env, system, work, capsys)[1]["source"] == "broken"


# ------------------------------------------------------------ the existing readers (VR-062)

def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_record_readers_ignore_the_source_line(tmp_path, home, env, system, places, monkeypatch, capsys):
    monkeypatch.setenv("LOCALAPPDATA", env["LOCALAPPDATA"])
    end_gate = _load(PLUGIN / "skills" / "autopilot" / "scripts" / "end_gate.py", "seam_end_gate")
    record = {"installed": "2026-11-26T00:00:00+00:00", other_provider.JUDGE_KEY.format(provider="codex"): "gpt-x",
              end_gate.DRIVER_KEY: "0.1 2026-11-26T00:00:00+00:00"}
    setup._write_record(places, record)
    without = (other_provider._judge_models(), end_gate._driver_proven())
    plugin = _plugin(tmp_path / "my plugins" / "afk src", home)
    assert _cli(["source", "--path", str(plugin)], env, system, tmp_path, capsys)[0] == 0
    assert f"source {plugin}\n" in places.install_record.read_text(encoding="utf-8")
    assert (other_provider._judge_models(), end_gate._driver_proven()) == without == ({"codex": "gpt-x"}, True)


# ------------------------------------------------------------ the setup step (VR-063)

def test_the_setup_skill_holds_the_source_step():
    text = SKILL_MD.read_text(encoding="utf-8")
    steps = dict(STEP.findall(text))
    assert steps.get("source") == "setup.py source"
    block = text.index("```sh step=source")
    step = text[text.rindex("\n\n", 0, block):text.index("\n\n", block)]
    assert "`source` is `ok`: ask nothing" in step
    assert "`source` is `missing` or `broken`" in step
    assert "--path" in step and "not-main-checkout" in step and "not-plugin-source" in step and "not-a-repo" in step
    assert text.index("**Prepare.**") < block < text.index("**herdr.**")
