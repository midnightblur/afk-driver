"""The Jira publish of a PRD, from the repository root. Every tracker call goes through the tracker port.

`publish.py preview --ticket KEY --prd FILE --run-dir DIR`: reads the ticket, builds the block and the pictures,
writes the preview and the receipt. Writes nothing to the ticket.
`publish.py publish --preview FILE --receipt RECEIPT`: runs after the developer's yes. Uploads the pictures, writes
the block, reads it back, and removes the afkv2 and v1 pictures the new block does not use.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "grill" / "scripts"))

import v1_facts  # noqa: E402
from grill_common import EXIT_REFUSED, EXIT_UNREADABLE, PLUGIN_ROOT, Parser, Refusal, read_json, serve, write_json, write_text  # noqa: E402
from grill_start import read_config  # noqa: E402
from prd_files import ID, set_row  # noqa: E402

TRACKER = PLUGIN_ROOT / "ports" / "tracker" / "cli.py"
TRACKER_TIMEOUT = 180
RENDER_TIMEOUT = 300
PICTURE_NAME = re.compile(r"afkv2-fig-[0-9a-f]{8}-\d+\.png")
FENCE = re.compile(r"^ *(`{3,}|~{3,})[ \t]*(\S*)[ \t]*$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PUBLISHED_TICKETS = "published-tickets.txt"


def call_tracker(verb, payload):
    """One tracker verb. The payload goes on stdin, because a whole PRD does not fit on a Windows command line."""
    if not TRACKER.is_file():
        raise Refusal("no-command", f"{TRACKER} does not exist in this plugin")
    try:
        run = subprocess.run([sys.executable, str(TRACKER), verb], input=json.dumps(payload), capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=TRACKER_TIMEOUT,
                             env={**os.environ, "PYTHONUTF8": "1"})
    except subprocess.TimeoutExpired as error:
        raise Refusal("timeout", f"tracker {verb}: no answer after {TRACKER_TIMEOUT} s") from error
    try:
        answer = json.loads(run.stdout)
    except json.JSONDecodeError as error:
        raise Refusal("bad-answer", f"tracker {verb}: exit {run.returncode}, no JSON answer: {run.stderr[-500:]}") from error
    if not isinstance(answer, dict) or not answer.get("ok"):
        problem = answer.get("error") if isinstance(answer, dict) else None
        problem = problem if isinstance(problem, dict) else {}
        extra = {key: value for key, value in problem.items() if key not in ("code", "reason")}
        raise Refusal(problem.get("code", "refused"), problem.get("reason", str(answer)),
                      run.returncode or EXIT_REFUSED, **extra)
    return answer


def extract_mermaid(markdown, token):
    """Each mermaid fence of the top level becomes a paragraph that holds only the figure token, in document order."""
    out, sources, fence, body = [], [], None, None
    for line in markdown.split("\n"):
        found = FENCE.match(line)
        if fence is None:
            if found and found.group(2) == "mermaid":
                fence, body = found.group(1), []
            elif found:
                fence, body = found.group(1), None
                out.append(line)
            else:
                out.append(line)
        elif found and not found.group(2) and found.group(1)[0] == fence[0] and len(found.group(1)) >= len(fence):
            if body is None:
                out.append(line)
            else:
                out.extend(["", token.format(len(sources)), ""])
                sources.append("\n".join(body))
            fence, body = None, None
        elif body is None:
            out.append(line)
        else:
            body.append(line)
    if fence is not None:
        raise Refusal("bad-prd", "a code fence of the PRD has no closing line")
    return "\n".join(out), sources


def check_ids_present(markdown, published_text):
    """Refuse when an AC id or a WE id of the PRD text is missing from the published text. Whole ids, never a part."""
    missing = sorted(set(ID.findall(markdown)) - set(ID.findall(published_text)))
    if missing:
        raise Refusal("missing-ids", f"not in the published text: {', '.join(missing)}", missing=missing)
    return sorted(set(ID.findall(markdown)))


def compute_receipt(ticket, block_text, picture_hashes):
    return hashlib.sha256((ticket + block_text + "".join(picture_hashes)).encode("utf-8")).hexdigest()


def picture_name(receipt, number):
    short = receipt[:8]
    return f"afkv2-fig-{short}-{number}.png"


def published_line(now, ticket, receipt):
    return f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')} {ticket} {receipt[:8]}"


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render_mermaid(source, out_png, work_dir):
    """Render one diagram on this machine: no diagram leaves the network."""
    script = Path(work_dir) / "diagram.mmd"
    write_text(script, source)
    mmdc, npx = shutil.which("mmdc"), shutil.which("npx")
    command = [mmdc] if mmdc else [npx, "-y", "@mermaid-js/mermaid-cli"] if npx else None
    try:
        if command is None:
            raise Refusal("render-failed", "mmdc and npx are not on the path; install @mermaid-js/mermaid-cli")
        run = subprocess.run([*command, "-i", str(script), "-o", str(out_png), "-b", "white"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=RENDER_TIMEOUT)
    except subprocess.TimeoutExpired as error:
        raise Refusal("render-failed", f"{command[0]}: no answer after {RENDER_TIMEOUT} s") from error
    finally:
        script.unlink(missing_ok=True)
    if run.returncode != 0:
        raise Refusal("render-failed", f"{command[0]}: {run.stderr[-500:]}")


def _rendered(sources, run_dir, renderer):
    """One PNG per source. A source renders once, so a re-run gets the same bytes and the same receipt."""
    cache = run_dir / "figure-cache"
    cache.mkdir(parents=True, exist_ok=True)
    files = []
    for source in sources:
        path = cache / f"{hashlib.sha256(source.encode('utf-8')).hexdigest()}.png"
        if not path.exists():
            scratch = path.with_name(path.name + ".tmp.png")
            renderer(source, scratch, run_dir)
            if not scratch.is_file() or scratch.read_bytes()[:8] != PNG_SIGNATURE:
                scratch.unlink(missing_ok=True)
                raise Refusal("render-failed", "the renderer wrote no PNG file")
            os.replace(scratch, path)
        files.append(path)
    for old in cache.iterdir():
        if old not in files:
            old.unlink()
    return files


def _figure_node(media_id, width=None, height=None):
    attrs = {"type": "file", "id": media_id, "collection": ""}
    if width and height:
        attrs.update(width=width, height=height)
    return {"type": "mediaSingle", "attrs": {"layout": "center"}, "content": [{"type": "media", "attrs": attrs}]}


def _refuse_bad_block(issue):
    if issue.get("block_problem"):
        raise Refusal("bad-block", issue["block_problem"])


def _inline(node):
    kind = node.get("type")
    if kind == "hardBreak":
        return "<br>"
    if kind == "text":
        text = html.escape(node.get("text") or "")
        for mark in node.get("marks") or []:
            tag = {"strong": "strong", "em": "em", "code": "code", "strike": "s"}.get(mark.get("type"))
            if tag:
                text = f"<{tag}>{text}</{tag}>"
            elif mark.get("type") == "link":
                text = f'<u title="{html.escape(str((mark.get("attrs") or {}).get("href")), quote=True)}">{text}</u>'
        return text
    return ""


def _html(nodes, pictures):
    """The page shows the ADF nodes that the publish sends, so the human reads what the ticket will hold."""
    tags = {"bulletList": "ul", "orderedList": "ol", "listItem": "li", "blockquote": "blockquote", "table": "table",
            "tableRow": "tr", "tableHeader": "th", "tableCell": "td", "paragraph": "p", "panel": "div", "expand": "div"}
    parts = []
    for node in nodes:
        kind, children = node.get("type"), node.get("content") or []
        if kind == "heading":
            level = (node.get("attrs") or {}).get("level", 2)
            parts.append(f"<h{level}>{_html(children, pictures)}</h{level}>")
        elif kind == "codeBlock":
            parts.append(f"<pre>{''.join(html.escape(child.get('text') or '') for child in children)}</pre>")
        elif kind == "rule":
            parts.append("<hr>")
        elif kind == "media":
            media = (node.get("attrs") or {}).get("id")
            parts.append(f'<img alt="{html.escape(str(media), quote=True)}" src="{pictures.get(media, "")}">')
        elif kind == "mediaSingle":
            parts.append(f"<figure>{_html(children, pictures)}</figure>")
        elif kind in ("text", "hardBreak"):
            parts.append(_inline(node))
        else:
            inner = _html(children, pictures)
            tag = tags.get(kind)
            parts.append(f"<{tag}>{inner}</{tag}>" if tag else inner)
    return "".join(parts)


PAGE_STYLE = ":root{color-scheme:light dark}body{font:15px/1.5 system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}" \
             "table{border-collapse:collapse}th,td{border:1px solid #8888;padding:.25rem .5rem;vertical-align:top}" \
             "pre{overflow:auto;padding:.5rem;border:1px solid #8888}img{max-width:100%;background:#fff}" \
             "header{border-bottom:2px solid #8888;margin-bottom:1rem}"


def _write_page(path, ticket, receipt, action, nodes, picture_files):
    """One self-contained file: the pictures are inside it, so it opens with no server."""
    data = {f"preview-{index}": "data:image/png;base64," + base64.b64encode(Path(file).read_bytes()).decode("ascii")
            for index, file in enumerate(picture_files)}
    write_text(path, f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(ticket)} preview</title>'
                     f"<style>{PAGE_STYLE}</style></head><body><header><p><strong>{html.escape(ticket)}</strong> · "
                     f"{html.escape(action)} · receipt {receipt[:8]}</p></header>{_html(nodes, data)}</body></html>\n")


def _action(block):
    family = (block or {}).get("family")
    return f"replaces the {family} block" if family else "appends the block at the end of the description"


def _already_published(block, preview, attachments, uploads):
    if not block or block.get("family") != "afkv2" or block.get("text") != preview["block_text"]:
        return False
    media, names = block.get("media_ids") or [], preview["pictures"]
    if len(media) != len(names) or not set(names) <= {item.get("filename") for item in attachments}:
        return False
    return not uploads or media == [uploads[name]["media_id"] for name in names if name in uploads]


def build_preview(ticket, prd, run_dir, tracker=call_tracker, renderer=render_mermaid):
    """Read the ticket, build the block with picture placeholders, render the pictures, write the preview + receipt."""
    run_dir = Path(run_dir)
    try:
        markdown = Path(prd).read_text("utf-8").replace("\r\n", "\n")
    except OSError as error:
        raise Refusal("unreadable", f"{prd}: {error}", EXIT_UNREADABLE) from error
    issue = tracker("issue-get", {"key": ticket})
    _refuse_bad_block(issue)
    if not issue.get("description_hash"):
        raise Refusal("bad-answer", "issue-get answered no `description_hash`")
    token = tracker("md-to-adf", {"markdown": "token"})["figure_token"]
    body, sources = extract_mermaid(markdown, token)
    placeholders = {str(index): [_figure_node(f"preview-{index}")] for index in range(len(sources))}
    adf = tracker("md-to-adf", {"markdown": body, "figures": placeholders})
    ids = check_ids_present(body, adf["block_text"])

    write_text(run_dir / ".gitignore", "*\n")
    rendered = _rendered(sources, run_dir, renderer)
    hashes = [_digest(file) for file in rendered]
    receipt = compute_receipt(ticket, adf["block_text"], hashes)
    pictures = run_dir / "pictures"
    shutil.rmtree(pictures, ignore_errors=True)
    pictures.mkdir(parents=True)
    names = [picture_name(receipt, number) for number in range(1, len(rendered) + 1)]
    for file, name in zip(rendered, names):
        shutil.copyfile(file, pictures / name)

    preview = {"ticket_key": ticket, "receipt": receipt, "description_hash": issue["description_hash"],
               "picture_hashes": hashes, "block_text": adf["block_text"], "pictures": names,
               "index": str(Path(prd).parent / "INDEX.md")}
    write_text(run_dir / "block.md", body)
    write_json(run_dir / "preview.json", preview)
    page = run_dir / "preview.html"
    action = _action(issue.get("block"))
    _write_page(page, ticket, receipt, action, adf["content"], rendered)
    attachments = tracker("attachment-list", {"key": ticket}).get("attachments") or []
    return {"ok": True, "ticket": ticket, "receipt": receipt, "preview": str(run_dir / "preview.json"),
            "page": str(page), "page_url": page.resolve().as_uri(), "pictures": [str(pictures / name) for name in names],
            "action": action, "ids": len(ids),
            "already_published": _already_published(issue.get("block"), preview, attachments, _uploads(run_dir, receipt))}


def _uploads(run_dir, receipt):
    path = Path(run_dir) / "uploads.json"
    if not path.exists():
        return {}
    state = read_json(path)
    return state.get("pictures", {}) if state.get("receipt") == receipt else {}


def _upload_pictures(tracker, preview, preview_path, run_dir, attachments):
    """Upload each picture once. A re-run reuses an upload the ticket still holds, so it adds no copy."""
    key, receipt = preview["ticket_key"], preview["receipt"]
    uploads = _uploads(run_dir, receipt)
    on_ticket = {str(item.get("id")) for item in attachments}
    uploaded = []
    for name in preview["pictures"]:
        if name in uploads and str(uploads[name]["attachment_id"]) in on_ticket:
            continue
        answer = tracker("attachment-put", {"key": key, "png": str(Path(run_dir) / "pictures" / name),
                                            "receipt": receipt, "preview": str(preview_path)})
        uploads[name] = {field: answer.get(field) for field in ("attachment_id", "media_id", "width", "height")}
        write_json(Path(run_dir) / "uploads.json", {"receipt": receipt, "pictures": uploads})
        uploaded.append(name)
    return uploads, uploaded


def _compare_read_back(block, text, media_ids):
    block = block or {}
    differs = [name for name, seen, sent in (("family", block.get("family"), "afkv2"), ("text", block.get("text"), text),
                                             ("media ids", block.get("media_ids") or [], media_ids)) if seen != sent]
    if differs:
        raise Refusal("read-back-mismatch", f"the ticket does not hold what was sent: {', '.join(differs)} differ; "
                                            "old pictures stay", differs=differs)


def _remove_unused(tracker, key, keep_ids, keep_names):
    """Delete only afkv2 and v1 pictures, each named in full, that the new block does not use."""
    deleted, not_deleted = [], []
    for item in tracker("attachment-list", {"key": key}).get("attachments") or []:
        name = item.get("filename") or ""
        if not (PICTURE_NAME.fullmatch(name) or v1_facts.PICTURE_NAME.fullmatch(name)):
            continue
        if str(item.get("id")) in keep_ids or (not keep_ids and name in keep_names):
            continue
        try:
            tracker("attachment-delete", {"id": item.get("id")})
            deleted.append(name)
        except Refusal as refusal:
            not_deleted.append({"filename": name, "code": refusal.code, "reason": refusal.reason})
    return deleted, not_deleted


def _record(log_path, ticket, receipt, now, only_if_new):
    """Answer the problem as text: a publish that reached the ticket does not fail on its local log."""
    path = Path(log_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if only_if_new and path.exists():
            if any(line.split()[1:] == [ticket, receipt[:8]] for line in path.read_text("utf-8").splitlines()):
                return None
        with open(path, "a", encoding="utf-8", newline="\n") as out:
            out.write(published_line(now, ticket, receipt) + "\n")
    except OSError as error:
        return f"{path}: {error}"
    return None


def _note_published(preview, now):
    index = Path(preview["index"])
    if index.exists():
        set_row(index, "PRD", "PRD.md", f"published to Jira {now.strftime('%Y-%m-%d')}")


def _load_preview(preview_path, receipt):
    preview = read_json(preview_path)
    run_dir = Path(preview_path).parent
    if receipt != preview.get("receipt"):
        raise Refusal("bad-receipt", "this receipt is not the receipt of the preview: show a new preview")
    if compute_receipt(preview["ticket_key"], preview["block_text"], preview["picture_hashes"]) != receipt:
        raise Refusal("bad-receipt", "the preview file changed after it was built: show a new preview")
    files = [run_dir / "pictures" / name for name in preview["pictures"]]
    if any(not file.is_file() for file in files) or [_digest(file) for file in files] != preview["picture_hashes"]:
        raise Refusal("bad-receipt", "a picture changed after the preview: show a new preview")
    return preview, run_dir


def _publish_answer(preview, **fields):
    return {"ok": True, "ticket": preview["ticket_key"], "receipt": preview["receipt"], **fields}


def publish_after_yes(preview_path, receipt, log_path, tracker=call_tracker, now=None):
    """The ordered writes. Call only after the developer said yes to this receipt's preview."""
    now = now or datetime.now(timezone.utc)
    preview, run_dir = _load_preview(preview_path, receipt)
    key = preview["ticket_key"]
    issue = tracker("issue-get", {"key": key})
    _refuse_bad_block(issue)
    attachments = tracker("attachment-list", {"key": key}).get("attachments") or []
    if _already_published(issue.get("block"), preview, attachments, _uploads(run_dir, receipt)):
        uploads = _uploads(run_dir, receipt)
        keep_ids = {str(uploads[name]["attachment_id"]) for name in preview["pictures"] if name in uploads}
        deleted, not_deleted = _remove_unused(tracker, key, keep_ids, set(preview["pictures"]))
        problem = _record(log_path, key, receipt, now, only_if_new=True)
        _note_published(preview, now)
        return _publish_answer(preview, published=False, already_published=True, deleted=deleted,
                               not_deleted=not_deleted, log_problem=problem)
    if issue.get("description_hash") != preview["description_hash"]:
        raise Refusal("stale", "the description changed after the preview: show a new preview and ask again")

    uploads, uploaded = _upload_pictures(tracker, preview, preview_path, run_dir, attachments)
    names = preview["pictures"]
    figures = {str(index): [_figure_node(uploads[name]["media_id"], uploads[name].get("width"), uploads[name].get("height"))]
               for index, name in enumerate(names)}
    markdown = (run_dir / "block.md").read_text("utf-8")
    final = tracker("md-to-adf", {"markdown": markdown, "figures": figures})
    check_ids_present(markdown, final["block_text"])
    if final["block_text"] != preview["block_text"]:
        raise Refusal("bad-receipt", "the converted text differs from the preview: show a new preview")
    put = tracker("description-put", {"key": key, "adf": final["content"], "expect_hash": preview["description_hash"],
                                      "receipt": receipt, "preview": str(preview_path)})
    back = tracker("issue-get", {"key": key})
    _compare_read_back(back.get("block"), preview["block_text"], [uploads[name]["media_id"] for name in names])
    problem = _record(log_path, key, receipt, now, only_if_new=False)
    _note_published(preview, now)
    keep_ids = {str(uploads[name]["attachment_id"]) for name in names}
    deleted, not_deleted = _remove_unused(tracker, key, keep_ids, set(names))
    return _publish_answer(preview, published=True, already_published=False, replaced=put.get("replaced"),
                           uploaded=uploaded, deleted=deleted, not_deleted=not_deleted, log_problem=problem)


def _preview_verb(argv):
    parser = Parser(add_help=False)
    for name in ("--ticket", "--prd", "--run-dir"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    kind = (read_config().get("tracker") or {}).get("kind")
    if kind != "jira":
        raise Refusal("not-jira", f"the tracker kind is {kind}: the PRD stays on disk, and nothing is published")
    return build_preview(args.ticket, args.prd, args.run_dir)


def _publish_verb(argv):
    parser = Parser(add_help=False)
    for name in ("--preview", "--receipt"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    return publish_after_yes(args.preview, args.receipt, Path(read_config()["data_folder"]) / PUBLISHED_TICKETS)


VERBS = {"preview": _preview_verb, "publish": _publish_verb}


def main(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", EXIT_UNREADABLE)
    try:
        return VERBS[argv[0]](argv[1:])
    except OSError as error:
        raise Refusal("io-error", f"{type(error).__name__}: {error}", EXIT_UNREADABLE) from error


if __name__ == "__main__":
    sys.exit(serve(main))
