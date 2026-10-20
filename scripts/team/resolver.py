"""The pattern resolver: turns the picked patterns into one checked team, written once per run.

`resolve_pattern` takes the patterns of a stage map entry or the human's pick (one name or a list of names),
or a one-off pattern in the field shape of a record. It reads built-in records (BUILTIN_FILES, beside this
file) and the saved patterns the configuration reader has validated, follows includes by name, and flattens
the combination into one team before any agent starts. Included steps follow the includer's own steps, in
includes order, depth first, each named pattern-name/step-name; roles merge by name. A list of 2 or more names
combines as if a pattern with no steps of its own included them. Each debate step with no hub in its pattern
gets the moderator role the resolver adds, whose charter part is MODERATOR_PART. Every role gets 2 implied
edges, to its report target and back, kind message; an empty report target is the agent that asked.

Every refusal raises `PatternRefused` (exit code 2 on the command line) and starts nothing. The resolved
pattern file `<root>/<feature>/pattern.json` carries no charter: `Resolution.charters` holds each role's
charter text, the pattern part of every combined pattern with roles in flattening order, then the role's part.
Record fields, edge and step entries, and the pattern standard: patterns/STANDARD.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from team.manifest import LIFESPANS  # noqa: E402

PATTERNS_DIR = Path(__file__).resolve().parent / "patterns"
BUILTIN_FILES = ("BP-1-solo.json", "BP-2-debate.json", "BP-3-build-verify.json",
                 "BP-4-review-panel.json", "BP-5-afk-lite.json")
MODERATOR_PART = "moderator.md"
MODERATOR = "moderator"
SCHEMA_VERSIONS = (1,)
RECORD_VERSIONS = (1,)
FORMAT_VERSION = 1
KINDS = ("message", "finished", "parked", "exited", "start-request")
ABILITIES = ("worker-to-contact", "worker-to-worker", "exit-signal", "limit-signal")
RECORD_KEYS = {"name", "description", "charter", "schema-version", "record-version",
               "roles", "edges", "steps", "includes"}
ROLE_KEYS = {"model", "lifespan", "count", "report-target", "hub", "charter"}
EDGE_KEYS = {"from", "to", "kinds"}
STEP_KEYS = {"name", "roles", "debate"}
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class PatternRefused(Exception):
    """A pattern that must not start: the message names the role, ability, pattern or version."""

    exit_code = 2


@dataclass(frozen=True)
class Resolution:
    path: Path
    pattern: dict
    charters: dict


def resolved_path(root: str | os.PathLike, feature: str) -> Path:
    """The run's one resolved pattern file under the ignored agent directory `root`."""
    if not isinstance(feature, str) or feature in ("", ".", "..") or any(c in feature for c in "/\\:\0"):
        raise PatternRefused(f"unsafe feature identifier {feature!r}: a non-empty name without path separators")
    return Path(root) / feature / "pattern.json"


def builtin_records() -> dict:
    """Every built-in record by pattern name, read from its file in BUILTIN_FILES."""
    records = {}
    for file in BUILTIN_FILES:
        record = json.loads((PATTERNS_DIR / file).read_text(encoding="utf-8"))
        records[record["name"]] = record
    return records


