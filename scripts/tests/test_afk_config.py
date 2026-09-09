"""Contract tests for the single configuration reader.

The point of these is that skills, hooks and the tracker server all get the same
answer. So the suite checks three things: the subset parser accepts exactly what
`CONFIG.md` documents and refuses the rest, the discovery order is the one the
documentation states, and `effective --json`, `export-shell` and `get` agree key
for key.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
SAMPLES = Path(__file__).resolve().parent / "samples"


def _module():
    spec = importlib.util.spec_from_file_location("afk_config", SCRIPTS / "afk-config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cfg = _module()


def run(args, cwd, env=None):
    environ = dict(os.environ)
    environ.pop("AFK_CONFIG", None)
    environ.update(env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "afk-config.py"), *args],
        cwd=str(cwd), capture_output=True, text=True, env=environ,
    )


def repo(tmp_path: Path, name: str = "repo") -> Path:
    root = tmp_path / name
    (root / ".afk").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    return root


# ---- parser: the documented subset ---------------------------------------

def test_block_map_list_and_scalars():
    text = (
        "schema: 1\n"
        "tracker: jira\n"
        "build-gates:\n"
        "  - maven\n"
        "  - npm\n"
        "git:\n"
        "  base-branch: origin/master\n"
        "  branch-pattern: '^team/[a-z]+$'\n"
        "jira:\n"
        "  transitions:\n"
        "    dev-pending: \"12463\"\n"
    )
    document = cfg.parse(text, "t")
    assert document["schema"] == 1
    assert document["build-gates"] == ["maven", "npm"]
    assert document["git"]["branch-pattern"] == "^team/[a-z]+$"
    # A quoted digit string stays a string: transition ids are opaque.
    assert document["jira"]["transitions"]["dev-pending"] == "12463"


def test_comments_and_blank_lines_are_ignored():
    document = cfg.parse("# top\nschema: 1  # trailing\n\ntracker: none\n", "t")
    assert document == {"schema": 1, "tracker": "none"}


def test_hash_inside_a_quoted_scalar_is_content():
    document = cfg.parse("git:\n  branch-pattern: '^a#b$'\n", "t")
    assert document["git"]["branch-pattern"] == "^a#b$"


def test_list_of_maps():
    document = cfg.parse("hooks:\n  - event: Stop\n    script: a.sh\n", "t")
    assert document["hooks"] == [{"event": "Stop", "script": "a.sh"}]


@pytest.mark.parametrize("text", [
    "tracker: {a: 1}\n",
    "build-gates: []\n",
    "build-gates: [maven]\n",
    "anchor: &a 1\n",
    "alias: *a\n",
    "body: |\n  text\n",
    "---\nschema: 1\n",
])
def test_unsupported_syntax_is_refused(text):
    with pytest.raises(cfg.ConfigError):
        cfg.parse(text, "t")


def test_tabs_are_refused():
    with pytest.raises(cfg.ConfigError):
        cfg.parse("git:\n\tbase-branch: x\n", "t")


def test_duplicate_key_is_refused():
    with pytest.raises(cfg.ConfigError):
        cfg.parse("tracker: jira\ntracker: none\n", "t")


# ---- schema ---------------------------------------------------------------

def test_shipped_samples_validate(tmp_path):
    for sample in (SAMPLES / "monorepo-config.yaml",):
        result = run(["validate", str(sample)], tmp_path)
        assert result.returncode == 0, result.stderr


def test_self_config_validates():
    result = run(["validate"], SCRIPTS.parent)
    assert result.returncode == 0, result.stderr


def test_unknown_adapter_is_refused():
    problems = cfg.validate({"schema": 1, "tracker": "trello"})
    assert any("trello" in p for p in problems)


def test_unknown_top_level_key_is_refused():
    problems = cfg.validate({"schema": 1, "traker": "jira"})
    assert any("traker" in p for p in problems)


def test_repo_hook_manifest_outside_the_root_is_refused(tmp_path):
    root = repo(tmp_path)
    problems = cfg.validate({"schema": 1, "repo-hooks": "../outside.json"}, root)
    assert any("outside the repository root" in p for p in problems)


# ---- discovery order ------------------------------------------------------

def test_four_layers_apply_in_the_documented_order(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".afk").mkdir(parents=True)
    (home / ".afk" / "config.yaml").write_text(
        "schema: 1\ntracker: jira\nforge: gitlab\nnotes: obsidian\n", encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda _: home))

    root = repo(tmp_path)
    (root / ".afk" / "config.yaml").write_text(
        "schema: 1\nforge: github\nnotes: notion\n", encoding="utf-8"
    )
    (root / ".afk" / "config.local.yaml").write_text("notes: repo-files\n", encoding="utf-8")

    effective = cfg.load(root)
    assert effective["tracker"] == "jira"        # from the machine layer
    assert effective["forge"] == "github"        # repository beats machine
    assert effective["notes"] == "repo-files"    # local overlay beats repository

    named = tmp_path / "explicit.yaml"
    named.write_text("notes: obsidian\n", encoding="utf-8")
    monkeypatch.setenv("AFK_CONFIG", str(named))
    assert cfg.load(root)["notes"] == "obsidian"  # AFK_CONFIG beats everything


def test_local_overlay_may_not_change_schema(tmp_path):
    root = repo(tmp_path)
    (root / ".afk" / "config.yaml").write_text("schema: 1\n", encoding="utf-8")
    (root / ".afk" / "config.local.yaml").write_text("schema: 2\n", encoding="utf-8")
    with pytest.raises(cfg.ConfigError):
        cfg.load(root)


def test_no_config_gives_the_documented_defaults(tmp_path, monkeypatch):
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda _: home))
    effective = cfg.load(tmp_path / "nowhere")
    assert effective["tracker"] == "none"
    assert effective["forge"] == "none"
    assert effective["notes"] == "repo-files"
    assert "build-gates" not in effective
    assert effective["git"]["base-branch"] == "auto"
    assert effective["git"]["branch-pattern"] == ""
    assert effective["repo-files"]["spec-dir"] == "docs/afk/{workId}"


# ---- the three views agree ------------------------------------------------

def test_effective_export_shell_and_get_agree(tmp_path):
    root = repo(tmp_path)
    (root / ".afk" / "config.yaml").write_text(
        (SAMPLES / "monorepo-config.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )

    effective = json.loads(run(["effective", "--json"], root).stdout)
    exported = run(["export-shell"], root).stdout

    values = {}
    for line in exported.splitlines():
        name, _, raw = line.partition("=")
        values[name] = shlex.split(raw)[0] if raw else ""

    for path, value in cfg.flatten(effective):
        name = cfg.shell_name(path)
        assert name in values, f"{path} missing from export-shell"
        assert values[name] == cfg.shell_value(value), path

    assert values["AFK_CFG_LOADED"] == "1"
    assert values["AFK_CFG_BUILD_GATES_COUNT"] == "2"
    assert values["AFK_CFG_BUILD_GATES_0"] == "maven"
    assert values["AFK_CFG_GIT_BASE_BRANCH"] == "origin/master"

    got = run(["get", "verification.tiers.e2e.command"], root)
    assert got.returncode == 0 and got.stdout.strip() == "npm"
    assert run(["get", "verification.tiers.nope"], root).returncode == 1


def test_export_shell_quotes_values_with_shell_metacharacters(tmp_path):
    root = repo(tmp_path)
    (root / ".afk" / "config.yaml").write_text(
        "schema: 1\ngit:\n  branch-pattern: '^a b;rm -rf /$'\n", encoding="utf-8"
    )
    exported = run(["export-shell"], root).stdout
    line = [l for l in exported.splitlines() if l.startswith("AFK_CFG_GIT_BRANCH_PATTERN=")][0]
    assert shlex.split(line.partition("=")[2])[0] == "^a b;rm -rf /$"


# ---- a typo under a documented map is refused ------------------------------

TYPOS = {
    "jira": "typo-project",
    "github-issues": "typo-repo",
    "gitlab": "typo-remote",
    "github": "typo-remote",
    "git": "typo-base-branch",
    "repo-files": "typo-spec-dir",
    "obsidian": "typo-vault",
    "notion": "typo-parent",
    "artifacts": "typo-service-map",
    "maven": "typo-reactor",
    "npm": "typo-lint",
    "verification": "typo-tiers",
    "setup": "typo-extra",
    "worktree": "typo-copy",
    "developer": "typoReviewer",
}


@pytest.mark.parametrize("name,typo", sorted(TYPOS.items()))
def test_an_unknown_child_key_is_refused_with_its_dotted_path(tmp_path, name, typo):
    root = repo(tmp_path, f"typo-{name}")
    (root / ".afk" / "config.yaml").write_text(
        f"schema: 1\n{name}:\n  {typo}: value\n", encoding="utf-8"
    )
    done = run(["validate"], root)
    assert done.returncode == 2
    assert f"{name}.{typo}: unknown key" in done.stderr


def test_every_map_in_the_schema_is_documented_the_same_way():
    """CONFIG.md and CHILD_KEYS say the same thing, or this test says which."""
    documented = {}
    for line in (SCRIPTS.parent / "CONFIG.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        # A cell may hold an escaped pipe (`a` \| `b`), so split on the
        # unescaped ones only.
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) < 3 or "map" not in cells[1]:
            continue
        for name in re.findall(r"`([^`]+)`", cells[0]):
            documented[name] = set(re.findall(r"`([^`]+)`", cells[2]))
    # Words a row spells in backticks that are VALUES a key may take, not keys.
    values = {
        "isolated", "shared", "auto", "none", "ci", "false", "true",
        "maven", "npm", "*-SNAPSHOT",
    }
    key = re.compile(r"^[a-z][A-Za-z0-9]*(?:-[a-z0-9]+)*$")
    for name, allowed in cfg.CHILD_KEYS.items():
        assert name in documented, f"{name} is in the schema and not in CONFIG.md"
        listed = {word for word in documented[name] if key.match(word)} - values
        assert allowed == listed, (
            f"{name}: schema says {sorted(allowed)}, CONFIG.md says {sorted(listed)}"
        )


# ---- `validate FILE` on a file that cannot be read -------------------------

def test_validate_names_a_missing_file(tmp_path):
    done = run(["validate", str(tmp_path / "absent.yaml")], tmp_path)
    assert done.returncode == 2
    assert "absent.yaml" in done.stderr and "Traceback" not in done.stderr


def test_validate_names_a_directory(tmp_path):
    done = run(["validate", str(tmp_path)], tmp_path)
    assert done.returncode == 2
    assert "Traceback" not in done.stderr


def test_validate_names_a_file_that_is_not_utf8(tmp_path):
    target = tmp_path / "binary.yaml"
    target.write_bytes(b"\xff\xfe\x00schema: 1")
    done = run(["validate", str(target)], tmp_path)
    assert done.returncode == 2
    assert "not UTF-8" in done.stderr and "Traceback" not in done.stderr


def test_validate_still_reads_a_good_file(tmp_path):
    target = tmp_path / "good.yaml"
    target.write_text("schema: 1\n", encoding="utf-8")
    done = run(["validate", str(target)], tmp_path)
    assert done.returncode == 0 and "valid" in done.stdout
