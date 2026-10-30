import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import plugin_check  # noqa: E402
import search_bench  # noqa: E402

CHECK = PLUGIN / "scripts" / "plugin_check.py"
BENCH = PLUGIN / "scripts" / "search_bench.py"
SOURCE = PLUGIN / plugin_check.CORE_SOURCE
BUILT = PLUGIN / plugin_check.BUILT_DIR
SEARCH_COMMAND = "`rg --hidden -g '!.git' PATTERN PATH`"


def _core_text():
    return SOURCE.read_text(encoding="utf-8").replace("\r\n", "\n")


def _timed(seconds_by_tool, hits_by_tool):
    """An in-process stand-in for the timed subprocess call."""

    def runner(command, cwd):
        tool = command[0]
        return search_bench.Sample(seconds=seconds_by_tool[tool], hits=hits_by_tool[tool], code=0)

    return runner


def _same_hits():
    return {"rg": [b"a/b.txt:word"], "git": [b"a/b.txt:word"]}


def test_a_benchmark_with_equal_hits_at_60_percent_passes():
    answer = search_bench.run_benchmark("repo", runner=_timed({"rg": 0.6, "git": 1.0}, _same_hits()))
    assert answer["verdict"] == "pass"
    assert answer["same_hits"] is True
    assert answer["ratio"] == pytest.approx(0.6)


def test_a_benchmark_over_60_percent_fails():
    answer = search_bench.run_benchmark("repo", runner=_timed({"rg": 0.61, "git": 1.0}, _same_hits()))
    assert answer["verdict"] == "fail"


def test_a_benchmark_with_different_hits_fails_and_names_them():
    hits = {"rg": [b"a.txt:word"], "git": [b"a.txt:word", b"b.txt:word"]}
    answer = search_bench.run_benchmark("repo", runner=_timed({"rg": 0.1, "git": 1.0}, hits))
    assert answer["verdict"] == "fail"
    assert answer["same_hits"] is False
    assert answer["only_in_git"] == 1
    assert answer["only_in_rg"] == 0
    assert answer["sample_differences"] == ["git only: b.txt:word"]


def test_a_benchmark_takes_the_median_of_the_runs_and_a_discarded_warm_up():
    times = iter([9.0, 9.0, 1.0, 2.0, 5.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0])

    def runner(command, cwd):
        return search_bench.Sample(seconds=next(times), hits=[b"a.txt:word"], code=0)

    answer = search_bench.run_benchmark("repo", runs=5, runner=runner)
    assert answer["rg"]["median_s"] == 1.0
    assert answer["git"]["median_s"] == 2.0
    assert answer["runs"] == 5
    assert len(answer["rg"]["seconds"]) == 5


def test_no_hits_is_no_verdict():
    answer = search_bench.run_benchmark("repo", runner=_timed({"rg": 0.1, "git": 1.0}, {"rg": [], "git": []}))
    assert answer["verdict"] == "no-verdict"


def test_a_tool_error_is_no_verdict():
    def runner(command, cwd):
        return search_bench.Sample(seconds=1.0, hits=[b"a.txt:word"], code=2)

    assert search_bench.run_benchmark("repo", runner=runner)["verdict"] == "no-verdict"


def test_a_binary_match_line_is_not_a_hit():
    assert search_bench.normalize_hits("rg", b".\\a.bin: binary file matches (found \"\\0\" byte around offset 5)\n") == []
    assert search_bench.normalize_hits("git", b"Binary file a.bin matches\n") == []


def test_the_answer_counts_binary_notices_per_tool(tmp_path):
    if not shutil.which("rg") or not shutil.which("git"):
        pytest.skip("rg or git is not on the path")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.txt").write_text("needle\n", encoding="utf-8")
    (tmp_path / "b.bin").write_bytes(b"needle\x00\n")

    answer = search_bench.run_benchmark(str(tmp_path), pattern="needle", runs=1)

    assert answer["same_hits"] is True
    assert answer["git"]["binary_notices"] == 1
    assert answer["rg"]["hits"] == answer["git"]["hits"] == 1


def test_normalize_keeps_a_colon_in_the_text_and_drops_a_carriage_return():
    assert search_bench.normalize_hits("rg", b".\\a\\b.txt:x:y\\z\r\n") == [b"a/b.txt:x:y\\z"]


def test_the_real_tools_agree_on_a_small_repository(tmp_path):
    if not shutil.which("rg") or not shutil.which("git"):
        pytest.skip("rg or git is not on the path")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "tracked.txt").write_text("needle one\n", encoding="utf-8")
    (tmp_path / "untracked.txt").write_text("needle two\n", encoding="utf-8")
    (tmp_path / ".hidden.txt").write_text("needle three\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.txt").write_text("needle four\n", encoding="utf-8")
    (tmp_path / "ignored.log").write_text("needle five\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.txt"], check=True)

    answer = search_bench.run_benchmark(str(tmp_path), pattern="needle", runs=1)

    assert answer["same_hits"] is True
    assert answer["rg"]["hits"] == 4


