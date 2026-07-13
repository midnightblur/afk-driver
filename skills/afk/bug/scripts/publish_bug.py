#!/usr/bin/env python3
"""
publish_bug.py — deterministic Jira engine for the bug-lifecycle publisher.

Owns the bug-lifecycle REST calls (SDD §9b seam "Jira REST v3"): create a Bug
from an on-disk evidence bundle (assignee, labels, optional FixVersion),
embed screenshots inline (attach + media-UUID 303 trick), transition it to
Dev-Pending, append lifecycle evidence comments (MR link / Ready / retest
verdict), and backfill FixVersion once a non-blocking ask resolves.

Builds on the plugin-root shared Jira lib `scripts/jira_core.py` (ADR-0001):
creds resolution, the REST client + auth, Markdown→ADF conversion, attachment
upload and media-UUID extraction, PNG sizing. This script keeps only the
bug-specific concerns — the create/transition/comment/backfill payloads and the
retry posture around them.

Failure affordance (SDD §9b, §3): every non-2xx and every failed transition is
surfaced as a non-zero exit carrying the response body — never swallowed. A
provided FixVersion is validated against the project's versions before any
write; unknown → non-zero exit, nothing created. Transient (5xx / network)
calls retry twice with exponential backoff before failing (SDD §5).

Usage:
    python publish_bug.py create   --project P2P --summary "…" --bundle bundle.md
                                    [--assignee ACCID] [--label L]... [--fix-version V]
                                    [--screenshot PNG]... [--dry-run]
    python publish_bug.py transition --key P2P-123 [--dry-run]
    python publish_bug.py comment    --key P2P-123 --body "…" | --body-file f.md [--dry-run]
    python publish_bug.py backfill   --key P2P-123 --project P2P --fix-version V [--dry-run]

Credentials resolve exactly as jira_core.load_creds documents (env vars, then
the Jira MCP env block in ~/.claude.json). Nothing is hardcoded.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
from pathlib import Path

# The shared Jira machinery lives at the plugin root (workflow/scripts/), five
# directories up from this file (scripts/bug/afk/skills/workflow).
_PLUGIN_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))), "scripts")
if _PLUGIN_SCRIPTS not in sys.path:
    sys.path.insert(0, _PLUGIN_SCRIPTS)

from jira_core import (  # noqa: E402
    Jira,
    load_creds,
    md_to_adf_content,
    png_size,
)

# Dev-Pending transition id — verified live against the P2P project this session
# (SDD §3 consumed-contract table; PRD Further Notes). The plugin transitions the
# ticket exactly once, to this state (PRD AC-014).
DEV_PENDING_TRANSITION_ID = "12463"

# Retry posture (SDD §5): 1 attempt + this many retries, exponential backoff.
JIRA_RETRIES = 2
BACKOFF_BASE_SECONDS = 0.5


class BugPublishError(Exception):
    """A Jira REST call failed. Carries the response body so the failure is
    surfaced to the caller (non-zero exit), never swallowed (SDD §9b)."""


class FixVersionError(BugPublishError):
    """A provided FixVersion does not exist in the project — re-ask, write
    nothing (PRD AC-004)."""


# ============================================================================
# REST plumbing — retry + never-swallow around the shared client's _req
# ============================================================================
def _sleep_backoff(attempt):
    """Exponential backoff between transient-failure retries (SDD §5)."""
    time.sleep(BACKOFF_BASE_SECONDS * (2 ** attempt))


def _request(jira, method, path, payload=None, *, retries=JIRA_RETRIES):
    """Issue one JSON REST call via the shared client, with the SDD §5 retry
    posture. Returns parsed JSON (or None on an empty body). A 4xx is
    deterministic → raised immediately with the response body. A 5xx / network
    error retries with exponential backoff, then raises. Nothing is swallowed."""
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else None
    attempt = 0
    while True:
        try:
            resp = jira._req(method, path, data=data, headers=headers)
            body = resp.read()
            return json.loads(body) if body else None
        except urllib.error.HTTPError as e:
            surfaced = _read_error_body(e)
            if e.code >= 500 and attempt < retries:
                _sleep_backoff(attempt)
                attempt += 1
                continue
            raise BugPublishError(
                f"{method} {path} -> HTTP {e.code}: {surfaced}") from e
        except urllib.error.URLError as e:
            if attempt < retries:
                _sleep_backoff(attempt)
                attempt += 1
                continue
            raise BugPublishError(f"{method} {path} -> network error: {e}") from e


def _read_error_body(e):
    try:
        raw = e.read()
        body = raw.decode(errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    except Exception:  # noqa: BLE001 — body already gone; report what we have
        body = getattr(e, "reason", "") or ""
    finally:
        try:
            e.close()
        except Exception:  # noqa: BLE001
            pass
    return body


# ============================================================================
# Pure payload builders (the seam-test asserts on these + the wiring below)
# ============================================================================
def bundle_to_adf(bundle_md):
    """Evidence-bundle markdown → ADF content array. Confidence labels
    (verified / inferred / guessed) are plain text in the bundle, so they render
    visibly in the ticket body (PRD AC-005). No figures here — screenshots embed
    separately after create, once the media UUID is known."""
    return md_to_adf_content(bundle_md, {})


def description_doc(content):
    """Wrap an ADF content array in a top-level doc node."""
    return {"type": "doc", "version": 1, "content": content}


def build_create_fields(project_key, summary, description, *,
                        assignee_account_id=None, labels=None, fix_version=None):
    """Build the issue-create `{"fields": {...}}` payload (SDD §3 POST /issue).
    Optional fields are omitted when absent, never sent empty."""
    fields = {
        "project": {"key": project_key},
        "issuetype": {"name": "Bug"},
        "summary": summary,
        "description": description,
    }
    if assignee_account_id:
        fields["assignee"] = {"accountId": assignee_account_id}
    if labels:
        fields["labels"] = list(labels)
    if fix_version:
        fields["fixVersions"] = [{"name": fix_version}]
    return {"fields": fields}


def build_transition_payload(transition_id=DEV_PENDING_TRANSITION_ID):
    return {"transition": {"id": transition_id}}


def build_comment_payload(md_text):
    return {"body": description_doc(md_to_adf_content(md_text, {}))}


def _media_node(uuid, width, height):
    """Inline media block — the only shape Jira Cloud renders inline
    (collection="")."""
    return {
        "type": "mediaSingle", "attrs": {"layout": "center"},
        "content": [{"type": "media", "attrs": {
            "type": "file", "id": uuid, "collection": "",
            "width": width, "height": height}}],
    }


# ============================================================================
# FixVersion validation
# ============================================================================
def project_version_names(jira, project_key):
    """Names of the project's existing versions (SDD §3 — validated before any
    FixVersion write)."""
    versions = _request(jira, "GET", f"/rest/api/3/project/{project_key}/versions") or []
    return {v.get("name") for v in versions}


def _ensure_fix_version(jira, project_key, fix_version):
    if fix_version is None:
        return
    names = project_version_names(jira, project_key)
    if fix_version not in names:
        raise FixVersionError(
            f"FixVersion '{fix_version}' does not exist in project {project_key}. "
            f"Known versions: {sorted(n for n in names if n)}. Nothing was written.")


# ============================================================================
# Bug-lifecycle REST calls (the seam this subtask owns)
# ============================================================================
def create_bug(jira, project_key, summary, bundle_md, *,
               assignee_account_id=None, labels=None, fix_version=None,
               screenshots=None):
    """Create a Bug from the evidence bundle and return its ticket key.

    A provided FixVersion is validated FIRST — unknown raises FixVersionError
    before any POST, so nothing is written (PRD AC-004). Screenshots are
    uploaded and embedded inline after create (the media UUID needs the key),
    then the description is re-PUT with the media nodes appended."""
    _ensure_fix_version(jira, project_key, fix_version)

    content = bundle_to_adf(bundle_md)
    fields = build_create_fields(
        project_key, summary, description_doc(content),
        assignee_account_id=assignee_account_id, labels=labels,
        fix_version=fix_version)
    created = _request(jira, "POST", "/rest/api/3/issue", fields)
    if not created or "key" not in created:
        raise BugPublishError(
            f"POST /rest/api/3/issue returned no ticket key: {created!r}")
    key = created["key"]

    # Embed screenshots inline after create (the media UUID needs the key). The
    # ticket already exists, so a failure here must NOT lose it — per SDD §3 the
    # embed edge degrades to "comment without inline embed, paths listed" rather
    # than aborting. Attachments are uploaded regardless, so they stay listed on
    # the ticket even when the inline media node can't be built.
    media_nodes = _embed_screenshots(jira, key, screenshots or [])
    if media_nodes:
        try:
            jira.update_description(key, description_doc(content + media_nodes))
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            print(f"WARNING: could not embed screenshots inline into {key} "
                  f"({e}); the attachments remain listed on the ticket.",
                  file=sys.stderr)
    return key


def _embed_screenshots(jira, key, screenshots):
    """Upload + resolve each screenshot into an inline media node. A per-shot
    failure (upload non-2xx, or a 303 whose Location carries no media UUID)
    degrades: the attachment is still listed on the ticket, and we skip only its
    inline node — the create never fails for a screenshot (SDD §3 embed edge)."""
    nodes = []
    for path in screenshots:
        try:
            att_id = jira.upload_attachment(key, path)
            uuid = jira.resolve_media_uuid(att_id)
            width, height = png_size(path) or (800, 600)
            nodes.append(_media_node(uuid, width, height))
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as e:
            print(f"WARNING: inline embed failed for {path} on {key} ({e}); "
                  f"the attachment stays listed on the ticket.", file=sys.stderr)
    return nodes


def transition_to_dev_pending(jira, key, transition_id=DEV_PENDING_TRANSITION_ID):
    """Transition the ticket to Dev-Pending. A failed transition is surfaced as
    a non-zero exit with the response body, never swallowed (SDD §9b)."""
    _request(jira, "POST", f"/rest/api/3/issue/{key}/transitions",
             build_transition_payload(transition_id))


def append_evidence_comment(jira, key, md_text):
    """Append one lifecycle evidence comment (MR link / Ready / retest verdict)
    as ADF. Returns the created comment id."""
    created = _request(jira, "POST", f"/rest/api/3/issue/{key}/comment",
                       build_comment_payload(md_text))
    return (created or {}).get("id")


def backfill_fix_version(jira, key, project_key, fix_version):
    """Set FixVersion after a non-blocking ask resolves. Validated against the
    project's versions first — unknown raises, nothing written (PRD AC-004)."""
    _ensure_fix_version(jira, project_key, fix_version)
    _request(jira, "PUT", f"/rest/api/3/issue/{key}",
             {"fields": {"fixVersions": [{"name": fix_version}]}})


