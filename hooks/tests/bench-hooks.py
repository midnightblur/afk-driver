#!/usr/bin/env python3
"""Time every registered hook command against realistic envelopes. Informational only.

    python hooks/tests/bench-hooks.py [--runs N] [--manifest hooks.json|hooks.codex.json]
                                      [--project DIR] [--only SCENARIO ...]

Each scenario sends one envelope to every handler the manifest registers for its event
and matcher subject (tool name, or session source). Commands come from the manifest itself,
run without a shell. The environment carries only the selected harness: every provider's
markers (`hooks/lib/providers/*.json`) are removed, then `AFK_PROVIDER`, the plugin root
(this checkout), the project and a temporary plugin data folder are set for that harness.

Tool and compaction scenarios run in `--project` (default: the repository the current folder
is in). Lifecycle scenarios (session start and end, worktree create and remove) run in a
disposable shallow clone of it with a temporary home folder, so no hook installs, prunes,
creates or opens anything outside the scratch folder; worktree removal times a worktree the
creation handler made, untimed, before each run.

Handlers run one at a time; the event wall time is the slowest handler of a run, because
the harness runs same-event handlers in parallel. One warm-up run per scenario is not
counted. Prints p50 and p95 per event and per handler, in milliseconds. A scenario whose
event the manifest does not register prints nothing.
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
PROVIDERS = {"hooks.json": "claude", "hooks.codex.json": "codex"}
ROOT_VARS = {"hooks.json": "CLAUDE_PLUGIN_ROOT", "hooks.codex.json": "PLUGIN_ROOT"}
PROJECT_VARS = {"hooks.json": "CLAUDE_PROJECT_DIR", "hooks.codex.json": "PROJECT_DIR"}
DATA_VARS = {"hooks.json": "CLAUDE_PLUGIN_DATA", "hooks.codex.json": "PLUGIN_DATA"}


class Scenario:
    def __init__(self, event: str, subject: str, fields: dict, lifecycle: bool = False,
                 needs_worktree: bool = False, per_run_name: str = ""):
        self.event, self.subject, self.fields = event, subject, fields
        self.lifecycle, self.needs_worktree, self.per_run_name = lifecycle, needs_worktree, per_run_name


def scenarios(project: Path, scratch: Path) -> dict[str, Scenario]:
    readme = (project / "README.md").as_posix()
    lavish = (scratch / "bench-x.html").as_posix()
    return {
        "read": Scenario("PreToolUse", "Read", {"tool_name": "Read", "tool_input": {"file_path": readme}}),
        "edit": Scenario("PreToolUse", "Edit", {"tool_name": "Edit", "tool_input": {
            "file_path": readme, "old_string": "a", "new_string": "b"}}),
        "bash": Scenario("PreToolUse", "Bash", {"tool_name": "Bash", "tool_input": {"command": "ls"}}),
        "bash-lavish": Scenario("PreToolUse", "Bash", {"tool_name": "Bash",
                                                       "tool_input": {"command": f"lavish-axi {lavish}"}}),
        "post": Scenario("PostToolUse", "Read", {"tool_name": "Read", "tool_input": {"file_path": readme},
                                                 "tool_response": {}}),
        "compact": Scenario("PostCompact", "auto", {"trigger": "auto"}),
        "stop": Scenario("Stop", "", {"stop_hook_active": False}),
        "session-start": Scenario("SessionStart", "startup", {"source": "startup"}, lifecycle=True),
        "worktree-create": Scenario("WorktreeCreate", "", {}, lifecycle=True, per_run_name="bench-new"),
        "worktree-remove": Scenario("WorktreeRemove", "", {}, lifecycle=True, needs_worktree=True),
        "session-end": Scenario("SessionEnd", "other", {"reason": "other"}, lifecycle=True),
    }


def handlers(manifest: dict, event: str, subject: str) -> list[dict]:
    found = []
    for group in manifest.get("hooks", {}).get(event, []):
        matcher = group.get("matcher") or "*"
        if matcher != "*" and subject and not re.fullmatch(matcher, subject):
            continue
        found.extend(h for h in group.get("hooks", []) if h.get("type") == "command")
    return found


def uncovered(manifest: dict) -> list[str]:
    """Manifest commands no scenario sends an envelope to."""
    table = scenarios(Path("."), Path("."))
    reached = {id(h) for s in table.values() for h in handlers(manifest, s.event, s.subject)}
    return [f"{event}: {h['command']}" for event, groups in manifest.get("hooks", {}).items()
            for group in groups for h in group.get("hooks", []) if id(h) not in reached]


def harness_env(manifest_name: str, project: Path, data: Path, home: Path | None = None) -> dict[str, str]:
    """The ambient environment minus every provider marker, plus the selected harness's own."""
    markers = {"AFK_PROVIDER", "AFK_WORKTREE_OWNER", *ROOT_VARS.values(), *PROJECT_VARS.values(),
               *DATA_VARS.values()}
    for path in (PLUGIN_ROOT / "hooks" / "lib" / "providers").glob("*.json"):
        spec = json.loads(path.read_text(encoding="utf-8"))
        markers.update(spec.get("detect", {}).get("any_env", []))
        if spec.get("owner_pid_env"):
            markers.add(spec["owner_pid_env"])
    env = {k: v for k, v in os.environ.items() if k not in markers}
    env["AFK_PROVIDER"] = PROVIDERS[manifest_name]
    env[ROOT_VARS[manifest_name]] = str(PLUGIN_ROOT)
    env[PROJECT_VARS[manifest_name]] = str(project)
    env[DATA_VARS[manifest_name]] = str(data)
    if manifest_name == "hooks.json":
        env["CLAUDECODE"] = "1"
    if home is not None:
        env["HOME"] = env["USERPROFILE"] = str(home)
    return env


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


