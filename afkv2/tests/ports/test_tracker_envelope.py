"""The one answer shape both ports share."""

from __future__ import annotations

import io
import json

import pytest

from tracker import envelope


def test_ok_and_fail_shapes():
    assert envelope.ok(a=1) == {"ok": True, "a": 1}
    assert envelope.fail("stale", "why") == {"ok": False, "error": {"code": "stale", "reason": "why"}}


@pytest.mark.parametrize("answer,code", [
    (envelope.ok(), 0),
    (envelope.fail("stale", "x"), 1),
    (envelope.fail("internal", "x"), 1),
    (envelope.fail("bad-payload", "x"), 2),
    (envelope.fail("unknown-verb", "x"), 2),
])
def test_exit_codes(answer, code):
    assert envelope.exit_code(answer) == code


@pytest.mark.parametrize("status,code", [
    (400, "bad-request"), (401, "auth"), (403, "forbidden"), (404, "not-found"),
    (409, "conflict"), (413, "too-large"), (429, "rate-limited"),
    (500, "server-error"), (503, "server-error"), (418, "http-error"),
])
def test_http_status_table(status, code):
    assert envelope.code_for_status(status) == code


@pytest.mark.parametrize("text", ["{bad", "[1, 2]", '"text"', "7"])
def test_a_payload_that_is_not_one_object_is_refused(text):
    with pytest.raises(envelope.Refusal) as caught:
        envelope.read_payload([text], io.StringIO(""))
    assert caught.value.code == "bad-payload"


@pytest.mark.parametrize("args,stream,expected", [
    (['{"a":1}'], "", {"a": 1}),
    ([], '{"a":2}', {"a": 2}),
    ([], "", {}),
    (["null"], "", {}),
])
def test_payload_sources(args, stream, expected):
    assert envelope.read_payload(args, io.StringIO(stream)) == expected


def test_payload_on_stdin_is_read_as_utf8_whatever_the_console_encoding():
    stream = io.TextIOWrapper(io.BytesIO('{"a":"é"}'.encode("utf-8")), encoding="cp1252")
    assert envelope.read_payload([], stream) == {"a": "é"}


def test_serve_answers_a_crash_as_one_object(capsys):
    def boom(_):
        raise ValueError("inner")
    assert envelope.serve({"v": boom}, ["v", "{}"]) == 1
    answer = json.loads(capsys.readouterr().out)
    assert answer["error"]["code"] == "internal" and "inner" in answer["error"]["reason"]


def test_serve_names_the_verbs_on_an_unknown_verb(capsys):
    assert envelope.serve({"known": lambda _: envelope.ok()}, ["other"]) == 2
    answer = json.loads(capsys.readouterr().out)
    assert answer["error"]["code"] == "unknown-verb" and "known" in answer["error"]["reason"]


def test_serve_exits_with_the_answers_own_code(capsys):
    def refuse(_):
        raise envelope.Refusal("stale", "changed", extra_field="kept")
    assert envelope.serve({"v": refuse}, ["v", "{}"]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["extra_field"] == "kept"


def test_need_refuses_missing_and_empty():
    assert envelope.need({"a": "x"}, "a") == "x"
    assert envelope.need({"a": 0}, "a") == 0
    for payload in ({}, {"a": None}, {"a": ""}):
        with pytest.raises(envelope.Refusal) as caught:
            envelope.need(payload, "a")
        assert caught.value.code == "bad-payload"
