"""Code names in code font (note of round 7 on a table row): a table cell given as a plain string takes the
inline marks of a `markdown: true` text, and a file reference (`Name.java:157`, `path/file.py:12-34`) or a
snake_case id outside a code span shows in code font with no mark at all. A prose word never does."""

import sys
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[2] / "engine"
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(ENGINE_DIR.parent / "scripts"))

import registry  # noqa: E402

registry.load_components()

HIGHLIGHT = '<mark class="afkv2-md-mark">{}</mark>'


def table(*cells):
    return registry.render_component({"type": "table", "props": {"columns": ["c"] * len(cells), "rows": [list(cells)]}})


def md(text):
    return registry.render_component({"type": "text", "props": {"text": text, "markdown": True}})


@pytest.mark.parametrize("cell, code", [
    ("kapteyn-jobs BaseScheduleJobService.java:157", "BaseScheduleJobService.java:157"),
    ("BaseScheduleJobService.java:160-162, 191-203", "BaseScheduleJobService.java:160-162, 191-203"),
    ("BaseScheduleJobService.java:66-70, 116-128; NFS descriptor nfs_sadmin", "BaseScheduleJobService.java:66-70, 116-128"),
    ("see src/main/java/a/Job.java", "src/main/java/a/Job.java"),
    ("the gate in scripts/plugin_check.py:12", "scripts/plugin_check.py:12"),
])
def test_a_file_reference_in_a_plain_cell_shows_in_code_font(cell, code):
    assert f"<code>{code}</code>" in table(cell)


def test_the_reported_row_renders_each_code_name_in_code_font():
    html = table("At a fire, the owner's data scope", "checked; a failure disables the schedule",
                 "BaseScheduleJobService.java:66-70, 116-128; NFS descriptor nfs_sadmin")
    assert "<code>nfs_sadmin</code>" in html and "<code>BaseScheduleJobService.java:66-70, 116-128</code>" in html
    assert "<code>At" not in html and "owner&#x27;s data scope" in html


def test_a_line_list_stops_before_a_prose_number():
    assert "<code>Foo.java:157</code>, 2 callers" in table("Foo.java:157, 2 callers")


@pytest.mark.parametrize("cell", ["Approver reworks; job 2 resubmits", "e.g. a closed period", "i.e. none",
                                  "example.com and v1.2", "JavaScript and GitLab", "kapteyn-jobs", "3.5 days",
                                  "a * b * c", "the end."])
def test_a_prose_cell_takes_no_code_font(cell):
    assert "<code>" not in table(cell)


def test_a_plain_cell_takes_the_marks_of_a_markdown_text():
    html = table("Approver reworks (`inv_rework`); clerk **resubmits by hand**", "*inferred* ==new==")
    assert "<code>inv_rework</code>" in html and "<strong>resubmits by hand</strong>" in html
    assert "<em>inferred</em>" in html and HIGHLIGHT.format("new") in html


def test_a_plain_cell_is_escaped_first():
    html = table("<script>x</script> & Foo.java")
    assert "<script>" not in html and "&lt;script&gt;x&lt;/script&gt; &amp; <code>Foo.java</code>" in html


def test_a_cell_names_no_code_inside_a_link_or_a_code_span():
    html = table("https://x.example/a/Job.java and `snake_case.py:1`")
    assert 'href="https://x.example/a/Job.java"' in html and "<code>Job.java</code>" not in html
    assert html.count("<code>") == 1 and "<code>snake_case.py:1</code>" in html


def test_a_markdown_text_shows_a_code_name_in_code_font():
    html = md("Transitions in PayableTransition.java:30-57 and status inv_rework.")
    assert "<code>PayableTransition.java:30-57</code>" in html and "<code>inv_rework</code>" in html


def test_a_plain_text_stays_plain():
    html = registry.render_component({"type": "text", "props": {"text": "Foo.java:1 and `x`"}})
    assert "<p>Foo.java:1 and `x`</p>" in html
