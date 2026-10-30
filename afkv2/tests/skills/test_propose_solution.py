"""Tests for the propose-solution skill.

The dry runs take every command from the fenced `sh step=...` blocks of SKILL.md, so a command the
skill states is a command that ran. Engine and config reader are recorded fakes (fakes/) in a
throwaway plugin tree. Once the S1 engine exists, the built document also goes through the real
`engine check`.
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

PLUGIN = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
SKILL_DIR = SKILLS / "propose-solution"
SKILL_MD = SKILL_DIR / "SKILL.md"
ENGINE = PLUGIN / "engine" / "engine.py"
HERE = Path(__file__).resolve().parent
FAKES = HERE / "fakes"
FIXTURES = HERE / "fixtures" / "propose_solution"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import design_files  # noqa: E402
import design_round as dr  # noqa: E402
import fork_cards  # noqa: E402
from grill_common import Refusal  # noqa: E402

STEP = re.compile(r"^ *```sh step=([\w-]+)\n *(.*?)\n *```", re.S | re.M)
STEP_ORDER = ["start", "row", "next", "second-provider", "build", "present", "wait", "ingest", "apply-readings", "gate"]
CAT_A = ["entities", "relations", "keys", "constraints", "cascade", "api", "migration", "authorization", "lifecycle",
         "other-teams", "large-data"]
CAT_A_LABELS = ["Entities", "Relations", "Keys", "Constraints", "Cascade", "API contract and compatibility",
                "Data migration", "Authorization", "Entity life cycle and states", "Other teams' modules", "Large data"]
SESSION = {"id": "s-1", "skill": "propose-solution", "feature": "PROJ-1", "ticket": "PROJ-1"}
OPTIONS = [{"name": "Join table", "text": "Keeps every run."}, {"name": "Run id", "text": "Keeps the last run."}]


def skill_steps():
    return dict(STEP.findall(SKILL_MD.read_text("utf-8")))


def picture(item_id):
    return {"type": "table", "id": f"{item_id}-now", "props": {"columns": ["Entity"], "rows": [["order"]]}}


def aspect_card(key, item_id=None, **extra):
    item_id = item_id or f"a-{key}"
    body = picture(item_id)
    body["children"] = [{"type": "text", "id": f"{item_id}-question", "props": {"text": f"The reading on {key}."}}]
    return {"id": item_id, "aspect": key, "kind": "confirm", "body": body, **extra}


def layer_card(layer, item_id=None, **extra):
    item_id = item_id or f"l-{layer.lower()}"
    return {"id": item_id, "layer": layer, "kind": "confirm",
            "body": {"type": "text", "id": f"{item_id}-text", "props": {"text": f"{layer} is inherited."}}, **extra}


def round_of(*items):
    return {"banner": {"settled": [], "unlocks": [], "parked": []}, "items": list(items)}


def nodes_of(doc, map_id):
    chart = next(chart for chart in doc["maps"] if chart["id"] == map_id)
    return {node["id"]: node for node in chart["props"]["nodes"]}


class World:
    def __init__(self, root, config=True, spec=True):
        self.root = root
        self.plugin = root / "plugin"
        self.repo = root / "repo"
        self.calls = root / "calls.log"
        self.raw = root / "raw-response.txt"
        for skill in ("propose-solution", "grill", "to-prd"):
            shutil.copytree(SKILLS / skill, self.plugin / "skills" / skill, ignore=shutil.ignore_patterns("__pycache__"))
        for fake, target in (("fake_engine.py", "engine/engine.py"), ("fake_config.py", "scripts/afkv2_config.py")):
            (self.plugin / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(FAKES / fake, self.plugin / target)
        self.repo.mkdir()
        if config:
            (self.repo / ".afkv2").mkdir()
            (self.repo / ".afkv2" / "config.json").write_text(
                json.dumps({"spec_folder": "specs", "tracker": {"kind": "jira"}}), "utf-8")
        self.spec = self.repo / "specs" / "PROJ-1"
        if spec:
            shutil.copytree(FIXTURES / "spec", self.spec)
        self.env = {"FAKE_CALL_LOG": str(self.calls), "FAKE_POLL_RAW": str(self.raw)}
        self.scratch = root / "scratch"
        self.scratch.mkdir()

    def run(self, step, expect=0, swap=None, **values):
        """Run one stated command with its placeholders filled; return its one JSON answer."""
        command = skill_steps()[step]
        if swap:
            assert swap[0] in command
            command = command.replace(*swap)
        filled = {"python": Path(sys.executable), "this skill's folder": self.plugin / "skills" / "propose-solution",
                  **{k.replace("_", " "): v for k, v in values.items()}}
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

    def doc(self, started):
        return json.loads((self.repo / started["doc"]).read_text("utf-8"))

    def build(self, started, content, **kwargs):
        return self.run("build", doc=started["doc"], session=started["session"], ticket_key=started["ticket"],
                        round_input=self.file("round.json", content), **kwargs)

    def answer(self, started, raw):
        self.raw.write_bytes(raw.encode("utf-8"))
        self.run("wait", doc=started["doc"], raw_file=started["raw_file"])
        return self.run("ingest", doc=started["doc"], raw_file=started["raw_file"])

    def accept_all(self, started):
        items = next(rnd for rnd in self.doc(started)["rounds"] if rnd["state"] == "current")["items"]
        marks = {"signoff": "sign", "debate": "option:a"}
        self.answer(started, "\n".join(f"{item['id']}: {marks.get(item['kind'], 'accept')}" for item in items))

    def write_design(self, sdd=None):
        (self.spec / "SDD.md").write_text(sdd or (FIXTURES / "design" / "SDD.md").read_text("utf-8"), "utf-8")
        target = self.spec / "adr" / "design"
        target.mkdir(parents=True, exist_ok=True)
        for adr in (FIXTURES / "design" / "adr").glob("*.md"):
            shutil.copy(adr, target / adr.name)

    def walk_to_write(self, started):
        """All aspects, then all layers, a fork and a sign-off, with every point accepted."""
        fork = {"id": "f-relations", "aspect": "relations",
                "fork": {"question": "How does a run link?", "options": OPTIONS, "recommended": "a",
                         "why_open": "2 live options.", "picture": picture("f-relations")}}
        cards = [fork if key == "relations" else aspect_card(key) for key in CAT_A]
        self.build(started, round_of(*cards))
        self.accept_all(started)
        sign = {"id": "sign-hl-1", "locked": "HL-1", "kind": "signoff",
                "body": {"type": "text", "id": "sign-hl-1-text", "props": {"text": "The field table is final."}}}
        self.build(started, round_of(sign, *(layer_card(f"L{n}") for n in range(1, 10))))
        self.accept_all(started)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


# The skill file.

def test_frontmatter_names_the_skill():
    head = SKILL_MD.read_text("utf-8").split("---")[1]
    assert re.search(r"^name: propose-solution$", head, re.M)
    assert re.search(r"^description: /afkv2:propose-solution", head, re.M)


def test_skill_states_every_command_in_order():
    assert [name for name, _ in STEP.findall(SKILL_MD.read_text("utf-8"))] == STEP_ORDER


def test_every_linked_sibling_exists():
    for target in re.findall(r"\]\(([^)#]+\.md)\)", SKILL_MD.read_text("utf-8")):
        assert (SKILL_DIR / target).resolve().is_file(), target


# CAT-A order.

def test_aspects_hold_cat_a_in_its_order():
    assert dr.group_keys("aspect") == CAT_A
    assert [label for _, label in dr.group_rows("aspect")] == CAT_A_LABELS


def test_no_other_file_restates_the_aspect_list():
    skill = SKILL_MD.read_text("utf-8")
    assert "Data migration" not in skill and "Large data" not in skill


def test_a_later_aspect_before_an_earlier_one_is_refused(tmp_path):
    with pytest.raises(Refusal) as refused:
        dr.build_design_round(tmp_path / "d.json", SESSION, round_of(aspect_card("relations")))
    assert refused.value.code == "out-of-order"
    assert "aspect-entities" in refused.value.reason
    assert not (tmp_path / "d.json").exists()


def test_aspects_in_order_in_one_round_are_accepted(tmp_path):
    answer = dr.build_design_round(tmp_path / "d.json", SESSION, round_of(*(aspect_card(key) for key in CAT_A)))
    assert answer["items"] == [f"a-{key}" for key in CAT_A]


def test_order_breaks_inside_one_round_too(tmp_path):
    with pytest.raises(Refusal) as refused:
        dr.build_design_round(tmp_path / "d.json", SESSION, round_of(aspect_card("keys"), aspect_card("entities")))
    assert refused.value.code == "out-of-order"


def test_a_second_card_on_an_asked_aspect_keeps_the_order(tmp_path):
    answer = dr.build_design_round(tmp_path / "d.json", SESSION, round_of(
        aspect_card("entities"), aspect_card("entities", "a-entities-2"), aspect_card("relations")))
    assert len(answer["items"]) == 3


def test_a_layer_card_waits_for_every_aspect(tmp_path):
    with pytest.raises(Refusal) as refused:
        dr.build_design_round(tmp_path / "d.json", SESSION, round_of(aspect_card("entities"), layer_card("L1")))
    assert refused.value.code == "aspects-first"


def test_next_counts_the_phases(world):
    started = world.run("start", ticket_key="PROJ-1")
    first = world.run("next", doc=started["doc"])
    assert first["phase"] == "aspects"
    assert [entry["key"] for entry in first["aspects_to_ask"]] == CAT_A


# Picture before a critical-aspect question.

def test_an_aspect_card_without_a_picture_is_refused(tmp_path):
    card = {"id": "a-entities", "aspect": "entities", "kind": "confirm",
            "body": {"type": "text", "props": {"text": "Which entities?"}}}
    with pytest.raises(Refusal) as refused:
        dr.build_design_round(tmp_path / "d.json", SESSION, round_of(card))
    assert refused.value.code == "no-picture"


def test_an_aspect_fork_without_a_picture_is_refused(tmp_path):
    card = {"id": "f", "aspect": "entities",
            "fork": {"question": "Which?", "options": OPTIONS, "why_open": "2 live options."}}
    with pytest.raises(Refusal) as refused:
        dr.build_design_round(tmp_path / "d.json", SESSION, round_of(card))
    assert refused.value.code == "no-picture"


@pytest.mark.parametrize("kind", ["info", "decided", "signoff"])
def test_an_aspect_card_asks_the_human(tmp_path, kind):
    with pytest.raises(Refusal) as refused:
        dr.build_design_round(tmp_path / "d.json", SESSION, round_of({**aspect_card("entities"), "kind": kind}))
    assert refused.value.code == "aspect-kind"


# Fork cards.

def test_fork_card_has_the_required_item_fields():
    item = fork_cards.build_fork_card("f-store", "Which store?", OPTIONS, "2 live options.", recommended="b", node="n-1")
    assert item["id"] == "f-store" and item["kind"] == "debate" and item["state"] == "open" and item["node"] == "n-1"
    assert isinstance(item["body"], dict) and item["body"]["type"] == "text"
    assert set(item) == {"id", "kind", "state", "node", "body"}


def test_fork_card_shows_the_options_side_by_side():
    item = fork_cards.build_fork_card("f-store", "Which store?", OPTIONS, "2 live options.")
    table = next(child for child in item["body"]["children"] if child["type"] == "table")
    assert table["props"]["columns"] == ["A — Join table", "B — Run id"]
    assert len(table["props"]["rows"]) == 1
    cells = table["props"]["rows"][0]
    assert [cell["id"] for cell in cells] == ["f-store-opt-a", "f-store-opt-b"]
    assert [cell["props"]["text"] for cell in cells] == ["Keeps every run.", "Keeps the last run."]


def test_fork_card_states_the_recommendation_and_why_it_is_open():
    item = fork_cards.build_fork_card("f", "Which?", OPTIONS, "A one-way door.", recommended="b")
    texts = json.dumps(item["body"])
    assert "Recommended: B." in texts and "A one-way door." in texts
    plain = fork_cards.build_fork_card("f", "Which?", OPTIONS, "A tie.")
    assert "No recommendation." in json.dumps(plain["body"])


def test_fork_card_with_a_picture_keeps_the_picture_as_root():
    now = picture("f")
    item = fork_cards.build_fork_card("f", "Which?", OPTIONS, "A tie.", picture=now)
    assert item["body"]["type"] == "table" and item["body"]["id"] == "f-now"
    assert [child["type"] for child in item["body"]["children"]] == ["text", "table", "text"]
    assert "children" not in now


@pytest.mark.parametrize("args, code", [
    (("f", "Which?", OPTIONS[:1], "A tie."), "bad-fork"),
    (("f", "", OPTIONS, "A tie."), "bad-fork"),
    (("f", "Which?", OPTIONS, ""), "bad-fork"),
    (("f", "Which?", [{"name": "A", "text": ""}, OPTIONS[1]], "A tie."), "bad-fork"),
    (("f", "Which?", [{"name": "A", "text": "x"}, {"name": "A", "text": "y"}], "A tie."), "bad-fork"),
    (("f", "Which?", [{"name": str(n), "text": "x"} for n in range(27)], "A tie."), "bad-fork"),
])
def test_a_bad_fork_is_refused(args, code):
    with pytest.raises(Refusal) as refused:
        fork_cards.build_fork_card(*args)
    assert refused.value.code == code


def test_a_recommendation_must_name_an_option():
    with pytest.raises(Refusal) as refused:
        fork_cards.build_fork_card("f", "Which?", OPTIONS, "A tie.", recommended="c")
    assert refused.value.code == "bad-fork"


def test_a_debate_card_must_come_from_a_fork(tmp_path):
    card = {"id": "d", "kind": "debate", "body": {"type": "text", "props": {"text": "A or B?"}}}
    with pytest.raises(Refusal) as refused:
        dr.build_design_round(tmp_path / "d.json", SESSION, round_of(card))
    assert refused.value.code == "not-a-fork"


def test_a_fork_input_with_a_body_or_a_stray_field_is_refused(tmp_path):
    fork = {"question": "Which?", "options": OPTIONS, "why_open": "A tie."}
    for card in ({"id": "f", "fork": fork, "body": {"type": "text"}},
                 {"id": "f", "fork": fork, "kind": "confirm"},
                 {"id": "f", "fork": {**fork, "extra": 1}},
                 {"id": "f", "fork": "A or B?"}):
        with pytest.raises(Refusal) as refused:
            dr.build_design_round(tmp_path / "d.json", SESSION, round_of(card))
        assert refused.value.code == "bad-fork"


def test_the_expanded_fork_survives_the_round_builder(tmp_path):
    card = {"id": "f", "fork": {"question": "Which?", "options": OPTIONS, "why_open": "A tie."}, "carries": []}
    path = tmp_path / "d.json"
    dr.build_design_round(path, SESSION, round_of(card))
    item = json.loads(path.read_text("utf-8"))["rounds"][0]["items"][0]
    assert item["kind"] == "debate" and "fork" not in item
    assert item["body"]["children"][0]["id"] == "f-options"


def test_a_reused_option_id_is_refused(tmp_path):
    card = lambda item_id: {"id": item_id, "fork": {"question": "Which?", "options": OPTIONS, "why_open": "A tie.",
                                                    "picture": picture("same")}}
    with pytest.raises(Refusal) as refused:
        dr.build_design_round(tmp_path / "d.json", SESSION, round_of(card("f-1"), card("f-2")))
    assert refused.value.code == "id-reused"


# The maps and the tags.

def test_round_one_draws_the_three_maps(tmp_path):
    path = tmp_path / "d.json"
    dr.build_design_round(path, SESSION, round_of(aspect_card("entities")))
    doc = json.loads(path.read_text("utf-8"))
    assert [chart["id"] for chart in doc["maps"]] == ["m-aspects", "m-layers", "m-locked"]
    aspects = nodes_of(doc, "m-aspects")
    assert list(aspects) == [f"aspect-{key}" for key in CAT_A]
    assert aspects["aspect-entities"]["state"] == "focus" and aspects["aspect-keys"]["state"] == "open"
    assert doc["rounds"][0]["items"][0]["node"] == "aspect-entities"
    assert "aspect" not in doc["rounds"][0]["items"][0] and "critical" not in doc["rounds"][0]["items"][0]


def test_a_settled_aspect_turns_its_node_settled(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.build(started, round_of(aspect_card("entities")))
    world.accept_all(started)
    world.build(started, round_of(aspect_card("relations")))
    aspects = nodes_of(world.doc(started), "m-aspects")
    assert aspects["aspect-entities"]["state"] == "settled"
    assert aspects["aspect-relations"]["state"] == "focus"
    assert aspects["aspect-entities"]["round"] == 2


def test_a_map_of_the_agent_stays_when_a_round_names_no_map(tmp_path):
    path = tmp_path / "d.json"
    chart = {"type": "map", "id": "m-mine", "props": {"title": "Mine", "nodes": [{"id": "n-1", "label": "One", "state": "open"}]}}
    dr.build_design_round(path, SESSION, {**round_of(aspect_card("entities")), "maps": [chart]})
    doc = json.loads(path.read_text("utf-8"))
    assert [item["id"] for item in doc["maps"]] == ["m-aspects", "m-layers", "m-locked", "m-mine"]


@pytest.mark.parametrize("card, code", [
    ({"id": "x", "aspect": "colour", "kind": "confirm", "body": {"type": "table"}}, "bad-item"),
    ({"id": "x", "layer": "L10", "kind": "confirm", "body": {"type": "text"}}, "bad-item"),
    ({"id": "x", "locked": "HL-9", "kind": "signoff", "body": {"type": "text"}}, "bad-item"),
    ({"id": "x", "aspect": "entities", "layer": "L1", "kind": "confirm", "body": {"type": "table"}}, "bad-item"),
    ({"id": "x", "aspect": "entities", "node": "n-1", "kind": "confirm", "body": {"type": "table"}}, "bad-item"),
    ({"id": "x", "node": "aspect-entities", "kind": "confirm", "body": {"type": "table"}}, "bad-item"),
    ({"id": "x", "kind": "signoff", "body": {"type": "text"}}, "signoff-untagged"),
    ("not an object", "bad-item"),
])
def test_a_bad_tag_is_refused(tmp_path, card, code):
    with pytest.raises(Refusal) as refused:
        dr.build_design_round(tmp_path / "d.json", SESSION, round_of(card))
    assert refused.value.code == code


def test_a_map_with_a_reserved_id_is_refused(tmp_path):
    chart = {"type": "map", "id": "m-aspects", "props": {"title": "Mine", "nodes": []}}
    with pytest.raises(Refusal) as refused:
        dr.build_design_round(tmp_path / "d.json", SESSION, {**round_of(aspect_card("entities")), "maps": [chart]})
    assert refused.value.code == "bad-round"


# Inputs.

def test_start_answers_the_paths(world):
    started = world.run("start", ticket_key="PROJ-1")
    assert started["resume"] is False and started["sdd_exists"] is False
    assert re.fullmatch(r".*/pages/propose-solution-s-[\d-]+\.json", started["doc"])
    assert started["raw_file"].endswith(f"propose-solution-{started['session']}.raw.txt")
    assert started["sdd"].endswith("SDD.md") and started["adr_dir"].endswith("adr/design")
    assert "## Solution design" in (world.spec / "GRILL-LOG.md").read_text("utf-8")


def test_missing_config_names_its_writer(tmp_path):
    world = World(tmp_path, config=False)
    error = world.run("start", expect=1, ticket_key="PROJ-1")["error"]
    assert error["code"] == "missing-input" and error["writer"] == "/afkv2:setup" and ".afkv2/config.json" in error["missing"]


def test_missing_grill_output_names_its_writer(tmp_path):
    world = World(tmp_path, spec=False)
    error = world.run("start", expect=1, ticket_key="PROJ-1")["error"]
    assert error["code"] == "missing-input" and error["writer"] == "/afkv2:grill" and "GRILL-LOG.md" in error["missing"]


def test_a_grill_with_no_passed_gate_names_its_writer(world):
    log = world.spec / "GRILL-LOG.md"
    log.write_text(log.read_text("utf-8").replace("- Settled: exit gate passed 2026-01-05 · session s-fixture\n", ""), "utf-8")
    assert world.run("start", expect=1, ticket_key="PROJ-1")["error"]["writer"] == "/afkv2:grill"


def test_missing_prd_names_its_writer(world):
    (world.spec / "PRD.md").unlink()
    error = world.run("start", expect=1, ticket_key="PROJ-1")["error"]
    assert error["code"] == "missing-input" and error["writer"] == "/afkv2:to-prd" and "PRD.md" in error["missing"]


def test_missing_ticket_key_is_named(world):
    command = ("start", ['--ticket "<ticket key>"', ""])
    error = world.run(command[0], expect=1, swap=command[1])["error"]
    assert error["code"] == "missing-input" and "ticket key" in error["missing"]


def test_a_second_process_needs_only_the_disk(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.build(started, round_of(aspect_card("entities")))
    resumed = world.run("start", ticket_key="PROJ-1")
    assert resumed["resume"] is True and resumed["session"] == started["session"]
    assert world.run("next", doc=resumed["doc"])["aspects_open"][0]["key"] == "entities"


def test_an_answer_on_disk_is_reported_at_resume(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.build(started, round_of(aspect_card("entities")))
    world.raw.write_bytes(b"a-entities: accept")
    world.run("wait", doc=started["doc"], raw_file=started["raw_file"])
    assert world.run("start", ticket_key="PROJ-1")["raw_pending"] is True


# The second provider.

def test_the_second_provider_slot_is_off(world):
    answer = world.run("second-provider", round_input=world.file("r.json", round_of()))
    assert answer == {"ok": True, "state": "off", "forks": []}


# The log.

def test_a_premise_row_is_written_once_and_updated(world):
    started = world.run("start", ticket_key="PROJ-1")
    for status in ("pending", "verified (src/orders.py:12)"):
        world.run("row", log=started["log"], kind="Premise", text=f"orders live in one table → {status}")
    text = (world.spec / "GRILL-LOG.md").read_text("utf-8")
    assert text.count("- Premise: orders live in one table") == 1 and "verified (src/orders.py:12)" in text
    assert text.index("## Requirements grill") < text.index("## Solution design") < text.index("- Premise:")


def test_a_row_of_another_kind_or_shape_is_refused(world):
    started = world.run("start", ticket_key="PROJ-1")
    assert world.run("row", expect=1, log=started["log"], kind="Ledger", text="x → pending")["error"]["code"] == "unknown-kind"
    assert world.run("row", expect=1, log=started["log"], kind="Premise", text="no arrow")["error"]["code"] == "bad-row"


def test_a_design_row_leaves_the_requirements_section_alone(world):
    log = world.spec / "GRILL-LOG.md"
    before = log.read_text("utf-8")
    started = world.run("start", ticket_key="PROJ-1")
    world.run("row", log=started["log"], kind="Premise", text="x → pending")
    after = log.read_text("utf-8")
    assert after.startswith(before)


# The gate.

def gate_failures(world, started, expect=1):
    answer = world.run("gate", expect=expect, doc=started["doc"], spec_dir=started["spec_dir"])
    return answer["error"]["failures"] if expect else answer


def test_the_gate_lists_every_failure_at_the_start(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.build(started, round_of(aspect_card("entities")))
    failures = gate_failures(world, started)
    joined = "\n".join(failures)
    assert "point a-entities is open" in joined
    assert "aspect keys has no card" in joined and "layer L9 has no card" in joined
    assert "no SDD.md" in joined


def test_the_gate_passes_a_whole_design_and_closes_the_session(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    assert world.run("next", doc=started["doc"])["phase"] == "write"
    world.write_design()
    answer = gate_failures(world, started, expect=0)
    assert answer["ok"] is True and answer["design_adrs"] == 1
    index = (world.spec / "INDEX.md").read_text("utf-8")
    assert "| SDD | SDD.md | draft |" in index and "| Design ADRs | adr/design/ | 1 records |" in index
    assert f"· session {started['session']}" in (world.spec / "GRILL-LOG.md").read_text("utf-8")
    again = world.run("start", ticket_key="PROJ-1")
    assert again["resume"] is False and again["session"] != started["session"] and again["sdd_exists"] is True


@pytest.mark.parametrize("old, new, expected", [
    ("## §9b External Seams & Failure Affordance", "## §9b Seams", "no section `## §9b External Seams & Failure Affordance`"),
    ("One module.", "TBD", "§8 L7 — Module Decomposition: blocker `TBD`"),
    ("| Which font does the report use? | L8 | yes |", "| Which store? | L3 | yes |", "open question blocks the executor"),
    ('| signed | owner / 2026-01-06 | "sign" (R-4) |', "| pending | — | — |", "HL-1: status is pending"),
    ('| signed | owner / 2026-01-06 | "sign" (R-4) |', "| signed | — | — |", "HL-1: signed needs who, date and the human's words"),
    ("| HL-2 API surface | §3 | n/a | owner / 2026-01-06 | no surface is added |\n", "", "HL-2: no row in the §0 register"),
])
def test_the_gate_refuses_a_bad_sdd(world, old, new, expected):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    text = (FIXTURES / "design" / "SDD.md").read_text("utf-8")
    assert old in text
    world.write_design(text.replace(old, new))
    assert any(expected in failure for failure in gate_failures(world, started))


def test_a_blocker_token_in_a_code_fence_is_no_blocker(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    text = (FIXTURES / "design" / "SDD.md").read_text("utf-8")
    world.write_design(text.replace("One module.", "One module.\n\n```text\nTBD\n```"))
    assert gate_failures(world, started, expect=0)["ok"] is True


def test_a_signed_row_needs_a_settled_card(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    text = (FIXTURES / "design" / "SDD.md").read_text("utf-8")
    world.write_design(text.replace("| HL-2 API surface | §3 | n/a | owner / 2026-01-06 | no surface is added |",
                                    '| HL-2 API surface | §3 | signed | owner / 2026-01-06 | "sign" |'))
    assert any("HL-2: signed, but no card holds its signature" in failure for failure in gate_failures(world, started))


def test_an_na_row_with_a_card_is_refused(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    text = (FIXTURES / "design" / "SDD.md").read_text("utf-8")
    world.write_design(text.replace('| HL-1 Persistence and entity design | §4 | signed | owner / 2026-01-06 | "sign" (R-4) |',
                                    "| HL-1 Persistence and entity design | §4 | n/a | owner / 2026-01-06 | no entity |"))
    assert any("HL-1: n/a, but a card asks it" in failure for failure in gate_failures(world, started))


def test_a_changes_mark_on_a_signoff_keeps_the_gate_closed_until_a_sign(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    sign = lambda item_id: {"id": item_id, "locked": "HL-2", "kind": "signoff",
                            "body": {"type": "text", "id": f"{item_id}-text", "props": {"text": "The API table is final."}}}
    world.build(started, round_of(sign("sign-hl-2")))
    world.answer(started, "sign-hl-2: changes")
    world.run("apply-readings", doc=started["doc"], readings=world.file(
        "readings.json", {"open": [{"item": "sign-hl-2", "reply": "The wording changes, so it returns."}]}))
    world.write_design()
    assert any("sign-hl-2" in failure for failure in gate_failures(world, started))
    world.build(started, round_of({**sign("sign-hl-2-b"), "carries": ["sign-hl-2"]}))
    assert world.run("next", doc=started["doc"])["locked_open"] == [{"key": "HL-2", "label": "API surface"}]


def test_a_pending_or_refuted_premise_keeps_the_gate_closed(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    world.write_design()
    world.run("row", log=started["log"], kind="Premise", text="orders live in one table → pending")
    world.run("row", log=started["log"], kind="Premise", text="exports are small → refuted (src/export.py:9)")
    failures = gate_failures(world, started)
    assert any("pending: orders live in one table" in failure for failure in failures)
    assert any("refuted: exports are small" in failure for failure in failures)


def test_a_settled_fork_with_no_record_keeps_the_gate_closed(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    world.write_design()
    adr = next((world.spec / "adr" / "design").glob("*.md"))
    adr.write_text(adr.read_text("utf-8").replace("> Forks: f-relations\n", ""), "utf-8")
    assert any("fork f-relations stands in no ADR and not in SDD.md" in failure for failure in gate_failures(world, started))


@pytest.mark.parametrize("old, new, expected", [
    ("> Status: Accepted\n", "", "no `> Status:` line"),
    ("## Decision\n", "## Choice\n", "no section `## Decision`"),
    ("## Alternatives Considered\n", "## Other\n", "no section `## Alternatives Considered`"),
    ("# ADR-0001 — ", "# ADR-0002 — ", "the title must start `# ADR-0001 — `"),
])
def test_the_gate_refuses_a_bad_adr(world, old, new, expected):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    world.write_design()
    adr = next((world.spec / "adr" / "design").glob("*.md"))
    adr.write_text(adr.read_text("utf-8").replace(old, new), "utf-8")
    assert any(expected in failure for failure in gate_failures(world, started))


def test_a_badly_named_adr_is_refused(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    world.write_design()
    adr = next((world.spec / "adr" / "design").glob("*.md"))
    adr.rename(adr.with_name("join-table.md"))
    assert any("join-table.md: the name must be `NNNN-<title>.md`" in failure for failure in gate_failures(world, started))


def test_a_missing_index_is_reported_and_blocks_nothing(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    world.write_design()
    (world.spec / "INDEX.md").unlink()
    answer = gate_failures(world, started, expect=0)
    assert answer["index_missing"] is True


def test_every_format_placeholder_would_fail_the_gate():
    template = design_files.sdd_template()
    assert design_files.blocker_problems(template), "a copy of the template with placeholders must not pass"


def test_the_template_is_the_home_of_the_section_list():
    headings = design_files.sdd_headings()
    assert headings[0] == "§0 Binding Contract" and "§9b External Seams & Failure Affordance" in headings
    assert headings[-1] == "§14 L9 — Implementation Seams & Change Impact"
    for layer, label in dr.group_rows("layer"):
        assert any(heading.endswith(f"{layer} — {label}") for heading in headings), layer


# The dry run: PRD fixture to round document to SDD.

def test_dry_run_first_round_has_the_picture_before_the_question_and_a_fork(world):
    started = world.run("start", ticket_key="PROJ-1")
    assert (world.repo / started["prd"]).read_text("utf-8").startswith("# PRD — order export")
    assert world.run("next", doc=started["doc"])["aspects_to_ask"][0]["key"] == "entities"
    content = json.loads((FIXTURES / "design" / "round-1.json").read_text("utf-8"))
    answer = world.build(started, content)
    assert answer["round"] == 1 and answer["items"] == ["a-entities", "f-relations"] and answer["degraded"] == []
    assert world.run("present", doc=started["doc"])["ok"] is True
    assert [line.split()[1] for line in world.calls.read_text("utf-8").splitlines()] == ["check", "render", "show"]
    doc = world.doc(started)
    assert doc["schema"] == "afkv2.page/0" and doc["session"]["skill"] == "propose-solution"
    assert Path(started["doc"]).name == f"propose-solution-{doc['session']['id']}.json"
    assert len(list((world.spec / "pages").glob("propose-solution-*.json"))) == 1
    first, fork = doc["rounds"][0]["items"]
    assert first["node"] == "aspect-entities" and first["body"]["type"] in {"table", "graph", "sequence", "run-strip", "map"}
    assert first["body"]["children"][0]["id"] == "a-entities-question"
    assert fork["kind"] == "debate" and fork["node"] == "aspect-relations"
    assert fork["body"]["type"] == "table" and fork["body"]["id"] == "f-relations-now"
    options = next(child for child in fork["body"]["children"] if child["id"] == "f-relations-options")
    assert options["props"]["columns"] == ["A — Join table", "B — Run id on the order"]


def test_dry_run_a_whole_session_through_every_stated_command(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.run("row", log=started["log"], kind="Premise", text="orders live in one table → verified (src/orders.py:12)")
    world.build(started, json.loads((FIXTURES / "design" / "round-1.json").read_text("utf-8")))
    world.run("present", doc=started["doc"])
    pending = world.answer(started, "a-entities: accept\nf-relations: option:a")
    assert pending["settled_by_mark"] == ["a-entities", "f-relations"]

    rest = [aspect_card(key) for key in CAT_A[2:]]
    world.build(started, round_of(*rest))
    world.run("present", doc=started["doc"])
    lines = [f"a-{key}: accept" for key in CAT_A[2:] if key not in ("keys", "cascade")]
    pending = world.answer(started, "\n".join([*lines, "a-keys: note: Keep the order id as the key.", "a-cascade: reopen"]))
    assert {card["id"] for card in pending["needs_reading"]} == {"a-keys", "a-cascade"}
    pending = world.run("apply-readings", doc=started["doc"], readings=world.file("readings.json", {
        "settle": [{"item": "a-keys", "note": "N-2-a-keys", "reading": "The order id stays the key."}],
        "open": [{"item": "a-cascade", "reply": "You reopened it, so it returns with a new reading."}]}))
    assert pending["settled_by_note"] == ["a-keys"] and pending["open"] == ["a-cascade"]

    assert world.run("next", doc=started["doc"])["phase"] == "aspects"
    stuck = world.run("build", expect=1, doc=started["doc"], session=started["session"], ticket_key=started["ticket"],
                      round_input=world.file("round.json", round_of(layer_card("L1"))))
    assert stuck["error"]["code"] == "aspects-first"
    world.build(started, round_of(aspect_card("cascade", "a-cascade-2", carries=["a-cascade"])))
    world.run("present", doc=started["doc"])
    world.answer(started, "a-cascade-2: accept")

    step = world.run("next", doc=started["doc"])
    assert step["phase"] == "draft" and step["aspects_open"] == [] and step["layers_to_ask"][0]["key"] == "L1"
    draft = round_of(*(layer_card(f"L{n}") for n in range(1, 10)),
                     {"id": "sign-hl-1", "locked": "HL-1", "kind": "signoff",
                      "body": {"type": "text", "id": "sign-hl-1-text", "props": {"text": "The field table is final."}}})
    assert world.run("second-provider", round_input=world.file("draft.json", draft))["forks"] == []
    world.build(started, draft)
    world.run("present", doc=started["doc"])
    world.accept_all(started)
    assert world.run("next", doc=started["doc"])["phase"] == "write"

    world.write_design()
    assert gate_failures(world, started, expect=0)["ok"] is True
    assert (world.spec / "SDD.md").exists() and list((world.spec / "adr" / "design").glob("0001-*.md"))
    doc = world.doc(started)
    assert nodes_of(doc, "m-aspects")["aspect-cascade"]["state"] == "settled"
    assert nodes_of(doc, "m-locked")["locked-hl-1"]["state"] == "focus"


def test_a_refused_round_is_corrected_with_replace(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.build(started, round_of(aspect_card("entities")))
    world.env["FAKE_ENGINE_REFUSE"] = "render"
    assert world.run("present", expect=1, doc=started["doc"])["error"]["verb"] == "render"
    del world.env["FAKE_ENGINE_REFUSE"]
    answer = world.run("build", swap=['--round-input', '--replace --round-input'], doc=started["doc"],
                       session=started["session"], ticket_key=started["ticket"],
                       round_input=world.file("round.json", round_of(aspect_card("entities", "a-entities-2"))))
    assert answer["round"] == 1 and answer["items"] == ["a-entities-2"]


@pytest.mark.skipif(not ENGINE.exists(), reason="page engine not merged yet; the fake engine checks")
def test_the_real_engine_accepts_the_round_document(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.build(started, json.loads((FIXTURES / "design" / "round-1.json").read_text("utf-8")))
    run = subprocess.run([sys.executable, str(ENGINE), "check", str(world.repo / started["doc"])],
                         capture_output=True, text=True, encoding="utf-8", cwd=world.repo)
    assert run.returncode == 0, run.stdout + run.stderr


# Placeholders and points that come back.

def test_a_placeholder_in_the_title_block_is_a_blocker():
    assert design_files.blocker_problems("# SDD — {Feature Name}\n\n> Last updated: 2026-01-06\n\n## §1 Context\n\nDone.\n")


@pytest.mark.parametrize("token", ["{who}", "{system}", "<NNNN>", "<service>", "ADR-NNNN", "<?>", "FILL_IN", "<TODO>"])
def test_every_template_placeholder_is_a_blocker(token):
    assert design_files.blocker_problems(f"## §1 Context\n\nDone {token} here.\n")


def test_an_api_path_with_a_brace_is_no_blocker():
    assert not design_files.blocker_problems("## §3 L2\n\nGET /orders/{id} answers one order.\n")


def test_a_note_on_a_settled_aspect_of_an_earlier_round_takes_it_out_of_settled(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.build(started, round_of(aspect_card("entities")))
    world.answer(started, "a-entities: accept")
    world.build(started, round_of(aspect_card("relations")))
    world.answer(started, "a-entities: note: one more entity\na-relations: accept")
    step = world.run("next", doc=started["doc"])
    assert [entry["key"] for entry in step["aspects_open"]] == ["entities"]
