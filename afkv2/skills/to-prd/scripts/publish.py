"""The publish of a PRD into a Jira ticket or a GitHub issue, from the repository root. Every tracker call goes through the tracker port.

`publish.py outline --ticket KEY --run-dir DIR`: writes the live top-level nodes with their indexes to `outline.json`.
`publish.py preview --ticket KEY [--prd FILE] --run-dir DIR [--ticket-file FILE]`: reads the ticket, builds the text
and the pictures, writes the preview and the receipt. Writes nothing to the ticket. With a ticket file the preview is
the whole new description, and `--prd` is optional: it only names the INDEX.md row to update. Jira: each `{{keep N}}`
or `{{keep N-M}}` line reuses those live nodes exactly, the Markdown between them is new text, bare keys of the
ticket's projects become link marks, and no block lines are written. GitHub: the ticket file is the whole new issue
body, with no keep lines. Without a ticket file, the PRD goes between the block lines.
`publish.py publish --preview FILE --receipt RECEIPT`: runs after the developer's yes. Uploads the pictures, writes
the block, reads it back, and removes the afkv2 and v1 pictures the new block does not use.
A GitHub issue gets the PRD Markdown as is: no picture is rendered, uploaded or removed.
"""

from __future__ import annotations

import base64
import copy
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
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "grill-requirements" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "use-lavish" / "scripts"))

import to_prd_v1_facts  # noqa: E402
from grill_common import EXIT_REFUSED, EXIT_UNREADABLE, PLUGIN_ROOT, Parser, Refusal, read_json, serve, write_json, write_text  # noqa: E402
from grill_start import SETUP, read_config  # noqa: E402
from prd_files import ID, set_row  # noqa: E402

