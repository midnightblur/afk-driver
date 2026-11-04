"""The page engine: one command, one JSON answer per verb.

    engine.py check DOC
    engine.py render DOC
    engine.py show DOC [--no-open|--reopen]
    engine.py poll DOC [--reply-file FILE]
    engine.py reply DOC --reply-file FILE
    engine.py end DOC
    engine.py ingest DOC --raw-file FILE

Show opens a browser tab only when no tab shows the page: a tab that show opened stays the page's tab
until a poll answers that the session ended or the browser left, or end runs. The host reloads that tab
when render rewrites the page.

Poll builds `raw` from the host's prompts against DOC (`prompt_lines.py`), in the grammar of `ingest.py`,
and lists the side questions of the send apart, in `btw`. A reply file holds Markdown the page shows.
Poll keeps a round send in `<DOC stem>.delivery.json` before it reads it; a later poll answers from that
file, and a successful ingest deletes it. An ingest that refuses the response moves the file to
`<DOC stem>.refused.<stamp>.json`.

Answer: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`, the reason naming the
item and the field. Exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
for folder in (ENGINE_DIR.parent / "scripts", ENGINE_DIR):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from afkv2_config import Refusal, data_folder, exit_code, read_config  # noqa: E402

import btw_listener  # noqa: E402
import ingest  # noqa: E402
import launcher  # noqa: E402
import prompt_lines  # noqa: E402
import registry  # noqa: E402
import side_question  # noqa: E402
from schema import invariants, note_rules  # noqa: E402
from schema.validate import problems  # noqa: E402
from shell import inject, page  # noqa: E402

SCHEMA_V0 = "afkv2.page/0"
SCHEMA_V1 = "afkv2.page/1"
SCHEMA_FILES = registry.SCHEMA_FILES
PAGES_FOLDER = "pages"
MAX_REASONS = 20
THREAD_VARIABLE = "CODEX_THREAD_ID"
COPIES_FOLDER = "page-copies"
TABS_FOLDER = "page-tabs"
TAB_GONE = {"ended", "browser_disconnected", "no-session"}
DELIVERY_SUFFIX = ".delivery.json"


def read_v0(raw: dict) -> dict:
    return raw


def _read_page_v1(raw: dict) -> dict:
    return raw


READERS = {SCHEMA_V0: read_v0, SCHEMA_V1: _read_page_v1}


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
        entry = doc["maps"][path[1]]
        name = f"map {(entry.get('id') if isinstance(entry, dict) else None) or path[1]}"
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
    """(uniqueness problems, every id with its path, the map nodes with theirs). A map held in a card
    or a table cell counts as a map; an entry of the `maps` list is a map whatever its type. The banner
    of each round is an element too (`note_rules.round_target`)."""
    found, ids, nodes = [], {}, {}
    last_round = len(doc["rounds"])

    def add(identifier, path) -> None:
        if identifier in ids:
            found.append(((*path, "id"), f"id {identifier!r} is not unique"))
        ids[identifier] = path

    def add_nodes(map_, base) -> None:
        for n, node in enumerate((map_.get("props") or {}).get("nodes") or []):
            where = (*base, "props", "nodes", n)
            found.extend(_map_node(node, where, last_round))
            if isinstance(node, dict) and isinstance(node.get("id"), str):
                add(node["id"], where)
                nodes[node["id"]] = where

    def add_tree(component, base, root_is_map=False) -> None:
        for sub, part in registry.walk(component, base):
            if part.get("id"):
                add(part["id"], sub)
            if part["type"] == "map" or (root_is_map and sub == base):
                add_nodes(part, sub)

    for r, round_ in enumerate(doc["rounds"]):
        add(note_rules.round_target(round_["n"]), ("rounds", r, "banner"))
    for m, map_ in enumerate(doc.get("maps") or []):
        add_tree(map_, ("maps", m), root_is_map=True)
    for r, round_ in enumerate(doc["rounds"]):
        for i, item in enumerate(round_["items"]):
            base = ("rounds", r, "items", i)
            add(item["id"], base)
            add_tree(item["body"], (*base, "body"))
    return found, ids, nodes


def _page_tip_problems(doc: dict, ids: dict) -> list[tuple]:
    """Check typed page/1 catalogs without discarding duplicate source entries.

    Term identity follows shell/tips.js: lowercase keys ignore case; other keys
    keep their case. A trailing s/es may vary in case when the token exceeds 2
    UTF-16 units. IDs match only the complete, same-case element ID.
    """
    if doc["schema"] != SCHEMA_V1:
        return []
    found = []
    tips = doc.get("tips", {})
    for catalog, key in (("terms", "term"), ("ids", "id")):
        exact, folded, insensitive = {}, {}, {}
        for index, entry in enumerate(tips.get(catalog, [])):
            token = entry[key]
            path = ("tips", catalog, index, key)
            if catalog == "ids" and (token not in ids or ids[token][-1] == "banner"):
                found.append((path, f"id {token!r} must reference an existing card, component, or map node"))
            ignore_case = catalog == "terms" and token == token.lower()
            forms = {token}
            if catalog == "terms":
                units = sum(2 if ord(char) > 0xFFFF else 1 for char in token)
                forms.update(token + tail for tail in ("s", "S", "es", "eS", "Es", "ES")
                             if units + len(tail) > 2)
            conflicts = set()
            for form in forms:
                previous = folded.get(form.lower()) if ignore_case else exact.get(form)
                if previous is not None:
                    conflicts.add(previous)
                if catalog == "terms" and form.lower() in insensitive:
                    conflicts.add(insensitive[form.lower()])
            for previous in sorted(conflicts):
                found.append((path, f"matches the same token as tips.{catalog}[{previous}].{key}"))
            for form in forms:
                exact.setdefault(form, index)
                folded.setdefault(form.lower(), index)
                if ignore_case:
                    insensitive.setdefault(form.lower(), index)
    return found


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


def _keyed_path(folder: str, file: Path) -> Path:
    key = os.path.normcase(os.path.abspath(file)).encode("utf-8")
    return data_folder() / folder / f"{hashlib.sha256(key).hexdigest()[:12]}.json"


def _copy_path(document: Path) -> Path:
    return _keyed_path(COPIES_FOLDER, document)


def tab_record(html_path: Path) -> Path:
    """The record that a browser tab shows the page; the host keeps no such state that the engine can read."""
    return _keyed_path(TABS_FOLDER, html_path)


def _forget_tab(html_path: Path) -> None:
    try:
        tab_record(html_path).unlink(missing_ok=True)
    except Refusal as refusal:
        if refusal.code != "no-data-folder":
            raise


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


def _content_problems(raw: dict, doc: dict) -> list[tuple]:
    """The invariant problems of a document. A problem of schema or component shape is refused here."""
    schema = json.loads(SCHEMA_FILES[raw["schema"]].read_text(encoding="utf-8"))
    found = problems(raw, schema)
    if found:
        raise _refuse(raw, found, "schema")
    found = []
    for m, map_ in enumerate(doc.get("maps") or []):
        found += registry.validate(map_, ("maps", m), schema_name=doc["schema"])
    for r, round_ in enumerate(doc["rounds"]):
        for i, item in enumerate(round_["items"]):
            found += registry.validate(item["body"], ("rounds", r, "items", i, "body"), schema_name=doc["schema"])
    if found:
        raise _refuse(raw, found, "schema")
    found, ids, nodes = _element_ids(doc)
    return found + _page_tip_problems(doc, ids) + invariants.check_invariants(doc, ids, nodes)


def check_document(path: str) -> tuple[dict, str]:
    """A document that passed every check, and what its settled rounds were compared with."""
    raw, doc = load_document(path)
    found = _content_problems(raw, doc)
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


def _check_changed(doc: dict) -> None:
    """Every check but the settled-round compare: ingest may change a settled round, and saves the copy."""
    found = _content_problems(doc, doc)
    if found:
        raise _refuse(doc, found, "invariant")


def _save_settled_copy_if_possible(document: Path, doc: dict) -> None:
    try:
        save_settled_copy(document, doc)
    except Refusal as refusal:
        if refusal.code != "no-data-folder":
            raise


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
    html = inject.inject(page.build(doc, btw_listener.address(document)), inject.load_dictionary(html_path))
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
    tab = tab_record(html_path)
    reused = not (args.no_open or args.reopen) and tab.is_file()
    if args.no_open or reused:
        argv.append("--no-open")
    elif args.reopen:
        argv.append("--reopen")
    code, out = launcher.run(argv)
    _raise_host_failure(code, out)
    session = launcher.parse_host_output(out).get("session") or {}
    if session.get("status") != "opened":
        reused = False
        tab.unlink(missing_ok=True)
    elif "--no-open" not in argv:
        inject.write_if_changed(tab, json.dumps({"page": str(html_path), "url": session.get("url")}).encode("utf-8"))
    record = None
    thread = os.environ.get(THREAD_VARIABLE)
    if thread:
        record = str(launcher.write_waiting_record(data_folder(), thread, str(document), str(html_path)))
    return {"ok": True, "verb": "show", "page": str(html_path), "url": session.get("url"),
            "status": session.get("status"), "tab": "reused" if reused else None, "waiting_record": record}


def _raise_host_failure(code: int, out: str) -> None:
    if code in launcher.FALLBACK_EXITS:
        raise Refusal("markdown-fallback", f"wrapper exit {code}: {out}; use the Markdown fallback")
    if code != 0:
        parsed = launcher.parse_host_output(out)
        raise Refusal("host-error", f"item page, field host: exit {code}: {parsed.get('error') or out.strip()}")


def _shown_page(document: str) -> Path:
    html_path = Path(document).resolve().with_suffix(".html")
    if not html_path.is_file():
        raise Refusal("unreadable", f"page {html_path}: no rendered page; run render and show first")
    return html_path


def _reply_flag(args) -> list[str]:
    if args.reply_file is None:
        return []
    if not Path(args.reply_file).is_file():
        raise Refusal("unreadable", f"reply file {args.reply_file} does not exist")
    return ["--agent-reply-file", str(args.reply_file)]


def cmd_reply(args) -> dict:
    """Show a reply on the open page and return; the host exits once it accepts the reply."""
    code, out = launcher.run(["reply", str(_shown_page(args.document)), *_reply_flag(args)])
    _raise_host_failure(code, out)
    return {"ok": True, "verb": "reply"}


def cmd_end(args) -> dict:
    """End the page session: the page shows 'Session ended' in place of 'Working...'."""
    html_path = _shown_page(args.document)
    code, out = launcher.run(["end", str(html_path)])
    _raise_host_failure(code, out)
    _forget_tab(html_path)
    return {"ok": True, "verb": "end"}


def delivery_file(document: str) -> Path:
    """Where a send that the host handed over waits, beside its document, until ingest reads it."""
    return Path(document).with_suffix(DELIVERY_SUFFIX)


def kept_delivery(document: str) -> dict | None:
    """The kept send `{"prompts", "session_ended"}`, or None when no round answer waits."""
    try:
        kept = json.loads(delivery_file(document).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(kept, dict) or not isinstance(kept.get("prompts"), list):
        return None
    if not prompt_lines.split_side_questions(kept["prompts"])[0]:
        delivery_file(document).unlink(missing_ok=True)  # no round answer: nothing for ingest
        return None
    return kept


def keep_delivery(document: str, detail: dict) -> bool:
    """Keep a send that holds a round answer; True when kept.

    The host forgets a send once it hands it over, so the send must be on disk before anything else
    reads it. Only the round prompts are kept: the poll that took the send answers its side questions,
    and a replay must not ask them again."""
    round_prompts, _ = prompt_lines.split_side_questions(detail.get("prompts") or [])
    if not round_prompts:
        return False
    kept = {"prompts": round_prompts, "session_ended": detail.get("session_ended") is True}
    inject.write_if_changed(delivery_file(document), json.dumps(kept, indent=2, ensure_ascii=False).encode("utf-8"))
    return True


def cmd_poll(args) -> dict:
    """With `--reply-file`, the host shows that reply on the page, then waits.

    A kept send that ingest has not read answers first, with no host poll. `btw` holds the side
    questions of the send; they never enter `raw`. `round_prompts` counts the prompts left for the
    round: 0 means the send held side questions only. A send that ends the session with no round
    prompt answers as `page-ended`. While the host poll waits, the side-question listener
    (`btw_listener.py`) answers the page's btw? panel."""
    html_path = _shown_page(args.document)
    detail = kept_delivery(args.document)
    status = "feedback"
    if detail is None:
        with btw_listener.Listener(args.document, side_question.ask):
            status, detail = launcher.poll_status(["poll", str(html_path), *_reply_flag(args)])
        if status == "feedback":
            keep_delivery(args.document, detail)
    if status == "feedback" and detail.get("session_ended") and not prompt_lines.split_side_questions(
            detail.get("prompts") or [])[0]:
        status = "ended"
    if status == "fallback":
        _raise_host_failure(detail["exit"], detail["reason"])
    if status in ("error", "no-session"):
        raise Refusal("host-error", f"item page, field host: {detail.get('code')}: {detail['reason']}")
    if status in TAB_GONE or (status == "feedback" and detail.get("session_ended")):
        _forget_tab(html_path)
    thread = os.environ.get(THREAD_VARIABLE)
    if status in ("feedback", "ended") and thread:
        launcher.clear_waiting_record(data_folder(), thread)
    if status != "feedback":
        raise Refusal(f"page-{status.replace('_', '-')}", f"item page, field status: {status}: no answer to read")
    round_prompts, questions = prompt_lines.split_side_questions(detail["prompts"])
    answer = {"ok": True, "verb": "poll", "status": status,
              "raw": "\n".join(str(p.get("prompt", "")) for p in round_prompts),
              "prompts": detail["prompts"], "session_ended": detail["session_ended"],
              "btw": questions, "round_prompts": len(round_prompts)}
    try:
        answer["raw"] = poll_raw(args.document, round_prompts)
    except (Refusal, KeyError, TypeError, AttributeError, StopIteration) as problem:
        # The host hands the prompts over once: keep them, with the joined text as the raw response.
        answer["raw_warning"] = f"the document did not resolve the prompts ({problem}); raw is the prompt text joined"
    return answer


