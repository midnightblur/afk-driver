"""The repository's `.afkv2` config: one copy from v1, and the ownership block.

The v1 config is opened for reading only. A copied value is moved as its
whole top-level block, byte for byte, so its YAML stays as v1 wrote it.
"""

from __future__ import annotations

import re
from pathlib import Path

from places import Places, write_atomic
import setup_v1_facts

AFKV2_CONFIG = (".afkv2", "config.yaml")
# Scalar keys copied; each value also names a section that is copied with it.
KIND_KEYS = ("tracker", "forge", "notes")
COPIED_SECTIONS = ("git",)
HEADER = b"# afkv2 repository config.\n"

_TOP_KEY = re.compile(rb"^([A-Za-z0-9_.-]+):(.*)$")


def v1_config(repo: Path) -> Path:
    return repo.joinpath(*setup_v1_facts.CONFIG_PATH)


def afkv2_config(repo: Path) -> Path:
    return repo.joinpath(*AFKV2_CONFIG)


def _blocks(text: bytes) -> dict[str, bytes]:
    """Top-level key -> its block: the key line plus the indented lines under it."""
    blocks: dict[str, bytes] = {}
    current = None
    for line in text.splitlines(keepends=True):
        match = _TOP_KEY.match(line)
        if match:
            current = match.group(1).decode("utf-8")
            blocks[current] = line
        elif current and (line[:1] in (b" ", b"\t") or line.startswith(b"- ") or not line.strip()):
            blocks[current] += line
        elif line.startswith(b"#"):
            continue
        else:
            current = None
    return {k: v.rstrip(b"\r\n") + _eol(v) for k, v in blocks.items()}


def _eol(text: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in text else b"\n"


def _scalar(block: bytes) -> str:
    value = block.split(b"\n", 1)[0].split(b":", 1)[1].strip().decode("utf-8")
    if value[:1] in ("'", '"'):
        return value[1:].split(value[0], 1)[0]
    return re.split(r"\s#", value, maxsplit=1)[0].strip()


def copy_plan(repo: Path) -> dict:
    """What a copy would bring over; read only."""
    source = v1_config(repo)
    if not source.is_file():
        return {"v1_config": False}
    blocks = _blocks(source.read_bytes())
    keys = [k for k in KIND_KEYS if k in blocks]
    keys += [s for s in (_scalar(blocks[k]) for k in list(keys)) if s in blocks and s not in keys]
    keys += [s for s in COPIED_SECTIONS if s in blocks and s not in keys]
    return {"v1_config": True, "keys": keys, "done": afkv2_config(repo).exists(),
            "_blocks": {k: blocks[k] for k in keys}}


def copy_v1_config(repo: Path) -> dict:
    """Copy the needed v1 values into `.afkv2` once; an existing file is kept."""
    plan = copy_plan(repo)
    if not plan["v1_config"]:
        return {"ok": True, "action": "no-v1-config"}
    target = afkv2_config(repo)
    if target.exists():
        return {"ok": True, "action": "exists", "path": str(target)}
    source = v1_config(repo).read_bytes()
    body = HEADER.replace(b"\n", _eol(source)) + b"".join(plan["_blocks"].values())
    write_atomic(target, body)
    return {"ok": True, "action": "copied", "keys": plan["keys"], "path": str(target)}


# ---------------------------------------------------------------- ownership

def ownership_state(repo: Path, places: Places) -> str:
    target = afkv2_config(repo)
    if target.exists() and "ownership" in _blocks(target.read_bytes()):
        return "set"
    if places.ownership_skips.exists():
        skipped = places.ownership_skips.read_text(encoding="utf-8").splitlines()
        if str(repo.resolve()) in skipped:
            return "skipped"
    return "missing"


def _quote(glob: str) -> str:
    return "'" + glob.replace("'", "''") + "'"


def write_ownership(repo: Path, places: Places, own: list[str], shared: list[str]) -> dict:
    state = ownership_state(repo, places)
    if state == "set":
        return {"ok": False, "error": {"code": "ownership-set",
                                       "reason": "the ownership block exists; edit it by hand"}}
    if not own and not shared:
        return {"ok": False, "error": {"code": "empty", "reason": "give at least one path"}}
    lines = ["ownership:"]
    for grade, globs in (("own", own), ("shared", shared)):
        if globs:
            lines.append(f"  {grade}:")
            lines += [f"    - {_quote(g)}" for g in globs]
    target = afkv2_config(repo)
    old = target.read_bytes() if target.exists() else HEADER
    eol = _eol(old)
    sep = b"" if old.endswith(b"\n") else eol
    write_atomic(target, old + sep + eol.join(line.encode("utf-8") for line in lines) + eol)
    return {"ok": True, "action": "written", "path": str(target)}


def record_ownership_skip(repo: Path, places: Places) -> dict:
    if ownership_state(repo, places) != "missing":
        return {"ok": True, "action": "unchanged"}
    places.ownership_skips.parent.mkdir(parents=True, exist_ok=True)
    with places.ownership_skips.open("a", encoding="utf-8") as handle:
        handle.write(str(repo.resolve()) + "\n")
    return {"ok": True, "action": "skipped"}
