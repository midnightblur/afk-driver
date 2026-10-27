#!/usr/bin/env afk-python
"""publish_bug_mode: the bug and ad-hoc mode of /afk:to-ticket, against stub trackers.

Each stub keeps the tickets it was asked to write, so a test asserts both the
payloads and what a re-run finds. Nothing here opens a socket or runs `gh`.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _path in (ROOT / "skills" / "afk" / "to-ticket" / "scripts", ROOT / "scripts"):
    sys.path.insert(0, str(_path))

import publish_bug_mode as mode  # noqa: E402
import tracker_api  # noqa: E402

WORK = "bug-export-drops-row"
PARTS = {
    "Work id": WORK,
    "Ticket key": "",
    "Verdict": "V-1 obvious fix",
    "Base": "main@0123abc",
    "Diagnosis branch": f"fix/{WORK}",
    "Symptom": "- [verified] the export has one row fewer than the grid",
    "Spec comparison": "- [verified] PRD AC-3 says every visible row exports",
    "Reproduction": "- [verified] `tests/test_export.py::test_last_row` fails on the Base commit",
    "Attempts": "",
    "Root cause": "- [inferred] the loop stops one short at `export.py:42`",
    "Fix proposal": "Iterate to the end of the filtered rows.",
    "Approval": "",
    "Outside writes": "",
}
WRITES = ("tracker_create", "tracker_edit", "tracker_comment", "tracker_transition", "tracker_attach")


def diagnosis(tmp_path, folder=WORK, **changes):
    parts = dict(PARTS, **changes)
    text = "# Diagnosis\n\n" + "".join(
        f"## {name}\n{body}\n\n" if body else f"## {name}\n\n" for name, body in parts.items()
        if body is not None)
    path = tmp_path / "docs" / folder / "DIAGNOSIS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def part(path, name):
    return mode._part_text(Path(path), name)


class Lost:
    """A scripted failure whose write never reached the tracker."""

    def __init__(self, answer):
        self.answer = answer


PASS = object()  # a scripted slot that keeps the stub's own answer


class Stub:
    """Shared bookkeeping: calls, scripted answers, and the tickets written."""

    def __init__(self):
        self.calls, self.script, self.issues, self.attachments = [], {}, {}, {}

    def call(self, operation, payload):
        """A scripted answer replaces the stub's own; `Lost(answer)` also skips the write."""
        self.calls.append((operation, json.loads(json.dumps(payload))))
        queued = self.script.get(operation)
        if queued and isinstance(queued[0], Lost):
            return queued.pop(0).answer
        answer = getattr(self, operation)(payload)
        scripted = queued.pop(0) if queued else PASS
        return answer if scripted is PASS else scripted

    def writes(self, operation=None):
        return [c for c in self.calls if c[0] in WRITES and (operation is None or c[0] == operation)]

    def comments(self, key):
        return self.issues[key]["comments"]

    def tracker_comment(self, p):
        self.comments(p["ticket_key"]).append(p["text"])
        return {"id": str(len(self.comments(p["ticket_key"])))}


class StubJira(Stub):
    TYPES = ("Bug", "Story")
    VERSIONS = ("1.4", "1.5")

    def resolve_creds_env(self):
        return {"JIRA_BASE_URL": "https://jira.example.test"}

    def add(self, key, **fields):
        self.issues[key] = dict({"description": "", "comments": [], "status": "Open",
                                 "fixVersions": []}, **fields)

    def tracker_get(self, p):
        issue = self.issues.get(p["ticket_key"])
        if issue is None:
            return {"error": True, "status": 404, "body": "Issue does not exist"}
        return {"key": p["ticket_key"], "fields": {
            "description": issue["description"],
            "comment": {"comments": [{"body": text} for text in issue["comments"]]},
            "status": {"name": issue["status"]},
            "fixVersions": [{"name": v} for v in issue["fixVersions"]]}}

    def tracker_search(self, p):
        query = p["query"]
        for field_name, known in (("issuetype", self.TYPES), ("fixVersion", self.VERSIONS)):
            if f"{field_name} = " in query:
                value = query.split(f'{field_name} = "', 1)[1].split('"', 1)[0]
                if value not in known:
                    return {"error": True, "status": 400, "body": f"The value '{value}' does not exist"}
                return {"issues": []}
        marker = query.split('~ "\\"', 1)[1].split('\\""', 1)[0]
        return {"issues": [{"key": k} for k, i in self.issues.items() if marker in i["description"]]}

    def tracker_create(self, p):
        key = f"PROJ-{len(self.issues) + 1}"
        self.add(key, description=p["description"], payload=p)
        return {"key": key, "id": "1000"}

    def tracker_edit(self, p):
        self.issues[p["ticket_key"]]["fixVersions"] = [v["name"] for v in p["fields"]["fixVersions"]]
        return {"ok": True}

    def tracker_transitions(self, p):
        return {"transitions": [{"id": "31", "name": "Start review", "to": {"name": "In Review"}},
                                {"id": "41", "name": "Done", "to": {"name": "Done"}}]}

    def tracker_transition(self, p):
        self.issues[p["ticket_key"]]["status"] = "In Review"
        return {"ok": True}

    def tracker_attachments(self, p):
        return [{"id": str(n), "filename": name}
                for n, name in enumerate(self.attachments.get(p["ticket_key"], []))]

    def tracker_attach(self, p):
        names = [os.path.basename(f) for f in p["files"]]
        self.attachments.setdefault(p["ticket_key"], []).extend(names)
        self.comments(p["ticket_key"]).append(p["text"])
        return {"ok": True, "attached": [{"file": f} for f in p["files"]], "mismatches": [],
                "unsupported_files": []}


