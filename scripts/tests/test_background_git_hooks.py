#!/usr/bin/env python3
"""`background_git_hooks.py` finds git hooks that detach a background process.

Every case builds its own hooks directory or git repository under tmp_path.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[2]
          / "skills" / "afk" / "setup" / "scripts" / "background_git_hooks.py")


def _module():
    spec = importlib.util.spec_from_file_location("afk_background_git_hooks", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _module()


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


def test_detaching_forms_are_flagged():
    for line in (
        "npx some-indexer analyze --force > /dev/null 2>&1 &",
        "long-task &  # keep going",
        "nohup long-task",
        "setsid long-task",
        "long-task & disown",
        'start "" /b long-task.exe',
        "start /B long-task.exe",
        "Start-Process long-task -WindowStyle Hidden",
    ):
        assert mod.detaching_lines(line), line


def test_foreground_forms_are_not_flagged():
    for line in (
        "a && b",
        "cmd > out.log 2>&1",
        "cmd &> out.log",
        "cmd |& tee out.log",
        "exec bash \"$gate\" \"$@\"",
        "# long-task &",
        "",
    ):
        assert mod.detaching_lines(line) == [], line


def test_offenders_skips_samples_and_afk_stubs(tmp_path):
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "post-commit").write_text("#!/bin/sh\nindexer analyze &\n", encoding="utf-8")
    (hooks / "post-merge").write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    (hooks / "pre-push.sample").write_text("#!/bin/sh\nx &\n", encoding="utf-8")
    (hooks / "pre-commit").write_text(
        "#!/usr/bin/env bash\n# afk-precommit-gates (installed by afk-toolkit install-git-hooks.sh).\n"
        "background-thing &\n", encoding="utf-8")
    found = mod.offenders(hooks)
    assert [h.name for h, _ in found] == ["post-commit"]
    assert found[0][1] == [(2, "indexer analyze &")]


def test_missing_directory_is_clean(tmp_path):
    assert mod.offenders(tmp_path / "absent") == []
    assert mod.offenders(None) == []


def test_cli_reads_the_repository_hooks_dir_and_exits_1(tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".git" / "hooks" / "post-commit").write_text(
        "#!/bin/sh\nindexer analyze --force > /dev/null 2>&1 &\n", encoding="utf-8")
    done = run(str(repo))
    assert done.returncode == 1
    assert "post-commit" in done.stdout
    assert "line 2" in done.stdout
    checked = run(str(repo), "--check")
    assert checked.returncode == 1
    assert checked.stdout == ""


def test_cli_follows_core_hooks_path(tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    custom = repo / ".githooks"
    custom.mkdir()
    (custom / "post-checkout").write_text("#!/bin/sh\nnohup warm-cache\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", ".githooks"], check=True)
    assert run(str(repo), "--check").returncode == 1


def test_cli_clean_repository_exits_0(tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assert run(str(repo)).returncode == 0
    assert run(str(repo), "--check").returncode == 0


def test_cli_bad_argv_exits_2(tmp_path):
    assert run(str(tmp_path), str(tmp_path)).returncode == 2
