#!/usr/bin/env afk-python
"""Resolve the Codex provider's installed plugin root, and its enablement,
without guessing.

Usage: codex_resolve.py [--enablement]

With no flag: prints the resolved root and exits 0 only when the root is
independently verifiable — a directory that exists and contains
``BEHAVIORS.md``. Prints nothing and exits 1 when the root cannot be
verified: the caller must then leave this provider's target unchanged rather
than install a wrong root — a provider whose root cannot be resolved
self-heals the next time it runs its own setup, in its own session, where
its native root is known.

With ``--enablement``: prints ``enabled``, ``disabled``, or ``absent`` and
always exits 0 — enablement always has a definite answer, never an
"unresolved" state the way a root does.

Root: the native ``PLUGIN_ROOT`` env var when set, else the version-cache
path Codex itself loads from. Codex names no root env var or config field for
this, so this reads the authoritative source instead: ``codex plugin
list``'s own table. Its ``afk@afk-toolkit`` row's ``VERSION`` column (located
by the header's column names, not fixed positions — column widths vary per
marketplace section) names the version Codex has loaded, and Codex always
caches a loaded version at
``${CODEX_HOME:-~/.codex}/plugins/cache/afk-toolkit/afk/<VERSION>``.
Unresolved when the ``codex`` CLI is absent, its row is missing from the
table, or that directory does not exist.

Enablement: the same row's ``STATUS`` cell (``"installed, enabled"``,
``"installed, disabled"``, or ``"not installed"``) — classified by
substring, not exact match, since only the ``enabled``/``disabled`` word
within it is load-bearing.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

PLUGIN_ID = "afk@afk-toolkit"
CODEX_CACHE_MARKETPLACE = "afk-toolkit"
CODEX_CACHE_PLUGIN = "afk"
CODEX_TABLE_COLUMNS = ("PLUGIN", "STATUS", "VERSION", "SOURCE")


def _verified(root_text: str | None) -> str | None:
    if not root_text:
        return None
    root = Path(root_text)
    if root.is_dir() and (root / "BEHAVIORS.md").is_file():
        return str(root)
    return None


def _plugin_row(table_output: str) -> dict[str, str] | None:
    """The ``afk@afk-toolkit`` row from ``codex plugin list``, as a
    column-name -> cell-text mapping.

    The output lists one table per marketplace, each with its own header and
    its own column widths (a plugin name column sized to that marketplace's
    longest name, for instance) — so column offsets are read fresh from each
    section's own header line, never reused across sections and never assumed
    to sit at a fixed position."""
    header = None
    positions: dict[str, int] | None = None
    for line in table_output.splitlines():
        if not line.strip():
            header = None
            positions = None
            continue
        if header is None:
            if all(name in line for name in CODEX_TABLE_COLUMNS):
                candidate = {name: line.find(name) for name in CODEX_TABLE_COLUMNS}
                if -1 not in candidate.values():
                    header = line
                    positions = candidate
            continue
        starts = [positions[name] for name in CODEX_TABLE_COLUMNS] + [len(line)]
        row = {
            CODEX_TABLE_COLUMNS[i]: line[starts[i] : starts[i + 1]].strip()
            for i in range(len(CODEX_TABLE_COLUMNS))
        }
        if row["PLUGIN"] != PLUGIN_ID:
            continue
        return row
    return None


def _table_output() -> str | None:
    codex_cli = shutil.which("codex")
    if not codex_cli:
        return None
    try:
        completed = subprocess.run(
            [codex_cli, "plugin", "list"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def resolve() -> str | None:
    verified = _verified(os.environ.get("PLUGIN_ROOT"))
    if verified:
        return verified
    table_output = _table_output()
    if table_output is None:
        return None
    row = _plugin_row(table_output)
    version = row["VERSION"] if row else None
    if not version:
        return None
    codex_home = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    candidate = (
        Path(codex_home) / "plugins" / "cache" / CODEX_CACHE_MARKETPLACE / CODEX_CACHE_PLUGIN / version
    )
    return _verified(str(candidate))


def _classify_status(status: str) -> str:
    lowered = status.lower()
    if "enabled" in lowered:
        return "enabled"
    if "disabled" in lowered:
        return "disabled"
    return "absent"


def enablement() -> str:
    table_output = _table_output()
    if table_output is None:
        return "absent"
    row = _plugin_row(table_output)
    if row is None:
        return "absent"
    return _classify_status(row.get("STATUS", ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--enablement", action="store_true", help="print enabled|disabled|absent instead of the root"
    )
    args = parser.parse_args(argv)
    if args.enablement:
        print(enablement())
        return 0
    root = resolve()
    if root is None:
        return 1
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
