"""The repository's `.afkv2/config.json`: one copy from v1, and the ownership block.

The config reader decides the format: a required `spec_folder`, an optional
`tracker` object with a `kind`, an optional `ownership` object with `own` and
`shared` lists. The v1 config is opened for reading only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath

from places import Places, write_atomic
import setup_v1_facts

AFKV2_CONFIG = (".afkv2", "config.json")
TRACKER_KINDS = ("jira", "github-issues")  # the kinds the config reader accepts
FORGE_KINDS = ("github", "gitlab")
OWNERSHIP_GRADES = ("own", "shared")
WORK_ID = "{workId}"
V1_SPEC_SECTION, V1_SPEC_KEY = "repo-files", "spec-dir"

_TOP_KEY = re.compile(rb"^([A-Za-z0-9_.-]+):(.*)$")
_SECTION_KEY = re.compile(rb"^  ([A-Za-z0-9_.-]+):(.*)$")


def v1_config(repo: Path) -> Path:
    return repo.joinpath(*setup_v1_facts.CONFIG_PATH)


def afkv2_config(repo: Path) -> Path:
    return repo.joinpath(*AFKV2_CONFIG)


def _refused(code: str, reason: str) -> dict:
    return {"ok": False, "error": {"code": code, "reason": reason}}


# ------------------------------------------------------------------ v1 values

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
        elif not line.startswith(b"#"):
            current = None
    return blocks


def _plain(value: bytes) -> str:
    text = value.strip().decode("utf-8")
    if text[:1] in ("'", '"'):
        return text[1:].split(text[0], 1)[0]
    return re.split(r"(?:^|\s)#", text, maxsplit=1)[0].strip()


def _scalar(block: bytes) -> str:
    return _plain(_TOP_KEY.match(block.splitlines()[0]).group(2))


def _section_scalars(block: bytes | None) -> dict[str, str]:
    """The first-level `key: value` lines of a section; a nested map or a list is left out."""
    found = {}
    for line in (block or b"").splitlines()[1:]:
        match = _SECTION_KEY.match(line)
        if match and _plain(match.group(2)):
            found[match.group(1).decode("utf-8")] = _plain(match.group(2))
    return found


def _folder_problem(value: object) -> str | None:
    """Why the config reader would refuse this `spec_folder`, on any system."""
    if not isinstance(value, str) or not value.strip():
        return "a non-empty folder path relative to the repository root is required"
    for flavour in (PurePosixPath, PureWindowsPath):
        path = flavour(value)
        if path.anchor or ".." in path.parts:
            return f"{value!r} must stay inside the repository root"
    if "{" in value or "}" in value:
        return f"{value!r} holds a template field"
    return None


def _from_template(template: str) -> str:
    """Skills add the ticket folder to `spec_folder`, so a last `{workId}` part goes."""
    parts = template.replace("\\", "/").rstrip("/").split("/")
    return "/".join(parts[:-1] if parts[-1] == WORK_ID else parts)


def _v1_values(repo: Path) -> dict:
    """The values v1 holds that afkv2 reads; a kind afkv2 has no port for is left out."""
    source = v1_config(repo)
    if not source.is_file():
        return {}
    blocks = _blocks(source.read_bytes())
    values: dict = {}
    template = _section_scalars(blocks.get(V1_SPEC_SECTION)).get(V1_SPEC_KEY)
    if template is not None:
        values["spec_folder"] = _from_template(template)
    tracker = _scalar(blocks["tracker"]) if "tracker" in blocks else None
    if tracker in TRACKER_KINDS:
        values["tracker"] = {**_section_scalars(blocks.get(tracker)), "kind": tracker}
    forge = _scalar(blocks["forge"]) if "forge" in blocks else None
    if forge in FORGE_KINDS:
        values["forge"] = forge
    return values


def copy_plan(repo: Path) -> dict:
    """What a copy would bring over; read only."""
    if not v1_config(repo).is_file():
        return {"v1_config": False}
    values = _v1_values(repo)
    keys = [key for key in values if key != "spec_folder" or not _folder_problem(values[key])]
    return {"v1_config": True, "keys": keys, "done": afkv2_config(repo).exists()}


# ----------------------------------------------------------------- the config

def _load(target: Path) -> dict:
    config = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"{target} must hold one JSON object")
    return config


def _write(target: Path, config: dict) -> None:
    write_atomic(target, (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def spec_folder_state(repo: Path, given: str | None = None) -> dict:
    """The `spec_folder` value and its source: the config, v1, then the developer's answer."""
    target = afkv2_config(repo)
    if target.exists() and _load(target).get("spec_folder"):
        return {"value": _load(target)["spec_folder"], "source": "config"}
    v1_value = _v1_values(repo).get("spec_folder")
    if v1_value is not None and not _folder_problem(v1_value):
        return {"value": v1_value, "source": "v1"}
    if given is not None:
        value = given.replace("\\", "/").strip()
        problem = _folder_problem(value)
        if problem:
            return {"value": None, "source": None, "code": "bad-spec-folder", "reason": f"spec_folder: {problem}"}
        return {"value": value, "source": "developer"}
    why = f"; the v1 value {v1_value!r} cannot be used" if v1_value is not None else ""
    return {"value": None, "source": None, "code": "no-spec-folder",
            "reason": f"the repository config needs a spec_folder{why}: ask the developer, then pass --spec-folder"}