class StubGitHub(Stub):
    LABELS = ("bug", "enhancement", "status:in-review")

    def __init__(self, labels=LABELS):
        super().__init__()
        self.labels = labels

    def _repo_args(self):
        return []

    def _gh(self, *args):
        self.calls.append(("gh", list(args)))
        assert args[:2] == ("label", "list")
        return [{"name": name} for name in self.labels]

    def add(self, key, **fields):
        self.issues[key] = dict({"body": "", "comments": [], "labels": []}, **fields)

    def tracker_get(self, p):
        issue = self.issues.get(str(p["ticket_key"]))
        if issue is None:
            return {"error": True, "status": 1, "body": "Could not resolve to an issue"}
        return {"number": int(p["ticket_key"]), "body": issue["body"], "state": "OPEN",
                "url": f"https://github.com/o/r/issues/{p['ticket_key']}",
                "comments": [{"body": text} for text in issue["comments"]],
                "labels": [{"name": label} for label in issue["labels"]]}

    def tracker_search(self, p):
        marker = p["query"].split('"', 2)[1]
        return [{"number": int(k)} for k, i in self.issues.items() if marker in i["body"]]

    def tracker_create(self, p):
        key = str(len(self.issues) + 1)
        self.add(key, body=p["description"], labels=[p["issue_type"]], payload=p)
        return {"key": key, "url": f"https://github.com/o/r/issues/{key}"}

    def tracker_transitions(self, p):
        held = self.issues[str(p["ticket_key"])]["labels"]
        return {"transitions": [
            {"id": "open", "name": "open", "native": True, "current": True},
            {"id": "in-review", "name": "in-review", "label": "status:in-review",
             "current": "status:in-review" in held}]}

    def tracker_transition(self, p):
        self.issues[str(p["ticket_key"])]["labels"].append("status:in-review")
        return {"ok": True, "state": "in-review", "label": "status:in-review"}

    def tracker_attachments(self, p):
        return {"attachments": [], "partial": True}

    def tracker_attach(self, p):
        shown = [f for f in p["files"] if f.endswith(".png")]
        other = [{"file": f, "reason": "gh attaches only image and video files"}
                 for f in p["files"] if f not in shown]
        self.comments(str(p["ticket_key"])).append(p["text"])
        return {"ok": True, "attached": [{"file": f} for f in shown], "unsupported_files": other}


JIRA = {"tracker": "jira", "developer": {"trackerAssignee": "dev@example.test"},
        "jira": {"project": "PROJ", "transitions": {"in-review": "31"},
                 "issue-types": {"bug": "Bug", "enhancement": "Story"}}}
GITHUB = {"tracker": "github-issues", "developer": {"trackerAssignee": "dev"},
          "github-issues": {"state-labels": {"in-review": "status:in-review"}}}


def run(source, stub, config, tmp_path, **options):
    sleeps = []
    options.setdefault("consent", "person")
    options.setdefault("yes", True)
    options.setdefault("resolve", lambda key: str(tmp_path / "docs" / key))
    result = mode.run_bug_mode(source, tracker=stub, config=config, sleep=sleeps.append, **options)
    result.sleeps = sleeps
    return result


# --- create and update --------------------------------------------------------

def test_jira_create_from_a_diagnosis_prints_the_ticket_line(tmp_path):
    stub, path = StubJira(), diagnosis(tmp_path)
    result = run(path, stub, JIRA, tmp_path)
    assert result.code == 0, result.lines
    assert result.ticket == "TICKET: PROJ-1 https://jira.example.test/browse/PROJ-1"
    payload = stub.issues["PROJ-1"]["payload"]
    assert payload["issue_type"] == "Bug" and payload["project"] == "PROJ"
    assert payload["assignee"] == "dev@example.test"
    assert f"afk-evidence {WORK} ticket" in payload["description"]
    assert "the loop stops one short" in payload["description"]


