#!/usr/bin/env python3
"""Tag-by-tag checks for the AGENTS.md standard mechanical checker.

Each case builds a tmp_path instruction-file tree and asserts on the tagged
findings the steward reads. Covers the docs/rules false-positive fix, the root
bridge exactness, chain summing with one-file-per-directory candidate order,
and the non-git case.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parents[2]
          / "skills" / "afk" / "agents-md" / "scripts" / "mechanical_check.py")


def run(root):
    return subprocess.run([sys.executable, str(SCRIPT), str(root)],
                          capture_output=True, text=True)


def sections(stdout):
    """Parse the tagged output into {tag: [body lines]}. `none` -> []."""
    out = {}
    cur = None
    for ln in stdout.splitlines():
        m = re.match(r"^\[(.+?)\]( none| skipped.*)?$", ln)
        if m:
            cur = m.group(1)
            out[cur] = []
            if m.group(2):
                out[cur + "::note"] = m.group(2).strip()
        elif cur is not None and ln.startswith("  "):
            out[cur].append(ln.strip())
    return out


def write(p: Path, text=""):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_wrong_argv_exits_2():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 2


def test_clean_tree_exit_0_and_summary_last(tmp_path):
    write(tmp_path / "AGENTS.md", "root steering\n")
    write(tmp_path / "CLAUDE.md", "@AGENTS.md\n")
    r = run(tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip().splitlines()[-1].startswith("summary:")


def test_size_over_200(tmp_path):
    write(tmp_path / "AGENTS.md", "\n".join(["line"] * 201) + "\n")
    s = sections(run(tmp_path).stdout)
    assert any("AGENTS.md" in x for x in s["size > 200"])


def test_bytes_over_limit(tmp_path):
    write(tmp_path / "sub" / "AGENTS.md", "x" * 40000)
    s = sections(run(tmp_path).stdout)
    assert any("AGENTS.md" in x for x in s["bytes > 32768"])


def test_chain_sums_one_file_per_directory_in_candidate_order(tmp_path):
    # Root holds override (5000) AND AGENTS.md (20000); candidate order picks
    # the override. sub/AGENTS.md is 30000. Correct chain(sub) = 5000 + 30000.
    write(tmp_path / "AGENTS.override.md", "o" * 5000)
    write(tmp_path / "AGENTS.md", "a" * 20000)
    write(tmp_path / "sub" / "AGENTS.md", "b" * 30000)
    s = sections(run(tmp_path).stdout)
    rows = s["chain > 32768"]
    assert len(rows) == 1
    total, path = rows[0].split(None, 1)
    assert int(total) == 35000          # 5000 (override, not the 20000 AGENTS.md) + 30000
    assert path.replace("\\", "/").endswith("/sub")


def test_import_in_agents_md(tmp_path):
    write(tmp_path / "AGENTS.md", "steering\n@shared/rules.md\n")
    write(tmp_path / "shared" / "rules.md", "x")
    s = sections(run(tmp_path).stdout)
    assert any("@shared/rules.md" in x for x in s["import"])


def test_bridge_flags_wrong_content_and_passes_exact(tmp_path):
    write(tmp_path / "AGENTS.md", "root\n")
    write(tmp_path / "CLAUDE.md", "hand-written steering, not a bridge\n")
    s = sections(run(tmp_path).stdout)
    assert s["bridge"]

    write(tmp_path / "CLAUDE.md", "@AGENTS.md\n")
    s = sections(run(tmp_path).stdout)
    assert s["bridge"] == []


def test_migrate_lists_nonroot_claude_not_the_bridge(tmp_path):
    write(tmp_path / "AGENTS.md", "root\n")
    write(tmp_path / "CLAUDE.md", "@AGENTS.md\n")
    write(tmp_path / "svc" / "CLAUDE.md", "service steering\n")
    s = sections(run(tmp_path).stdout)
    assert any(x.replace("\\", "/").endswith("svc/CLAUDE.md") for x in s["migrate"])
    assert not any(x.replace("\\", "/").endswith("/CLAUDE.md")
                   and "/svc/" not in x.replace("\\", "/") for x in s["migrate"])


def test_override_listed(tmp_path):
    write(tmp_path / "AGENTS.override.md", "override steering\n")
    s = sections(run(tmp_path).stdout)
    assert s["override"]


def test_docs_rules_is_not_a_claude_rules_file(tmp_path):
    # docs/rules/ must NOT be classified as .claude/rules — the false positive.
    write(tmp_path / "docs" / "rules" / "style.md", "no frontmatter\n")
    write(tmp_path / ".claude" / "rules" / "scoped.md", "no frontmatter\n")
    s = sections(run(tmp_path).stdout)
    flagged = "\n".join(s["rule-paths"]).replace("\\", "/")
    assert ".claude/rules/scoped.md" in flagged
    assert "docs/rules/style.md" not in flagged


def test_rule_paths_frontmatter(tmp_path):
    write(tmp_path / ".claude" / "rules" / "nopaths.md", "no key\n")
    write(tmp_path / ".claude" / "rules" / "withpaths.md",
          "---\npaths:\n  - \"**/*.java\"\n---\nbody\n")
    s = sections(run(tmp_path).stdout)
    flagged = "\n".join(s["rule-paths"]).replace("\\", "/")
    assert ".claude/rules/nopaths.md" in flagged
    assert ".claude/rules/withpaths.md" not in flagged


def test_broken_import_in_claude_only(tmp_path):
    write(tmp_path / "AGENTS.md", "root\n")
    write(tmp_path / "CLAUDE.md", "@AGENTS.md\n")            # resolves -> not broken
    write(tmp_path / "svc" / "CLAUDE.md", "@../missing.md\n")  # broken
    s = sections(run(tmp_path).stdout)
    assert any("@../missing.md" in x for x in s["broken-import"])
    assert not any("@AGENTS.md" in x for x in s["broken-import"])


def test_tracked_local_needs_git_and_skips_cleanly_without_it(tmp_path):
    # No git repo -> tracked-local skipped cleanly, exit 0.
    write(tmp_path / "CLAUDE.local.md", "personal pref\n")
    r = run(tmp_path)
    assert r.returncode == 0
    s = sections(r.stdout)
    assert s.get("tracked-local::note", "").startswith("skipped")


def test_tracked_local_flags_committed_files(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@t")
    git(tmp_path, "config", "user.name", "t")
    write(tmp_path / "CLAUDE.local.md", "personal\n")
    write(tmp_path / "AGENTS.override.md", "override\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "init")
    s = sections(run(tmp_path).stdout)
    flagged = "\n".join(s["tracked-local"]).replace("\\", "/")
    assert "CLAUDE.local.md" in flagged
    assert "AGENTS.override.md" in flagged


def test_claude_md_excludes_drops_a_file(tmp_path):
    write(tmp_path / "vendored" / "CLAUDE.md", "third-party steering\n")
    s = sections(run(tmp_path).stdout)
    assert any("vendored/CLAUDE.md" in x.replace("\\", "/") for x in s["migrate"])

    write(tmp_path / ".claude" / "settings.json",
          '{"claudeMdExcludes": ["vendored/**"]}')
    s = sections(run(tmp_path).stdout)
    assert not any("vendored/CLAUDE.md" in x.replace("\\", "/") for x in s["migrate"])
