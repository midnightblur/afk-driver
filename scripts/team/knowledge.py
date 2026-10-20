"""The knowledge store: one JSON file per entry that a team run's agents write and read during the run.

`write_entry` creates an entry unfinished; `mark_finished` is the author's stamp, on its clean exit or at the
end of a debate step; nothing else moves an entry, so an early-ended author's entry stays unfinished for ever.
`read_finished` returns only finished entries, filtered by the stages the reader may read, and returns a debate
draft only when every debater role of its work item has a finished draft (the release rule counts roles).

Layout under the caller's ignored agent directory `root`: `<root>/<feature>/knowledge/`, one file per entry named
`<YYYYMMDDTHHMMSSZ>-<author>.json`; author and time are the entry's identity. Times are UTC ISO 8601 to the
second. A file of an unknown format version is foreign: never read, never changed. Nothing here copies an entry
to any other record; cleanup deletes the store whole.
"""
from __future__ import annotations

import json
import os
import sys
import time as _clock
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping

FORMAT_VERSION = 1
KNOWN_VERSIONS = (1,)
DEBATE_STEPS = ("draft", "critique", "revision", "verdict")
VERDICTS = ("AGREE", "DISAGREE-FINAL")
FIELDS = ("author", "role", "model", "time", "ground", "stage", "body", "finished",
          "work_item", "debate_step", "verdict", "reason")
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

_REPORTED: set[tuple[str, str]] = set()


class KnowledgeError(Exception):
    """A malformed entry, an unsafe name, or a write the store cannot take."""


def _name(value: object, what: str) -> str:
    if not isinstance(value, str) or value in ("", ".", "..") or any(c in value for c in "/\\:\0"):
        raise KnowledgeError(f"unsafe {what} {value!r}: a non-empty name without path separators")
    return value


def store_path(root: str | os.PathLike, feature: str) -> Path:
    """The feature's knowledge store folder under the ignored agent directory `root`."""
    return Path(root) / _name(feature, "feature identifier") / "knowledge"


def _parse_time(value: object) -> datetime:
    try:
        parsed = datetime.strptime(value, _TIME_FORMAT) if isinstance(value, str) else None
        if parsed is not None and parsed.strftime(_TIME_FORMAT) == value:
            return parsed
    except ValueError:
        pass
    raise KnowledgeError(f"time {value!r} is not UTC ISO 8601 to the second, YYYY-MM-DDTHH:MM:SSZ")


def _entry_path(root: str | os.PathLike, feature: str, author: object, time: object) -> Path:
    stamp = _parse_time(time).strftime("%Y%m%dT%H%M%SZ")
    return store_path(root, feature) / f"{stamp}-{_name(author, 'author')}.json"


def _text(entry: dict, field: str) -> None:
    value = entry.get(field)
    if not isinstance(value, str) or value == "":
        raise KnowledgeError(f"entry field {field} must be non-empty text, got {value!r}")


def _check(entry: dict) -> dict:
    """Refuse an entry whose fields break SDD §4; returns it unchanged."""
    for field in ("author", "role", "model", "ground", "stage"):
        _text(entry, field)
    _name(entry["author"], "author")
    _parse_time(entry.get("time"))
    if not isinstance(entry.get("body"), str):
        raise KnowledgeError(f"entry field body must be text, got {entry.get('body')!r}")
    if not isinstance(entry.get("finished"), bool):
        raise KnowledgeError("entry field finished must be true or false")
    step, item = entry.get("debate_step"), entry.get("work_item")
    if step is None and item is None:
        if entry.get("verdict") is not None or entry.get("reason") is not None:
            raise KnowledgeError("verdict and reason stay empty outside a debate")
        return entry
    if step is None or item is None:
        raise KnowledgeError("a debate entry needs both a work item and a debate step; outside a debate, neither")
    _text(entry, "work_item")
    if step not in DEBATE_STEPS:
        raise KnowledgeError(f"debate step {step!r} is not one of {', '.join(DEBATE_STEPS)}")
    reason = entry.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise KnowledgeError(f"entry field reason must be text, got {reason!r}")
    if step != "verdict":
        if entry.get("verdict") is not None:
            raise KnowledgeError(f"only a verdict entry carries a verdict, not a {step} entry")
        return entry
    if entry.get("verdict") not in VERDICTS:
        raise KnowledgeError(f"a verdict entry carries one verdict, AGREE or DISAGREE-FINAL, got {entry.get('verdict')!r}")
    if not reason:
        raise KnowledgeError("a verdict entry must carry its reason")
    return entry


def _patient(action: Callable, *args):
    """Run a filesystem action, retrying while Windows reports the path in use."""
    for _ in range(100):
        try:
            return action(*args)
        except PermissionError:
            _clock.sleep(0.02)
    return action(*args)


def _report(path: Path, why: str) -> None:
    if (str(path), why) not in _REPORTED:
        _REPORTED.add((str(path), why))
        print(f"knowledge: skipped {path}: {why}", file=sys.stderr)


