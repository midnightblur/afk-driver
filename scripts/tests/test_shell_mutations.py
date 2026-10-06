"""The shell mutation recognizer: which literal paths a command line changes.

`resources(command, cwd)` returns the absolute paths an identified mutation changes
(a repository folder for a git verb, the target for a file writer). A command it cannot
resolve literally, or cannot call a mutation, returns [] (PRD D1/D3: opaque text passes).
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[2] / "hooks" / "lib"
spec = importlib.util.spec_from_file_location("shell_mutations_under_test", LIB / "shell_mutations.py")
sm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sm)

CWD = Path(os.path.abspath("proj"))


def res(command: str) -> list[Path]:
    return sm.resources(command, CWD)


def at(*names: str) -> list[Path]:
    return [Path(os.path.normpath(CWD / name)) for name in names]


@pytest.mark.parametrize("command", [
    "git status", "git status && git log -1", "git log -1 2>&1", "cat a.md b.md", "cd docs",
    "herdr agent list", "git fetch origin", "git worktree list", "C:/x/scripts/create-worktree --name foo",
    'python -c "print(1)"', "jq . x.json", "sed -n 1,5p x", "echo hi", "gh api repos/x/y", "ls | head",
    "git branch", "git remote -v", "find . -name x", "git -C C:/elsewhere status",
    "echo hi > /dev/null", "ls 2>&1", "echo hi >&2", "echo hi 2> /dev/null", "echo hi > $null", "echo hi > nul",
    "echo $(date)", "touch $HOME/x", "rm *.o", "rm -rf $TMP/x", "touch %TEMP%\\x",
    "git stash list", "git stash show -p", "git tag", "git tag -l", "git tag -l 'v*'", "git branch -a",
    "git clean -n", "git clean --dry-run", "git apply --check p.diff", "git apply --stat p.diff",
    "gh issue create --title x --body y", "gh pr view 3", "unknown-reader README.md", "rg --pre mutate pat",
    'echo "rm -rf x"', 'echo "a; touch b"', "echo 'git commit -m x'", 'grep -r "git commit" .',
    "cat <<EOF\nrm -rf x\ntouch y\nEOF", "git log --oneline | head -5", "diff a b", "tee",
    "npm install", "python build.py", "git push origin topic", "git pull-request-thing", "git config user.name",
    "git branch --list", "git worktree add ../w", "git worktree prune",
    "Get-Content README.md", "Get-ChildItem -Recurse | Select-String x", "Write-Output hi",
    "touch $x; echo hi", "cd $x && touch f", "echo > $(pwd)/f",
])
def test_reads_composition_and_opaque_text_pass(command):
    assert res(command) == []


@pytest.mark.parametrize("verb", [
    "add .", "am p.mbox", "apply p.diff", "checkout topic", "cherry-pick abc", "clean -fd", "commit -m x",
    "merge topic", "mv a b", "pull", "pull origin main", "rebase main", "reset --hard", "restore f",
    "revert abc", "rm f", "stash", "stash push -m x", "stash pop", "stash drop", "stash apply", "switch topic",
    "tag v1", "tag -d v1", "tag -a v1 -m x", "update-ref refs/heads/x abc", "update-index --add f",
    "branch -d x", "branch -D x", "branch -m x", "branch -M a b", "branch -f x abc", "branch -c a b",
    "branch --delete x", "branch --move a b", "worktree move a b", "worktree remove w",
    "worktree remove --force w",
])
def test_git_mutating_verbs_name_the_session_folder(verb):
    assert res(f"git {verb}") == at(".")


def test_git_options_before_the_verb_are_skipped():
    assert res("git --no-pager -c core.x=1 commit -m x") == at(".")
    assert res("git -C sub commit -m x") == at("sub")
    assert res("git -C sub -C deeper add .") == at("sub/deeper")
    assert res("git -C C:/elsewhere add .") == [Path("C:/elsewhere")] if os.name == "nt" else True
    assert res("git --git-dir=g --work-tree=w add .") == at("w")
    assert res("git --work-tree w add .") == at("w")


def test_cd_before_a_verb_moves_the_resource():
    assert res("cd docs && git add .") == at("docs")
    assert res("cd docs; touch f") == at("docs/f")
    assert res("(cd sub && touch f)") == at("sub/f")
    assert res("Set-Location docs; git add .") == at("docs")


def test_an_opaque_cd_makes_later_relative_targets_opaque():
    assert res("cd $x && touch f") == []
    assert res("cd $x && touch /abs/f") == [Path("/abs/f")] if os.name != "nt" else True


def test_composition_keeps_every_mutation_segment():
    assert res("git status && git commit -m x") == at(".")
    assert res("ls | tee out.txt") == at("out.txt")
    assert res("touch a; touch b") == at("a", "b")
    assert res("true || touch a") == at("a")
    assert res("touch a & touch b") == at("a", "b")
    assert res("echo x\ntouch a") == at("a")


@pytest.mark.parametrize("command,expected", [
    ("echo hi > out.txt", ["out.txt"]), ("echo hi >> out.txt", ["out.txt"]), ("echo hi >out.txt", ["out.txt"]),
    ("echo hi 2> err.txt", ["err.txt"]), ("echo hi &> all.txt", ["all.txt"]), ("echo hi 1>o", ["o"]),
    ("echo hi >| out.txt", ["out.txt"]), ("echo hi > 'a b.txt'", ["a b.txt"]), ('echo hi > "a b.txt"', ["a b.txt"]),
    ("ls | tee out.txt", ["out.txt"]), ("tee -a one two", ["one", "two"]),
    ("cp a b", ["b"]), ("cp -r a b", ["b"]), ("cp -t dir a b", ["dir"]),
    ("mv a b", ["a", "b"]), ("rm -rf d", ["d"]), ("rm a b", ["a", "b"]), ("rmdir d", ["d"]),
    ("mkdir -p d/e", ["d/e"]), ("touch f", ["f"]), ("touch -t 2001010101 f", ["f"]), ("ln -s a b", ["b"]),
    ("sed -i s/a/b/ f.txt", ["f.txt"]), ("sed -i.bak -e s/a/b/ f", ["f"]), ("sed -ni 1p f", ["f"]),
    ("sed --in-place s/a/b/ f", ["f"]), ("sed -i -e s/a/b/ -e s/c/d/ f g", ["f", "g"]),
    ("perl -pi -e s/a/b/ f", ["f"]), ("perl -i.bak -pe s/a/b/ f", ["f"]),
    ("Set-Content README.md changed", ["README.md"]), ("Set-Content -Path b -Value x", ["b"]),
    ("Get-Content a | Set-Content -Path b", ["b"]), ("Add-Content f x", ["f"]),
    ("Out-File -FilePath f", ["f"]), ("Get-Date | Out-File f -Append", ["f"]),
    ("New-Item -ItemType File -Path f", ["f"]), ("New-Item f -ItemType Directory", ["f"]),
    ("Remove-Item README.md", ["README.md"]), ("Remove-Item -Recurse -Force d", ["d"]),
    ("Move-Item a b", ["a", "b"]), ("Copy-Item a -Destination b", ["b"]), ("Copy-Item a b", ["b"]),
    ("Rename-Item a b", ["a"]), ("Clear-Content f", ["f"]), ("Set-Content -LiteralPath 'a b' x", ["a b"]),
    ("sc f x", ["f"]), ("ri f", ["f"]), ("del f", ["f"]), ("md d", ["d"]), ("mi a b", ["a", "b"]),
    ("Get-Content README.md; Remove-Item README.md", ["README.md"]),
    ("Get-Content (Set-Content copy.txt changed)", ["copy.txt"]),
    ("Get-Content @(Set-Content copy.txt changed)", ["copy.txt"]),
    ("Get-ChildItem -Filter { Set-Content copy.txt changed }", ["copy.txt"]),
    ("Get-Content README.md > copy.txt", ["copy.txt"]), ("git diff --output=copy.diff", ["copy.diff"]),
    ("git log --output copy.log", ["copy.log"]),
])
def test_file_writers_name_their_literal_targets(command, expected):
    assert res(command) == at(*expected)


def test_a_target_is_absolute_or_relative_to_the_running_folder():
    absolute = os.path.abspath(os.path.join(os.sep, "elsewhere", "f"))
    assert res(f"touch {absolute}") == [Path(absolute)]
    assert res("touch ../up") == at("../up")


@pytest.mark.parametrize("command", [
    "FOO=1 git commit -m x", "env FOO=1 git commit -m x", "command git commit -m x", "sudo git commit -m x",
    "nohup git commit -m x", "time git commit -m x", "GIT.EXE commit -m x", "/usr/bin/git commit -m x",
    "C:/Program Files/Git/cmd/git.exe commit -m x".replace("Program Files", "Progra~1"),
    "Git Commit -m x",
])
def test_wrappers_case_and_executable_paths_do_not_hide_a_verb(command):
    assert res(command) == at(".")


def test_heredoc_body_is_not_commands_but_text_after_it_is():
    assert res("cat <<EOF > f\nrm -rf x\nEOF\n") == at("f")
    assert res("cat <<'EOF'\ntouch y\nEOF\ntouch z") == at("z")


def test_unbalanced_quotes_and_garbage_never_raise():
    for command in ["echo 'unterminated", 'echo "x', "git", "git -C", ">", ">>", "tee >", "| | ;;", "", "   ",
                    "touch", "cp a", "sed -i", "(((", "{{{", "\\"]:
        assert isinstance(res(command), list)


def test_the_same_verb_inside_quotes_is_text():
    assert res('git commit -m "a; touch b"') == at(".")
    assert res('echo "git commit"') == []
