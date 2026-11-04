"""Tests for the grill skill.

The dry runs take every command from the fenced `sh step=...` blocks of SKILL.md, so a
command the skill states is a command that ran. Tracker, engine and config reader are
recorded fakes (fakes/) in a throwaway plugin tree. Once the S1 engine exists, the built
document also goes through the real `engine check`.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_visualize import V1_WORD, _example, _find, _next_round, check_document

PLUGIN = Path(__file__).resolve().parents[2]
SKILL_DIR = PLUGIN / "skills" / "grill"
LAVISH_DIR = PLUGIN / "skills" / "use-lavish"
SKILL_MD = SKILL_DIR / "SKILL.md"
ENGINE = PLUGIN / "engine" / "engine.py"
FAKES = Path(__file__).resolve().parent / "fakes"
sys.path.insert(0, str(LAVISH_DIR / "scripts"))

import round_document as rd  # noqa: E402

STEP = re.compile(r"^ *```sh step=([\w-]+)\n *(.*?)\n *```", re.S | re.M)
STEP_ORDER = ["start", "read-ticket", "row", "build", "present", "wait", "reply", "ingest",
              "apply-readings", "sync", "term", "gate", "end"]


def skill_steps():
    return dict(STEP.findall(SKILL_MD.read_text("utf-8")))


class World:
    def __init__(self, root, tickets, config):
        self.root = root
        self.plugin = root / "plugin"
        self.repo = root / "repo"
        self.calls = root / "calls.log"
        self.raw = root / "raw-response.txt"
        for skill_dir in (SKILL_DIR, LAVISH_DIR):
            shutil.copytree(skill_dir, self.plugin / "skills" / skill_dir.name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        for fake, target in (("fake_engine.py", "engine/engine.py"),
                             ("fake_tracker.py", "ports/tracker/cli.py"),
                             ("fake_config.py", "scripts/afkv2_config.py")):
            (self.plugin / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(FAKES / fake, self.plugin / target)
        self.repo.mkdir()
        if config is not None:
            (self.repo / ".afkv2").mkdir()
            (self.repo / ".afkv2" / "config.json").write_text(json.dumps(config), "utf-8")
        self.env = {"FAKE_CALL_LOG": str(self.calls), "FAKE_POLL_RAW": str(self.raw),
                    "FAKE_TICKETS": str(FAKES / tickets)}
        self.scratch = root / "scratch"
        self.scratch.mkdir()

    def run(self, step, expect=0, swap=None, **values):
        """Run one stated command with its placeholders filled; return its one JSON answer."""
        command = skill_steps()[step]
        if swap:
            assert swap[0] in command
            command = command.replace(*swap)
        filled = {"python": Path(sys.executable), "this skill's folder": self.plugin / "skills" / "grill",
                  "plugin root": self.plugin, **{k.replace("_", " "): v for k, v in values.items()}}
        for name, value in filled.items():
            command = command.replace(f"<{name}>", Path(value).as_posix() if isinstance(value, Path) else str(value))
        left = re.findall(r"<[^<>]+>", command)
        assert not left, f"{step}: unfilled {left}"
        run = subprocess.run(shlex.split(command), cwd=self.repo, capture_output=True, text=True, timeout=120,
                             env={**os.environ, **self.env}, encoding="utf-8")
        assert run.returncode == expect, f"{step}: {run.returncode}\n{run.stdout}\n{run.stderr}"
        return json.loads(run.stdout)

    def file(self, name, content):
        path = self.scratch / name
        path.write_bytes((json.dumps(content) if not isinstance(content, str) else content).encode("utf-8"))
        return path

    def call_log(self):
        return self.calls.read_text("utf-8").splitlines() if self.calls.exists() else []

    def verbs(self):
        return [line.split()[1] for line in self.call_log()]

    def start_and_read(self, key="PROJ-1"):
        started = self.run("start", ticket_key=key)
        self.run("read-ticket", ticket_key=key, ticket_file=self.scratch / "ticket.json")
        return started

    def build_round(self, started, content, ticket=True):
        extra = self.scratch / "ticket.json" if ticket else self.file("no-ticket.json", {})
        return self.run("build", doc=started["doc"], session=started["session"], ticket_key=started["ticket"],
                        round_input=self.file("round.json", content), ticket_file=extra)


JIRA = {"spec_folder": "specs", "tracker": {"kind": "jira"}}
GITHUB = {"spec_folder": "specs", "tracker": {"kind": "github-issues", "repo": "acme/shop"}}


@pytest.fixture
def world(tmp_path):
    return World(tmp_path, "tickets_jira.json", JIRA)


def check_authored_part(doc):
    """The guide's check, on a document ingest wrote to: only ingest writes `responses`."""
    check_document({**doc, "rounds": [{k: v for k, v in r.items() if k != "responses"} for r in doc["rounds"]]})


def text(value, **extra):
    return {"type": "text", "props": {"text": value}, **extra}


def scope_map(state="open"):
    return {"type": "map", "id": "m-scope", "props": {"title": "Scope", "nodes": [
        {"id": "n-scope", "label": "Scope", "state": state},
        {"id": "n-format", "label": "Format", "state": "open"}]}}


def round_one():
    return {"banner": {"settled": [], "unlocks": ["The file format"], "parked": []},
            "maps": [scope_map()],
            "items": [{"id": "i-scope", "kind": "confirm", "node": "n-scope",
                       "body": text("The export covers one order per file.")},
                      {"id": "i-format", "kind": "debate", "node": "n-format", "title": "The file format",
                       "body": text("Which file format? Recommended: CSV.")}]}


def note_settle_payload():
    return {"settle": [{"item": "i-format", "note": "N-1-i-format", "reading": "Picks CSV."}]}


DECIDED = {"decision": "The export writes UTF-8.", "alternatives": ["UTF-16: no reader asks for it"],
           "evidence": "src/io.py:12 writes UTF-8", "grade": "repo",
           "why": "Beats UTF-16: every current reader takes UTF-8.", "reverse": "change the writer",
           "depends_on": []}


# ---- the skill file


def test_frontmatter_and_produces_anchors():
    text_md = SKILL_MD.read_text("utf-8")
    head = re.match(r"---\n(.*?)\n---\n", text_md, re.S).group(1)
    assert re.search(r"^name: grill$", head, re.M)
    assert re.search(r"^description: .+", head, re.M)
    assert "/afkv2:grill" in text_md
    assert "def build_round_document(" in (LAVISH_DIR / "scripts" / "round_document.py").read_text("utf-8")


def test_commands_come_in_the_contract_order():
    assert list(skill_steps()) == STEP_ORDER


def test_no_step_asks_for_a_lane():
    for path in SKILL_DIR.rglob("*.md"):
        assert not re.search(r"\blanes?\b", path.read_text("utf-8"), re.I), path


def test_no_v1_name_and_no_upstream_caller():
    v1 = V1_WORD
    for path in [p for p in SKILL_DIR.rglob("*") if p.is_file() and "__pycache__" not in p.parts]:
        assert not v1.search(path.relative_to(SKILL_DIR).as_posix()), path
        assert not v1.search(path.read_text("utf-8")), path
    refs = set(re.findall(r"/afkv2:[\w-]+", SKILL_MD.read_text("utf-8")))
    assert refs <= {"/afkv2:grill", "/afkv2:visualize", "/afkv2:setup", "/afkv2:to-prd"}, refs


