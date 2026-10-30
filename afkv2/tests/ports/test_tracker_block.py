"""The managed block: found only by full lines, and only the text between them changes."""

from __future__ import annotations

import copy
import json

import pytest

from conftest import FakeResp, http_error
from tracker import envelope, jira, v1_facts

BEGIN, END = jira.BEGIN_LINE, jira.END_LINE
V1_BEGIN = v1_facts.BLOCK_BEGIN_LINES[0]
V1_BEGIN_BARE = v1_facts.BLOCK_BEGIN_LINES[1]
V1_END = v1_facts.BLOCK_END_LINE


def para(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def doc(*nodes):
    return {"type": "doc", "version": 1, "content": list(nodes)}


SHORT_BEFORE = para("Short note before.")
SHORT_AFTER = {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "After"}]}
NEW_BLOCK = [para("the new PRD")]


def refused(content):
    with pytest.raises(envelope.Refusal) as caught:
        jira.find_managed_block(content)
    assert caught.value.code == "bad-block"
    return caught.value.reason


def test_no_block():
    assert jira.find_managed_block([para("x")]) is None
    assert jira.find_managed_block([]) is None


def test_afkv2_block():
    block = jira.find_managed_block([SHORT_BEFORE, para(BEGIN), para("x"), para(END), SHORT_AFTER])
    assert (block.start, block.end, block.family) == (1, 3, "afkv2")


@pytest.mark.parametrize("begin", [V1_BEGIN, V1_BEGIN_BARE])
def test_v1_block(begin):
    block = jira.find_managed_block([para(begin), para("x"), para(V1_END)])
    assert (block.start, block.end, block.family) == (0, 2, "v1")


def test_marks_and_outer_spaces_do_not_hide_a_line():
    marked = {"type": "paragraph", "content": [{"type": "text", "text": f" {BEGIN} ", "marks": [{"type": "em"}]}]}
    assert jira.find_managed_block([marked, para(END)]).family == "afkv2"


@pytest.mark.parametrize("content,word", [
    ([para(BEGIN)], "without an end"),
    ([para(END)], "without a begin"),
    ([para(END), para(BEGIN)], "before"),
    ([para(BEGIN), para(END), para(BEGIN), para(END)], "2"),
    ([para(BEGIN), para(BEGIN), para(END)], "2"),
    ([para(BEGIN), para(END), para(V1_BEGIN), para(V1_END)], "2"),
    ([para(BEGIN), para(V1_END)], "different"),
    ([para(V1_BEGIN), para(END)], "different"),
    ([para(V1_BEGIN)], "without an end"),
    ([para(V1_END)], "without a begin"),
])
def test_broken_or_doubled_blocks_are_refused(content, word):
    assert word in refused(content)


def test_a_prefix_is_not_a_line():
    assert jira.find_managed_block([para(BEGIN + " tail"), para("x " + END)]) is None
    assert jira.find_managed_block([para("afkv2:prd:start:more")]) is None


def test_a_v1_prefix_only_line_is_plain_text():
    assert jira.find_managed_block([para(V1_BEGIN_BARE + " some other note")]) is None


def test_a_v1_prefix_line_with_a_v1_end_is_refused_never_appended_beside():
    assert "without a begin" in refused([para(V1_BEGIN_BARE + " some other note"), para(V1_END)])


def test_a_marker_buried_in_another_node_is_refused():
    panel = {"type": "panel", "content": [para(BEGIN)]}
    assert "inside" in refused([panel, para(END)])


def test_a_marker_sharing_a_paragraph_with_other_lines_is_refused():
    node = {"type": "paragraph", "content": [
        {"type": "text", "text": BEGIN}, {"type": "hardBreak"}, {"type": "text", "text": "more"}]}
    assert "inside" in refused([node, para(END)])


def test_a_marker_in_a_code_block_is_quoted_text():
    code = {"type": "codeBlock", "content": [{"type": "text", "text": BEGIN}]}
    assert jira.find_managed_block([code]) is None