def poll_raw(document: str, prompts: list[dict]) -> str:
    """The raw response that a poll's prompts make, read against the page document."""
    _, doc = load_document(document)
    _, ids, _ = _element_ids(doc)
    return prompt_lines.raw_from_prompts(doc, prompts, ids, page.targets(doc))


def set_aside_file(document: str, stamp: str) -> Path:
    """Where a kept send that ingest refused goes: `<DOC stem>.refused.<stamp>.json`. The extra dots make it
    a side file: no session picker and no duplicate check reads it as a page document."""
    path = Path(document)
    return path.with_name(f"{path.stem}.refused.{stamp}.json")


def _set_aside(document: str, refusal: Refusal) -> Path | None:
    """Move the kept send aside with the refusal, so the next poll reads the host; None when no send waits."""
    kept = kept_delivery(document)
    if kept is None:
        return None
    target = set_aside_file(document, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    record = {**kept, "refused": {"code": refusal.code, "reason": refusal.reason}}
    inject.write_if_changed(target, json.dumps(record, indent=2, ensure_ascii=False).encode("utf-8"))
    delivery_file(document).unlink(missing_ok=True)
    return target


def _ingest(args) -> dict:
    """Ingest; the kept send goes only after the document holds the answer.

    A refusal of the response sets the kept send aside, with the human's answer in it: a refused send must
    not answer every later poll. A refusal of the document or of an unreadable raw file keeps it."""
    check_document(args.document)
    try:
        answer = ingest.cmd_ingest(args, check=check_document, check_changed=_check_changed,
                                   elements=_element_ids, save_copy=_save_settled_copy_if_possible)
    except Refusal as refusal:
        aside = None if refusal.code == "unreadable" else _set_aside(args.document, refusal)
        if aside is not None:
            refusal.reason += f"; the send is set aside in {aside}, and the next poll reads the page"
        raise
    delivery_file(args.document).unlink(missing_ok=True)
    return answer


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise Refusal("usage", message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="engine.py", add_help=False)
    verbs = parser.add_subparsers(dest="verb", required=True, parser_class=_Parser)
    for verb, handler in (("check", cmd_check), ("render", cmd_render), ("show", cmd_show), ("poll", cmd_poll),
                          ("reply", cmd_reply), ("end", cmd_end), ("ingest", _ingest)):
        sub = verbs.add_parser(verb, add_help=False)
        sub.add_argument("document")
        sub.set_defaults(handler=handler)
        if verb == "show":
            mode = sub.add_mutually_exclusive_group()
            mode.add_argument("--no-open", action="store_true")
            mode.add_argument("--reopen", action="store_true")
        if verb == "ingest":
            sub.add_argument("--raw-file", required=True)
        if verb in ("poll", "reply"):
            sub.add_argument("--reply-file", required=verb == "reply")
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
