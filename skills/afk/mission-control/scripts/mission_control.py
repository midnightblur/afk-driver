#!/usr/bin/env python3
"""Mission-control renderer CLI (M5) — spec folder -> static dashboard.

Usage: mission_control.py <spec_dir> [--once] [--port PORT]

Binding contract: SDD.md (this feature's own spec folder) §3 contract table
row "MC renderer (M5)" and §8 module table row "M5 renderer". `spec_dir` is
the feature's spec folder (containing `PRD.md` / `SDD.md` / `plan/`).

`EXIT_PATH_FENCE` and `PANEL_PARSERS` are this subtask's `## Produces`
anchors, read by later subtasks (0004-mission-control-skill,
0005-preflight-skill) in this plan.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mc import server
from mc.panels import design_map, diffs, gates, progress, timeline

EXIT_OK = 0
EXIT_PATH_FENCE = 2

DEFAULT_PORT = 8420

# ADR-0007: five independent parsers behind one registry; each yields
# PanelVM | Absent(reason), never an exception (see mc/vm.py).
PANEL_PARSERS = [
    progress.parse,
    timeline.parse,
    design_map.parse,
    diffs.parse,
    gates.parse,
]


def _find_repo_root(start: Path):
    current = start
    for _ in range(64):
        if (current / ".git").exists():  # a file in worktrees, a dir in the main checkout
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def enforce_path_fence(spec_dir_arg: str) -> Path:
    """SDD §5 authz table, "MC renderer inputs" row: reject any spec-dir
    argument that does not resolve to an existing directory inside a git
    checkout, before anything else runs. Must be the very first action in
    `main` — the "nothing written" guarantee depends on no output directory
    existing yet when this raises.
    """
    spec_dir = Path(spec_dir_arg).resolve()
    if not spec_dir.is_dir():
        raise SystemExit(EXIT_PATH_FENCE)
    if _find_repo_root(spec_dir) is None:
        raise SystemExit(EXIT_PATH_FENCE)
    return spec_dir


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mission_control.py",
        description="Render the mission-control dashboard for a feature's spec/plan folder.",
    )
    parser.add_argument("spec_dir", help="path to the feature's spec folder (contains PRD.md/SDD.md/plan/)")
    parser.add_argument("--once", action="store_true", help="render once and exit (retroactive mode, AC-013)")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"serve port, 127.0.0.1 only (default {DEFAULT_PORT}); ignored with --once",
    )
    return parser


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    spec_dir = enforce_path_fence(args.spec_dir)
    out_dir = spec_dir / "plan" / "mission-control"

    if args.once:
        server.render_once(spec_dir, out_dir, PANEL_PARSERS, live_reload=False)
        return EXIT_OK

    httpd = server.watch_and_serve(spec_dir, out_dir, args.port, PANEL_PARSERS)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
