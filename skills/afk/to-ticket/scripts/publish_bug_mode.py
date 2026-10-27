#!/usr/bin/env afk-python
"""publish_bug_mode.py — the bug and ad-hoc mode of /afk:to-ticket.

Files a ticket from a DIAGNOSIS.md, or from a description written to a file,
through the configured tracker adapter's verbs (`tracker_api.load(("call",))`).
The run is an ordered list of named steps: ticket, fix-version, evidence,
proof, in-review. A step whose Outside writes entry is listed is skipped; every
other write is read back first, and a failed write is retried at most twice,
each after a read-back shows it left nothing (`outside_writes.py`). The first
failure ends the run; no write follows it. Steps, refusals and write order:
`../BUG-MODE.md`.

Usage:
    afk-python publish_bug_mode.py (--diagnosis DIAGNOSIS.md | --description FILE)
        [--type bug|enhancement] [--key KEY] [--summary TEXT]
        [--fix-version NAME] [--proof P-n=PATH]... [--in-review]
        [--consent person|prior] [--dry-run | --yes]

Exit: 0 written, or a dry run; 1 refused or not confirmed, nothing written;
2 a write failed after its retries, and no write followed it.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
DIAGNOSE_SCRIPTS = PLUGIN_ROOT / "skills" / "utils" / "diagnose" / "scripts"
for _path in (PLUGIN_ROOT / "scripts", DIAGNOSE_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import tracker_api  # noqa: E402
from check_diagnosis import check_diagnosis  # noqa: E402
from diagnosis_file import BOM, headings, sections, split_lines  # noqa: E402
from outside_writes import (append_outside_write, listed, replace_text,  # noqa: E402
                            retry_with_read_back)

TYPES = ("bug", "enhancement")
PROOF_KINDS = ("P-1", "P-2", "P-3")
IN_REVIEW = "in-review"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
STEPS = ("ticket", "fix-version", "evidence", "proof", "in-review")
EVIDENCE_PARTS = ("Spec comparison", "Reproduction", "Attempts", "Root cause", "Fix proposal")
WRITTEN_PARTS = ("Work id", "Ticket key", "Outside writes")


class Refused(Exception):
    """A check failed before any write."""


class Failed(Exception):
    """A write failed after its retries."""


@dataclass
class Result:
    code: int
    lines: list[str] = field(default_factory=list)
    ticket: str | None = None


@dataclass(frozen=True)
class Kind:
    in_review_path: str
    fix_versions: bool
    body_fields: str
    comment_fields: str
    state_fields: str
    body_query: Callable[[dict, str], str]
    type_name: Callable[[dict, str], str]
    type_check: Callable[["Run", str], str | None]
    link: Callable[["Run", str], str]
    key_of: Callable[[str], str]


def _jira_project(config: dict) -> str:
    block = config.get("jira") if isinstance(config.get("jira"), dict) else {}
    return str(block.get("project") or os.environ.get("JIRA_DEFAULT_PROJECT") or "")


def _jira_type_name(config: dict, ticket_type: str) -> str:
    block = config.get("jira") if isinstance(config.get("jira"), dict) else {}
    types = block.get("issue-types") if isinstance(block.get("issue-types"), dict) else {}
    return str(types.get(ticket_type) or ticket_type.capitalize())


def _jql_value(run: "Run", field_name: str, value: str) -> str | None:
    """Jira answers 400 for a JQL value it does not know: an unknown type or version."""
    project = _jira_project(run.config)
    query = (f'project = "{project}" AND ' if project else "") + f'{field_name} = "{value}"'
    answer = run.call("tracker_search", {"query": query, "max_results": 1})
    if _bad(answer):
        return f"Jira does not accept {field_name} `{value}`: {_why(answer)}"
    return None


def _jira_link(run: "Run", key: str) -> str:
    creds = getattr(run.tracker, "resolve_creds_env", lambda: {})() or {}
    base = str(creds.get("JIRA_BASE_URL") or "").rstrip("/")
    return f"{base}/browse/{key}" if base else ""


def _github_label_check(run: "Run", name: str) -> str | None:
    gh, repo_args = getattr(run.tracker, "_gh", None), getattr(run.tracker, "_repo_args", None)
    if gh is None or repo_args is None:
        return "the github-issues adapter offers no label list, so the type label cannot be checked"
    labels = gh("label", "list", *repo_args(), "--search", name, "--json", "name", "--limit", "100")
    if _bad(labels) or not isinstance(labels, list):
        return f"the labels could not be read: {_why(labels)}"
    if not any(str(label.get("name", "")).casefold() == name.casefold()
               for label in labels if isinstance(label, dict)):
        return f"the label `{name}` does not exist in the repository"
    return None


def _github_link(run: "Run", key: str) -> str:
    answer = run.call("tracker_get", {"ticket_key": key, "fields": "url"})
    return str(answer.get("url") or "") if isinstance(answer, dict) and not _bad(answer) else ""


KINDS = {
    "jira": Kind(
        in_review_path="jira.transitions", fix_versions=True,
        body_fields="description", comment_fields="comment", state_fields="status",
        body_query=lambda config, marker:
            f'project = "{_jira_project(config)}" AND description ~ "\\"{marker}\\""',
        type_name=_jira_type_name,
        type_check=lambda run, name: _jql_value(run, "issuetype", name),
        link=_jira_link, key_of=lambda key: key.strip().upper()),
    "github-issues": Kind(
        in_review_path="github-issues.state-labels", fix_versions=False,
        body_fields="body", comment_fields="comments", state_fields="labels,state",
        body_query=lambda config, marker: f'"{marker}" in:body',
        type_name=lambda config, ticket_type: ticket_type,
        type_check=_github_label_check,
        link=_github_link, key_of=lambda key: key.rsplit("#", 1)[-1].strip()),
}


def _bad(answer) -> bool:
    """An answer that did not do what was asked; a list is a read that worked."""
    if isinstance(answer, list):
        return False
    return not isinstance(answer, dict) or bool(
        answer.get("error") or answer.get("unavailable") or answer.get("unsupported"))


TRANSIENT = re.compile(r"\b5\d\d\b|timed? ?out|timeout|connection|network|temporar|rate limit|EOF",
                       re.IGNORECASE)


def _why(answer) -> str:
    if not isinstance(answer, dict):
        return repr(answer)
    if answer.get("reason"):
        return str(answer["reason"])
    status = answer.get("status")
    if status is not None:
        label = f"HTTP {status}" if isinstance(status, int) and status >= 100 else f"exit code {status}"
        return f"{label}: {str(answer.get('body') or '')[:2000]}"
    return str(answer.get("body") or answer.get("message") or answer)


def _permanent(answer) -> bool:
    """A refusal, a 4xx, or a command-line client's error that names no network or
    server fault: the same write would fail again, so it is not retried."""
    if not isinstance(answer, dict):
        return False
    status = answer.get("status")
    if answer.get("refused") or answer.get("unsupported"):
        return True
    if isinstance(status, int) and 400 <= status < 500:
        return True
    return (isinstance(status, int) and 0 < status < 100
            and not TRANSIENT.search(str(answer.get("body") or "")))


def _marker_seen(answer, marker: str) -> bool:
    text = json.dumps(answer, ensure_ascii=False)
    return re.search(re.escape(marker) + r"(?![A-Za-z0-9-])", text) is not None


def _hits(answer) -> list:
    if isinstance(answer, list):
        return answer
    return list(answer.get("issues") or []) if isinstance(answer, dict) else []


def _part_lines(path: Path, part: str) -> list[str]:
    return sections(path.read_text(encoding="utf-8")).get(part.lower(), [])


def _part_text(path: Path, part: str) -> str:
    return "\n".join(_part_lines(path, part)).strip()


def _write_part(path: Path, part: str, value: str, only_empty: bool) -> bool:
    """Set `## {part}` to `value`; with `only_empty`, only while it has no content."""
    raw = path.read_bytes().decode("utf-8")
    bom = raw.startswith(BOM)
    lines = split_lines(raw.removeprefix(BOM), keepends=True)
    marks = list(headings(lines))
    for n, (at, name) in enumerate(marks):
        if name != part.lower():
            continue
        end = marks[n + 1][0] if n + 1 < len(marks) else len(lines)
        if only_empty and any(line.strip() for line in lines[at + 1:end]):
            return False
        eol = "\r\n" if lines[at].endswith("\r\n") else "\n"
        if not lines[at].endswith("\n"):
            lines[at] += eol
        tail = [eol] if end < len(lines) else []
        lines[at + 1:end] = [eol, value + eol, *tail]
        replace_text(path, (BOM if bom else "") + "".join(lines))
        return True
    raise ValueError(f"the diagnosis has no `## {part}` part")


def _listed_change(path: Path) -> str:
    for line in _part_lines(path, "Outside writes"):
        item = line.strip()
        if item.startswith("- change:"):
            return item.split(":", 1)[1].strip()
    return ""


def _strip_mark(line: str) -> str:
    return re.sub(r"^[-*]\s+(\[[a-z]+\]\s*)?", "", line.strip()).strip()


def _config_module():
    spec = importlib.util.spec_from_file_location("afk_config", PLUGIN_ROOT / "scripts" / "afk-config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_folder(work_id: str) -> str | None:
    """The spec folder the notes adapter renders for `work_id`, or None."""
    spec = importlib.util.spec_from_file_location("afk_run_hook", PLUGIN_ROOT / "hooks" / "run-hook.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    bash = launcher.find_bash()
    if bash is None:
        return None
    env = launcher.shell_env(bash)
    env["AFK_PLUGIN_ROOT"] = os.environ.get("AFK_PLUGIN_ROOT") or str(PLUGIN_ROOT)
    try:
        done = subprocess.run(
            [str(bash), "-c", '. "$AFK_PLUGIN_ROOT/hooks/lib/adapter.sh"; afk_adapter notes resolve "$1"',
             "--", json.dumps({"workId": work_id, "ticket": work_id})],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            env=env, stdin=subprocess.DEVNULL)
        answer = json.loads(done.stdout or "{}")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return answer.get("dir") if isinstance(answer, dict) else None


def _confirm(question: str) -> bool:
    try:
        return input(question).strip().lower() in ("y", "yes")
    except EOFError:
        return False


@dataclass
class Run:
    tracker: object
    kind: Kind
    config: dict
    sleep: Callable[[float], None]
    lines: list[str]

    def call(self, operation: str, payload: dict):
        return self.tracker.call(operation, payload)

    def say(self, line: str):
        self.lines.append(line)


def run_bug_mode(source, *, description: bool = False, ticket_type: str | None = None,
                 key: str | None = None, summary: str | None = None,
                 fix_version: str | None = None, proof: tuple = (), in_review: bool = False,
                 consent: str | None = None, dry_run: bool = False, yes: bool = False,
                 tracker=None, kind: str | None = None, config: dict | None = None,
                 resolve: Callable[[str], str | None] | None = None,
                 confirm: Callable[[str], bool] = _confirm,
                 sleep: Callable[[float], None] = time.sleep) -> Result:
    """Diagnosis path, or description file, plus an optional type and key ->
    the `TICKET: <key> <link>` line of the ticket created or updated."""
    lines: list[str] = []
    plan = None
    resolve = resolve or _resolve_folder
    try:
        source = Path(source)
        if not source.is_file():
            raise Refused(f"no such file: {source}")
        if not dry_run and consent not in ("person", "prior"):
            raise Refused("a tracker write needs a person present or a prior approval that "
                          "covers ticket writes: pass --consent person or --consent prior")
        if ticket_type is not None and ticket_type not in TYPES:
            raise Refused(f"type `{ticket_type}` is not one of {', '.join(TYPES)}")
        reader = _config_module()
        if config is None:
            try:
                config = reader.load(reader.project_root())
            except Exception as e:  # the reader's ConfigError, or a file it could not open
                raise Refused(f".afk/config.yaml could not be read: {e}") from e
        assignee = reader.developer_value(config, "trackerAssignee")
        kind_name = kind or str(config.get("tracker") or "none")
        if kind_name == "none":
            raise Refused("tracker kind `none`: set `tracker:` in .afk/config.yaml to a tracker")
        if kind_name not in KINDS:
            raise Refused(f"tracker kind `{kind_name}` has no bug mode")
        if tracker is None:
            tracker = tracker_api.load(("call",))
        run = Run(tracker, KINDS[kind_name], config, sleep, lines)
        plan = _preflight(run, source, description, ticket_type, key, summary,
                          fix_version, proof, in_review, assignee)
        _show(run, plan)
        if dry_run:
            run.say("DRY-RUN: nothing was written")
            return Result(0, lines)
        if not yes and not confirm(f"Run the {len(plan.writes)} write step(s) above? [y/N] "):
            raise Refused("not confirmed")
        if plan.proof:
            _hold(plan)
        key_now, link = _execute(run, plan, resolve)
        ticket = f"TICKET: {key_now} {link}".rstrip()
        lines.append(ticket)
        return Result(0, lines, ticket)
    except Refused as e:
        lines.append(f"REFUSED: {e}; nothing was written")
        return Result(1, lines)
    except (Failed, OSError, ValueError) as e:
        lines.append(f"FAILED: {e}; no write followed it")
        return Result(2, lines)
    finally:
        if plan is not None and plan.staged:
            shutil.rmtree(plan.staged, ignore_errors=True)


@dataclass
class Plan:
    source: Path
    description: bool
    work_id: str
    recorded: str
    given: str
    key: str
    create: dict | None
    body: str
    fix_version: str
    proof: list
    in_review: bool
    target: tuple | None
    assignee: str | None
    writes: list = field(default_factory=list)
    mark_id: str = ""
    staged: str | None = None


def _preflight(run, source, description, ticket_type, key, summary, fix_version, proof,
               in_review, assignee) -> Plan:
    """Every check that can refuse, before any write."""
    if description:
        real = source.resolve()
        digest = hashlib.sha1(f"{real.parent.name}/{real.name}".encode("utf-8")).hexdigest()[:8]
        work_id = f"{_slug(real.parent.name)}_{_slug(real.stem)}-{digest}"
        recorded, text = "", source.read_text(encoding="utf-8").strip()
        if not text:
            raise Refused(f"the description file {source} is empty")
    else:
        checked = check_diagnosis(source)
        if not checked.ok:
            raise Refused("the diagnosis check refuses the file: "
                          + "; ".join([f"missing {m}" for m in checked.missing] + checked.problems))
        present = {name for _, name in headings(split_lines(
            source.read_text(encoding="utf-8").removeprefix(BOM), keepends=True))}
        absent = [part for part in WRITTEN_PARTS if part.lower() not in present]
        if absent:
            raise Refused("the diagnosis has no " + ", ".join(f"`## {part}`" for part in absent)
                          + " part, which this mode writes")
        work_id = _part_text(source, "Work id")
        recorded = _part_text(source, "Ticket key")
        text = ""
    if not SAFE_ID.match(work_id):
        raise Refused(f"work id `{work_id}` must match {SAFE_ID.pattern} to be searchable")
    configured = _dotted(run.config, run.kind.in_review_path)
    value = configured.get(IN_REVIEW) if isinstance(configured, dict) else None
    if not value:
        raise Refused(f"the in-review key is not configured: set `{run.kind.in_review_path}.{IN_REVIEW}`")
    if fix_version and not run.kind.fix_versions:
        raise Refused("this tracker has no fix version; drop --fix-version")
    for kind_name, path in proof:
        if kind_name not in PROOF_KINDS:
            raise Refused(f"proof kind `{kind_name}` is not one of {', '.join(PROOF_KINDS)}")
        if not Path(path).is_file():
            raise Refused(f"no such proof file: {path}")

    given = run.kind.key_of(str(key)) if key is not None else ""
    if key is not None and not given:
        raise Refused(f"`--key {key}` names no ticket")
    if given and recorded and given == run.kind.key_of(recorded):
        given = recorded
    target_key = given or recorded
    if target_key:
        got = run.call("tracker_get", {"ticket_key": target_key})
        if _bad(got):
            raise Refused(f"the tracker does not return ticket `{target_key}`: {_why(got)}")
    create = None
    if not target_key:
        ticket_type = ticket_type or "bug"
        if run.kind.fix_versions and not _jira_project(run.config):
            raise Refused("no project to create in: set `jira.project` in .afk/config.yaml")
        create = {"summary": summary or _summary(source, description),
                  "issue_type": run.kind.type_name(run.config, ticket_type)}
    if ticket_type:
        why = run.kind.type_check(run, run.kind.type_name(run.config, ticket_type))
        if why:
            raise Refused(f"type `{ticket_type}`: {why}")
    if fix_version:
        why = _jql_value(run, "fixVersion", fix_version)
        if why:
            raise Refused(why)
    target = None
    if in_review and target_key and (description or not listed(source, f"in-review: {target_key}")):
        target = _in_review_target(run, target_key, str(value))

    plan = Plan(source, description, work_id, recorded, given, target_key, create, text,
                fix_version or "", list(proof), in_review, target, assignee)
    plan.writes = _planned(plan)
    return plan


def _dotted(config: dict, path: str):
    node = config
    for part in path.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node


def _summary(source: Path, description: bool) -> str:
    if description:
        lines = source.read_text(encoding="utf-8").splitlines()
    else:
        lines = _part_lines(source, "Symptom")
    first = next((_strip_mark(line).lstrip("#").strip() for line in lines if line.strip()), "")
    return first[:120] or source.parent.name


def _in_review_target(run, key: str, value: str) -> tuple:
    """(field, name) the ticket shows once moved: a status name or a label."""
    answer = run.call("tracker_transitions", {"ticket_key": key})
    if _bad(answer):
        raise Refused(f"the transitions of {key} could not be read: {_why(answer)}")
    offered = answer.get("transitions") or [] if isinstance(answer, dict) else []
    for t in offered:
        if not isinstance(t, dict):
            continue
        if value in (str(t.get("id")), t.get("label")) or str(t.get("name", "")).lower() == value.lower():
            if t.get("label"):
                return ("label", str(t["label"]))
            return ("status", str((t.get("to") or {}).get("name") or t.get("name")))
    state = run.call("tracker_get", {"ticket_key": key, "fields": run.kind.state_fields})
    if not _bad(state) and _in_state(state, ("status", value)):
        return ("status", value)
    names = ", ".join(f"{t.get('name')} ({t.get('id')})" for t in offered if isinstance(t, dict)) or "none"
    raise Refused(f"{key} offers no transition matching the in-review value `{value}`; it offers: {names}; "
                  "if it is already in review, re-run without --in-review")


def _in_state(answer, target: tuple) -> bool:
    kind, name = target
    if kind == "label":
        labels = answer.get("labels") if isinstance(answer, dict) else None
        return any(isinstance(l, dict) and l.get("name") == name for l in labels or [])
    fields = answer.get("fields") if isinstance(answer, dict) else None
    status = (fields or {}).get("status") if isinstance(fields, dict) else None
    return isinstance(status, dict) and str(status.get("name", "")).lower() == name.lower()


def _planned(plan: Plan) -> list[str]:
    writes = ["ticket"] if plan.create else []
    if plan.fix_version and not plan.create:
        writes.append("fix-version")
    if not plan.description or not plan.create:
        writes.append("evidence")
    if plan.proof:
        writes.append("proof")
    if plan.in_review:
        writes.append("in-review")
    return writes


def _show(run: Run, plan: Plan):
    run.say(f"PLAN: work id {plan.work_id}; ticket "
            + (f"{plan.key} (exists)" if plan.key else "to be created"))
    for step in STEPS:
        if step == "ticket" and plan.create:
            payload = dict(plan.create, assignee=plan.assignee or "",
                           fix_version=plan.fix_version)
            run.say(f"PLAN: ticket — create {json.dumps(payload, ensure_ascii=False)}")
        elif step in plan.writes and step != "ticket":
            run.say(f"PLAN: {step} — {_step_text(plan, step)}")
    if not plan.assignee and plan.create:
        run.say("NOTE: `trackerAssignee` resolves to nothing, so the ticket is filed unassigned "
                "(CONFIG.md \"Developer settings (K1–K5)\")")


def _step_text(plan: Plan, step: str) -> str:
    if step == "fix-version":
        return f"add fix version `{plan.fix_version}`"
    if step == "evidence":
        return "comment with the " + ("description" if plan.description else "diagnosis")
    if step == "proof":
        return "attach " + ", ".join(f"{k} {Path(p).name}" for k, p in plan.proof)
    return f"move to the in-review state `{IN_REVIEW}`"


def _hold(plan: Plan) -> None:
    """Copy each proof file aside before any write, so a folder move cannot take it away."""
    plan.staged = tempfile.mkdtemp(prefix="afk-proof-")
    held = []
    for n, (kind_name, path) in enumerate(plan.proof):
        spot = os.path.join(plan.staged, str(n))
        os.mkdir(spot)
        held.append((kind_name, os.path.join(spot, Path(path).name)))
        shutil.copyfile(path, held[-1][1])
    plan.proof = held


def _stage(plan: Plan) -> None:
    """Copy each held proof file to a name carrying the marker id, the kind and the step."""
    folder = plan.staged
    names = set()
    staged = []
    for kind_name, path in plan.proof:
        base = f"{plan.mark_id}-{kind_name.lower()}-proof-{Path(path).name}"
        name, n = base, 2
        while name.lower() in names:
            stem, dot, ext = base.rpartition(".")
            name = f"{stem}-{n}.{ext}" if dot else f"{base}-{n}"
            n += 1
        names.add(name.lower())
        shutil.copyfile(path, os.path.join(folder, name))
        staged.append((kind_name, os.path.join(folder, name)))
    plan.proof = staged


def _execute(run: Run, plan: Plan, resolve) -> tuple[str, str]:
    try:
        return _steps(run, plan, resolve)
    except (Refused, OSError, ValueError) as e:
        raise Failed(f"{e}; the writes reported above stay on the tracker") from e


def _filed_here(plan: Plan) -> bool:
    """This mode created the ticket: its key is recorded and listed as a ticket write."""
    return (not plan.description and listed(plan.source, f"ticket: {plan.key}")
            and _part_text(plan.source, "Ticket key") == plan.key)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-") or "ticket"


def _steps(run: Run, plan: Plan, resolve) -> tuple[str, str]:
    created = False
    if plan.create:
        plan.key = _create(run, plan, f"afk-evidence {plan.work_id} ticket")
        created = True
        if not plan.description:
            _list(run, plan, f"ticket: {plan.key}")
            _write_part(plan.source, "Ticket key", plan.key, only_empty=True)
    elif not plan.description:
        if plan.given and not plan.recorded:
            _write_part(plan.source, "Ticket key", plan.given, only_empty=True)
            run.say(f"STEP: ticket — recorded {plan.given} as the ticket key")
        elif plan.given and plan.given != plan.recorded:
            _list(run, plan, f"ticket: {plan.given}")
            run.say(f"STEP: ticket — {plan.given} listed in Outside writes")
    filed = _filed_here(plan)
    if filed and plan.work_id != plan.key:
        _move(run, plan, resolve)
    plan.mark_id = plan.key if filed else plan.work_id
    later = bool(plan.given and plan.recorded and plan.given != plan.recorded)
    suffix = f"-{_slug(plan.key)}" if later else ""
    marker = lambda step: f"afk-evidence {plan.mark_id} {step}{suffix}"  # noqa: E731
    if plan.in_review and plan.target is None and (
            plan.description or not listed(plan.source, f"in-review: {plan.key}")):
        value = str(_dotted(run.config, run.kind.in_review_path).get(IN_REVIEW))
        plan.target = _in_review_target(run, plan.key, value)
    if plan.fix_version and not created:
        _fix_version(run, plan)
    if "evidence" in plan.writes:
        _comment_step(run, plan, marker("evidence"), _evidence_text(plan, marker("evidence")))
    if plan.proof:
        _stage(plan)
        _proof(run, plan, marker("proof"))
    if plan.in_review:
        _move_to_in_review(run, plan)
    return plan.key, run.kind.link(run, plan.key)


def _list(run: Run, plan: Plan, entry: str):
    if not plan.description:
        append_outside_write(plan.source, entry)


def _retry(run: Run, step: str, write, read_back, *, key=None):
    """Run one write through the helper; a refusal or a 4xx ends it with no retry."""
    last = {}

    def attempt():
        last["answer"] = write()
        return last["answer"]

    def back():
        if _permanent(last.get("answer")):
            return dict(last["answer"], error=True)
        return read_back()

    outcome = retry_with_read_back(attempt, back, key=key, read_first=True, sleep=run.sleep)
    if not outcome.ok:
        answer = last.get("answer") if _permanent(last.get("answer")) else outcome.answer
        raise Failed(f"step {step}: {_why(answer) if answer is not None else outcome.reason}")
    return outcome


def _create(run: Run, plan: Plan, marker: str) -> str:
    body = plan.body if plan.description else _ticket_body(plan)
    payload = dict(plan.create, description=f"{body}\n\n{marker}\n")
    if plan.assignee:
        payload["assignee"] = plan.assignee
    if plan.fix_version:
        payload["fix_version"] = plan.fix_version
    if run.kind.fix_versions:
        payload["project"] = _jira_project(run.config)

    def find():
        answer = run.call("tracker_search", {"query": run.kind.body_query(run.config, marker),
                                             "max_results": 10})
        if _bad(answer):
            return answer
        for hit in _hits(answer):
            found = str((hit or {}).get("key") or (hit or {}).get("number") or "")
            got = run.call("tracker_get", {"ticket_key": found, "fields": run.kind.body_fields})
            if found and not _bad(got) and _marker_seen(got, marker):
                return {"key": found}
        return None

    outcome = _retry(run, "ticket", lambda: run.call("tracker_create", payload), find, key="key")
    key = str(outcome.answer["key"])
    how = "found by its marker, not created again" if outcome.found else "created"
    run.say(f"STEP: ticket — {key} {how}")
    for warning in ("assignee_warning", "fix_version_warning", "status_warning"):
        if isinstance(outcome.answer, dict) and outcome.answer.get(warning):
            run.say(f"NOTE: {outcome.answer[warning]}")
    return key


def _ticket_body(plan: Plan) -> str:
    parts = [f"**Diagnosis:** {_part_text(plan.source, 'Verdict')}",
             "**Symptom**\n\n" + _part_text(plan.source, "Symptom")]
    cause = _part_text(plan.source, "Root cause")
    if cause:
        parts.append("**Root cause**\n\n" + cause)
    return "\n\n".join(parts)


def _evidence_text(plan: Plan, marker: str) -> str:
    if plan.description:
        parts = [plan.body]
    else:
        parts = [f"**Diagnosis {plan.work_id}:** {_part_text(plan.source, 'Verdict')}",
                 "**Symptom**\n\n" + _part_text(plan.source, "Symptom")]
        for name in EVIDENCE_PARTS:
            text = _part_text(plan.source, name)
            if text:
                parts.append(f"**{name}**\n\n{text}")
    change = "" if plan.description else _listed_change(plan.source)
    if change:
        parts.append(f"**Change:** {change}")
    return "\n\n".join(parts + [marker])


def _comments_show(run: Run, key: str, marker: str):
    got = run.call("tracker_get", {"ticket_key": key, "fields": run.kind.comment_fields})
    if _bad(got):
        return got
    return {"found": marker} if _marker_seen(got, marker) else None


def _comment_step(run: Run, plan: Plan, marker: str, text: str):
    step = "evidence"
    entry = f"evidence: {marker}"
    if not plan.description and listed(plan.source, entry):
        run.say(f"STEP: {step} — skipped, listed in Outside writes")
        return
    outcome = _retry(run, step, lambda: run.call("tracker_comment", {"ticket_key": plan.key, "text": text}),
                     lambda: _comments_show(run, plan.key, marker))
    _list(run, plan, entry)
    run.say(f"STEP: {step} — " + ("found by its marker" if outcome.found else "comment posted"))


def _proof(run: Run, plan: Plan, marker: str):
    entry = f"evidence: {marker}"
    if not plan.description and listed(plan.source, entry):
        run.say("STEP: proof — skipped, listed in Outside writes")
        return
    names = {os.path.basename(path) for _, path in plan.proof}
    lines = [f"**Proof for {plan.mark_id}**", ""]
    lines += [f"- {kind_name}: `{os.path.basename(path)}`" for kind_name, path in plan.proof]
    change = "" if plan.description else _listed_change(plan.source)
    if change:
        lines += ["", f"**Change:** {change}"]
    text = "\n".join(lines + ["", marker])

    def stored():
        files = run.call("tracker_attachments", {"ticket_key": plan.key})
        items = files if isinstance(files, list) else []
        return any(isinstance(a, dict) and a.get("filename") in names for a in items)

    def back():
        seen = _comments_show(run, plan.key, marker)
        if seen is not None:
            return seen
        if stored():
            return {"error": True, "files_stored": True,
                    "reason": "the files are on the ticket; the comment is missing"}
        return None

    payload = {"ticket_key": plan.key, "files": [path for _, path in plan.proof], "text": text}
    try:
        outcome = _retry(run, "proof", lambda: run.call("tracker_attach", payload), back)
    except Failed:
        if not stored():
            raise
        note = text.replace(marker, "These files are attached to the ticket; the comment that "
                                    "carried them failed.\n\n" + marker)
        outcome = _retry(run, "proof", lambda: run.call(
            "tracker_comment", {"ticket_key": plan.key, "text": note}),
            lambda: _comments_show(run, plan.key, marker))
    _list(run, plan, entry)
    answer = outcome.answer if isinstance(outcome.answer, dict) else {}
    run.say("STEP: proof — " + ("found by its marker" if outcome.found else "comment and files posted"))
    for item in answer.get("unsupported_files") or []:
        run.say(f"NOTE: not attached, named in the comment: {item.get('file')} ({item.get('reason')})")
    for item in answer.get("mismatches") or []:
        run.say(f"NOTE: stored differently, named in the comment: {item.get('file')} ({item.get('reason')})")


def _fix_version(run: Run, plan: Plan):
    def current():
        got = run.call("tracker_get", {"ticket_key": plan.key, "fields": "fixVersions"})
        if _bad(got):
            return got, []
        versions = ((got.get("fields") or {}).get("fixVersions") or []) if isinstance(got, dict) else []
        return None, [v for v in versions if isinstance(v, dict)]

    error, versions = current()
    if error is not None:
        raise Failed(f"step fix-version: the fix versions of {plan.key} could not be read: {_why(error)}")

    def back():
        error, now = current()
        if error is not None:
            return error
        return {"found": True} if any(v.get("name") == plan.fix_version for v in now) else None

    wanted = [{"name": v.get("name")} for v in versions if v.get("name")] + [{"name": plan.fix_version}]
    outcome = _retry(run, "fix-version", lambda: run.call(
        "tracker_edit", {"ticket_key": plan.key, "fields": {"fixVersions": wanted}}), back)
    run.say("STEP: fix-version — " + ("already set" if outcome.found else f"set to {plan.fix_version}"))
    if isinstance(outcome.answer, dict) and outcome.answer.get("fix_version_warning"):
        run.say(f"NOTE: {outcome.answer['fix_version_warning']}")


def _move_to_in_review(run: Run, plan: Plan):
    entry = f"in-review: {plan.key}"
    if not plan.description and listed(plan.source, entry):
        run.say("STEP: in-review — skipped, listed in Outside writes")
        return
    def back():
        got = run.call("tracker_get", {"ticket_key": plan.key, "fields": run.kind.state_fields})
        if _bad(got):
            return got
        return {"found": True} if _in_state(got, plan.target) else None

    outcome = _retry(run, "in-review", lambda: run.call(
        "tracker_transition", {"ticket_key": plan.key, "transition_id": IN_REVIEW}), back)
    _list(run, plan, entry)
    run.say("STEP: in-review — " + ("already there" if outcome.found else "moved"))


def _move(run: Run, plan: Plan, resolve):
    """Move the spec folder to the one the new key renders, and make the key the work id."""
    old = plan.source.resolve().parent
    rendered = resolve(plan.key)
    if not rendered or "{" in rendered:
        run.say(f"NOTE: the spec folder for {plan.key} could not be resolved; it stays at {old}")
        return
    new = Path(rendered).resolve()
    if os.path.normcase(str(new)) == os.path.normcase(str(old)):
        return
    if new.exists():
        run.say(f"NOTE: {new} already exists; the spec folder stays at {old}")
        return
    new.parent.mkdir(parents=True, exist_ok=True)
    moved = subprocess.run(["git", "mv", "--", str(old), str(new)], cwd=str(old.parent),
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if moved.returncode != 0:
        shutil.move(str(old), str(new))
    plan.source = new / plan.source.name
    _write_part(plan.source, "Work id", plan.key, only_empty=False)
    plan.work_id = plan.key
    run.say(f"STEP: ticket — spec folder moved to {new}; the work id is now {plan.key}")


def _proof_arg(text: str):
    kind_name, sep, path = text.partition("=")
    if not sep or not path:
        raise argparse.ArgumentTypeError(f"`{text}` is not P-n=PATH")
    return kind_name.upper(), path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="The bug and ad-hoc mode of /afk:to-ticket.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--diagnosis", help="path to DIAGNOSIS.md")
    source.add_argument("--description", help="path to a description file in the spec folder")
    parser.add_argument("--type", dest="ticket_type", choices=TYPES)
    parser.add_argument("--key", help="an existing ticket key")
    parser.add_argument("--summary", help="the title of a ticket this run creates")
    parser.add_argument("--fix-version", dest="fix_version", help="Jira only")
    parser.add_argument("--proof", action="append", default=[], type=_proof_arg, help="P-n=PATH")
    parser.add_argument("--in-review", action="store_true", dest="in_review")
    parser.add_argument("--consent", choices=("person", "prior"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", dest="dry_run")
    mode.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    result = run_bug_mode(args.diagnosis or args.description, description=bool(args.description),
                          ticket_type=args.ticket_type, key=args.key, summary=args.summary,
                          fix_version=args.fix_version, proof=tuple(args.proof),
                          in_review=args.in_review, consent=args.consent,
                          dry_run=args.dry_run, yes=args.yes)
    for line in result.lines:
        print(line)
    return result.code


if __name__ == "__main__":
    sys.exit(main())