def _text(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _whole(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _role_name(pattern: str, value: object, what: str) -> str:
    if not _text(value) or value in (".", "..") or any(c in value for c in "/\\:\0"):
        raise PatternRefused(f"pattern {pattern}: {what} {value!r} is not a role name")
    return value


def _check_record(name: str, record: object, source: str) -> dict:
    """One record's own fields; returns it with every default filled. Refuses with the field named."""
    if not isinstance(record, dict):
        raise PatternRefused(f"pattern {name}: must be a JSON object")
    unknown = sorted(set(record) - RECORD_KEYS)
    if unknown:
        raise PatternRefused(f"pattern {name}: unknown field {', '.join(unknown)}")
    if record.get("name", name) != name:
        raise PatternRefused(f"pattern {name}: its name field says {record.get('name')!r}")
    schema = record.get("schema-version", 1)
    if not _whole(schema) or schema not in SCHEMA_VERSIONS:
        raise PatternRefused(f"pattern {name}: unknown schema version {schema!r}")
    version = record.get("record-version", 1 if source == "saved" else None)
    if source != "one-off" and (not _whole(version) or version not in RECORD_VERSIONS):
        raise PatternRefused(f"pattern {name}: unknown record version {version!r}")
    roles = record.get("roles") or {}
    if not isinstance(roles, dict):
        raise PatternRefused(f"pattern {name}: roles must be a map of role name to role")
    if roles and not _text(record.get("charter")):
        raise PatternRefused(f"pattern {name}: its charter pattern part is missing or empty")
    checked_roles = {}
    for role, fields in roles.items():
        _role_name(name, role, "role")
        checked_roles[role] = _check_role(name, role, fields)
    hubs = [role for role, fields in checked_roles.items() if fields["hub"]]
    if len(hubs) > 1:
        raise PatternRefused(f"pattern {name}: {len(hubs)} hubs ({', '.join(hubs)}); at most 1")
    for role, fields in checked_roles.items():
        target = fields["report-target"]
        if target and target not in checked_roles:
            raise PatternRefused(f"pattern {name}: role {role} reports to {target!r}, a role it does not define")
    edges = [_check_edge(name, edge, checked_roles) for edge in _entries(name, record, "edges", required=False)]
    steps = [_check_step(name, step, checked_roles) for step in _entries(name, record, "steps", required=True)]
    seen: set[str] = set()
    for step in steps:
        if step["name"] in seen:
            raise PatternRefused(f"pattern {name}: 2 steps named {step['name']}")
        seen.add(step["name"])
    includes = record.get("includes") or []
    if not isinstance(includes, list) or not all(_text(item) for item in includes):
        raise PatternRefused(f"pattern {name}: includes must be a list of pattern names")
    return {"name": name, "source": source, "record-version": version if source != "one-off" else None,
            "schema-version": schema, "charter": record.get("charter") if roles else None,
            "roles": checked_roles, "edges": edges, "steps": steps, "includes": list(includes)}


def _check_role(pattern: str, role: str, fields: object) -> dict:
    where = f"pattern {pattern}: role {role}"
    if not isinstance(fields, dict):
        raise PatternRefused(f"{where} must be a map of role fields")
    unknown = sorted(set(fields) - ROLE_KEYS)
    if unknown:
        raise PatternRefused(f"{where}: unknown field {', '.join(unknown)}")
    if not _text(fields.get("charter")):
        raise PatternRefused(f"{where}: its charter part is missing or empty")
    if not _text(fields.get("model")):
        raise PatternRefused(f"{where}: model is missing or empty")
    if fields.get("lifespan") not in LIFESPANS:
        raise PatternRefused(f"{where}: lifespan {fields.get('lifespan')!r} is not one of {', '.join(LIFESPANS)}")
    count = fields.get("count", 1)
    if not _whole(count) or count < 1:
        raise PatternRefused(f"{where}: count {count!r} is not a whole number of 1 or more")
    hub = fields.get("hub", False)
    if not isinstance(hub, bool):
        raise PatternRefused(f"{where}: hub {hub!r} is not true or false")
    target = fields.get("report-target") or ""
    if target:
        _role_name(pattern, target, f"role {role}'s report target")
    return {"model": fields["model"], "lifespan": fields["lifespan"], "count": count,
            "report-target": target, "hub": hub, "charter": fields["charter"]}


def _entries(pattern: str, record: dict, key: str, required: bool) -> list:
    value = record.get(key)
    if value is None and not required:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value) or (required and not value):
        need = "a non-empty list" if required else "a list"
        raise PatternRefused(f"pattern {pattern}: {key} must be {need} of maps")
    return value


def _check_edge(pattern: str, edge: dict, roles: dict) -> dict:
    unknown = sorted(set(edge) - EDGE_KEYS)
    if unknown:
        raise PatternRefused(f"pattern {pattern}: an edge has unknown field {', '.join(unknown)}")
    for end in ("from", "to"):
        if edge.get(end) not in roles:
            raise PatternRefused(f"pattern {pattern}: an edge's {end} {edge.get(end)!r} names a role it does not define")
    kinds = edge.get("kinds")
    if not isinstance(kinds, list) or not kinds or any(kind not in KINDS for kind in kinds):
        raise PatternRefused(f"pattern {pattern}: edge {edge['from']} -> {edge['to']} kinds {kinds!r} "
                             f"must be a non-empty list of {', '.join(KINDS)}")
    return {"from": edge["from"], "to": edge["to"], "kinds": list(kinds)}


def _check_step(pattern: str, step: dict, roles: dict) -> dict:
    unknown = sorted(set(step) - STEP_KEYS)
    if unknown:
        raise PatternRefused(f"pattern {pattern}: a step has unknown field {', '.join(unknown)}")
    if not _text(step.get("name")):
        raise PatternRefused(f"pattern {pattern}: a step has no name")
    starts = step.get("roles", [])
    if not isinstance(starts, list):
        raise PatternRefused(f"pattern {pattern}: step {step['name']} roles must be a list")
    for role in starts:
        if role not in roles:
            raise PatternRefused(f"pattern {pattern}: step {step['name']} starts {role!r}, a role it does not define")
    debate = step.get("debate", False)
    if not isinstance(debate, bool):
        raise PatternRefused(f"pattern {pattern}: step {step['name']} debate {debate!r} is not true or false")
    return {"name": step["name"], "roles": list(starts), "debate": debate}


class _Flattener:
    """Walks the include graph depth first and folds every reached record into one team."""

    def __init__(self, lookup: Callable[[str], dict], moderator: dict):
        self.lookup = lookup
        self.moderator = moderator
        self.roles: dict = {}
        self.owner: dict = {}
        self.edges: list = []
        self.steps: list = []
        self.parts: list = []
        self.sources: list = []
        self.reached: set = set()

    def walk(self, record: dict, qualify: bool, stack: tuple) -> None:
        name = record["name"]
        if name in stack:
            raise PatternRefused(f"pattern {name} includes itself: {' -> '.join((*stack, name))}")
        if name in self.reached:
            raise PatternRefused(f"pattern {name} is reached twice in one combination")
        self.reached.add(name)
        self.sources.append({"name": name, "record-version": record["record-version"], "source": record["source"]})
        if record["charter"]:
            self.parts.append(record["charter"])
        hub = next((role for role, fields in record["roles"].items() if fields["hub"]), None)
        for role, fields in record["roles"].items():
            self.merge(role, fields, name)
        self.edges.extend(record["edges"])
        for step in record["steps"]:
            starts = list(step["roles"])
            if step["debate"] and hub is None:
                self.merge(MODERATOR, self.moderator, name)
                for role in starts:
                    if role != MODERATOR:
                        self.edges.append({"from": MODERATOR, "to": role, "kinds": ["message"]})
                        self.edges.append({"from": role, "to": MODERATOR, "kinds": ["message"]})
                starts = [*starts, MODERATOR] if MODERATOR not in starts else starts
            self.steps.append({"name": f"{name}/{step['name']}" if qualify else step["name"],
                               "roles": starts, "debate": step["debate"],
                               "moderator": (hub or MODERATOR) if step["debate"] else None})
        for include in record["includes"]:
            self.walk(self.lookup(include), True, (*stack, name))

    def merge(self, role: str, fields: dict, pattern: str) -> None:
        known = self.roles.get(role)
        if known is None:
            self.roles[role] = fields
            self.owner[role] = pattern
        elif known != fields:
            raise PatternRefused(f"role {role} has 2 different definitions, in patterns {self.owner[role]} and {pattern}")


def _implied_edges(roles: dict) -> list:
    implied = []
    for role, fields in roles.items():
        target = fields["report-target"]
        implied.append({"from": role, "to": target, "kinds": ["message"], "implied": True})
        implied.append({"from": target, "to": role, "kinds": ["message"], "implied": True})
    return implied


def _needs(roles: dict, edges: list) -> list:
    if not roles:
        return []
    needs = ["worker-to-contact", "exit-signal", "limit-signal"]
    if any(edge["from"] in roles and edge["to"] in roles for edge in edges):
        needs.insert(1, "worker-to-worker")
    return needs


def _moderator(model: str) -> dict:
    return {"model": model, "lifespan": "Step", "count": 1, "report-target": "", "hub": False,
            "charter": (PATTERNS_DIR / MODERATOR_PART).read_text(encoding="utf-8")}


def resolve_pattern(root: str | os.PathLike, feature: str, pick: str | list | dict, *, session: str,
                    can_fill: Callable[[str], bool], abilities: Iterable[str], moderator_model: str,
                    saved: Mapping[str, dict] | None = None, now: datetime | None = None) -> Resolution:
    """Resolve `pick` into the run's one resolved pattern file, or raise `PatternRefused` and start nothing.

    `pick` is one pattern name, a list of names (a stage map entry or the human's pick), or a one-off pattern
    as a map in the field shape of a record. `saved` holds the configuration's validated saved patterns;
    `can_fill(model)` says whether a role on that model can be filled; `abilities` are the transport's
    messaging abilities (ABILITIES); `moderator_model` is the model of a moderator the resolver adds.
    """
    if not _text(session):
        raise PatternRefused("the owning contact session is missing or empty")
    if not _text(moderator_model):
        raise PatternRefused("the added moderator's model is missing or empty")
    if saved is not None and not isinstance(saved, Mapping):
        raise PatternRefused("the saved patterns must be a map of pattern name to pattern")
    builtin = builtin_records()
    saved = dict(saved or {})
    checked: dict = {}

    def lookup(name: str) -> dict:
        if name not in checked:
            if name in builtin:
                checked[name] = _check_record(name, builtin[name], "built-in")
            elif name in saved:
                checked[name] = _check_record(name, saved[name], "saved")
            else:
                raise PatternRefused(f"{name!r} names no pattern")
        return checked[name]

    flat = _Flattener(lookup, _moderator(moderator_model))
    if isinstance(pick, dict):
        name = pick.get("name")
        if not _text(name):
            raise PatternRefused("the one-off pattern has no name")
        if name in builtin or name in saved:
            raise PatternRefused(f"one-off pattern {name}: the name is a built-in or saved pattern's")
        checked[name] = _check_record(name, pick, "one-off")
        flat.walk(checked[name], False, ())
        top = {"pattern-name": name, "record-version": None, "source": "one-off"}
    else:
        names = [pick] if isinstance(pick, str) else pick
        if not isinstance(names, list) or not names or not all(_text(item) for item in names):
            raise PatternRefused("the pick must be one pattern name, a non-empty list of names, or a one-off pattern")
        for item in names:
            flat.walk(lookup(item), len(names) > 1, ())
        first = checked[names[0]]
        top = ({"pattern-name": names[0], "record-version": first["record-version"], "source": first["source"]}
               if len(names) == 1 else {"pattern-name": "+".join(names), "record-version": None, "source": "combined"})

    for step in flat.steps:
        if step["moderator"] and not can_fill(flat.roles[step["moderator"]]["model"]):
            raise PatternRefused(f"debate {step['name']}: its moderator {step['moderator']} cannot be filled "
                                 f"(model {flat.roles[step['moderator']]['model']})")
    for role, fields in flat.roles.items():
        if not can_fill(fields["model"]):
            raise PatternRefused(f"role {role} cannot be filled (model {fields['model']})")
    edges = flat.edges + _implied_edges(flat.roles)
    have = set(abilities)
    for need in _needs(flat.roles, edges):
        if need not in have:
            raise PatternRefused(f"the pattern needs messaging ability {need}, which the transport lacks")

    charters = {role: "\n\n".join([*flat.parts, fields["charter"]]) for role, fields in flat.roles.items()}
    team = {"roles": {role: {k: v for k, v in fields.items() if k != "charter"} for role, fields in flat.roles.items()},
            "edges": edges, "steps": flat.steps}
    created = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime(_TIME_FORMAT)
    pattern = {"format_version": FORMAT_VERSION, **top, "schema-version": SCHEMA_VERSIONS[-1],
               "sources": flat.sources, "team": team, "created-at": created, "owning-session": session}
    path = resolved_path(root, feature)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        tmp.write_text(json.dumps(pattern, indent=1), "utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return Resolution(path, pattern, charters)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve team patterns into the run's resolved pattern file.")
    parser.add_argument("--root", required=True, help="the ignored agent directory")
    parser.add_argument("--feature", required=True)
    parser.add_argument("--session", required=True, help="the owning contact session")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pattern", action="append", help="a pattern name; repeat to combine in order")
    group.add_argument("--one-off", type=Path, help="a JSON file holding a one-off pattern")
    parser.add_argument("--saved", type=Path, help="a JSON file holding the saved patterns map")
    parser.add_argument("--model", action="append", default=[], help="a model a role can be filled on")
    parser.add_argument("--ability", action="append", default=[], help="a messaging ability of the transport")
    parser.add_argument("--moderator-model", required=True)
    args = parser.parse_args(argv)
    try:
        pick = json.loads(args.one_off.read_text(encoding="utf-8")) if args.one_off else args.pattern
        if args.one_off and not isinstance(pick, dict):
            raise PatternRefused("the one-off pattern file must hold one JSON object")
        saved = json.loads(args.saved.read_text(encoding="utf-8")) if args.saved else None
        result = resolve_pattern(args.root, args.feature, pick, session=args.session,
                                 can_fill=set(args.model).__contains__, abilities=args.ability,
                                 moderator_model=args.moderator_model, saved=saved)
    except PatternRefused as refusal:
        print(f"resolver: refused: {refusal}", file=sys.stderr)
        return PatternRefused.exit_code
    except (OSError, ValueError) as exc:
        print(f"resolver: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"path": str(result.path), "charters": result.charters}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
