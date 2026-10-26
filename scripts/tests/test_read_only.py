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
    ('find . -name -name -name "$x"', 'find . -name -name "$x"'),
    ('find . -perm 644 -name "$x"', 'find . -newer -name "$x"'),
    ('find . -maxdepth 1 -type "$t"', 'find . -newermt -type "$t"'),
    ('gh pr view -- "$n"', 'gh pr view "$flag" "$n"'),
    ("gh pr view -- $n", "gh pr view --comments $n"),
    ("gh pr view 12", "gh $GROUP view -- 12"),
    ('gh run view --log -- "$id"', 'gh run view --log "$id"'),
    ("gh issue view --comments -- $n", "gh -R $REPO pr view -- 12"),
    ("gh pr view 12", "gh pr $VERB -- $n"),
    ('glab mr view -- "$id"', 'glab mr view "$id" "$x"'),
    ("glab issue view -- $n", "glab $GROUP view -- 1"),
    ("glab mr view 1", 'glab mr view 1 "$x"'),
    ("glab mr view 1", 'glab mr view $DASHES $N'),
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


@pytest.mark.parametrize("command,powershell,expected", [
    ("echo hi > /dev/null", False, True),
    ("echo hi > nul", False, True),
    ('echo hi > "$null"', False, False),
    ("echo hi > $null", False, False),
    ("echo hi > '$null'", False, False),
    ("Get-Content a.txt > $null", True, True),
    ("Get-Content a.txt > $NULL", True, True),
    ('Get-Content a.txt > "$null"', True, False),
    ("Get-Content a.txt > '$null'", True, False),
])
def test_null_redirect_is_shell_and_quote_aware(command, powershell, expected):
    segments = [s for s in sm.segments(command, powershell) if not s.mark]
    assert all(read_only.proven_segment(s) for s in segments) is expected


@pytest.mark.parametrize("command,powershell,expected", [
    (r'Test-Path "docs\"; Remove-Item a.txt', True, False),
    (r'Test-Path "docs\"; Remove-Item a.txt', False, True),
    (r'Test-Path "docs\"', True, True),
    (r'Write-Output "\$(Remove-Item a.txt)"', True, False),
    (r'Write-Output "`$(x)"', True, False),
    ("Get-Content a.txt \\\nRemove-Item a.txt", True, False),
    ("Get-Content a.txt `\n-Raw", True, True),
    ("cat a.txt `\nrm a.txt `", False, False),
    ("cat a.txt \\\n-n", False, True),
    ("Write-Output a`;Remove-Item", True, True),
    ("echo a`;rm", False, False),
    (r"echo \`x\`", False, True),
    (r"cat a\\;rm b", False, False),
    (r"""cat $'a\'b' "$(rm b)" 'c'""", False, False),
    (r"""cat $'a\\' 'b'""", False, True),
    ("echo $(pwd)", False, True),
    ('echo "$(pwd)"', False, False),
    ("Write-Output “a\"; Remove-Item a.txt; \"b”", True, False),
    ("Write-Output ‘a'; Remove-Item a.txt; 'b’", True, False),
    ("Write-Output “a b”", True, True),
])
def test_word_reading_follows_each_shell(command, powershell, expected):
    segments = [s for s in sm.segments(command, powershell) if not s.mark]
    assert all(read_only.proven_segment(s) for s in segments) is expected


@pytest.mark.parametrize("command,twin", [
    ('git log --end-of-options "$sha"', 'git log "$sha"'),
    ('git show --end-of-options "$sha"', 'git show --end-of-options "$sha" --output=x'),
    ('git diff --end-of-options "$base"...HEAD', 'git blame --end-of-options "$f"'),
    ('git rev-parse --end-of-options "$ref"', 'git shortlog --end-of-options "$x"'),
    ('git log --oneline --end-of-options "$sha"', 'git log -n --end-of-options "$sha"'),
    ("git log -5 --end-of-options $sha", 'git log --grep --end-of-options "$x"'),
    ("git log '--format=%H' --end-of-options \"$sha\"", 'git branch --end-of-options "$x"'),
    ('git -C ../other log --end-of-options "$sha"', 'git range-diff --end-of-options "$a" "$b"'),
])
def test_an_opaque_git_revision_after_a_literal_end_of_options_is_proven(command, twin):
    """Probed on git 2.53: blame, shortlog and range-diff still read `--output` after `--end-of-options`."""
    assert proven(command), command
    assert not proven(twin), twin


