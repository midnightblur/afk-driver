"""Tests for the section rules of a design page: catalog order, shape, caption, links (ADR-0001 design)."""

import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / "skills" / "propose-solution" / "scripts"))

import section_rules as sr  # noqa: E402
from grill_common import Refusal  # noqa: E402

ORDER = ["sec-system", "sec-crit-a", "sec-crit-b", "sec-l1", "sec-l2", "sec-l3", "sec-l4", "sec-l5", "sec-l6",
         "sec-l7", "sec-logic", "sec-l8", "sec-l9", "sec-patterns", "sec-performance"]


def text(words, label=None, fold=None, children=None):
    props = {"text": words, **({"label": label} if label else {})}
    return {"type": "text", "props": props, **({"fold": fold} if fold else {}),
            **({"children": children} if children else {})}


def chip(words, tone):
    return {"type": "chip", "props": {"text": words, "tone": tone}}


def picture(children=None, title=None, caption=True):
    kids = ([text("the boxes and what passes", label="What to see")] if caption else []) + (children or [])
    return {"type": "graph", "props": {"nodes": [], **({"title": title} if title else {})}, "children": kids}


def level_body(summary="one line", rest=None):
    return picture([text(summary, label="Summary"), *(rest or [text("detail", fold="Detail")])])


def section(sid, body=None, links=None, state="current"):
    links = ["sec-l1"] if links is None and sid.startswith("sec-crit-") else links
    return {"id": sid, "title": sid, "state": state, "changes": [], "body": body or default_body(sid),
            **({"links": links} if links is not None else {})}


def default_body(sid):
    if sid.startswith("sec-crit-"):
        return picture([chip("critical", "proposed")])
    if sid == "sec-patterns":
        return text("no pattern applied")
    if sid == "sec-performance":
        return text("the design reads 1 file of under 1 KB", label="No performance risk")
    if sid == "sec-system":
        return picture()
    return level_body()


def page(ids):
    return [section(sid) for sid in ids]


def codes(failures):
    return [failure.split(":")[0] for failure in failures]


# --- catalog and order key

def test_catalog_reads_the_one_table_of_draft_md():
    ids = [row["id"] for row in sr.catalog()]
    assert ids == ["sec-system", "sec-crit-<slug>", "sec-l1", "sec-l2", "sec-l3", "sec-l4", "sec-l5", "sec-l6",
                   "sec-l7", "sec-logic", "sec-l8", "sec-l9", "sec-patterns", "sec-performance"]
    assert {row["kind"] for row in sr.catalog()} == {"system", "critical", "level", "patterns", "performance"}


def test_order_key_sorts_ids_in_catalog_order():
    shuffled = list(reversed(ORDER))
    assert sorted(shuffled, key=sr.order_key) == ["sec-system", "sec-crit-b", "sec-crit-a", *ORDER[3:]]
    assert sr.order_key("sec-crit-a") == sr.order_key("sec-crit-zz")


@pytest.mark.parametrize("sid", ["sec-l10", "sec-crit-", "sec-crit-A", "sec-other", "section-l1"])
def test_order_key_refuses_an_id_the_catalog_does_not_name(sid):
    with pytest.raises(Refusal) as refusal:
        sr.order_key(sid)
    assert refusal.value.code == "section-unknown"


# --- order

def test_sections_in_catalog_order_pass():
    assert sr.check_sections(page(ORDER)) == []


def test_the_first_section_out_of_order_is_named():
    ids = ["sec-system", "sec-l2", "sec-l1", "sec-l4", "sec-l3"]
    failures = sr.check_sections(page(ids))
    assert codes(failures) == ["section-order"]
    assert "sec-l1" in failures[0]


def test_a_critical_section_after_a_level_section_is_out_of_order():
    failures = sr.check_sections(page(["sec-system", "sec-l1", "sec-crit-a"]))
    assert codes(failures) == ["section-order"] and "sec-crit-a" in failures[0]


def test_an_unknown_id_is_named():
    assert codes(sr.check_sections(page(["sec-system", "sec-extra"]))) == ["section-unknown"]


@pytest.mark.parametrize("state", ["removed", "merged"])
def test_a_removed_or_merged_section_is_not_checked(state):
    sections = page(["sec-system", "sec-l1"]) + [section("sec-crit-a", state=state)]
    assert sr.check_sections(sections) == []


