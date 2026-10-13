"""The guard's allow-list: a shell segment it proves read-only, and the mutating twin it does not.

A command is proven when every segment is. One case per listed form, each beside the flag or
shape that makes it unproven.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[2] / "hooks" / "lib"
sys.path.insert(0, str(LIB))
import read_only  # noqa: E402
import shell_mutations as sm  # noqa: E402


def proven(command: str) -> bool:
    return all(read_only.proven_segment(s) for s in sm.segments(command) if not s.mark)


@pytest.mark.parametrize("command,twin", [
    ("ls -la src", "ls > listing.txt"),
    ("find . -name '*.py' -type f", "find . -name '*.pyc' -delete"),
    ("find . -type f -print", "find . -type f -exec rm {} +"),
    ("grep -rn pattern src", "grep -rn pattern src > hits.txt"),
    ("rg -n pattern", "rg --pre ./run.sh pattern"),
    ("cat a.txt", "cat a.txt >> b.txt"),
    ("head -5 a.txt | tail -2", "head -5 a.txt | tee b.txt"),
    ("wc -l a.txt", "wc -l a.txt &> counts.txt"),
    ("stat a.txt", "touch a.txt"),
    ("sed -n 1,5p a.txt", "sed -i s/a/b/ a.txt"),
    ("sed -n 1,5p a.txt", "sed --in-place=.bak s/a/b/ a.txt"),
    ("sed s/a/b/ a.txt", "sed s/a/b/w out.txt a.txt"),
    ("sort a.txt", "sort -o out.txt a.txt"),
    ("sort -r a.txt", "sort -ro out.txt a.txt"),
    ("uniq a.txt", "uniq a.txt out.txt"),
    ("curl -sSL https://example.test/x", "curl -o x https://example.test/x"),
    ("curl -I https://example.test/x", "curl -O https://example.test/x"),
    ("curl -s https://example.test/x", "curl --output=x https://example.test/x"),
    ("curl -s https://example.test/x", "curl -T file https://example.test/x"),
    ("curl -s https://example.test/x", "curl -d a=b https://example.test/x"),
    ("curl -s https://example.test/x", "curl -X DELETE https://example.test/x"),
    ("docker ps -a", "docker run alpine"),
    ("docker logs -f web", "docker rm web"),
    ("docker inspect web", "docker exec web sh"),
    ("docker images", "docker image prune -f"),
    ("docker container ls", "docker container rm web"),
    ("git log --oneline -5", "git commit -m x"),
    ("git diff HEAD~1", "git diff --output=out.diff"),
    ("git show HEAD:a.txt", "git checkout a.txt"),
    ("git branch -a", "git branch -D topic"),
    ("git remote -v", "git remote add other url"),
    ("git stash list", "git stash"),
    ("git tag -l", "git tag v1"),
    ("git worktree list", "git worktree add ../x"),
    ("git config --get user.name", "git config user.name x"),
    ("git grep -n pattern", "git grep -Ovim pattern"),
    ("git -C ../other status", "git -c core.pager=less log"),
    ("git --version", "git gc"),
    ("gh pr view 12 --comments", "gh pr merge 12"),
    ("gh issue list --state open", "gh issue create --title x --body y"),
    ("gh api repos/o/r/pulls", "gh api -X POST repos/o/r/issues"),
    ("gh api repos/o/r/pulls", "gh api repos/o/r/issues -f title=x"),
    ("glab mr view 3", "glab mr merge 3"),
    ("Get-ChildItem C:/elsewhere", "Get-ChildItem C:/elsewhere | Out-File list.txt"),
    ("Get-Content a.txt | Select-String x", "Get-Content a.txt | Set-Content b.txt"),
    ("Test-Path a.txt", "Remove-Item a.txt"),
    ("Get-ChildItem -Filter *.md", "Get-ChildItem -Filter {Remove-Item a.txt}"),
    ("echo hi > /dev/null", "echo hi > out.txt"),
    ("for f in a b; do wc -l $f; done", 'for f in a b; do mv "$f" moved/; done'),
    ("if test -f a.txt; then cat a.txt; fi", "if test -f a.txt; then rm a.txt; fi"),
    ("cd src && ls", "cd src && make"),
    ("herdr pane list", "herdr worktree create topic"),
    ("herdr pane read p1 --lines 20", "herdr pane run p1 make"),
    ("herdr agent list", "herdr worktree remove topic"),
    ("herdr worktree list", "herdr worktree list --trust-repository"),
    ("herdr api snapshot", "herdr api schema --output schema.json"),
    ("herdr --version", "herdr update"),
    ("find . -name x", "find . $ACTION"),
    ("find . -name '*.py'", "find . -name x *"),
    ("sort a.txt", "sort $OPTS a.txt"),
    ("uniq a.txt", "uniq $FILES"),
    ("rg pattern -- $DIR", "rg $FLAGS pattern"),
    ("sed -n 1p a.txt", "sed $SCRIPT a.txt"),
    ('git log -1 -- "$f"', "git log $OPTS"),
    ("curl -s https://example.test/x", "curl $FLAGS https://example.test/x"),
    ("gh pr view 12", "gh pr $VERB 12"),
    ("ls $DIR", "date $WHEN"),
    ("grep -n x $FILES", "docker $VERB"),
    ("cat <<EOF\nhello $USER\nEOF", "cat <<EOF\n$(touch changed)\nEOF"),
    ("cat <<'EOF'\n$(touch changed)\nEOF", "cat <<EOF | grep x\n`touch changed`\nEOF"),
    ("env FOO=1 ls", "env -S 'touch changed'"),
    ("env ls", "env --split-string='touch changed'"),
    ("Get-ChildItem -Force", "Get-Report"),
    ("Get-Content a.txt", "Get-Command make"),
    ('find . -name "$x"', "find . -name $x"),
    ('find . -iname "$x" -type f', 'find "$dir" -name x'),
    ('find . -path "$p" -type "$t"', 'find . -newer "$x"'),
    ('gh pr view -- "$n"', 'gh pr view "$flag"'),
    ("gh pr view -- $n", "gh pr view $n"),
    ("gh pr view 12", "gh $GROUP view -- 12"),
    ('gh run view --log -- "$id"', 'gh run view "$id" --log'),
    ("gh issue view --comments -- $n", "gh -R $REPO pr view -- 12"),
    ("gh pr view 12", "gh pr $VERB -- $n"),
    ('glab mr view -- "$id"', 'glab mr view "$id"'),
    ("glab issue view -- $n", "glab $GROUP view -- 1"),
    ("glab mr view 1", 'glab mr view "$x" -- 1'),
    ("glab mr view 1", 'glab mr view $DASHES 1'),
])
def test_a_listed_form_is_proven_and_its_mutating_twin_is_not(command, twin):
    assert proven(command), command
    assert not proven(twin), twin


@pytest.mark.parametrize("command,twin", [
    ("git status --short", "git add ."),
    ("git fetch origin", "git fetch origin main:main"),
])
def test_an_index_refresh_or_a_fetch_without_a_local_destination_is_an_accepted_gap(command, twin):
    """ADR-0014 accepted gaps: `git status` may refresh the index stat cache, and a fetch writes FETCH_HEAD,
    objects and remote-tracking refs; neither changes a local branch, the index content or the work tree."""
    assert proven(command), command
    assert not proven(twin), twin


@pytest.mark.parametrize("command", [
    "unknown-reader README.md",
    'python -c "print(1)"',
    "./ls",
    "C:/tmp/git.exe status",
    "echo $(rm -rf x)",
    "echo `rm -rf x`",
    "env $CMD",
    "$TOOL a.txt",
    "ls > $OUT",
    "npm test",
    "X=$Y touch changed",
    "X=$(rm -rf x)",
    "herdr",
    "herdr pane close p1",
])
def test_an_unlisted_or_unreadable_command_is_unproven(command):
    assert not proven(command), command
