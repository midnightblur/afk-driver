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
    environ.pop("CLAUDE_PROJECT_DIR", None)
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


def _commit(root: Path) -> None:
    for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "T"],
                 ["commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True)


def test_the_shared_overlay_sits_between_repository_and_checkout(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda _: home))
    monkeypatch.delenv("AFK_CONFIG", raising=False)
    root = repo(tmp_path)
    (root / ".afk" / "config.yaml").write_text("schema: 1\nforge: github\nnotes: notion\n",
                                               encoding="utf-8")
    shared = cfg.shared_overlay(root)
    assert shared.resolve() == (root / ".git" / "afk" / "config.yaml").resolve()
    shared.parent.mkdir(parents=True)
    shared.write_text("forge: gitlab\nnotes: obsidian\n", encoding="utf-8")
    (root / ".afk" / "config.local.yaml").write_text("notes: repo-files\n", encoding="utf-8")

    effective = cfg.load(root)
    assert effective["forge"] == "gitlab"        # shared overlay beats repository
    assert effective["notes"] == "repo-files"    # checkout overlay beats shared overlay


def test_every_worktree_reads_the_same_shared_overlay(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda _: home))
    monkeypatch.delenv("AFK_CONFIG", raising=False)
    root = repo(tmp_path)
    _commit(root)
    linked = tmp_path / "linked"
    subprocess.run(["git", "worktree", "add", "-q", str(linked)], cwd=str(root), check=True,
                   capture_output=True)
    assert cfg.shared_overlay(linked).resolve() == cfg.shared_overlay(root).resolve()

    shared = cfg.shared_overlay(root)
    shared.parent.mkdir(parents=True)
    shared.write_text("developer:\n  mrReviewer: someone\n", encoding="utf-8")
    assert cfg.developer_value(cfg.load(linked), "mrReviewer") == "someone"


def test_shared_overlay_may_not_change_schema(tmp_path, monkeypatch):
    monkeypatch.delenv("AFK_CONFIG", raising=False)
    root = repo(tmp_path)
    shared = cfg.shared_overlay(root)
    shared.parent.mkdir(parents=True)
    shared.write_text("schema: 2\n", encoding="utf-8")
    with pytest.raises(cfg.ConfigError):
        cfg.load(root)


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
    assert effective["review"]["ledger-only-paths"] == [
        "plan/review/**",
        "plan/JOURNAL.md",
    ]


def test_review_ledger_only_paths_override_replaces_the_default(tmp_path, monkeypatch):
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda _: home))
    root = repo(tmp_path)
    (root / ".afk" / "config.yaml").write_text(
        "schema: 1\nreview:\n  ledger-only-paths:\n    - docs/review/**\n",
        encoding="utf-8",
    )

    assert cfg.load(root)["review"]["ledger-only-paths"] == ["docs/review/**"]


@pytest.mark.parametrize(
    "value,problem",
    [
        ("plan/review/**", "block list"),
        (["!plan/review/private/**"], "does not support negation"),
        (["/plan/review/**"], "repository-relative"),
        (["plan\\review\\**"], "forward slashes"),
        ([1], "must be a path glob"),
    ],
)
def test_review_ledger_only_paths_rejects_invalid_values(value, problem):
    problems = cfg.validate(
        {"schema": 1, "review": {"ledger-only-paths": value}}
    )
    assert any(problem in item for item in problems)


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
    "review": "typo-ledger-paths",
    "transport": "typo-kind",
    "multiplexer": "typo-key",
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
        "maven", "npm", "*-SNAPSHOT", "pane", "subagent",
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


# ------------------------------------------------- configured paths must exist

PATH_CONFIG = """schema: 1
repo-hooks: .afk/missing-hooks.json
maven:
  reactor-pom: missing-pom.xml
  formatter-config: missing-format.xml
  default-module: missing-module
setup:
  extra:
    - docs/x.md
npm:
  workspace-root: missing-ui
"""

MISSING_KEYS = ("repo-hooks", "maven.reactor-pom", "maven.formatter-config",
                "maven.default-module", "setup.extra", "npm.workspace-root")


