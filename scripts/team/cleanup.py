"""Cleanup: one call per team run, at its end (SDD §8 row "Cleanup"; plan D-155 to D-157).

    cleanup.py '{"run": <feature>}'

Five fixed steps. 1. agent-stop, which holds the identity check, on every entry the manifest still lists: process
entries (the wait job, each job supervisor) first, then each agent entry not cleaned; then list the strays
agent-list finds, which cleanup never stops. 2. Delete the message area: everything in the run directory but what
steps 3 to 5 delete (plan D-156). 3. The knowledge store. 4. The resolved pattern. 5. The manifest, last. While an
entry is left after step 1, steps 2 to 5 are skipped and the report says the files are kept for the next cleanup.
Exit codes: 0 finished; 1 held (an entry is left or a delete failed; files kept); 2 a bad argument; 4 the manifest
cannot be read, so nothing was stopped or deleted.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from team import entry, knowledge, manifest, resolver  # noqa: E402

KEPT = "the message area, the knowledge store, the resolved pattern and the manifest are kept for the next cleanup"
NO_LIST = "the transport kind cannot list agents, so cleanup listed no strays"
STEPS = ("message area", "knowledge store", "resolved pattern", "manifest")


def _report(feature: str) -> dict:
    return {"run": feature, "finished": False, "stopped": [], "already_gone": [], "nothing_recorded": [],
            "unkillable": [], "processes_left": [], "panes_open": [], "strays": [], "strays_note": "",
            "kept": "", "deleted": [], "says": []}


def _stop_processes(host: entry.Host, feature: str, rows: list[dict], report: dict, why: dict) -> None:
    for row in rows:
        pid = row["pid"]
        code, answer = entry.run_command("agent-stop", {"run": feature, "pid": pid, "force": True}, host)
        if code != 0 or not answer.get("stopped"):
            why[("process", pid)] = (answer.get("reason") or f"agent-stop answered exit {code}",
                                     answer.get("survivors", []))
            continue
        try:
            manifest.remove_process(host.root, feature, pid)
        except manifest.ManifestError as problem:
            why[("process", pid)] = (f"stopped, but its entry could not be removed: {problem}", [])
            continue
        method = answer.get("method", "")
        done = {"pid": pid, "label": row["label"], "owner": row["owner"], "method": method}
        report["already_gone" if method == "already gone" else "stopped"].append(done)


def _stop_agent(host: entry.Host, feature: str, agent: dict, report: dict, why: dict) -> None:
    agent_id, name = agent["agent_id"], agent["agent_name"] or ""
    if agent["state"] == "starting":
        try:
            manifest.move_entry(host.root, feature, agent_id, "lost")
        except manifest.ManifestError as problem:
            why[("agent", agent_id)] = f"it could not move from starting to lost, so it was not stopped: {problem}"
            return
    code, answer = entry.run_command("agent-stop", {"run": feature, "agent_id": agent_id, "force": True}, host)
    if code != 0:
        why[("agent", agent_id)] = answer.get("reason") or f"agent-stop answered exit {code}"
        try:
            manifest.move_entry(host.root, feature, agent_id, "unkillable")
        except manifest.ManifestError:
            pass                    # already unkillable, or the manifest refused: the re-read reports the state
        return
    if answer.get("move_refused"):
        why[("agent", agent_id)] = answer["move_refused"]
    if answer.get("pane_closed") is False:
        where = {k: answer[k] for k in ("pane_id", "terminal_id") if answer.get(k)}
        where = where or {"pane_id": agent.get("handle") or "", **({"terminal_id": agent["terminal_id"]}
                                                                   if agent.get("terminal_id") else {})}
        report["panes_open"].append({"agent_id": agent_id, "agent_name": name, **where})
        why.setdefault(("agent", agent_id), answer.get("pane_reason") or "its pane or terminal could not be closed")
        return
    if not answer.get("stopped"):
        why.setdefault(("agent", agent_id), answer.get("reason") or "agent-stop answered stopped false")
        return
    method = answer.get("method", "")
    if method == "nothing recorded":
        report["nothing_recorded"].append({"agent_id": agent_id, "agent_name": name})
    else:
        bucket = "already_gone" if method == "already gone" else "stopped"
        report[bucket].append({"agent_id": agent_id, "agent_name": name, "pid": agent["pid"], "method": method})


def _list_strays(host: entry.Host, feature: str, data: dict | None, report: dict) -> None:
    code, answer = entry.run_command("agent-list", {"run": feature}, host)
    if code == 3:
        report["strays_note"] = NO_LIST
        return
    if code != 0:
        report["strays_note"] = (f"agent-list failed, so cleanup listed no strays: "
                                 f"{answer.get('reason') or f'exit {code}'}")
        return
    held = {a["handle"] for a in (data or {}).get("agents", []) if a.get("handle")}
    report["strays"] = [{"agent_name": item.get("agent_name", ""), "pane_id": item.get("pane_id", "")}
                        for item in answer.get("agents", []) if item.get("pane_id") not in held]


def _left(data: dict | None, report: dict, why: dict) -> bool:
    """Name every entry step 1 left in the manifest; True when there is one."""
    for agent in (data or {}).get("agents", []):
        if agent["state"] != "cleaned":
            reason = why.get(("agent", agent["agent_id"]), f"the entry is {agent['state']}")
            report["unkillable"].append({"agent_id": agent["agent_id"], "agent_name": agent["agent_name"] or "",
                                         "pid": agent["pid"], "state": agent["state"], "reason": reason})
    for row in (data or {}).get("processes", []):
        reason, survivors = why.get(("process", row["pid"]), ("the entry is still listed", []))
        report["processes_left"].append({"pid": row["pid"], "label": row["label"], "owner": row["owner"],
                                         "reason": reason, "survivors": survivors})
    return bool(report["unkillable"] or report["processes_left"])


def _writable(func, path, exc) -> None:
    """rmtree's retry for a read-only file: clear the flag, then run the refused call once more."""
    if not isinstance(exc, PermissionError):
        raise exc
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _remove(path: Path) -> None:
    """Delete a file, a link or a folder tree; a link is removed, never followed."""
    for attempt in range(50):
        try:
            if path.is_symlink() or path.is_junction() or not path.is_dir():
                try:
                    os.unlink(path)
                except (IsADirectoryError, PermissionError):
                    if not (path.is_symlink() or path.is_junction()):
                        raise
                    os.rmdir(path)
            else:
                shutil.rmtree(path, onexc=_writable)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(0.05)        # Windows: a file another process still holds open


