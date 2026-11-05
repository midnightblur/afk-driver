"""Code blocks and diffs (PRD AC-029, AC-030; ADR-0003 design; SDD §9b row "Code highlighter", §10 row "Page weight"):
the engine marks each block with its language, and a copy of highlight.js 11.12.0 colours it in the browser. The
library and its 2 themes are inlined once, only on a page with code or a diff. A browser check proves the colours."""

import hashlib
import re
import sys
from html import unescape
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
for folder in (PLUGIN / "scripts", ENGINE_DIR):
    sys.path.insert(0, str(folder))

import registry  # noqa: E402
from shell import page  # noqa: E402

HIGHLIGHT = ENGINE_DIR / "shell" / "highlight"
BUNDLE = HIGHLIGHT / "highlight.min.js"
# The common-language bundle of @highlightjs/cdn-assets 11.12.0, as npm ships it.
BUNDLE_BYTES = 129254
BUNDLE_SHA256 = "8ab71eb09c51f501e5e25157d9cff100e46cc29bcbfc744d0b746d451fca7f53"
BANNER = "Highlight.js v11.12.0"
LIMIT = 132 * 1024
# The marks of the code and diff HTML, each on a line of its own (plugin_check: a marker is never matched by part).
CODE_FIGURE = '<figure class="afkv2-code">'
CODE_WHERE = '<span class="afkv2-code-where">{}</span>'
CODE_WHERE_CLASS = "afkv2-code-where"
CODE_LANG = '<span class="afkv2-code-lang">{}</span>'
CODE_NUMBERS = re.compile(r'<pre class="afkv2-code-numbers" aria-hidden="true">([^<]*)</pre>')
CODE_PYTHON = re.compile(r'<code class="afkv2-code-text language-python" data-afkv2-lang="python">(.*?)</code>', re.S)
PLAIN_CODE = '<code class="afkv2-code-text">'
CODE_FONT = re.compile(r"\.afkv2-code-numbers,\s*\.afkv2-code-body pre[^{]*\{[^}]*font:[^;}]*monospace")
LANG_NAME = "data-afkv2-lang"
LANG_MARK = 'data-afkv2-lang="{}"'
DIFF_HUNK = re.compile(r'<div class="afkv2-diff-hunk">(.*?)</table></div>', re.S)
DIFF_ROW = re.compile(r'<tr class="afkv2-diff-line afkv2-diff-line--(\w+)"><td class="afkv2-diff-n">(\d*)</td>'
                      r'<td class="afkv2-diff-n">(\d*)</td><td class="afkv2-diff-sign">(.)</td>'
                      r'<td class="afkv2-diff-code"><code[^>]*>(.*?)</code></td></tr>', re.S)
DIFF_WHERE = '<span class="afkv2-diff-where">{}</span>'
DIFF_WHERE_TEXT = re.compile(r'<span class="afkv2-diff-where">([^<]*)</span>')
REMOVED_TINT = re.compile(r"\.afkv2-diff-line--removed[^{]*\{[^}]*var\(--blocked\)")
ADDED_TINT = re.compile(r"\.afkv2-diff-line--added[^{]*\{[^}]*var\(--settled\)")

PYTHON = "def export(orders):\n    return [o for o in orders if o.paid]\n"
DIFF = """diff --git a/shop/export.py b/shop/export.py
index 1111111..2222222 100644
--- a/shop/export.py
+++ b/shop/export.py
@@ -10,4 +10,4 @@ def export(orders):
     rows = []
-    for o in orders:
+    for o in paid(orders):
         rows.append(o)
     return rows
@@ -40,2 +40,3 @@ def paid(orders):
 def paid(orders):
+    \"\"\"Only the paid orders.\"\"\"
     return [o for o in orders if o.paid]
"""


def code(text=PYTHON, **props):
    return {"type": "code", "props": {"text": text, **props}}


def diff(text=DIFF, **props):
    return {"type": "diff", "props": {"text": text, **props}}


def drawn(component):
    assert registry.validate(component) == [], registry.validate(component)
    return registry.render_component(component)


