"""Tests for the design build on a page format 2 document: sections, decisions, banner, ticket card, fork credits.

Each build runs in process against the real page engine (SDD §3 row S-1).
"""

import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / "skills" / "propose-solution" / "scripts"))

import design_round as dr  # noqa: E402
import page_round  # noqa: E402
import round_document as rd  # noqa: E402
from grill_common import Refusal  # noqa: E402

SESSION = {"id": "s-1", "skill": "propose-solution", "feature": "PROJ-1", "ticket": "PROJ-1"}


def text(words, label=None, fold=None, children=None):
    props = {"text": words, **({"label": label} if label else {})}
    return {"type": "text", "props": props, **({"fold": fold} if fold else {}),
            **({"children": children} if children else {})}


def picture(children=()):
    return {"type": "graph", "props": {"nodes": [{"id": "n1", "label": "A"}]},
            "children": [text("what passes", label="What to see"), *children]}


def level_body():
    return picture([text("the summary", label="Summary"), text("detail", fold="Detail")])


def critical_body():
    return picture([{"type": "chip", "props": {"text": "critical", "tone": "proposed"}}])


def section(sid, body=None, **extra):
    return {"id": sid, "title": sid, "state": "current", "body": body or level_body(),
            "change": {"cause": "finding", "text": "drafted"}} | extra


def confirm(item_id):
    return {"id": item_id, "kind": "confirm", "body": text("A reading.") | {"id": f"{item_id}-text"}}


def round_of(*items, **extra):
    return {"banner": {"settled": [], "unlocks": [], "parked": []}, "items": list(items), **extra}


def doc_path(tmp_path):
    path = tmp_path / "PROJ-1" / "pages" / "s-1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def answer_current_round(path):
    """Accept every card of the current round, unless the round holds an answer already."""
    current = rd.current_round(rd.read_json(path))
    if not current.get("responses"):
        raw = path.with_name("raw.txt")
        lines = [f"{item['id']} accept" for item in current["items"] if item["kind"] != "info"]
        raw.write_text("\n".join([f"[round R-{current['n']}]", *lines]), "utf-8")
        page_round.ingest(path, raw)


def build(tmp_path, round_input, **kwargs):
    """Build the next round; answer the round before it first. A round with no card gets 1 confirm card."""
    path = doc_path(tmp_path)
    if path.exists():
        answer_current_round(path)
    if not round_input.get("items"):
        n = len(rd.read_json(path)["rounds"]) + 1 if path.exists() else 1
        round_input = {**round_input, "items": [confirm(f"c-{n}")]}
    return dr.build_design_round(path, SESSION, round_input, **kwargs)


def stored(tmp_path):
    return json.loads(doc_path(tmp_path).read_text("utf-8"))


def refused(tmp_path, round_input, **kwargs):
    with pytest.raises(Refusal) as refusal:
        build(tmp_path, round_input, **kwargs)
    return refusal.value


# --- sections: order, shape, links (SDD §6 I-1, I-2; PRD AC-005, AC-006)

def test_a_section_out_of_catalog_order_is_refused_before_any_write(tmp_path):
    refusal = refused(tmp_path, round_of(sections=[section("sec-l2"), section("sec-l1")]))
    assert refusal.code == "section-order" and "sec-l1" in refusal.reason
    assert not doc_path(tmp_path).exists()


def test_a_level_section_without_its_summary_is_refused(tmp_path):
    refusal = refused(tmp_path, round_of(sections=[section("sec-l1", picture())]))
    assert refusal.code == "section-shape"
    assert not doc_path(tmp_path).exists()


def test_a_section_placed_with_after_is_checked_in_its_merged_place(tmp_path):
    build(tmp_path, round_of(sections=[section("sec-l1"), section("sec-l3")]))
    refusal = refused(tmp_path, round_of(sections=[section("sec-l4", after="sec-l1")]))
    assert refusal.code == "section-order"
    answer = build(tmp_path, round_of(sections=[section("sec-l2", after="sec-l1")]))
    assert answer["section_order"] == ["sec-l1", "sec-l2", "sec-l3"]