TRACKER = PLUGIN_ROOT / "ports" / "tracker" / "cli.py"
TRACKER_TIMEOUT = 180
RENDER_TIMEOUT = 300
PICTURE_NAME = re.compile(r"afkv2-fig-[0-9a-f]{8}-\d+\.png")
FENCE = re.compile(r"^ *(`{3,}|~{3,})[ \t]*(\S*)[ \t]*$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PUBLISHED_TICKETS = "published-tickets.txt"
JIRA_TEXT_LIMIT = 30000  # visible characters of the whole description: 29.8k passed, 52.5k failed on one site
GITHUB_TEXT_LIMIT = 65536
GITHUB_FRAME = 60  # the 2 block lines and the blank line before the block
JIRA, GITHUB = "jira", "github-issues"
TRACKER_NAMES = {JIRA: "Jira", GITHUB: "GitHub"}


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


INLINE_HOLDERS = {"paragraph", "heading", "codeBlock"}


def _visible_text(nodes):
    """The words a reader sees. `block_text` does not serve: it is JSON, so it holds link targets and escapes line ends.
    Text nodes of one block join whole, because a mark splits a word; blocks and line breaks part words."""
    def words(node):
        kind = node.get("type")
        if kind == "text":
            return node.get("text") or ""
        if kind == "hardBreak":
            return "\n"
        return ("" if kind in INLINE_HOLDERS else "\n").join(map(words, node.get("content") or []))
    return "\n".join(map(words, nodes))


def compute_receipt(ticket, block_text, picture_hashes):
    """`block_text` is the port's answer, in the port's canonical form. This skill never computes that form."""
    return hashlib.sha256((ticket + block_text + "".join(picture_hashes)).encode("utf-8")).hexdigest()


def picture_name(receipt, number):
    short = receipt[:8]
    return f"afkv2-fig-{short}-{number}.png"


def published_line(now, ticket, receipt):
    return f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')} {ticket} {receipt[:8]}"


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _renderer_config():
    """The browser settings that setup writes for `mmdc`, or None when the file is not there."""
    root = os.environ.get("LOCALAPPDATA")
    config = Path(root) / "afkv2" / "puppeteer-config.json" if root else None
    return config if config and config.is_file() else None


def render_mermaid(source, out_png, work_dir):
    """Render one diagram with `mmdc` on this machine: no diagram leaves the network, and a publish downloads nothing."""
    mmdc, config = shutil.which("mmdc"), _renderer_config()
    if not mmdc or not config:
        missing = "`mmdc` is not on the path" if not mmdc else "%LOCALAPPDATA%\\afkv2\\puppeteer-config.json is missing"
        raise Refusal("no-renderer", f"the diagram renderer is not set up, {missing}: run {SETUP}", setup=SETUP)
    script = Path(work_dir) / "diagram.mmd"
    write_text(script, source)
    try:
        run = subprocess.run([mmdc, "-p", str(config), "-i", str(script), "-o", str(out_png), "-b", "white"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=RENDER_TIMEOUT)
    except subprocess.TimeoutExpired as error:
        raise Refusal("render-failed", f"{mmdc}: no answer after {RENDER_TIMEOUT} s") from error
    finally:
        script.unlink(missing_ok=True)
    if run.returncode != 0:
        raise Refusal("render-failed", f"{mmdc}: {run.stderr[-500:]}")


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
            if media in pictures:
                parts.append(f'<img alt="{html.escape(str(media), quote=True)}" src="{pictures[media]}">')
            else:
                parts.append(f"<p><em>[a picture on the ticket, kept as it is: {html.escape(str(media))}]</em></p>")
        elif kind == "inlineCard":
            parts.append(f"<u>{html.escape(str((node.get('attrs') or {}).get('url')))}</u>")
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


def _write_page(path, ticket, receipt, action, nodes, picture_files, dropped=()):
    """One self-contained file: the pictures are inside it, so it opens with no server. `dropped` lists the live
    nodes the new description leaves out."""
    data = {f"preview-{index}": "data:image/png;base64," + base64.b64encode(Path(file).read_bytes()).decode("ascii")
            for index, file in enumerate(picture_files)}
    gone = "".join(f"<li>node {item['index']} ({html.escape(str(item['type']))}): {html.escape(item['text'])}</li>"
                   for item in dropped)
    gone = f"<p><strong>Removed from the description</strong></p><ul>{gone}</ul>" if gone else ""
    _write_both(path, ticket, receipt, action, f"{gone}</header>{_html(nodes, data)}")


def _action(block, where="the description"):
    family = (block or {}).get("family")
    return f"replaces the {family} block" if family else f"appends the block at the end of {where}"


def _already_published(block, preview, attachments, uploads):
    if not block or block.get("family") != "afkv2" or block.get("text") != preview["block_text"]:
        return False
    media, names = block.get("media_ids") or [], preview["pictures"]
    if len(media) != len(names) or not set(names) <= {item.get("filename") for item in attachments}:
        return False
    return all(name in uploads for name in names) and media == [uploads[name]["media_id"] for name in names]


def _read_prd(prd):
    try:
        return Path(prd).read_text("utf-8").replace("\r\n", "\n")
    except OSError as error:
        raise Refusal("unreadable", f"{prd}: {error}", EXIT_UNREADABLE) from error


def _write_text_page(path, ticket, receipt, action, text, what="the block"):
    """The exact Markdown the issue body gets. GitHub draws the Markdown and each Mermaid fence itself."""
    _write_both(path, ticket, receipt, action, f"<p>The exact Markdown of {what}. GitHub shows it formatted, with "
                                               f"each Mermaid diagram drawn.</p></header><pre>{html.escape(text)}</pre>")


ROUND_FILE = "preview-round.json"
CARD_STYLE = ".ticket-preview table{border-collapse:collapse}.ticket-preview th,.ticket-preview td{border:1px solid #8888;"              "padding:.25rem .5rem;vertical-align:top}.ticket-preview pre{overflow:auto;padding:.5rem;border:1px solid "              "#8888}.ticket-preview img{max-width:100%;background:#fff}.ticket-preview header{border-bottom:2px solid "              "#8888;margin-bottom:1rem}"
PUBLISH_CARD = "i-publish"


def _write_both(path, ticket, receipt, action, rest):
    """The preview as 1 file, and the same text as the round input of 1 page round: 1 card that shows it, and 1
    sign-off card whose sign mark is the yes to publish it."""
    head = f"<header><p><strong>{html.escape(ticket)}</strong> · {html.escape(action)} · receipt {receipt[:8]}</p>"
    write_text(path, f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(ticket)} preview</title>'
                     f"<style>{PAGE_STYLE}</style></head><body>{head}{rest}</body></html>\n")
    shown = {"type": "freestyle", "id": "i-preview-text", "props": {"reason": "the exact ticket text with its pictures"},
             "html": f'<style>{CARD_STYLE}</style><div class="ticket-preview">{head}{rest}</div>'}
    sign = {"type": "text", "id": "i-publish-text", "props": {"markdown": True, "text": (
        f"Sign to publish the text above into **{ticket}**: it {action}. Receipt `{receipt[:8]}`. Any other mark or a "
        "note changes nothing on the ticket.")}}
    write_json(Path(path).with_name(ROUND_FILE), {
        "short_title": f"{ticket} ticket preview"[:40], "step": "Ticket preview",
        "banner": {"settled": [], "unlocks": [f"the publish into {ticket}"], "parked": []},
        "items": [{"id": "i-preview", "kind": "info", "title": f"The exact text {ticket} gets", "body": shown},
                  {"id": PUBLISH_CARD, "kind": "signoff", "title": f"Publish this text into {ticket}", "body": sign}]})


def _github_preview(ticket, prd, run_dir, tracker):
    """The GitHub-issue preview: the PRD Markdown as is, Mermaid fences included; no picture to render or upload."""
    markdown = _read_prd(prd)
    issue = tracker("issue-get", {"key": ticket})
    _refuse_bad_block(issue)
    if not issue.get("description_hash"):
        raise Refusal("bad-answer", "issue-get answered no `description_hash`")
    text = tracker("block-text", {"markdown": markdown})["block_text"]
    ids = check_ids_present(markdown, text)
    write_text(run_dir / ".gitignore", "*\n")
    receipt = compute_receipt(ticket, text, [])
    preview = {"ticket_key": ticket, "kind": GITHUB, "receipt": receipt, "description_hash": issue["description_hash"],
               "picture_hashes": [], "block_text": text, "pictures": [], "index": str(Path(prd).parent / "INDEX.md")}
    write_text(run_dir / "block.md", markdown)
    write_json(run_dir / "preview.json", preview)
    page = run_dir / "preview.html"
    action = _action(issue.get("block"), "the issue body")
    _write_text_page(page, ticket, receipt, action, text)
    length = (issue.get("length_without_block") or 0) + len(text) + GITHUB_FRAME
    block = issue.get("block") or {}
    return {"ok": True, "ticket": ticket, "receipt": receipt, "preview": str(run_dir / "preview.json"),
            "page": str(page), "page_url": page.resolve().as_uri(), "round_input": str(page.with_name(ROUND_FILE)), "pictures": [], "action": action, "ids": len(ids),
            "over_github_limit": length > GITHUB_TEXT_LIMIT,
            "already_published": block.get("family") == "afkv2" and block.get("text") == text}


def build_preview(ticket, prd, run_dir, tracker=call_tracker, renderer=render_mermaid, kind=JIRA):
    """Read the ticket, build the block with picture placeholders, render the pictures, write the preview + receipt."""
    run_dir = Path(run_dir)
    if kind == GITHUB:
        return _github_preview(ticket, prd, run_dir, tracker)
    markdown = _read_prd(prd)
    issue = tracker("issue-get", {"key": ticket})
    _refuse_bad_block(issue)
    if not issue.get("description_hash"):
        raise Refusal("bad-answer", "issue-get answered no `description_hash`")
    token = tracker("md-to-adf", {"markdown": "token"})["figure_token"]
    body, sources = extract_mermaid(markdown, token)
    placeholders = {str(index): [_figure_node(f"preview-{index}")] for index in range(len(sources))}
    adf = tracker("md-to-adf", {"markdown": body, "figures": placeholders})
    ids = check_ids_present(body, _visible_text(adf["content"]))

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
            "page": str(page), "page_url": page.resolve().as_uri(), "round_input": str(page.with_name(ROUND_FILE)), "pictures": [str(pictures / name) for name in names],
            "action": action, "ids": len(ids), "over_jira_limit": over_jira_limit(_outside_block(issue) + adf["content"]),
            "already_published": _already_published(issue.get("block"), preview, attachments, _uploads(run_dir, receipt))}


