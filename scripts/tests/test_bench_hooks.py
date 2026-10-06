"""`hooks/tests/bench-hooks.py` picks the handlers the harness would run and reports per event."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "hooks" / "tests" / "bench-hooks.py"


def _bench():
    spec = importlib.util.spec_from_file_location("afk_bench_hooks", BENCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_handlers_follow_the_manifest_matchers():
    bench = _bench()
    manifest = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    bash = [bench.label_of(h["command"]) for h in bench.handlers(manifest, "PreToolUse", "Bash")]
    read = [bench.label_of(h["command"]) for h in bench.handlers(manifest, "PreToolUse", "Read")]
    assert "plugin lavish-dark.sh" in bash and "plugin lavish-dark.sh" not in read
    assert "protected-branch-guard.py" in bash and "protected-branch-guard.py" in read


def test_percentile_is_nearest_rank():
    bench = _bench()
    assert bench.percentile([5.0, 1.0, 3.0, 2.0, 4.0], 0.5) == 3.0
    assert bench.percentile([5.0, 1.0, 3.0, 2.0, 4.0], 0.95) == 5.0


def test_one_run_reports_the_event_and_each_handler(tmp_path):
    done = subprocess.run([sys.executable, str(BENCH), "--runs", "1", "--only", "read"], cwd=ROOT,
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    assert "read (PreToolUse)" in done.stdout and "protected-branch-guard.py" in done.stdout