def as_version_1(tmp_path):
    doc = stored(tmp_path)
    doc["schema"] = "afkv2.page/1"
    doc_path(tmp_path).write_text(json.dumps(doc), "utf-8")


def test_a_version_1_page_refuses_sections_before_the_section_rules_run(tmp_path):
    build(tmp_path, round_of())
    as_version_1(tmp_path)
    refusal = refused(tmp_path, round_of(sections=[section("sec-l2"), section("sec-l1")]))
    assert refusal.code == "bad-round" and "version 2" in refusal.reason


def test_a_version_1_page_that_upgrades_runs_the_section_rules(tmp_path):
    build(tmp_path, round_of())
    as_version_1(tmp_path)
    refusal = refused(tmp_path, round_of(sections=[section("sec-l2"), section("sec-l1")], upgrade=True))
    assert refusal.code == "section-order"


def test_a_built_page_links_each_level_to_the_next_level_and_its_critical_sections(tmp_path):
    build(tmp_path, round_of(sections=[section("sec-crit-keys", critical_body(), links=["sec-l3"]),
                                       section("sec-l1"), section("sec-l3")]))
    links = {entry["id"]: entry.get("links") for entry in stored(tmp_path)["sections"]}
    assert links["sec-l1"] == ["sec-l3"]
    assert links["sec-l3"] == ["sec-crit-keys"]
    assert links["sec-crit-keys"] == ["sec-l3"]


def test_a_stored_level_section_gets_the_link_to_a_later_level_with_a_change_line(tmp_path):
    build(tmp_path, round_of(sections=[section("sec-l1")]))
    build(tmp_path, round_of(sections=[section("sec-l2")]))
    level = next(entry for entry in stored(tmp_path)["sections"] if entry["id"] == "sec-l1")
    assert level["links"] == ["sec-l2"]
    assert [line["round"] for line in level["changes"]] == [1, 2]


# --- decided cards: driven_by, typed alternatives, hover tips (SDD §6 I-3; PRD AC-009, AC-010; ADR-0004 design)

PRD = """# PRD

## Acceptance Criteria

- [ ] AC-009 Every decision on the page shows the 5 blocks.
- [ ] AC-010 Every requirement named in a D-2 block shows its text on hover.

## Catalog

| P-01 | One table per entity |
"""


def decided(item_id, **changes):
    fields = {"decision": "Keep one table.", "driven_by": ["AC-009", "ADR-0001", "P-01"],
              "alternatives": [{"option": "Two tables", "why_lost": "a join on every read"}],
              "evidence": "src/orders.py:12", "grade": "repo", "why": "fewer reads", "reverse": "split the table"}
    fields.update(changes)
    return {"id": item_id, "kind": "decided", "decided": {k: v for k, v in fields.items() if v is not None}}


def write_spec(tmp_path):
    spec = tmp_path / "PROJ-1"
    (spec / "adr" / "requirements").mkdir(parents=True, exist_ok=True)
    (spec / "PRD.md").write_text(PRD, "utf-8")
    (spec / "adr" / "requirements" / "0001-one-table.md").write_text("# Orders stay in one table\n\nBody.\n", "utf-8")


def card(tmp_path, item_id):
    return next(item for rnd in stored(tmp_path)["rounds"] for item in rnd["items"] if item["id"] == item_id)


def test_a_whole_decided_card_stays_decided_with_each_alternative_as_one_line(tmp_path):
    answer = build(tmp_path, round_of(decided("d-1")))
    assert answer["degraded"] == []
    item = card(tmp_path, "d-1")
    assert item["kind"] == "decided"
    parts = {c["props"].get("label"): c["props"]["text"] for c in [item["body"], *item["body"]["children"]]}
    assert parts["Driven by"] == "AC-009, ADR-0001, P-01"
    assert parts["Other options considered (rejected)"] == "- Two tables — a join on every read"


