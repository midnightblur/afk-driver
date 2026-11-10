"""References in page text link to the tracker and the forge through `session.links`."""

import json
import re
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
for folder in (PLUGIN / "scripts", ENGINE_DIR):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
from shell import inject, page  # noqa: E402
from shell.references import linkify  # noqa: E402

REPO = "https://github.com/acme/shop"
LINKS = {"issue": REPO + "/issues/{id}", "change": REPO + "/pull/{id}", "commit": REPO + "/commit/{id}",
         "ticket": "https://acme.atlassian.net/browse/{id}", "projects": ["ABC"]}
SHA = "0123456789abcdef0123456789abcdef01234567"
NEW_TAB = 'target="_blank" rel="noopener noreferrer" data-lavish-action="afkv2-ref"'
REF_CLASS = 'class="afkv2-ref"'
TIPS_DICT = 'id="afkv2-tips-dict"'
OPEN_LINK = re.compile(r"<a\b[^>]*>")
LET_THROUGH = re.compile(r'\sdata-lavish-action="[^"]+"')
REF_ATTRS = re.compile(r'<a class="afkv2-ref" href="[^"]*" ([^>]*)>')


def anchor(href, words):
    return f'<a {REF_CLASS} href="{href}" {NEW_TAB}>{words}</a>'


def document(links=None, banner_entry="Scope of #159 settled", text="See ABC-12 and R-3.", ticket="158"):
    session = {"id": "s1", "skill": "grill", "feature": "Feature", "ticket": ticket, "started": "2026-01-05T10:00:00Z"}
    if links is not None:
        session["links"] = links
    body = {"type": "text", "id": "i-a-text", "props": {"text": text}, "children": [
        {"type": "table", "id": "t-refs", "props": {"columns": ["Ticket"], "rows": [["#160"]]}},
        {"type": "text", "props": {"text": "`#161` in code", "markdown": True}}]}
    return {"schema": "afkv2.page/0", "session": session, "rounds": [{
        "n": 1, "state": "current", "banner": {"settled": [banner_entry], "unlocks": [], "parked": []},
        "items": [{"id": "i-a", "kind": "info", "body": body}]}]}


def ids_of(html):
    return re.findall(r'\sid="([^"]*)"', html)


def test_each_reference_kind_links_to_its_template_in_a_new_tab():
    text = f"PR #12, MR !7, !8, #9, ABC-3, XYZ-4, commit abc1234, sha: 1234abcd and {SHA}."
    assert linkify(f"<p>{text}</p>", LINKS) == (
        f'<p>PR {anchor(REPO + "/pull/12", "#12")}, MR {anchor(REPO + "/pull/7", "!7")}, '
        f'{anchor(REPO + "/pull/8", "!8")}, {anchor(REPO + "/issues/9", "#9")}, '
        f'{anchor("https://acme.atlassian.net/browse/ABC-3", "ABC-3")}, XYZ-4, '
        f'commit {anchor(REPO + "/commit/abc1234", "abc1234")}, sha: {anchor(REPO + "/commit/1234abcd", "1234abcd")} '
        f'and {anchor(REPO + "/commit/" + SHA, SHA)}.</p>')


@pytest.mark.parametrize("text", [
    "a1b2c3d4 is no commit without the word", "ABC-12x", "#12abc", "owner/name#7", "x#7", "&#39;", "issue 159",
])
def test_text_that_is_no_clear_reference_stays_text(text):
    assert linkify(f"<p>{text}</p>", LINKS) == f"<p>{text}</p>"


def test_a_kind_without_a_template_stays_text():
    assert linkify("<p>#159 and !3 and ABC-1</p>", {"commit": LINKS["commit"]}) == "<p>#159 and !3 and ABC-1</p>"
    assert linkify("<p>ABC-1</p>", {"ticket": LINKS["ticket"]}) == "<p>ABC-1</p>"


def test_tags_attributes_links_code_and_svg_keep_their_bytes():
    html = ('<div id="i-159" title="#159"><a href="x">#1</a><code>#2</code><svg><text>#3</text></svg>'
            '<summary>#4</summary><label>#5</label><!-- #6 --><br/>#7</div>')
    assert linkify(html, LINKS) == html.replace("<br/>#7", f'<br/>{anchor(REPO + "/issues/7", "#7")}')


def test_the_page_links_the_banner_the_table_the_text_and_the_ticket_but_not_code():
    html = page.build(document(LINKS))
    assert f'Scope of {anchor(REPO + "/issues/159", "#159")} settled' in html
    assert anchor(REPO + "/issues/160", "#160") in html
    assert f'See {anchor("https://acme.atlassian.net/browse/ABC-12", "ABC-12")} and R-3.' in html
    assert anchor(REPO + "/issues/158", "#158") in html
    assert "<code>#161</code>" in html
    assert ids_of(html) == ids_of(page.build(document()))


def test_without_links_the_page_shows_plain_text():
    html = page.build(document())
    assert REF_CLASS not in html and "Scope of #159 settled" in html
    assert html == page.build(document({}))


def test_tip_words_beside_a_link_stay_plain_text_for_the_tooltips():
    html = page.build(document(LINKS, banner_entry="the steer in #159 holds"))
    assert f'<li>the steer in {anchor(REPO + "/issues/159", "#159")} holds</li>' in html
    shown = inject.inject(html, {"steer": "A note for the whole session."})
    assert TIPS_DICT in shown and "the steer in " in shown