def _outside_block(issue):
    """The live nodes a block publish keeps: all but the block and its lines."""
    content, block = _content(issue), _block_range(issue)
    return [node for index, node in enumerate(content) if index not in block]


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


def _remove_unused(tracker, key, keep_ids):
    """Delete only afkv2 and v1 pictures, each named in full, that the new block does not use."""
    deleted, not_deleted = [], []
    for item in tracker("attachment-list", {"key": key}).get("attachments") or []:
        name = item.get("filename") or ""
        if not (PICTURE_NAME.fullmatch(name) or to_prd_v1_facts.PICTURE_NAME.fullmatch(name)):
            continue
        if str(item.get("id")) in keep_ids:
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


def _index_of(prd):
    return str(Path(prd).parent / "INDEX.md") if prd else None


def _note_published(preview, now):
    if not preview.get("index"):
        return
    index = Path(preview["index"])
    if index.exists():
        name = TRACKER_NAMES[preview.get("kind", JIRA)]
        set_row(index, "PRD", "PRD.md", f"published to {name} {now.strftime('%Y-%m-%d')}")


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


def _publish_github(preview, preview_path, run_dir, log_path, tracker, now):
    """Write the block, read it back. A GitHub block has no pictures, so nothing is uploaded or deleted."""
    key, receipt = preview["ticket_key"], preview["receipt"]
    issue = tracker("issue-get", {"key": key})
    _refuse_bad_block(issue)
    block = issue.get("block") or {}
    if block.get("family") == "afkv2" and block.get("text") == preview["block_text"]:
        problem = _record(log_path, key, receipt, now, only_if_new=True)
        _note_published(preview, now)
        return _publish_answer(preview, published=False, already_published=True, deleted=[], not_deleted=[],
                               log_problem=problem)
    if issue.get("description_hash") != preview["description_hash"]:
        raise Refusal("stale", "the issue body changed after the preview: show a new preview and ask again")
    markdown = (run_dir / "block.md").read_text("utf-8")
    put = tracker("description-put", {"key": key, "markdown": markdown, "expect_hash": preview["description_hash"],
                                      "receipt": receipt, "preview": str(preview_path)})
    back = tracker("issue-get", {"key": key})
    _compare_read_back(back.get("block"), preview["block_text"], [])
    problem = _record(log_path, key, receipt, now, only_if_new=False)
    _note_published(preview, now)
    return _publish_answer(preview, published=True, already_published=False, replaced=put.get("replaced"),
                           uploaded=[], deleted=[], not_deleted=[], log_problem=problem)


