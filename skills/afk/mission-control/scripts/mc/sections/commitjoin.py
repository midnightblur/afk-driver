"""Shared commit↔subtask join. Two deterministic signals, in priority order:

1. Subject tag `[NNNN-slug]` (or the bare subtask id anywhere in the subject).
2. Commit hashes the journal records on that subtask's own event lines
   (executors journal '2 commits <sha>/<sha> ...'), prefix-matched against
   real history — a mined token that matches no commit is dropped.

Feature-level commits carry the parent ticket tag `[{ticket}]` (case-
insensitive) without a subtask id. Anything matching neither is repo noise
(the spec folder shares history with the whole monorepo) and is excluded.
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import gitio, journal

_MAX_LOG = 2000
_HASH_TOKEN_RE = re.compile(r"\b[0-9a-f]{9,40}\b")
_SUBTASK_TAG_RE = re.compile(r"\b(\d{4}-[a-z0-9-]+)\b")


def join(spec_dir: Path, subtask_ids: list, parent_ticket: str) -> dict:
    """{'by_subtask': {id: [commit]}, 'feature': [commit], 'scanned': int}
    where commit = {short, subject}. Empty shells when git is unavailable."""
    log = gitio.log_subjects(spec_dir, _MAX_LOG)
    if not log:
        return {"by_subtask": {}, "feature": [], "scanned": 0}

    id_set = set(subtask_ids)
    ticket = (parent_ticket or "").strip().lower()
    journal_hashes = _journal_hashes(spec_dir, id_set)

    by_subtask = {}
    feature = []
    for commit in log:
        subject = commit["subject"]
        entry = {"short": commit["short"], "subject": subject}
        subtask_id = _subject_subtask(subject, id_set)
        if subtask_id is None:
            subtask_id = _hash_subtask(commit["full"], journal_hashes)
        if subtask_id is not None:
            by_subtask.setdefault(subtask_id, []).append(entry)
        elif ticket and f"[{ticket}]" in subject.lower():
            feature.append(entry)
    return {"by_subtask": by_subtask, "feature": feature, "scanned": len(log)}


def _subject_subtask(subject: str, id_set: set):
    for match in _SUBTASK_TAG_RE.finditer(subject):
        if match.group(1) in id_set:
            return match.group(1)
    return None


def _hash_subtask(full_hash: str, journal_hashes: dict):
    for subtask_id, prefixes in journal_hashes.items():
        for prefix in prefixes:
            if full_hash.startswith(prefix):
                return subtask_id
    return None


def _journal_hashes(spec_dir: Path, id_set: set) -> dict:
    """{subtask_id: {hash-prefix, ...}} mined from that subtask's own journal
    lines. Only hex tokens ≥9 chars — shorter ones collide with real words."""
    events = journal.parse_journal(spec_dir) or []
    mined = {}
    for event in events:
        subject = event["subject"]
        if subject not in id_set:
            continue
        for blob in (event["event"], event["plain"]):
            for match in _HASH_TOKEN_RE.finditer(blob):
                mined.setdefault(subject, set()).add(match.group(0))
    return mined
