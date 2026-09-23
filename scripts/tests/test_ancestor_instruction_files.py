#!/usr/bin/env python3
"""`ancestor_instruction_files.py` finds instruction files above a repository.

Every case builds an isolated ancestor tree under tmp_path and passes it in, so
the probe never walks real directories above the temp dir. The user-global homes
are monkeypatched into the same tree, so the exclusion is exercised without
touching ~/.claude or ~/.codex.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[2]
          / "skills" / "afk" / "setup" / "scripts" / "ancestor_instruction_files.py")


def _module():
    spec = importlib.util.spec_from_file_location("afk_ancestor_files", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _module()


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


def test_finds_planted_strays(tmp_path):
    a = tmp_path / "a"
    b = a / "b"
    b.mkdir(parents=True)
    (a / "CLAUDE.md").write_text("root steering\n", encoding="utf-8")
    (b / "AGENTS.md").write_text("deeper steering\n", encoding="utf-8")
    repo = b / "repo"
    repo.mkdir()
    found = {p: n for p, n in mod.strays(repo, ancestors=[a, b])}
    assert a / "CLAUDE.md" in found
    assert b / "AGENTS.md" in found
    assert found[a / "CLAUDE.md"] == (a / "CLAUDE.md").stat().st_size


def test_all_six_fixed_names(tmp_path):
    anc = tmp_path / "anc"
    (anc / ".claude").mkdir(parents=True)
    for name in ("AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "CLAUDE.local.md"):
        (anc / name).write_text("x\n", encoding="utf-8")
    (anc / ".claude" / "CLAUDE.md").write_text("x\n", encoding="utf-8")
    (anc / ".claude" / "AGENTS.md").write_text("x\n", encoding="utf-8")
    repo = anc / "repo"
    repo.mkdir()
    # This ancestor is not a global home, so its .claude/* files are strays too.
    names = {p.relative_to(anc).as_posix() for p, _ in mod.strays(repo, ancestors=[anc])}
    assert names == {
        "AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "CLAUDE.local.md",
        ".claude/CLAUDE.md", ".claude/AGENTS.md",
    }


def test_excludes_global_homes_but_flags_home_root(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".codex").mkdir(parents=True)
    monkeypatch.setattr(mod, "global_homes",
                        lambda: (home / ".claude", home / ".codex"))
    # The global steering files, which must NOT be reported.
    (home / ".claude" / "CLAUDE.md").write_text("global\n", encoding="utf-8")
    (home / ".claude" / "AGENTS.md").write_text("global\n", encoding="utf-8")
    # A file directly in the home directory IS a stray.
    (home / "AGENTS.md").write_text("stray\n", encoding="utf-8")
    repo = home / "proj" / "repo"
    repo.mkdir(parents=True)
    found = {p for p, _ in mod.strays(repo, ancestors=[home / ".claude", home])}
    assert home / "AGENTS.md" in found
    assert home / ".claude" / "CLAUDE.md" not in found
    assert home / ".claude" / "AGENTS.md" not in found


def test_no_strays_is_clean(tmp_path):
    repo = tmp_path / "clean"
    repo.mkdir()
    assert mod.strays(repo, ancestors=[tmp_path]) == []


def test_cli_reports_a_planted_stray_and_exits_1(tmp_path):
    # A real git repo so `git rev-parse` resolves to it; a stray in its parent.
    repo = tmp_path / "wrap" / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (tmp_path / "wrap" / "CLAUDE.md").write_text("stray\n", encoding="utf-8")
    done = run(str(repo))
    assert done.returncode == 1
    assert "CLAUDE.md" in done.stdout
    assert "claudeMdExcludes" in done.stdout
    # --check is silent, same non-zero verdict.
    checked = run(str(repo), "--check")
    assert checked.returncode == 1
    assert checked.stdout == ""


def test_cli_bad_argv_exits_2(tmp_path):
    done = run(str(tmp_path), str(tmp_path), "extra")
    assert done.returncode == 2