# ============================================================================
# CLI
# ============================================================================
def _read_bundle(path):
    return Path(path).read_text(encoding="utf-8")


def _connect():
    base, email, token = load_creds()
    return Jira(base, email, token)


def _cmd_create(args):
    bundle_md = _read_bundle(args.bundle)
    if args.dry_run:
        desc = description_doc(bundle_to_adf(bundle_md))
        fields = build_create_fields(
            args.project, args.summary, desc,
            assignee_account_id=args.assignee, labels=args.label,
            fix_version=args.fix_version)
        print(json.dumps(fields, indent=2, ensure_ascii=False))
        if args.screenshot:
            print(f"[dry-run] would attach+embed {len(args.screenshot)} screenshot(s) "
                  f"after create, then re-PUT the description.")
        print("[dry-run] nothing written.")
        return
    jira = _connect()
    key = create_bug(jira, args.project, args.summary, bundle_md,
                     assignee_account_id=args.assignee, labels=args.label,
                     fix_version=args.fix_version, screenshots=args.screenshot)
    print(key)


def _cmd_transition(args):
    if args.dry_run:
        print(json.dumps(build_transition_payload(), indent=2))
        print("[dry-run] nothing written.")
        return
    transition_to_dev_pending(_connect(), args.key)
    print(f"{args.key} -> Dev-Pending")