def page_of(*bodies):
    items = [{"id": f"i-{k}", "kind": "info", "body": body} for k, body in enumerate(bodies)]
    return {"schema": "afkv2.page/1",
            "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                        "started": "2026-01-05T09:00:00Z", "step": "Requirements grill"},
            "maps": [], "notes": [],
            "rounds": [{"n": 1, "state": "current", "banner": {"settled": [], "unlocks": [], "parked": []},
                        "items": items}]}


def text_body(value="x"):
    return {"type": "text", "props": {"text": value}}


# --- code block (AC-029)

def test_a_code_block_shows_a_path_line_header_line_numbers_and_its_language_mark():
    html = drawn(code(path="shop/export.py", line=10, language="python"))
    assert CODE_FIGURE in html
    assert CODE_WHERE.format("shop/export.py:10") in html
    numbers = CODE_NUMBERS.search(html).group(1)
    assert numbers == "10\n11"
    block = CODE_PYTHON.search(html)
    assert block and unescape(block.group(1)) == PYTHON.rstrip("\n")


def test_a_code_block_starts_at_line_1_and_without_a_path_names_its_language():
    html = drawn(code(language="sql", text="select 1"))
    assert CODE_NUMBERS.search(html).group(1) == "1"
    assert CODE_WHERE_CLASS not in html and CODE_LANG.format("sql") in html


def test_a_code_block_with_no_language_carries_no_language_mark():
    html = drawn(code(path="notes.txt"))
    assert LANG_NAME not in html and PLAIN_CODE in html


def test_the_code_text_is_escaped():
    html = drawn(code(text="<script>alert(1)</script> & </pre>", language="html"))
    assert "<script>" not in html and "&lt;script&gt;" in html and "&amp; &lt;/pre&gt;" in html


def test_the_kit_gives_code_a_fixed_width_font():
    css = (ENGINE_DIR / "shell" / "code.css").read_text("utf-8")
    assert CODE_FONT.search(css)


@pytest.mark.parametrize("bad", [{"text": ""}, {"line": 0}, {"line": 1.5}, {"path": ""}, {"language": "c sharp"},
                                 {"language": "x" * 33}, {"colour": "red"}])
def test_a_code_block_refuses_props_outside_its_rules(bad):
    assert registry.validate({"type": "code", "props": {"text": PYTHON, **bad}}) != []


# --- diff (AC-030)

def _hunks(html):
    return DIFF_HUNK.findall(html)


def _rows(hunk):
    return DIFF_ROW.findall(hunk)


def test_a_diff_shows_a_file_and_line_header_per_hunk():
    hunks = _hunks(drawn(diff()))
    assert len(hunks) == 2
    heads = [DIFF_WHERE_TEXT.search(hunk).group(1) for hunk in hunks]
    assert heads == ["shop/export.py:10", "shop/export.py:40"]
    assert "@@ -10,4 +10,4 @@ def export(orders):" in unescape(hunks[0])


def test_removed_lines_show_with_minus_and_added_lines_with_plus_and_their_numbers():
    first, second = (_rows(hunk) for hunk in _hunks(drawn(diff())))
    assert [(kind, old, new, sign) for kind, old, new, sign, _ in first] == [
        ("kept", "10", "10", " "), ("removed", "11", "", "-"), ("added", "", "11", "+"),
        ("kept", "12", "12", " "), ("kept", "13", "13", " ")]
    assert unescape(first[1][4]) == "    for o in orders:" and unescape(first[2][4]) == "    for o in paid(orders):"
    assert [kind for kind, *_ in second] == ["kept", "added", "kept"]


def test_the_kit_paints_removed_lines_red_and_added_lines_green_in_both_themes():
    css = (ENGINE_DIR / "shell" / "code.css").read_text("utf-8")
    assert REMOVED_TINT.search(css)
    assert ADDED_TINT.search(css)


def test_a_diff_line_is_marked_with_the_language_of_its_file():
    html = drawn(diff())
    assert LANG_MARK.format("py") in html
    assert LANG_MARK.format("sql") in drawn(diff(language="sql"))


def test_a_diff_with_no_file_lines_takes_its_path():
    body = "@@ -1,2 +1,2 @@\n-a = 1\n+a = 2\n b = 3\n"
    html = drawn(diff(body, path="conf/app.yml"))
    assert DIFF_WHERE.format("conf/app.yml:1") in html and LANG_MARK.format("yml") in html