def publish_after_yes(preview_path, receipt, log_path, tracker=call_tracker, now=None):
    """The ordered writes. Call only after the developer said yes to this receipt's preview."""
    now = now or datetime.now(timezone.utc)
    preview, run_dir = _load_preview(preview_path, receipt)
    if preview.get("kind") == GITHUB:
        if preview.get("whole"):
            return _publish_github_whole(preview, preview_path, log_path, tracker, now)
        return _publish_github(preview, preview_path, run_dir, log_path, tracker, now)
    if preview.get("whole"):
        return _publish_whole(preview, preview_path, run_dir, log_path, tracker, now)
    key = preview["ticket_key"]
    issue = tracker("issue-get", {"key": key})
    _refuse_bad_block(issue)
    attachments = tracker("attachment-list", {"key": key}).get("attachments") or []
    if _already_published(issue.get("block"), preview, attachments, _uploads(run_dir, receipt)):
        uploads = _uploads(run_dir, receipt)
        keep_ids = {str(uploads[name]["attachment_id"]) for name in preview["pictures"]}
        deleted, not_deleted = _remove_unused(tracker, key, keep_ids)
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
    check_ids_present(markdown, _visible_text(final["content"]))
    if final["block_text"] != preview["block_text"]:
        raise Refusal("bad-receipt", "the converted text differs from the preview: show a new preview")
    put = tracker("description-put", {"key": key, "adf": final["content"], "expect_hash": preview["description_hash"],
                                      "receipt": receipt, "preview": str(preview_path)})
    back = tracker("issue-get", {"key": key})
    _compare_read_back(back.get("block"), preview["block_text"], [uploads[name]["media_id"] for name in names])
    problem = _record(log_path, key, receipt, now, only_if_new=False)
    _note_published(preview, now)
    keep_ids = {str(uploads[name]["attachment_id"]) for name in names}
    deleted, not_deleted = _remove_unused(tracker, key, keep_ids)
    return _publish_answer(preview, published=True, already_published=False, replaced=put.get("replaced"),
                           uploaded=uploaded, deleted=deleted, not_deleted=not_deleted, log_problem=problem)


# ---------------------------------------------------------------- the whole description (Jira, a ticket file)

KEEP_LINE = re.compile(r"\{\{keep (\d+)(?:-(\d+))?\}\}")
WIKI_LINK = re.compile(r"\[[^\[\]|]+\|\s*https?://[^\[\]]*\]")
LEDGER_HEADING = re.compile(r"(?i)^[\d.\s]*(?:scope\s+)?(?:update|history|change\s*log|meeting\s+(?:summary|summaries"
                            r"|notes|minutes))\b")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
OUTLINE = "outline.json"
WHOLE_ACTION = "replaces the whole description"
TEXT_HOLDERS = {"codeBlock"}


def over_jira_limit(nodes):
    """Jira refuses a description by its text length, not by its JSON length (CONTRACT: CONTENT_LIMIT_EXCEEDED)."""
    return len(_visible_text(nodes)) > JIRA_TEXT_LIMIT


def _uploaded_media(run_dir):
    """The media ids of the pictures that a publish from this run folder uploaded, whatever its receipt."""
    path = Path(run_dir) / "uploads.json"
    if not path.is_file():
        return set()
    return {str(item.get("media_id")) for item in (read_json(path).get("pictures") or {}).values()
            if isinstance(item, dict) and item.get("media_id")}


def _afkv2_picture(node, uploaded):
    """True when each picture of the node is afkv2's own: uploaded by a publish of this run folder, or its alt is a PICTURE_NAME."""
    media = _media_nodes(node)
    return bool(media) and all(str(attrs.get("id")) in uploaded or PICTURE_NAME.fullmatch(str(attrs.get("alt") or ""))
                               for attrs in media)


def _media_nodes(node):
    found = [node.get("attrs") or {}] if node.get("type") == "media" else []
    for child in node.get("content") or []:
        if isinstance(child, dict):
            found.extend(_media_nodes(child))
    return found


def _media_in(node):
    found = [node["attrs"]["id"]] if node.get("type") == "media" and (node.get("attrs") or {}).get("id") else []
    for child in node.get("content") or []:
        if isinstance(child, dict):
            found.extend(_media_in(child))
    return found