@pytest.mark.parametrize("changes", [{"driven_by": None}, {"driven_by": []},
                                     {"alternatives": [{"option": "Two tables"}]},
                                     {"alternatives": [{"option": "", "why_lost": "slow"}]},
                                     {"alternatives": ["Two tables lose"]}])
def test_a_decided_card_missing_a_block_degrades_to_confirm(tmp_path, changes):
    answer = build(tmp_path, round_of(decided("d-1", **changes)))
    assert answer["degraded"] == ["d-1"]
    item = card(tmp_path, "d-1")
    assert item["kind"] == "confirm"
    parts = {c["props"].get("label"): c["props"]["text"] for c in [item["body"], *item["body"]["children"]]}
    assert parts["Decision"] == "Keep one table."
    if changes.get("driven_by", True):
        assert parts["Driven by"] == "AC-009, ADR-0001, P-01"


def _block(doc, block_id):
    found = []

    def walk(component):
        if isinstance(component, dict):
            if component.get("id") == block_id:
                found.append(component)
            for child in component.get("children") or []:
                walk(child)
    for rnd in doc["rounds"]:
        for item in rnd["items"]:
            walk(item.get("body"))
    return found[0] if found else None


def test_each_driven_by_id_of_the_prd_or_a_record_gets_its_text_on_hover(tmp_path):
    write_spec(tmp_path)
    build(tmp_path, round_of(decided("d-1"), tips={"terms": [{"term": "run", "definition": "1 export."}]}))
    doc = stored(tmp_path)
    assert doc["tips"] == {"terms": [{"term": "run", "definition": "1 export."}]}
    assert _block(doc, "d-1-driven-by")["tip"] == ("AC-009: Every decision on the page shows the 5 blocks.\n"
                                                    "ADR-0001: Orders stay in one table")


def test_a_later_round_keeps_the_driven_by_tip_of_an_earlier_card(tmp_path):
    write_spec(tmp_path)
    build(tmp_path, round_of(decided("d-1")))
    build(tmp_path, round_of(confirm("c-2"), tips={"terms": [{"term": "run", "definition": "1 export."}]}))
    assert _block(stored(tmp_path), "d-1-driven-by")["tip"].startswith("AC-009: ")


def test_a_long_driven_by_text_is_cut_to_the_schema_cap(tmp_path):
    write_spec(tmp_path)
    item = decided("d-1")
    item["decided"]["driven_by"] = ["AC-009", "ADR-0001"] * 20
    build(tmp_path, round_of(item))
    tip = _block(stored(tmp_path), "d-1-driven-by")["tip"]
    assert len(tip) == 300 and tip.endswith("\u2026")


def test_a_confirm_card_that_carries_decided_fields_gets_no_driven_by_tip(tmp_path):
    write_spec(tmp_path)
    item = {**confirm("c-1"), "decided": {"driven_by": ["AC-009"]}}
    assert build(tmp_path, round_of(item))["ok"] is True
    assert "ids" not in (stored(tmp_path).get("tips") or {})
    assert _block(stored(tmp_path), "c-1-driven-by") is None or "tip" not in _block(stored(tmp_path), "c-1-driven-by")


@pytest.mark.parametrize("tips", [None, "x", ["a"]])
def test_tips_that_are_not_an_object_are_refused(tmp_path, tips):
    assert refused(tmp_path, round_of(confirm("c-1"), tips=tips)).code == "bad-round"
    assert not doc_path(tmp_path).exists()


def test_a_replaced_round_drops_the_driven_by_tip_of_its_card(tmp_path):
    write_spec(tmp_path)
    build(tmp_path, round_of(decided("d-1")))
    dr.build_design_round(doc_path(tmp_path), SESSION, round_of(confirm("c-1")), replace=True)
    assert [item["id"] for item in stored(tmp_path)["rounds"][-1]["items"]] == ["c-1"]
    assert "ids" not in (stored(tmp_path).get("tips") or {})


