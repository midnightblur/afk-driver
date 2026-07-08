#!/usr/bin/env python3
"""
publish_meeting.py — publish a meeting summary into a Jira Cloud issue as a
collapsible ADF `expand`, idempotently.

This is the meeting-mode engine behind /afk:to-ticket. Where publish_prd.py owns
the PRD body (sentinel-delimited managed block), this owns the "Meeting
Summaries" region: a plain `Meeting Summaries` heading followed by one
collapsible `expand` per meeting (the expand title is the meeting's key). It
does the parts that must be byte-for-byte reproducible:

  1. Convert the meeting body Markdown to ADF via the shared md->ADF mapping
     (reused from publish_prd.py — one home for that logic).
  2. Wrap the body in an `expand` node whose `attrs.title` is the meeting key
     ("{date} — {title}", or just "{title}" when no date is given).
  3. Merge into the issue description:
       - locate the level-2 `Meeting Summaries` heading (create it at the top of
         the description if absent — matching the human convention);
       - the meetings are the contiguous run of `expand` nodes right after that
         heading;
       - a meeting whose title matches an existing expand REPLACES it in place
         (idempotent re-run); a new title is INSERTED newest-first, directly
         after the heading.
  4. Everything else in the description — the PRD managed block, product-owner
     prose, any trailing rule/notes — is preserved verbatim; only the one
     expand this run owns is added or replaced.

The meeting body is authored by the caller (synthesized from a transcript or
notes) into a Markdown file in the shape documented in REFERENCE.md
("Meeting Summaries publish"); this script publishes whatever that file
contains, wrapped and merged — nothing more.

Usage:
    python publish_meeting.py --parent P2P-1220 \
        --title "Demo & QA" --date 2026-07-08 \
        --meeting path/to/MEETING.md [--dry-run] [--yes]

Credentials are resolved exactly as publish_prd.py does (OS env, else the Jira
MCP server's env block in ~/.claude.json). Nothing is hardcoded.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Reuse the shared engine pieces — one home for creds, REST, and md->ADF.
# When run as `python scripts/publish_meeting.py`, this file's directory is on
# sys.path[0], so the sibling module resolves.
from publish_prd import Jira, load_creds, md_to_adf_content, node_text

MEETING_HEADING = "Meeting Summaries"


# ============================================================================
# Meeting-region merge (owns only the one expand this run publishes)
# ============================================================================
def heading_paragraph():
    return {"type": "heading", "attrs": {"level": 2},
            "content": [{"type": "text", "text": MEETING_HEADING}]}


def is_meeting_heading(node):
    return (node.get("type") == "heading"
            and node.get("attrs", {}).get("level") == 2
            and node_text(node).strip().lower() == MEETING_HEADING.lower())


def expand_title(node):
    if node.get("type") == "expand":
        return node.get("attrs", {}).get("title", "")
    return None


def build_description(existing_adf, expand_node, title):
    """Return (new_doc, action). action ∈ {created, inserted, replaced}."""
    content = list((existing_adf or {}).get("content", [])
                   if isinstance(existing_adf, dict) else [])

    h = next((i for i, n in enumerate(content) if is_meeting_heading(n)), None)
    if h is None:
        # No section yet: create it at the top of the description, matching the
        # human convention (heading first, meetings below).
        return {"version": 1, "type": "doc",
                "content": [heading_paragraph(), expand_node, *content]}, "created"

    # The meetings are the contiguous run of expands right after the heading.
    run = h + 1
    while run < len(content) and content[run].get("type") == "expand":
        run += 1
    for k in range(h + 1, run):
        if expand_title(content[k]) == title:
            content[k] = expand_node                     # idempotent re-run
            return {"version": 1, "type": "doc", "content": content}, "replaced"
    content.insert(h + 1, expand_node)                   # newest-first
    return {"version": 1, "type": "doc", "content": content}, "inserted"


# ============================================================================
# Main
# ============================================================================
def main():
    ap = argparse.ArgumentParser(
        description="Publish a meeting summary into a Jira issue as a collapsible expand (ADF).")
    ap.add_argument("--parent", required=True, help="Jira issue key, e.g. P2P-1220")
    ap.add_argument("--meeting", required=True, help="path to the meeting body Markdown")
    ap.add_argument("--title", required=True,
                    help="short meeting name; the expand key becomes '{date} — {title}'")
    ap.add_argument("--date", default="",
                    help="meeting date (ISO, e.g. 2026-07-08); prefixed onto the expand title")
    ap.add_argument("--dry-run", action="store_true",
                    help="convert + plan only; mutate nothing, write the would-be ADF")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = ap.parse_args()

    md_path = Path(args.meeting)
    if not md_path.exists():
        sys.exit(f"ERROR: meeting body not found: {md_path}")
    body = md_to_adf_content(md_path.read_text(encoding="utf-8"), {})
    if not body:
        sys.exit("ERROR: meeting body is empty — nothing to publish.")

    full_title = f"{args.date} — {args.title}".strip(" —") if args.date else args.title
    expand_node = {"type": "expand", "attrs": {"title": full_title}, "content": body}

    base, email, token = load_creds()
    jira = Jira(base, email, token)
    issue = jira.get_issue(args.parent, "summary,description")
    new_desc, action = build_description(issue["fields"].get("description"), expand_node, full_title)

    print(f"\nparent      : {args.parent} — {issue['fields']['summary']}")
    print(f"meeting     : {md_path}")
    print(f"expand title: {full_title!r}")
    print(f"body blocks : {len(body)}")
    print(f"action      : {action}  (created=new section · inserted=new meeting · replaced=same-title update)")
    print(f"ADF blocks  : {len(new_desc['content'])}")

    if args.dry_run:
        out = md_path.with_suffix(".adf.json")
        out.write_text(json.dumps(new_desc, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[dry-run] wrote ADF to {out} — nothing mutated.")
        return

    if not args.yes:
        ans = input("\nPUT this description to the issue? [y/N] ").strip().lower()
        if ans != "y":
            sys.exit("aborted.")
    jira.update_description(args.parent, new_desc)
    print(f"\nDONE: {args.parent} description updated ({action}).")


if __name__ == "__main__":
    main()
