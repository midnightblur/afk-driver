"""The job supervisor: one watcher process per agent (SDD §8 row "Job supervisor").

agent-start starts it as `supervisor.py '{"run": <feature>, "watched_agent_id": <agent-id>}'` (plan D-122). It
watches the agent's process. When the process ends, it sends one message to the contact agent as that agent:
parked when a headless run, whose output it owns (TR-2), ended on a provider limit, else exited (plan D-149).
Exit codes: 0 done; 2 a bad argument, an agent-id with no entry, or a second supervisor for one agent; 4 the send
failed.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from team import entry  # noqa: E402

POLL_S = 5.0
SEND_TRIES = 3
SEND_PAUSE_S = 2.0
STATUS_TRIES = 10
STATUS_PAUSE_S = 0.5
TAIL_BYTES = 64 * 1024
TAIL_LINES = 20
OWNS_OUTPUT = ("headless",)
FIELDS = {"run", "watched_agent_id"}
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

LIMIT = re.compile(r"usage limit|hit your (?:usage )?limit|\b\d+-hour limit|weekly limit", re.I)
RETRYING = re.compile(r"\bretrying\b", re.I)
EPOCH = re.compile(r"\|(\d{10})\b")
ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?", re.I)
SPAN = re.compile(r"\bin\s+((?:\d+\s*(?:days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b[\s,]*(?:and\s+)?)+)",
                  re.I)
SPAN_PART = re.compile(r"(\d+)\s*([dhms])", re.I)
AFTER_RESET = re.compile(r"\b(?:resets?|try again)\b(.*)", re.I)
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
DATE = re.compile(r"\b(" + "|".join(MONTHS) + r")[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4})\b)?", re.I)
DAY_WORD = re.compile(r"\b(?:today|tomorrow|tonight|(?:mon|tues|wednes|thurs|fri|satur|sun)day)\b", re.I)
CLOCK_12 = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\b", re.I)
CLOCK_24 = re.compile(r"\b(\d{1,2}):(\d{2})\b")
ZONE = re.compile(r"\(([^()]+)\)")
LOCAL = "local"


class Refused(Exception):
    """A start the supervisor refuses with exit 2."""


def message_id_for(agent_id: str, counter: int) -> str:
    """The watched agent-id, then sup, then the counter: never an `<agent-id>-<n>` id the agent makes."""
    return f"{agent_id}-sup-{counter}"


def _message_id(run_dir: Path, agent_id: str) -> str:
    """One above the highest id an earlier supervisor of this agent used (plan D-151)."""
    used = re.compile(re.escape(agent_id) + r"-sup-([0-9]+)(?:\.json)?")
    highest = 0
    for folder in ("inbox", "processed", "bodies"):
        try:
            names = os.listdir(run_dir / folder)
        except OSError:
            continue
        for name in names:
            found = used.fullmatch(name)
            if found:
                highest = max(highest, int(found.group(1)))
    return message_id_for(agent_id, highest + 1)


def _holder(path: Path) -> dict | None:
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return held if isinstance(held, dict) and isinstance(held.get("pid"), int) else None


def _claim(run_dir: Path, agent_id: str) -> Path:
    """Claim the next slot of `<run>/supervisors/<agent-id>/`; Refused while a live supervisor holds one (D-150)."""
    folder = run_dir / "supervisors" / agent_id
    folder.mkdir(parents=True, exist_ok=True)
    slots = []
    for path in folder.glob("*.json"):
        if not path.stem.isdigit():
            continue
        slots.append(int(path.stem))
        held = _holder(path)
        if held is not None and entry._same_process(held["pid"], held.get("started_at")) != "gone":
            raise Refused(f"agent {agent_id} already has a job supervisor, process {held['pid']}")
    me = os.getpid()
    temp = folder / f".{me}.{uuid.uuid4().hex}.tmp"
    temp.write_text(json.dumps({"pid": me, "started_at": entry.process.creation_time(me)}), encoding="utf-8")
    slot = folder / f"{max(slots, default=0) + 1}.json"
    try:
        os.link(temp, slot)
    except FileExistsError:
        raise Refused(f"agent {agent_id} already has a job supervisor: another one took claim {slot.name} first") \
            from None
    finally:
        temp.unlink(missing_ok=True)
    return slot


def limit_line(text: str) -> str | None:
    """The last of the last 20 non-blank lines that names a provider limit."""
    lines = [line.strip() for line in text.splitlines() if line.strip()][-TAIL_LINES:]
    return next((line for line in reversed(lines) if LIMIT.search(line) and not RETRYING.search(line)), None)


def _zone(text: str) -> object:
    """The zone a `(…)` after the time names; LOCAL when none; None when the machine cannot resolve it."""
    found = ZONE.search(text)
    if not found:
        return LOCAL
    name = found.group(1).strip()
    if name.upper() in ("UTC", "GMT", "Z"):
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except (ImportError, ValueError, OSError, KeyError):     # ZoneInfoNotFoundError is a KeyError
        return None


def _clock(text: str, seen_at: datetime) -> datetime | None:
    """A date and/or clock time after "resets" or "try again"; a time alone is its next occurrence after `seen_at`."""
    after = AFTER_RESET.search(text)
    if not after:
        return None
    rest = after.group(1)
    if DAY_WORD.search(rest):
        return None
    date, twelve = DATE.search(rest), CLOCK_12.search(rest)
    clock = twelve or CLOCK_24.search(rest)
    if not date and not clock:
        return None
    hour, minute = 0, 0
    if clock:
        hour, minute = int(clock.group(1)), int(clock.group(2) or 0)
        if twelve:
            if not 1 <= hour <= 12:
                return None
            hour = hour % 12 + (12 if twelve.group(3).lower() == "p" else 0)
        if hour > 23 or minute > 59:
            return None
    zone = _zone(rest)
    if zone is None:
        return None
    base = seen_at.astimezone() if zone == LOCAL else seen_at.astimezone(zone)
    try:
        if date:
            year = int(date.group(3) or base.year)
            day = datetime(year, MONTHS.index(date.group(1)[:3].lower()) + 1, int(date.group(2)), hour, minute)
            if not date.group(3) and day.date() < base.date():
                day = day.replace(year=year + 1)
        else:
            day = base.replace(tzinfo=None, hour=hour, minute=minute, second=0, microsecond=0)
            if day <= base.replace(tzinfo=None):
                day += timedelta(days=1)
    except ValueError:
        return None
    local = day.astimezone() if zone == LOCAL else day.replace(tzinfo=zone)
    return local.astimezone(timezone.utc)


def reset_time(line: str, seen_at: datetime) -> datetime | None:
    """The reset time a provider-limit line states, in UTC; None when it states none the supervisor reads."""
    found = EPOCH.search(line)
    if found:
        return datetime.fromtimestamp(int(found.group(1)), timezone.utc)
    found = ISO.search(line)
    if found:
        year, month, day, hour, minute, second, offset = found.groups()
        zone = "+00:00" if (offset or "").upper() == "Z" else offset or ""
        text = f"{year}-{month}-{day}T{hour}:{minute}:{second or '00'}{zone}"
        try:      # with no offset the naive time is the machine's local time
            return datetime.fromisoformat(text).astimezone(timezone.utc)
        except ValueError:
            return None
    found = SPAN.search(line)
    if found:
        units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
        seconds = sum(int(n) * units[u.lower()] for n, u in SPAN_PART.findall(found.group(1)))
        return seen_at.astimezone(timezone.utc) + timedelta(seconds=seconds)
    return _clock(line, seen_at)


def _tail(path: Path) -> tuple[str, datetime] | None:
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, os.path.getsize(path) - TAIL_BYTES))
            text = handle.read().decode("utf-8", "replace")
        return text, datetime.fromtimestamp(os.path.getmtime(path), timezone.utc)
    except OSError:
        return None


def _exit_code(host: entry.Host, feature: str, agent_id: str, sleep: Callable[[float], None]) -> int | None:
    """The run's exit code from agent-status, asked again while the job owner has not written it yet."""
    code = None
    for attempt in range(STATUS_TRIES):
        if attempt:
            sleep(STATUS_PAUSE_S)
        answer, status = entry.run_command("agent-status", {"run": feature, "agent_id": agent_id}, host)
        code = status.get("exit_code") if answer == 0 else None
        if code is not None:
            break
    return code


