"""H12's probe reads the harness config for a trust key at each guarded hook position."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN_ROOT / "skills" / "afk" / "setup" / "scripts" / "check_hook_trust.py"
MANIFEST = PLUGIN_ROOT / "hooks" / "hooks.codex.json"


def keys() -> list[str]:
    events = json.loads(MANIFEST.read_text(encoding="utf-8"))["hooks"]
    out = []
    for event, script in (("PreToolUse", "protected-branch-guard.py"), ("PostToolUse", "protected-branch-meter.py"),
                          ("SessionEnd", "worktree-remove.sh"), ("SessionStart", "worktree-prune.sh"),
                          ("SessionStart", "protected-branch-occupancy.py")):
        for group, entry in enumerate(events[event]):
            for handler, hook in enumerate(entry["hooks"]):
                if script in hook["command"]:
                    out.append(f"{event}:{group}:{handler}")
    return out


def check(tmp_path: Path, config: str | None):
    target = tmp_path / "config.toml"
    if config is not None:
        target.write_text(config, encoding="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), "--config", str(target), "--manifest", str(MANIFEST)],
                          capture_output=True, text=True, timeout=60)


def table(position: str) -> str:
    return f'[hooks.state."afk@some-market:hooks/hooks.codex.json:{position}"]\ntrusted_hash = "sha256:0"\n\n'


def test_the_manifest_positions_are_the_five_guarded_hooks():
    assert len(keys()) == 5


def test_every_key_present_is_trusted(tmp_path):
    done = check(tmp_path, "".join(table(p) for p in keys()))
    assert done.returncode == 0 and done.stdout == ""


def test_a_missing_key_names_the_position_and_the_step(tmp_path):
    present = keys()
    done = check(tmp_path, "".join(table(p) for p in present[1:]))
    assert done.returncode == 1
    assert f"missing: {present[0]}" in done.stdout and "/hooks" in done.stdout


def test_a_key_without_a_hash_is_not_trusted(tmp_path):
    wanted = keys()
    text = "".join(table(p) for p in wanted[1:]) + f'[hooks.state."afk@m:hooks/hooks.codex.json:{wanted[0]}"]\n'
    assert check(tmp_path, text).returncode == 1


def test_r9_5_another_plugins_key_at_the_same_position_is_not_afks(tmp_path):
    text = "".join(table(p).replace("afk@some-market", "other@some-market") for p in keys())
    done = check(tmp_path, text)
    assert done.returncode == 1 and done.stdout.count("missing:") == 5


def test_no_config_file_is_not_applicable(tmp_path):
    assert check(tmp_path, None).returncode == 2
