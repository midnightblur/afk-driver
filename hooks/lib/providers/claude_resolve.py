#!/usr/bin/env python3
"""Resolve the Claude provider's installed plugin root, and its enablement,
without guessing.

Usage: claude_resolve.py [--enablement]

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

Root: the native ``CLAUDE_PLUGIN_ROOT`` env var, trusted only when
``PLUGIN_ROOT`` is absent — Codex also sets ``CLAUDE_PLUGIN_ROOT`` as a
compatibility alias for its own root, so its presence alone does not prove a
Claude install exists; ``PLUGIN_ROOT`` is Codex's own native signal and
nothing else sets it. Falls back to
``${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/installed_plugins.json``, entry
``afk@afk-toolkit`` — read from a top-level ``plugins`` wrapper or, failing
that, from the top level directly (both shapes have been observed on real
installs) — first entry's ``installPath``.

Enablement: ``${CLAUDE_CONFIG_DIR:-~/.claude}/settings.json``'s
``enabledPlugins["afk@afk-toolkit"]`` — ``true`` is ``enabled``, ``false`` is
``disabled``, and a missing key or file is ``absent``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

PLUGIN_ID = "afk@afk-toolkit"


def _verified(root_text: str | None) -> str | None:
    if not root_text:
        return None
    root = Path(root_text)
    if root.is_dir() and (root / "BEHAVIORS.md").is_file():
        return str(root)
    return None


def _entries(data: object) -> list:
    if not isinstance(data, dict):
        return []
    plugins = data.get("plugins")
    if isinstance(plugins, dict) and PLUGIN_ID in plugins:
        return plugins[PLUGIN_ID] or []
    if PLUGIN_ID in data:
        return data[PLUGIN_ID] or []
    return []


def _settings_path() -> Path:
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(config_dir) / "settings.json"


def enablement() -> str:
    settings = _settings_path()
    if not settings.is_file():
        return "absent"
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "absent"
    if not isinstance(data, dict):
        return "absent"
    enabled_plugins = data.get("enabledPlugins")
    if not isinstance(enabled_plugins, dict) or PLUGIN_ID not in enabled_plugins:
        return "absent"
    return "enabled" if enabled_plugins[PLUGIN_ID] else "disabled"


def resolve() -> str | None:
    if not os.environ.get("PLUGIN_ROOT"):
        verified = _verified(os.environ.get("CLAUDE_PLUGIN_ROOT"))
        if verified:
            return verified
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    registry = Path(config_dir) / "plugins" / "installed_plugins.json"
    if not registry.is_file():
        return None
    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for entry in _entries(data):
        if isinstance(entry, dict):
            verified = _verified(entry.get("installPath"))
            if verified:
                return verified
    return None


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
