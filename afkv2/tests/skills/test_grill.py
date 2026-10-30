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
from pathlib import Path

import pytest

from test_visualize import check_document

PLUGIN = Path(__file__).resolve().parents[2]
SKILL_DIR = PLUGIN / "skills" / "grill"
SKILL_MD = SKILL_DIR / "SKILL.md"
ENGINE = PLUGIN / "engine" / "engine.py"
FAKES = Path(__file__).resolve().parent / "fakes"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import round_document as rd  # noqa: E402

STEP = re.compile(r"^ *```sh step=([\w-]+)\n *(.*?)\n *```", re.S | re.M)
STEP_ORDER = ["start", "read-ticket", "row", "build", "present", "wait", "ingest",
              "apply-readings", "sync", "term", "gate"]


def skill_steps():
    return dict(STEP.findall(SKILL_MD.read_text("utf-8")))


class World:
    def __init__(self, root, tickets, config):
        self.root = root
        self.plugin = root / "plugin"
        self.repo = root / "repo"
        self.calls = root / "calls.log"
        self.raw = root / "raw-response.txt"
        shutil.copytree(SKILL_DIR, self.plugin / "skills" / "grill",
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
                      {"id": "i-format", "kind": "debate", "node": "n-format",
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
    assert "def build_round_document(" in (SKILL_DIR / "scripts" / "round_document.py").read_text("utf-8")


def test_commands_come_in_the_contract_order():
    assert list(skill_steps()) == STEP_ORDER


def test_no_step_asks_for_a_lane():
    for path in SKILL_DIR.rglob("*.md"):
        assert not re.search(r"\blanes?\b", path.read_text("utf-8"), re.I), path


def test_no_v1_name_and_no_upstream_caller():
    v1 = re.compile(r"afk(?!v2)", re.I)
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
    for path in (SKILL_DIR / "scripts").glob("*.py"):
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
    assert doc["schema"] == "afkv2.page/0"
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
    shown = json.dumps(item["body"])
    for value in ("The export writes UTF-8.", "UTF-16: no reader asks for it", "repo: src/io.py:12",
                  "Beats UTF-16", "reverse: change the writer", "depends-on: none"):
        assert value in shown


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


def test_dry_run_on_claude_settles_one_by_mark_and_one_by_note(world):
    started = first_round(world)
    doc = json.loads(Path(started["doc"]).read_text("utf-8"))
    assert doc["session"]["skill"] == "grill"
    assert Path(started["doc"]).name == f"grill-{started['session']}.json"
    assert Path(started["doc"]).parent.name == "pages"
    ticket_card = doc["rounds"][0]["items"][0]
    shown = json.dumps(ticket_card)
    assert ticket_card["kind"] == "info" and "What about cancelled orders?" in shown and "PROJ-2" in shown
    check_document(doc)

    raw = "i-scope: accept\ni-format: note: csv please, \"quoted\" é\n"
    world.raw.write_bytes(raw.encode("utf-8"))
    raw_file = Path(started["raw_file"])
    world.run("wait", doc=started["doc"], raw_file=raw_file)
    assert raw_file.read_bytes() == raw.encode("utf-8")

    pending = world.run("ingest", doc=started["doc"], raw_file=raw_file)
    assert not raw_file.exists(), "the raw text now lives in the document"
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
    carried = {"id": "i-format-2", "kind": "debate", "node": "n-format",
               "body": text("From i-format. Your note: maybe. Which file format?")}
    world.build_round(started, next_round([carried]), ticket=False)
    world.run("present", doc=started["doc"])
    doc = json.loads(Path(started["doc"]).read_text("utf-8"))
    assert [r["state"] for r in doc["rounds"]] == ["settled", "current"]
    check_authored_part(doc)


def test_a_note_on_an_older_card_returns_and_must_be_carried(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    world.build_round(started, next_round([{"id": "i-two", "kind": "confirm", "body": text("Two.")}]), ticket=False)
    pending = answered(world, started, "i-two: accept\ni-scope: note: only for open orders\n")
    assert [p["id"] for p in pending["returned"]] == ["i-scope"]
    with pytest.raises(AssertionError, match="missing-carry"):
        world.build_round(started, next_round([{"id": "i-three", "kind": "confirm", "body": text("x")}]), ticket=False)
    world.build_round(started, next_round([{"id": "i-scope-2", "kind": "confirm",
                                            "body": text("From i-scope: only for open orders?")}]), ticket=False)
    world.run("sync", doc=started["doc"], log=started["log"])
    log = Path(started["log"]).read_text("utf-8")
    assert 'owner note on i-scope (N-2-i-scope): "only for open orders"' in log


def test_a_steer_is_kept_word_for_word_and_settles_nothing(world):
    started = first_round(world)
    pending = answered(world, started, "i-scope: accept\ni-format: accept\nn-format: note: prefer plain text\n")
    assert pending["needs_reading"] == []
    assert pending["steers"][0]["text"] == "prefer plain text"
    assert pending["steers"][0]["target"] == "n-format"
    world.run("sync", doc=started["doc"], log=started["log"])
    assert '- Steer: n-format (N-1-i-format): "prefer plain text"' in Path(started["log"]).read_text("utf-8")


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
    assert glossary.read_text("utf-8") == "# G\n\n**Alpha**:\nNew.\n\n**Beta**:\nSecond.\n"


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


@pytest.mark.skipif(not ENGINE.exists(), reason="page engine not merged yet; the fake engine checks")
def test_real_engine_accepts_the_built_document(tmp_path):
    path = tmp_path / "doc.json"
    rd.build_round_document(path, session(), round_one())
    run = subprocess.run([sys.executable, str(ENGINE), "check", str(path)],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr


# ---- returns stay answered, sessions stay on the log


def test_a_carried_point_does_not_return_again(world):
    started = first_round(world)
    answered(world, started, "i-scope: accept\ni-format: accept\n")
    world.build_round(started, next_round([{"id": "i-two", "kind": "confirm", "body": text("Two.")}]), ticket=False)
    answered(world, started, "i-two: accept\ni-scope: note: only for open orders\n")
    world.build_round(started, next_round([{"id": "i-scope-2", "kind": "confirm",
                                            "body": text("From i-scope: only for open orders?")}]), ticket=False)
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