def link_ticket_keys(nodes, projects, site):
    """Each bare key of `projects` in a text node with no link or code mark becomes a link mark to `<site>/browse/KEY`.
    Text in a code block stays."""
    if not projects:
        return nodes
    key = re.compile(r"\b(?:%s)-\d+\b" % "|".join(map(re.escape, sorted(projects))))

    def split(node):
        marks = node.get("marks") or []
        if any(mark.get("type") in ("link", "code") for mark in marks) or not key.search(node.get("text") or ""):
            return [node]
        if not site:
            raise Refusal("bad-answer", "issue-get answered no `site`: a ticket key cannot become a link")
        out, at, text = [], 0, node["text"]
        for found in key.finditer(text):
            if found.start() > at:
                out.append({**node, "text": text[at:found.start()]})
            out.append({**node, "text": found.group(0),
                        "marks": [*marks, {"type": "link", "attrs": {"href": f"{site}/browse/{found.group(0)}"}}]})
            at = found.end()
        if at < len(text):
            out.append({**node, "text": text[at:]})
        return out

    def walk(node):
        if node.get("type") in TEXT_HOLDERS or not node.get("content"):
            return node
        children = []
        for child in node["content"]:
            children.extend(split(child) if child.get("type") == "text" else [walk(child)])
        return {**node, "content": children}

    return [walk(node) for node in nodes]


def _refuse_wiki_links(nodes):
    found = sorted({match.group(0) for match in WIKI_LINK.finditer(_visible_text(nodes))})
    if found:
        raise Refusal("wiki-link", f"wiki link text shows as raw text in Jira; write a Markdown link or the bare key: "
                                   f"{', '.join(found)}", found=found)


def _dated(heading):
    return bool(LEDGER_HEADING.match(heading) or DATE.search(heading))


def check_no_dated_headings(markdown):
    """The Markdown form of `check_no_dated_sections`: the headings outside a code fence."""
    found, fence = [], None
    for line in markdown.split("\n"):
        mark = FENCE.match(line)
        if fence is not None:
            if mark and not mark.group(2) and mark.group(1)[0] == fence[0] and len(mark.group(1)) >= len(fence):
                fence = None
            continue
        if mark:
            fence = mark.group(1)
        elif re.match(r" {0,3}#{1,6}\s", line) and _dated(line.strip().lstrip("#").strip()):
            found.append(line.strip().lstrip("#").strip())
    if found:
        raise Refusal("dated-section", f"apply each update to the text and put meetings in comments: {found}",
                      found=found)


GITHUB_WHOLE_ACTION = "replaces the whole issue body"


def build_github_ticket_preview(ticket, prd, ticket_file, run_dir, tracker=call_tracker):
    """The whole new issue body from the ticket file. Writes nothing to the issue."""
    run_dir = Path(run_dir)
    markdown = _read_prd(ticket_file)
    issue = tracker("issue-get", {"key": ticket})
    if not issue.get("description_hash"):
        raise Refusal("bad-answer", "issue-get answered no `description_hash`")
    _check_outline(run_dir, ticket, issue)
    if any(segment[0] == "keep" for segment in split_ticket(markdown)):
        raise Refusal("bad-ticket", "a GitHub issue body has no nodes to keep: copy the text from `live-body.md`")
    check_no_dated_headings(markdown)
    text = tracker("block-text", {"markdown": markdown})["block_text"]
    receipt = compute_receipt(ticket, text, [])
    write_text(run_dir / ".gitignore", "*\n")
    write_text(run_dir / "block.md", markdown)
    preview = {"ticket_key": ticket, "kind": GITHUB, "whole": True, "receipt": receipt,
               "description_hash": issue["description_hash"], "picture_hashes": [], "block_text": text, "pictures": [],
               "index": _index_of(prd)}
    write_json(run_dir / "preview.json", preview)
    page = run_dir / "preview.html"
    _write_text_page(page, ticket, receipt, GITHUB_WHOLE_ACTION, text, "the whole issue body")
    return {"ok": True, "ticket": ticket, "receipt": receipt, "preview": str(run_dir / "preview.json"),
            "page": str(page), "page_url": page.resolve().as_uri(), "round_input": str(page.with_name(ROUND_FILE)),
            "pictures": [], "action": GITHUB_WHOLE_ACTION, "replaces_block": (issue.get("block") or {}).get("family"),
            "dropped": [], "text_length": len(text), "over_github_limit": len(text) > GITHUB_TEXT_LIMIT,
            "already_published": (issue.get("whole") or {}).get("text") == text}


def _publish_github_whole(preview, preview_path, log_path, tracker, now):
    """Write the whole issue body, read it back."""
    key, receipt = preview["ticket_key"], preview["receipt"]
    issue = tracker("issue-get", {"key": key})
    if (issue.get("whole") or {}).get("text") == preview["block_text"]:
        problem = _record(log_path, key, receipt, now, only_if_new=True)
        _note_published(preview, now)
        return _publish_answer(preview, published=False, already_published=True, deleted=[], not_deleted=[],
                               log_problem=problem)
    if issue.get("description_hash") != preview["description_hash"]:
        raise Refusal("stale", "the issue body changed after the preview: show a new preview and ask again")
    markdown = (Path(preview_path).parent / "block.md").read_text("utf-8")
    put = tracker("description-put", {"key": key, "markdown": markdown, "expect_hash": preview["description_hash"],
                                      "receipt": receipt, "preview": str(preview_path), "whole": True})
    back = tracker("issue-get", {"key": key})
    if (back.get("whole") or {}).get("text") != preview["block_text"]:
        raise Refusal("read-back-mismatch", "the issue body does not hold what was sent", differs=["text"])
    problem = _record(log_path, key, receipt, now, only_if_new=False)
    _note_published(preview, now)
    return _publish_answer(preview, published=True, already_published=False, replaced=put.get("replaced"),
                           uploaded=[], deleted=[], not_deleted=[], log_problem=problem)