def _git_repo(tmp_path, text):
    repo = tmp_path / "repo"
    (repo / ".afk").mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True)
    (repo / ".afk" / "config.yaml").write_text(text, encoding="utf-8")
    return repo


def test_a_missing_configured_path_is_a_warning(tmp_path):
    result = run(["validate"], _git_repo(tmp_path, PATH_CONFIG))
    assert result.returncode == 0, result.stderr
    lines = [l for l in result.stderr.splitlines() if l.startswith("afk-config: warning: ")]
    assert len(lines) == len(MISSING_KEYS)
    for key in MISSING_KEYS:
        assert sum(l.startswith(f"afk-config: warning: {key}: ") for l in lines) == 1
    assert "docs/x.md does not exist under the repository root" in result.stderr
    assert "configuration is valid (6 warnings)" in result.stdout


def test_present_paths_warn_nothing(tmp_path):
    repo = _git_repo(tmp_path, PATH_CONFIG)
    for name in (".afk/missing-hooks.json", "missing-pom.xml", "missing-format.xml", "docs/x.md"):
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text("x", encoding="utf-8")
    for name in ("missing-module", "missing-ui"):
        (repo / name).mkdir()
    result = run(["validate"], repo)
    assert result.returncode == 0 and "warning" not in result.stderr
    assert result.stdout.strip() == "afk-config: configuration is valid"


def test_a_warning_never_masks_a_problem(tmp_path):
    repo = _git_repo(tmp_path, """schema: 1
tracker: trello
maven:
  reactor-pom: nope-pom.xml
""")
    result = run(["validate"], repo)
    assert result.returncode == 2
    assert "trello" in result.stderr and "maven.reactor-pom: nope-pom.xml" in result.stderr


def test_no_config_no_path_warnings(tmp_path):
    repo = tmp_path / "bare"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True)
    home = tmp_path / "home"
    home.mkdir()
    result = run(["validate"], repo, env={"HOME": str(home), "USERPROFILE": str(home)})
    assert result.returncode == 0 and "warning" not in result.stderr


def test_path_warnings_unit(tmp_path):
    (tmp_path / "a-pom.xml").write_text("x", encoding="utf-8")
    config = {"maven": {"reactor-pom": "a-pom.xml", "worktree-seed": "~/nowhere/.m2"},
              "setup": {"extra": ["gone.md", 7]}}
    assert cfg.path_warnings(config, None) == []
    assert cfg.path_warnings(config, tmp_path) == [
        "setup.extra: gone.md does not exist under the repository root"]


# ---- team keys: transport settings, kind blocks, stage map, saved patterns --

TEAM_CONFIG = """schema: 1
transport:
  kind: multiplexer
  pane-switch: subagent
stage-map:
  to-sdd: debate
  review:
    - review-panel
    - my-team
patterns:
  my-team:
    name: my-team
    description: two builders and a checker
    charter: build, then check each other
    schema-version: 1
    record-version: 1
    includes:
      - solo
    roles:
      builder:
        model: frontier
        lifespan: step
        count: 2
        report-target: checker
        hub: false
        charter: build the slice
      checker:
        model: frontier
        lifespan: step
        charter: check the slice
    edges:
      - from: builder
        to: checker
    steps:
      - name: build
"""


def _validate_text(tmp_path, text, name="config.yaml"):
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return run(["validate", str(target)], tmp_path)


