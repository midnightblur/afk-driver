#!/usr/bin/env python3
"""Set Claude Code's project-instructions mode to read AGENTS.md files too.

    set_instruction_files.py [settings.json] [--check]

Merges exactly pluginConfigs."agents-md@builtin".options.instructionFiles =
"claude-md-and-agents-md" into the Claude settings file. Every other key and
the file's existing indentation are preserved where feasible. Idempotent:
already set means no write and no backup. Tolerant of a missing file or missing
parent objects. Writes a timestamped `.bak-<UTC>` before any change.

Path resolution when no path argument: $CLAUDE_CONFIG_DIR/settings.json, else
~/.claude/settings.json.

--check: exit 0 when already set to the value, 1 otherwise; never writes.
Exit 2 on argv/JSON-shape errors (a settings file that is not a JSON object, or
a non-object parent on the merge path).
"""
import json
import os
import sys
import time
from pathlib import Path

PLUGIN = "agents-md@builtin"
VALUE = "claude-md-and-agents-md"


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def resolve_path(argv):
    args = [a for a in argv[1:] if a != "--check"]
    if len(args) > 1:
        die("usage: set_instruction_files.py [settings.json] [--check]")
    if args:
        return Path(args[0])
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base) / "settings.json"


def detect_indent(text):
    for ln in text.splitlines():
        stripped = ln.lstrip(" ")
        if stripped and 0 < len(ln) - len(stripped):
            return len(ln) - len(stripped)
    return 2


def current_value(data):
    try:
        return data["pluginConfigs"][PLUGIN]["options"]["instructionFiles"]
    except (KeyError, TypeError):
        return None


def child_object(parent, key, path):
    """setdefault a dict child; abort if the existing value is not an object."""
    if key in parent and not isinstance(parent[key], dict):
        die("not a JSON object at .%s in %s; refusing to overwrite" % (key, path))
    return parent.setdefault(key, {})


def main():
    check = "--check" in sys.argv
    path = resolve_path(sys.argv)
    text = ""
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text) if text.strip() else {}
        except ValueError:
            die("not valid JSON: %s" % path)
    else:
        data = {}
    if not isinstance(data, dict):
        die("top-level JSON is not an object: %s" % path)

    if current_value(data) == VALUE:
        if not check:
            print("instructionFiles already %s in %s" % (VALUE, path))
        sys.exit(0)
    if check:
        sys.exit(1)

    opts = child_object(
        child_object(child_object(data, "pluginConfigs", path), PLUGIN, path),
        "options", path)
    opts["instructionFiles"] = VALUE

    indent = detect_indent(text) if text.strip() else 2
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(path.name + ".bak-" + time.strftime("%Y%m%d%H%M%SZ", time.gmtime()))
        backup.write_text(text, encoding="utf-8")
    path.write_text(json.dumps(data, indent=indent) + "\n", encoding="utf-8")
    print("set instructionFiles=%s in %s" % (VALUE, path))


if __name__ == "__main__":
    main()