def test_github_create_uses_the_type_label_and_the_issue_link(tmp_path):
    stub, path = StubGitHub(), diagnosis(tmp_path)
    result = run(path, stub, GITHUB, tmp_path, ticket_type="enhancement")
    assert result.code == 0, result.lines
    assert result.ticket == "TICKET: 1 https://github.com/o/r/issues/1"
    assert stub.issues["1"]["payload"]["issue_type"] == "enhancement"


def test_jira_enhancement_maps_through_the_configured_issue_type(tmp_path):
    stub = StubJira()
    result = run(diagnosis(tmp_path), stub, JIRA, tmp_path, ticket_type="enhancement")
    assert result.code == 0, result.lines
    assert stub.issues["PROJ-1"]["payload"]["issue_type"] == "Story"


def test_create_sets_the_key_lists_the_writes_and_moves_the_folder(tmp_path):
    stub, path = StubJira(), diagnosis(tmp_path)
    assert run(path, stub, JIRA, tmp_path).code == 0
    moved = tmp_path / "docs" / "PROJ-1" / "DIAGNOSIS.md"
    assert moved.is_file() and not path.exists()
    assert part(moved, "Ticket key") == "PROJ-1" and part(moved, "Work id") == "PROJ-1"
    writes = part(moved, "Outside writes").splitlines()
    assert writes == ["- ticket: PROJ-1", "- evidence: afk-evidence PROJ-1 evidence"]
    assert "afk-evidence PROJ-1 evidence" in stub.comments("PROJ-1")[0]


def test_a_local_write_failing_after_the_create_says_the_ticket_stays(tmp_path, monkeypatch):
    stub, path = StubJira(), diagnosis(tmp_path)

    def denied(*_args, **_kwargs):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(mode, "replace_text", denied)
    result = run(path, stub, JIRA, tmp_path)
    assert result.code == 2 and "PROJ-1" in stub.issues
    assert result.lines[-1].endswith("the writes reported above stay on the tracker; no write followed it")


def test_an_existing_ticket_gets_a_comment_only_and_its_key_recorded(tmp_path):
    stub, path = StubJira(), diagnosis(tmp_path)
    stub.add("PROJ-9", description="<!-- afk:prd:start -->kept<!-- afk:prd:end -->")
    result = run(path, stub, JIRA, tmp_path, key="PROJ-9")
    assert result.code == 0, result.lines
    assert [c[0] for c in stub.writes()] == ["tracker_comment"]
    assert stub.issues["PROJ-9"]["description"] == "<!-- afk:prd:start -->kept<!-- afk:prd:end -->"
    assert part(path, "Ticket key") == "PROJ-9"
    assert path.is_file(), "the folder moves only after a create"


def test_a_later_different_key_is_listed_not_recorded(tmp_path):
    stub = StubJira()
    stub.add("PROJ-2")
    stub.add("PROJ-3")
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-2"})
    assert run(path, stub, JIRA, tmp_path, key="PROJ-3").code == 0
    assert part(path, "Ticket key") == "PROJ-2"
    assert "- ticket: PROJ-3" in part(path, "Outside writes")


def test_the_evidence_comment_carries_the_listed_change_link(tmp_path):
    stub = StubGitHub()
    stub.add("4")
    path = diagnosis(tmp_path, **{"Outside writes": "- change: https://forge.example.test/change/7"})
    assert run(path, stub, GITHUB, tmp_path, key="4").code == 0
    assert "https://forge.example.test/change/7" in stub.comments("4")[0]


def test_a_stopped_diagnosis_is_one_comment_read_back_before_a_retry(tmp_path):
    stub = StubJira()
    stub.add("PROJ-5")
    stub.script["tracker_comment"] = [{"error": True, "status": 502, "body": "bad gateway"}]
    path = diagnosis(tmp_path, Verdict="V-4 works as specified",
                     **{"Ticket key": "PROJ-5", "Root cause": "", "Fix proposal": ""})
    result = run(path, stub, JIRA, tmp_path)
    assert result.code == 0, result.lines
    assert len(stub.writes("tracker_comment")) == 1, "the read-back found the comment"
    assert len(stub.comments("PROJ-5")) == 1 and result.sleeps == []


def test_a_description_file_creates_a_ticket_with_its_text_and_no_comment(tmp_path):
    stub = StubGitHub()
    note = tmp_path / "docs" / "adhoc-export" / "DESCRIPTION.md"
    note.parent.mkdir(parents=True)
    note.write_text("Export drops the last row\n\nSeen on the grid page.\n", encoding="utf-8")
    result = run(note, stub, GITHUB, tmp_path, description=True)
    assert result.code == 0, result.lines
    body = stub.issues["1"]["payload"]["description"]
    assert "Seen on the grid page." in body and "afk-evidence adhoc-export-DESCRIPTION ticket" in body
    assert stub.issues["1"]["payload"]["summary"] == "Export drops the last row"
    assert stub.writes("tracker_comment") == [] and note.is_file()