@pytest.mark.parametrize("links, why", [
    ({"issue": "javascript:alert(1)//{id}"}, "does not match"),
    ({"issue": "https://x/issues/"}, "does not match"),
    ({"tracker": "https://x/{id}"}, "tracker"),
    ({"ticket": "https://x/{id}", "projects": ["abc"]}, "does not match"),
])
def test_the_check_refuses_bad_links(tmp_path, monkeypatch, capsys, links, why):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(document(links)), "utf-8")
    assert engine.main(["check", str(path)]) == 1
    assert why in capsys.readouterr().out


def test_the_check_accepts_the_links_block(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(document(LINKS)), "utf-8")
    assert engine.main(["check", str(path)]) == 0


def test_each_link_lets_its_click_through_the_note_mode_of_lavish():
    """lavish's note mode takes every click outside `[data-lavish-action]` and opens the note composer, so a
    link without the attribute never opens."""
    html = page.build(document(LINKS))
    attrs = REF_ATTRS.findall(html)
    assert attrs and set(attrs) == {NEW_TAB}


@pytest.mark.parametrize("text", ["https://acme.atlassian.net/browse/ABC-12", "see https://x.test/ABC-12?a=1&amp;b=#9."])
def test_a_reference_inside_a_url_stays_text(text):
    assert linkify(f"<p>{text}</p>", LINKS) == f"<p>{text}</p>"


def test_a_markdown_link_in_a_plain_cell_links_its_key_once_and_keeps_its_url_as_text():
    """A plain cell is plain text: the brackets show, the key links, the key inside the URL does not."""
    url = "https://acme.atlassian.net/browse/ABC-748"
    assert linkify(f"<td>[ABC-748]({url})</td>", LINKS) == (
        f"<td>[{anchor(url, 'ABC-748')}]({url})</td>")


@pytest.mark.parametrize("fixture", ["v0-page-with-notes.json", "v0-sdd-pass.json"])
def test_every_link_of_a_page_lets_its_click_through(fixture):
    """A link the engine writes without `data-lavish-action` opens the note composer, never its target."""
    doc = json.loads((PLUGIN / "tests" / "engine" / "fixtures" / fixture).read_text("utf-8"))
    tags = OPEN_LINK.findall(page.build(doc))
    assert tags and [tag for tag in tags if not LET_THROUGH.search(tag)] == []


def test_a_url_ends_at_an_escaped_quote_so_the_key_after_it_links():
    url = "https://x.test/a"
    assert linkify(f"<p>&quot;{url}&quot;ABC-1</p>", LINKS) == (
        f'<p>&quot;{url}&quot;{anchor("https://acme.atlassian.net/browse/ABC-1", "ABC-1")}</p>')


def test_an_element_link_of_a_version_2_page_lets_its_click_through():
    from shell import parts_v2
    tags = OPEN_LINK.findall(parts_v2.link({"session": {}, "rounds": []}, "sec-a"))
    assert len(tags) == 1 and LET_THROUGH.search(tags[0])


FLAG_TIP = 'data-afkv2-tip="Add a flag"'
LOGIN_TIP = 'data-afkv2-tip="Fix the &quot;login&quot; &lt;page&gt;"'
TITLES = {**LINKS, "titles": {"ABC-3": 'Fix the "login" <page>', "#9": "Add a flag", "!7": "Ship it"}}


def titled(href, words, title):
    return (f'<a class="afkv2-ref afkv2-tip" href="{href}" {NEW_TAB} data-afkv2-tip="{title}">{words}</a>')


def test_a_reference_with_a_title_shows_it_on_hover_and_one_with_none_has_no_hover_text():
    html = linkify("<p>ABC-3, ABC-4, #9, MR !7, PR #12.</p>", TITLES)
    assert html == (
        f'<p>{titled("https://acme.atlassian.net/browse/ABC-3", "ABC-3", "Fix the &quot;login&quot; &lt;page&gt;")}, '
        f'{anchor("https://acme.atlassian.net/browse/ABC-4", "ABC-4")}, '
        f'{titled(REPO + "/issues/9", "#9", "Add a flag")}, MR {titled(REPO + "/pull/7", "!7", "Ship it")}, '
        f'PR {anchor(REPO + "/pull/12", "#12")}.</p>')


def test_a_titled_link_in_a_table_cell_a_text_and_a_map_label_keeps_its_tip_on_the_page():
    doc = document(TITLES, text="See ABC-3.")
    doc["rounds"][0]["items"][0]["body"]["children"][0]["props"]["rows"] = [["#9"]]
    doc["maps"] = [{"type": "map", "id": "m-1", "props": {"nodes": [
        {"id": "n-1", "label": "ABC-3 login", "state": "open", "round": 1}]}}]
    html = page.build(engine.READERS[doc["schema"]](doc))
    assert html.count(FLAG_TIP) == 1 and html.count(LOGIN_TIP) == 2


def test_a_change_written_after_its_words_takes_the_title_of_the_change_before_the_issue():
    links = {**LINKS, "titles": {"#5": "issue five", "!5": "change five", "#6": "shared six"}}
    html = linkify("<p>MR #5, #5, PR #6.</p>", links)
    assert html == (f'<p>MR {titled(REPO + "/pull/5", "#5", "change five")}, '
                    f'{titled(REPO + "/issues/5", "#5", "issue five")}, PR {titled(REPO + "/pull/6", "#6", "shared six")}.</p>')