def test_a_card_whose_ids_are_page_or_catalog_ids_gets_no_tip(tmp_path):
    write_spec(tmp_path)
    build(tmp_path, round_of(confirm("c-1")))
    build(tmp_path, round_of(decided("d-1", driven_by=["c-1", "P-01"])))
    assert "ids" not in (stored(tmp_path).get("tips") or {})


def test_a_driven_by_id_that_names_nothing_is_refused_before_any_write(tmp_path):
    write_spec(tmp_path)
    build(tmp_path, round_of(confirm("c-1")))
    answer_current_round(doc_path(tmp_path))
    before = doc_path(tmp_path).read_text("utf-8")
    refusal = refused(tmp_path, round_of(decided("d-1", driven_by=["AC-009", "AC-999"])))
    assert refusal.code == "driven-by-unknown" and "AC-999" in refusal.reason and "AC-009" not in refusal.reason
    assert doc_path(tmp_path).read_text("utf-8") == before


def test_a_page_with_no_prd_beside_it_checks_no_driven_by_id(tmp_path):
    assert build(tmp_path, round_of(decided("d-1", driven_by=["AC-999"])))["ok"] is True


# --- the ticket card (PRD AC-036)

TICKET = {"key": "PROJ-1", "title": "Export runs", "description": "Export each run.",
          "links": [{"key": "PROJ-2", "title": "Import runs", "status": "Open"}]}


def test_ticket_file_adds_the_ticket_card_to_round_one(tmp_path):
    path = doc_path(tmp_path)
    ticket_file = tmp_path / "ticket.json"
    ticket_file.write_text(json.dumps(TICKET), "utf-8")
    round_file = tmp_path / "round.json"
    round_file.write_text(json.dumps(round_of(confirm("c-1"))), "utf-8")
    answer = dr.main(["build", "--doc", str(path), "--session", "s-1", "--ticket", "PROJ-1",
                      "--round-input", str(round_file), "--ticket-file", str(ticket_file)])
    assert answer["items"] == ["c-1"]
    items = stored(tmp_path)["rounds"][0]["items"]
    assert [item["id"] for item in items] == ["i-ticket", "c-1"]
    assert "PROJ-2" in json.dumps(items[0])


def test_a_later_round_gets_no_ticket_card(tmp_path):
    build(tmp_path, round_of(confirm("c-1")), ticket=TICKET)
    build(tmp_path, round_of(confirm("c-2")), ticket=TICKET)
    assert [item["id"] for item in stored(tmp_path)["rounds"][1]["items"]] == ["c-2"]


# --- the proposers banner (PRD AC-021, AC-024, R-5; SDD §5)

FENCE = ("Each solution proposer ran with full auto-approval in a throwaway worktree. "
         "The worktree fences only the working folder; it is not a sandbox.")


def banner(tmp_path):
    return stored(tmp_path)["rounds"][-1]["banner"]


def test_two_proposers_write_one_line_and_the_fence(tmp_path):
    build(tmp_path, round_of(proposers={"count": 2, "tools": ["claude", "codex"], "reason": None}))
    assert banner(tmp_path)["settled"] == ["2 solution proposers drafted the design: Claude and Codex.", FENCE]


@pytest.mark.parametrize("reason, words", [("no-herdr", "herdr is not installed"),
                                           ("outside-herdr", "the session runs outside herdr"),
                                           ("no-other-tool", "the other tool is not installed"),
                                           ("bypass-forbidden", "full auto-approval is forbidden")])
def test_one_proposer_writes_one_line_with_the_reason_and_no_fence(tmp_path, reason, words):
    build(tmp_path, round_of(proposers={"count": 1, "tools": ["claude"], "reason": reason}))
    assert banner(tmp_path)["settled"] == [f"1 solution proposer drafted the design alone (Claude): {words}."]