def test_a_description_file_on_an_existing_ticket_is_one_comment(tmp_path):
    stub = StubGitHub()
    stub.add("8")
    note = tmp_path / "docs" / "adhoc-export" / "DESCRIPTION.md"
    note.parent.mkdir(parents=True)
    note.write_text("Also seen on the report page.\n", encoding="utf-8")
    assert run(note, stub, GITHUB, tmp_path, description=True, key="8").code == 0
    assert [c[0] for c in stub.writes()] == ["tracker_comment"]
    assert "Also seen on the report page." in stub.comments("8")[0]


def test_an_unset_assignee_files_unassigned_and_names_the_key(tmp_path):
    stub = StubJira()
    config = dict(JIRA, developer={"trackerAssignee": "none"})
    result = run(diagnosis(tmp_path), stub, config, tmp_path)
    assert result.code == 0
    assert "assignee" not in stub.issues["PROJ-1"]["payload"]
    assert any("trackerAssignee" in line for line in result.lines)


# --- in-review, fix version, proof -------------------------------------------

def test_in_review_moves_the_ticket_and_lists_the_move(tmp_path):
    stub = StubGitHub()
    path = diagnosis(tmp_path)
    assert run(path, stub, GITHUB, tmp_path, in_review=True).code == 0
    assert "status:in-review" in stub.issues["1"]["labels"]
    assert "- in-review: 1" in part(tmp_path / "docs" / "1" / "DIAGNOSIS.md", "Outside writes")


def test_jira_in_review_matches_the_configured_transition_id(tmp_path):
    stub = StubJira()
    stub.add("PROJ-4")
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-4"})
    assert run(path, stub, JIRA, tmp_path, in_review=True).code == 0
    assert stub.issues["PROJ-4"]["status"] == "In Review"
    assert ("tracker_transition", {"ticket_key": "PROJ-4", "transition_id": "in-review"}) in stub.calls


def test_the_jira_fix_version_is_added_to_the_versions_already_set(tmp_path):
    stub = StubJira()
    stub.add("PROJ-6", fixVersions=["1.4"])
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-6"})
    assert run(path, stub, JIRA, tmp_path, fix_version="1.5").code == 0
    assert stub.issues["PROJ-6"]["fixVersions"] == ["1.4", "1.5"]


def test_the_jira_fix_version_goes_on_a_created_ticket(tmp_path):
    stub = StubJira()
    assert run(diagnosis(tmp_path), stub, JIRA, tmp_path, fix_version="1.5").code == 0
    assert stub.issues["PROJ-1"]["payload"]["fix_version"] == "1.5"
    assert stub.writes("tracker_edit") == []


def test_proof_files_carry_the_work_id_the_kind_and_the_step(tmp_path):
    stub = StubGitHub()
    stub.add("3")
    shot, log = tmp_path / "grid.png", tmp_path / "run.log"
    shot.write_bytes(b"png")
    log.write_text("rows: 9 of 10\n", encoding="utf-8")
    path = diagnosis(tmp_path, **{"Ticket key": "3"})
    result = run(path, stub, GITHUB, tmp_path, proof=(("P-3", str(shot)), ("P-1", str(log))))
    assert result.code == 0, result.lines
    attach = [p for op, p in stub.calls if op == "tracker_attach"][0]
    names = [os.path.basename(f) for f in attach["files"]]
    assert names == [f"{WORK}-p-3-proof-grid.png", f"{WORK}-p-1-proof-run.log"]
    assert f"afk-evidence {WORK} proof" in attach["text"]
    assert any(line.startswith("NOTE: not attached") and "run.log" in line for line in result.lines)
    assert not os.path.exists(os.path.dirname(attach["files"][0])), "the staging folder is removed"


def test_jira_files_stored_with_a_failed_comment_are_not_uploaded_again(tmp_path):
    stub = StubJira()
    stub.add("PROJ-8")
    stub.script["tracker_attach"] = [{"error": True, "reason": "the files are attached; the comment failed"}]
    real = stub.tracker_attach
    stub.tracker_attach = lambda p: (real(p), stub.comments("PROJ-8").pop())[0]
    log = tmp_path / "run.log"
    log.write_text("rows\n", encoding="utf-8")
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-8"})
    result = run(path, stub, JIRA, tmp_path, proof=(("P-1", str(log)),))
    assert result.code == 0, result.lines
    assert len(stub.writes("tracker_attach")) == 1
    assert stub.attachments["PROJ-8"] == [f"{WORK}-p-1-proof-run.log"]
    assert f"afk-evidence {WORK} proof" in stub.comments("PROJ-8")[-1]


# --- refusals: no write -------------------------------------------------------