def _load(path: Path) -> dict:
    """The entry stored at `path`, checked against its file name; raises KnowledgeError when it is unusable."""
    try:
        data = json.loads(_patient(path.read_text, "utf-8"))
    except FileNotFoundError:
        raise
    except (OSError, ValueError) as exc:
        raise KnowledgeError(f"unreadable entry: {exc}") from None
    if not isinstance(data, dict):
        raise KnowledgeError("entry is not a JSON object")
    version = data.get("format_version")
    if version not in KNOWN_VERSIONS or isinstance(version, bool):
        raise KnowledgeError(f"foreign entry of format version {version!r}; not read, not changed")
    entry = {field: data.get(field) for field in FIELDS}
    if sorted(data) != sorted(FIELDS + ("format_version",)):
        raise KnowledgeError("entry does not hold exactly the knowledge-store fields")
    _check(entry)
    if _entry_path(path.parent.parent.parent, path.parent.parent.name, entry["author"], entry["time"]) != path:
        raise KnowledgeError("entry's author and time do not match its file name")
    return entry


def _publish(path: Path, entry: dict, replace: bool) -> None:
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        tmp.write_text(json.dumps({"format_version": FORMAT_VERSION, **entry}, indent=1), "utf-8")
        if replace:
            _patient(os.replace, tmp, path)
        else:
            os.link(tmp, path)
    except FileExistsError:
        raise KnowledgeError(f"an entry by {entry['author']} at {entry['time']} already exists") from None
    finally:
        if tmp.exists():
            _patient(tmp.unlink)


def write_entry(root: str | os.PathLike, feature: str, *, author: str, role: str, model: str, ground: str,
                stage: str, body: str, time: str | None = None, work_item: str | None = None,
                debate_step: str | None = None, verdict: str | None = None,
                reason: str | None = None) -> dict:
    """Create an unfinished entry; `time` defaults to now. A second entry by one author in one second is refused."""
    if time is None:
        time = datetime.now(timezone.utc).strftime(_TIME_FORMAT)
    entry = _check({"author": author, "role": role, "model": model, "time": time, "ground": ground,
                    "stage": stage, "body": body, "finished": False, "work_item": work_item,
                    "debate_step": debate_step, "verdict": verdict, "reason": reason})
    path = _entry_path(root, feature, author, time)
    path.parent.mkdir(parents=True, exist_ok=True)
    _publish(path, entry, replace=False)
    return entry


def mark_finished(root: str | os.PathLike, feature: str, author: str, time: str) -> dict:
    """The author's stamp: its clean exit, or the end of a debate step. Marking a finished entry changes nothing."""
    path = _entry_path(root, feature, author, time)
    try:
        entry = _load(path)
    except FileNotFoundError:
        raise KnowledgeError(f"no entry by {author} at {time} in the knowledge store of {feature}") from None
    if not entry["finished"]:
        entry["finished"] = True
        _publish(path, entry, replace=True)
    return entry


def _names(value: object, what: str) -> set[str]:
    """`value` as a set of non-empty names; refuses one text, a non-list, or a member that is not text."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise KnowledgeError(f"{what} must be a list of names, got {value!r}")
    names = list(value)
    if not all(isinstance(name, str) and name for name in names):
        raise KnowledgeError(f"{what} must hold only non-empty names, got {value!r}")
    return set(names)


def read_finished(root: str | os.PathLike, feature: str, stages: Iterable[str],
                  debaters: Mapping[str, Iterable[str]] | None = None) -> list[dict]:
    """Finished entries of `stages`, plus those of a work item in `debaters`, ordered by time then author.

    `stages` holds the reader's stage and the earlier ones it may read; `debaters` maps each work-item id to its
    debater roles. A draft is returned only when every role of its item has a finished draft; a draft whose item
    is not in `debaters` is withheld.
    """
    stages = _names(stages, "stages")
    if not isinstance(debaters, (Mapping, type(None))):
        raise KnowledgeError(f"debaters must map each work-item id to its debater roles, got {debaters!r}")
    roles = {item: _names(names, f"debater roles of work item {item!r}") for item, names in (debaters or {}).items()}
    folder = store_path(root, feature)
    finished = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else ():
        try:
            entry = _load(path)
        except FileNotFoundError:
            continue
        except KnowledgeError as exc:
            _report(path, str(exc))
            continue
        if entry["finished"]:
            finished.append(entry)
    drafted: dict[str, set[str]] = {}
    for entry in finished:
        if entry["debate_step"] == "draft":
            drafted.setdefault(entry["work_item"], set()).add(entry["role"])
    released = {item for item, needed in roles.items() if needed and needed <= drafted.get(item, set())}
    out = []
    for entry in finished:
        item = entry["work_item"]
        if entry["stage"] not in stages and item not in roles:
            continue
        if entry["debate_step"] == "draft" and item not in released:
            continue
        out.append(entry)
    return sorted(out, key=lambda e: (e["time"], e["author"]))
