"""The tracker command: `cli.py <verb> [json-payload]`, or the payload on stdin."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tracker import envelope, github_issues, jira, settings  # noqa: E402

KINDS = {"jira": jira, "github-issues": github_issues}


def _kind_and_repo(payload):
    tracker = (settings.read_config().get("tracker") or {}) if not payload.get("tracker") else {}
    kind = payload.get("tracker") or tracker.get("kind")
    if kind is not None and not isinstance(kind, str):
        raise envelope.Refusal("bad-payload", "`tracker` must be a word: " + " or ".join(KINDS))
    if kind not in KINDS:
        raise envelope.Refusal("no-tracker", f"no tracker kind ({kind}): the repository config names no "
                                             f"{' or '.join(KINDS)} tracker, and the payload has no `tracker`")
    if not payload.get("tracker") and not payload.get("repo") and tracker.get("repo"):
        payload = {**payload, "repo": tracker["repo"]}
    return kind, payload


def _issue_get(payload):
    kind, payload = _kind_and_repo(payload)
    return KINDS[kind].issue_get(payload)


def _issue_search(payload):
    kind, payload = _kind_and_repo(payload)
    if kind != "github-issues":
        raise envelope.Refusal("unsupported", f"issue-search has no {kind} form")
    return github_issues.issue_search(payload)


VERBS = {
    "issue-get": _issue_get,
    "issue-search": _issue_search,
    "md-to-adf": jira.md_to_adf,
    "attachment-list": jira.attachment_list,
    "attachment-put": jira.attachment_put,
    "attachment-delete": jira.attachment_delete,
    "description-put": jira.description_put,
}


def tracker_main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(tracker_main())
