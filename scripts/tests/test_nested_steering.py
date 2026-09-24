#!/usr/bin/env python3
"""`nested_steering.py` collects nested AGENTS.md + matching rules for injection.

Each case builds a throwaway git repo with a nested AGENTS.md carrying a unique
token, then runs the collector as the launcher would — envelope on stdin, policy
in argv, markers under a tmp data dir. Nothing touches a real harness home.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

MODULE = (Path(__file__).resolve().parents[2]
          / "hooks" / "lib" / "nested_steering.py")

TOKEN = "NESTED-TOKEN-XYZ"
RULE_TOKEN = "RULE-TOKEN-QRS"


def _module():
    spec = importlib.util.spec_from_file_location("afk_nested_steering", MODULE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ns = _module()


def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "sub" / "deep").mkdir(parents=True)
    (root / ".claude" / "rules").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "AGENTS.md").write_text("root steering\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (root / "sub" / "deep" / "AGENTS.md").write_text(
        "deep steering %s\n" % TOKEN, encoding="utf-8")
    (root / "sub" / "deep" / "x.txt").write_text("hello\n", encoding="utf-8")
    (root / "sub" / "deep" / "widget.ts").write_text("export const a=1;\n", encoding="utf-8")
    (root / ".claude" / "rules" / "scoped.md").write_text(
        '---\npaths: ["**/*.ts"]\n---\nrule body %s\n' % RULE_TOKEN, encoding="utf-8")
    # git rev-parse may report a differently-spelled root; use the reported one.
    top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True).stdout.strip()
    return Path(top)


def run(root, data_dir, mode="always", rules="1", event="PostToolUse",
        file_path=None, agent_id=None, session="s1"):
    envelope = {"session_id": session, "cwd": str(root), "hook_event_name": event,
                "tool_name": "Read"}
    if file_path is not None:
        envelope["tool_input"] = {"file_path": str(file_path)}
    if agent_id is not None:
        envelope["agent_id"] = agent_id
    done = subprocess.run(
        [sys.executable, str(MODULE), "--provider", "codex", "--mode", mode,
         "--rules", rules, "--data-dir", str(data_dir)],
        input=json.dumps(envelope), capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_injects_nested_agents_below_launch_dir(tmp_path):
    root = repo(tmp_path)
    out = run(root, tmp_path / "d", file_path=root / "sub" / "deep" / "x.txt")
    assert TOKEN in out
    assert "root steering" not in out          # the launch-dir chain is not re-injected


def test_dedup_then_reset(tmp_path):
    root = repo(tmp_path)
    data = tmp_path / "d"
    first = run(root, data, file_path=root / "sub" / "deep" / "x.txt")
    assert TOKEN in first
    second = run(root, data, file_path=root / "sub" / "deep" / "x.txt")
    assert second == ""                        # same (session, agent, dir) deduped
    run(root, data, event="PostCompact")       # reset markers
    third = run(root, data, file_path=root / "sub" / "deep" / "x.txt")
    assert TOKEN in third                      # re-armed


def test_reset_on_session_start(tmp_path):
    root = repo(tmp_path)
    data = tmp_path / "d"
    run(root, data, file_path=root / "sub" / "deep" / "x.txt")
    run(root, data, event="SessionStart")
    assert TOKEN in run(root, data, file_path=root / "sub" / "deep" / "x.txt")


def test_mode_never_is_silent(tmp_path):
    root = repo(tmp_path)
    out = run(root, tmp_path / "d", mode="never",
              file_path=root / "sub" / "deep" / "x.txt")
    assert out == ""


def test_agent_only_gate(tmp_path):
    root = repo(tmp_path)
    data = tmp_path / "d"
    # No agent id: agent-only injects nothing.
    assert run(root, data, mode="agent-only",
               file_path=root / "sub" / "deep" / "x.txt") == ""
    # With an agent id: it injects.
    assert TOKEN in run(root, data, mode="agent-only", agent_id="child-7",
                        file_path=root / "sub" / "deep" / "x.txt")


def test_rules_leg_toggles(tmp_path):
    root = repo(tmp_path)
    with_rules = run(root, tmp_path / "d1", rules="1",
                     file_path=root / "sub" / "deep" / "widget.ts")
    assert RULE_TOKEN in with_rules
    without = run(root, tmp_path / "d2", rules="0",
                  file_path=root / "sub" / "deep" / "widget.ts")
    assert RULE_TOKEN not in without


def test_touch_at_launch_dir_injects_nothing(tmp_path):
    root = repo(tmp_path)
    (root / "top.txt").write_text("x\n", encoding="utf-8")
    out = run(root, tmp_path / "d", file_path=root / "top.txt")
    assert out == ""


def test_chain_below_strictly_below_ceiling(tmp_path):
    ceiling = tmp_path / "a" / "b"
    deep = ceiling / "c" / "d"
    deep.mkdir(parents=True)
    chain = ns.chain_below(deep, ceiling)
    assert [p.name for p in chain] == ["c", "d"]         # shallow first, deepest last
    assert ns.chain_below(ceiling, ceiling) == []        # nothing at the ceiling
    assert ns.chain_below(tmp_path / "a", ceiling) == []  # nothing above it


def test_claim_is_atomic_once(tmp_path):
    assert ns.claim(str(tmp_path), "s", "main", "k") is True
    assert ns.claim(str(tmp_path), "s", "main", "k") is False
    ns.reset(str(tmp_path), "s")
    assert ns.claim(str(tmp_path), "s", "main", "k") is True