@pytest.mark.parametrize("command,twin", [
    ('cd "$(git rev-parse --show-toplevel)"', 'cd "$(git rev-parse --show-toplevel; touch x)"'),
    ('ls "$(git rev-parse --show-toplevel)"', 'ls "$(touch x)"'),
    ('cat "$(git rev-parse --git-path HEAD)"', 'grep x "$(git rev-parse --show-toplevel)"'),
    ('cd "$(pwd)"', 'cd "$(git -c core.pager=less log)"'),
    ('cd "$(git rev-parse --show-toplevel)"', r'cd "$(echo \"; touch x; \")"'),
    ('cd "$(git rev-parse --show-toplevel)"', 'cd x"$(git rev-parse --show-toplevel)"'),
])
def test_a_quoted_substitution_of_a_proven_command_is_a_reader_operand(command, twin):
    assert proven(command), command
    assert not proven(twin), twin


@pytest.mark.parametrize("command,twin", [
    ('gh pr view "$n"', 'gh pr view "$n" "$m"'),
    ('gh run view "$id" --log', "gh run view --log $id"),
    ("glab mr view $n --comments", "glab mr $VERB $n"),
    ('rg -e "$pat"', "rg -e $pat"),
    ('rg --regexp "$pat" src', 'rg -g -e "$pat"'),
    ('rg -n -e "$pat"', 'rg -e -e "$pat"'),
    ('rg -g "*.py" -e "$pat"', 'rg -A -e "$pat"'),
    ('rg --type=py -e "$pat"', 'rg "$pat"'),
])
def test_an_opaque_word_in_a_value_only_position_is_proven(command, twin):
    assert proven(command), command
    assert not proven(twin), twin


@pytest.mark.parametrize("command,twin", [
    ("du -sh src", "du -sh src > sizes.txt"),
    ("df -h", "df -h >> disk.txt"),
    ("ps -ef", "ps -ef | tee procs.txt"),
    ("printenv PATH", "printenv PATH > path.txt"),
    ("id -u", "id -u > me.txt"),
    ("nl a.txt", "nl a.txt > b.txt"),
    ("od -c a.bin", "od -c a.bin > a.txt"),
    ("sha256sum a.txt", "sha256sum a.txt > sums"),
    ("md5sum -c sums", "md5sum a.txt > sums"),
    ("cmp a b", "cmp a b > diff.txt"),
    ("comm -12 a b", "comm -12 a b > c"),
    ("paste a b", "paste a b > c"),
    ("seq 3", "seq 3 > n.txt"),
    ("strings a.bin", "strings a.bin > s.txt"),
    ("nproc", "nproc > n.txt"),
    ("tasklist /FI x", "taskkill /IM x"),
    ("where git", "where {Remove-Item a.txt}"),
    ("tree -L 2", "tree -o out.txt"),
    ("tree -a src", "tree -R -H . -L 1"),
    ("file a.txt", "file -C -m magic"),
    ("file -b a.txt", "file -p a.txt"),
    ("xxd a.bin", "xxd a.bin out.hex"),
    ("xxd -l 64 a.bin", "xxd -r a.hex a.bin"),
    ("xxd -s 16 -c 8 a.bin", "xxd -s 16 a.bin out.hex"),
])
def test_an_added_plain_reader_is_proven_and_its_writing_form_is_not(command, twin):
    assert proven(command), command
    assert not proven(twin), twin


@pytest.mark.parametrize("command,twin", [
    ("node --version", 'node -e "x"'),
    ("python -V", "python -v"),
    ("python3 --version", "python3 -m pip install x"),
    ("afk-python --version", "afk-python -c x"),
    ("mvn -v", "mvn -V"),
    ("java -version", "java -jar x.jar"),
    ("uv --version", "uv sync"),
    ("gh --version", "gh --version x"),
    ("npm -v", "npm -v install"),
    ("npm ls", "npm install"),
    ("npm ls --depth 0 --json", "npm ls --cache ./c"),
    ("npm list --all", "npm ls --logs-dir=."),
    ("npm view react versions", "npm view react --registry=$R"),
    ("npm outdated --json", "npm update"),
    ("pip list --outdated", "pip list --log pip.log"),
    ("pip show requests", "pip --python /x show requests"),
    ("pip3 list --format=json", "pip install x"),
])
def test_a_version_probe_or_package_listing_is_proven_and_its_twin_is_not(command, twin):
    """npm runs lifecycle scripts only for the commands its scripts page lists; `ls`, `view` and `outdated`
    are not among them."""
    assert proven(command), command
    assert not proven(twin), twin