def _delete(host: entry.Host, feature: str, report: dict) -> bool:
    """Steps 2 to 5, in order; stop at the first failed delete and name it. True when every step ran."""
    run_dir = host.root / feature
    store, pattern = knowledge.store_path(host.root, feature), resolver.resolved_path(host.root, feature)
    sheet = manifest.manifest_path(host.root, feature)
    family = f"{sheet.stem}."
    try:
        area = sorted(p for p in run_dir.iterdir() if p.name not in (store.name, pattern.name)
                      and not p.name.startswith(family))
    except FileNotFoundError:
        area = []
    except OSError as problem:
        report["says"].append(f"cleanup could not read the run directory {run_dir}: {problem}")
        return False
    for step, paths in zip(STEPS, (area, [store], [pattern], [sheet, run_dir])):
        for path in paths:
            try:
                _remove(path)
            except OSError as problem:
                report["says"].append(f"the {step} step could not delete {path}: {problem}")
                return False
        report["deleted"].append(step)
    return True


def _say(report: dict) -> None:
    says = report["says"]
    for row in report["unkillable"]:
        pid = f", process {row['pid']}" if row["pid"] is not None else ""
        says.append(f"could not stop {row['agent_name'] or row['agent_id']} (agent {row['agent_id']}{pid}): "
                    f"{row['reason']}; stop it by its agent name")
    for row in report["processes_left"]:
        says.append(f"could not kill {row['label']} (process {row['pid']}): {row['reason']}")
    for row in report["panes_open"]:
        where = f"terminal {row['terminal_id']}" if row.get("terminal_id") else f"pane {row.get('pane_id', '')}"
        says.append(f"{where} of {row['agent_name'] or row['agent_id']} is still open; close it by hand")
    for row in report["strays"]:
        says.append(f"stray agent {row['agent_name']} in pane {row['pane_id']}: the manifest does not name it, "
                    "so cleanup did not stop it; stop it by its name")
    if report["strays_note"]:
        says.append(report["strays_note"])
    for row in report["nothing_recorded"]:
        says.append(f"{row['agent_name'] or row['agent_id']} (agent {row['agent_id']}) had nothing recorded to "
                    "stop; it is cleaned")
    for row in report["already_gone"]:
        says.append(f"{row.get('agent_name') or row.get('label')} was already gone")