def _verdict(host: entry.Host, feature: str, run_dir: Path, agent: dict,
             sleep: Callable[[float], None]) -> tuple[str, str | None, datetime | None]:
    """(kind, provider line, reset time): parked for a headless run that ended on a provider limit (D-149)."""
    if agent.get("transport_kind") not in OWNS_OUTPUT:
        return "exited", None, None
    if _exit_code(host, feature, agent["agent_id"], sleep) == 0:
        return "exited", None, None
    tail = _tail(run_dir / "logs" / f"{agent['agent_id']}.log")
    line = limit_line(tail[0]) if tail else None
    if line is None:
        return "exited", None, None
    return "parked", line, reset_time(line, tail[1])


def _ended(host: entry.Host, feature: str, agent: dict) -> bool:
    """Whether the watched agent is gone: by its process id, else by agent-status on its handle."""
    if agent.get("pid") is not None:
        return entry._same_process(agent["pid"], agent.get("started_at")) == "gone"
    if agent.get("handle"):
        code, status = entry.run_command("agent-status", {"run": feature, "agent_id": agent["agent_id"]}, host)
        return code == 0 and status.get("alive") is False
    return False


def _send(host: entry.Host, feature: str, payload: dict, sleep: Callable[[float], None]) -> tuple[int, dict]:
    """agent-send with the same message id on each retry, so the inbox keeps one copy."""
    code, answer = entry.run_command("agent-send", {"run": feature, **payload}, host)
    for _ in range(SEND_TRIES - 1):
        if code == 0:
            break
        sleep(SEND_PAUSE_S)
        code, answer = entry.run_command("agent-send", {"run": feature, **payload}, host)
    return code, answer


