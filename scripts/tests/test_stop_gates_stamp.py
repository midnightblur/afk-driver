import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_stop", ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()


@pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")
def test_stop_stamp_is_written_in_a_repository_without_a_cache_directory(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {**os.environ, "GATE_CACHE_DISABLE": "0"}
    result = subprocess.run([str(BASH), str(ROOT / "hooks" / "stop-gates.sh")], cwd=tmp_path, env=env,
                            input="{}", capture_output=True, text=True, timeout=300)
    assert "No such file or directory" not in result.stderr
    stamp = tmp_path / ".claude" / "hooks" / ".gate-cache" / ".last-stop"
    assert stamp.read_text(encoding="utf-8").startswith("pass:")