def test_a_new_file_names_its_new_path_and_a_deleted_file_its_old_path():
    added = "--- /dev/null\n+++ b/docs/new.md\n@@ -0,0 +1,1 @@\n+hello\n"
    removed = "--- a/docs/old.md\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-bye\n"
    assert DIFF_WHERE.format("docs/new.md:1") in drawn(diff(added))
    assert DIFF_WHERE.format("docs/old.md:1") in drawn(diff(removed))


def test_a_line_with_no_newline_at_the_end_shows_as_a_note():
    body = "--- a/x.txt\n+++ b/x.txt\n@@ -1 +1 @@\n-a\n\\ No newline at end of file\n+b\n"
    rows = _rows(_hunks(drawn(diff(body)))[0])
    assert [kind for kind, *_ in rows] == ["removed", "note", "added"]


@pytest.mark.parametrize("body, why", [
    ("just words\n", "no hunk"),
    ("@@ -1,1 +1,1 @@\n-a\n+b\n", "file"),
    ("--- a/x\n+++ b/x\n@@ -1,2 +1,2 @@\n-a\n+b\n", "ends"),
    ("--- a/x\n+++ b/x\n@@ -1,1 +1,1 @@\n?a\n+b\n", "line 4"),
    ("--- a/x\n+++ b/x\n@@ broken @@\n-a\n", "line 3"),
    ("--- a/x\n+++ b/x\n@@ -1 +1 @@\n a\n-b\n+c\n", "more lines than its header counts"),
    ("--- a/x\n+++ b/x\n@@ -1,1 +1,2 @@\n-a\n-b\n+c\n", "more lines than its header counts"),
])
def test_a_diff_that_is_no_unified_diff_is_refused(body, why):
    found = registry.validate({"type": "diff", "props": {"text": body}})
    assert found and any(why in reason for _, reason in found), found


# --- the highlighter: inlined once, only on a page with code (ADR-0003 design, SDD §10 row "Page weight")

def test_the_copied_bundle_is_the_11_12_0_common_bundle_with_its_licence():
    raw = BUNDLE.read_bytes()
    assert len(raw) == BUNDLE_BYTES and hashlib.sha256(raw).hexdigest() == BUNDLE_SHA256
    assert BANNER in raw[:200].decode("utf-8")
    licence = (HIGHLIGHT / "LICENSE").read_text("utf-8")
    assert licence.startswith("BSD 3-Clause License") and "Ivan Sagalaev" in licence
    for theme in ("github.min.css", "github-dark.min.css"):
        assert 1000 < (HIGHLIGHT / theme).stat().st_size < 1500


def test_git_keeps_the_copied_files_byte_for_byte():
    assert (HIGHLIGHT / ".gitattributes").read_text("utf-8").split() == ["*", "-text"]


def test_a_page_with_code_and_a_diff_inlines_the_library_and_both_themes_once():
    html = page.build(page_of(code(language="python"), code(language="sql", text="select 1"), diff()))
    assert html.count(BANNER) == 1
    assert html.count("Theme: GitHub Dark") == 1 and html.count("Theme: GitHub\n") == 1
    assert ':root[data-theme="light"]{' in html
    assert html.index(BANNER) > html.index(LANG_MARK.format("python")), "the library runs after the blocks it colours"


@pytest.mark.parametrize("body", [code(language="python"), diff()])
def test_the_highlighter_adds_132_kb_at_most(body):
    with_code = page.build(page_of(body)).encode("utf-8")
    plain = page.build(page_of(text_body())).encode("utf-8")
    component = registry.render_component(body).encode("utf-8")
    plain_component = registry.render_component(text_body()).encode("utf-8")
    added = len(with_code) - len(component) - (len(plain) - len(plain_component))
    assert BUNDLE_BYTES < added <= LIMIT, added


def test_a_page_with_neither_code_nor_a_diff_holds_0_bytes_of_the_highlighter():
    html = page.build(page_of(text_body(), {"type": "diagram", "props": {"caption": "c", "text": "flowchart LR; a-->b"}}))
    assert BANNER not in html and "hljs" not in html and "Theme: GitHub" not in html


def test_the_run_script_colours_only_a_known_language():
    script = (HIGHLIGHT / "run.js").read_text("utf-8")
    assert "hljs.getLanguage(" in script and LANG_NAME in script and "ignoreIllegals: true" in script