def check_no_dated_sections(nodes):
    """A description states the current scope: no dated, update, history or meeting-summary section."""
    found = []
    for node in nodes:
        if node.get("type") == "heading":
            text = _visible_text([node]).strip()
            if _dated(text):
                found.append(text)
    if found:
        raise Refusal("dated-section", f"apply each update to the text and put meetings in comments: {found}",
                      found=found)


def split_ticket(markdown):
    """The ticket file as segments: ("keep", first, last) for a `{{keep N}}` or `{{keep N-M}}` line outside a code
    fence, ("md", text) for the Markdown between them."""
    segments, chunk, fence = [], [], None

    def flush():
        if "\n".join(chunk).strip():
            segments.append(("md", "\n".join(chunk)))
        chunk.clear()

    for line in markdown.split("\n"):
        found = FENCE.match(line)
        keep = KEEP_LINE.fullmatch(line.strip()) if fence is None else None
        if keep:
            flush()
            first, last = int(keep.group(1)), int(keep.group(2) or keep.group(1))
            if last < first:
                raise Refusal("bad-ticket", f"{line.strip()}: the last node comes before the first")
            segments.append(("keep", first, last))
            continue
        if fence is None and found:
            fence = found.group(1)
        elif fence is not None and found and not found.group(2) and found.group(1)[0] == fence[0] \
                and len(found.group(1)) >= len(fence):
            fence = None
        chunk.append(line)
    flush()
    return segments


def _block_range(issue):
    found = issue.get("block_range")
    return range(found[0], found[1] + 1) if found else range(0)


def _kept_indexes(segments, live, block):
    kept = [index for segment in segments if segment[0] == "keep" for index in range(segment[1], segment[2] + 1)]
    past = sorted({index for index in kept if index >= len(live)})
    if past:
        raise Refusal("bad-ticket", f"the description has {len(live)} nodes: no node {past}")
    twice = sorted({index for index in kept if kept.count(index) > 1})
    if twice:
        raise Refusal("bad-ticket", f"nodes kept twice: {twice}")
    inside = sorted(set(kept) & set(block))
    if inside:
        raise Refusal("keeps-block", f"nodes {inside} belong to the old block: write their content anew", nodes=inside)
    return set(kept)


def _assemble(segments, live, convert):
    nodes = []
    for segment in segments:
        nodes.extend(copy.deepcopy(live[segment[1]:segment[2] + 1]) if segment[0] == "keep" else convert(segment[1]))
    return nodes


def _converter(tracker, figures, projects, site):
    def convert(markdown):
        content = tracker("md-to-adf", {"markdown": markdown, "figures": figures})["content"]
        _refuse_wiki_links(content)
        return link_ticket_keys(content, projects, site)
    return convert


def outline(ticket, run_dir, tracker=call_tracker, kind=JIRA):
    """The live top-level nodes with their indexes, for the `{{keep}}` lines of the ticket file. A GitHub issue has no
    nodes: its live body goes to `live-body.md`, to copy from. Writes nothing to the ticket."""
    issue = tracker("issue-get", {"key": ticket})
    _refuse_bad_block(issue)
    meetings = _write_meetings(ticket, Path(run_dir), tracker)
    if kind == GITHUB:
        run_dir = Path(run_dir)
        body = (issue.get("body") or "").replace("\r\n", "\n")
        write_text(run_dir / ".gitignore", "*\n")
        write_text(run_dir / "live-body.md", body)
        write_json(run_dir / OUTLINE, {"ticket_key": ticket, "description_hash": issue["description_hash"], "nodes": []})
        return {"ok": True, "ticket": ticket, "outline": str(run_dir / OUTLINE), "nodes": 0,
                "live_body": str(run_dir / "live-body.md"), "block": (issue.get("block") or {}).get("family"),
                "text_length": len(body), "meetings": meetings}
    live, block = _content(issue), _block_range(issue)
    nodes = [{"index": index, "type": node.get("type"), "text": _visible_text([node]), "media": bool(_media_in(node)),
              "in_block": index in block} for index, node in enumerate(live)]
    run_dir = Path(run_dir)
    write_text(run_dir / ".gitignore", "*\n")
    write_json(run_dir / OUTLINE, {"ticket_key": ticket, "description_hash": issue["description_hash"], "nodes": nodes})
    return {"ok": True, "ticket": ticket, "outline": str(run_dir / OUTLINE), "nodes": len(nodes),
            "block": (issue.get("block") or {}).get("family"), "text_length": len(_visible_text(live)),
            "meetings": meetings}