def _cmd_comment(args):
    md = args.body if args.body is not None else _read_bundle(args.body_file)
    if args.dry_run:
        print(json.dumps(build_comment_payload(md), indent=2, ensure_ascii=False))
        print("[dry-run] nothing written.")
        return
    append_evidence_comment(_connect(), args.key, md)
    print(f"{args.key} <- evidence comment")


def _cmd_backfill(args):
    if args.dry_run:
        print(json.dumps({"fields": {"fixVersions": [{"name": args.fix_version}]}}, indent=2))
        print("[dry-run] validated on real run before write; nothing written now.")
        return
    backfill_fix_version(_connect(), args.key, args.project, args.fix_version)
    print(f"{args.key} fixVersion={args.fix_version}")


def _build_parser():
    p = argparse.ArgumentParser(description="Jira Bug lifecycle publisher for /afk:bug.")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="create a Bug from an evidence bundle")
    c.add_argument("--project", required=True)
    c.add_argument("--summary", required=True)
    c.add_argument("--bundle", required=True, help="path to the evidence bundle markdown")
    c.add_argument("--assignee", help="assignee Jira accountId (K1)")
    c.add_argument("--label", action="append", default=[], help="repeatable ticket label")
    c.add_argument("--fix-version", dest="fix_version", help="optional FixVersion (validated)")
    c.add_argument("--screenshot", action="append", default=[], help="repeatable PNG to embed")
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(func=_cmd_create)

    t = sub.add_parser("transition", help="transition a Bug to Dev-Pending")
    t.add_argument("--key", required=True)
    t.add_argument("--dry-run", action="store_true")
    t.set_defaults(func=_cmd_transition)

    m = sub.add_parser("comment", help="append a lifecycle evidence comment")
    m.add_argument("--key", required=True)
    g = m.add_mutually_exclusive_group(required=True)
    g.add_argument("--body")
    g.add_argument("--body-file", dest="body_file")
    m.add_argument("--dry-run", action="store_true")
    m.set_defaults(func=_cmd_comment)

    b = sub.add_parser("backfill", help="set FixVersion after a non-blocking ask resolves")
    b.add_argument("--key", required=True)
    b.add_argument("--project", required=True)
    b.add_argument("--fix-version", dest="fix_version", required=True)
    b.add_argument("--dry-run", action="store_true")
    b.set_defaults(func=_cmd_backfill)
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    try:
        args.func(args)
    except (BugPublishError, OSError) as e:
        # BugPublishError = a surfaced Jira failure (with response body); OSError
        # = an operational input error (missing --bundle / --screenshot file).
        # Both exit non-zero with a clean message rather than a raw traceback.
        sys.exit(f"ERROR: {e}")


if __name__ == "__main__":
    main()