def test_every_team_key_and_pattern_field_reads(tmp_path):
    done = _validate_text(tmp_path, TEAM_CONFIG)
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize("text,refusal", [
    ("patterns:\n  debate:\n    description: mine\n",
     "patterns.debate: `debate` is a built-in pattern's name"),
    ("patterns:\n  Afk_Lite:\n    description: mine\n",
     "patterns.Afk_Lite: `afk-lite` is a built-in pattern's name"),
    ("patterns:\n  my-team:\n    description: a\n  my_team:\n    description: b\n",
     "`my-team` and `my_team` are 2 saved patterns with one name"),
    ("patterns:\n  my-team:\n    description: a\n  my-team:\n    description: b\n",
     "duplicate key 'my-team'"),
    ("patterns:\n  my-team:\n    includes:\n      - nowhere\n",
     "patterns.my-team.includes: 'nowhere' names no pattern"),
    ("stage-map:\n  to-sdd: nowhere\n", "stage-map.to-sdd: 'nowhere' names no pattern"),
    ("stage-map:\n  review:\n    - debate\n    - nowhere\n",
     "stage-map.review: 'nowhere' names no pattern"),
])
def test_the_reader_refuses_the_three_pattern_errors(tmp_path, text, refusal):
    done = _validate_text(tmp_path, "schema: 1\n" + text)
    assert done.returncode == 2
    assert refusal in done.stderr, done.stderr


def test_includes_and_stage_entries_may_name_built_in_or_saved_patterns(tmp_path):
    done = _validate_text(tmp_path, (
        "schema: 1\npatterns:\n  mine:\n    includes:\n      - debate\n"
        "  other:\n    includes:\n      - mine\nstage-map:\n  fix: other\n"
        "  review:\n    - afk-lite\n    - mine\n"))
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize("value", ["pane", "subagent", None])
def test_the_pane_switch_reads_pane_subagent_or_nothing(tmp_path, value):
    line = f"transport:\n  pane-switch: {value}\n" if value else ""
    done = _validate_text(tmp_path, "schema: 1\n" + line)
    assert done.returncode == 0, done.stderr


def test_another_pane_switch_value_is_refused(tmp_path):
    done = _validate_text(tmp_path, "schema: 1\ntransport:\n  pane-switch: panes\n")
    assert done.returncode == 2
    assert "transport.pane-switch: 'panes' is not one of pane, subagent" in done.stderr


def test_the_pane_switch_is_read_back_not_refused(tmp_path):
    root = repo(tmp_path)
    (root / ".afk" / "config.yaml").write_text(
        "schema: 1\ntransport:\n  pane-switch: subagent\n", encoding="utf-8")
    got = run(["get", "transport.pane-switch"], root)
    assert got.returncode == 0 and got.stdout.strip() == "subagent"
    assert run(["validate"], root).returncode == 0


@pytest.mark.parametrize("kind", ["subagent", "headless", "multiplexer", "desktop"])
def test_the_kind_override_names_one_kind(tmp_path, kind):
    done = _validate_text(tmp_path, f"schema: 1\ntransport:\n  kind: {kind}\n")
    assert done.returncode == 0, done.stderr


def test_an_unknown_kind_is_refused_and_absent_means_the_probe_chooses(tmp_path):
    done = _validate_text(tmp_path, "schema: 1\ntransport:\n  kind: tmux\n")
    assert done.returncode == 2
    assert ("transport.kind: 'tmux' is not one of subagent, headless, multiplexer, desktop"
            in done.stderr)
    root = repo(tmp_path)
    (root / ".afk" / "config.yaml").write_text("schema: 1\n", encoding="utf-8")
    absent = run(["get", "transport.kind"], root)
    assert absent.returncode == 1 and absent.stdout == ""
    assert cfg.validate({"schema": 1, "transport": {"pane-switch": "pane"}}) == []


def test_every_transport_kind_has_its_settings_block():
    assert set(cfg.TRANSPORTS) <= cfg.TOP_LEVEL
    assert all(cfg.CHILD_KEYS[kind] == set() for kind in cfg.TRANSPORTS)


def test_a_kind_block_takes_no_keys_yet(tmp_path):
    done = _validate_text(tmp_path, "schema: 1\ndesktop:\n  tool: x\n")
    assert done.returncode == 2
    assert "desktop.tool: unknown key; `desktop` takes no keys yet" in done.stderr


