"""The pass history of a gate that ends a page session, shared by the grill gate and the design gate.

`last_pass_row(doc)` and `last_pass(row, session)`: the `- Last pass: R<n> · session <id>` row of a passed gate.
`changed(doc, since_round)`: the points changed after the round of the last passed gate.
`stale(spec_dir, writers)`: the later documents that may be out of date.
`open_questions(doc)`: the open questions for others of a version 2 page.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from round_document import ASKING, _carries_card, _components, current_round

# The run branch of a feature branch. Lockstep copy of check_plan.RUN_SUFFIX of to-subtasks, not imported: a test world
# copies only the skills it runs. test_pass_history.py compares them.
RUN_SUFFIX = "-run"
GIT_LIMIT_S = 30
# The round of the session's last passed gate; `changed` measures from it.
LAST_PASS_ROW = re.compile(r"^- Last pass: R([1-9][0-9]*) · session (\S+)$")
# The page lists whose entries carry change lines, with the field that names each entry (SDD §4).
ENTRY_TEXT = {"sections": ("section", "title"), "stories": ("story", "text"), "examples": ("example", "title"),
              "questions": ("question", "question")}


def card_text(item):
    """The first text of a card, else its id."""
    for component in _components(item["body"]):
        value = (component.get("props") or {}).get("text")
        if component.get("type") == "text" and value:
            return " ".join(value.split())
    return item["id"]


def last_pass(row, session):
    """The round that a `Last pass` row holds for the session, else None."""
    found = LAST_PASS_ROW.match(row)
    return int(found.group(1)) if found and found.group(2) == session else None


def last_pass_row(doc):
    return f"- Last pass: R{current_round(doc)['n']} · session {doc['session']['id']}"


def changed(doc, since_round):
    """Each point of round `since_round` or earlier that changed later: a card a later card carries, and an entry
    with a change line on both sides of that round. An entry added later is new, not changed. No pass yet: nothing."""
    if since_round is None:
        return []
    later = [card for rnd in doc["rounds"] if rnd["n"] > since_round for card in rnd["items"]]
    found = [{"id": item["id"], "kind": "card", "text": card_text(item)}
             for rnd in doc["rounds"] if rnd["n"] <= since_round for item in rnd["items"]
             if item["kind"] in ASKING and any(_carries_card(card, item["id"]) for card in later)]
    for name, (kind, field) in ENTRY_TEXT.items():
        for entry in doc.get(name) or []:
            rounds = [line.get("round", 0) for line in entry.get("changes") or []]
            if any(n <= since_round for n in rounds) and any(n > since_round for n in rounds):
                found.append({"id": entry["id"], "kind": kind, "text": entry[field]})
    return found


class _NoAnswer(Exception):
    """Git did not answer: no git program, or the shared time limit ran out."""


def run_plan(spec_dir):
    """`<run branch>:plan/PLAN.md` when git holds the plan of this feature branch, else None. When git does not
    answer within GIT_LIMIT_S for all its calls, that spec with ` (not checked: <reason>)`: the plan can be stale."""
    deadline = time.monotonic() + GIT_LIMIT_S

    def git(*args):
        left = deadline - time.monotonic()
        if left <= 0:
            raise _NoAnswer(f"git took more than {GIT_LIMIT_S} s")
        try:
            done = subprocess.run(["git", "-C", str(spec_dir), *args], capture_output=True, stdin=subprocess.DEVNULL,
                                  timeout=left)
        except subprocess.TimeoutExpired as error:
            raise _NoAnswer(f"git took more than {GIT_LIMIT_S} s") from error
        except OSError as error:
            raise _NoAnswer(f"git did not run: {error}") from error
        return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else None
    run = f"<feature branch>{RUN_SUFFIX}"
    try:
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        if not branch or branch == "HEAD":
            return None
        run = branch + RUN_SUFFIX
        for ref in (f"refs/heads/{run}", f"refs/remotes/origin/{run}"):
            if git("cat-file", "-e", f"{ref}:plan/PLAN.md") is not None:
                return f"{run}:plan/PLAN.md"
    except _NoAnswer as error:
        return f"{run}:plan/PLAN.md (not checked: {error})"
    return None


def stale(spec_dir, writers):
    """Each later document of the ticket that exists. `writers` holds (file name, record folder) pairs, both relative
    to `spec_dir`. An entry is a file path, or the git spec `<run branch>:plan/PLAN.md` (read it with `git show`), with
    ` (not checked: <reason>)` when git did not answer."""
    spec_dir = Path(spec_dir)
    found = []
    for name, folder in writers:
        found += [path for path in [spec_dir / name] if path.is_file()]
        found += sorted((spec_dir / folder).glob("*.md"))
    plan = run_plan(spec_dir)
    return [path.as_posix() for path in found] + ([plan] if plan else [])


def is_open(question):
    return question.get("state") == "open"


def open_questions(doc):
    """The questions for others that are still open."""
    return [question for question in doc.get("questions") or [] if is_open(question)]


def question_line(question):
    return f"{question['id']}: {question['question']} (who: {', '.join(question['who'])})"