def run_cleanup(feature: str, host: entry.Host | None = None) -> tuple[int, dict]:
    """One call per run: kill, delete the message area, the knowledge store, the resolved pattern, then the
    manifest; answer (exit code, report naming every survivor, pane still open and stray)."""
    if not isinstance(feature, str) or not entry.SAFE.fullmatch(feature):
        return 2, {"error": True, "operation": "cleanup",
                   "reason": f"field `run`: {feature!r} is not a feature identifier"}
    host = host or entry.Host.discover()
    report, why = _report(feature), {}
    try:
        data = manifest.read_manifest(host.root, feature)
    except manifest.ManifestError as problem:
        return 4, {"unavailable": True, "operation": "cleanup", "run": feature,
                   "reason": f"the manifest cannot be read, so nothing was stopped or deleted: {problem}"}
    if data is None and not (host.root / feature).exists():
        report.update(finished=True, says=[f"run {feature} has no run directory; there is nothing to clean"])
        return 0, report
    if data is not None:
        _stop_processes(host, feature, data["processes"], report, why)
        for agent in data["agents"]:
            if agent["state"] != "cleaned":
                _stop_agent(host, feature, agent, report, why)
    try:
        data = manifest.read_manifest(host.root, feature)
    except manifest.ManifestError as problem:
        report.update(kept=KEPT, says=[f"the manifest cannot be read after the stops: {problem}", KEPT])
        return 1, report
    _list_strays(host, feature, data, report)
    held = _left(data, report, why)
    _say(report)
    if held or not _delete(host, feature, report):
        report["kept"] = KEPT if not report["deleted"] else (
            f"the {', '.join(s for s in STEPS if s not in report['deleted'])} are kept for the next cleanup")
        report["says"].append(report["kept"])
        return 1, report
    report["finished"] = True
    return 0, report


def main(argv: list[str]) -> int:
    """`cleanup.py '<json>'`: the object holds exactly `run`; prints the report as one JSON object."""
    try:
        data = json.loads(argv[0]) if len(argv) == 1 else None
    except ValueError:
        data = None
    if not isinstance(data, dict) or set(data) != {"run"} or not isinstance(data["run"], str) \
            or not entry.SAFE.fullmatch(data["run"]):
        code, answer = 2, {"error": True, "operation": "cleanup",
                           "reason": "the argument is one JSON object with only `run`, a feature identifier"}
    else:
        try:
            code, answer = run_cleanup(data["run"])
        except entry.contract.Answer as problem:
            code, answer = problem.code, problem.body
        except Exception as error:      # answer in the house shape, never a traceback
            code, answer = 4, {"unavailable": True, "operation": "cleanup",
                               "reason": f"cleanup failed: {type(error).__name__}: {error}"}
    sys.stdout.write(json.dumps(answer, sort_keys=True) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
