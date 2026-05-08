"""One-shot: backfill CLAUDE.md files from main checkout into existing worktrees.

Reuses worktree_manager._copy_claude_md_recursive (skip-if-present semantics
so committed CLAUDE.md already on disk stays untouched and the worktree
remains clean). Reports per-worktree what got filled in.

Run from any cwd:
    python scripts/backfill_claude_md.py [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from afk_driver import worktree_manager as wm  # noqa: E402

WORKTREE_ROOTS = [
    Path(r"C:\Users\mvu\.afk-driver\worktrees"),
    Path(r"C:\Users\mvu\core-services-worktrees"),
]


def main_repo_for(worktree: Path) -> Path | None:
    proc = subprocess.run(
        ["git", "worktree", "list"],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return None
    first_line = proc.stdout.splitlines()[0] if proc.stdout.strip() else ""
    parts = first_line.split()
    return Path(parts[0]) if parts else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would be copied; do not write.")
    args = ap.parse_args()

    # Track copies by monkey-patching shutil.copy2 in the worktree_manager module.
    copied: list[tuple[Path, Path]] = []
    real_copy2 = shutil.copy2

    def tracking_copy2(src, dst, *a, **kw):
        copied.append((Path(src), Path(dst)))
        if args.dry_run:
            return dst
        return real_copy2(src, dst, *a, **kw)

    wm.shutil.copy2 = tracking_copy2  # type: ignore[attr-defined]

    total_filled = 0
    for root in WORKTREE_ROOTS:
        if not root.is_dir():
            print(f"-- skip (missing root) {root}")
            continue
        for wt in sorted(root.iterdir()):
            if not wt.is_dir():
                continue
            if not (wt / ".git").exists():
                print(f"-- skip (not a worktree) {wt}")
                continue
            main = main_repo_for(wt)
            if main is None or not main.is_dir():
                print(f"-- skip (no main repo) {wt}")
                continue
            copied.clear()
            wm._copy_claude_md_recursive(main, wt)
            tag = "[dry-run]" if args.dry_run else "[copied]"
            print(f"== {wt}")
            print(f"   main = {main}")
            if copied:
                for src, dst in copied:
                    rel = dst.relative_to(wt)
                    print(f"   {tag} {rel}")
                total_filled += len(copied)
            else:
                print("   (no missing CLAUDE.md — nothing to do)")
    print(f"\nTotal: {total_filled} CLAUDE.md file(s) filled in"
          f"{' (dry-run)' if args.dry_run else ''}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
