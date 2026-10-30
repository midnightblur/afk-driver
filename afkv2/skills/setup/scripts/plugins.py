"""Plugin enable state on Claude (per project) and Codex (per machine).

Claude: `enabledPlugins` in user < project < project-local settings; setup
writes only the project-local file. Both plugin ids are written there, so the
effective value is the same whether the harness merges the object per key or
replaces it whole.
Codex: `[plugins."<id>"]` tables with `enabled = true|false` in the global
`config.toml`; Codex has no enable command (`codex plugin --help`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping

from places import write_atomic
import v1_facts

NEW_NAME = "afkv2"
NAMES = (v1_facts.PLUGIN_NAME, NEW_NAME)


def plugin_name(plugin_id: str) -> str:
    return plugin_id.split("@", 1)[0]


def default_id(name: str) -> str:
    return f"{name}@{v1_facts.MARKETPLACE}"


# ------------------------------------------------------------------ Claude

def claude_layers(user_settings: Path, repo: Path) -> list[Path]:
    return [user_settings, repo / ".claude" / "settings.json", repo / ".claude" / "settings.local.json"]


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def claude_effective(user_settings: Path, repo: Path) -> dict[str, bool]:
    """plugin id -> enabled, for ids named afk or afkv2, highest layer wins."""
    effective: dict[str, bool] = {}
    for layer in claude_layers(user_settings, repo):
        for plugin_id, on in (_read_json(layer).get("enabledPlugins") or {}).items():
            if plugin_name(plugin_id) in NAMES:
                effective[plugin_id] = bool(on)
    return effective


def claude_target(user_settings: Path, repo: Path, enable: str) -> dict[str, bool]:
    """The local values that leave exactly `enable` on."""
    known = claude_effective(user_settings, repo)
    ids = {n: [i for i in known if plugin_name(i) == n] or [default_id(n)] for n in NAMES}
    wanted = {i: False for n in NAMES if n != enable for i in ids[n] if i in known}
    wanted.update({i: True for i in ids[enable]})
    return wanted


def write_claude_local(repo: Path, wanted: Mapping[str, bool]) -> bool:
    """Merge `wanted` into the local settings; False when every value is equal."""
    local = repo / ".claude" / "settings.local.json"
    data = _read_json(local)
    plugins = dict(data.get("enabledPlugins") or {})
    if all(plugins.get(k) is v for k, v in wanted.items()):
        return False
    plugins.update(wanted)
    data["enabledPlugins"] = plugins
    write_atomic(local, (json.dumps(data, indent=2) + "\n").encode("utf-8"))
    return True


def only_one_on(state: Mapping[str, bool]) -> str | None:
    """The one plugin name left on, or None when both or neither are on."""
    on = {plugin_name(i) for i, v in state.items() if v}
    return on.pop() if len(on) == 1 else None


# ------------------------------------------------------------------- Codex

_TABLE = re.compile(r'^\[plugins\."([^"]+)"\]\s*$')
_ENABLED = re.compile(r"^(\s*enabled\s*=\s*)(true|false)(\s*(#.*)?)$")


def codex_config_state(text: str) -> dict[str, bool]:
    import tomllib

    tables = tomllib.loads(text).get("plugins") or {}
    return {i: bool((t or {}).get("enabled", True)) for i, t in tables.items()
            if plugin_name(i) in NAMES}


def codex_edit(text: str, wanted: Mapping[str, bool]) -> str:
    """Set `enabled` in each wanted plugin table; lines outside stay as they are.

    A wanted table with no `enabled` line gets one under its header; a wanted
    table that does not exist is an error, because only Codex installs one.
    """
    eol = "\r\n" if "\r\n" in text else "\n"
    out: list[str] = []
    table = None
    header_at: dict[str, int] = {}
    done: set[str] = set()
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        head = _TABLE.match(body)
        if head:
            table = head.group(1)
            header_at[table] = len(out)
        elif body.startswith("["):
            table = None
        elif table in wanted and table not in done:
            match = _ENABLED.match(body)
            if match:
                value = "true" if wanted[table] else "false"
                line = match.group(1) + value + match.group(3) + line[len(body):]
                done.add(table)
        out.append(line)
    missing = [i for i in wanted if i not in header_at]
    if missing:
        raise ValueError(f"Codex has no plugin table for {', '.join(missing)}")
    for plugin_id in sorted((i for i in wanted if i not in done),
                            key=lambda i: header_at[i], reverse=True):
        value = "true" if wanted[plugin_id] else "false"
        at = header_at[plugin_id]
        if not out[at].endswith(("\n", "\r")):
            out[at] += eol
        out.insert(at + 1, f"enabled = {value}{eol}")
    return "".join(out)


def parse_codex_list(table: str) -> dict[str, bool]:
    """plugin id -> enabled, read from `codex plugin list` by its column names."""
    state: dict[str, bool] = {}
    cols = None
    for line in table.splitlines():
        if not line.strip():
            cols = None
            continue
        if cols is None:
            if "PLUGIN" in line and "STATUS" in line:
                cols = (line.find("PLUGIN"), line.find("STATUS"))
            continue
        plugin = line[cols[0]:cols[1]].strip()
        status = line[cols[1]:].split("  ")[0].strip().lower()
        if plugin_name(plugin) in NAMES:
            state[plugin] = "enabled" in status and "disabled" not in status
    return state
