"""Recorded fake of the page engine command (SDD §3, §4, §6), until the S1 engine merges.

`engine.py check|render|show|poll DOC` and `engine.py ingest DOC --raw-file FILE`.

Environment:
  FAKE_CALL_LOG      file; one line `engine <verb>` per call
  FAKE_POLL_RAW      file; poll answers its exact text as `raw`
  FAKE_ENGINE_REFUSE verb that answers a refusal

The raw response grammar here is the fake's own: one line per signal.
  <item id>: accept | sign | option:<letter> | reopen | changes
  <item id>: note: <text>
  <item id>: write-in: <text>
  <map node id>: note: <text>     a steer
The grill passes raw text through and never parses it.
"""

import json
import os
import sys
from pathlib import Path

SCHEMA = "afkv2.page/0"
KINDS = {"decided", "confirm", "debate", "signoff", "info"}
STATES = {"open", "blocked", "needs_reading", "settled_by_mark", "settled_by_note"}
LONE_MARKS = ("accept", "sign", "option:")


def answer(obj, code=0):
    print(json.dumps(obj))
    return code


def refuse(reason, code=1):
    return answer({"ok": False, "error": {"code": "refused", "reason": reason}}, code)


def saved_copy(doc_path):
    return Path(str(doc_path) + ".saved")


def check(doc, doc_path):
    if doc.get("schema") != SCHEMA:
        return f"document: schema {doc.get('schema')}"
    session = doc.get("session") or {}
    for field in ("id", "skill", "feature", "ticket", "started"):
        if not session.get(field):
            return f"session: {field}"
    rounds = doc.get("rounds")
    if not rounds:
        return "document: rounds"
    if sum(r.get("state") == "current" for r in rounds) != 1:
        return "document: exactly one round is current"
    seen = set()
    for rnd in rounds:
        if "banner" not in rnd or "n" not in rnd or "items" not in rnd:
            return f"round {rnd.get('n')}: n, banner, items"
        for item in rnd["items"]:
            where = f"item {item.get('id')}"
            if not item.get("id") or item["id"] in seen:
                return f"{where}: id"
            seen.add(item["id"])
            if item.get("kind") not in KINDS:
                return f"{where}: kind"
            if item.get("state") not in STATES:
                return f"{where}: state"
            if not isinstance(item.get("body"), dict) or not item["body"].get("type"):
                return f"{where}: body"
            if item["state"] == "settled_by_note":
                settled = item.get("settled") or {}
                notes = {n["id"] for n in item.get("notes", [])}
                if settled.get("by") != "note" or not settled.get("reading"):
                    return f"{where}: settled.reading"
                if settled.get("signal") not in notes:
                    return f"{where}: settled.signal"
    saved = saved_copy(doc_path)
    if saved.exists():
        before = json.loads(saved.read_text("utf-8"))
        old = {r["n"]: r for r in before["rounds"] if r["state"] == "settled"}
        for rnd in rounds:
            if rnd["n"] in old and rnd != old[rnd["n"]]:
                return f"round {rnd['n']}: a settled round is never rewritten"
    return None


def parse(raw):
    lines = []
    for line in raw.splitlines():
        if line.strip():
            target, _, signal = line.partition(": ")
            lines.append((target.strip(), signal))
    return lines


def ingest(doc, raw):
    current = next(r for r in doc["rounds"] if r["state"] == "current")
    n = current["n"]
    items = {i["id"]: (r, i) for r in doc["rounds"] for i in r["items"]}
    nodes = {node["id"] for m in doc.get("maps") or [] for node in m["props"]["nodes"]}
    by_item, signals = {}, []
    for target, signal in parse(raw):
        if target in nodes:
            home = [i for _, i in items.values() if i.get("node") == target]
            home[-1].setdefault("notes", []).append({
                "id": f"N-{n}-{home[-1]['id']}", "round": n, "target": target,
                "text": signal.split("note: ", 1)[1], "deleted": False})
            signals.append({"target": target, "note": True})
            continue
        by_item.setdefault(target, []).append(signal)
        signals.append({"target": target, "signal": signal})
    for item_id, lines in by_item.items():
        rnd, item = items[item_id]
        for line in lines:
            if line.startswith("note: "):
                item.setdefault("notes", []).append({
                    "id": f"N-{n}-{item_id}", "round": n, "target": item_id,
                    "text": line[len("note: "):], "deleted": False})
        lone = len(lines) == 1 and lines[0].startswith(LONE_MARKS)
        if rnd is not current:
            item["state"] = "open"
        elif lone:
            item["state"] = "settled_by_mark"
            item["settled"] = {"by": "mark", "round": n, "signal": lines[0]}
        else:
            item["state"] = "needs_reading"
    current.setdefault("responses", []).append(
        {"received": "2026-01-05T10:00:00Z", "raw": raw, "signals": signals})
    return signals


def main(argv):
    verb, doc_path = argv[0], Path(argv[1])
    log = os.environ.get("FAKE_CALL_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as out:
            out.write(f"engine {verb}\n")
    if os.environ.get("FAKE_ENGINE_REFUSE") == verb:
        return refuse(f"{verb} refused by the fake")
    try:
        doc = json.loads(doc_path.read_text("utf-8"))
    except OSError as error:
        return refuse(str(error), 2)
    if verb == "check":
        problem = check(doc, doc_path)
        if problem:
            return refuse(problem)
        return answer({"ok": True})
    if verb == "render":
        problem = check(doc, doc_path)
        if problem:
            return refuse(problem)
        saved_copy(doc_path).write_text(json.dumps(doc), "utf-8")
        return answer({"ok": True, "page": str(doc_path.with_suffix(".html"))})
    if verb == "show":
        return answer({"ok": True})
    if verb == "poll":
        raw = Path(os.environ["FAKE_POLL_RAW"]).read_bytes().decode("utf-8")
        return answer({"ok": True, "raw": raw})
    if verb == "ingest":
        raw = Path(argv[argv.index("--raw-file") + 1]).read_bytes().decode("utf-8")
        signals = ingest(doc, raw)
        text = json.dumps(doc, indent=2)
        doc_path.write_text(text, "utf-8")
        saved_copy(doc_path).write_text(text, "utf-8")
        return answer({"ok": True, "signals": signals})
    return refuse(f"unknown verb {verb}", 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