MEETINGS_FILE = "meetings.md"


def _write_meetings(ticket, run_dir, tracker):
    """The ticket's meeting comments, oldest first, in 1 file: the new text must not contradict them."""
    found = tracker("meeting-comments", {"key": ticket}).get("comments") or []
    text = "".join(f"## {item.get('title')}\n\n{item.get('text') or ''}\n\n" for item in found)
    run_dir.mkdir(parents=True, exist_ok=True)
    write_text(run_dir / MEETINGS_FILE, text or "No meeting comment on this ticket.\n")
    return str(run_dir / MEETINGS_FILE)


def _content(issue):
    content = (issue.get("description") or {}).get("content")
    return content if isinstance(content, list) else []


def _check_outline(run_dir, ticket, issue):
    path = Path(run_dir) / OUTLINE
    if not path.is_file():
        raise Refusal("no-outline", "run `outline` first: the keep lines name its node indexes")
    seen = read_json(path)
    if seen.get("ticket_key") != ticket or seen.get("description_hash") != issue["description_hash"]:
        raise Refusal("stale", "the description changed after the outline: run `outline` again and check each keep line")


def build_ticket_preview(ticket, prd, ticket_file, run_dir, projects, tracker=call_tracker, renderer=render_mermaid):
    """The whole new description: live nodes kept by index, new Markdown converted, keys linked. Writes nothing to
    the ticket."""
    run_dir = Path(run_dir)
    markdown = _read_prd(ticket_file)
    issue = tracker("issue-get", {"key": ticket})
    _refuse_bad_block(issue)
    if not issue.get("description_hash"):
        raise Refusal("bad-answer", "issue-get answered no `description_hash`")
    _check_outline(run_dir, ticket, issue)
    live, block = _content(issue), _block_range(issue)
    token = tracker("md-to-adf", {"markdown": "token"})["figure_token"]
    body, sources = extract_mermaid(markdown, token)
    segments = split_ticket(body)
    kept = _kept_indexes(segments, live, block)
    ours = _uploaded_media(run_dir)
    dropped_media = [index for index, node in enumerate(live) if index not in kept and index not in block
                     and _media_in(node) and not _afkv2_picture(node, ours)]
    if dropped_media:
        raise Refusal("drops-media", f"nodes {dropped_media} hold the owner's pictures: keep each one",
                      nodes=dropped_media)
    placeholders = {str(index): [_figure_node(f"preview-{index}")] for index in range(len(sources))}
    nodes = _assemble(segments, live, _converter(tracker, placeholders, projects, issue.get("site")))
    check_no_dated_sections(nodes)
    ids = check_ids_present(body, _visible_text(nodes))
    text = tracker("adf-text", {"adf": nodes})["block_text"]

    write_text(run_dir / ".gitignore", "*\n")
    rendered = _rendered(sources, run_dir, renderer)
    hashes = [_digest(file) for file in rendered]
    receipt = compute_receipt(ticket, text, hashes)
    pictures = run_dir / "pictures"
    shutil.rmtree(pictures, ignore_errors=True)
    pictures.mkdir(parents=True)
    names = [picture_name(receipt, number) for number in range(1, len(rendered) + 1)]
    for file, name in zip(rendered, names):
        shutil.copyfile(file, pictures / name)
    media_plan = [f"picture:{names[int(media.split('-', 1)[1])]}" if media in
                  {f"preview-{index}" for index in range(len(names))} else media
                  for node in nodes for media in _media_in(node)]
    dropped = [{"index": index, "type": node.get("type"), "text": _visible_text([node])[:200]}
               for index, node in enumerate(live) if index not in kept and index not in block]
    preview = {"ticket_key": ticket, "whole": True, "receipt": receipt, "description_hash": issue["description_hash"],
               "picture_hashes": hashes, "block_text": text, "pictures": names, "segments": segments,
               "projects": projects, "media_plan": media_plan, "index": _index_of(prd)}
    write_json(run_dir / "preview.json", preview)
    page = run_dir / "preview.html"
    _write_page(page, ticket, receipt, WHOLE_ACTION, nodes, rendered, dropped)
    attachments = tracker("attachment-list", {"key": ticket}).get("attachments") or []
    return {"ok": True, "ticket": ticket, "receipt": receipt, "preview": str(run_dir / "preview.json"),
            "page": str(page), "page_url": page.resolve().as_uri(), "round_input": str(page.with_name(ROUND_FILE)), "pictures": [str(pictures / name) for name in names],
            "action": WHOLE_ACTION, "replaces_block": (issue.get("block") or {}).get("family"), "dropped": dropped,
            "ids": len(ids), "text_length": len(_visible_text(nodes)), "over_jira_limit": over_jira_limit(nodes),
            "already_published": _whole_published(issue, preview, attachments, _uploads(run_dir, receipt))}