def clone_of(project: Path, scratch: Path) -> Path:
    clone = scratch / "clone"
    subprocess.run(["git", "clone", "-q", "--depth", "1", project.as_uri(), str(clone)], check=True,
                   capture_output=True)
    return clone


def call(entry: dict, envelope: dict, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(argv_of(entry["command"], env), input=json.dumps(envelope).encode("utf-8"),
                              cwd=cwd, env=env, capture_output=True, timeout=entry.get("timeout", 600))
    except subprocess.TimeoutExpired:
        return None


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
    creators = handlers(manifest, "WorktreeCreate", "")

    with tempfile.TemporaryDirectory(prefix="afk-bench-", ignore_cleanup_errors=True) as scratch_dir:
        scratch = Path(scratch_dir)
        (scratch / "home").mkdir()
        clone: Path | None = None
        print(f"plugin {PLUGIN_ROOT}\nproject {project}\nmanifest {args.manifest}, {args.runs} runs, ms\n")
        print(f"{'scenario / handler':<52} {'p50':>7} {'p95':>7}  rc")
        for name, scenario in scenarios(project, scratch).items():
            entries = handlers(manifest, scenario.event, scenario.subject)
            if (args.only and name not in args.only) or not entries:
                continue
            if scenario.needs_worktree and not creators:
                continue
            if scenario.lifecycle and clone is None:
                clone = clone_of(project, scratch)
            where = clone if scenario.lifecycle else project
            env = harness_env(args.manifest, where, scratch / "data", scratch / "home" if scenario.lifecycle else None)
            base = {"session_id": "bench", "cwd": where.as_posix(), "hook_event_name": scenario.event,
                    "transcript_path": (scratch / "t.jsonl").as_posix(), **scenario.fields}
            times: dict[int, list[float]] = {i: [] for i in range(len(entries))}
            codes: dict[int, int] = {}
            for run in range(args.runs + 1):
                envelope = dict(base)
                if scenario.per_run_name:
                    envelope["name"] = f"{scenario.per_run_name}-{run}"
                if scenario.needs_worktree:  # untimed: the worktree this run removes
                    made = call(creators[0], {**base, "hook_event_name": "WorktreeCreate",
                                              "name": f"bench-old-{run}"}, where, env)
                    lines = made.stdout.decode(errors="replace").strip().splitlines() if made else []
                    envelope["worktree_path"] = lines[-1] if lines else ""
                for i, entry in enumerate(entries):
                    start = time.perf_counter()
                    done = call(entry, envelope, where, env)
                    codes[i] = done.returncode if done else -1
                    if run:  # run 0 warms caches and stamps
                        times[i].append((time.perf_counter() - start) * 1000)
            walls = [max(times[i][r] for i in times) for r in range(args.runs)]
            print(f"{name + ' (' + scenario.event + ')':<52} {percentile(walls, .5):>7.0f} "
                  f"{percentile(walls, .95):>7.0f}")
            for i, entry in enumerate(entries):
                print(f"  {label_of(entry['command']):<50} {percentile(times[i], .5):>7.0f} "
                      f"{percentile(times[i], .95):>7.0f}  {codes.get(i)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