@pytest.mark.parametrize("stub_cls, config, options, reason", [
    (StubJira, JIRA, {"consent": None}, "--consent"),
    (StubJira, dict(JIRA, tracker="none"), {}, "tracker kind `none`"),
    (StubJira, dict(JIRA, jira={"project": "PROJ"}), {}, "in-review key is not configured"),
    (StubGitHub, dict(GITHUB, **{"github-issues": {}}), {}, "in-review key is not configured"),
    (StubJira, JIRA, {"key": "PROJ-404"}, "does not return ticket"),
    (StubJira, JIRA, {"fix_version": "9.9"}, "fixVersion `9.9`"),
    (StubGitHub, GITHUB, {"fix_version": "1.5"}, "no fix version"),
    (StubJira, dict(JIRA, jira=dict(JIRA["jira"], **{"issue-types": {"bug": "Defect"}})),
     {}, "issuetype `Defect`"),
    (StubJira, JIRA, {"proof": (("P-1", "missing.log"),)}, "no such proof file"),
    (StubJira, JIRA, {"proof": (("P-9", __file__),)}, "proof kind"),
    (StubJira, JIRA, {"yes": False, "confirm": lambda q: False}, "not confirmed"),
])
def test_a_refusal_writes_nothing(tmp_path, stub_cls, config, options, reason):
    stub, path = stub_cls(), diagnosis(tmp_path)
    before = path.read_bytes()
    result = run(path, stub, config, tmp_path, **options)
    assert result.code == 1
    assert reason in result.lines[-1] and result.lines[-1].startswith("REFUSED:")
    assert stub.writes() == [] and path.read_bytes() == before


def test_a_missing_github_type_label_is_refused(tmp_path):
    stub = StubGitHub(labels=("status:in-review",))
    result = run(diagnosis(tmp_path), stub, GITHUB, tmp_path)
    assert result.code == 1 and "label `bug` does not exist" in result.lines[-1]
    assert stub.writes() == []


def test_jira_in_review_with_no_matching_transition_is_refused(tmp_path):
    stub = StubJira()
    stub.add("PROJ-7")
    config = dict(JIRA, jira=dict(JIRA["jira"], transitions={"in-review": "99"}))
    result = run(diagnosis(tmp_path), stub, config, tmp_path, key="PROJ-7", in_review=True)
    assert result.code == 1 and "offers no transition" in result.lines[-1]
    assert stub.writes() == []


def test_a_diagnosis_the_check_refuses_is_refused(tmp_path):
    stub = StubJira()
    result = run(diagnosis(tmp_path, Symptom=""), stub, JIRA, tmp_path)
    assert result.code == 1 and "missing Symptom" in result.lines[-1]
    assert stub.calls == []


# --- dry run, retries, re-runs ------------------------------------------------

def test_a_dry_run_prints_the_payloads_and_writes_nothing(tmp_path):
    stub, path = StubJira(), diagnosis(tmp_path)
    result = run(path, stub, JIRA, tmp_path, consent=None, yes=False, dry_run=True,
                 in_review=False, fix_version="1.5")
    assert result.code == 0 and result.ticket is None
    assert any('"issue_type": "Bug"' in line for line in result.lines)
    assert result.lines[-1].startswith("DRY-RUN")
    assert stub.writes() == [] and part(path, "Outside writes") == ""


def test_a_4xx_answer_is_shown_and_never_retried(tmp_path):
    stub = StubJira()
    stub.script["tracker_create"] = [{"error": True, "status": 400, "body": "summary is too long"}]
    result = run(diagnosis(tmp_path), stub, JIRA, tmp_path)
    assert result.code == 2 and "summary is too long" in result.lines[-1]
    assert len(stub.writes("tracker_create")) == 1 and result.sleeps == []
    assert stub.writes("tracker_comment") == [], "no write follows a failed one"


def test_a_5xx_answer_is_retried_twice_after_read_backs(tmp_path):
    stub = StubJira()
    down = {"error": True, "status": 503, "body": "unavailable"}
    stub.script["tracker_create"] = [dict(down), dict(down), dict(down)]
    stub.tracker_create = lambda p: down
    result = run(diagnosis(tmp_path), stub, JIRA, tmp_path)
    assert result.code == 2 and result.sleeps == [5, 20]
    assert len(stub.writes("tracker_create")) == 3


def test_a_create_that_landed_but_answered_an_error_is_found_not_repeated(tmp_path):
    stub = StubJira()
    stub.script["tracker_create"] = [{"error": True, "status": 504, "body": "timeout"}]
    result = run(diagnosis(tmp_path), stub, JIRA, tmp_path)
    assert result.code == 0, result.lines
    assert len(stub.issues) == 1 and len(stub.writes("tracker_create")) == 1
    assert result.ticket.startswith("TICKET: PROJ-1 ")