def _expected_media(preview, uploads):
    out = []
    for media in preview["media_plan"]:
        if media.startswith("picture:"):
            name = media.split(":", 1)[1]
            if name not in uploads:
                return None
            out.append(uploads[name]["media_id"])
        else:
            out.append(media)
    return out


def _whole_published(issue, preview, attachments, uploads):
    whole = issue.get("whole") or {}
    if issue.get("block") or whole.get("text") != preview["block_text"]:
        return False
    if not set(preview["pictures"]) <= {item.get("filename") for item in attachments}:
        return False
    return (whole.get("media_ids") or []) == _expected_media(preview, uploads)


def _publish_whole(preview, preview_path, run_dir, log_path, tracker, now):
    """The ordered writes of a whole description: upload, write, read back, then remove unused old pictures."""
    key, receipt = preview["ticket_key"], preview["receipt"]
    issue = tracker("issue-get", {"key": key})
    _refuse_bad_block(issue)
    attachments = tracker("attachment-list", {"key": key}).get("attachments") or []
    if _whole_published(issue, preview, attachments, _uploads(run_dir, receipt)):
        uploads = _uploads(run_dir, receipt)
        deleted, not_deleted = _remove_unused(tracker, key, {str(uploads[name]["attachment_id"])
                                                              for name in preview["pictures"]})
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
    segments = [tuple(segment) for segment in preview["segments"]]
    nodes = _assemble(segments, _content(issue), _converter(tracker, figures, preview["projects"], issue.get("site")))
    if tracker("adf-text", {"adf": nodes})["block_text"] != preview["block_text"]:
        raise Refusal("bad-receipt", "the converted text differs from the preview: show a new preview")
    put = tracker("description-put", {"key": key, "adf": nodes, "expect_hash": preview["description_hash"],
                                      "receipt": receipt, "preview": str(preview_path), "whole": True})
    back = tracker("issue-get", {"key": key})
    whole = back.get("whole") or {}
    differs = [name for name, seen, sent in (("text", whole.get("text"), preview["block_text"]),
                                             ("media ids", whole.get("media_ids") or [], _expected_media(preview, uploads)))
               if seen != sent]
    if differs:
        raise Refusal("read-back-mismatch", f"the ticket does not hold what was sent: {', '.join(differs)} differ; "
                                            "old pictures stay", differs=differs)
    problem = _record(log_path, key, receipt, now, only_if_new=False)
    _note_published(preview, now)
    deleted, not_deleted = _remove_unused(tracker, key, {str(uploads[name]["attachment_id"]) for name in names})
    return _publish_answer(preview, published=True, already_published=False, replaced=put.get("replaced"),
                           uploaded=uploaded, deleted=deleted, not_deleted=not_deleted, log_problem=problem)


def _preview_verb(argv):
    parser = Parser(add_help=False)
    for name in ("--ticket", "--run-dir"):
        parser.add_argument(name, required=True)
    parser.add_argument("--prd")
    parser.add_argument("--ticket-file")
    args = parser.parse_args(argv)
    if not (args.prd or args.ticket_file):
        raise Refusal("usage", "give --prd, --ticket-file, or both", EXIT_UNREADABLE)
    tracker = read_config().get("tracker") or {}
    kind = tracker.get("kind")
    if kind not in TRACKER_NAMES:
        raise Refusal("no-publish", f"the tracker kind is {kind}: the PRD stays on disk, and nothing is published")
    if args.ticket_file:
        if kind == GITHUB:
            return build_github_ticket_preview(args.ticket, args.prd, args.ticket_file, args.run_dir)
        return build_ticket_preview(args.ticket, args.prd, args.ticket_file, args.run_dir, _projects(args.ticket, tracker))
    return build_preview(args.ticket, args.prd, args.run_dir, kind=kind)


def _projects(ticket, tracker):
    """The Jira projects whose bare keys become links: the ticket's own and the config's."""
    listed = tracker.get("projects") if isinstance(tracker.get("projects"), list) else []
    found = {key for key in [ticket.rsplit("-", 1)[0], tracker.get("project"), *listed]
             if isinstance(key, str) and re.fullmatch(r"[A-Z][A-Z0-9_]+", key)}
    return sorted(found)


def _outline_verb(argv):
    parser = Parser(add_help=False)
    for name in ("--ticket", "--run-dir"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    return outline(args.ticket, args.run_dir, kind=(read_config().get("tracker") or {}).get("kind"))


def _publish_verb(argv):
    parser = Parser(add_help=False)
    for name in ("--preview", "--receipt"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    return publish_after_yes(args.preview, args.receipt, Path(read_config()["data_folder"]) / PUBLISHED_TICKETS)


VERBS = {"outline": _outline_verb, "preview": _preview_verb, "publish": _publish_verb}


def main(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", EXIT_UNREADABLE)
    try:
        return VERBS[argv[0]](argv[1:])
    except OSError as error:
        raise Refusal("io-error", f"{type(error).__name__}: {error}", EXIT_UNREADABLE) from error


if __name__ == "__main__":
    sys.exit(serve(main))