@pytest.mark.parametrize("command,twin", [
    ("git ls-files | xargs grep -l foo", "git ls-files | xargs rm"),
    ("git ls-files | xargs -0 wc -l", "git ls-files | xargs git log"),
    ("xargs -I{} grep x {}", "xargs -I{} {} x"),
    ("xargs -n 1 cat", "xargs sh -c 'rm $0'"),
    ("xargs git log --", "xargs -I{} git log {}"),
    ("xargs", "xargs -Q x"),
    ("xargs -r --max-args=2 head -1", "xargs -n 1 sed -i s/a/b/"),
])
def test_xargs_into_a_proven_reader_is_proven(command, twin):
    assert proven(command), command
    assert not proven(twin), twin


@pytest.mark.parametrize("command,twin", [
    ("awk '{print $1}' a.txt", """awk '{print $1 > "out"}' a.txt"""),
    ("awk -F: '{print $2}' a", """awk '{system("rm x")}' a"""),
    ("awk -v n=1 'NR==n' a", "awk -f prog.awk a"),
    ("gawk 'END{print NR}' a", "gawk -i inplace '{print}' a"),
    ("awk 'BEGIN{print 1}'", """awk '{print | "sh"}'"""),
    ("awk -- '{print}' a", """awk 'BEGIN{while ((getline l < "x") > 0) print l}'"""),
    ("gawk -e '{print}' a", "awk -o out.awk '{print}'"),
    ("awk '{print}' a", "awk --profile '{print}' a"),
    ("awk '{print}' a", "awk -W exec x"),
    ("awk '{print}' a", "awk --prof '{print}' a"),
    ("awk '{print}' a", """gawk '@load "x"; {print}' a"""),
])
def test_awk_without_a_command_write_or_program_file_is_proven(command, twin):
    assert proven(command), command
    assert not proven(twin), twin


@pytest.mark.parametrize("command,twin", [
    ("gh api graphql -f query='query { viewer { login } }'", "gh api graphql -f query='mutation { x }'"),
    ("gh api graphql -F n=1 -f query='{ viewer { login } }'", "gh api graphql -F query=@q.graphql"),
    ("gh api graphql --raw-field=query='{ viewer { login } }'", "gh api graphql --input q.json"),
    ("gh api graphql -f query='{ viewer { login } }'", "gh api graphql -X POST -f query='{ viewer { login } }'"),
    ("gh search prs x --state open", "gh api -f title=x repos/o/r/issues"),
    ("gh search code foo", "gh $GROUP prs x"),
])
def test_a_graphql_query_and_a_search_are_forge_reads(command, twin):
    assert proven(command), command
    assert not proven(twin), twin


@pytest.mark.parametrize("command,twin", [
    ("git -c core.quotepath=off status", "git -c core.pager=less log"),
    ("git -c color.ui=always log", "git -c core.hooksPath=x status"),
    ("git -c core.pager=cat log", "git -c log.showSignature=true log"),
    ("git -c log.date=iso log -1", "git -c core.fsmonitor=x status"),
    ("git ls-remote origin", "git ls-remote --upload-pack=x ."),
    ("git fetch origin", "git fetch --upl=x ."),
    ("git fetch origin", "git fetch --exec=x ."),
])
def test_a_git_display_setting_is_proven_and_a_program_setting_is_not(command, twin):
    """Probed on git 2.53: `fetch` and `ls-remote` run an `--upload-pack` program, also when abbreviated."""
    assert proven(command), command
    assert not proven(twin), twin


@pytest.mark.parametrize("command,twin", [
    ("Get-Content a.json | ConvertFrom-Json", "Get-Content a.json | ConvertFrom-Json | Set-Content b.txt"),
    ("Get-Process | ConvertTo-Json", "Get-Process | ConvertTo-Json | Out-File p.json"),
    ("Compare-Object $a $b", "Compare-Object $a $b -Property {Remove-Item a.txt}"),
    ("Get-ChildItem | Group-Object Extension", "Get-ChildItem | Group-Object {Remove-Item a.txt}"),
    ("Get-CimInstance Win32_Process", "Invoke-CimMethod Win32_Process"),
    ("Get-ChildItem", "Get-Command git -CommandType Application"),
])
def test_a_pure_pipeline_cmdlet_is_proven(command, twin):
    """`Get-Command` stays out: probed on PowerShell 7.6 and 5.1, `-CommandType Application` still imports a
    module that exports the name, running its code."""
    assert proven(command), command
    assert not proven(twin), twin
