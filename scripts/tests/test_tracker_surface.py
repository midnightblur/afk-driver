"""What a tracker command surface answers when the input or the answer is odd.

Two things are pinned here, for both tracker kinds:

- A payload that is not one JSON object is answered with the family's error
  object and exit 2 — never a Python traceback, which a caller cannot route on.
- A paginated `gh` answer arrives as one JSON document per page. Every page is
  read, and array pages are joined into the one list the caller asked for.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = PLUGIN_ROOT / "adapters" / "tracker"
KINDS = ("jira", "github-issues")


def load(kind: str):
    spec = importlib.util.spec_from_file_location(
        f"afk_tracker_{kind.replace('-', '_')}_surface", ADAPTERS / kind / "api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def surface(kind: str, *argv):
    return subprocess.run(
        [sys.executable, str(ADAPTERS / kind / "api.py"), *argv],
        capture_output=True, text=True, timeout=120, env=dict(os.environ),
    )


# ---- the payload ----------------------------------------------------------

@pytest.mark.parametrize("kind", KINDS)
def test_a_payload_that_is_not_json_is_an_answer(kind):
    done = surface(kind, "tracker_get", "{bad")
    assert done.returncode == 2
    assert "Traceback" not in done.stderr
    answer = json.loads(done.stdout)
    assert answer["error"] is True and answer["operation"] == "tracker_get"
    assert "not JSON" in answer["reason"]


@pytest.mark.parametrize("kind", KINDS)
def test_a_payload_that_is_not_an_object_is_an_answer(kind):
    done = surface(kind, "tracker_get", "[1, 2]")
    assert done.returncode == 2
    answer = json.loads(done.stdout)
    assert "JSON object" in answer["reason"]


@pytest.mark.parametrize("kind", KINDS)
def test_no_payload_is_still_an_empty_payload(kind):
    """An operation with no argument keeps reaching `call`, not the error path."""
    module = load(kind)
    payload, problem = module.payload_reader.parse(None, "tracker_get")
    assert problem is None and payload == {}


@pytest.mark.parametrize("kind", KINDS)
def test_the_operation_list_still_answers(kind):
    done = surface(kind, "--list-tools")
    assert done.returncode == 0 and "tracker_get" in done.stdout


# ---- the paginated answer -------------------------------------------------

TWO_PAGES = json.dumps([{"id": 1}, {"id": 2}]) + "\n" + json.dumps([{"id": 3}])


def gh_answering(text: str):
    """A `gh` that prints `text` and succeeds."""
    return mock.Mock(returncode=0, stdout=text, stderr="")


def test_every_page_of_a_paginated_answer_is_read():
    module = load("github-issues")
    with mock.patch.object(module.shutil, "which", return_value="gh"), \
         mock.patch.object(module.subprocess, "run", return_value=gh_answering(TWO_PAGES)):
        answer = module._gh("api", "repos/o/r/issues/1/timeline", "--paginate")
    assert answer == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_one_page_is_still_one_value():
    module = load("github-issues")
    single = json.dumps({"number": 7, "title": "one"})
    with mock.patch.object(module.shutil, "which", return_value="gh"), \
         mock.patch.object(module.subprocess, "run", return_value=gh_answering(single)):
        answer = module._gh("issue", "view", "7")
    assert answer == {"number": 7, "title": "one"}


def test_an_answer_that_is_not_json_is_still_reported_raw():
    module = load("github-issues")
    with mock.patch.object(module.shutil, "which", return_value="gh"), \
         mock.patch.object(module.subprocess, "run", return_value=gh_answering("not json")):
        answer = module._gh("issue", "view", "7")
    assert answer == {"raw": "not json"}
