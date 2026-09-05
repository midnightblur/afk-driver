"""`afk-config.py init` on three fixture repositories, plus the resolution order.

The scaffold's job is to be a correct starting point, so every test here checks
two things about it: that it says what the repository actually is, and that
`validate` accepts it. A scaffold that needs hand-repair before it validates is
worse than no scaffold.
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "afk_config", Path(__file__).resolve().parents[1] / "afk-config.py"
)
ac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ac)


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def make_repo(tmp_path, name, remote=None, files=()):
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "T")
    for relative, body in files:
        p = repo / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    if remote:
        git(repo, "remote", "add", "origin", remote)
    return repo


def scaffold_of(repo):
    """The scaffold text, asserted to validate, as `(text, config)`."""
    text = ac.scaffold(repo)
    config = ac.deep_merge(dict(ac.DEFAULTS), ac.parse(text, "<scaffold>"))
    assert ac.validate(config, repo) == []
    return text, config


# ---------------------------------------------------------------- fixtures

def test_github_repo_with_package_json(tmp_path):
    repo = make_repo(tmp_path, "gh", "https://github.com/acme/widget.git",
                     [("package.json", '{"name":"widget"}\n')])
    text, config = scaffold_of(repo)
    assert config["forge"] == "github"
    assert config["tracker"] == "github-issues"
    assert config["build-gates"] == ["npm"]
    assert config["npm"]["workspace-root"] == "."
    assert config["github"]["remote"] == "origin"


def test_gitlab_repo_with_pom(tmp_path):
    repo = make_repo(tmp_path, "gl", "git@gitlab.com:acme/widget.git",
                     [("pom.xml", "<project/>\n")])
    text, config = scaffold_of(repo)
    assert config["forge"] == "gitlab"
    # No tracker can be inferred from a GitLab remote, so it stays `none` and
    # the Jira block is offered as comments.
    assert config["tracker"] == "none"
    assert config["build-gates"] == ["maven"]
    assert config["maven"]["reactor-pom"] == "pom.xml"
    assert "# jira:" in text
    assert "default-module: TODO" in text


def test_repo_with_no_remote(tmp_path):
    repo = make_repo(tmp_path, "bare")
    text, config = scaffold_of(repo)
    assert config["forge"] == "none"
    assert config["tracker"] == "none"
    assert "build-gates" not in config or config.get("build-gates") == []
    assert "# build-gates:" in text


def test_self_hosted_gitlab_is_still_gitlab(tmp_path):
    repo = make_repo(tmp_path, "self", "https://gitlab.example.internal/acme/w.git")
    _, config = scaffold_of(repo)
    assert config["forge"] == "gitlab"


def test_a_forge_we_do_not_know_is_none_not_a_guess(tmp_path):
    repo = make_repo(tmp_path, "other", "https://git.example.com/acme/w.git")
    _, config = scaffold_of(repo)
    assert config["forge"] == "none"


def test_the_scaffold_writes_an_empty_string_not_an_empty_scalar(tmp_path):
    """`branch-pattern:` with nothing after it parses as None, not "".

    Both read as "gate off" today, so this is about the file saying what the
    schema documents rather than about behaviour.
    """
    repo = make_repo(tmp_path, "q")
    text, config = scaffold_of(repo)
    assert '  branch-pattern: ""' in text
    assert config["git"]["branch-pattern"] == ""


# ---------------------------------------------------------------- writing

def test_init_writes_the_file_and_refuses_to_overwrite(tmp_path):
    repo = make_repo(tmp_path, "w", "https://github.com/acme/w.git")
    target, problems = ac.init(repo)
    assert problems == []
    assert target == repo / ".afk" / "config.yaml"
    assert target.read_text(encoding="utf-8").startswith("# AFK configuration")

    with pytest.raises(ac.ConfigError):
        ac.init(repo)

    target.write_text("schema: 1\n", encoding="utf-8")
    ac.init(repo, force=True)
    assert "forge:" in target.read_text(encoding="utf-8")


# ------------------------------------------------------- resolution order

def test_developer_value_wins_over_the_team_default():
    config = {"developer": {"trackerAssignee": "mine"},
              "tracker-defaults": {"assignee": "team"}}
    assert ac.developer_value(config, "trackerAssignee") == "mine"


def test_the_team_default_stands_in_when_the_developer_set_nothing():
    config = {"tracker-defaults": {"assignee": "team"},
              "forge-defaults": {"reviewer": "lead"}}
    assert ac.developer_value(config, "trackerAssignee") == "team"
    assert ac.developer_value(config, "mrReviewer") == "lead"


def test_an_empty_developer_value_does_not_shadow_the_default():
    config = {"developer": {"mrReviewer": "  "}, "forge-defaults": {"reviewer": "lead"}}
    assert ac.developer_value(config, "mrReviewer") == "lead"


def test_neither_layer_set_means_fail_closed():
    assert ac.developer_value({}, "trackerAssignee") is None
    assert ac.developer_value({}, "ideBinary") is None


def test_ide_binary_has_no_team_default():
    config = {"tracker-defaults": {"assignee": "team"}}
    assert ac.developer_value(config, "ideBinary") is None


# ------------------------------------------------------- derived worktrees

def test_worktree_base_is_derived_beside_the_main_checkout(tmp_path):
    repo = make_repo(tmp_path, "widget")
    assert ac.worktree_base(repo) == tmp_path / "widget-worktrees"


def test_a_worktree_derives_the_same_base_as_its_main_checkout(tmp_path):
    repo = make_repo(tmp_path, "widget")
    linked = tmp_path / "elsewhere" / "wt"
    git(repo, "worktree", "add", "-q", "-b", "side", str(linked))
    assert ac.worktree_base(linked) == ac.worktree_base(repo)


def test_the_derived_base_is_used_when_the_key_is_absent(tmp_path):
    repo = make_repo(tmp_path, "widget")
    resolved = ac.developer_value({}, "worktreeBasePath", repo)
    assert resolved == str(tmp_path / "widget-worktrees").replace("\\", "/")


def test_an_explicit_worktree_base_still_wins(tmp_path):
    repo = make_repo(tmp_path, "widget")
    config = {"developer": {"worktreeBasePath": "D:/elsewhere"}}
    assert ac.developer_value(config, "worktreeBasePath", repo) == "D:/elsewhere"


# ------------------------------------------------------------- validation

def test_team_default_blocks_are_validated():
    base = {"schema": ac.SCHEMA}
    assert ac.validate({**base, "tracker-defaults": {"assignee": "x"}}) == []
    assert any("must be a mapping" in p
               for p in ac.validate({**base, "tracker-defaults": "x"}))
    assert any("unknown key" in p
               for p in ac.validate({**base, "forge-defaults": {"reviewr": "x"}}))
    assert any("must be a string" in p
               for p in ac.validate({**base, "forge-defaults": {"reviewer": 7}}))
