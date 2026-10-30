"""Pictures: the receipt guard on upload, the two ids in the answer, the delete guard."""

from __future__ import annotations

import struct

import pytest

from conftest import FakeResp, http_error
from tracker import envelope, jira, v1_facts

UUID = "0123abcd-4567-89ab-cdef-0123456789ab"
ATTACH = ("POST", "/rest/api/3/issue/PROJ-1/attachments")
MEDIA = ("GET", "/rest/api/3/attachment/content/9001")


def routes():
    return {ATTACH: FakeResp(b'[{"id":"9001"}]'),
            MEDIA: http_error(303, location=f"https://api.media.atlassian.com/file/{UUID}/binary")}


def test_put_returns_attachment_and_media_id(recorded_jira, preview):
    file, receipt, paths = preview()
    recorded_jira(routes())
    answer = jira.attachment_put({"key": "PROJ-1", "png": str(paths[0]), "receipt": receipt, "preview": file})
    assert answer["ok"] is True
    assert answer["attachment_id"] == "9001" and answer["media_id"] == UUID
    assert answer["filename"] == paths[0].name


def test_put_reports_width_and_height(recorded_jira, preview):
    data = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 32, 16) + b"\x00" * 16
    file, receipt, paths = preview(pictures=(data,))
    recorded_jira(routes())
    answer = jira.attachment_put({"key": "PROJ-1", "png": str(paths[0]), "receipt": receipt, "preview": file})
    assert (answer["width"], answer["height"]) == (32, 16)


@pytest.mark.parametrize("change", [{"receipt": None}, {"receipt": "f" * 64}, {"preview": None}])
def test_put_without_a_matching_receipt_is_refused(recorded_jira, preview, change):
    file, receipt, paths = preview()
    client = recorded_jira(routes())
    payload = {"key": "PROJ-1", "png": str(paths[0]), "receipt": receipt, "preview": file, **change}
    with pytest.raises(envelope.Refusal) as caught:
        jira.attachment_put(payload)
    assert caught.value.code == "bad-receipt" and client.calls == []


def test_put_of_a_picture_the_preview_did_not_show_is_refused(recorded_jira, preview):
    file, receipt, paths = preview()
    paths[0].write_bytes(b"\x89PNG changed after the preview")
    client = recorded_jira(routes())
    with pytest.raises(envelope.Refusal) as caught:
        jira.attachment_put({"key": "PROJ-1", "png": str(paths[0]), "receipt": receipt, "preview": file})
    assert caught.value.code == "bad-receipt" and client.calls == []


@pytest.mark.parametrize("name", ["picture.png", "afkv2-fig-00000000-1.png", "afkv2-fig-{r}-x.png", "afkv2-fig-{r}-1.txt"])
def test_put_refuses_a_name_outside_the_pattern(recorded_jira, preview, name):
    file, receipt, paths = preview()
    other = paths[0].with_name(name.format(r=receipt[:8]))
    paths[0].rename(other)
    client = recorded_jira(routes())
    with pytest.raises(envelope.Refusal) as caught:
        jira.attachment_put({"key": "PROJ-1", "png": str(other), "receipt": receipt, "preview": file})
    assert caught.value.code == "bad-name" and client.calls == []


def test_put_of_a_missing_file_is_bad_payload(recorded_jira, preview):
    file, receipt, paths = preview()
    paths[0].unlink()
    recorded_jira(routes())
    with pytest.raises(envelope.Refusal) as caught:
        jira.attachment_put({"key": "PROJ-1", "png": str(paths[0]), "receipt": receipt, "preview": file})
    assert caught.value.code == "bad-payload"


def test_a_lost_media_id_names_the_uploaded_attachment(recorded_jira, preview):
    file, receipt, paths = preview()
    table = routes()
    table[MEDIA] = http_error(403)
    recorded_jira(table)
    with pytest.raises(envelope.Refusal) as caught:
        jira.attachment_put({"key": "PROJ-1", "png": str(paths[0]), "receipt": receipt, "preview": file})
    assert caught.value.code == "no-media-id" and caught.value.extra["attachment_id"] == "9001"


def test_list_keeps_the_v1_shape(recorded_jira):
    recorded_jira({("GET", "/rest/api/3/issue/PROJ-1"): FakeResp({"fields": {"attachment": [
        {"id": "1", "filename": "a.png", "mimeType": "image/png", "size": 3, "created": "t",
         "author": {"displayName": "D"}, "content": "u", "ignored": True}]}})})
    assert jira.attachment_list({"key": "PROJ-1"}) == {"ok": True, "count": 1, "attachments": [
        {"id": "1", "filename": "a.png", "mimeType": "image/png", "size": 3, "created": "t", "author": "D", "content": "u"}]}


@pytest.mark.parametrize("name", ["afkv2-fig-0123abcd-1.png", f"{v1_facts.PICTURE_PREFIX}3.png"])
def test_delete_removes_afkv2_and_v1_pictures(recorded_jira, name):
    client = recorded_jira({("GET", "/rest/api/3/attachment/5"): FakeResp({"filename": name}),
                            ("DELETE", "/rest/api/3/attachment/5"): FakeResp(b"")})
    assert jira.attachment_delete({"id": "5"}) == {"ok": True, "id": "5", "filename": name, "deleted": True}
    assert [call[0] for call in client.writes()] == ["DELETE"]


@pytest.mark.parametrize("name", ["contract.pdf", "afkv2-fig-1.png", "photo.png"])
def test_delete_refuses_a_file_that_is_not_a_picture_of_the_publish(recorded_jira, name):
    client = recorded_jira({("GET", "/rest/api/3/attachment/5"): FakeResp({"filename": name})})
    with pytest.raises(envelope.Refusal) as caught:
        jira.attachment_delete({"id": "5"})
    assert caught.value.code == "not-a-picture" and not client.writes()


def test_delete_of_an_attachment_already_gone_is_ok(recorded_jira):
    recorded_jira({("GET", "/rest/api/3/attachment/5"): http_error(404)})
    assert jira.attachment_delete({"id": "5"}) == {"ok": True, "id": "5", "deleted": False}


def test_a_refused_delete_status_is_mapped(recorded_jira):
    recorded_jira({("GET", "/rest/api/3/attachment/5"): FakeResp({"filename": "afkv2-fig-0123abcd-1.png"}),
                   ("DELETE", "/rest/api/3/attachment/5"): http_error(403)})
    with pytest.raises(envelope.Refusal) as caught:
        jira.attachment_delete({"id": "5"})
    assert caught.value.code == "forbidden"