class Publish:
    """One description-put against a recorded Jira description."""

    def __init__(self, recorded_jira, preview, description):
        self.description = description
        self.hash = jira.description_hash(description)
        self.preview, self.receipt, _ = preview(description_hash=self.hash, pictures=())
        self.client = recorded_jira({
            ("GET", "/rest/api/3/issue/PROJ-1"): FakeResp({"key": "PROJ-1", "fields": {"description": description}}),
            ("PUT", "/rest/api/3/issue/PROJ-1"): FakeResp(b""),
        })

    def payload(self, **change):
        return {"key": "PROJ-1", "adf": NEW_BLOCK, "expect_hash": self.hash, "receipt": self.receipt,
                "preview": self.preview, **change}

    def sent(self):
        put = [call for call in self.client.calls if call[0] == "PUT"]
        assert len(put) == 1
        return json.loads(put[0][2])["fields"]["description"]


@pytest.fixture
def publish(recorded_jira, preview):
    return lambda description: Publish(recorded_jira, preview, description)


def test_first_publish_appends_at_the_end_and_keeps_the_rest(publish):
    run = publish(doc(SHORT_BEFORE, SHORT_AFTER))
    answer = jira.description_put(run.payload())
    assert answer["ok"] is True and answer["replaced"] is None
    content = run.sent()["content"]
    assert content[:2] == [SHORT_BEFORE, SHORT_AFTER]
    assert jira.node_text(content[2]) == BEGIN and content[3] == NEW_BLOCK[0] and jira.node_text(content[4]) == END


def test_an_empty_description_gets_the_block_alone(publish):
    run = publish(None)
    assert jira.description_put(run.payload())["ok"] is True
    sent = run.sent()
    assert sent["type"] == "doc" and sent["version"] == 1 and len(sent["content"]) == 3


def test_replace_keeps_short_sections_byte_identical(publish):
    before, after = copy.deepcopy(SHORT_BEFORE), copy.deepcopy(SHORT_AFTER)
    run = publish(doc(before, para(BEGIN), para("old"), para(END), after))
    answer = jira.description_put(run.payload())
    assert answer["replaced"] == "afkv2"
    content = run.sent()["content"]
    assert json.dumps(content[0]) == json.dumps(SHORT_BEFORE)
    assert json.dumps(content[-1]) == json.dumps(SHORT_AFTER)
    assert [jira.node_text(n) for n in content[1:4]] == [BEGIN, "the new PRD", END]


def test_a_v1_block_is_replaced_by_the_afkv2_block(publish):
    run = publish(doc(SHORT_BEFORE, para(V1_BEGIN), para("old"), para(V1_END), SHORT_AFTER))
    answer = jira.description_put(run.payload())
    assert answer["replaced"] == "v1"
    assert [jira.node_text(n) for n in run.sent()["content"]] == [
        "Short note before.", BEGIN, "the new PRD", END, "After"]


def test_a_description_of_short_text_only_is_never_absorbed(publish):
    run = publish(doc(para("TBD")))
    jira.description_put(run.payload())
    assert jira.node_text(run.sent()["content"][0]) == "TBD"


def test_doc_root_fields_stay(publish):
    description = {"type": "doc", "version": 1, "extra": "kept", "content": []}
    run = publish(description)
    jira.description_put(run.payload())
    assert run.sent()["extra"] == "kept"


def test_a_whole_doc_is_accepted_as_adf(publish):
    run = publish(doc())
    jira.description_put(run.payload(adf={"type": "doc", "version": 1, "content": NEW_BLOCK}))
    assert jira.node_text(run.sent()["content"][1]) == "the new PRD"


@pytest.mark.parametrize("adf", [[], "text", {"type": "doc"}, [1]])
def test_adf_that_holds_no_nodes_is_bad_payload(publish, adf):
    run = publish(doc())
    with pytest.raises(envelope.Refusal) as caught:
        jira.description_put(run.payload(adf=adf))
    assert caught.value.code == "bad-payload" and not run.client.writes()


