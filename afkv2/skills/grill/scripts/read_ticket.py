"""Read a ticket with its comments and links: `read_ticket.py --ticket KEY --out FILE`.

Calls the tracker command's read verbs only: issue-get on Jira, issue-get and issue-search on
GitHub issues. Writes one normalized JSON file and answers the counts. A link that cannot be
read goes to `unread_links` with its reason; only the ticket itself can refuse the whole read.
"""

from __future__ import annotations

import json
import re
import sys

from grill_common import PLUGIN_ROOT, Parser, Refusal, run_command, serve, write_json

TRACKER = PLUGIN_ROOT / "ports" / "tracker" / "cli.py"
TIMEOUT_S = 90
MAX_LINKS = 20
GITHUB_REFERENCE = re.compile(r"(?<![\w/#-])((?:[\w.-]+/[\w.-]+)?)#(\d+)\b")
BLOCK_NODES = {"paragraph", "heading", "listItem", "blockquote", "codeBlock", "tableRow", "rule"}


def tracker(verb, payload):
    return run_command(TRACKER, [verb, json.dumps(payload)], TIMEOUT_S)


def adf_text(node):
    """Plain text of a rich-text node; a string passes through."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_text(child) for child in node)
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    if node.get("type") in ("media", "mediaSingle", "mediaInline"):
        return "[picture]"
    text = adf_text(node.get("content"))
    return text.rstrip("\n") + "\n" if node.get("type") in BLOCK_NODES else text


def _is_jira(answer):
    return "fields" in answer or "description_hash" in answer


def _jira_issue(answer):
    fields = answer.get("fields") or {}
    comment = fields.get("comment") or {}
    comments = comment.get("comments") or []
    return {"key": answer.get("key"), "title": fields.get("summary"), "status": (fields.get("status") or {}).get("name"),
            "description": adf_text(answer.get("description")).strip(),
            "comments": [{"author": (c.get("author") or {}).get("displayName"), "created": c.get("created"),
                          "text": adf_text(c.get("body")).strip()} for c in comments],
            "comments_cut": max(0, (comment.get("total") or 0) - len(comments))}


def _github_issue(answer):
    comments = answer.get("comments") or []
    return {"key": str(answer.get("key")), "title": answer.get("title"), "status": answer.get("state"),
            "description": answer.get("body") or "",
            "comments": [{"author": (c.get("author") or {}).get("login"), "created": c.get("createdAt"),
                          "text": c.get("body") or ""} for c in comments],
            "comments_cut": 0}


def _jira_links(answer):
    links = []
    for link in (answer.get("fields") or {}).get("issuelinks") or []:
        kind = link.get("type") or {}
        for side, name in (("inwardIssue", "inward"), ("outwardIssue", "outward")):
            if link.get(side):
                links.append({"key": link[side].get("key"), "relation": kind.get(name) or kind.get("name")})
    return links


def _github_links(issue):
    """References in the body and comments, then the issues that mention this one, and what could not be searched."""
    texts = [issue["description"], *(c["text"] for c in issue["comments"])]
    links, seen = [], {issue["key"]}
    for text in texts:
        for repo, number in GITHUB_REFERENCE.findall(text):
            key = f"{repo}#{number}" if repo else number
            if key not in seen:
                seen.add(key)
                links.append({"key": key, "relation": "named in this ticket"})
    try:
        found = tracker("issue-search", {"query": f'"#{issue["key"]}"'}).get("issues") or []
    except Refusal as refusal:
        return links, [{"key": f"mentions of #{issue['key']}", "reason": f"issue-search: {refusal.code}: {refusal.reason}"}]
    for match in found:
        key = str(match.get("number"))
        if key not in seen:
            seen.add(key)
            links.append({"key": key, "relation": "mentions this ticket"})
    return links, []


def _read_link(link, normalize):
    payload = {"key": link["key"]}
    if "/" in link["key"]:
        payload["tracker"] = "github-issues"
    issue = normalize(tracker("issue-get", payload))
    return {**link, "title": issue["title"], "status": issue["status"], "description": issue["description"]}


def read_ticket(key):
    answer = tracker("issue-get", {"key": key})
    if _is_jira(answer):
        issue, normalize = _jira_issue(answer), _jira_issue
        links, unread = _jira_links(answer), []
    else:
        issue, normalize = _github_issue(answer), _github_issue
        links, unread = _github_links(issue)
    read = []
    for position, link in enumerate(links):
        if position >= MAX_LINKS:
            unread.append({**link, "reason": f"over the limit of {MAX_LINKS} links"})
            continue
        try:
            read.append(_read_link(link, normalize))
        except Refusal as refusal:
            unread.append({**link, "reason": f"{refusal.code}: {refusal.reason}"})
    return {**issue, "links": read, "unread_links": unread}


def main(argv):
    parser = Parser(add_help=False)
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    ticket = read_ticket(args.ticket)
    write_json(args.out, ticket)
    return {"ok": True, "out": args.out, "key": ticket["key"], "title": ticket["title"],
            "comments": len(ticket["comments"]), "comments_cut": ticket["comments_cut"],
            "links": len(ticket["links"]), "unread_links": ticket["unread_links"]}


if __name__ == "__main__":
    sys.exit(serve(main))