def supervise_agent(host: entry.Host, feature: str, watched_agent_id: str, *, poll_s: float = POLL_S,
                    sleep: Callable[[float], None] = time.sleep) -> tuple[int, dict]:
    """Watch one agent; when its process ends, send exited, or parked with the reset time in a body file (TR-2)."""
    run = entry.Run(host, feature)
    try:
        if entry._agent(run.manifest(), watched_agent_id) is None:
            raise Refused(f"field `watched_agent_id`: no entry holds agent-id {watched_agent_id}")
        _claim(run.dir, watched_agent_id)
    except Refused as refused:
        return 2, {"error": True, "operation": "supervise", "reason": str(refused)}
    while True:
        data = run.manifest(required=False)
        agent = entry._agent(data, watched_agent_id) if data else None
        if agent is None:
            return 0, {"sent": False, "reason": f"run {feature} no longer lists agent {watched_agent_id}"}
        if _ended(host, feature, agent):
            break
        if agent["state"] not in entry.LIVE and agent.get("pid") is None and not agent.get("handle"):
            return 0, {"sent": False, "reason": f"agent {watched_agent_id} is {agent['state']} and never ran"}
        sleep(poll_s)
    kind, line, reset = _verdict(host, feature, run.dir, agent, sleep)
    message_id = _message_id(run.dir, watched_agent_id)
    body_path = ""
    if kind == "parked" and reset is not None:
        when = reset.strftime(UTC_FORMAT)
        provider = (agent.get("model") or "").partition("@")[2] or "unknown"
        body = run.dir / "supervisors" / watched_agent_id / f"{message_id}.txt"
        body.parent.mkdir(parents=True, exist_ok=True)
        body.write_text(f"Agent {watched_agent_id} (role {agent['role']}, provider {provider}) stopped on a provider "
                        f"limit; the provider resets at {when}.\nThe provider said: {line[:500]}\n", encoding="utf-8")
        body_path = str(body)
    payload = {"agent_id": watched_agent_id, "generation": agent["owner_generation"], "target": entry.CONTACT,
               "kind": kind, "message_id": message_id, **({"body_path": body_path} if body_path else {})}
    code, answer = _send(host, feature, payload, sleep)
    if code != 0:
        return code, answer
    return 0, {"sent": True, "kind": kind, "message_id": message_id, "body_path": body_path,
               "reset": reset.strftime(UTC_FORMAT) if reset else None}


def main(argv: list[str]) -> int:
    """`supervisor.py '<json>'`: the object holds exactly run and watched_agent_id; prints one JSON answer."""
    try:
        data = json.loads(argv[0]) if len(argv) == 1 else None
    except ValueError:
        data = None
    if not isinstance(data, dict) or set(data) != FIELDS or not all(
            isinstance(data[k], str) and entry.SAFE.fullmatch(data[k]) for k in FIELDS):
        extra = sorted(set(data) - FIELDS) if isinstance(data, dict) else []
        named = f"field `{extra[0]}` is not a field of a supervisor start; " if extra else ""
        code, answer = 2, {"error": True, "operation": "supervise",
                           "reason": f"{named}the argument is one JSON object with run and watched_agent_id"}
    else:
        try:
            code, answer = supervise_agent(entry.Host.discover(), data["run"], data["watched_agent_id"])
        except entry.contract.Answer as problem:
            code, answer = problem.code, problem.body
        except Exception as error:      # a detached process answers in the house shape, never a traceback
            code, answer = 4, {"unavailable": True, "operation": "supervise",
                               "reason": f"the supervisor failed: {type(error).__name__}: {error}"}
    sys.stdout.write(json.dumps(answer, sort_keys=True) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