def test_skill_states_each_harness_wait():
    body = SKILL_MD.read_text("utf-8")
    claude, codex = body.index("**On Claude"), body.index("**On Codex")
    wait = body.index("```sh step=wait")
    assert claude < wait < codex, "the poll command belongs to the Claude branch"
    codex_text = body[codex:body.index("```sh step=ingest")]
    assert "End your turn" in codex_text and "Stop hook" in codex_text
    assert "background" in body[claude:wait]


def test_skill_loads_the_guide_and_never_writes_html():
    body = SKILL_MD.read_text("utf-8")
    assert "/afkv2:visualize" in body
    assert "../visualize/SKILL.md" in body
    assert "never write page HTML" in body


def test_grill_writes_nothing_to_the_tracker():
    for path in [*(SKILL_DIR / "scripts").glob("*.py"), *(LAVISH_DIR / "scripts").glob("*.py")]:
        source = path.read_text("utf-8")
        for verb in ("description-put", "attachment-put", "attachment-delete", "md-to-adf"):
            assert verb not in source, path


# ---- round_document unit


def session():
    return {"id": "s-1", "skill": "grill", "feature": "PROJ-1", "ticket": "PROJ-1"}


def test_builder_output_has_the_schema_fields(tmp_path):
    path = tmp_path / "pages" / "grill-s-1.json"
    result = rd.build_round_document(path, session(), round_one())
    doc = json.loads(path.read_text("utf-8"))
    check_document(doc)
    assert result == {"ok": True, "doc": str(path), "round": 1, "items": ["i-scope", "i-format"], "degraded": []}
    assert doc["schema"] == "afkv2.page/1"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", doc["session"]["started"])
    assert doc["rounds"][0]["state"] == "current"
    assert [i["state"] for i in doc["rounds"][0]["items"]] == ["open", "open"]
    assert doc["maps"][0]["props"]["nodes"][0]["round"] == 1


@pytest.mark.parametrize("mutate, code", [
    (lambda r: r.pop("banner"), "bad-round"),
    (lambda r: r["items"][0].update(kind="fork"), "bad-item"),
    (lambda r: r["items"][0].update(node="n-none"), "bad-item"),
    (lambda r: r["items"][0].pop("body"), "bad-item"),
    (lambda r: r["items"][0].update(notes=[]), "engine-field"),
    (lambda r: r["items"][0].update(settled={}), "engine-field"),
    (lambda r: r.update(responses=[]), "engine-field"),
    (lambda r: r["items"][1].update(id="i-scope"), "id-reused"),
    (lambda r: r["items"][0].update(body={"type": "text", "html": "<b>x</b>", "props": {"text": "x"}}), "not-freestyle"),
    (lambda r: r["items"][0].update(critical=True), "no-picture"),
])
def test_builder_refuses(tmp_path, mutate, code):
    content = round_one()
    mutate(content)
    path = tmp_path / "doc.json"
    with pytest.raises(rd.Refusal) as caught:
        rd.build_round_document(path, session(), content)
    assert caught.value.code == code
    assert not path.exists(), "a refused build writes nothing"


def test_critical_question_keeps_the_picture_above_the_question(tmp_path):
    picture = {"type": "table", "id": "i-scope-now", "props": {"columns": ["Field"], "rows": [["total"]]},
               "children": [text("Keep this field?")]}
    content = round_one()
    content["items"][0].update(critical=True, body=picture)
    path = tmp_path / "doc.json"
    rd.build_round_document(path, session(), content)
    item = json.loads(path.read_text("utf-8"))["rounds"][0]["items"][0]
    assert "critical" not in item
    assert item["body"]["type"] == "table"
    check_document(json.loads(path.read_text("utf-8")))


def test_critical_question_refuses_a_picture_below_the_question(tmp_path):
    content = round_one()
    content["items"][0].update(critical=True, body=text("Keep this field?", children=[
        {"type": "table", "props": {"columns": ["Field"], "rows": [["total"]]}}]))
    with pytest.raises(rd.Refusal) as caught:
        rd.build_round_document(tmp_path / "doc.json", session(), content)
    assert caught.value.code == "no-picture"


def test_decided_card_carries_all_six_fields(tmp_path):
    content = round_one()
    content["items"][0] = {"id": "i-scope", "kind": "decided", "node": "n-scope", "decided": DECIDED}
    path = tmp_path / "doc.json"
    result = rd.build_round_document(path, session(), content)
    doc = json.loads(path.read_text("utf-8"))
    check_document(doc)
    item = doc["rounds"][0]["items"][0]
    assert item["kind"] == "decided" and result["degraded"] == []
    assert "decided" not in item
    fields = {c["id"]: c for c in rd._components(item["body"])}
    labelled = [(fields[f"i-scope-{name}"]["props"]["label"], fields[f"i-scope-{name}"]["props"]["text"])
                for name in ("decision", "why", "alternatives", "evidence", "reverse", "scope")]
    assert labelled == [("Decision", "The export writes UTF-8."),
                        ("Why this one", "Beats UTF-16: every current reader takes UTF-8."),
                        ("Other options considered (rejected)", "- UTF-16: no reader asks for it"),
                        ("Evidence", "src/io.py:12 writes UTF-8"), ("To undo", "change the writer"),
                        ("Depends on", "no other card")]
    assert fields["i-scope-evidence"]["props"]["badge"] == "repo"
    assert fields["i-scope-alternatives"]["props"]["markdown"] is True
    assert "font-weight" in fields["i-scope-decision"]["style"]


@pytest.mark.parametrize("field", ["decision", "alternatives", "evidence", "why", "reverse"])
def test_decided_card_with_a_gap_degrades_to_confirm(tmp_path, field):
    content = round_one()
    content["items"][0] = {"id": "i-scope", "kind": "decided", "node": "n-scope",
                           "decided": {**DECIDED, field: "" if field != "alternatives" else []}}
    path = tmp_path / "doc.json"
    result = rd.build_round_document(path, session(), content)
    assert result["degraded"] == ["i-scope"]
    item = json.loads(path.read_text("utf-8"))["rounds"][0]["items"][0]
    assert item["kind"] == "confirm"


@pytest.mark.parametrize("change", [{"grade": "judgment"}, {"depends_on": ["i-none"]}])
def test_decided_card_with_a_bad_grade_or_dependency_degrades(tmp_path, change):
    content = round_one()
    content["items"][0] = {"id": "i-scope", "kind": "decided", "node": "n-scope",
                           "decided": {**DECIDED, **change}}
    result = rd.build_round_document(tmp_path / "doc.json", session(), content)
    assert result["degraded"] == ["i-scope"]


