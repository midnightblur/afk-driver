"""Seam-test on Jira REST: the read-back compare on text and media ids, on hand-built answers (decision D-33)."""

from __future__ import annotations

import json
from pathlib import Path

from port_fakes import FakeResp
from tracker import jira

HAND_BUILT = Path(__file__).parent / "hand_built"
MEDIA_ID = "6e8f6c52-3b1a-4a55-9f10-2a1e6f0c7d11"


def hand_built(name):
    return json.loads((HAND_BUILT / name).read_text(encoding="utf-8"))


def sent_block():
    return [
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Goal"}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "Publish the PRD."}]},
        {"type": "mediaSingle", "attrs": {"layout": "center"}, "content": [
            {"type": "media", "attrs": {"type": "file", "id": MEDIA_ID, "collection": "", "width": 640, "height": 480}}]},
    ]


def publish_then_read(fake_jira, preview, after):
    before = hand_built("issue-before-publish.json")["response"]
    previewed = jira.description_hash(before["fields"]["description"])
    file, receipt, _ = preview(description_hash=previewed, pictures=(), text="Goal\nPublish the PRD.")
    client = fake_jira({
        ("GET", "/rest/api/3/issue/PROJ-1"): FakeResp(before),
        ("PUT", "/rest/api/3/issue/PROJ-1"): FakeResp(b""),
    })
    put = jira.description_put({"key": "PROJ-1", "adf": sent_block(), "expect_hash": previewed,
                                "receipt": receipt, "preview": file})
    client.routes[("GET", "/rest/api/3/issue/PROJ-1")] = FakeResp(after)
    return put, jira.issue_get({"key": "PROJ-1"})


def test_a_read_back_with_added_attributes_compares_equal(fake_jira, preview):
    put, read = publish_then_read(fake_jira, preview, hand_built("issue-after-publish.json")["response"])
    assert put["block"] == read["block"]
    assert read["block"]["family"] == "afkv2" and read["block"]["media_ids"] == [MEDIA_ID]


def test_a_read_back_with_another_media_id_compares_different(fake_jira, preview):
    after = hand_built("issue-after-publish.json")["response"]
    text = json.dumps(after).replace(MEDIA_ID, "00000000-0000-0000-0000-000000000000")
    put, read = publish_then_read(fake_jira, preview, json.loads(text))
    assert put["block"]["media_ids"] != read["block"]["media_ids"]


def test_a_read_back_with_other_text_compares_different(fake_jira, preview):
    after = hand_built("issue-after-publish.json")["response"]
    text = json.dumps(after).replace("Publish the PRD.", "Someone edited this.")
    put, read = publish_then_read(fake_jira, preview, json.loads(text))
    assert put["block"]["text"] != read["block"]["text"]


def test_issue_get_answers_the_hash_to_send_as_expect_hash(fake_jira):
    before = hand_built("issue-before-publish.json")["response"]
    fake_jira({("GET", "/rest/api/3/issue/PROJ-1"): FakeResp(before)})
    read = jira.issue_get({"key": "PROJ-1"})
    assert read["description"] == before["fields"]["description"]
    assert read["description_hash"] == jira.description_hash(before["fields"]["description"])
    assert read["block"] is None and "block_problem" not in read
    assert read["key"] == "PROJ-1" and "description" not in read["fields"]


def test_issue_get_always_asks_for_the_description(fake_jira):
    client = fake_jira({("GET", "/rest/api/3/issue/PROJ-1"): FakeResp({"fields": {"summary": "s"}})})
    read = jira.issue_get({"key": "PROJ-1", "fields": "summary"})
    assert "fields=summary%2Cdescription" in client.calls[0][1]
    assert read["description"] is None


def test_issue_get_accepts_a_field_list(fake_jira):
    client = fake_jira({("GET", "/rest/api/3/issue/PROJ-1"): FakeResp({"fields": {}})})
    jira.issue_get({"key": "PROJ-1", "fields": ["summary", "description"]})
    assert "fields=summary%2Cdescription" in client.calls[0][1]


def test_issue_get_default_fields_serve_the_grill(fake_jira):
    client = fake_jira({("GET", "/rest/api/3/issue/PROJ-1"): FakeResp({"fields": {}})})
    jira.issue_get({"key": "PROJ-1"})
    asked = client.calls[0][1]
    assert "comment" in asked and "issuelinks" in asked


def test_issue_get_names_a_broken_block_without_failing_the_read(fake_jira):
    broken = {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": jira.BEGIN_LINE}]}]}
    fake_jira({("GET", "/rest/api/3/issue/PROJ-1"): FakeResp({"fields": {"description": broken}})})
    read = jira.issue_get({"key": "PROJ-1"})
    assert read["ok"] is True and read["block"] is None and "without an end" in read["block_problem"]


def test_the_key_cannot_change_the_rest_path(fake_jira):
    client = fake_jira({("GET", "/rest/api/3/issue/"): FakeResp({"fields": {}})})
    jira.issue_get({"key": "../../myself"})
    assert client.calls[0][1].startswith("/rest/api/3/issue/..%2F..%2Fmyself")