def test_a_failed_proposer_writes_the_reason_and_the_fence(tmp_path):
    build(tmp_path, round_of(proposers={"count": 1, "tools": ["claude"], "reason": dr.PROPOSER_FAILED}))
    assert banner(tmp_path)["settled"] == [
        "1 solution proposer drafted the design alone (Claude): a solution proposer failed before the drafts and "
        "critiques were done.", FENCE]


def test_the_banner_line_comes_before_the_lines_of_the_agent(tmp_path):
    round_input = round_of(proposers={"count": 1, "tools": ["codex"], "reason": "no-herdr"})
    round_input["banner"]["settled"] = ["Keys settled."]
    build(tmp_path, round_input)
    assert banner(tmp_path)["settled"][1:] == ["Keys settled."]
    assert "proposers" not in json.dumps(stored(tmp_path)["rounds"])


@pytest.mark.parametrize("proposers", [{"count": 3, "tools": ["a", "b", "c"], "reason": None},
                                       {"count": 2, "tools": ["claude"], "reason": None},
                                       {"count": 2, "tools": ["claude", "claude"], "reason": None},
                                       {"count": 2, "tools": ["claude", "codex"], "reason": "no-herdr"},
                                       {"count": 1, "tools": ["claude"], "reason": None},
                                       {"count": 1, "tools": ["claude"], "reason": "tired"},
                                       {"count": 1, "tools": ["claude"], "reason": "no-herdr", "extra": 1},
                                       {"count": True, "tools": ["claude"], "reason": "no-herdr"},
                                       "two"])
def test_a_bad_proposers_input_is_refused(tmp_path, proposers):
    assert refused(tmp_path, round_of(confirm("c-1"), proposers=proposers)).code == "bad-proposers"
    assert not doc_path(tmp_path).exists()


# --- no estimate (PRD AC-042, SDD §6 I-7)

def test_a_design_page_holds_no_estimate_field(tmp_path):
    build(tmp_path, round_of(decided("d-1"), estimate={"hours": 3}))
    assert '"estimate"' not in doc_path(tmp_path).read_text("utf-8")


# --- fork credits (PRD AC-022; SDD §14 row "fork cards")

import fork_cards  # noqa: E402


def fork_item(*options):
    return {"id": "f-1", "fork": {"question": "Which store?", "why_open": "2 live options.", "options": list(options)}}


def option_table(item):
    return next(c for c in item["body"]["children"] if c["type"] == "table")


def test_a_fork_option_with_by_shows_the_tool_credit(tmp_path):
    build(tmp_path, round_of(fork_item({"name": "One table", "text": "Fewer reads.", "by": "claude"},
                                       {"name": "Two tables", "text": "Smaller rows.", "by": "codex"})))
    rows = option_table(card(tmp_path, "f-1"))["props"]["rows"]
    assert [cell["id"] for cell in rows[0]] == ["f-1-opt-a", "f-1-opt-b"]
    assert [(cell["type"], cell["props"]["text"]) for cell in rows[1]] == [("chip", "Claude proposes"),
                                                                        ("chip", "Codex proposes")]


def test_an_option_without_by_gets_an_empty_credit_cell(tmp_path):
    item = fork_cards.expand_fork(fork_item({"name": "One table", "text": "Fewer reads.", "by": "codex"},
                                            {"name": "Two tables", "text": "Smaller rows."}))
    assert option_table(item)["props"]["rows"][1][1] == ""


def test_a_fork_with_no_credit_keeps_one_row(tmp_path):
    item = fork_cards.expand_fork(fork_item({"name": "One table", "text": "Fewer reads."},
                                            {"name": "Two tables", "text": "Smaller rows."}))
    assert len(option_table(item)["props"]["rows"]) == 1