def test_map_node_round_moves_only_when_its_state_moves(tmp_path):
    path = tmp_path / "doc.json"
    rd.build_round_document(path, session(), round_one())
    doc = json.loads(path.read_text("utf-8"))
    doc["rounds"][0]["responses"] = [{"received": "2026-01-05T10:00:00Z", "raw": "x", "signals": []}]
    for item in doc["rounds"][0]["items"]:
        item.update(state="settled_by_mark", settled={"by": "mark", "round": 1, "signal": "accept"})
    path.write_text(json.dumps(doc), "utf-8")
    next_round = {"banner": {"settled": [], "unlocks": [], "parked": []}, "maps": [scope_map("settled")],
                  "items": [{"id": "i-next", "kind": "confirm", "body": text("Next point.")}]}
    rd.build_round_document(path, session(), next_round)
    nodes = {n["id"]: n for n in json.loads(path.read_text("utf-8"))["maps"][0]["props"]["nodes"]}
    assert nodes["n-scope"]["round"] == 2
    assert nodes["n-format"]["round"] == 1


def test_unknown_schema_is_refused_on_append(tmp_path):
    path = tmp_path / "doc.json"
    path.write_text(json.dumps({"schema": "afkv2.page/9", "session": session(), "rounds": []}), "utf-8")
    with pytest.raises(rd.Refusal) as caught:
        rd.build_round_document(path, session(), round_one())
    assert caught.value.code == "bad-schema"
    assert "afkv2.page/9" in caught.value.reason


# ---- required input


def test_no_config_names_the_file_and_its_writer(tmp_path):
    world = World(tmp_path, "tickets_jira.json", None)
    answer = world.run("start", expect=1, ticket_key="PROJ-1")
    assert answer["error"]["code"] == "missing-input"
    assert answer["error"]["missing"] == ".afkv2/config.json"
    assert answer["error"]["writer"] == "/afkv2:setup"
    assert ".afkv2/config.json" in answer["error"]["reason"] and "/afkv2:setup" in answer["error"]["reason"]
    assert not list(world.repo.rglob("GRILL-LOG.md"))


def test_no_tracker_kind_names_the_key_and_its_writer(tmp_path):
    world = World(tmp_path, "tickets_jira.json", {"spec_folder": "specs"})
    answer = world.run("start", expect=1, ticket_key="PROJ-1")
    assert answer["error"]["missing"] == ".afkv2/config.json tracker.kind"
    assert answer["error"]["writer"] == "/afkv2:setup"


def test_no_ticket_key_is_refused(world):
    command = shlex.split(skill_steps()["start"].replace("<python>", Path(sys.executable).as_posix()).replace(
        "<this skill's folder>", (world.plugin / "skills" / "grill").as_posix()).replace(' --ticket "<ticket key>"', ""))
    run = subprocess.run(command, cwd=world.repo, capture_output=True, text=True, timeout=60)
    assert run.returncode == 1, run.stdout + run.stderr
    assert json.loads(run.stdout)["error"]["missing"] == "ticket key"


def test_build_on_a_missing_round_input_names_it(world):
    started = world.run("start", ticket_key="PROJ-1")
    answer = world.run("build", expect=2, doc=started["doc"], session=started["session"],
                       ticket_key=started["ticket"], round_input=world.scratch / "none.json",
                       ticket_file=world.file("t.json", {}))
    assert "none.json" in answer["error"]["reason"]


# ---- ticket reading


def test_jira_ticket_with_comments_and_a_link(world):
    world.run("start", ticket_key="PROJ-1")
    out = world.scratch / "ticket.json"
    answer = world.run("read-ticket", ticket_key="PROJ-1", ticket_file=out)
    assert answer["comments"] == 2 and answer["links"] == 1 and answer["unread_links"] == []
    ticket = json.loads(out.read_text("utf-8"))
    assert "Users need their orders in a file." in ticket["description"]
    assert [c["text"] for c in ticket["comments"]] == ["One file per order.", "What about cancelled orders?"]
    assert ticket["comments"][0]["author"] == "Ana PO"
    assert ticket["links"][0]["key"] == "PROJ-2"
    assert ticket["links"][0]["relation"] == "is blocked by"
    assert ticket["links"][0]["description"] == "Archive closed orders."
    assert world.call_log() == ["tracker issue-get PROJ-1", "tracker issue-get PROJ-2"]


def test_github_ticket_reads_references_and_reverse_mentions(tmp_path):
    world = World(tmp_path, "tickets_github.json", GITHUB)
    out = world.scratch / "ticket.json"
    answer = world.run("read-ticket", ticket_key="7", ticket_file=out)
    ticket = json.loads(out.read_text("utf-8"))
    assert answer["comments"] == 2
    keys = [link["key"] for link in ticket["links"]]
    assert keys == ["8", "10"]
    assert ticket["links"][0]["description"] == "Archive closed orders."
    assert ticket["links"][1]["relation"] == "mentions this ticket"
    assert [u["key"] for u in ticket["unread_links"]] == ["acme/other#9"]
    assert "tracker issue-search \"#7\"" in world.call_log()


def test_a_github_build_writes_the_issue_link_and_the_ticket_card_names_references(tmp_path):
    world = World(tmp_path, "tickets_github.json", GITHUB)
    started = world.start_and_read(key="7")
    world.build_round(started, round_one())
    doc = json.loads(Path(started["doc"]).read_text("utf-8"))
    assert doc["session"]["links"] == {"issue": "https://github.com/acme/shop/issues/{id}"}
    card = doc["rounds"][0]["items"][0]
    assert card["body"]["props"]["text"].startswith("#7: ")
    rows = next(c for c in card["body"]["children"] if c["id"] == "i-ticket-links")["props"]["rows"]
    assert [row[1] for row in rows] == ["#8", "#10"]
    unread = next(c for c in card["body"]["children"] if c["id"] == "i-ticket-unread")["props"]["rows"]
    assert unread[0][0] == "acme/other#9"
    check_document(doc)


@pytest.mark.parametrize("remote, url", [
    ("https://github.com/acme/shop.git", "https://github.com/acme/shop"),
    ("https://user@gitlab.example.com:8443/group/sub/proj.git", "https://gitlab.example.com/group/sub/proj"),
    ("git@gitlab.example.com:group/proj.git", "https://gitlab.example.com/group/proj"),
    ("ssh://git@github.com/acme/shop", "https://github.com/acme/shop"),
    ("not a remote", None),
])
def test_the_web_url_of_a_remote(remote, url):
    import page_links
    assert page_links.web_url(remote) == url


@pytest.mark.parametrize("config, remote, base, expected", [
    ({"forge": "github", "tracker": {"kind": "github-issues", "repo": "acme/issues"}}, "git@github.com:acme/shop.git", None,
     {"issue": "https://github.com/acme/issues/issues/{id}", "change": "https://github.com/acme/shop/pull/{id}",
      "commit": "https://github.com/acme/shop/commit/{id}"}),
    ({"tracker": {"kind": "jira"}}, "https://gitlab.example.com/g/p.git", "https://acme.atlassian.net/",
     {"issue": "https://gitlab.example.com/g/p/-/issues/{id}", "change": "https://gitlab.example.com/g/p/-/merge_requests/{id}",
      "commit": "https://gitlab.example.com/g/p/-/commit/{id}", "ticket": "https://acme.atlassian.net/browse/{id}",
      "projects": ["OLD", "PROJ", "WEB"]}),
    ({"tracker": {"kind": "jira"}}, None, None, None),
])
def test_the_links_come_from_the_config_the_remote_and_the_jira_base(monkeypatch, config, remote, base, expected):
    import page_links
    monkeypatch.setattr(page_links, "run_command", lambda *_: {"ok": True, **config})
    monkeypatch.setattr(page_links, "_origin", lambda: remote)
    monkeypatch.setattr(page_links, "_jira_base", lambda: base and base.rstrip("/"))
    assert page_links.links_for(["PROJ-1", "WEB-7", None, "8"], {"projects": ["OLD"]}) == expected