def write_config(repo: Path, given: str | None = None, with_v1: bool = True) -> dict:
    """Write the config once, with its required `spec_folder`; an existing value is kept."""
    target = afkv2_config(repo)
    existing = _load(target) if target.exists() else {}
    if existing.get("spec_folder"):
        return {"ok": True, "action": "exists", "path": str(target)}
    spec = spec_folder_state(repo, given)
    if spec["value"] is None:
        return _refused(spec["code"], spec["reason"])
    copied = {k: v for k, v in _v1_values(repo).items() if k != "spec_folder"} if with_v1 else {}
    _write(target, {**copied, **existing, "spec_folder": spec["value"]})
    answer = {"ok": True, "action": "copied" if v1_config(repo).is_file() and with_v1 else "written",
              "spec_folder": spec["value"], "spec_folder_source": spec["source"], "path": str(target)}
    return answer | ({"keys": ["spec_folder", *copied]} if copied else {})


# ---------------------------------------------------------------- ownership

def ownership_state(repo: Path, places: Places) -> str:
    target = afkv2_config(repo)
    if target.exists() and "ownership" in _load(target):
        return "set"
    if places.ownership_skips.exists():
        skipped = places.ownership_skips.read_text(encoding="utf-8").splitlines()
        if str(repo.resolve()) in skipped:
            return "skipped"
    return "missing"


def write_ownership(repo: Path, places: Places, own: list[str], shared: list[str]) -> dict:
    state = ownership_state(repo, places)
    if state == "set":
        return _refused("ownership-set", "the ownership block exists; edit it by hand")
    if not own and not shared:
        return _refused("empty", "give at least one path")
    if not all(glob.strip() for glob in [*own, *shared]):
        return _refused("bad-glob", "a path glob cannot be blank")
    target = afkv2_config(repo)
    config = _load(target) if target.exists() else {}
    if not config.get("spec_folder"):
        spec = spec_folder_state(repo)
        if spec["value"] is None:
            return _refused(spec["code"], spec["reason"])
        config["spec_folder"] = spec["value"]
    grades = dict(zip(OWNERSHIP_GRADES, (own, shared)))
    _write(target, {**config, "ownership": {grade: globs for grade, globs in grades.items() if globs}})
    return {"ok": True, "action": "written", "path": str(target)}


def record_ownership_skip(repo: Path, places: Places) -> dict:
    if ownership_state(repo, places) != "missing":
        return {"ok": True, "action": "unchanged"}
    places.ownership_skips.parent.mkdir(parents=True, exist_ok=True)
    with places.ownership_skips.open("a", encoding="utf-8") as handle:
        handle.write(str(repo.resolve()) + "\n")
    return {"ok": True, "action": "skipped"}