def test_a_re_run_writes_nothing_twice(tmp_path):
    stub, path = StubGitHub(), diagnosis(tmp_path)
    shot = tmp_path / "grid.png"
    shot.write_bytes(b"png")
    options = {"proof": (("P-3", str(shot)),), "in_review": True}
    assert run(path, stub, GITHUB, tmp_path, **options).code == 0
    moved = tmp_path / "docs" / "1" / "DIAGNOSIS.md"
    first = len(stub.writes())
    again = run(moved, stub, GITHUB, tmp_path, **options)
    assert again.code == 0, again.lines
    assert len(stub.writes()) == first and len(stub.issues) == 1
    assert again.ticket == "TICKET: 1 https://github.com/o/r/issues/1"


def test_a_re_run_after_an_unlisted_comment_finds_it_by_its_marker(tmp_path):
    stub = StubJira()
    stub.add("PROJ-2", comments=[f"earlier\n\nafk-evidence {WORK} evidence"])
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-2"})
    assert run(path, stub, JIRA, tmp_path).code == 0
    assert stub.writes() == []
    assert f"- evidence: afk-evidence {WORK} evidence" in part(path, "Outside writes")


def test_a_re_run_finishes_a_folder_move_a_crash_left_undone(tmp_path):
    stub = StubJira()
    stub.add("PROJ-1", description=f"x\n\nafk-evidence {WORK} ticket")
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-1", "Outside writes": "- ticket: PROJ-1"})
    assert run(path, stub, JIRA, tmp_path).code == 0
    moved = tmp_path / "docs" / "PROJ-1" / "DIAGNOSIS.md"
    assert part(moved, "Work id") == "PROJ-1"


# --- the adapter load ---------------------------------------------------------

def test_load_goes_through_tracker_api_and_the_stub_gets_the_attach_payload(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("tracker: jira\njira:\n  project: PROJ\n  transitions:\n    in-review: \"31\"\n",
                      encoding="utf-8")
    monkeypatch.setenv("AFK_CONFIG", str(config))
    stub, loads, real_load = StubJira(), [], tracker_api.load
    stub.add("PROJ-3")

    def load(required=()):
        module = real_load(required)
        loads.append((required, Path(module.__file__)))
        monkeypatch.setattr(module, "call", stub.call)
        monkeypatch.setattr(module, "resolve_creds_env", stub.resolve_creds_env)
        return module

    monkeypatch.setattr(tracker_api, "load", load)
    log = tmp_path / "run.log"
    log.write_text("rows: 9 of 10\n", encoding="utf-8")
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-3"})
    result = mode.run_bug_mode(path, consent="prior", yes=True, proof=(("P-1", str(log)),),
                               sleep=lambda s: None)
    assert result.code == 0, result.lines
    assert loads == [(("call",), ROOT / "adapters" / "tracker" / "jira" / "api.py")]
    attach = [p for op, p in stub.calls if op == "tracker_attach"][0]
    assert set(attach) == {"ticket_key", "files", "text"} and attach["ticket_key"] == "PROJ-3"
    assert os.path.basename(attach["files"][0]) == f"{WORK}-p-1-proof-run.log"


def test_the_command_line_needs_exactly_one_input(capsys):
    with pytest.raises(SystemExit):
        mode.main(["--type", "bug"])


# --- writes that fail part-way, re-runs, markers -----------------------------

def test_a_created_ticket_with_no_matching_in_review_move_fails_before_more_writes(tmp_path):
    stub = StubJira()
    config = dict(JIRA, jira=dict(JIRA["jira"], transitions={"in-review": "99"}))
    result = run(diagnosis(tmp_path), stub, config, tmp_path, in_review=True)
    assert result.code == 2
    assert result.lines[-1].startswith("FAILED:") and "offers no transition" in result.lines[-1]
    assert "stay on the tracker" in result.lines[-1]
    assert [c[0] for c in stub.writes()] == ["tracker_create"]


@pytest.mark.parametrize("dropped", ["Outside writes", "Ticket key"])
def test_a_diagnosis_without_a_part_this_mode_writes_is_refused(tmp_path, dropped):
    stub = StubJira()
    result = run(diagnosis(tmp_path, **{dropped: None}), stub, JIRA, tmp_path)
    assert result.code == 1 and f"`## {dropped}`" in result.lines[-1]
    assert stub.writes() == []


class StubJiraInReview(StubJira):
    def tracker_transitions(self, p):
        if self.issues[p["ticket_key"]]["status"] == "In Review":
            return {"transitions": [{"id": "21", "name": "Back to dev", "to": {"name": "In Progress"}}]}
        return super().tracker_transitions(p)


def test_a_re_run_after_the_in_review_move_is_not_refused(tmp_path):
    stub = StubJiraInReview()
    stub.add("PROJ-9")
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-9"})
    assert run(path, stub, JIRA, tmp_path, in_review=True).code == 0
    again = run(path, stub, JIRA, tmp_path, in_review=True)
    assert again.code == 0, again.lines
    assert len(stub.writes("tracker_transition")) == 1


def test_jira_in_review_matches_a_transition_by_name(tmp_path):
    stub = StubJira()
    stub.add("PROJ-4")
    config = dict(JIRA, jira=dict(JIRA["jira"], transitions={"in-review": "start REVIEW"}))
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-4"})
    assert run(path, stub, config, tmp_path, in_review=True).code == 0
    assert stub.issues["PROJ-4"]["status"] == "In Review"


def test_a_ticket_already_in_the_configured_state_needs_no_transition(tmp_path):
    stub = StubJiraInReview()
    stub.add("PROJ-4", status="In Review")
    config = dict(JIRA, jira=dict(JIRA["jira"], transitions={"in-review": "In Review"}))
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-4"})
    result = run(path, stub, config, tmp_path, in_review=True)
    assert result.code == 0, result.lines
    assert stub.writes("tracker_transition") == []
    assert "- in-review: PROJ-4" in part(path, "Outside writes")


def test_two_description_files_in_one_folder_file_two_tickets(tmp_path):
    stub = StubGitHub()
    folder = tmp_path / "docs" / "adhoc"
    folder.mkdir(parents=True)
    (folder / "a.md").write_text("Export drops the last row\n", encoding="utf-8")
    (folder / "b.md").write_text("Import ignores the header\n", encoding="utf-8")
    assert run(folder / "a.md", stub, GITHUB, tmp_path, description=True).code == 0
    assert run(folder / "b.md", stub, GITHUB, tmp_path, description=True).code == 0
    assert sorted(stub.issues) == ["1", "2"]


def test_a_folder_move_done_on_a_later_run_does_not_repeat_the_evidence(tmp_path):
    stub, path = StubJira(), diagnosis(tmp_path)
    first = run(path, stub, JIRA, tmp_path, resolve=lambda key: None)
    assert first.code == 0 and path.is_file()
    again = run(path, stub, JIRA, tmp_path)
    assert again.code == 0, again.lines
    assert len(stub.comments("PROJ-1")) == 1
    assert (tmp_path / "docs" / "PROJ-1" / "DIAGNOSIS.md").is_file()


def test_a_re_run_after_a_failed_proof_comment_does_not_upload_again(tmp_path):
    stub = StubJira()
    stub.script["tracker_attach"] = [{"error": True, "reason": "the files are attached; the comment failed"}]
    real = stub.tracker_attach
    stub.tracker_attach = lambda p: (real(p), stub.comments(p["ticket_key"]).pop())[0]
    down = Lost({"error": True, "status": 503, "body": "down"})
    stub.script["tracker_comment"] = [PASS, down, down, down]
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"png")
    proof = (("P-1", str(shot)),)
    first = run(diagnosis(tmp_path), stub, JIRA, tmp_path, proof=proof)
    assert first.code == 2, first.lines
    again = run(tmp_path / "docs" / "PROJ-1" / "DIAGNOSIS.md", stub, JIRA, tmp_path, proof=proof)
    assert again.code == 0, again.lines
    assert stub.attachments["PROJ-1"] == ["PROJ-1-p-1-proof-shot.png"]
    assert "afk-evidence PROJ-1 proof" in stub.comments("PROJ-1")[-1]