def test_unreadable_ticket_is_refused_and_writes_nothing(world):
    out = world.scratch / "ticket.json"
    answer = world.run("read-ticket", expect=1, ticket_key="PROJ-404", ticket_file=out)
    assert answer["error"]["code"] == "not-found"
    assert not out.exists()


# ---- dry runs


def first_round(world):
    started = world.start_and_read()
    built = world.build_round(started, round_one())
    assert built["round"] == 1
    presented = world.run("present", doc=started["doc"])
    assert presented["ok"] is True
    return started


def test_the_ticket_text_is_markdown_and_folds_when_long():
    short = rd._ticket_card({"key": "K-1", "description": "**Pain.** It hurts."})["body"]["children"][0]
    assert short["props"] == {"text": "**Pain.** It hurts.", "markdown": True} and "fold" not in short
    long = rd._ticket_card({"key": "K-1", "description": "word " * 121})["body"]["children"][0]
    assert long["fold"] == "The ticket text" and long["props"]["markdown"] is True


def test_dry_run_on_claude_settles_one_by_mark_and_one_by_note(world):
    started = first_round(world)
    doc = json.loads(Path(started["doc"]).read_text("utf-8"))
    assert doc["session"]["skill"] == "grill"
    assert Path(started["doc"]).name == f"grill-{started['session']}.json"
    assert Path(started["doc"]).parent.name == "pages"
    ticket_card = doc["rounds"][0]["items"][0]
    shown = json.dumps(ticket_card)
    assert ticket_card["kind"] == "info" and "What about cancelled orders?" in shown and "PROJ-2" in shown
    assert doc["rounds"][0]["items"][2]["title"] == "The file format" and "title" not in doc["rounds"][0]["items"][1]
    links = next(c for c in ticket_card["body"]["children"] if c["id"] == "i-ticket-links")["props"]
    assert links["columns"] == ["Relation", "Ticket", "Title", "Status"] and "Archive closed orders." not in shown
    assert ticket_card["title"] == "What the ticket says"
    check_document(doc)

    raw = "i-scope: accept\ni-format: note: csv please, \"quoted\" é\n"
    world.raw.write_bytes(raw.encode("utf-8"))
    raw_file = Path(started["raw_file"])
    waited = world.run("wait", doc=started["doc"], raw_file=raw_file)
    assert raw_file.read_bytes() == raw.encode("utf-8")
    prompts = Path(waited["prompts_file"])
    assert prompts == Path(f"{raw_file}.prompts.json") and json.loads(prompts.read_text("utf-8"))[0]["prompt"] == raw

    pending = world.run("ingest", doc=started["doc"], raw_file=raw_file)
    assert not raw_file.exists(), "the raw text now lives in the document"
    assert not prompts.exists(), "the audit copy goes with the raw file"
    assert [p["id"] for p in pending["needs_reading"]] == ["i-format"]
    assert pending["needs_reading"][0]["notes"][0]["text"] == "csv please, \"quoted\" é"
    assert pending["settled_by_mark"] == ["i-scope"]

    world.run("apply-readings", doc=started["doc"], readings=world.file("r.json", note_settle_payload()))
    world.run("sync", doc=started["doc"], log=started["log"])

    doc = json.loads(Path(started["doc"]).read_text("utf-8"))
    items = {i["id"]: i for i in doc["rounds"][0]["items"]}
    assert items["i-scope"]["state"] == "settled_by_mark"
    assert items["i-format"]["state"] == "settled_by_note"
    assert items["i-format"]["settled"] == {"by": "note", "round": 1, "signal": "N-1-i-format", "reading": "Picks CSV."}
    assert doc["rounds"][0]["replies"] == [{"text": "Settled by your note: Picks CSV.", "about": ["i-format"]}]
    assert doc["rounds"][0]["responses"][0]["raw"] == raw
    check_authored_part(doc)

    log = Path(started["log"]).read_text("utf-8")
    assert "- Settled: The export covers one order per file. · settled by mark accept R1 · card i-scope" in log
    assert "- Settled: Which file format? Recommended: CSV. · settled by note R1 · reading: Picks CSV. · card i-format" in log
    assert 'owner note on i-format (N-1-i-format): "csv please, \\"quoted\\" é"' in log

    assert world.call_log() == [
        "tracker issue-get PROJ-1", "tracker issue-get PROJ-2",
        "engine check", "engine render", "engine show", "engine poll", "engine ingest"]


def test_dry_run_on_codex_has_no_poll_and_ingests_the_handed_text(world):
    started = first_round(world)
    raw_file = Path(started["raw_file"])
    raw_file.write_bytes(b"i-scope: accept\ni-format: accept\n")
    pending = world.run("ingest", doc=started["doc"], raw_file=raw_file)
    assert pending["needs_reading"] == []
    assert world.verbs() == ["issue-get", "issue-get", "check", "render", "show", "ingest"]


def test_present_stops_at_the_first_refusal_and_names_the_verb(world):
    started = world.start_and_read()
    world.build_round(started, round_one())
    world.env["FAKE_ENGINE_REFUSE"] = "render"
    answer = world.run("present", expect=1, doc=started["doc"])
    assert answer["error"]["verb"] == "render"
    assert world.verbs()[-2:] == ["check", "render"]


def test_ingest_refusal_keeps_the_raw_text(world):
    started = first_round(world)
    raw_file = Path(started["raw_file"])
    raw_file.write_text("i-scope: accept\n", "utf-8")
    world.env["FAKE_ENGINE_REFUSE"] = "ingest"
    world.run("ingest", expect=1, doc=started["doc"], raw_file=raw_file)
    assert raw_file.exists()


def test_start_resumes_an_open_session_and_reports_unread_raw_text(world):
    started = first_round(world)
    Path(started["raw_file"]).write_text("i-scope: accept\n", "utf-8")
    again = world.run("start", ticket_key="PROJ-1")
    assert again["resume"] is True and again["session"] == started["session"]
    assert again["raw_pending"] is True


def test_a_waited_answer_resumes_its_own_session_beside_the_audit_file(world):
    started = first_round(world)
    world.raw.write_bytes(b"i-scope: accept\n")
    waited = world.run("wait", doc=started["doc"], raw_file=started["raw_file"])
    assert Path(waited["prompts_file"]).is_file()
    os.utime(waited["prompts_file"], (time.time() + 60, time.time() + 60))
    again = world.run("start", ticket_key="PROJ-1")
    assert again["session"] == started["session"] and again["raw_pending"] is True
    world.run("sync", doc=started["doc"], log=started["log"])


