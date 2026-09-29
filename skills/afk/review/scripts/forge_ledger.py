#!/usr/bin/env python3
"""Store and reconstruct the settle ledger on a forge change."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote, unquote


PLUGIN_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_LEDGER_ONLY_PATHS = ("plan/review/**", "plan/JOURNAL.md")
MARKER_RE = re.compile(r"<!--\s*afk:(finding|record|settle:summary|settle:history|settle:trust)\s+v([^\s]+)\s+([^>]*?)\s*-->")
MARKER_HINT_RE = re.compile(r"<!--\s*afk:(?:finding|record|settle:summary|settle:history|settle:trust)\b")
LEGACY_SUMMARY_RE = re.compile(r"<!--\s*afk:settle-mr:summary\s*-->")
KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/f\d{3,}$")
OUTCOMES = {"dispute", "verdict", "fixed", "verified", "carried", "deferred", "disposition"}
TERMINAL = {"fixed", "verified", "withdrawn", "disposition"}
FINDING_FIELDS = {"id", "concern", "criterion", "severity", "class", "file", "line",
                  "finding", "why", "fix", "evidence"}
HISTORY_FIELDS = {"round", "start_head", "reviewed_head", "code_changed", "keys_new",
                  "keys_remediated", "scope_shape_keys", "agents_md_chain_new",
                  "scope_escalated", "ledger_only", "observed"}
OBSERVED_FIELDS = {"key", "concern", "severity", "class"}


class LedgerError(Exception):
    pass


class UsageError(Exception):
    pass


class LedgerArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def canonical(value):
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [canonical(v) for v in value]
    if isinstance(value, dict):
        return {canonical(str(k)): canonical(v) for k, v in value.items()}
    return value


def canonical_bytes(value):
    return json.dumps(canonical(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def b64(value):
    return base64.urlsafe_b64encode(canonical_bytes(value)).decode().rstrip("=")


def unb64(value):
    return json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))


def enc(value):
    return quote(str(value), safe="")


def norm_path(value):
    value = str(value or "").replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if not value or value.startswith("/") or ".." in value.split("/"):
        raise UsageError(f"invalid repository path: {value!r}")
    return value


def normalize_locator(item):
    side = item.get("side", "new")
    if side not in {"new", "old", "context"}:
        raise UsageError(f"invalid side: {side}")
    file = norm_path(item["file"])
    old_path = norm_path(item.get("old_path") or file)
    new_path = norm_path(item.get("new_path") or file)
    line = item.get("line")
    old_line = item.get("old_line")
    if side == "old":
        old_line = old_line if old_line is not None else line
        line = None
        file = old_path
    elif side == "context":
        old_line = old_line if old_line is not None else line
        file = new_path
    else:
        file = new_path
    return {"file": file, "old_path": old_path, "new_path": new_path,
            "line": line, "old_line": old_line, "side": side}


def normalize_positive_int(value, name):
    try:
        value = int(value)
    except (TypeError, ValueError) as error:
        raise UsageError(f"{name} must be a positive integer") from error
    if value < 1:
        raise UsageError(f"{name} must be a positive integer")
    return value


def validate_finding(item):
    if not isinstance(item, dict):
        raise UsageError("each finding must be an object")
    missing = FINDING_FIELDS - set(item)
    if missing:
        raise UsageError("finding is missing: " + ", ".join(sorted(missing)))
    if item["severity"] not in {"critical", "high", "medium", "low"}:
        raise UsageError("invalid finding severity")
    if item["class"] not in {"correctness", "spec", "compliance", "smell", "scope", "test",
                             "design", "pattern-debt"}:
        if item["class"] == "product-debt":
            raise UsageError("reviewers cannot assign product-debt")
        raise UsageError("invalid finding class")
    if not isinstance(item["line"], int) or item["line"] < 1:
        raise UsageError("finding line must be a positive integer")


def fingerprints(unit, head, finding, locator):
    routing = {
        "unit": unit, "reviewed_head": head,
        "concern": finding.get("concern"), "criterion": finding.get("criterion"),
        "severity": finding.get("severity"), "class": finding.get("class"),
        **locator, "finding": finding.get("finding"), "why": finding.get("why"),
        "fix": finding.get("fix"), "evidence": finding.get("evidence"),
    }
    stable = {"criterion": finding.get("criterion"), "file": locator["file"],
              "finding": finding.get("finding"), "why": finding.get("why"),
              "evidence": finding.get("evidence")}
    return digest(routing), digest(stable)


def make_finding_marker(key, unit, head, finding, locator, moved_from=None):
    rfp, sfp = fingerprints(unit, head, finding, locator)
    attrs = {
        "key": key, "seq": 1, "rfp": rfp, "sfp": sfp,
        "file": locator["file"], "old_path": locator["old_path"],
        "new_path": locator["new_path"], "line": locator.get("line") or "-",
        "old_line": locator.get("old_line") or "-", "side": locator["side"],
        "data": b64(finding),
    }
    if moved_from:
        attrs["moved_from"] = moved_from
    return "<!-- afk:finding v1 " + " ".join(f"{k}={enc(v)}" for k, v in attrs.items()) + " -->"


def operation_id(key, kind, attrs, prior_seq):
    normalized = dict(attrs)
    for name in ("line", "old_line"):
        if normalized.get(name) == "-":
            normalized[name] = None
    if "mapped" in normalized:
        normalized["mapped"] = str(normalized["mapped"])
    if isinstance(normalized.get("data"), str):
        normalized["data"] = unb64(normalized["data"])
    return digest({"key": key, "kind": kind, "attrs": normalized, "prior_seq": prior_seq})[:24]


def make_record_marker(key, seq, kind, attrs, prior_seq=None):
    clean = {k: ("-" if k in {"line", "old_line"} and v is None else v)
             for k, v in attrs.items() if v is not None or k in {"line", "old_line"}}
    op = clean.pop("op", None) or operation_id(key, kind, clean, prior_seq if prior_seq is not None else seq - 1)
    fields = {"key": key, "seq": seq, "kind": kind, "op": op, **clean}
    return "<!-- afk:record v1 " + " ".join(f"{k}={enc(v)}" for k, v in fields.items()) + " -->"


def _attrs(raw):
    result = {}
    for token in shlex.split(raw):
        if "=" not in token:
            raise LedgerError(f"malformed marker attribute: {token}")
        key, value = token.split("=", 1)
        if key in result:
            raise LedgerError(f"duplicate marker attribute: {key}")
        result[key] = unquote(value)
    return result


def parse_marker(text):
    match = MARKER_RE.search(text)
    if not match:
        raise LedgerError("marker not found")
    tag, version, raw = match.groups()
    if version != "1":
        raise LedgerError(f"unknown marker version: {tag} v{version}")
    value = _attrs(raw)
    value["tag"] = tag
    if "seq" in value:
        try:
            value["seq"] = int(value["seq"])
        except ValueError as error:
            raise LedgerError("marker seq is not an integer") from error
    for name in ("line", "old_line"):
        if name in value:
            try:
                value[name] = None if value[name] == "-" else int(value[name])
            except (TypeError, ValueError) as error:
                raise LedgerError(f"marker {name} is not an integer") from error
    if "data" in value:
        try:
            value["data"] = unb64(value["data"])
        except (ValueError, TypeError) as error:
            raise LedgerError("marker data is not valid base64url JSON") from error
    return value


def parse_markers(text):
    text = text or ""
    matches = list(MARKER_RE.finditer(text))
    if len(matches) != len(MARKER_HINT_RE.findall(text)):
        raise LedgerError("malformed trusted marker")
    return [parse_marker(m.group(0)) for m in matches]


def _require_fields(marker, required, optional=()):
    actual = set(marker) - {"tag", "entry"}
    required, optional = set(required), set(optional)
    if actual != required | (actual & optional):
        missing = required - actual
        extra = actual - required - optional
        detail = []
        if missing:
            detail.append("missing " + ", ".join(sorted(missing)))
        if extra:
            detail.append("extra " + ", ".join(sorted(extra)))
        raise LedgerError("invalid marker fields: " + "; ".join(detail))


def validate_marker(marker):
    tag = marker["tag"]
    if tag == "finding":
        _require_fields(marker, {"key", "seq", "rfp", "sfp", "file", "old_path", "new_path",
                                 "line", "old_line", "side", "data"}, {"moved_from"})
        if not KEY_RE.fullmatch(marker["key"]) or marker["seq"] != 1:
            raise LedgerError("invalid finding key or sequence")
        try:
            validate_finding(marker["data"])
        except UsageError as error:
            raise LedgerError(str(error)) from error
        if marker["side"] not in {"new", "old", "context"}:
            raise LedgerError("invalid finding side")
        return
    if tag == "record":
        base = {"key", "seq", "kind", "op"}
        kind_fields = {
            "dispute": (set(), set()), "verdict": ({"result", "reason"}, set()),
            "fixed": ({"sha", "path", "line", "side"}, set()),
            "verified": ({"sha", "path", "line", "side"}, set()),
            "carried": (set(), set()), "deferred": ({"gate"}, set()),
            "disposition": ({"result"}, {"home"}),
            "seen": ({"head", "data", "file", "old_path", "new_path", "line", "old_line", "side"}, {"mapped"}),
            "reclassified": ({"data"}, set()), "move-intent": ({"to"}, set()),
            "moved": ({"to"}, set()), "move-failed": ({"note", "move_op"}, set()),
        }
        kind = marker.get("kind")
        if kind not in kind_fields:
            raise LedgerError(f"unknown record kind: {kind}")
        required, optional = kind_fields[kind]
        _require_fields(marker, base | required, optional)
        if not KEY_RE.fullmatch(marker["key"]) or marker["seq"] < 2 or not marker["op"]:
            raise LedgerError("invalid record key, sequence, or operation id")
        if kind in {"seen", "reclassified"}:
            try:
                validate_finding(marker["data"])
            except UsageError as error:
                raise LedgerError(str(error)) from error
        return
    if tag == "settle:summary":
        _require_fields(marker, {"unit", "round", "reviewed_head", "clean", "ledger_only"})
        if marker["clean"] not in {"true", "false"} or marker["ledger_only"] not in {"true", "false"}:
            raise LedgerError("invalid summary boolean")
        try:
            marker["round"] = int(marker["round"])
        except (TypeError, ValueError) as error:
            raise LedgerError("invalid summary round") from error
        return
    if tag == "settle:history":
        _require_fields(marker, {"data"})
        return
    if tag == "settle:trust":
        _require_fields(marker, {"trusted", "rejected"})
        return
    raise LedgerError(f"unknown marker kind: {tag}")


def validate_record_attrs(key, kind, attrs, seq):
    reserved = {"key", "seq", "kind", "op"} & set(attrs)
    if reserved:
        raise UsageError("record attributes use reserved names: " + ", ".join(sorted(reserved)))
    marker = {"tag": "record", "key": key, "seq": seq, "kind": kind,
              "op": operation_id(key, kind, attrs, seq - 1), **attrs}
    try:
        validate_marker(marker)
    except LedgerError as error:
        raise UsageError(str(error)) from error


class ParsedDiff(set):
    def __init__(self):
        super().__init__()
        self.renames = {}
        self.context = {}


def _decode_git_quoted_path(text):
    data = bytearray()
    index = 1
    escapes = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12,
               "r": 13, '"': 34, "\\": 92}
    while index < len(text):
        char = text[index]
        if char == '"':
            try:
                return data.decode("utf-8"), text[index + 1:]
            except UnicodeDecodeError as error:
                raise UsageError("Git path is not valid UTF-8") from error
        if char != "\\":
            data.extend(char.encode("utf-8"))
            index += 1
            continue
        index += 1
        if index >= len(text):
            raise UsageError("unterminated Git path escape")
        char = text[index]
        if char in "01234567":
            end = index
            while end < len(text) and end < index + 3 and text[end] in "01234567":
                end += 1
            value = int(text[index:end], 8)
            if value > 0xFF:
                raise UsageError("Git path escape is out of byte range")
            data.append(value)
            index = end
            continue
        if char not in escapes:
            raise UsageError(f"unknown Git path escape: \\{char}")
        data.append(escapes[char])
        index += 1
    raise UsageError("unterminated quoted Git path")


def _git_path_field(text, prefix=None):
    if text.startswith('"'):
        value, _ = _decode_git_quoted_path(text)
    else:
        value = text.split("\t", 1)[0]
    if value == "/dev/null":
        return None
    if prefix and value.startswith(prefix):
        value = value[len(prefix):]
    return value


def _diff_header_paths(text):
    if text.startswith('"'):
        old_path, rest = _decode_git_quoted_path(text)
        rest = rest.lstrip()
        if not rest:
            return old_path, None
        if rest.startswith('"'):
            new_path, tail = _decode_git_quoted_path(rest)
            if tail.strip():
                raise UsageError("trailing diff header text")
        else:
            new_path = _git_path_field(rest)
        return old_path, new_path
    separator = text.rfind(" b/")
    if separator < 0:
        return None, None
    return text[:separator], text[separator + 1:]


def parse_diff(text):
    result = ParsedDiff()
    old_path = new_path = None
    old_line = new_line = None
    old_remaining = new_remaining = 0
    in_hunk = False
    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            header_old, header_new = _diff_header_paths(raw[11:].lstrip())
            old_path = _git_path_field(header_old or "", "a/") if header_old else None
            new_path = _git_path_field(header_new or "", "b/") if header_new else None
            in_hunk = False
        elif raw.startswith("@@"):
            match = re.search(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", raw)
            if not match:
                continue
            old_line = int(match.group(1))
            new_line = int(match.group(3))
            old_remaining = int(match.group(2) or 1)
            new_remaining = int(match.group(4) or 1)
            in_hunk = bool(old_remaining or new_remaining)
        elif in_hunk and raw.startswith("\\ No newline"):
            continue
        elif in_hunk and raw.startswith(" "):
            if new_path is not None:
                result.add((new_path, new_line, "new"))
                result.add((new_path, new_line, "context"))
            if old_path is not None:
                result.add((old_path, old_line, "old"))
            if new_path is not None and old_path is not None:
                result.context[(new_path, new_line)] = (old_path, old_line)
            old_line += 1
            new_line += 1
            old_remaining -= 1
            new_remaining -= 1
            in_hunk = bool(old_remaining or new_remaining)
        elif in_hunk and raw.startswith("-"):
            if old_path is not None:
                result.add((old_path, old_line, "old"))
            old_line += 1
            old_remaining -= 1
            in_hunk = bool(old_remaining or new_remaining)
        elif in_hunk and raw.startswith("+"):
            if new_path is not None:
                result.add((new_path, new_line, "new"))
            new_line += 1
            new_remaining -= 1
            in_hunk = bool(old_remaining or new_remaining)
        elif raw.startswith("rename from "):
            old_path = _git_path_field(raw[12:])
        elif raw.startswith("rename to "):
            new_path = _git_path_field(raw[10:])
            result.renames[new_path] = old_path
        elif raw.startswith("--- "):
            old_path = _git_path_field(raw[4:], "a/")
        elif raw.startswith("+++ "):
            new_path = _git_path_field(raw[4:], "b/")
    return result


def locator_from_diff(item, parsed_diff):
    locator = normalize_locator(item)
    if not isinstance(parsed_diff, ParsedDiff):
        return locator
    new_path = norm_path(item["file"])
    old_path = parsed_diff.renames.get(new_path, locator["old_path"])
    locator["new_path"] = new_path
    locator["old_path"] = old_path
    if locator["side"] == "old":
        locator["file"] = old_path
    elif locator["side"] == "context":
        pair = parsed_diff.context.get((new_path, locator["line"]))
        if pair:
            locator["old_path"], locator["old_line"] = pair
    return locator


def resolved_locator(item, parsed_diff, hint=None):
    locator = locator_from_diff(item, parsed_diff)
    if hint is None:
        return locator
    if not isinstance(hint, dict):
        raise UsageError("each locator hint must be an object")
    candidate = locator_from_diff({**item, **hint}, parsed_diff)
    same_target = (candidate["old_path"] == locator["old_path"] and
                   candidate["new_path"] == locator["new_path"] and
                   candidate["side"] == locator["side"])
    if same_target and is_anchorable(candidate, parsed_diff):
        return candidate
    return locator


def locator_values(value):
    return {name: value.get(name) for name in
            ("file", "old_path", "new_path", "line", "old_line", "side")}


def same_finding(left, right):
    return canonical_bytes(left) == canonical_bytes(right)


def is_anchorable(locator, parsed_diff):
    if locator["side"] == "old":
        return (locator["old_path"], locator.get("old_line"), "old") in parsed_diff
    return (locator["new_path"], locator.get("line"), locator["side"]) in parsed_diff


def validate_transition(previous, kind, attrs):
    if kind not in OUTCOMES and kind not in {"seen", "moved", "move-intent", "move-failed", "reclassified"}:
        raise UsageError(f"unknown record kind: {kind}")
    if kind == "disposition" and attrs.get("result") not in {"pattern-debt", "product-debt"}:
        raise UsageError("disposition result must be pattern-debt or product-debt")
    if kind == "disposition" and attrs.get("result") == "product-debt" and not attrs.get("home"):
        raise UsageError("product-debt disposition requires home")
    if kind in {"fixed", "verified"} and attrs.get("side") not in {"new", "old", "context"}:
        raise UsageError(f"{kind} side must be new, old, or context")
    if kind == "deferred" and not attrs.get("gate"):
        raise UsageError("deferred requires gate")
    if kind == "reclassified":
        terminal = previous and (
            previous.get("kind") in {"fixed", "verified", "disposition"} or
            previous.get("kind") == "verdict" and
            previous.get("attrs", {}).get("result") == "withdrawn"
        )
        if terminal:
            raise LedgerError("reclassified follows a terminal outcome")
        return
    if kind in {"moved", "move-intent", "move-failed", "seen"}:
        return
    state = None
    if previous:
        state = previous.get("kind")
        if state == "verdict":
            state = "verdict " + previous.get("attrs", {}).get("result", "")
        if state == "disposition" or state in {"fixed", "verified"}:
            raise LedgerError(f"illegal transition from terminal {state}")
        if state == "verdict withdrawn":
            raise LedgerError("illegal transition from terminal verdict withdrawn")
    allowed = {
        None: {"dispute", "fixed", "verified", "carried", "deferred", "disposition"},
        "carried": {"dispute", "fixed", "verified", "carried", "deferred", "disposition"},
        "dispute": {"verdict"},
        "verdict stands": {"fixed", "verified", "carried", "dispute", "disposition"},
        "deferred": {"fixed", "verified", "dispute", "disposition", "carried"},
    }
    if kind not in allowed.get(state, set()):
        raise LedgerError(f"illegal transition: {state or 'none'} -> {kind}")
    if kind == "verdict" and attrs.get("result") not in {"withdrawn", "stands"}:
        raise UsageError("verdict result must be withdrawn or stands")
    if kind == "disposition":
        result = attrs.get("result")
        if result == "product-debt" and state != "verdict stands":
            raise LedgerError("product-debt requires verdict stands")
        if result == "pattern-debt" and state == "verdict stands":
            raise LedgerError("stands can only become product-debt")


def _glob_regex(pattern):
    pattern = norm_path(pattern)
    if pattern.startswith("!"):
        raise UsageError("ledger-only globs do not support negation")
    out, index = [], 0
    while index < len(pattern):
        if pattern[index:index + 3] == "**/":
            out.append("(?:[^/]+/)*")
            index += 3
        elif pattern[index:index + 2] == "**":
            out.append(".*")
            index += 2
        elif pattern[index] == "*":
            out.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(pattern[index]))
            index += 1
    return re.compile("^" + "".join(out) + "$", re.ASCII)


def is_ledger_only(path, patterns):
    path = norm_path(path)
    return any(_glob_regex(pattern).fullmatch(path) for pattern in patterns)


def trailers(keys):
    values = []
    for key in keys.split(","):
        key = key.strip()
        if not key or not KEY_RE.fullmatch(key):
            raise UsageError(f"invalid ledger key: {key!r}")
        if key not in values:
            values.append(key)
    if not values:
        raise UsageError("at least one key is required")
    return {"trailers": [f"Settles: {key}" for key in values]}


def validate_trust(trusted, rejected):
    overlap = trusted & rejected
    if overlap:
        raise UsageError("authors cannot be both trusted and rejected: " + ", ".join(sorted(overlap)))


def classify_author(author, trusted, rejected):
    if author in trusted:
        return "trusted"
    if author in rejected:
        return "rejected"
    raise LedgerError("unclassified_authors: " + str(author))


def scan_entries(entries, trusted, rejected):
    found, unclassified = [], set()
    ignored = edited = 0
    for entry in entries:
        body = entry.get("body", "")
        marker_bearing = bool(MARKER_HINT_RE.search(body) or LEGACY_SUMMARY_RE.search(body))
        if not marker_bearing:
            continue
        if entry.get("updated_at") and entry.get("created_at") and entry["updated_at"] > entry["created_at"]:
            edited += 1
            continue
        author = entry.get("author", "")
        if author in rejected:
            ignored += 1
            continue
        if author not in trusted:
            unclassified.add(author)
            continue
        markers = parse_markers(body)
        if LEGACY_SUMMARY_RE.search(body):
            markers.append({"tag": "settle:summary", "unit": "change", "round": 0,
                            "reviewed_head": "", "clean": "false", "ledger_only": "false"})
        for marker in markers:
            validate_marker(marker)
        found.append((entry, markers))
    return SimpleNamespace(found=found, ignored_untrusted=ignored,
                           unclassified_authors=sorted(unclassified), edited_markers=edited)


def append_history(old, entry):
    if entry.get("round") is None:
        raise UsageError("history entry needs round")
    for index, prior in enumerate(old):
        if prior.get("round") == entry["round"]:
            if prior != entry:
                raise LedgerError("history prefix changed")
            return old
        if index and prior.get("round", 0) <= old[index - 1].get("round", 0):
            raise LedgerError("history rounds are not increasing")
    if old and entry["round"] <= old[-1].get("round", 0):
        raise LedgerError("history prefix changed")
    return [*old, entry]


def validate_history_entry(entry, unit, allowed_keys):
    if not isinstance(entry, dict) or set(entry) != HISTORY_FIELDS:
        raise LedgerError("history fields do not match the record grammar")
    if isinstance(entry["round"], bool) or not isinstance(entry["round"], int) or entry["round"] < 1:
        raise LedgerError("history round must be a positive integer")
    for name in ("start_head", "reviewed_head"):
        if not isinstance(entry[name], str) or not entry[name]:
            raise LedgerError(f"history {name} must be a non-empty string")
    for name in ("code_changed", "scope_escalated", "ledger_only"):
        if not isinstance(entry[name], bool):
            raise LedgerError(f"history {name} must be a boolean")
    for name in ("keys_new", "keys_remediated", "scope_shape_keys", "agents_md_chain_new", "observed"):
        if not isinstance(entry[name], list):
            raise LedgerError(f"history {name} must be a list")
    for name in ("keys_new", "keys_remediated", "scope_shape_keys"):
        if any(not isinstance(key, str) or key not in allowed_keys for key in entry[name]):
            raise LedgerError(f"history {name} contains a key outside unit {unit}")
        if len(entry[name]) != len(set(entry[name])):
            raise LedgerError(f"history {name} contains duplicate keys")
    if any(not isinstance(path, str) or not path for path in entry["agents_md_chain_new"]):
        raise LedgerError("history agents_md_chain_new contains an invalid path")
    for item in entry["observed"]:
        if not isinstance(item, dict) or set(item) != OBSERVED_FIELDS:
            raise LedgerError("history observed item has invalid fields")
        if item["key"] not in allowed_keys:
            raise LedgerError(f"history observed contains a key outside unit {unit}")
        if any(not isinstance(item[name], str) or not item[name]
               for name in ("concern", "severity", "class")):
            raise LedgerError("history observed item has invalid routing")
    observed_keys = [item["key"] for item in entry["observed"]]
    if len(observed_keys) != len(set(observed_keys)):
        raise LedgerError("history observed contains duplicate keys")
    if not set(entry["keys_new"] + entry["keys_remediated"]).issubset(observed_keys):
        raise LedgerError("history key accounting is outside observed")


def parse_adapter_output(stdout, mode):
    lines = stdout.splitlines()
    if len(lines) != 1:
        raise LedgerError("adapter wrote extra stdout")
    try:
        value = json.loads(lines[0])
    except (ValueError, TypeError) as error:
        raise LedgerError("adapter returned invalid JSON") from error
    if not isinstance(value, dict):
        raise LedgerError("adapter answer is not an object")
    if mode == "move" and value.get("error") and value.get("note"):
        return value
    if any(value.get(k) for k in ("error", "unsupported", "unavailable")):
        raise LedgerError(value.get("reason") or "adapter operation failed")
    if mode == "write" and value.get("ok") is not True:
        raise LedgerError("adapter write did not return ok:true")
    if mode == "move" and value.get("ok") is not True and not value.get("cleaned"):
        raise LedgerError(value.get("reason") or "inline move failed without cleanup")
    return value


def find_bash():
    for variable in ("AFK_BASH", "GIT_BASH"):
        named = os.environ.get(variable)
        if named and Path(named).is_file():
            return Path(named)
    found = shutil.which("bash")
    if found:
        return Path(found)
    if os.name == "nt":
        for base in (os.environ.get("ProgramW6432", r"C:\Program Files"),
                     os.environ.get("LOCALAPPDATA", "")):
            candidate = Path(base) / "Git" / "bin" / "bash.exe"
            if candidate.is_file():
                return candidate
    return None


def shell_env(bash):
    env = dict(os.environ)
    if os.name == "nt":
        root = bash.resolve().parent.parent
        extra = [root / "bin", root / "usr" / "bin", root / "mingw64" / "bin"]
        env["PATH"] = os.pathsep.join([str(p) for p in extra if p.is_dir()] + [env.get("PATH", "")])
    return env


class Adapter:
    def __init__(self, cwd=None):
        self.cwd = Path(cwd or Path.cwd())
        self.root = Path(os.environ.get("AFK_PLUGIN_ROOT", PLUGIN_ROOT))

    def call(self, verb, payload, mode="read"):
        seam = os.environ.get("AFK_LEDGER_ADAPTER_CMD")
        env = dict(os.environ)
        env["AFK_PLUGIN_ROOT"] = str(self.root)
        if seam:
            command = [*shlex.split(seam), verb]
        else:
            bash = find_bash()
            if not bash:
                raise LedgerError("bash is unavailable")
            env = shell_env(bash)
            env["AFK_PLUGIN_ROOT"] = str(self.root)
            command = [str(bash), "-c", '. "$AFK_PLUGIN_ROOT/hooks/lib/adapter.sh"; afk_adapter forge "$1"', "--", verb]
        run = subprocess.run(command, cwd=self.cwd, env=env, input=json.dumps(payload),
                             text=True, capture_output=True)
        if run.returncode != 0:
            raise LedgerError(run.stderr.strip() or f"adapter {verb} exited {run.returncode}")
        value = parse_adapter_output(run.stdout, mode)
        required = {
            "change-view": {"url", "head_sha", "base_sha", "head_ref", "blob_base", "cross_fork"}, "change-diff": {"diff"},
            "note-list": {"notes", "count"}, "thread-list": {"threads", "count"},
        }.get(verb, set())
        missing = required - set(value)
        if missing:
            raise LedgerError(f"adapter {verb} omitted: " + ", ".join(sorted(missing)))
        if verb == "change-view":
            for name in ("url", "head_sha", "base_sha", "head_ref", "blob_base"):
                if not isinstance(value[name], str):
                    raise LedgerError(f"adapter change-view field is not a string: {name}")
            if not isinstance(value["cross_fork"], bool):
                raise LedgerError("adapter change-view field is not a boolean: cross_fork")
        return value


def _author(value):
    if isinstance(value, dict):
        return value.get("username") or value.get("login") or value.get("name") or ""
    return str(value or "")


def dedupe_notes(notes):
    by_id = {}
    order = []
    for note in notes:
        note_id = str(note.get("id", ""))
        if not note_id:
            raise LedgerError("note is missing id")
        prior = by_id.get(note_id)
        if prior is None:
            order.append(note_id)
            by_id[note_id] = note
            continue
        prior_time = prior.get("updated_at", "")
        new_time = note.get("updated_at", "")
        if new_time == prior_time and note.get("body", "") != prior.get("body", ""):
            raise LedgerError(f"duplicate note id has divergent bodies: {note_id}")
        if new_time > prior_time:
            by_id[note_id] = note
    return [by_id[note_id] for note_id in order]


def _entries(notes, threads):
    result = []
    for note in dedupe_notes(notes.get("notes", [])):
        result.append({**note, "thread": "", "resolved": False, "url": note.get("url", ""), "inline": False})
    for thread in threads.get("threads", []):
        for note in dedupe_notes(thread.get("notes", [])):
            result.append({**note, "thread": str(thread.get("id", "")),
                           "resolved": bool(thread.get("resolved")),
                           "url": thread.get("url") or note.get("url", ""), "inline": True})
    return dedupe_notes(result)


def reconstruct_state(adapter, change, trust=(), reject=()):
    auth = adapter.call("auth-status", {})
    current = _author(auth.get("user") or auth.get("username") or auth.get("login"))
    trusted, rejected = set(trust), set(reject)
    if current:
        trusted.add(current)
    validate_trust(trusted, rejected)
    view = adapter.call("change-view", {"id": change})
    notes = adapter.call("note-list", {"id": change})
    threads = adapter.call("thread-list", {"id": change})
    entries = _entries(notes, threads)
    scan = scan_entries(entries, trusted, rejected)
    if scan.edited_markers:
        raise LedgerError(f"edited_markers: {scan.edited_markers}")
    if scan.unclassified_authors:
        raise LedgerError("unclassified_authors: " + ", ".join(scan.unclassified_authors))
    origins, records, summaries = {}, {}, {}
    for entry, markers in scan.found:
        for marker in markers:
            marker["entry"] = entry
            if marker["tag"] == "finding":
                origins.setdefault(marker["key"], []).append(marker)
            elif marker["tag"] == "record":
                records.setdefault(marker["key"], []).append(marker)
            elif marker["tag"] == "settle:summary":
                unit = marker.get("unit", "change")
                summaries.setdefault(unit, []).append(marker)
    orphan_records = set(records) - set(origins)
    if orphan_records:
        raise LedgerError("record has no finding origin: " + ", ".join(sorted(orphan_records)))
    units = {}
    for key, key_origins in origins.items():
        unit = key.rsplit("/f", 1)[0]
        unit_data = units.setdefault(unit, {"round": None, "reviewed_head": None, "clean": False,
                                            "next_key": 1, "keys": {}, "history": []})
        recs = records.get(key, [])
        failed_notes = {str(r.get("note")) for r in recs if r.get("kind") == "move-failed"}
        key_origins = [origin for origin in key_origins
                       if str(origin["entry"].get("id")) not in failed_notes]
        if not key_origins:
            raise LedgerError(f"finding has no valid origin: {key}")
        by_seq = {}
        for rec in recs:
            prior = by_seq.get(rec["seq"])
            signature = {k: v for k, v in rec.items() if k != "entry"}
            if prior and prior != signature:
                raise LedgerError(f"duplicate seq with different content: {key} seq {rec['seq']}")
            by_seq[rec["seq"]] = signature
        recs = [next(r for r in recs if r["seq"] == seq) for seq in sorted(by_seq)]
        expected_sequences = list(range(2, 2 + len(recs)))
        if [rec["seq"] for rec in recs] != expected_sequences:
            raise LedgerError(f"record sequence is not contiguous: {key}")
        previous = None
        for rec in recs:
            attrs = {name: value for name, value in rec.items()
                     if name not in {"entry", "tag", "key", "seq", "kind", "op"}}
            expected_op = operation_id(key, rec["kind"], attrs, rec["seq"] - 1)
            if rec.get("op") != expected_op:
                raise LedgerError(f"record operation id is invalid: {key} seq {rec['seq']}")
            try:
                validate_transition(previous, rec["kind"], attrs)
            except UsageError as error:
                raise LedgerError(str(error)) from error
            if rec["kind"] in OUTCOMES:
                previous = {"kind": rec["kind"], "attrs": attrs}
        move_ids = {r.get("op") for r in recs if r.get("kind") == "move-intent"}
        valid_pairs = [o for o in key_origins if o.get("moved_from") in move_ids]
        if len(key_origins) > 1 and len(valid_pairs) != len(key_origins) - 1:
            raise LedgerError(f"duplicate finding origin: {key}")
        active = max(key_origins, key=lambda o: (o["entry"].get("created_at", ""), o["entry"].get("inline", False)))
        moved = [r for r in recs if r.get("kind") == "moved"]
        if moved:
            target = moved[-1].get("to")
            active = next((o for o in key_origins if o["entry"].get("url") == target), active)
        outcome_rec = None
        for rec in recs:
            if rec.get("kind") in OUTCOMES:
                outcome_rec = rec
        seen = [r for r in recs if r.get("kind") == "seen"]
        current_loc = seen[-1] if seen else active
        locator_names = ("file", "old_path", "new_path", "line", "old_line", "side")
        locator_current = all(active.get(n) == current_loc.get(n) for n in locator_names)
        routing_rec = next((r for r in reversed(recs) if r.get("kind") == "reclassified"), None)
        finding = seen[-1].get("data") if seen else active["data"]
        routing_data = finding if seen else (routing_rec.get("data") if routing_rec else finding)
        if isinstance(routing_data, str):
            routing_data = unb64(routing_data)
        severity = routing_data.get("severity")
        outcome_attrs = ({k: v for k, v in outcome_rec.items()
                          if k not in {"entry", "tag", "key", "seq", "kind", "op"}}
                         if outcome_rec else None)
        disposition = outcome_attrs if outcome_rec and outcome_rec.get("kind") == "disposition" else None
        verdict = outcome_attrs if outcome_rec and outcome_rec.get("kind") == "verdict" else None
        fix = outcome_attrs if outcome_rec and outcome_rec.get("kind") in {"fixed", "verified"} else None
        threads_seen = {}
        for origin in key_origins:
            thread = origin["entry"].get("thread")
            if thread:
                threads_seen[thread] = {"id": thread, "resolved": origin["entry"].get("resolved", False),
                                        "url": origin["entry"].get("url", "")}
        outcome_name = None
        if outcome_rec:
            outcome_name = outcome_rec["kind"]
            if outcome_name == "verdict":
                outcome_name = "verdict " + outcome_rec.get("result", "")
        if seen:
            current_rfp, current_sfp = fingerprints(unit, seen[-1].get("head", ""), finding, {
                n: current_loc.get(n) for n in locator_names
            })
        else:
            current_rfp, current_sfp = active.get("rfp"), active.get("sfp")
        unit_data["keys"][key] = {
            "outcome": outcome_name, "seq": max([1] + [r["seq"] for r in recs]),
            "record_id": active["entry"].get("id", ""), "thread": active["entry"].get("thread", ""),
            "anchored": bool(active["entry"].get("inline")), "location": active["entry"].get("url", ""),
            **{n: current_loc.get(n) for n in locator_names}, "sfp": current_sfp, "rfp": current_rfp,
            "origin_rfp": active.get("rfp"),
            "fix": fix, "verdict": verdict, "disposition": disposition,
            "deferred_gate": outcome_attrs.get("gate") if outcome_rec and outcome_rec.get("kind") == "deferred" else None,
            "ever_deferred_to": list(dict.fromkeys(r.get("gate") for r in recs if r.get("kind") == "deferred")),
            "routing": {"concern": routing_data.get("concern"), "severity": severity,
                        "class": routing_data.get("class"), "blocks_ship": severity in {"critical", "high"}},
            "finding": finding, "locator_current": locator_current,
            "threads": list(threads_seen.values()), "records": recs,
            "pending_move": bool(active.get("moved_from") and
                                 not any(r.get("to") == active["entry"].get("url") for r in moved)),
        }
        try:
            number = int(key.rsplit("/f", 1)[1])
            unit_data["next_key"] = max(unit_data["next_key"], number + 1)
        except ValueError:
            raise LedgerError(f"invalid key: {key}")
    for unit, notes_for_unit in summaries.items():
        data = units.setdefault(unit, {"round": None, "reviewed_head": None, "clean": False,
                                       "next_key": 1, "keys": {}, "history": []})
        allowed_keys = set(data["keys"])
        if unit == "feature":
            allowed_keys.update(key for other in units.values() for key, value in other["keys"].items()
                                if "feature" in value.get("ever_deferred_to", []))
        by_round = {}
        for summary in notes_for_unit:
            round_number = summary.get("round", 0)
            if round_number in by_round:
                raise LedgerError(f"duplicate summary: {unit} round {round_number}")
            by_round[round_number] = summary
            markers = parse_markers(summary["entry"].get("body", ""))
            history_markers = [m for m in markers if m["tag"] == "settle:history"]
            if round_number and len(history_markers) != 1:
                raise LedgerError(f"summary needs one history marker: {unit} round {round_number}")
            if history_markers:
                entry = history_markers[0].get("data")
                validate_history_entry(entry, unit, allowed_keys)
                if entry["round"] != round_number or entry["reviewed_head"] != summary.get("reviewed_head"):
                    raise LedgerError("summary and history disagree")
                data["history"] = append_history(data["history"], entry)
        latest = by_round[max(by_round)]
        data.update(round=max(by_round), reviewed_head=latest.get("reviewed_head"),
                    clean=latest.get("clean") == "true", ledger_only=latest.get("ledger_only") == "true")
    return {"head_sha": view.get("head_sha", ""), "base_sha": view.get("base_sha", ""),
            "blob_base": view.get("blob_base", ""), "cross_fork": bool(view.get("cross_fork")),
            "units": units, "ignored_untrusted": scan.ignored_untrusted,
            "edited_markers": scan.edited_markers, "unclassified_authors": scan.unclassified_authors,
            "trusted": sorted(trusted), "rejected": sorted(rejected)}


def public_state(state, unit=None):
    units = state["units"]
    if unit is not None:
        units = {unit: units.get(unit, {"round": None, "reviewed_head": None, "clean": False,
                                       "next_key": 1, "keys": {}, "history": []})}
    clean = json.loads(json.dumps(units, default=str))
    for value in clean.values():
        for key in value.get("keys", {}).values():
            key.pop("records", None)
            key.pop("origin_rfp", None)
    return {"head_sha": state["head_sha"], "units": clean,
            "ignored_untrusted": state["ignored_untrusted"], "edited_markers": state["edited_markers"]}


def _human_finding(finding, key):
    return f"{finding.get('file')}:{finding.get('line')} [{key}] {finding.get('finding')}\n\n{finding.get('why')}\n\nFix: {finding.get('fix')}"


def _post_comment(adapter, change, text, locator=None, require_inline=False):
    payload = {"id": change, "text": text}
    if locator:
        payload.update(locator)
        if require_inline:
            payload["require_inline"] = True
    return adapter.call("change-comment", payload, "move" if require_inline else "write")


def _record(adapter, change, key_state, key, kind, attrs, text):
    seq = key_state["seq"] + 1
    marker = make_record_marker(key, seq, kind, attrs, key_state["seq"])
    body = (text + "\n\n" + marker).strip()
    if key_state.get("thread"):
        answer = adapter.call("thread-reply", {"id": change, "thread": key_state["thread"], "text": body}, "write")
    else:
        answer = _post_comment(adapter, change, body)
    key_state["seq"] = seq
    key_state.setdefault("records", []).append({"tag": "record", "key": key, "seq": seq,
                                                  "kind": kind, **attrs})
    return answer, marker


def command_reply(args, adapter):
    state = reconstruct_state(adapter, args.change, args.trust, args.reject)
    unit = args.key.rsplit("/f", 1)[0]
    key_state = state["units"].get(unit, {}).get("keys", {}).get(args.key)
    if not key_state:
        raise LedgerError(f"unknown key: {args.key}")
    attrs = dict(args.attr or [])
    for name in ("sha", "path", "line", "side", "result", "reason", "gate", "home",
                 "to", "head", "data", "mapped"):
        value = getattr(args, name, None)
        if value is not None:
            attrs[name] = value
    if "line" in attrs:
        attrs["line"] = normalize_positive_int(attrs["line"], "line")
    if "path" in attrs:
        attrs["path"] = norm_path(attrs["path"])
    previous = None
    for rec in reversed(key_state["records"]):
        if rec.get("kind") in OUTCOMES:
            previous = {"kind": rec["kind"], "attrs": rec}
            break
    validate_record_attrs(args.key, args.kind, attrs, key_state["seq"] + 1)
    latest = key_state["records"][-1] if key_state["records"] else None
    if latest and latest.get("kind") == args.kind:
        replay_op = operation_id(args.key, args.kind, attrs, latest["seq"] - 1)
        if latest.get("op") == replay_op:
            return {"ok": True, "key": args.key, "idempotent": True, "op": replay_op}
    validate_transition(previous, args.kind, attrs)
    state = _repair_all_pending(adapter, args.change, state, args.trust, args.reject)
    key_state = state["units"][unit]["keys"][args.key]
    permalink = None
    target_project_fallback = False
    if args.kind in {"fixed", "verified"}:
        for name in ("sha", "path", "line", "side"):
            if name not in attrs:
                raise UsageError(f"{args.kind} requires {name}")
        view = adapter.call("change-view", {"id": args.change})
        sha = attrs["sha"]
        if attrs["side"] == "old":
            parent = subprocess.run(["git", "rev-parse", f"{sha}^"], cwd=adapter.cwd,
                                    text=True, capture_output=True)
            if parent.returncode == 0:
                sha = parent.stdout.strip()
        base = (view.get("blob_base") or "").rstrip("/")
        if not base:
            change_url = view.get("url", "").rstrip("/")
            if re.search(r"/pull/\d+$", change_url):
                base = re.sub(r"/pull/\d+$", "/blob", change_url)
            elif re.search(r"/-/merge_requests/\d+$", change_url):
                base = re.sub(r"/-/merge_requests/\d+$", "/-/blob", change_url)
            else:
                raise LedgerError("forge did not provide a target-project blob prefix")
            target_project_fallback = True
        permalink = f"{base}/{sha}/{quote(attrs['path'], safe='/')}#L{attrs['line']}"
        fallback_note = "\n\nTarget project fallback used." if target_project_fallback else ""
        args.text = args.text.rstrip() + fallback_note + "\n\n" + permalink
        if not key_state["anchored"]:
            diff_answer = adapter.call("change-diff", {"id": args.change})
            locator = normalize_locator({"file": attrs["path"], "line": attrs["line"],
                                         "side": attrs["side"]})
            if is_anchorable(locator, parse_diff(diff_answer.get("diff", ""))):
                if _move_key(adapter, args.change, args.key, key_state, key_state["finding"],
                             locator, state["head_sha"]):
                    state = reconstruct_state(adapter, args.change, args.trust, args.reject)
                    key_state = state["units"][unit]["keys"][args.key]
    op = operation_id(args.key, args.kind, attrs, key_state["seq"])
    if any(rec.get("op") == op for rec in key_state["records"]):
        return {"ok": True, "key": args.key, "idempotent": True}
    attrs["op"] = op
    _record(adapter, args.change, key_state, args.key, args.kind, attrs, args.text)
    result = {"ok": True, "key": args.key, "kind": args.kind, "op": op}
    if permalink:
        result.update(permalink=permalink, target_project_fallback=target_project_fallback)
    return result


def command_resolve(args, adapter):
    state = reconstruct_state(adapter, args.change, args.trust, args.reject)
    unit = args.key.rsplit("/f", 1)[0]
    key_state = state["units"].get(unit, {}).get("keys", {}).get(args.key)
    if not key_state:
        raise LedgerError(f"unknown key: {args.key}")
    state = _repair_all_pending(adapter, args.change, state, args.trust, args.reject)
    key_state = state["units"][unit]["keys"][args.key]
    if not key_state["threads"]:
        return {"resolved": False, "resolvable": False, "key": args.key}
    resolved = True
    for thread in key_state["threads"]:
        desired = not args.reopen
        if thread["resolved"] == desired:
            continue
        try:
            adapter.call("thread-resolve", {"id": args.change, "thread": thread["id"], "resolved": desired}, "write")
        except LedgerError:
            resolved = False
    return {"resolved": resolved, "resolvable": True, "key": args.key}


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError) as error:
        raise UsageError(f"cannot read JSON from {path}: {error}") from error


def ledger_only_patterns(cwd):
    script = PLUGIN_ROOT / "scripts" / "afk-config.py"
    run = subprocess.run([sys.executable, str(script), "effective"], cwd=cwd,
                         text=True, capture_output=True)
    if run.returncode == 0:
        try:
            value = json.loads(run.stdout).get("review", {}).get("ledger-only-paths")
            if isinstance(value, list) and value:
                return value
        except (ValueError, AttributeError):
            pass
    return list(DEFAULT_LEDGER_ONLY_PATHS)


def changed_paths(cwd, start, end):
    if not start or not end:
        raise LedgerError("history needs start_head and reviewed_head")
    run = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", "-z", start, end, "--"],
        cwd=cwd, capture_output=True)
    if run.returncode:
        raise LedgerError(os.fsdecode(run.stderr).strip() or "cannot derive changed paths")
    return [norm_path(os.fsdecode(path)) for path in run.stdout.split(b"\0") if path]


def derive_observed(unit_state, head, extra_keys=None):
    prior = {item.get("key") for entry in unit_state.get("history", [])
             for item in entry.get("observed", []) if isinstance(item, dict)}
    observed = []
    available = dict(unit_state.get("keys", {}))
    available.update(extra_keys or {})
    for key, value in available.items():
        seen_here = any(record.get("kind") == "seen" and record.get("head") == head
                        for record in value.get("records", []))
        locator = {name: value.get(name) for name in
                   ("file", "old_path", "new_path", "line", "old_line", "side")}
        origin_here = fingerprints(key.rsplit("/f", 1)[0], head, value["finding"], locator)[0] == value["rfp"]
        if (key not in prior and origin_here) or seen_here:
            observed.append({"key": key, "concern": value["routing"]["concern"],
                             "severity": value["routing"]["severity"],
                             "class": value["routing"]["class"]})
    return observed


def _same_locator(key_state, locator):
    return all(key_state.get(name) == locator.get(name)
               for name in ("file", "old_path", "new_path", "line", "old_line", "side"))


def _move_key(adapter, change, key, key_state, finding, locator, head, close_new=False):
    intent_attrs = {"to": b64(locator)}
    _, intent_marker = _record(adapter, change, key_state, key, "move-intent", intent_attrs,
                               "Move this finding to its current exact line.")
    intent_op = parse_marker(intent_marker)["op"]
    marker = make_finding_marker(key, key.rsplit("/f", 1)[0], head, finding, locator,
                                 moved_from=intent_op)
    answer = _post_comment(adapter, change, _human_finding(finding, key) + "\n\n" + marker,
                           locator, require_inline=True)
    if not answer.get("inline"):
        _record(adapter, change, key_state, key, "move-failed",
                {"note": answer.get("note") or answer.get("comment", ""), "move_op": intent_op},
                "The forge could not keep the replacement comment inline.")
        return False
    _record(adapter, change, key_state, key, "moved", {"to": answer.get("url", "")},
            "The finding moved to its current exact line.")
    if close_new and answer.get("thread"):
        adapter.call("thread-resolve", {"id": change, "thread": answer["thread"], "resolved": True}, "write")
    return True


def _repair_pending_move(adapter, change, key_state, key):
    if not key_state.get("pending_move"):
        return False
    intent = next((record for record in reversed(key_state.get("records", []))
                   if record.get("kind") == "move-intent"), None)
    record_state = key_state
    if intent and intent.get("entry", {}).get("thread"):
        record_state = {**key_state, "thread": intent["entry"]["thread"]}
    _record(adapter, change, record_state, key, "moved", {"to": key_state.get("location", "")},
            "The interrupted move now has its durable location record.")
    return True


def _repair_all_pending(adapter, change, state, trust=(), reject=()):
    repaired = False
    for unit_state in state["units"].values():
        for key, key_state in unit_state.get("keys", {}).items():
            repaired = _repair_pending_move(adapter, change, key_state, key) or repaired
    if repaired:
        return reconstruct_state(adapter, change, trust, reject)
    return state


def _keys_for_unit(state, unit):
    unit_state = state["units"].get(unit, {"next_key": 1, "keys": {}})
    existing = dict(unit_state["keys"])
    if unit == "feature":
        for other in state["units"].values():
            for key, value in other.get("keys", {}).items():
                if "feature" in value.get("ever_deferred_to", []):
                    existing.setdefault(key, value)
    return unit_state, existing


def _hint_for(hints, index, finding):
    if isinstance(hints, list):
        return hints[index] if index < len(hints) else None
    if isinstance(hints, dict):
        return hints.get(str(index), hints.get(finding.get("id")))
    raise UsageError("hints file must contain a list or object")


def _seen_matches(value, finding, locator, head):
    seen = [record for record in value.get("records", []) if record.get("kind") == "seen"]
    if not seen:
        return False
    current = seen[-1]
    return (current.get("head") == head and same_finding(current.get("data"), finding) and
            locator_values(current) == locator)


def _post_retry_key(existing, unit, finding, locator, head):
    for key, value in existing.items():
        key_unit = key.rsplit("/f", 1)[0]
        origin_rfp = fingerprints(key_unit, head, finding, locator)[0]
        origin_retry = (key_unit == unit and value.get("outcome") is None and
                        value.get("origin_rfp") == origin_rfp)
        if origin_retry or _seen_matches(value, finding, locator, head):
            return key
    return None


def _validate_post_matches(findings, locators, mapping, existing, unit, head):
    used = set()
    for index, (finding, locator) in enumerate(zip(findings, locators)):
        if _post_retry_key(existing, unit, finding, locator, head):
            continue
        sfp = fingerprints(unit, head, finding, locator)[1]
        candidates = [key for key, value in existing.items()
                      if value["sfp"] == sfp and key not in used]
        requested = mapping.get(str(index), mapping.get(finding.get("id")))
        if requested == "new":
            candidates = []
        elif requested:
            if requested not in existing:
                raise LedgerError(f"map names unknown key: {requested}")
            if _terminal(existing[requested]):
                raise LedgerError(f"map target is not open: {requested}")
            candidates = [requested]
        if len(candidates) > 1:
            raise LedgerError("ambiguous sfp: " + ", ".join(candidates))
        if candidates:
            used.add(candidates[0])


def command_post(args, adapter):
    state = reconstruct_state(adapter, args.change, args.trust, args.reject)
    findings = _load_json(args.findings)
    if not isinstance(findings, list):
        raise UsageError("findings file must contain a JSON list")
    for finding in findings:
        validate_finding(finding)
    diff = parse_diff(Path(args.diff).read_text(encoding="utf-8"))
    hints = _load_json(args.hints) if args.hints else {}
    mapping = _load_json(args.map) if args.map else {}
    if not isinstance(mapping, dict):
        raise UsageError("map file must contain an object")
    requested_keys = [value for value in mapping.values() if value != "new"] if isinstance(mapping, dict) else []
    if len(requested_keys) != len(set(requested_keys)):
        raise LedgerError("map targets must be one-to-one")
    locators = [resolved_locator(finding, diff, _hint_for(hints, index, finding))
                for index, finding in enumerate(findings)]
    _, before_repair = _keys_for_unit(state, args.unit)
    for requested in requested_keys:
        if requested not in before_repair:
            raise LedgerError(f"map names unknown key: {requested}")
        if _terminal(before_repair[requested]):
            raise LedgerError(f"map target is not open: {requested}")
    _validate_post_matches(findings, locators, mapping, before_repair, args.unit, args.head)
    state = _repair_all_pending(adapter, args.change, state, args.trust, args.reject)
    unit_state, existing = _keys_for_unit(state, args.unit)
    output = {"posted": 0, "anchored": 0, "unanchored": 0, "reused_closed": 0,
              "reused_open": 0, "stale_locator": 0,
              "ignored_untrusted": state["ignored_untrusted"], "keys": {}}
    next_key = unit_state["next_key"]
    used = set()
    for index, finding in enumerate(findings):
        locator = locators[index]
        rfp, sfp = fingerprints(args.unit, args.head, finding, locator)
        retry = _post_retry_key(existing, args.unit, finding, locator, args.head)
        candidates = [k for k, v in existing.items() if v["sfp"] == sfp and k not in used]
        requested = mapping.get(str(index), mapping.get(finding.get("id")))
        if requested == "new":
            candidates = []
        elif requested:
            if requested not in existing:
                raise LedgerError(f"map names unknown key: {requested}")
            if _terminal(existing[requested]):
                raise LedgerError(f"map target is not open: {requested}")
            candidates = [requested]
        if retry:
            key = retry
            used.add(key)
            _repair_pending_move(adapter, args.change, existing[key], key)
            output["reused_open"] += 1
            output["keys"][key] = {"record_id": existing[key]["record_id"],
                                   "thread": existing[key]["thread"], "anchored": existing[key]["anchored"]}
            continue
        if len(candidates) > 1:
            raise LedgerError("ambiguous sfp: " + ", ".join(candidates))
        if candidates:
            key = candidates[0]
            used.add(key)
            old = existing[key]
            kind = "reused_closed" if old["outcome"] in {"verdict withdrawn", "disposition"} else "reused_open"
            if old["outcome"] in {"fixed", "verified"}:
                candidates = []
            else:
                output[kind] += 1
                _repair_pending_move(adapter, args.change, old, key)
                routing = old["routing"]
                if kind == "reused_open" and any(
                        routing.get(name) != finding.get(name) for name in ("concern", "severity", "class")):
                    _record(adapter, args.change, old, key, "reclassified", {"data": b64(finding)},
                            "The current review changes this finding's routing.")
                if not _same_locator(old, locator):
                    if is_anchorable(locator, diff) and _move_key(
                            adapter, args.change, key, old, finding, locator, args.head,
                            close_new=kind == "reused_closed"):
                        key_unit = key.rsplit("/f", 1)[0]
                        old = reconstruct_state(adapter, args.change, args.trust, args.reject)["units"][key_unit]["keys"][key]
                    else:
                        output["stale_locator"] += 1
                seen_attrs = {**locator, "head": args.head, "data": b64(finding)}
                if requested:
                    seen_attrs["mapped"] = 1
                _record(adapter, args.change, old, key, "seen", seen_attrs, f"Seen again at {args.head}.")
                output["keys"][key] = {"record_id": old["record_id"], "thread": old["thread"],
                                       "anchored": old["anchored"]}
                continue
        key = f"{args.unit}/f{next_key:03d}"
        next_key += 1
        marker = make_finding_marker(key, args.unit, args.head, finding, locator)
        anchor = is_anchorable(locator, diff)
        answer = _post_comment(adapter, args.change, _human_finding(finding, key) + "\n\n" + marker,
                               locator if anchor else None)
        anchored = bool(answer.get("inline"))
        output["posted"] += 1
        output["anchored" if anchored else "unanchored"] += 1
        output["keys"][key] = {"record_id": answer.get("comment", ""),
                               "thread": answer.get("thread", ""), "anchored": anchored}
    if args.state:
        target = Path(args.state)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(json.dumps(output, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, target)
    return output


def command_summary(args, adapter):
    state = reconstruct_state(adapter, args.change, args.trust, args.reject)
    history = _load_json(args.history_file)
    if not isinstance(history, dict):
        raise UsageError("history file must contain one object")
    unit_state = state["units"].get(args.unit, {"keys": {}, "history": []})
    extra = {}
    if args.unit == "feature":
        for other in state["units"].values():
            for key, value in other.get("keys", {}).items():
                if "feature" in value.get("ever_deferred_to", []):
                    extra[key] = value
    available_keys = {**unit_state.get("keys", {}), **extra}
    validate_history_entry(history, args.unit, set(available_keys))
    if history["round"] != args.round or history["reviewed_head"] != args.head:
        raise LedgerError("history round or reviewed_head does not match summary")
    old = unit_state.get("history", [])
    if unit_state.get("round") == args.round:
        if unit_state.get("reviewed_head") == args.head and old and history == old[-1]:
            _repair_all_pending(adapter, args.change, state, args.trust, args.reject)
            return {"ok": True, "idempotent": True, "unit": args.unit, "round": args.round}
        raise LedgerError("duplicate summary")
    derived_start = old[-1]["reviewed_head"] if old else state["base_sha"]
    if history["start_head"] != derived_start:
        raise LedgerError("history start_head does not match the durable round boundary")
    derived_observed = derive_observed(unit_state, args.head, extra)
    if history["observed"] != derived_observed:
        raise LedgerError("history observed does not match the durable round findings")
    paths = changed_paths(adapter.cwd, derived_start, args.head)
    patterns = ledger_only_patterns(adapter.cwd)
    derived_code_changed = any(not is_ledger_only(path, patterns) for path in paths)
    if history["code_changed"] != derived_code_changed:
        raise LedgerError("history code_changed does not match the changed paths")
    prior_keys = {item.get("key") for entry in unit_state.get("history", [])
                  for item in entry.get("observed", []) if isinstance(item, dict)}
    current_keys = [item["key"] for item in derived_observed]
    derived_new = [key for key in current_keys if key not in prior_keys]
    derived_remediated = [key for key in current_keys if _terminal(available_keys[key])]
    if history["keys_new"] != derived_new or history["keys_remediated"] != derived_remediated:
        raise LedgerError("history key accounting does not match the durable round findings")
    if history["ledger_only"] != args.ledger_only:
        raise LedgerError("history ledger_only does not match summary")
    if args.ledger_only:
        bad_paths = [path for path in paths if not is_ledger_only(path, patterns)]
        bad_keys = [item["key"] for item in derived_observed
                    if not is_ledger_only(available_keys[item["key"]]["file"], patterns)]
        if bad_paths or bad_keys:
            raise LedgerError("ledger_only includes non-ledger paths or findings: " +
                              ", ".join(bad_paths + bad_keys))
    state = _repair_all_pending(adapter, args.change, state, args.trust, args.reject)
    append_history(old, history)
    text = Path(args.text_file).read_text(encoding="utf-8").strip()
    summary = (f"<!-- afk:settle:summary v1 unit={enc(args.unit)} round={args.round} reviewed_head={enc(args.head)} "
               f"clean={str(args.clean).lower()} ledger_only={str(args.ledger_only).lower()} -->")
    trust = (f"<!-- afk:settle:trust v1 trusted={enc(','.join(state['trusted']))} "
             f"rejected={enc(','.join(state['rejected']))} -->")
    history_marker = f"<!-- afk:settle:history v1 data={b64(history)} -->"
    answer = _post_comment(adapter, args.change, "\n\n".join((summary, text, history_marker, trust)))
    return {"ok": True, "note": answer.get("comment", ""), "unit": args.unit, "round": args.round}


def _terminal(key):
    return key["outcome"] in {"fixed", "verified", "verdict withdrawn", "disposition"}


def known_debt_has_key(path, key):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return False
    match = re.search(r"(?ms)^## Known debt\s*$\n(.*?)(?=^##\s|\Z)", text)
    return bool(match and re.search(rf"(?m)^.*\bledger:\s*{re.escape(key)}(?:\s|$).*$", match.group(1)))


def _progress_match(key, value, finding, locator, diff, head):
    current = locator_values(value)
    if not value.get("locator_current") or not same_finding(value.get("finding"), finding):
        return False
    direct = current == locator
    same_target = (current["old_path"] == locator["old_path"] and
                   current["new_path"] == locator["new_path"] and
                   current["side"] == locator["side"])
    corrected = (not is_anchorable(locator, diff) and same_target and
                 is_anchorable(current, diff))
    if not direct and not corrected:
        return False
    key_unit = key.rsplit("/f", 1)[0]
    origin_rfp = fingerprints(key_unit, head, finding, current)[0]
    return value.get("origin_rfp") == origin_rfp or _seen_matches(value, finding, current, head)


def command_gate(args, adapter):
    state = reconstruct_state(adapter, args.change, args.trust, args.reject)
    unit = state["units"].get(args.unit, {"keys": {}, "history": []})
    if args.phase == "progress":
        expected = _load_json(args.expected) if args.expected else []
        if not expected:
            return {"ok": True, "clean": True}
        if not isinstance(expected, list):
            raise UsageError("expected findings file must contain a list")
        diff = parse_diff(adapter.call("change-diff", {"id": args.change}).get("diff", ""))
        keys = dict(unit.get("keys", {}))
        if args.unit == "feature":
            for other in state["units"].values():
                for key, value in other.get("keys", {}).items():
                    if "feature" in value.get("ever_deferred_to", []):
                        keys[key] = value
        missing = []
        for finding in expected:
            validate_finding(finding)
            locator = resolved_locator(finding, diff)
            if not any(_progress_match(key, value, finding, locator, diff, args.head)
                       for key, value in keys.items()):
                missing.append(finding.get("id", finding.get("file")))
        if missing:
            raise LedgerError("progress gate missing durable current findings: " + ", ".join(missing))
        return {"ok": True, "clean": False}
    if state["head_sha"] != args.head:
        raise LedgerError("forge head moved")
    if state.get("cross_fork"):
        raise LedgerError("cross-fork changes cannot be certified by local settle commits")
    if unit.get("round") != args.round or unit.get("reviewed_head") != args.head:
        raise LedgerError("summary does not describe the requested final head and round")
    if not unit.get("clean") and not unit.get("ledger_only"):
        raise LedgerError("final summary is neither clean nor ledger-only")
    keys = dict(unit.get("keys", {}))
    if args.unit == "feature":
        for other in state["units"].values():
            for key, value in other.get("keys", {}).items():
                if "feature" in value.get("ever_deferred_to", []):
                    keys[key] = value
    for key, value in keys.items():
        if value.get("pending_move"):
            raise LedgerError(f"key has an incomplete move: {key}")
        if not value["anchored"] or not value["locator_current"]:
            raise LedgerError(f"key has no current inline location: {key}")
        if not _terminal(value):
            if value["outcome"] == "deferred" and args.unit not in {"change", "feature"}:
                continue
            raise LedgerError(f"key is open: {key}")
        if any(not thread["resolved"] for thread in value["threads"]):
            raise LedgerError(f"thread is unresolved: {key}")
        if value["outcome"] == "disposition" and value["disposition"].get("result") == "product-debt":
            home = value["disposition"].get("home")
            if not home or not known_debt_has_key(Path(adapter.cwd) / home, key):
                raise LedgerError(f"product-debt home is missing: {key}")
        if value["outcome"] == "fixed":
            sha = value["fix"].get("sha")
            ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", sha, args.head], cwd=adapter.cwd)
            if ancestor.returncode:
                raise LedgerError(f"fix commit is not reachable: {key}")
            message = subprocess.run(["git", "show", "-s", "--format=%B", sha], cwd=adapter.cwd,
                                     text=True, capture_output=True)
            if message.returncode or f"Settles: {key}" not in message.stdout:
                raise LedgerError(f"fix commit lacks trailer: {key}")
    return {"ok": True, "settled": True, "unit": args.unit, "round": args.round}


def parse_bool(value):
    if value not in {"true", "false"}:
        raise argparse.ArgumentTypeError("expected true or false")
    return value == "true"


def parser():
    root = LedgerArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    def trust_flags(p):
        p.add_argument("--trust", action="append", default=[])
        p.add_argument("--reject", action="append", default=[])
    p = sub.add_parser("reconstruct"); p.add_argument("--change", required=True); p.add_argument("--unit"); trust_flags(p)
    p = sub.add_parser("trailers"); p.add_argument("--keys", required=True)
    p = sub.add_parser("post"); p.add_argument("--change", required=True); p.add_argument("--unit", required=True); p.add_argument("--findings", required=True); p.add_argument("--diff", required=True); p.add_argument("--head", required=True); p.add_argument("--hints"); p.add_argument("--map"); p.add_argument("--state"); trust_flags(p)
    p = sub.add_parser("reply"); p.add_argument("--change", required=True); p.add_argument("--key", required=True); p.add_argument("--kind", required=True); p.add_argument("--attr", action="append", nargs=2, metavar=("NAME", "VALUE")); p.add_argument("--text", required=True); p.add_argument("--state")
    for name in ("sha", "path", "line", "side", "result", "reason", "gate", "home", "to", "head", "data", "mapped"):
        p.add_argument("--" + name.replace("_", "-"))
    trust_flags(p)
    p = sub.add_parser("resolve"); p.add_argument("--change", required=True); p.add_argument("--key", required=True); p.add_argument("--reopen", action="store_true"); p.add_argument("--state"); trust_flags(p)
    p = sub.add_parser("summary"); p.add_argument("--change", required=True); p.add_argument("--unit", required=True); p.add_argument("--round", required=True, type=int); p.add_argument("--head", required=True); p.add_argument("--clean", required=True, type=parse_bool); p.add_argument("--ledger-only", required=True, type=parse_bool); p.add_argument("--text-file", required=True); p.add_argument("--history-file", required=True); p.add_argument("--state"); trust_flags(p)
    p = sub.add_parser("gate"); p.add_argument("--change", required=True); p.add_argument("--unit", required=True); p.add_argument("--phase", choices=("progress", "closure"), required=True); p.add_argument("--head", required=True); p.add_argument("--expected"); p.add_argument("--round", type=int); p.add_argument("--state"); trust_flags(p)
    return root


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == "trailers":
            result = trailers(args.keys)
        else:
            adapter = Adapter()
            if args.command == "reconstruct":
                result = public_state(reconstruct_state(adapter, args.change, args.trust, args.reject), args.unit)
            elif args.command == "post": result = command_post(args, adapter)
            elif args.command == "reply": result = command_reply(args, adapter)
            elif args.command == "resolve": result = command_resolve(args, adapter)
            elif args.command == "summary": result = command_summary(args, adapter)
            elif args.command == "gate": result = command_gate(args, adapter)
            else: raise UsageError("unknown command")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        state_path = getattr(args, "state", None)
        if state_path and args.command != "post":
            target = Path(state_path)
            temp = target.with_suffix(target.suffix + ".tmp")
            temp.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(temp, target)
        return 0
    except UsageError as error:
        print(json.dumps({"error": True, "reason": str(error)}, sort_keys=True))
        return 3
    except LedgerError as error:
        print(json.dumps({"ok": False, "reason": str(error)}, sort_keys=True))
        return 2
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({"error": True, "reason": str(error)}, sort_keys=True))
        return 3


if __name__ == "__main__":
    sys.exit(main())
