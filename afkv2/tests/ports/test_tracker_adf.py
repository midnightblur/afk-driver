"""Ported from the v1 Jira tests: the Markdown to ADF conversion."""

from __future__ import annotations

import pytest

from tracker import adf


def convert(md, figures=None):
    return adf.md_to_adf_content(md, figures or {})


def test_heading():
    assert convert("# Title") == [{
        "type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "Title"}],
    }]


def test_heading_level():
    assert convert("### Deep")[0]["attrs"]["level"] == 3


def test_paragraph_with_marks():
    nodes = convert("plain **bold** and *em* and `code`")
    assert nodes[0]["type"] == "paragraph"
    texts = {tuple(sorted(m["type"] for m in n.get("marks", []))): n["text"] for n in nodes[0]["content"]}
    assert "bold" in texts[("strong",)] and "em" in texts[("em",)] and "code" in texts[("code",)]


def test_code_mark_is_exclusive():
    assert [m["type"] for m in convert("**`bolded code`**")[0]["content"][0]["marks"]] == ["code"]


def test_absolute_link_kept_relative_dropped():
    nodes = convert("[abs](https://x.test/y) and [rel](../foo.md)")
    marks = {n["text"]: [m["type"] for m in n.get("marks", [])] for n in nodes[0]["content"]}
    assert "link" in marks["abs"] and "link" not in marks.get("rel", [])


def test_bullet_list():
    nodes = convert("- one\n- two")
    assert nodes[0]["type"] == "bulletList" and len(nodes[0]["content"]) == 2
    assert nodes[0]["content"][0]["type"] == "listItem"


def test_ordered_list_start_attr():
    nodes = convert("3. three\n4. four")
    assert nodes[0]["type"] == "orderedList" and nodes[0]["attrs"] == {"order": 3}


def test_code_fence_language():
    nodes = convert("```python\nx = 1\n```")
    assert nodes[0]["type"] == "codeBlock" and nodes[0]["attrs"] == {"language": "python"}
    assert nodes[0]["content"][0]["text"] == "x = 1"


@pytest.mark.parametrize("source", ["```  \nx = 1\n```", "```\t \nx = 1\n```"])
def test_code_fence_whitespace_only_info_does_not_crash(source):
    nodes = convert(source)
    assert nodes[0]["type"] == "codeBlock" and "attrs" not in nodes[0]
    assert nodes[0]["content"][0]["text"] == "x = 1"


def test_table():
    rows = convert("| a | b |\n|---|---|\n| 1 | 2 |")[0]["content"]
    assert rows[0]["content"][0]["type"] == "tableHeader"
    assert rows[1]["content"][0]["type"] == "tableCell"


def test_figure_placeholder_substitution():
    token = adf.FIG_TOKEN.format(0)
    figure = [{"type": "mediaSingle", "attrs": {"layout": "center"},
               "content": [{"type": "media", "attrs": {"type": "file", "id": "u"}}]}]
    nodes = convert(f"before\n\n{token}\n\nafter", {0: figure})
    assert figure[0] in nodes and "FIGURE" not in str(nodes)


def test_figure_token_is_the_afkv2_token():
    assert adf.FIG_TOKEN == "AFKV2FIGURE{}ENDFIGURE"


def test_missing_parser_is_a_named_refusal(monkeypatch):
    import builtins
    from tracker import envelope

    real = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name == "markdown_it":
            raise ImportError(name)
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(envelope.Refusal) as caught:
        convert("# x")
    assert caught.value.code == "missing-dependency" and "markdown-it-py" in caught.value.reason