def test_the_charter_fields_read_and_an_unknown_role_field_is_refused(tmp_path):
    done = _validate_text(tmp_path, (
        "schema: 1\npatterns:\n  mine:\n    charter: the pattern part\n    roles:\n"
        "      lead:\n        charter: the role part\n        modle: frontier\n"))
    assert done.returncode == 2
    refusals = [line for line in done.stderr.splitlines() if "afk-config: " in line]
    assert refusals == [
        "afk-config: patterns.mine.roles.lead.modle: unknown role field; expected one of "
        "charter, count, hub, lifespan, model, report-target"], done.stderr


@pytest.mark.parametrize("text,problem", [
    ("patterns:\n  mine:\n    charter: 7\n", "patterns.mine.charter: must be a string"),
    ("patterns:\n  mine:\n    roles:\n      - lead\n",
     "patterns.mine.roles: must be a mapping of role name to role"),
    ("patterns:\n  mine:\n    team: x\n", "patterns.mine.team: unknown key"),
    ("patterns:\n  mine:\n    name: yours\n", "patterns.mine.name: 'yours' differs from its key"),
    ("stage-map:\n  review:\n", "stage-map.review: must be one pattern name or a block list"),
    ("stage-map:\n  review:\n    - a: b\n",
     "stage-map.review: must be one pattern name or a block list"),
    ("stage-map: debate\n", "stage-map: must be a mapping of stage name to pattern"),
    ("patterns: debate\n", "patterns: must be a mapping of pattern name to pattern"),
    ("patterns:\n  mine: x\n", "patterns.mine: must be a mapping"),
    ("transport: subagent\n", "transport: must be a mapping"),
    ("headless: x\n", "headless: must be a mapping"),
    ("patterns:\n  mine:\n    description: 3\n", "patterns.mine.description: must be a string"),
    ("patterns:\n  mine:\n    schema-version: true\n",
     "patterns.mine.schema-version: must be a whole number"),
    ("patterns:\n  mine:\n    record-version: two\n",
     "patterns.mine.record-version: must be a whole number"),
    ("patterns:\n  mine:\n    edges: x\n", "patterns.mine.edges: must be a block list of mappings"),
    ("patterns:\n  mine:\n    steps:\n      - x\n",
     "patterns.mine.steps: must be a block list of mappings"),
    ("patterns:\n  mine:\n    includes: debate\n",
     "patterns.mine.includes: must be a block list of pattern names"),
    ("patterns:\n  mine:\n    includes:\n      - a: b\n",
     "patterns.mine.includes: must be a block list of pattern names"),
    ("patterns:\n  mine:\n    roles:\n      lead: x\n", "patterns.mine.roles.lead: must be a mapping"),
])
def test_a_misshapen_pattern_is_refused(tmp_path, text, problem):
    done = _validate_text(tmp_path, "schema: 1\n" + text)
    assert done.returncode == 2
    assert problem in done.stderr, done.stderr


def test_an_empty_stage_entry_is_refused():
    # The file subset cannot spell an empty list; a caller passing one is refused all the same.
    assert cfg.validate({"schema": 1, "stage-map": {"review": []}}) == [
        "stage-map.review: must be one pattern name or a block list of them"]


@pytest.mark.parametrize("text,name", [
    ("stage-map:\n  to-sdd: debate\n  to_sdd: solo\n", "AFK_CFG_STAGE_MAP_TO_SDD"),
    ("stage-map:\n  review:\n    - debate\n  review-count: solo\n",
     "AFK_CFG_STAGE_MAP_REVIEW_COUNT"),
    ("patterns:\n  mine:\n    roles:\n      a-b:\n        model: x\n      A_B:\n        model: y\n",
     "AFK_CFG_PATTERNS_MINE_ROLES_A_B_MODEL"),
    ("transport:\n  pane-switch: pane\n  pane_switch: pane\n", "AFK_CFG_TRANSPORT_PANE_SWITCH"),
    ("desktop:\n  a-b: x\n  a_b: y\n", "AFK_CFG_DESKTOP_A_B"),
])
def test_keys_that_fold_to_one_shell_name_are_refused(tmp_path, text, name):
    done = _validate_text(tmp_path, "schema: 1\n" + text)
    assert done.returncode == 2
    assert f"exports as {name}" in done.stderr, done.stderr


