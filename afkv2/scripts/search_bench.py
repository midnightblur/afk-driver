"""Time the core search command against `git grep --untracked`; answer one JSON object.

Command: `search_bench.py --repo DIR [--pattern WORD] [--runs N]`.
Exit 0 pass, 1 fail, 2 usage or no verdict. Pass: same hits, and rg at most 60% of the git median.
A hit is one matching text line. A binary-file notice is not a hit; the answer counts notices per tool.
The repository stays read-only: rg and git grep only read, and git takes no optional lock.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DEFAULT_PATTERN = "Transactional"
DEFAULT_RUNS = 5
LIMIT = 0.60
TIMEOUT_SECONDS = 600
MAX_SAMPLE_DIFFERENCES = 10
PLAIN_WORD = re.compile(r"[A-Za-z0-9_]+")
RG_BINARY_LINE = re.compile(rb"^[^:]*: binary file matches \(")
GIT_BINARY_LINE = re.compile(rb"^Binary file .* matches$")


@dataclass
class Sample:
    seconds: float
    hits: list[bytes]
    code: int
    binary_notices: int = 0


def rg_command(pattern: str) -> list[str]:
    return ["rg", "--hidden", "-g", "!.git", pattern, "."]


def git_command(pattern: str) -> list[str]:
    return [
        "git", "--no-pager",
        "-c", "core.quotepath=off",
        "-c", "grep.lineNumber=false",
        "-c", "grep.column=false",
        "-c", "grep.fullName=false",
        "grep", "--untracked", "--no-color", pattern,
    ]  # fmt: skip


def normalize_hits(tool: str, raw: bytes) -> list[bytes]:
    """`path:text` lines with a repository-relative forward-slash path, without binary-file notices."""
    hits = []
    for line in raw.split(b"\n"):
        line = line.rstrip(b"\r")
        if not line or _is_binary_notice(tool, line):
            continue
        path, separator, text = line.partition(b":")
        path = path.replace(b"\\", b"/")
        hits.append((path[2:] if path.startswith(b"./") else path) + separator + text)
    return hits


def count_binary_notices(tool: str, raw: bytes) -> int:
    return sum(_is_binary_notice(tool, line.rstrip(b"\r")) for line in raw.split(b"\n"))


def _is_binary_notice(tool: str, line: bytes) -> bool:
    return (RG_BINARY_LINE if tool == "rg" else GIT_BINARY_LINE).match(line) is not None


def timed_run(command: list[str], cwd: str) -> Sample:
    """Run one search with stdin closed: rg with an open stdin can wait on it."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    env.pop("RIPGREP_CONFIG_PATH", None)
    started = time.perf_counter()
    try:
        done = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return Sample(seconds=time.perf_counter() - started, hits=[], code=-1)
    seconds = time.perf_counter() - started
    tool = command[0]
    return Sample(seconds, normalize_hits(tool, done.stdout), done.returncode, count_binary_notices(tool, done.stdout))


def run_benchmark(
    repo: str,
    pattern: str = DEFAULT_PATTERN,
    runs: int = DEFAULT_RUNS,
    runner: Callable[[list[str], str], Sample] = timed_run,
) -> dict:
    """Each run times rg, then git grep. One first pair warms the file cache and does not count."""
    commands = {"rg": rg_command(pattern), "git": git_command(pattern)}
    for command in commands.values():
        runner(command, repo)
    seconds = {"rg": [], "git": []}
    counts = {}
    notices = {}
    difference = None
    failed_code = None
    for _ in range(runs):
        for tool, command in commands.items():
            sample = runner(command, repo)
            seconds[tool].append(sample.seconds)
            counts[tool] = Counter(sample.hits)
            notices[tool] = sample.binary_notices
            if sample.code not in (0, 1):
                failed_code = f"{tool} exited {sample.code}"
        if difference is None and counts["rg"] != counts["git"]:
            difference = (counts["rg"] - counts["git"], counts["git"] - counts["rg"])
    medians = {tool: statistics.median(values) for tool, values in seconds.items()}
    only_in_rg, only_in_git = difference or (Counter(), Counter())
    same_hits = difference is None
    ratio = medians["rg"] / medians["git"] if medians["git"] else None
    answer = {
        "ok": True,
        "repo": repo,
        "pattern": pattern,
        "runs": runs,
        "limit": LIMIT,
        "ratio": ratio,
        "same_hits": same_hits,
        "only_in_rg": sum(only_in_rg.values()),
        "only_in_git": sum(only_in_git.values()),
        "sample_differences": _sample_differences(only_in_rg, only_in_git),
    }
    for tool in commands:
        answer[tool] = {
            "median_s": medians[tool],
            "seconds": seconds[tool],
            "hits": sum(counts[tool].values()),
            "binary_notices": notices[tool],
        }
    answer["verdict"], answer["reason"] = _verdict(failed_code, counts, same_hits, ratio)
    return answer


def _verdict(failed_code: str | None, counts: dict, same_hits: bool, ratio: float | None) -> tuple[str, str]:
    if failed_code:
        return "no-verdict", failed_code
    if not counts["rg"] and not counts["git"]:
        return "no-verdict", "the pattern has no hits, so the compare proves nothing"
    if not same_hits:
        return "fail", "the tools return different hits"
    if ratio is None or ratio > LIMIT:
        return "fail", f"rg took more than {LIMIT:.0%} of the git grep time"
    return "pass", f"same hits, and rg took at most {LIMIT:.0%} of the git grep time"


def _sample_differences(only_in_rg: Counter, only_in_git: Counter) -> list[str]:
    lines = [f"rg only: {_text(hit)}" for hit in sorted(only_in_rg)]
    lines += [f"git only: {_text(hit)}" for hit in sorted(only_in_git)]
    return lines[:MAX_SAMPLE_DIFFERENCES]


def _text(hit: bytes) -> str:
    return hit.decode("utf-8", "replace")[:200]


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _UsageError(message)


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = _Parser(prog="search_bench.py", add_help=False)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pattern", default=DEFAULT_PATTERN)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    args = parser.parse_args(argv)
    if not PLAIN_WORD.fullmatch(args.pattern):
        raise _UsageError("--pattern must be one plain word: rg and git grep read other patterns differently")
    if args.runs < 1:
        raise _UsageError("--runs must be at least 1")
    if not Path(args.repo).is_dir():
        raise _UsageError(f"--repo is not a directory: {args.repo}")
    return args


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse(argv)
    except _UsageError as error:
        print(json.dumps({"ok": False, "error": {"code": "usage", "reason": str(error)}}))
        return 2
    answer = run_benchmark(args.repo, args.pattern, args.runs)
    print(json.dumps(answer))
    return {"pass": 0, "fail": 1, "no-verdict": 2}[answer["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