@pytest.mark.parametrize("by", ["", 3, None])
def test_a_bad_credit_is_refused(by):
    with pytest.raises(Refusal) as refusal:
        fork_cards.expand_fork(fork_item({"name": "One table", "text": "Fewer reads.", "by": by},
                                         {"name": "Two tables", "text": "Smaller rows."}))
    assert refusal.value.code == "bad-fork"


# --- the proposers phase and open resources (PRD AC-018, AC-026; SDD §3 row S-1, §6 I-6)

def aspect(key):
    body = {"type": "table", "id": f"a-{key}-now", "props": {"columns": ["Entity"], "rows": [["order"]]},
            "children": [text("The reading.") | {"id": f"a-{key}-question"}]}
    return {"id": f"a-{key}", "aspect": key, "kind": "confirm", "body": body}


def layer(key):
    return {"id": f"l-{key.lower()}", "layer": key, "kind": "confirm", "body": text("Inherited.") | {"id": f"l-{key.lower()}-text"}}


def settle_aspects(tmp_path):
    build(tmp_path, round_of(*(aspect(key) for key in dr.group_keys("aspect"))))
    answer_current_round(doc_path(tmp_path))


def write_state(tmp_path, **state):
    path = doc_path(tmp_path).with_suffix(".proposers.json")
    path.write_text(json.dumps({"version": 1, **state}), "utf-8")


def phase(tmp_path):
    return dr.main(["next", "--doc", str(doc_path(tmp_path))])["phase"]


def test_next_answers_proposers_between_aspects_and_draft(tmp_path):
    assert dr.PROPOSERS_PHASE == "proposers"
    build(tmp_path, round_of(*(aspect(key) for key in dr.group_keys("aspect"))))
    assert phase(tmp_path) == "aspects"
    answer_current_round(doc_path(tmp_path))
    assert phase(tmp_path) == "proposers"


def test_a_draft_round_with_no_state_file_is_refused_and_writes_nothing(tmp_path):
    settle_aspects(tmp_path)
    before = doc_path(tmp_path).read_text("utf-8")
    refusal = refused(tmp_path, round_of(layer("L1")))
    assert refusal.code == "proposers-first"
    assert doc_path(tmp_path).read_text("utf-8") == before


def test_a_draft_round_is_refused_while_2_proposers_are_not_cleaned_up(tmp_path):
    settle_aspects(tmp_path)
    write_state(tmp_path, count=2, proposers=[{"tool": "codex", "pane": None, "worktree": None}], cleaned=False)
    assert refused(tmp_path, round_of(layer("L1"))).code == "proposers-first"


def test_a_later_draft_round_needs_no_state_file(tmp_path):
    settle_aspects(tmp_path)
    write_state(tmp_path, count=1, proposers=[], cleaned=False)
    build(tmp_path, round_of(layer("L1")))
    doc_path(tmp_path).with_suffix(".proposers.json").unlink()
    assert build(tmp_path, round_of(layer("L2")))["ok"] is True


def test_a_state_file_with_count_one_moves_on_to_the_draft(tmp_path):
    settle_aspects(tmp_path)
    write_state(tmp_path, count=1, proposers=[], cleaned=False)
    assert phase(tmp_path) == "draft"


def test_two_proposers_hold_the_phase_until_cleanup_is_done(tmp_path):
    settle_aspects(tmp_path)
    write_state(tmp_path, count=2, proposers=[{"tool": "claude", "pane": "p-1", "worktree": "w-1"}], cleaned=False)
    assert phase(tmp_path) == "proposers"
    write_state(tmp_path, count=2, proposers=[{"tool": "claude", "pane": None, "worktree": None}], cleaned=True)
    assert phase(tmp_path) == "draft"