@pytest.mark.parametrize("topology", [True, False])
@pytest.mark.parametrize("models", [True, False])
def test_topology_and_per_role_models_read_independently(tmp_path, topology, models):
    text = "schema: 1\n"
    if topology:
        text += "stage-map:\n  fix: afk-lite\n"
    if models:
        text += "patterns:\n  mine:\n    roles:\n      lead:\n        model: frontier\n"
    done = _validate_text(tmp_path, text)
    assert done.returncode == 0, done.stderr


def test_a_local_override_of_one_role_keeps_the_others(tmp_path, monkeypatch):
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda _: home))
    monkeypatch.delenv("AFK_CONFIG", raising=False)
    root = repo(tmp_path)
    (root / ".afk" / "config.yaml").write_text(TEAM_CONFIG, encoding="utf-8")
    (root / ".afk" / "config.local.yaml").write_text(
        "patterns:\n  my-team:\n    roles:\n      checker:\n        model: other\n",
        encoding="utf-8")
    roles = cfg.load(root)["patterns"]["my-team"]["roles"]
    assert roles["checker"]["model"] == "other"
    assert roles["checker"]["charter"] == "check the slice"
    assert roles["builder"]["count"] == 2


def test_an_old_configuration_reads_as_before(tmp_path):
    root = repo(tmp_path)
    (root / ".afk" / "config.yaml").write_text(
        (SAMPLES / "monorepo-config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    assert run(["validate"], root).returncode == 0
    exported = run(["export-shell"], root).stdout
    assert not any(line.startswith(("AFK_CFG_TRANSPORT", "AFK_CFG_STAGE_MAP", "AFK_CFG_PATTERNS"))
                   for line in exported.splitlines())


def test_the_team_keys_export_like_every_other_key(tmp_path):
    root = repo(tmp_path)
    (root / ".afk" / "config.yaml").write_text(TEAM_CONFIG, encoding="utf-8")
    exported = dict(line.partition("=")[::2]
                    for line in run(["export-shell"], root).stdout.splitlines())
    assert exported["AFK_CFG_TRANSPORT_KIND"] == "multiplexer"
    assert exported["AFK_CFG_STAGE_MAP_REVIEW_COUNT"] == "2"
    assert exported["AFK_CFG_STAGE_MAP_REVIEW_1"] == "my-team"
    assert "AFK_CFG_TRANSPORT" not in exported


def _registry():
    spec = importlib.util.spec_from_file_location(
        "adapter_registry_check", SCRIPTS.parent / "hooks" / "lib" / "adapter_registry_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_registry_check_reads_the_transport_family_from_config_md():
    config_md = (SCRIPTS.parent / "CONFIG.md").read_text(encoding="utf-8")
    registry = _registry()
    assert registry.family_enum(config_md, "transport") == set(cfg.TRANSPORTS)
    assert registry.family_enum(config_md, "tracker") == set(cfg.TRACKERS)
    assert registry.family_enum(config_md, "build-gate") == set(cfg.BUILD_GATES)


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook", SCRIPTS.parent / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


@pytest.mark.parametrize("kind,shown", [("multiplexer", "multiplexer"), (None, "auto")])
def test_the_issue_collector_reports_the_transport_kind(tmp_path, kind, shown):
    bash = _bash()
    if bash is None:
        pytest.skip("no POSIX shell on this machine")
    root = repo(tmp_path)
    text = "schema: 1\n" + (f"transport:\n  kind: {kind}\n" if kind else "")
    (root / ".afk" / "config.yaml").write_text(text, encoding="utf-8")
    environ = {k: v for k, v in os.environ.items() if k not in ("AFK_CONFIG", "CLAUDE_PROJECT_DIR")}
    environ["AFK_PYTHON"] = sys.executable
    collector = SCRIPTS.parent / "skills" / "utils" / "report-issue" / "scripts" / "collect_env.sh"
    done = subprocess.run([bash, str(collector)], cwd=str(root), capture_output=True,
                          text=True, env=environ)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["transport"] == shown
