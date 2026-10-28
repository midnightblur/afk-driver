"""The owner rule in the settings reader (`CONFIG.md` "Setting owners").

Each setting is read only from its owner's files: team from the committed file
(the repository personal file when none is committed), personal from the
developer's own files with the machine file as a default, machine from the
machine file. A value anywhere else is absent from every answer and listed by
`validate`.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
PLUGIN = SCRIPTS.parent


def _module():
    spec = importlib.util.spec_from_file_location("afk_config_owner", SCRIPTS / "afk-config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cfg = _module()
TEAM = sorted(k for k, owner in cfg.OWNER_TABLE.items() if owner == cfg.TEAM)
PERSONAL = sorted(k for k, owner in cfg.OWNER_TABLE.items() if owner == cfg.PERSONAL)
MACHINE = sorted(k for k, owner in cfg.OWNER_TABLE.items() if owner == cfg.MACHINE)


@pytest.fixture
def home(tmp_path, monkeypatch):
    folder = tmp_path / "home"
    (folder / ".afk").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda _: folder))
    monkeypatch.delenv("AFK_CONFIG", raising=False)
    return folder


def _repo(tmp_path: Path, name: str = "repo") -> Path:
    root = tmp_path / name
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    return root


def _yaml(setting: str, value: str) -> str:
    head, _, child = setting.partition(".")
    return f"{head}:\n  {child}: {value}\n" if child else f"{head}: {value}\n"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def committed(root: Path, text: str) -> Path:
    return _write(root / ".afk" / "config.yaml", text)


def personal(root: Path, text: str) -> Path:
    return _write(cfg.shared_overlay(root), text)


def local(root: Path, text: str) -> Path:
    return _write(root / ".afk" / "config.local.yaml", text)


def machine(home: Path, text: str) -> Path:
    return _write(home / ".afk" / "config.yaml", text)


def _settings(ignored):
    return [(setting, Path(file).name, rule) for setting, file, rule in ignored]


# ---- team -------------------------------------------------------------------

@pytest.mark.parametrize("setting", [k for k in TEAM if k != "schema"])
def test_a_team_setting_reads_the_committed_file_and_ignores_the_personal_file(
        tmp_path, home, setting):
    root = _repo(tmp_path)
    committed(root, _yaml(setting, "from-committed"))
    shared = personal(root, _yaml(setting, "from-personal"))
    assert cfg.get(cfg.load(root), setting) == "from-committed"
    assert (setting, str(shared), cfg._OWNER_RULES[cfg.TEAM]) in cfg.ignored_values(root)


@pytest.mark.parametrize("setting", [k for k in TEAM if k != "schema"])
def test_with_no_committed_file_a_team_setting_reads_the_personal_file(tmp_path, home, setting):
    root = _repo(tmp_path)
    personal(root, _yaml(setting, "from-personal"))
    assert cfg.get(cfg.load(root), setting) == "from-personal"
    assert cfg.ignored_values(root) == []


@pytest.mark.parametrize("setting", TEAM)
def test_a_team_setting_in_the_machine_file_is_ignored(tmp_path, home, setting):
    root = _repo(tmp_path)
    file = machine(home, _yaml(setting, "from-machine"))
    assert cfg.get(cfg.load(root), setting) != "from-machine"
    assert (setting, str(file), cfg._OWNER_RULES[cfg.TEAM]) in cfg.ignored_values(root)


def test_a_team_setting_in_the_local_overlay_is_ignored_once_a_file_is_committed(tmp_path, home):
    root = _repo(tmp_path)
    committed(root, "forge: github\n")
    overlay = local(root, "forge: gitlab\n")
    assert cfg.load(root)["forge"] == "github"
    assert cfg.ignored_values(root) == [("forge", str(overlay), cfg._OWNER_RULES[cfg.TEAM])]


def test_without_a_committed_file_the_local_overlay_beats_the_personal_file(tmp_path, home):
    root = _repo(tmp_path)
    personal(root, "forge: gitlab\ntracker: jira\n")
    local(root, "forge: github\n")
    effective = cfg.load(root)
    assert (effective["forge"], effective["tracker"]) == ("github", "jira")


# ---- personal ---------------------------------------------------------------

@pytest.mark.parametrize("setting", PERSONAL)
def test_a_personal_setting_in_the_committed_file_is_ignored(tmp_path, home, setting):
    root = _repo(tmp_path)
    file = committed(root, _yaml(setting, "from-committed"))
    assert cfg.get(cfg.load(root), setting) != "from-committed"
    assert cfg.ignored_values(root) == [(setting, str(file), cfg._OWNER_RULES[cfg.PERSONAL])]


@pytest.mark.parametrize("setting", PERSONAL)
def test_a_personal_setting_reads_the_personal_file_over_the_machine_default(
        tmp_path, home, setting):
    root = _repo(tmp_path)
    machine(home, _yaml(setting, "from-machine"))
    assert cfg.get(cfg.load(root), setting) == "from-machine"
    personal(root, _yaml(setting, "from-personal"))
    assert cfg.get(cfg.load(root), setting) == "from-personal"
    local(root, _yaml(setting, "from-local"))
    assert cfg.get(cfg.load(root), setting) == "from-local"
    assert cfg.ignored_values(root) == []


# ---- machine ----------------------------------------------------------------

@pytest.mark.parametrize("setting", MACHINE)
@pytest.mark.parametrize("where", ["committed", "personal", "local"])
def test_a_machine_setting_in_any_repository_file_is_ignored(tmp_path, home, setting, where):
    root = _repo(tmp_path)
    machine(home, _yaml(setting, "from-machine"))
    file = {"committed": committed, "personal": personal, "local": local}[where](
        root, _yaml(setting, f"from-{where}"))
    assert cfg.get(cfg.load(root), setting) == "from-machine"
    assert cfg.ignored_values(root) == [(setting, str(file), cfg._OWNER_RULES[cfg.MACHINE])]


# ---- the files themselves ---------------------------------------------------

def test_the_explicit_file_is_not_filtered(tmp_path, home, monkeypatch):
    root = _repo(tmp_path)
    committed(root, "forge: github\n")
    named = _write(tmp_path / "explicit.yaml", "forge: gitlab\nnotes: obsidian\n")
    monkeypatch.setenv("AFK_CONFIG", str(named))
    effective = cfg.load(root)
    assert (effective["forge"], effective["notes"]) == ("gitlab", "obsidian")
    assert cfg.ignored_values(root) == []


def test_the_personal_file_may_not_hold_schema(tmp_path, home):
    root = _repo(tmp_path)
    personal(root, "schema: 1\n")
    with pytest.raises(cfg.ConfigError, match="may not set `schema`"):
        cfg.load(root)


def test_a_block_left_empty_by_the_filter_is_dropped(tmp_path, home):
    root = _repo(tmp_path)
    committed(root, "worktree:\n  copy-personal: false\n")
    assert cfg.load(root)["worktree"] == cfg.DEFAULTS["worktree"]


def test_unknown_keys_pass_the_filter_for_validate_to_refuse(tmp_path, home):
    root = _repo(tmp_path)
    committed(root, "traker: jira\ndeveloper:\n  typoReviewer: x\n")
    problems = cfg.validate(cfg.load(root), root)
    assert any(p.startswith("traker:") for p in problems)
    assert any(p.startswith("developer.typoReviewer:") for p in problems)


@pytest.mark.parametrize("broken", ["dot-git", "commondir"])
def test_an_unreadable_git_pointer_is_a_reader_error(tmp_path, home, monkeypatch, broken):
    root = tmp_path / "linked"
    root.mkdir()
    admin = tmp_path / "admin"
    admin.mkdir()
    (root / ".git").write_text(f"gitdir: {admin.as_posix()}\n", encoding="utf-8")
    (admin / "commondir").write_text("..\n", encoding="utf-8")
    target = root / ".git" if broken == "dot-git" else admin / "commondir"
    real = Path.read_text

    def refuse(self, *args, **kwargs):
        if self == target:
            raise PermissionError(13, "Permission denied")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", refuse)
    with pytest.raises(cfg.ConfigError, match=re.escape(str(target))):
        cfg.load(root)


# ---- new and removed keys ---------------------------------------------------

def test_the_new_keys_are_accepted_with_their_owners(tmp_path, home):
    assert cfg.OWNER_TABLE["jira.site"] == cfg.TEAM
    assert cfg.OWNER_TABLE["developer.forgeAccount"] == cfg.PERSONAL
    assert cfg.OWNER_TABLE["developer.worktreeRoot"] == cfg.MACHINE
    root = _repo(tmp_path)
    committed(root, "jira:\n  site: https://example.atlassian.net\n")
    personal(root, "developer:\n  forgeAccount: someone\n")
    machine(home, "developer:\n  worktreeRoot: /work/trees\n")
    effective = cfg.load(root)
    assert cfg.validate(effective, root) == []
    assert effective["jira"]["site"] == "https://example.atlassian.net"
    assert effective["developer"] == {"forgeAccount": "someone", "worktreeRoot": "/work/trees"}


@pytest.mark.parametrize("site", ["example.atlassian.net", "https://a b",
                                  "https://example.net/jira", "ftp://example.net"])
def test_a_jira_site_that_is_not_an_address_is_refused(site):
    problems = cfg.validate({"schema": 1, "jira": {"site": site}})
    assert any(p.startswith("jira.site:") for p in problems)


@pytest.mark.parametrize("site", ["https://x.atlassian.net", "https://x.atlassian.net/",
                                  "http://jira.example.net"])
def test_a_jira_site_address_is_accepted(site):
    assert cfg.validate({"schema": 1, "jira": {"site": site}}) == []


def test_validate_accepts_a_parsed_file_holding_the_removed_key():
    document = cfg.parse("schema: 1\njira:\n  project: ABC\n  credentials-env:\n    - X\n", "x")
    assert cfg.validate(cfg.deep_merge(dict(cfg.DEFAULTS), document)) == []


@pytest.mark.parametrize("where", ["committed", "personal", "explicit"])
def test_the_removed_key_is_ignored_in_every_file(tmp_path, home, monkeypatch, where):
    root = _repo(tmp_path)
    text = "jira:\n  project: ABC\n  credentials-env:\n    - JIRA_BASE_URL\n"
    if where == "explicit":
        file = _write(tmp_path / "explicit.yaml", text)
        monkeypatch.setenv("AFK_CONFIG", str(file))
    else:
        file = {"committed": committed, "personal": personal}[where](root, text)
    effective = cfg.load(root)
    assert effective["jira"] == {"project": "ABC"}
    assert cfg.ignored_values(root) == [
        ("jira.credentials-env", str(file), "jira.credentials-env was removed; delete this key")]


# ---- the other calls ---------------------------------------------------------

def test_is_set_up_with_a_committed_file_or_a_personal_file(tmp_path, home):
    root = _repo(tmp_path)
    (root / ".afk").mkdir()
    assert not cfg.is_set_up(root)
    personal(root, "forge: github\n")
    assert cfg.is_set_up(root)
    cfg.shared_overlay(root).unlink()
    committed(root, "schema: 1\n")
    assert cfg.is_set_up(root)


def test_parse_single_file_reads_one_file_unfiltered(tmp_path, home):
    file = machine(home, "tracker: jira\ndeveloper:\n  worktreeRoot: /w\n")
    assert cfg.parse_single_file(file) == {"tracker": "jira", "developer": {"worktreeRoot": "/w"}}
    assert cfg.parse_single_file(tmp_path / "absent.yaml") == {}


def test_load_still_returns_a_plain_dictionary(tmp_path, home):
    root = _repo(tmp_path)
    committed(root, "forge: github\n")
    assert type(cfg.load(root)) is dict


def test_the_owner_rule_reads_no_new_file(tmp_path, home, monkeypatch):
    root = _repo(tmp_path)
    machine(home, "developer:\n  mrReviewer: a\n")
    committed(root, "forge: github\ndeveloper:\n  mrReviewer: b\n")
    personal(root, "developer:\n  mrReviewer: c\n")
    local(root, "notes: obsidian\n")
    reads: list[Path] = []
    real = Path.read_text

    def counted(self, *args, **kwargs):
        reads.append(self)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted)
    cfg.load(root)
    assert len(reads) == 4 and len(set(reads)) == 4


def test_informational_bench_of_the_owner_rule(tmp_path, home, monkeypatch, record_property):
    """Measures the time the filter adds per load; reported, never asserted."""
    root = _repo(tmp_path)
    machine(home, "notes: repo-files\ndeveloper:\n  mrReviewer: a\n")
    committed(root, (PLUGIN / "scripts" / "tests" / "samples" / "monorepo-config.yaml")
              .read_text(encoding="utf-8"))
    personal(root, "developer:\n  mrReviewer: c\n")

    def per_load(runs: int = 200) -> float:
        start = time.perf_counter()
        for _ in range(runs):
            cfg.load(root)
        return (time.perf_counter() - start) * 1000 / runs

    filtered = per_load()
    monkeypatch.setattr(cfg, "_owner_filter", lambda kind, document, *rest: document)
    plain = per_load()
    added = filtered - plain
    record_property("owner_rule_added_ms_per_load", round(added, 3))
    print(f"owner rule added {added:.3f} ms per load ({filtered:.3f} vs {plain:.3f})")


# ---- the command line -------------------------------------------------------

def run(args, cwd, home):
    environ = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    for name in ("AFK_CONFIG", "CLAUDE_PROJECT_DIR"):
        environ.pop(name, None)
    return subprocess.run([sys.executable, str(SCRIPTS / "afk-config.py"), *args],
                          cwd=str(cwd), capture_output=True, text=True, env=environ)


def test_validate_prints_valid_then_one_warning_per_ignored_value(tmp_path, home):
    root = _repo(tmp_path)
    committed_file = committed(
        root, "schema: 1\nforge: github\nnotes: obsidian\ngithub:\n  remote: origin\n"
              "jira:\n  credentials-env:\n    - JIRA_BASE_URL\n")
    shared = personal(root, "forge: gitlab\n")
    done = run(["validate"], root, home)
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == [
        "afk-config: configuration is valid",
        f"afk-config: warning: notes in {committed_file} is ignored: "
        "a machine setting is read only from the machine file",
        f"afk-config: warning: github.remote in {committed_file} is ignored: "
        "a personal setting is never read from the committed file",
        f"afk-config: warning: jira.credentials-env was removed; delete this key ({committed_file})",
        f"afk-config: warning: forge in {shared} is ignored: "
        "a team setting is read from the committed file, else the repository personal file",
    ]


def test_validate_still_refuses_an_unknown_key_beside_ignored_values(tmp_path, home):
    root = _repo(tmp_path)
    committed(root, "schema: 1\ntraker: jira\nnotes: obsidian\n")
    done = run(["validate"], root, home)
    assert done.returncode == 2
    assert "traker: unknown top-level key" in done.stderr
    assert "notes in" in done.stderr and "configuration is valid" not in done.stdout


def test_validate_of_one_named_file_filters_it_as_its_layer(tmp_path, home):
    root = _repo(tmp_path)
    file = committed(root, "schema: 1\ndeveloper:\n  mrReviewer: me\n")
    done = run(["validate", str(file)], root, home)
    assert done.returncode == 0, done.stderr
    assert f"developer.mrReviewer in {file} is ignored" in done.stdout


@pytest.mark.parametrize("layer, text, setting, outside", [
    ("personal", "notes: obsidian\n", "notes", False),
    ("personal", "notes: obsidian\n", "notes", True),
    ("local", "notes: obsidian\n", "notes", False),
    ("machine", "tracker: jira\n", "tracker", False),
    ("machine", "tracker: jira\n", "tracker", True),
])
def test_validate_of_one_named_file_filters_every_layer(tmp_path, home, layer, text, setting,
                                                        outside):
    root = _repo(tmp_path)
    file = machine(home, text) if layer == "machine" else {"personal": personal,
                                                           "local": local}[layer](root, text)
    done = run(["validate", str(file)], tmp_path if outside else root, home)
    assert done.returncode == 0, done.stderr
    assert f"{setting} in {file} is ignored" in done.stdout


def test_validate_of_a_named_personal_file_refuses_schema_from_outside_the_checkout(
        tmp_path, home):
    root = _repo(tmp_path)
    file = personal(root, "schema: 1\nnotes: obsidian\n")
    done = run(["validate", str(file)], tmp_path, home)
    assert done.returncode == 2
    assert "may not set `schema`" in done.stderr


def test_validate_of_a_named_personal_file_checks_paths_under_its_checkout(tmp_path, home):
    root = _repo(tmp_path)
    (root / "web").mkdir()
    file = personal(root, "npm:\n  workspace-root: web\n")
    done = run(["validate", str(file)], tmp_path, home)
    assert done.returncode == 0, done.stderr
    assert "does not exist" not in done.stderr


def test_validate_of_the_committed_file_of_a_checkout_at_home_reads_it_as_both_layers(home):
    subprocess.run(["git", "init", "-q"], cwd=str(home), check=True)
    file = machine(home, "schema: 1\ntracker: jira\nnotes: obsidian\n")
    done = run(["validate", str(file)], home, home)
    assert done.returncode == 0, done.stderr
    assert "is ignored" not in done.stdout


def test_validate_of_a_file_under_a_folder_named_git_that_is_not_one_reads_it_whole(
        tmp_path, home):
    file = _write(tmp_path / "plain" / ".git" / "afk" / "config.yaml",
                  "schema: 1\nnotes: obsidian\n")
    done = run(["validate", str(file)], tmp_path, home)
    assert done.returncode == 0, done.stderr
    assert "is ignored" not in done.stdout


def test_every_reader_view_leaves_an_ignored_value_out(tmp_path, home):
    root = _repo(tmp_path)
    committed(root, "schema: 1\nnotes: obsidian\ndeveloper:\n  mrReviewer: committed\n")
    effective = json.loads(run(["effective", "--json"], root, home).stdout)
    assert effective["notes"] == "repo-files" and "developer" not in effective
    exported = dict(line.partition("=")[::2] for line in
                    run(["export-shell"], root, home).stdout.splitlines())
    assert shlex.split(exported["AFK_CFG_NOTES"]) == ["repo-files"]
    assert "AFK_CFG_DEVELOPER_MRREVIEWER" not in exported
    assert run(["get", "developer.mrReviewer"], root, home).returncode == 1
    assert run(["resolve", "mrReviewer"], root, home).returncode == 1


# ---- the owner table and CONFIG.md agree ------------------------------------

def _documented_owners() -> dict[str, str]:
    text = (PLUGIN / "CONFIG.md").read_text(encoding="utf-8")
    section = text.split("## Setting owners", 1)[1].split("\n## ", 1)[0]
    owners: dict[str, str] = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] not in (cfg.TEAM, cfg.PERSONAL, cfg.MACHINE):
            continue
        for name in re.findall(r"`([^`]+)`", cells[2]):
            block = name.removesuffix(".*")
            children = (cfg.CHILD_KEYS.get(block) or (cfg.INVESTIGATION_KEYS if block == "investigation"
                                                      else None)) if name.endswith(".*") else None
            for setting in ([f"{block}.{c}" for c in children] if children else [name]):
                assert setting not in owners, f"{setting} is listed twice in CONFIG.md"
                owners[setting] = cells[0]
    return owners


def test_the_owner_table_matches_config_md():
    assert _documented_owners() == cfg.OWNER_TABLE


def test_the_owner_table_covers_every_setting_of_the_schema():
    blocks = {**cfg.CHILD_KEYS, "investigation": cfg.INVESTIGATION_KEYS}
    every = {f"{block}.{child}" for block, children in blocks.items() for child in children}
    every |= cfg.TOP_LEVEL - set(blocks)
    assert set(cfg.OWNER_TABLE) == every


def test_the_top_level_key_list_stays_a_literal():
    source = (SCRIPTS / "afk-config.py").read_text(encoding="utf-8")
    block = re.search(r"TOP_LEVEL\s*=\s*\{([^}]*)\}", source)
    assert block and set(re.findall(r'"([^"]+)"', block.group(1))) == cfg.TOP_LEVEL


# ---- notes kinds keep agent files in the repository ------------------------

_hooks = importlib.util.spec_from_file_location("afk_run_hook_for_owner", PLUGIN / "hooks" / "run-hook.py")
_runner = importlib.util.module_from_spec(_hooks)
_hooks.loader.exec_module(_runner)
BASH = _runner.find_bash()


@pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")
@pytest.mark.parametrize("kind", ["repo-files", "obsidian"])
def test_every_file_backed_notes_kind_resolves_the_spec_folder_in_the_repository(
        tmp_path, home, kind):
    root = _repo(tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    machine(home, f"notes: {kind}\nobsidian:\n  vault: {vault.as_posix()}\n")
    committed(root, "schema: 1\nrepo-files:\n  spec-dir: 'specs/{workId}'\n")
    environ = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
               "AFK_PLUGIN_ROOT": PLUGIN.as_posix()}
    environ.pop("AFK_CONFIG", None)
    done = subprocess.run([str(BASH), (PLUGIN / "adapters" / "notes" / kind / "notes.sh").as_posix(),
                           "note-create", '{"workId": "W-1", "name": "PRD.md", "content": "x"}'],
                          cwd=str(root), capture_output=True, text=True, env=environ)
    assert done.returncode == 0, done.stdout + done.stderr
    written = Path(json.loads(done.stdout)["path"])
    assert written.resolve() == (root / "specs" / "W-1" / "PRD.md").resolve()
    assert list(vault.iterdir()) == []


def test_every_notes_kind_declares_the_spec_folder_key():
    for manifest in sorted((PLUGIN / "adapters" / "notes").glob("*/adapter.json")):
        keys = json.loads(manifest.read_text(encoding="utf-8"))["configKeys"]
        assert "repo-files.spec-dir" in keys, manifest.parent.name