def test_new_text_holding_a_block_line_is_refused(publish):
    run = publish(doc())
    with pytest.raises(envelope.Refusal) as caught:
        jira.description_put(run.payload(adf=[para(END)]))
    assert caught.value.code == "bad-block" and not run.client.writes()


def test_stale_writes_nothing(publish):
    run = publish(doc(SHORT_BEFORE))
    run.client.routes[("GET", "/rest/api/3/issue/PROJ-1")] = FakeResp(
        {"fields": {"description": doc(para("edited after the preview"))}})
    with pytest.raises(envelope.Refusal) as caught:
        jira.description_put(run.payload())
    assert caught.value.code == "stale" and not run.client.writes()


def test_the_stale_check_reads_just_before_the_write(publish):
    run = publish(doc(SHORT_BEFORE))
    jira.description_put(run.payload())
    assert [call[0] for call in run.client.calls] == ["GET", "PUT"]


@pytest.mark.parametrize("description", [
    doc(para(BEGIN)),
    doc(para(END)),
    doc(para(BEGIN), para(END), para(BEGIN), para(END)),
    doc(para(V1_BEGIN), para(BEGIN), para(END)),
])
def test_bad_block_writes_nothing(publish, description):
    run = publish(description)
    with pytest.raises(envelope.Refusal) as caught:
        jira.description_put(run.payload())
    assert caught.value.code == "bad-block" and not run.client.writes()


@pytest.mark.parametrize("change", [
    {"receipt": None}, {"receipt": ""}, {"receipt": "short"}, {"receipt": "f" * 64},
    {"preview": None}, {"preview": "no-such-file.json"}, {"expect_hash": "0" * 64},
])
def test_bad_receipt_touches_nothing(publish, change):
    run = publish(doc())
    with pytest.raises(envelope.Refusal) as caught:
        jira.description_put(run.payload(**change))
    assert caught.value.code == "bad-receipt" and run.client.calls == []


def test_a_preview_of_another_ticket_is_a_bad_receipt(publish, tmp_path):
    run = publish(doc())
    data = json.loads(open(run.preview, encoding="utf-8").read())
    data["ticket_key"] = "PROJ-2"
    other = tmp_path / "other.json"
    other.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(envelope.Refusal) as caught:
        jira.description_put(run.payload(preview=str(other)))
    assert caught.value.code == "bad-receipt"


@pytest.mark.parametrize("text", ["not json", "[1]"])
def test_an_unreadable_preview_is_a_bad_receipt(publish, tmp_path, text):
    run = publish(doc())
    broken = tmp_path / "broken.json"
    broken.write_text(text, encoding="utf-8")
    with pytest.raises(envelope.Refusal) as caught:
        jira.description_put(run.payload(preview=str(broken)))
    assert caught.value.code == "bad-receipt"


@pytest.mark.parametrize("missing", ["key", "adf", "expect_hash"])
def test_missing_arguments_are_bad_payload(publish, missing):
    run = publish(doc())
    payload = run.payload()
    del payload[missing]
    with pytest.raises(envelope.Refusal) as caught:
        jira.description_put(payload)
    assert caught.value.code == "bad-payload"


def test_a_failed_write_maps_the_status(publish):
    run = publish(doc())
    run.client.routes[("PUT", "/rest/api/3/issue/PROJ-1")] = http_error(403, b"nope")
    with pytest.raises(envelope.Refusal) as caught:
        jira.description_put(run.payload())
    assert caught.value.code == "forbidden" and "nope" in caught.value.reason


def test_the_hash_ignores_key_order_only():
    assert jira.description_hash({"a": 1, "b": [2]}) == jira.description_hash({"b": [2], "a": 1})
    assert jira.description_hash({"a": 1}) != jira.description_hash({"a": 2})
    assert jira.description_hash(None) != jira.description_hash(doc())
