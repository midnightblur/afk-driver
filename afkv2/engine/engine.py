"""The page engine: one command, one JSON answer per verb.

    engine.py check DOC
    engine.py render DOC
    engine.py show DOC [--no-open|--reopen]
    engine.py poll DOC

Answer: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`, the reason naming the
item and the field. Exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
for folder in (ENGINE_DIR.parent / "scripts", ENGINE_DIR):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from afkv2_config import Refusal, data_folder, exit_code, read_config  # noqa: E402

import launcher  # noqa: E402
import registry  # noqa: E402
from schema import invariants  # noqa: E402
from schema.validate import problems  # noqa: E402
from shell import inject, page  # noqa: E402

SCHEMA_V0 = "afkv2.page/0"
SCHEMA_FILES = {SCHEMA_V0: ENGINE_DIR / "schema" / "page-v0.schema.json"}
PAGES_FOLDER = "pages"
MAX_REASONS = 20
THREAD_VARIABLE = "CODEX_THREAD_ID"
COPIES_FOLDER = "page-copies"


def read_v0(raw: dict) -> dict:
    return raw


READERS = {SCHEMA_V0: read_v0}


def load_document(path: str) -> tuple[dict, dict]:
    """The raw document and its reader's in-memory form. Unknown schema values are refused."""
    try:
        raw = json.loads(Path(path).read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Refusal("unreadable", f"document {path}: {error}") from error
    if not isinstance(raw, dict):
        raise Refusal("unreadable", f"document {path}: the file must hold one JSON object")
    version = raw.get("schema")
    if not isinstance(version, str) or version not in READERS:
        known = ", ".join(READERS)
        raise Refusal("unknown-schema", f"item document, field schema: version {version!r} is unknown; known: {known}")
    return raw, READERS[version](raw)


def describe(doc: dict, path: tuple) -> tuple[str, str]:
    """The item name and the dotted field of a problem path from the document root."""
    name, rest = "document", path
    if path[:1] == ("session",):
        name, rest = "session", path[1:]
    elif path[:1] == ("maps",) and len(path) > 1:
        entry = (doc.get("maps") or [None])[path[1]]
        name = f"map {(entry or {}).get('id') or path[1]}"
        rest = path[2:]
    elif path[:1] == ("rounds",) and len(path) > 1:
        round_ = doc["rounds"][path[1]]
        name, rest = f"round {round_.get('n')}" if isinstance(round_, dict) else f"round {path[1]}", path[2:]
        if rest[:1] == ("items",) and len(rest) > 1:
            item = round_["items"][rest[1]]
            name = f"item {item.get('id')}" if isinstance(item, dict) else f"item {rest[1]}"
            rest = rest[2:]
    field = ""
    for part in rest:
        field += f"[{part}]" if isinstance(part, int) else f".{part}" if field else str(part)
    return f"item {name}" if name in ("document", "session") else name, field or "(the whole object)"


def _refuse(doc: dict, found: list[tuple], code: str) -> Refusal:
    lines = []
    for path, why in found[:MAX_REASONS]:
        name, field = describe(doc, path)
        lines.append(f"{name}, field {field}: {why}")
    more = len(found) - MAX_REASONS
    if more > 0:
        lines.append(f"and {more} more")
    return Refusal(code, "; ".join(lines))


def _element_ids(doc: dict) -> tuple[list[tuple], dict, dict]:
    """(uniqueness problems, every id with its path, the map nodes with theirs)."""
    found, ids, nodes = [], {}, {}

    def add(identifier, path) -> None:
        if identifier in ids:
            found.append(((*path, "id"), f"id {identifier!r} is not unique"))
        ids[identifier] = path

    def add_tree(component, base) -> None:
        for sub, part in registry.walk(component, base):
            if part.get("id"):
                add(part["id"], sub)

    for m, map_ in enumerate(doc.get("maps") or []):
        base = ("maps", m)
        add_tree(map_, base)
        props = map_.get("props") or {}
        for n, node in enumerate(props.get("nodes") or []):
            where = (*base, "props", "nodes", n)
            found += _map_node(node, where, len(doc["rounds"]))
            if isinstance(node, dict) and isinstance(node.get("id"), str):
                add(node["id"], where)
                nodes[node["id"]] = where
    for r, round_ in enumerate(doc["rounds"]):
        for i, item in enumerate(round_["items"]):
            base = ("rounds", r, "items", i)
            add(item["id"], base)
            add_tree(item["body"], (*base, "body"))
    return found, ids, nodes


def _map_node(node, where: tuple, last_round: int) -> list[tuple]:
    if not isinstance(node, dict):
        return [(where, "a map node must be an object")]
    found = []
    if not isinstance(node.get("id"), str):
        found.append(((*where, "id"), "is required"))
    if not isinstance(node.get("state"), str):
        found.append(((*where, "state"), "is required"))
    round_ = node.get("round")
    if not isinstance(round_, int) or isinstance(round_, bool) or not 1 <= round_ <= last_round:
        found.append(((*where, "round"), f"must be a round from 1 to {last_round}"))
    return found


def _copy_path(document: Path) -> Path:
    key = os.path.normcase(os.path.abspath(document)).encode("utf-8")
    return data_folder() / COPIES_FOLDER / f"{hashlib.sha256(key).hexdigest()[:12]}.json"


def read_saved_copy(document: Path) -> dict[int, str] | None:
    """The last saved settled rounds, or None when no copy was saved."""
    path = _copy_path(document)
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise Refusal("unreadable", f"last saved copy {path}: {error}") from error
    return {int(n): text for n, text in saved["rounds"].items()}


def save_settled_copy(document: Path, doc: dict) -> None:
    """Save the settled rounds. Ingest calls this too: a late note changes a settled round."""
    rounds = invariants.settled_rounds(doc)
    if rounds:
        record = {"document": str(document), "rounds": {str(n): text for n, text in rounds.items()}}
        inject.write_if_changed(_copy_path(document), json.dumps(record).encode("utf-8"))


def check_document(path: str) -> tuple[dict, str]:
    """A document that passed every check, and what its settled rounds were compared with."""
    raw, doc = load_document(path)
    schema = json.loads(SCHEMA_FILES[raw["schema"]].read_text(encoding="utf-8"))
    found = problems(raw, schema)
    if found:
        raise _refuse(raw, found, "schema")
    found = []
    for m, map_ in enumerate(doc.get("maps") or []):
        found += registry.validate(map_, ("maps", m))
    for r, round_ in enumerate(doc["rounds"]):
        for i, item in enumerate(round_["items"]):
            found += registry.validate(item["body"], ("rounds", r, "items", i, "body"))
    if found:
        raise _refuse(raw, found, "schema")
    found, ids, nodes = _element_ids(doc)
    found += invariants.check_invariants(doc, ids, nodes)
    copy_state = "unavailable"
    try:
        saved = read_saved_copy(Path(path))
    except Refusal as refusal:
        if refusal.code != "no-data-folder":
            raise
    else:
        copy_state = "none" if saved is None else "compared"
        found += invariants.check_rewrite(doc, saved or {})
    if found:
        raise _refuse(raw, found, "invariant")
    return doc, copy_state


def _require_home(path: str, doc: dict) -> Path:
    """The document lives in the spec folder as `pages/<skill>-<session id>.json`, alone with its id."""
    document = Path(path).resolve()
    session = doc["session"]
    expected = f"{session['skill']}-{session['id']}.json"
    if document.name != expected:
        raise Refusal("bad-location", f"item session, field id: the file must be named {expected}, found {document.name}")
    if document.parent.name != PAGES_FOLDER:
        raise Refusal("bad-location", f"item session, field id: {document} must sit in a {PAGES_FOLDER} folder")
    config = read_config(document.parent)
    if not config["ok"]:
        raise Refusal(config["error"]["code"], config["error"]["reason"])
    if not document.is_relative_to(Path(config["spec_folder"]).resolve()):
        raise Refusal("bad-location", f"item session, field id: {document} is outside the spec folder {config['spec_folder']}")
    for other in document.parent.glob(f"*-{session['id']}.json"):
        if other.name != document.name:
            raise Refusal("duplicate-session", f"item session, field id: {session['id']!r} is also used by {other.name}")
    return document


def _render(path: str) -> tuple[dict, Path, Path]:
    doc, _ = check_document(path)
    document = _require_home(path, doc)
    data_folder()
    html_path = document.with_suffix(".html")
    html = inject.inject(page.build(doc), inject.load_dictionary(html_path))
    inject.write_if_changed(html_path, html.encode("utf-8"))
    save_settled_copy(document, doc)
    return doc, document, html_path


def cmd_check(args) -> dict:
    _, copy_state = check_document(args.document)
    return {"ok": True, "verb": "check", "saved_copy": copy_state}


def cmd_render(args) -> dict:
    _, _, html_path = _render(args.document)
    return {"ok": True, "verb": "render", "page": str(html_path)}


def cmd_show(args) -> dict:
    _, document, html_path = _render(args.document)
    argv = ["open", str(html_path)]
    if args.no_open:
        argv.append("--no-open")
    elif args.reopen:
        argv.append("--reopen")
    code, out = launcher.run(argv)
    _raise_host_failure(code, out)
    session = launcher.parse_host_output(out).get("session") or {}
    record = None
    thread = os.environ.get(THREAD_VARIABLE)
    if thread:
        record = str(launcher.write_waiting_record(data_folder(), thread, str(document), str(html_path)))
    return {"ok": True, "verb": "show", "page": str(html_path), "url": session.get("url"),
            "status": session.get("status"), "waiting_record": record}


def _raise_host_failure(code: int, out: str) -> None:
    if code in launcher.FALLBACK_EXITS:
        raise Refusal("markdown-fallback", f"wrapper exit {code}: {out}; use the Markdown fallback")
    if code != 0:
        parsed = launcher.parse_host_output(out)
        raise Refusal("host-error", f"item page, field host: exit {code}: {parsed.get('error') or out.strip()}")


def cmd_poll(args) -> dict:
    html_path = Path(args.document).resolve().with_suffix(".html")
    if not html_path.is_file():
        raise Refusal("unreadable", f"page {html_path}: no rendered page; run render and show first")
    status, detail = launcher.poll_status(["poll", str(html_path)])
    if status == "fallback":
        _raise_host_failure(detail["exit"], detail["reason"])
    if status in ("error", "no-session"):
        raise Refusal("host-error", f"item page, field host: {detail.get('code')}: {detail['reason']}")
    thread = os.environ.get(THREAD_VARIABLE)
    if status in ("feedback", "ended") and thread:
        launcher.clear_waiting_record(data_folder(), thread)
    if status != "feedback":
        raise Refusal(f"page-{status.replace('_', '-')}", f"item page, field status: {status}: no answer to read")
    return {"ok": True, "verb": "poll", "status": status, "raw": detail["raw"],
            "prompts": detail["prompts"], "session_ended": detail["session_ended"]}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise Refusal("usage", message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="engine.py", add_help=False)
    verbs = parser.add_subparsers(dest="verb", required=True, parser_class=_Parser)
    for verb, handler in (("check", cmd_check), ("render", cmd_render), ("show", cmd_show), ("poll", cmd_poll)):
        sub = verbs.add_parser(verb, add_help=False)
        sub.add_argument("document")
        sub.set_defaults(handler=handler)
        if verb == "show":
            mode = sub.add_mutually_exclusive_group()
            mode.add_argument("--no-open", action="store_true")
            mode.add_argument("--reopen", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        answer = args.handler(args)
    except Refusal as refusal:
        answer = {"ok": False, "error": {"code": refusal.code, "reason": refusal.reason}}
    print(json.dumps(answer))
    return exit_code(answer)


if __name__ == "__main__":
    sys.exit(main())