def test_a_later_different_ticket_gets_its_own_evidence(tmp_path):
    stub = StubJira()
    stub.add("PROJ-2", comments=[f"x\n\nafk-evidence {WORK} evidence"])
    stub.add("PROJ-3")
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-2",
                                  "Outside writes": f"- evidence: afk-evidence {WORK} evidence"})
    assert run(path, stub, JIRA, tmp_path, key="PROJ-3").code == 0
    assert f"afk-evidence {WORK} evidence-proj-3" in stub.comments("PROJ-3")[0]
    assert f"- evidence: afk-evidence {WORK} evidence-proj-3" in part(path, "Outside writes")


def test_a_command_line_client_error_is_shown_and_not_retried(tmp_path):
    stub = StubGitHub()
    stub.add("5")
    stub.script["tracker_comment"] = [Lost({"error": True, "status": 1, "body": "GraphQL: Could not comment"})]
    result = run(diagnosis(tmp_path, **{"Ticket key": "5"}), stub, GITHUB, tmp_path)
    assert result.code == 2 and "exit code 1: GraphQL" in result.lines[-1]
    assert result.sleeps == [] and len(stub.writes("tracker_comment")) == 1


def test_a_lost_comment_is_retried_after_a_read_back_finds_nothing(tmp_path):
    stub = StubGitHub()
    stub.add("5")
    stub.script["tracker_comment"] = [Lost({"error": True, "status": 1, "body": "HTTP 502: bad gateway"})]
    result = run(diagnosis(tmp_path, **{"Ticket key": "5"}), stub, GITHUB, tmp_path)
    assert result.code == 0, result.lines
    assert result.sleeps == [5] and len(stub.writes("tracker_comment")) == 2
    assert len(stub.comments("5")) == 1