def test_the_real_search_closes_stdin(tmp_path):
    if not shutil.which("rg"):
        pytest.skip("rg is not on the path")
    (tmp_path / "a.txt").write_text("needle\n", encoding="utf-8")
    sample = search_bench.timed_run(search_bench.rg_command("needle"), str(tmp_path))
    assert sample.code == 0
    assert sample.hits == [b"a.txt:needle"]


def test_the_rg_command_is_the_core_command():
    assert search_bench.rg_command("word") == ["rg", "--hidden", "-g", "!.git", "word", "."]


@pytest.mark.parametrize("args", [[], ["--repo"], ["--repo", ".", "--pattern", "a b"], ["--repo", ".", "--runs", "0"]])
def test_bad_use_exits_2_with_one_json_object(args):
    done = subprocess.run([sys.executable, str(BENCH), *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert done.returncode == 2
    assert json.loads(done.stdout)["ok"] is False


def test_the_command_prints_the_answer_and_exits_by_verdict(tmp_path):
    if not shutil.which("rg") or not shutil.which("git"):
        pytest.skip("rg or git is not on the path")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.txt").write_text("needle\n", encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(BENCH), "--repo", str(tmp_path), "--pattern", "needle", "--runs", "1"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    answer = json.loads(done.stdout)
    assert answer["same_hits"] is True
    assert done.returncode == {"pass": 0, "fail": 1, "no-verdict": 2}[answer["verdict"]]


def _copy_tree(tmp_path):
    copy = tmp_path / "plugin"
    shutil.copytree(PLUGIN, copy, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return copy


def _run_check(root, verb="check"):
    done = subprocess.run(
        [sys.executable, str(CHECK), verb, "--root", str(root)],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    return done.returncode, json.loads(done.stdout)


def _pad_core(root, characters):
    text = _core_text().rstrip("\n") + "\n"
    (root / plugin_check.CORE_SOURCE).write_text(text + "x" * (characters - len(text)), encoding="utf-8", newline="")


def test_a_copy_with_8001_characters_fails_the_plugin_check_and_the_build(tmp_path):
    root = _copy_tree(tmp_path)
    _pad_core(root, 8001)
    for verb in ("check", "build"):
        code, answer = _run_check(root, verb)
        assert code == 1
        assert any("8001 characters" in problem for problem in answer["problems"])


def test_a_copy_with_8000_characters_builds_and_passes(tmp_path):
    root = _copy_tree(tmp_path)
    _pad_core(root, 8000)
    assert _run_check(root, "build")[0] == 0
    assert _run_check(root)[0] == 0


def test_the_real_tree_passes_the_plugin_check():
    code, answer = _run_check(PLUGIN)
    assert code == 0, answer


def test_the_text_names_one_search_command_with_its_reason():
    lines = [line for line in _core_text().splitlines() if "rg --hidden" in line]
    assert len(lines) == 1
    assert SEARCH_COMMAND in lines[0]
    assert "for every code search" in lines[0]
    assert "Always give a PATH. Without a path, rg reads stdin and can hang." in _core_text()


@pytest.mark.parametrize(
    "rule",
    [
        "linked worktree",
        "Commit often.",
        "Draft change",
        "merge the target in and resolve conflicts",
        "Never rebase a pushed branch.",
        "test only what changed",
        "ownership grade",
        "Own:",
        "Shared:",
        "Not owned:",
        "two-way door",
        "Verify instead of asking.",
        "Simplified Technical English",
    ],
)
def test_the_text_carries_the_interim_rule(rule):
    assert rule in _core_text()


def test_the_text_holds_no_v1_name():
    assert plugin_check.V1_FILE_PART.search(_core_text()) is None


def test_the_text_is_ascii_so_the_cmd_hook_prints_it_unchanged():
    assert _core_text().isascii()


def test_the_markers_wrap_the_text_in_the_prebuilt_files():
    body = _core_text().rstrip("\n")
    sha = plugin_check.marker_hash(body)
    expected = f"{plugin_check.MARKER} begin {sha}\n{body}\n{plugin_check.MARKER} end {sha}\n"
    assert (BUILT / plugin_check.PLAIN_VARIANT).read_bytes() == expected.encode("utf-8")
    subagent = json.loads((BUILT / plugin_check.CLAUDE_SUBAGENT_VARIANT).read_text(encoding="utf-8"))
    assert subagent["hookSpecificOutput"]["additionalContext"] == expected