# --- shape, caption, critical chip

def test_a_level_section_that_opens_with_text_has_the_wrong_shape():
    sections = [section("sec-l1", body=text("words", children=[text("one line", label="Summary")]))]
    assert codes(sr.check_sections(sections)) == ["section-shape"]


def test_a_summary_of_3_lines_has_the_wrong_shape():
    sections = [section("sec-l1", body=level_body("a\nb\nc"))]
    failures = sr.check_sections(sections)
    assert codes(failures) == ["section-shape"] and "summary" in failures[0]


def test_a_summary_of_2_lines_passes():
    assert sr.check_sections([section("sec-l1", body=level_body("a\nb"))]) == []


def test_detail_before_the_summary_has_the_wrong_shape():
    body = picture([text("detail", fold="Detail"), text("one line", label="Summary")])
    failures = sr.check_sections([section("sec-l1", body=body)])
    assert codes(failures) == ["section-shape"] and "summary" in failures[0].lower()


def test_a_level_section_with_no_summary_has_the_wrong_shape():
    sections = [section("sec-l1", body=picture([text("detail", fold="Detail")]))]
    assert codes(sr.check_sections(sections)) == ["section-shape"]


def test_detail_that_is_not_folded_has_the_wrong_shape():
    sections = [section("sec-l1", body=level_body(rest=[text("open detail")]))]
    failures = sr.check_sections(sections)
    assert codes(failures) == ["section-shape"] and "fold" in failures[0]


def test_a_picture_with_no_caption_and_no_title_is_named():
    sections = [section("sec-system", body=picture(caption=False))]
    assert codes(sr.check_sections(sections)) == ["section-caption"]


def test_a_picture_with_a_title_or_a_diagram_caption_passes():
    diagram = {"type": "diagram", "props": {"caption": "the flow", "text": "flowchart LR\n a-->b"}}
    sections = [section("sec-system", body=picture(caption=False, title="The system")),
                section("sec-l1", body={**diagram, "children": [text("one line", label="Summary")]})]
    assert sr.check_sections(sections) == []


def test_a_caption_of_more_than_1_line_is_named():
    long = {"type": "graph", "props": {"nodes": []}, "children": [text("a\nb\nc", label="What to see")]}
    failures = sr.check_sections([section("sec-system", body=long)])
    assert codes(failures) == ["section-caption"] and "1 line" in failures[0]


def test_draft_md_is_read_once_per_check(monkeypatch):
    reads = []
    real = Path.read_text

    def counting(self, *args, **kwargs):
        if self == sr.DRAFT:
            reads.append(1)
        return real(self, *args, **kwargs)

    sr._draft_text.cache_clear()
    monkeypatch.setattr(Path, "read_text", counting)
    sr.check_sections(page(ORDER))
    sr.check_sections(page(ORDER))
    assert len(reads) == 1


def test_a_nested_picture_with_no_caption_is_named():
    nested = picture(caption=False)
    sections = [section("sec-l1", body=level_body(rest=[text("detail", fold="Detail", children=[nested])]))]
    assert codes(sr.check_sections(sections)) == ["section-caption"]


@pytest.mark.parametrize("links", [[], ["sec-system"], ["sec-l3"]])
def test_a_critical_section_that_names_no_level_section_on_the_page_is_named(links):
    sections = [section("sec-crit-a", links=links), section("sec-l1")]
    failures = sr.check_sections(sections)
    assert codes(failures) == ["section-shape"] and "links" in failures[0]


def test_a_critical_section_with_no_critical_chip_is_named():
    sections = [section("sec-crit-a", body=picture()), section("sec-l1")]
    failures = sr.check_sections(sections)
    assert codes(failures) == ["section-shape"] and "critical" in failures[0]


# --- patterns and performance

PATTERN_COLUMNS = ["Name", "What it is", "Where", "Why here", "Quality goal", "Beat"]


def table(columns, rows):
    return {"type": "table", "props": {"columns": columns, "rows": rows},
            "children": [text("each row is 1 pattern", label="What to see")]}


def test_a_patterns_table_with_every_column_passes():
    body = table(PATTERN_COLUMNS, [["strategy", "one class per format", "export", "2 formats", "changeability",
                                    "an if per format"]])
    assert sr.check_sections([section("sec-patterns", body=body)]) == []