def test_two_proof_files_with_one_name_upload_under_two_names(tmp_path):
    stub = StubGitHub()
    stub.add("3")
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        (tmp_path / sub / "run.png").write_bytes(sub.encode())
    path = diagnosis(tmp_path, **{"Ticket key": "3"})
    proof = (("P-1", str(tmp_path / "a" / "run.png")), ("P-1", str(tmp_path / "b" / "run.png")))
    assert run(path, stub, GITHUB, tmp_path, proof=proof).code == 0
    attach = [p for op, p in stub.calls if op == "tracker_attach"][0]
    assert [os.path.basename(f) for f in attach["files"]] == [
        f"{WORK}-p-1-proof-run.png", f"{WORK}-p-1-proof-run-2.png"]


def test_a_jira_file_stored_differently_is_named_in_a_note(tmp_path):
    stub = StubJira()
    stub.add("PROJ-8")
    real = stub.tracker_attach
    stub.tracker_attach = lambda p: dict(real(p), mismatches=[
        {"file": p["files"][0], "reason": "stored differently"}])
    log = tmp_path / "run.log"
    log.write_text("rows\n", encoding="utf-8")
    path = diagnosis(tmp_path, **{"Ticket key": "PROJ-8"})
    result = run(path, stub, JIRA, tmp_path, proof=(("P-1", str(log)),))
    assert result.code == 0
    assert any(line.startswith("NOTE: stored differently") and "run.log" in line for line in result.lines)


# --- the command line and the real folder resolver ---------------------------

def _github_config(tmp_path, monkeypatch, stub):
    config = tmp_path / "config.yaml"
    config.write_text("tracker: github-issues\ngithub-issues:\n  state-labels:\n"
                      "    in-review: \"status:in-review\"\n", encoding="utf-8")
    monkeypatch.setenv("AFK_CONFIG", str(config))
    monkeypatch.setattr(mode.tracker_api, "load", lambda required=(): stub)


def test_the_command_line_passes_every_option_through(tmp_path, monkeypatch, capsys):
    stub = StubGitHub()
    stub.add("4")
    _github_config(tmp_path, monkeypatch, stub)
    shot = tmp_path / "grid.png"
    shot.write_bytes(b"png")
    path = diagnosis(tmp_path)
    code = mode.main(["--diagnosis", str(path), "--key", "4", "--type", "enhancement",
                      "--proof", f"p-3={shot}", "--in-review", "--consent", "prior", "--yes"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "TICKET: 4 https://github.com/o/r/issues/4" in out
    assert ("gh", ["label", "list", "--search", "enhancement", "--json", "name", "--limit", "100"]) in stub.calls
    attach = [p for op, p in stub.calls if op == "tracker_attach"][0]
    assert os.path.basename(attach["files"][0]) == f"{WORK}-p-3-proof-grid.png"
    assert "status:in-review" in stub.issues["4"]["labels"]


def test_the_command_line_dry_run_and_its_refusals(tmp_path, monkeypatch, capsys):
    stub = StubGitHub()
    _github_config(tmp_path, monkeypatch, stub)
    path = diagnosis(tmp_path)
    assert mode.main(["--diagnosis", str(path), "--summary", "Rows go missing", "--dry-run"]) == 0
    assert '"summary": "Rows go missing"' in capsys.readouterr().out and stub.writes() == []
    assert mode.main(["--diagnosis", str(path), "--yes"]) == 1
    assert "--consent" in capsys.readouterr().out
    for argv in (["--type", "bug"], ["--diagnosis", str(path), "--description", str(path)],
                 ["--diagnosis", str(path), "--dry-run", "--yes"], ["--diagnosis", str(path), "--proof", "P-1"]):
        with pytest.raises(SystemExit):
            mode.main(argv)


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.test", *args],
                          cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_the_folder_move_is_a_git_rename(tmp_path):
    _git(tmp_path, "init", "-q")
    path = diagnosis(tmp_path)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    assert run(path, StubJira(), JIRA, tmp_path).code == 0
    status = _git(tmp_path, "status", "--porcelain")
    assert any(line.startswith("R") and "docs/PROJ-1/DIAGNOSIS.md" in line
               for line in status.splitlines()), status


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_the_real_resolver_renders_the_configured_spec_folder(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q")
    (tmp_path / ".afk").mkdir()
    (tmp_path / ".afk" / "config.yaml").write_text(
        "notes: repo-files\nrepo-files:\n  spec-dir: 'specs/{workId}'\n", encoding="utf-8")
    monkeypatch.delenv("AFK_CONFIG", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    rendered = mode._resolve_folder("PROJ-1")
    if rendered is None:
        pytest.skip("no POSIX shell to run the notes adapter")
    assert Path(rendered).resolve() == (tmp_path / "specs" / "PROJ-1").resolve()
