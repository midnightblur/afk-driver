#!/usr/bin/env python3
"""Does the harness config hold a trust entry for each protected-branch hook?

    check_hook_trust.py [--config <config.toml>] [--manifest <hooks.codex.json>]

The harness trusts a plugin hook by position: a `[hooks.state."<plugin>@<marketplace>:
hooks/hooks.codex.json:<event>:<group>:<handler>"]` table carries `trusted_hash`. This reads the
shipped manifest for the position of the guard (PreToolUse), the session-end cleanup
(SessionEnd) and the session-start prune (SessionStart), then checks the config for a key at
each. A key can be stale (the hash no longer matches): only the harness can tell, so a present
key is reported as present and `/hooks` stays the place to see "need review".

Exit 0 every key present; 1 at least one missing (one `missing:` line each, plus the step);
2 no config file (the harness is not installed or never ran). Never writes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HOOKS = (("PreToolUse", "protected-branch-guard.py"),
         ("SessionEnd", "worktree-remove.sh"),
         ("SessionStart", "worktree-prune.sh"))
STEP = ("start the harness once in its terminal UI without the full-bypass flag and choose "
        "\"Trust all and continue\", or type `/hooks` and press `t`")


def positions(manifest: Path) -> list[tuple[str, int, int, str]]:
    """`(event, group, handler, script)` of each guarded hook in the shipped manifest."""
    found = []
    events = json.loads(manifest.read_text(encoding="utf-8")).get("hooks", {})
    for event, script in HOOKS:
        for group, entry in enumerate(events.get(event, [])):
            for handler, hook in enumerate(entry.get("hooks", [])):
                if script in str(hook.get("command", "")):
                    found.append((event, group, handler, script))
    return found


def plugin_name(manifest: Path) -> str:
    """The plugin's name in the codex plugin manifest beside the hooks folder, or "afk"."""
    try:
        found = json.loads((manifest.parent.parent / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        return str(found.get("name") or "afk")
    except (OSError, ValueError):
        return "afk"


def trusted(config: str, plugin: str, event: str, group: int, handler: int) -> bool:
    key = re.compile(r'^\[hooks\.state\."' + re.escape(plugin) + r'@[^"\n]*:hooks/hooks\.codex\.json:'
                     + re.escape(f"{event}:{group}:{handler}") + r'"\]', re.M)
    found = key.search(config)
    return bool(found) and "trusted_hash" in config[found.end():].split("\n[", 1)[0]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    root = Path(os.environ.get("AFK_PLUGIN_ROOT") or Path(__file__).resolve().parents[4])
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    parser.add_argument("--config", default=str(home / "config.toml"))
    parser.add_argument("--manifest", default=str(root / "hooks" / "hooks.codex.json"))
    args = parser.parse_args(argv)
    try:
        config = Path(args.config).read_text(encoding="utf-8")
    except OSError:
        print(f"no harness config at {args.config}")
        return 2
    missing = 0
    plugin = plugin_name(Path(args.manifest))
    for event, group, handler, script in positions(Path(args.manifest)):
        if not trusted(config, plugin, event, group, handler):
            missing += 1
            print(f"missing: {event}:{group}:{handler} ({script})")
    if missing:
        print(f"step: {STEP}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