def test_a_patterns_table_missing_a_column_has_the_wrong_shape():
    body = table(PATTERN_COLUMNS[:-1], [["a", "b", "c", "d", "e"]])
    assert codes(sr.check_sections([section("sec-patterns", body=body)])) == ["section-shape"]


def performance(budget_tone="measured", parts=("PF-1", "PF-2", "PF-3", "PF-4")):
    def part(name):
        if name == "PF-4":
            return text("budgets", label=f"{name} Budgets",
                        children=[table(["Flow", "Target", "Basis"], [["build", "3 s", chip("measured", budget_tone)]])])
        return text("words", label=f"{name} part", children=[table(["Item"], [["x"]])])
    return text("performance", children=[part(name) for name in parts])


def test_a_performance_section_with_pf_1_to_pf_4_passes():
    assert sr.check_sections([section("sec-performance", body=performance())]) == []


def test_a_performance_section_missing_a_part_has_the_wrong_shape():
    body = performance(parts=("PF-1", "PF-2", "PF-4"))
    failures = sr.check_sections([section("sec-performance", body=body)])
    assert codes(failures) == ["section-shape"] and "PF-3" in failures[0]


def test_a_budget_row_with_no_basis_mark_has_the_wrong_shape():
    body = performance(budget_tone="new")
    failures = sr.check_sections([section("sec-performance", body=body)])
    assert codes(failures) == ["section-shape"] and "PF-4" in failures[0]


def test_a_pf_part_with_no_picture_has_the_wrong_shape():
    body = performance()
    body["children"][0]["children"] = []
    failures = sr.check_sections([section("sec-performance", body=body)])
    assert codes(failures) == ["section-shape"] and "PF-1" in failures[0]


def test_a_pf_4_part_with_no_budget_table_has_the_wrong_shape():
    body = performance()
    body["children"][3]["children"] = [picture()]
    failures = sr.check_sections([section("sec-performance", body=body)])
    assert codes(failures) == ["section-shape"] and "no budget table" in failures[0]


def test_a_no_risk_line_with_a_child_has_the_wrong_shape():
    body = text("one line", label="No performance risk", children=[text("more")])
    assert codes(sr.check_sections([section("sec-performance", body=body)])) == ["section-shape"]


def test_a_no_risk_line_of_2_lines_has_the_wrong_shape():
    body = text("a\nb", label="No performance risk")
    assert codes(sr.check_sections([section("sec-performance", body=body)])) == ["section-shape"]


# --- links

def test_fill_links_links_each_level_to_the_next_and_to_its_critical_sections():
    sections = page(["sec-system", "sec-crit-a", "sec-l1", "sec-l3", "sec-logic", "sec-l9", "sec-patterns"])
    sections[1]["links"] = ["sec-l3"]
    sections[2]["links"] = ["sec-system"]
    assert sr.check_sections(sections) == []
    filled = {entry["id"]: entry.get("links") for entry in sr.fill_links(sections)}
    assert filled["sec-l1"] == ["sec-system", "sec-l3"]
    assert filled["sec-l3"] == ["sec-logic", "sec-crit-a"]
    assert filled["sec-logic"] == ["sec-l9"]
    assert filled["sec-l9"] is None
    assert filled["sec-patterns"] is None and filled["sec-system"] is None
    assert sections[2]["links"] == ["sec-system"], "fill_links changes a copy"


def test_fill_links_adds_no_link_twice_and_skips_removed_sections():
    sections = page(["sec-l1", "sec-l2", "sec-l3"])
    sections[0]["links"] = ["sec-l2"]
    sections[1]["state"] = "removed"
    filled = {entry["id"]: entry.get("links") for entry in sr.fill_links(sections)}
    assert filled["sec-l1"] == ["sec-l2", "sec-l3"]


def test_fill_links_drops_the_old_next_level_link_when_a_section_comes_between():
    sections = page(["sec-l7", "sec-logic", "sec-l8"])
    sections[0]["links"] = ["sec-l8", "sec-system"]
    filled = {entry["id"]: entry.get("links") for entry in sr.fill_links(sections)}
    assert filled["sec-l7"] == ["sec-system", "sec-logic"]