def test_a_draft_round_is_refused_while_a_pane_or_worktree_is_recorded(tmp_path):
    settle_aspects(tmp_path)
    before = doc_path(tmp_path).read_text("utf-8")
    write_state(tmp_path, count=2, proposers=[{"tool": "codex", "pane": None, "worktree": "w-2"}], cleaned=False)
    refusal = refused(tmp_path, round_of(layer("L1")))
    assert refusal.code == "proposers-open" and "w-2" in refusal.reason
    assert doc_path(tmp_path).read_text("utf-8") == before
    write_state(tmp_path, count=2, proposers=[{"tool": "codex", "pane": None, "worktree": None}], cleaned=True)
    assert build(tmp_path, round_of(layer("L1")))["ok"] is True
    assert phase(tmp_path) == "draft"


def test_an_unreadable_state_file_is_refused(tmp_path):
    settle_aspects(tmp_path)
    doc_path(tmp_path).with_suffix(".proposers.json").write_text('{"version": 9}', "utf-8")
    with pytest.raises(Refusal) as refusal:
        phase(tmp_path)
    assert refusal.value.code == "bad-proposers-state"


@pytest.mark.parametrize("state", [{"count": True, "proposers": [], "cleaned": False},
                                   {"count": 2, "proposers": ["claude"], "cleaned": False},
                                   {"count": 2, "proposers": [], "cleaned": "yes"},
                                   {"count": 2, "proposers": [{"tool": "claude", "pane": "p-1", "worktree": None}],
                                    "cleaned": True},
                                   {"count": 2, "proposers": [{"tool": "claude", "pane": None, "worktree": "w-1"}],
                                    "cleaned": True}])
def test_a_state_file_of_the_wrong_shape_is_refused(tmp_path, state):
    settle_aspects(tmp_path)
    write_state(tmp_path, **state)
    with pytest.raises(Refusal) as refusal:
        phase(tmp_path)
    assert refusal.value.code == "bad-proposers-state"


def test_a_late_section_moves_the_next_level_link_and_the_change_line_names_titles(tmp_path):
    build(tmp_path, round_of(sections=[section("sec-l7", title="L7 Modules"), section("sec-l8", title="L8 Patterns")]))
    build(tmp_path, round_of(sections=[section("sec-logic", title="Key logic", after="sec-l7")]))
    level = next(entry for entry in stored(tmp_path)["sections"] if entry["id"] == "sec-l7")
    titles = {entry["id"]: entry["title"] for entry in stored(tmp_path)["sections"]}
    assert level["links"] == ["sec-logic"]
    text = level["changes"][-1]["text"]
    assert text == f"The design build now links {titles['sec-logic']} and no longer links {titles['sec-l8']}."
    assert "sec-" not in text


def test_the_design_build_passes_ticket_projects_to_the_links_and_not_to_the_document(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(dr, "links_for", lambda keys, earlier, extra, titles: seen.update(extra=extra, titles=titles) or None)
    monkeypatch.setattr(dr, "build_design_round", lambda doc, session, round_input, *rest: seen.update(sent=round_input))
    round_input = tmp_path / "round.json"
    round_input.write_text(json.dumps({"banner": {}, "items": [], "ticket_projects": ["OPS"], "ticket_titles": {"OPS-1": "A title"}}), "utf-8")
    dr.main(["build", "--doc", str(tmp_path / "pages" / "propose-solution-s-1.json"), "--session", "s-1",
             "--ticket", "PROJ-1", "--round-input", str(round_input)])
    assert seen["extra"] == ["OPS"] and "ticket_projects" not in seen["sent"]
    assert seen["titles"] == {"OPS-1": "A title"} and "ticket_titles" not in seen["sent"]


def test_a_fork_refuses_a_second_recommendation_field():
    raw = {**fork_item({"name": "One table", "text": "Fewer reads."}, {"name": "Two tables", "text": "Smaller rows."}),
           "recommend": {"option": "a", "why": "Fewer reads."}}
    with pytest.raises(Refusal) as refusal:
        fork_cards.expand_fork(raw)
    assert refusal.value.code == "bad-fork"