def test_reply_and_end_run_their_engine_verbs(world):
    started = first_round(world)
    reply = world.file("reply.md", "An answer.")
    assert world.run("reply", doc=started["doc"], reply_file=reply) == {"ok": True}
    assert world.run("end", doc=started["doc"]) == {"ok": True}
    assert world.verbs()[-2:] == ["reply", "end"]


def answered(world, started, raw):
    raw_file = Path(started["raw_file"])
    raw_file.write_text(raw, "utf-8")
    return world.run("ingest", doc=started["doc"], raw_file=raw_file)


def next_round(items, maps=None):
    content = {"banner": {"settled": ["i-scope"], "unlocks": [], "parked": []}, "items": items}
    if maps:
        content["maps"] = maps
    return content


def test_next_round_refuses_while_a_point_needs_reading(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: note: maybe\n")
    with pytest.raises(AssertionError, match="round-pass-open"):
        world.build_round(started, next_round([{"id": "i-x", "kind": "confirm", "body": text("x")}]), ticket=False)


def test_next_round_refuses_before_the_round_is_answered(world):
    started = first_round(world)
    with pytest.raises(AssertionError, match="round-not-sent"):
        world.build_round(started, next_round([{"id": "i-x", "kind": "confirm", "body": text("x")}]), ticket=False)


def test_unclear_note_returns_to_open_and_must_be_carried(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: note: maybe\n")
    world.run("apply-readings", doc=started["doc"], readings=world.file(
        "r.json", {"open": [{"item": "i-format", "reply": "Your note leaves the format open."}]}))
    with pytest.raises(AssertionError, match="missing-carry"):
        world.build_round(started, next_round([{"id": "i-x", "kind": "confirm", "body": text("x")}]), ticket=False)
    carried = {"id": "i-format-2", "kind": "debate", "node": "n-format", "carries": ["i-format"],
               "body": text("Your note: maybe. Which file format?")}
    world.build_round(started, next_round([carried]), ticket=False)
    world.run("present", doc=started["doc"])
    doc = json.loads(Path(started["doc"]).read_text("utf-8"))
    assert [r["state"] for r in doc["rounds"]] == ["settled", "current"]
    assert doc["rounds"][1]["items"][0]["carries"] == ["i-format"]
    assert "-carries" not in json.dumps(doc["rounds"][1]["items"][0]["body"])
    check_authored_part(doc)


def test_a_note_on_an_older_card_returns_and_must_be_carried(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    world.build_round(started, next_round([{"id": "i-two", "kind": "confirm", "body": text("Two.")}]), ticket=False)
    pending = answered(world, started, "i-two: accept\ni-scope: note: only for open orders\n")
    assert [p["id"] for p in pending["returned"]] == ["i-scope"]
    with pytest.raises(AssertionError, match="missing-carry"):
        world.build_round(started, next_round([{"id": "i-three", "kind": "confirm", "body": text("x")}]), ticket=False)
    world.build_round(started, next_round([{"id": "i-scope-2", "kind": "confirm", "carries": ["i-scope"],
                                            "body": text("Only for open orders?")}]), ticket=False)
    world.run("sync", doc=started["doc"], log=started["log"])
    log = Path(started["log"]).read_text("utf-8")
    assert 'owner note on i-scope (N-2-i-scope): "only for open orders"' in log


def test_a_reopen_on_an_older_card_returns_and_must_be_carried(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    world.build_round(started, next_round([{"id": "i-two", "kind": "confirm", "body": text("Two.")}]), ticket=False)
    pending = answered(world, started, "i-two: accept\ni-scope: reopen\n")
    assert [p["id"] for p in pending["returned"]] == ["i-scope"]
    with pytest.raises(AssertionError, match="missing-carry"):
        world.build_round(started, next_round([{"id": "i-three", "kind": "confirm", "body": text("x")}]), ticket=False)
    world.build_round(started, next_round([{"id": "i-scope-2", "kind": "confirm", "carries": ["i-scope"],
                                            "body": text("Open again?")}]), ticket=False)
    assert "i-scope" not in [p["id"] for p in rd.returning(json.loads(Path(started["doc"]).read_text("utf-8")))]


@pytest.mark.parametrize("line", ["i-data reopen", "i-data — | Use the new name."])
def test_the_real_ingest_returns_an_older_card(tmp_path, line):
    doc, raw = tmp_path / "doc.json", tmp_path / "raw.txt"
    doc.write_text(json.dumps(_next_round(_example())), "utf-8")
    raw.write_text(f"[round R-2]\n{line}", "utf-8")
    run = subprocess.run([sys.executable, str(ENGINE), "ingest", str(doc), "--raw-file", str(raw)],
                         capture_output=True, text=True, encoding="utf-8", timeout=60,
                         env={**os.environ, "LOCALAPPDATA": str(tmp_path / "local")})
    assert run.returncode == 0, run.stdout + run.stderr
    after = json.loads(doc.read_text("utf-8"))
    for rnd in after["rounds"]:
        for item in rnd["items"]:
            item.setdefault("state", "open")
    assert _find(after, "i-data").get("settled") is None
    assert [item["id"] for item in rd.returning(after)] == ["i-data"]


def test_a_steer_is_kept_word_for_word_and_settles_nothing(world):
    started = first_round(world)
    pending = answered(world, started, "i-scope: accept\ni-format: accept\nn-format: note: prefer plain text\n")
    assert pending["needs_reading"] == []
    assert pending["steers"][0]["text"] == "prefer plain text"
    assert pending["steers"][0]["target"] == "n-format"
    world.run("sync", doc=started["doc"], log=started["log"])
    assert '- Steer: n-format (N-1-n-format): "prefer plain text"' in Path(started["log"]).read_text("utf-8")


def test_an_older_steer_on_the_map_kept_on_a_card_reads_as_a_steer():
    """An engine before round steers kept a note on the map itself on a free card. It names no card."""
    steer = {"id": "N-1-i-format", "round": 1, "target": "m-scope", "text": "link the issue", "deleted": False}
    first = round_one()
    doc = {"schema": "afkv2.page/0", "session": {**session(), "started": "2026-01-01T00:00:00Z"},
           "maps": first["maps"], "rounds": [{"n": 1, "state": "current", "banner": first["banner"], "items": [
               {**first["items"][0], "state": "open"},
               {**first["items"][1], "state": "needs_reading", "notes": [steer]}]}]}
    pending = rd.pending(doc)
    assert pending["steers"] == [{**steer, "item": "i-format"}]
    assert pending["needs_reading"] == [{"id": "i-format", "kind": "debate", "state": "needs_reading", "notes": []}]


@pytest.mark.parametrize("payload, code", [
    ({"settle": [{"item": "i-format", "note": "N-1-i-format", "reading": " "}]}, "no-reading"),
    ({"settle": [{"item": "i-format", "note": "N-9-i-format", "reading": "r"}]}, "no-note"),
    ({"settle": [{"item": "i-scope", "note": "N-1-i-format", "reading": "r"}]}, "not-needs-reading"),
    ({"settle": [{"item": "i-none", "note": "N-1-i-format", "reading": "r"}]}, "not-in-round"),
    ({"open": [{"item": "i-format", "reply": ""}]}, "no-reply"),
    ({"unblock": ["i-format"]}, "not-blocked"),
    ({"other": []}, "bad-payload"),
])
def test_bad_readings_refuse_and_change_nothing(world, payload, code):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: note: csv\n")
    before = Path(started["doc"]).read_bytes()
    answer = world.run("apply-readings", expect=1, doc=started["doc"], readings=world.file("r.json", payload))
    assert answer["error"]["code"] == code
    assert Path(started["doc"]).read_bytes() == before


def test_a_note_on_an_info_card_cannot_settle(world):
    started = first_round(world)
    pending = answered(world, started, "i-scope: accept\ni-format: accept\ni-ticket: note: also see the archive\n")
    assert [p["id"] for p in pending["needs_reading"]] == ["i-ticket"]
    answer = world.run("apply-readings", expect=1, doc=started["doc"], readings=world.file("r.json", {
        "settle": [{"item": "i-ticket", "note": "N-1-i-ticket", "reading": "r"}]}))
    assert answer["error"]["code"] == "info-card"
    world.run("apply-readings", doc=started["doc"], readings=world.file("r2.json", {
        "open": [{"item": "i-ticket", "reply": "Noted: I read the archive ticket."}]}))


def test_info_card_left_open_needs_no_carry(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    world.build_round(started, next_round([{"id": "i-two", "kind": "confirm", "body": text("Two.")}]), ticket=False)


def test_blocked_card_unblocks(world):
    started = world.start_and_read()
    content = round_one()
    content["items"][1]["state"] = "blocked"
    world.build_round(started, content)
    answered(world, started, "i-scope: accept\n")
    world.run("apply-readings", doc=started["doc"], readings=world.file("r.json", {"unblock": ["i-format"]}))
    doc = json.loads(Path(started["doc"]).read_text("utf-8"))
    assert {i["id"]: i["state"] for i in doc["rounds"][0]["items"]}["i-format"] == "open"


def test_decided_row_carries_its_provenance(world):
    started = world.start_and_read()
    content = round_one()
    content["items"][0] = {"id": "i-scope", "kind": "decided", "node": "n-scope", "decided": DECIDED}
    world.build_round(started, content)
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    world.run("sync", doc=started["doc"], log=started["log"])
    log = Path(started["log"]).read_text("utf-8")
    assert ("- Settled: The export writes UTF-8. · decided-by agent R1 · accepted 2026-01-05 · "
            "repo: src/io.py:12 writes UTF-8 · reverse: change the writer · card i-scope") in log


# ---- grill log, glossary, exit gate


def full_rows(world, log):
    for kind, row in (("Policy", "developer: may export; guest denied; own orders; total required"),
                      ("Staples", "none"), ("Examples", "WE-1 frequent, WE-2 edge, WE-3 risky"),
                      ("Devil", "pass ran; findings resolved")):
        world.run("row", log=log, kind=kind, text=row)


def settled_session(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    world.run("sync", doc=started["doc"], log=started["log"])
    return started


def test_start_creates_only_its_own_log_section_and_keeps_the_others(world):
    log = world.repo / "specs" / "PROJ-1" / "GRILL-LOG.md"
    log.parent.mkdir(parents=True)
    log.write_text("# Grill log — PROJ-1\n\n## Solution grill\n\n- Locked: L1 keep\n", "utf-8")
    started = settled_session(world)
    assert Path(started["log"]) == log
    text_now = log.read_text("utf-8")
    assert "- Locked: L1 keep" in text_now
    assert text_now.index("## Solution grill") < text_now.index("## Requirements grill")


def test_ledger_row_overwrites_in_place_and_refuses_a_bad_status(world):
    started = world.run("start", ticket_key="PROJ-1")
    log = started["log"]
    world.run("row", log=log, kind="Ledger", text="orders have totals → pending")
    world.run("row", log=log, kind="Ledger", text="orders have totals → verified (src/o.py:4)")
    body = Path(log).read_text("utf-8")
    assert "→ pending" not in body and body.count("orders have totals") == 1
    world.run("row", expect=1, log=log, kind="Ledger", text="orders have totals, I think")
    world.run("row", expect=1, log=log, kind="Nonsense", text="x")


def test_round_zero_row_keeps_the_human_words_verbatim(world):
    started = world.run("start", ticket_key="PROJ-1")
    words = 'line one\nline "two"'
    by_file = ('--text "<text>"', '--text-file "<text file>"')
    world.run("row", swap=by_file, log=started["log"], kind="Round 0", text_file=world.file("words.txt", words))
    body = Path(started["log"]).read_text("utf-8")
    assert "- Round 0: " + json.dumps(words, ensure_ascii=False) in body
    world.run("row", log=started["log"], kind="Round 0", text="new")
    body = Path(started["log"]).read_text("utf-8")
    assert "line one" not in body and '- Round 0: "new"' in body


def test_sync_keeps_agent_rows_and_is_idempotent(world):
    started = settled_session(world)
    world.run("row", log=started["log"], kind="Ledger", text="orders have totals → verified (src/o.py:4)")
    world.run("sync", doc=started["doc"], log=started["log"])
    once = Path(started["log"]).read_text("utf-8")
    world.run("sync", doc=started["doc"], log=started["log"])
    assert Path(started["log"]).read_text("utf-8") == once
    assert once.count("- Settled: The export covers one order per file.") == 1
    assert "orders have totals" in once
    assert f"- Session: {started['session']}" in once


def test_term_goes_to_the_glossary_as_it_settles(world):
    started = world.run("start", ticket_key="PROJ-1")
    glossary = world.repo / "GLOSSARY.md"
    world.run("term", log=started["log"], glossary=glossary, term="Order file",
              definition="The file one export writes for one order.")
    body = glossary.read_text("utf-8")
    assert "**Order file**:\nThe file one export writes for one order.\n" in body
    world.run("term", log=started["log"], glossary=glossary, term="Order file", definition="A better definition.")
    body = glossary.read_text("utf-8")
    assert body.count("**Order file**:") == 1 and "A better definition." in body
    assert "The file one export" not in body
    assert f"- Term: Order file → verified ({glossary.name})" in Path(started["log"]).read_text("utf-8")


def test_term_upsert_keeps_other_entries(world):
    started = world.run("start", ticket_key="PROJ-1")
    glossary = world.repo / "GLOSSARY.md"
    glossary.write_text("# G\n\n**Alpha**:\nFirst.\n`Related:` Beta\n\n**Beta**:\nSecond.\n", "utf-8")
    world.run("term", log=started["log"], glossary=glossary, term="Alpha", definition="New.")
    assert glossary.read_text("utf-8") == "# G\n\n**Alpha**:\nNew.\n`Related:` Beta\n\n**Beta**:\nSecond.\n"


def test_a_mention_or_a_dependency_does_not_carry_a_point(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\n")
    dependent = {"id": "i-next", "kind": "decided", "decided": {**DECIDED, "depends_on": ["i-format"]},
                 "body": text("Holds if i-format = CSV.")}
    with pytest.raises(AssertionError, match="missing-carry"):
        world.build_round(started, next_round([dependent]), ticket=False)
    world.build_round(started, next_round([dependent, {"id": "i-format-2", "kind": "debate", "carries": ["i-format"],
                                                       "body": text("Which file format?")}]), ticket=False)


def test_a_carry_of_an_unknown_card_is_refused(tmp_path):
    content = round_one()
    content["items"][0]["carries"] = ["i-none"]
    with pytest.raises(rd.Refusal) as caught:
        rd.build_round_document(tmp_path / "doc.json", session(), content)
    assert caught.value.code == "bad-item"


REPLACE = ('--round-input "<round input>"', '--replace --round-input "<round input>"')


def test_a_round_the_engine_refused_can_be_built_again(world):
    started = world.start_and_read()
    world.build_round(started, round_one())
    world.env["FAKE_ENGINE_REFUSE"] = "check"
    assert world.run("present", expect=1, doc=started["doc"])["error"]["verb"] == "check"
    del world.env["FAKE_ENGINE_REFUSE"]
    corrected = round_one()
    corrected["items"][0]["body"] = text("Corrected.")
    answer = world.run("build", swap=REPLACE, doc=started["doc"], session=started["session"], ticket_key=started["ticket"],
                       round_input=world.file("round.json", corrected), ticket_file=world.scratch / "ticket.json")
    assert answer["round"] == 1
    world.run("present", doc=started["doc"])
    doc = json.loads(Path(started["doc"]).read_text("utf-8"))
    assert len(doc["rounds"]) == 1 and doc["rounds"][0]["state"] == "current"
    shown = json.dumps(doc["rounds"][0]["items"])
    assert "Corrected." in shown and "per file" not in shown and shown.count('"i-ticket"') == 1


def test_replace_restores_the_round_before_and_closes_it_again(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    world.build_round(started, next_round([{"id": "i-two", "kind": "confirm", "body": text("Two.")}]), ticket=False)
    answer = world.run("build", swap=REPLACE, doc=started["doc"], session=started["session"], ticket_key=started["ticket"],
                       round_input=world.file("round.json", next_round([{"id": "i-two", "kind": "confirm",
                                                                         "body": text("Two, corrected.")}])),
                       ticket_file=world.file("t.json", {}))
    assert answer["round"] == 2
    doc = json.loads(Path(started["doc"]).read_text("utf-8"))
    assert [r["state"] for r in doc["rounds"]] == ["settled", "current"]
    world.run("present", doc=started["doc"])


def test_replace_refuses_a_round_with_an_answer(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    before = Path(started["doc"]).read_bytes()
    answer = world.run("build", expect=1, swap=REPLACE, doc=started["doc"], session=started["session"],
                       ticket_key=started["ticket"], round_input=world.file("round.json", round_one()),
                       ticket_file=world.file("t.json", {}))
    assert answer["error"]["code"] == "round-answered"
    assert Path(started["doc"]).read_bytes() == before


def replace_round(world, started, expect=0, content=None):
    return world.run("build", expect=expect, swap=REPLACE, doc=started["doc"], session=started["session"],
                     ticket_key=started["ticket"], round_input=world.file("round.json", content or round_one()),
                     ticket_file=world.file("t.json", {}))


def test_replace_refuses_a_shown_round_with_no_answer(world):
    started = first_round(world)
    before = Path(started["doc"]).read_bytes()
    assert replace_round(world, started, expect=1)["error"]["code"] == "round-shown"
    assert Path(started["doc"]).read_bytes() == before


def test_replace_refuses_a_round_whose_show_failed_because_chat_shows_it(world):
    started = world.start_and_read()
    world.build_round(started, round_one())
    world.env["FAKE_ENGINE_REFUSE"] = "show"
    assert world.run("present", expect=1, doc=started["doc"])["error"]["verb"] == "show"
    del world.env["FAKE_ENGINE_REFUSE"]
    assert replace_round(world, started, expect=1)["error"]["code"] == "round-shown"


def test_replace_works_on_a_later_round_the_engine_refused(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    world.build_round(started, next_round([{"id": "i-two", "kind": "confirm", "body": text("Two.")}]), ticket=False)
    world.env["FAKE_ENGINE_REFUSE"] = "render"
    assert world.run("present", expect=1, doc=started["doc"])["error"]["verb"] == "render"
    del world.env["FAKE_ENGINE_REFUSE"]
    corrected = next_round([{"id": "i-two", "kind": "confirm", "body": text("Two, corrected.")}])
    assert replace_round(world, started, content=corrected)["round"] == 2


def test_ingest_removes_the_shown_record(world):
    started = first_round(world)
    record = rd.shown_record(started["doc"])
    assert record.read_text("utf-8").strip() == "1"
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    assert not record.exists()


def test_resume_of_a_shown_round_presents_again_with_no_replace(world):
    started = first_round(world)
    assert world.start_and_read()["session"] == started["session"]
    assert world.run("present", doc=started["doc"])["ok"] is True
    assert replace_round(world, started, expect=1)["error"]["code"] == "round-shown"


def signoff_session(world):
    started = world.start_and_read()
    world.build_round(started, {"banner": {"settled": [], "unlocks": [], "parked": []},
                                "items": [{"id": "i-sign", "kind": "signoff", "body": text("The field table is final.")}]})
    return started


def test_a_clear_note_does_not_settle_a_signoff_card(world):
    started = signoff_session(world)
    answered(world, started, "i-sign: note: Fine, go ahead.\n")
    before = Path(started["doc"]).read_bytes()
    readings = {"settle": [{"item": "i-sign", "note": "N-1-i-sign", "reading": "Signs the table."}]}
    answer = world.run("apply-readings", expect=1, doc=started["doc"], readings=world.file("r.json", readings))
    assert answer["error"]["code"] == "signoff-needs-mark"
    assert Path(started["doc"]).read_bytes() == before


def test_a_sign_mark_settles_a_signoff_card_and_opens_the_exit_gate(world):
    started = signoff_session(world)
    answered(world, started, "i-sign: sign\n")
    item = json.loads(Path(started["doc"]).read_text("utf-8"))["rounds"][0]["items"][1]
    assert item["id"] == "i-sign" and item["state"] == "settled_by_mark"
    full_rows(world, started["log"])
    assert world.run("gate", doc=started["doc"], log=started["log"])["ok"] is True


def test_the_exit_gate_refuses_a_signoff_card_with_no_sign_mark(world):
    started = signoff_session(world)
    answered(world, started, "i-sign: note: Fine, go ahead.\n")
    doc = json.loads(Path(started["doc"]).read_text("utf-8"))
    item = doc["rounds"][0]["items"][1]
    item.update(state="settled_by_note", settled={"by": "note", "round": 1, "signal": "N-1-i-sign", "reading": "Signs."})
    Path(started["doc"]).write_text(json.dumps(doc), "utf-8")
    full_rows(world, started["log"])
    failures = world.run("gate", expect=1, doc=started["doc"], log=started["log"])["error"]["failures"]
    assert any("i-sign" in failure and "sign mark" in failure for failure in failures)


def test_exit_gate_lists_every_failure_and_passes_when_clean(world):
    started = settled_session(world)
    log, doc = started["log"], started["doc"]
    world.run("row", log=log, kind="Ledger", text="orders have totals → pending")
    world.run("row", log=log, kind="Term", text="Order file → pending")
    answer = world.run("gate", expect=1, doc=doc, log=log)
    assert answer["error"]["code"] == "exit-gate"
    joined = "\n".join(answer["error"]["failures"])
    for needed in ("orders have totals", "Order file", "Policy", "Staples", "Examples", "Devil"):
        assert needed in joined
    assert "exit gate passed" not in Path(log).read_text("utf-8")

    world.run("row", log=log, kind="Ledger", text="orders have totals → refuted (src/o.py:4)")
    joined = "\n".join(world.run("gate", expect=1, doc=doc, log=log)["error"]["failures"])
    assert "refuted" in joined

    world.run("row", log=log, kind="Ledger", text="orders have totals → verified (src/o.py:4)")
    world.run("row", log=log, kind="Term", text="Order file → verified (GLOSSARY.md)")
    full_rows(world, log)
    assert world.run("gate", doc=doc, log=log)["ok"] is True
    assert re.search(rf"- Settled: exit gate passed \d{{4}}-\d\d-\d\d · session {started['session']}",
                     Path(log).read_text("utf-8"))


def test_exit_gate_refuses_an_open_point_and_an_unanswered_round(world):
    started = first_round(world)
    full_rows(world, started["log"])
    joined = "\n".join(world.run("gate", expect=1, doc=started["doc"], log=started["log"])["error"]["failures"])
    assert "i-scope" in joined and "no answer" in joined
    answered(world, started, "i-scope: accept\ni-format: note: maybe\n")
    joined = "\n".join(world.run("gate", expect=1, doc=started["doc"], log=started["log"])["error"]["failures"])
    assert "i-format" in joined and "i-scope" not in joined


def test_passed_gate_starts_a_new_session_and_first_sync_voids_the_old_pass(world):
    started = settled_session(world)
    full_rows(world, started["log"])
    world.run("gate", doc=started["doc"], log=started["log"])
    again = world.run("start", ticket_key="PROJ-1")
    assert again["resume"] is False and again["session"] != started["session"]
    world.run("sync", doc=started["doc"], log=started["log"])
    assert "exit gate passed" not in Path(started["log"]).read_text("utf-8")


def test_real_engine_accepts_the_built_document(tmp_path):
    path = tmp_path / "doc.json"
    rd.build_round_document(path, session(), round_one())
    run = subprocess.run([sys.executable, str(ENGINE), "check", str(path)],
                         capture_output=True, text=True, timeout=60,
                         env={**os.environ, "LOCALAPPDATA": str(tmp_path / "local")})
    assert run.returncode == 0, run.stdout + run.stderr


# ---- returns stay answered, sessions stay on the log


def test_a_carried_point_does_not_return_again(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    world.build_round(started, next_round([{"id": "i-two", "kind": "confirm", "body": text("Two.")}]), ticket=False)
    answered(world, started, "i-two: accept\ni-scope: note: only for open orders\n")
    world.build_round(started, next_round([{"id": "i-scope-2", "kind": "confirm", "carries": ["i-scope"],
                                            "body": text("Only for open orders?")}]), ticket=False)
    pending = answered(world, started, "i-scope-2: accept\n")
    assert pending["returned"] == []
    world.build_round(started, next_round([{"id": "i-four", "kind": "confirm", "body": text("Four.")}]), ticket=False)
    pending = answered(world, started, "i-four: accept\n")
    assert pending["returned"] == []
    world.run("sync", doc=started["doc"], log=started["log"])
    full_rows(world, started["log"])
    assert world.run("gate", doc=started["doc"], log=started["log"])["ok"] is True


def test_a_second_session_keeps_the_rows_of_the_first(world):
    first = settled_session(world)
    full_rows(world, first["log"])
    world.run("gate", doc=first["doc"], log=first["log"])
    second = world.run("start", ticket_key="PROJ-1")
    content = round_one()
    for item in content["items"]:
        item["id"] += "-b"
    world.build_round(second, content, ticket=False)
    answered(world, second, "i-scope-b: note: mine\n")
    world.run("sync", doc=second["doc"], log=second["log"])
    log = Path(second["log"]).read_text("utf-8")
    assert "· settled by mark accept R1 · card i-scope\n" in log, "the first session's row stays"
    assert 'owner note on i-scope-b (N-1-i-scope-b): "mine"' in log
    assert f"- Session: {first['session']}" in log and f"- Session: {second['session']}" in log
    assert log.index(first["session"]) < log.index(second["session"])


def test_a_verified_ledger_row_needs_its_citation(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.run("row", expect=1, log=started["log"], kind="Ledger", text="orders have totals → verified")
    world.run("row", expect=1, log=started["log"], kind="Ledger", text="orders have totals → refuted")
    world.run("row", log=started["log"], kind="Ledger", text="orders have totals → unverified-external (human acknowledged)")


def test_candidate_term_goes_on_the_log_and_not_in_the_glossary(world):
    started = world.run("start", ticket_key="PROJ-1")
    glossary = world.repo / "GLOSSARY.md"
    pending = ('--glossary "<glossary>" --term "<term>" --definition "<definition>"', '--term "<term>" --pending')
    world.run("term", swap=pending, log=started["log"], term="Order file")
    assert "- Term: Order file → pending" in Path(started["log"]).read_text("utf-8")
    assert not glossary.exists()


@pytest.mark.parametrize("content, code, status", [
    ({"banner": {}, "items": "not a list"}, "bad-round", 1),
    ({"banner": {}, "items": [{"id": "i-a", "kind": "decided", "body": "not a component"}]}, "bad-input", 2),
    ({"banner": {}, "items": [], "maps": [{"props": {"nodes": ["not a node"]}}]}, "bad-input", 2),
])
def test_a_malformed_round_answers_json_and_writes_nothing(world, content, code, status):
    started = world.run("start", ticket_key="PROJ-1")
    answer = world.run("build", expect=status, doc=started["doc"], session=started["session"], ticket_key=started["ticket"],
                       round_input=world.file("bad.json", content), ticket_file=world.file("t.json", {}))
    assert answer["ok"] is False and answer["error"]["code"] == code
    assert not Path(started["doc"]).exists()


def test_a_failed_reverse_search_leaves_the_rest_of_the_read(tmp_path):
    world = World(tmp_path, "tickets_github.json", GITHUB)
    world.env["FAKE_TRACKER_REFUSE"] = "issue-search"
    out = world.scratch / "ticket.json"
    world.run("read-ticket", ticket_key="7", ticket_file=out)
    ticket = json.loads(out.read_text("utf-8"))
    assert [link["key"] for link in ticket["links"]] == ["8"]
    assert any("issue-search" in entry["reason"] for entry in ticket["unread_links"])
