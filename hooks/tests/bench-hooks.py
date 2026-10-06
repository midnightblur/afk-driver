#!/usr/bin/env python3
"""Time every registered hook command against realistic envelopes. Informational only.

    python hooks/tests/bench-hooks.py [--runs N] [--manifest hooks.json|hooks.codex.json]
                                      [--project DIR] [--only SCENARIO ...]

Each scenario sends one envelope to every handler the manifest registers for its event
and tool. Commands come from the manifest itself, with the plugin root variable set to
this checkout and the project variable set to `--project` (default: the repository the
current folder is in), run without a shell. Plugin data goes to a temporary folder. Handlers run one at a time;
the event wall time is the slowest handler of a run, because the harness runs same-event
handlers in parallel. One warm-up run per scenario is not counted. Prints p50 and p95
per event and per handler, in milliseconds.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
ROOT_VARS = {"hooks.json": "CLAUDE_PLUGIN_ROOT", "hooks.codex.json": "PLUGIN_ROOT"}
PROJECT_VARS = {"hooks.json": "CLAUDE_PROJECT_DIR", "hooks.codex.json": "PROJECT_DIR"}
DATA_VARS = {"hooks.json": "CLAUDE_PLUGIN_DATA", "hooks.codex.json": "PLUGIN_DATA"}


def scenarios(project: Path, scratch: Path) -> dict[str, tuple[str, str, dict]]:
    """name -> (event, tool name, envelope)."""
    readme = (project / "README.md").as_posix()
    base = {"session_id": "bench", "cwd": project.as_posix(), "transcript_path": (scratch / "t.jsonl").as_posix()}
    lavish = (scratch / "bench-x.html").as_posix()
    return {
        "read": ("PreToolUse", "Read", {**base, "hook_event_name": "PreToolUse", "tool_name": "Read",
                                         "tool_input": {"file_path": readme}}),
        "edit": ("PreToolUse", "Edit", {**base, "hook_event_name": "PreToolUse", "tool_name": "Edit",
                                         "tool_input": {"file_path": readme, "old_string": "a", "new_string": "b"}}),
        "bash": ("PreToolUse", "Bash", {**base, "hook_event_name": "PreToolUse", "tool_name": "Bash",
                                         "tool_input": {"command": "ls"}}),
        "bash-lavish": ("PreToolUse", "Bash", {**base, "hook_event_name": "PreToolUse", "tool_name": "Bash",
                                                "tool_input": {"command": f"lavish-axi {lavish}"}}),
        "post": ("PostToolUse", "Read", {**base, "hook_event_name": "PostToolUse", "tool_name": "Read",
                                          "tool_input": {"file_path": readme}, "tool_response": {}}),
        "stop": ("Stop", "", {**base, "hook_event_name": "Stop", "stop_hook_active": False}),
    }


def handlers(manifest: dict, event: str, tool: str) -> list[dict]:
    found = []
    for group in manifest.get("hooks", {}).get(event, []):
        matcher = group.get("matcher") or "*"
        if matcher != "*" and tool and not re.fullmatch(matcher, tool):
            continue
        found.extend(h for h in group.get("hooks", []) if h.get("type") == "command")
    return found


def argv_of(command: str, env: dict[str, str]) -> list[str]:
    expanded = re.sub(r"\$\{(\w+)\}", lambda m: env.get(m.group(1), ""), command)
    return shlex.split(expanded, posix=True)


def label_of(command: str) -> str:
    words = [w.strip('"') for w in command.split()]
    for kind in ("plugin", "repo-list"):
        if kind in words:
            return f"{kind} {words[words.index(kind) + 1]}"
    return Path(words[1] if len(words) > 1 else words[0]).name


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * share // 1))  # nearest-rank
    return ordered[int(rank) - 1]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--manifest", choices=sorted(ROOT_VARS), default="hooks.json")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--only", nargs="*", default=[])
    args = parser.parse_args(argv)

    project = args.project
    if project is None:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        project = Path(top.stdout.strip() or os.getcwd())
    project = project.resolve()
    manifest = json.loads((PLUGIN_ROOT / "hooks" / args.manifest).read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="afk-bench-") as scratch_dir:
        scratch = Path(scratch_dir)
        env = dict(os.environ)
        env[ROOT_VARS[args.manifest]] = str(PLUGIN_ROOT)
        env[PROJECT_VARS[args.manifest]] = str(project)
        env[DATA_VARS[args.manifest]] = str(scratch / "data")
        if args.manifest == "hooks.json":
            env["CLAUDECODE"] = "1"
        print(f"plugin {PLUGIN_ROOT}\nproject {project}\nmanifest {args.manifest}, {args.runs} runs, ms\n")
        print(f"{'scenario / handler':<52} {'p50':>7} {'p95':>7}  rc")
        for name, (event, tool, envelope) in scenarios(project, scratch).items():
            if args.only and name not in args.only:
                continue
            entries = handlers(manifest, event, tool)
            payload = json.dumps(envelope).encode("utf-8")
            times: dict[int, list[float]] = {i: [] for i in range(len(entries))}
            codes: dict[int, int] = {}
            for run in range(args.runs + 1):
                for i, entry in enumerate(entries):
                    start = time.perf_counter()
                    try:
                        done = subprocess.run(argv_of(entry["command"], env), input=payload, cwd=project, env=env,
                                              capture_output=True, timeout=entry.get("timeout", 60))
                        codes[i] = done.returncode
                    except subprocess.TimeoutExpired:
                        codes[i] = -1
                    if run:  # run 0 warms caches and stamps
                        times[i].append((time.perf_counter() - start) * 1000)
            walls = [max(times[i][r] for i in times) for r in range(args.runs)] if entries else [0.0]
            print(f"{name + ' (' + event + ')':<52} {percentile(walls, .5):>7.0f} {percentile(walls, .95):>7.0f}")
            for i, entry in enumerate(entries):
                print(f"  {label_of(entry['command']):<50} {percentile(times[i], .5):>7.0f} "
                      f"{percentile(times[i], .95):>7.0f}  {codes.get(i)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
