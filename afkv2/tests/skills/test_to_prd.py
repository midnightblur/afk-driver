"""Tests for the to-prd skill.

The sequence tests take every command from the fenced `sh step=...` blocks of SKILL.md, so a command the skill
states is a command that ran. The tracker port, config reader and renderer are recorded fakes (fakes/) in a throwaway
plugin tree. When the real port is present, `test_real_port_*` runs the same sequence through it, against a local
HTTP stand-in for Jira. No test sends anything to a real tracker.
"""

import base64
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
SKILL_DIR = SKILLS / "to-prd"
SKILL_MD = SKILL_DIR / "SKILL.md"
FAKES = Path(__file__).resolve().parent / "fakes"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import prd_files  # noqa: E402
import publish  # noqa: E402

_spec = importlib.util.spec_from_file_location("fake_v1_facts", FAKES / "fake_v1_facts.py")
V1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V1)

STEP = re.compile(r"^ *```sh step=([\w-]+)\n *(.*?)\n *```", re.S | re.M)
WRITE_VERBS = {"attachment-put", "attachment-delete", "description-put"}
KEY = "PROJ-1"
DIAGRAM = "flowchart LR\n  A[start] --> B[end]"
BEGIN = "afkv2:prd:start"
END = "afkv2:prd:end"

PRD = f"""# PRD — shop

## Problem Statement

A buyer cannot see the total.

## Solution

The basket shows the total.

## User Stories

1. As a buyer, I want the total, so that I can decide.

## Acceptance Criteria

- [ ] AC-001 The basket shows the total.
- [ ] AC-002 An empty basket shows zero.

## Worked examples

### WE-01 — frequent: one item

```mermaid
{DIAGRAM}
```

Total 5 for 1 item.

## Access & validation policy

Buyer only.

## Implementation Decisions

None.

## Testing Decisions

Behaviour.

## Out of Scope

Tax.

## Further Notes

None.
"""


def skill_steps():
    return dict(STEP.findall(SKILL_MD.read_text("utf-8")))


def picture(answer, number=1):
    return publish.picture_name(answer["receipt"], number)


def paragraph(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def doc(*texts):
    return {"type": "doc", "version": 1, "content": [paragraph(text) for text in texts]}


class World:
    def __init__(self, root, config=None):
        self.root, self.plugin, self.repo = root, root / "plugin", root / "repo"
        self.calls, self.state_file = root / "calls.log", root / "jira.json"
        for skill in ("to-prd", "grill"):
            shutil.copytree(SKILLS / skill, self.plugin / "skills" / skill, ignore=shutil.ignore_patterns("__pycache__"))
        for fake, target in (("fake_jira_port.py", "ports/tracker/cli.py"), ("fake_v1_facts.py", "ports/tracker/fake_v1_facts.py"),
                             ("fake_config.py", "scripts/afkv2_config.py")):
            (self.plugin / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(FAKES / fake, self.plugin / target)
        self.repo.mkdir()
        (self.repo / ".afkv2").mkdir()
        (self.repo / ".afkv2" / "config.json").write_text(
            json.dumps(config or {"spec_folder": "specs", "tracker": {"kind": "jira"}}), "utf-8")
        self.spec = self.repo / "specs" / KEY
        (self.spec / "pages").mkdir(parents=True)
        (self.spec / "pages" / "grill-s-1.json").write_text("{}", "utf-8")
        self.log = self.spec / "GRILL-LOG.md"
        self.log.write_text("## Requirements grill\n- Settled: exit gate passed 2026-10-30 · session s-1\n", "utf-8")
        self.prd = self.spec / "PRD.md"
        self.prd.write_text(PRD, "utf-8")
        self.run_dir = self.spec / "run"
        self.published = self.repo / "data" / "published-tickets.txt"
        bin_dir = root / "bin"
        bin_dir.mkdir()
        shutil.copy(FAKES / "fake_mmdc.py", bin_dir / "fake_mmdc.py")
        (bin_dir / "mmdc.cmd").write_text(f'@"{sys.executable}" "%~dp0fake_mmdc.py" %*\r\n', "utf-8")
        script = bin_dir / "mmdc"
        script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/fake_mmdc.py" "$@"\n', "utf-8")
        script.chmod(0o755)
        self.env = {"FAKE_CALL_LOG": str(self.calls), "FAKE_JIRA_STATE": str(self.state_file),
                    "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
        self.set_ticket(None)

    def set_ticket(self, description, attachments=()):
        self.state_file.write_text(json.dumps({
            "issues": {KEY: {"description": description, "attachments": list(attachments)}}, "next": 100}), "utf-8")

    def ticket(self):
        return json.loads(self.state_file.read_text("utf-8"))["issues"][KEY]

    def edit_ticket(self, text):
        state = json.loads(self.state_file.read_text("utf-8"))
        state["issues"][KEY]["description"]["content"].append(paragraph(text))
        self.state_file.write_text(json.dumps(state), "utf-8")

    def run(self, step, expect=0, **values):
        command = skill_steps()[step]
        filled = {"python": Path(sys.executable), "this skill's folder": self.plugin / "skills" / "to-prd",
                  **values, **{k.replace("_", " "): v for k, v in values.items()}}
        for name, value in filled.items():
            command = command.replace(f"<{name}>", Path(value).as_posix() if isinstance(value, Path) else str(value))
        left = re.findall(r"<[^<>]+>", command)
        assert not left, f"{step}: unfilled {left}"
        run = subprocess.run(shlex.split(command), cwd=self.repo, capture_output=True, text=True, timeout=120,
                             env={**os.environ, **self.env}, encoding="utf-8")
        assert run.returncode == expect, f"{step}: {run.returncode}\n{run.stdout}\n{run.stderr}"
        return json.loads(run.stdout)

    def preview(self, expect=0, ticket=KEY):
        return self.run("preview", expect=expect, ticket_key=ticket, prd=self.prd, run_dir=self.run_dir)

    def publish(self, answer, expect=0, receipt=None):
        return self.run("publish", expect=expect, preview=Path(answer["preview"]), receipt=receipt or answer["receipt"])

    def preview_and_publish(self):
        answer = self.preview()
        return answer, self.publish(answer)

    def verbs(self):
        return [line.split()[0] for line in self.calls.read_text("utf-8").splitlines()] if self.calls.exists() else []

    def clear_calls(self):
        self.calls.unlink(missing_ok=True)

    def writes(self):
        return [verb for verb in self.verbs() if verb in WRITE_VERBS]

    def names(self):
        return [item["filename"] for item in self.ticket()["attachments"]]

    def lines(self):
        return self.published.read_text("utf-8").splitlines() if self.published.exists() else []

    def block_nodes(self):
        content = self.ticket()["description"]["content"]
        texts = [publish_text(node) for node in content]
        return content[texts.index(BEGIN) + 1:texts.index(END)]

    def block_text(self):
        return "\n".join(publish_text(node) for node in self.block_nodes())


def publish_text(node):
    if node.get("type") == "text":
        return node.get("text") or ""
    return "".join(publish_text(child) for child in node.get("content") or [])


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


# --- unit ---


def test_ids_present_reads_whole_ids():
    assert publish.check_ids_present("AC-001 and WE-01", "WE-01 then AC-001") == ["AC-001", "WE-01"]
    with pytest.raises(publish.Refusal) as refused:
        publish.check_ids_present("AC-001 and WE-02", "AC-0011 and WE-020 and XWE-02")
    assert refused.value.code == "missing-ids"
    assert refused.value.extra["missing"] == ["AC-001", "WE-02"]


def test_receipt_is_the_sha256_of_key_text_and_picture_hashes():
    expected = hashlib.sha256(b"PROJ-1the textaabb").hexdigest()
    assert publish.compute_receipt("PROJ-1", "the text", ["aa", "bb"]) == expected
    assert publish.compute_receipt("PROJ-2", "the text", ["aa", "bb"]) != expected
    assert publish.compute_receipt("PROJ-1", "other", ["aa", "bb"]) != expected
    assert publish.compute_receipt("PROJ-1", "the text", ["bb", "aa"]) != expected


def test_picture_name_carries_8_characters_of_the_receipt():
    assert publish.picture_name("abcdef0123456789", 2) == "afkv2-fig-abcdef01-2.png"
    assert publish.PICTURE_NAME.fullmatch(publish.picture_name("abcdef0123456789", 2))


def test_published_line_has_the_three_fields():
    now = datetime(2026, 10, 30, 12, 0, 5, tzinfo=timezone.utc)
    assert publish.published_line(now, "PROJ-1", "abcdef0123") == "2026-10-30T12:00:05Z PROJ-1 abcdef01"


def test_extract_mermaid_takes_only_top_level_fences():
    text = "a\n\n```mermaid\nX --> Y\n```\n\n````markdown\n```mermaid\nnot a figure\n```\n````\n\n```\nmermaid\n```\n\n~~~mermaid\nZ\n~~~\nb"
    body, sources = publish.extract_mermaid(text, "T{}T")
    assert sources == ["X --> Y", "Z"]
    assert "T0T" in body and "T1T" in body and "not a figure" in body
    assert "X --> Y" not in body


def test_extract_mermaid_refuses_an_open_fence():
    with pytest.raises(publish.Refusal) as refused:
        publish.extract_mermaid("```mermaid\nX", "T{}T")
    assert refused.value.code == "bad-prd"


def test_check_refuses_missing_sections_and_ids():
    good = PRD
    assert prd_files.id_problems(good) == []
    assert any("Worked examples" in item for item in prd_files.id_problems(good.replace("## Worked examples", "## Examples")))
    assert any("no id on" in item for item in prd_files.id_problems(good.replace("AC-002 ", "")))
    assert any("defined twice" in item for item in prd_files.id_problems(good.replace("AC-002", "AC-001")))
    assert any("no id on" in item for item in prd_files.id_problems(good.replace("WE-01 ", "")))
    assert any("no acceptance" in item for item in prd_files.id_problems(good.replace("- [ ] AC-001 The basket shows the total.\n", "").replace("- [ ] AC-002 An empty basket shows zero.\n", "")))


@pytest.mark.parametrize("change, word", [
    (lambda text: text.replace("- [ ] AC-002 An empty basket shows zero.\n", ""), "AC-002 is gone"),
    (lambda text: text.replace("### WE-01 ", "### WE-02 "), "WE-01 is gone"),
    (lambda text: text.replace("AC-001 The basket", "AC-X The basket").replace("AC-002 An empty", "AC-001 An empty").replace("AC-X The basket", "AC-002 The basket"), "never renumbered"),
    (lambda text: text.replace("- [ ] AC-001", "- [ ] AC-003 A new first line.\n- [ ] AC-001").replace("AC-002 An empty basket shows zero.", "AC-002 retired: not wanted"), None),
])
def test_ids_are_never_renumbered(change, word):
    problems = prd_files.renumber_problems(PRD, change(PRD))
    if word:
        assert any(word in item for item in problems), problems
    else:
        assert problems == []


def test_a_new_id_below_the_highest_is_a_reused_id():
    old = PRD.replace("- [ ] AC-002 An empty", "- [ ] AC-009 Late.\n- [ ] AC-002 An empty")
    new = old.replace("- [ ] AC-002 An empty", "- [ ] AC-005 Reused gap.\n- [ ] AC-002 An empty")
    assert any("never reused" in item for item in prd_files.renumber_problems(old, new))


def test_2_criteria_with_one_text_stay_valid_when_nothing_moved():
    old = PRD.replace("AC-002 An empty basket shows zero.", "AC-002 The basket shows the total.")
    assert prd_files.renumber_problems(old, old) == []


def test_check_compares_with_the_last_commit(world):
    def git(*args):
        subprocess.run(["git", *args], cwd=world.repo, check=True, capture_output=True)

    git("init", "-q")
    assert world.run("check", prd=world.prd)["compared_with_commit"] is False
    git("add", "specs/PROJ-1/PRD.md")
    git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "prd")
    assert world.run("check", prd=world.prd)["compared_with_commit"] is True
    world.prd.write_text(PRD.replace("- [ ] AC-002 An empty basket shows zero.\n", ""), "utf-8")
    assert "AC-002 is gone" in world.run("check", expect=1, prd=world.prd)["error"]["reason"]


def test_every_section_of_the_check_stands_in_the_format():
    text = (SKILL_DIR / "PRD-FORMAT.md").read_text("utf-8")
    for name in prd_files.SECTIONS:
        assert f"| {name} |" in text


def test_only_this_skill_names_a_jira_write_verb():
    for path in SKILLS.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.is_relative_to(SKILL_DIR):
            continue
        text = path.read_text("utf-8", "replace")
        assert not any(verb in text for verb in WRITE_VERBS), f"{path} names a Jira write verb"


def test_skill_has_the_frontmatter_and_the_order():
    text = SKILL_MD.read_text("utf-8")
    assert re.match(r"---\nname: to-prd\ndescription: \S", text)
    order = [text.index(f"step={step}") for step in ("start", "check", "index", "preview", "publish")]
    assert order == sorted(order)
    assert "ask" in text[text.index("step=preview"):text.index("step=publish")].lower()


# --- start and INDEX.md ---


def test_start_answers_the_paths(world):
    answer = world.run("start", ticket_key=KEY)
    assert Path(answer["prd"]) == Path(world.prd)
    assert Path(answer["run_dir"]) == Path(world.run_dir)
    assert answer["tracker_kind"] == "jira" and answer["resume"] is True
    assert answer["session"] == "s-1"


def test_start_refuses_a_grill_that_did_not_pass_its_gate(world):
    world.log.write_text("## Requirements grill\n- Open: a point · card c1\n", "utf-8")
    error = world.run("start", expect=1, ticket_key=KEY)["error"]
    assert error["code"] == "missing-input" and error["writer"] == "/afkv2:grill"


def test_start_refuses_a_gate_of_an_older_session(world):
    (world.spec / "pages" / "grill-s-2.json").write_text("{}", "utf-8")
    assert world.run("start", expect=1, ticket_key=KEY)["error"]["code"] == "missing-input"


def test_start_refuses_a_pending_row_and_lists_external_claims(world):
    gate = world.log.read_text("utf-8")
    world.log.write_text(gate + "- Ledger: a claim → unverified-external (human acknowledged)\n", "utf-8")
    assert world.run("start", ticket_key=KEY)["unverified_external"] == ["a claim"]
    world.log.write_text(gate + "- Ledger: b claim → pending\n", "utf-8")
    assert world.run("start", expect=1, ticket_key=KEY)["error"]["missing"] == ["b claim"]


def test_index_is_seeded_from_the_format_and_keeps_other_rows(world):
    adr_dir = world.spec / "adr" / "requirements"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-a.md").write_text("# a\n", "utf-8")
    summary = world.root / "summary.txt"
    summary.write_text("The basket shows a total.\n", "utf-8")
    index = world.spec / "INDEX.md"
    answer = world.run("index", index=index, ticket_key=KEY, summary_file=summary, adr_dir=adr_dir)
    assert answer["requirement_adrs"] == 1
    text = index.read_text("utf-8")
    assert text.startswith(f"# {KEY} — start here\n\nThe basket shows a total.\n")
    assert "| PRD | PRD.md | draft |" in text and "| Requirement ADRs | adr/requirements/ | 1 records |" in text
    assert "| SDD | SDD.md | — |" in text and "## Reading order" in text

    prd_files.set_row(index, "SDD", "SDD.md", "draft")
    summary.write_text("A new summary.\n", "utf-8")
    world.run("index", index=index, ticket_key=KEY, summary_file=summary, adr_dir=adr_dir)
    text = index.read_text("utf-8")
    assert "| SDD | SDD.md | draft |" in text and "A new summary." in text and "The basket shows" not in text


# --- the publish sequence ---


def test_first_publish_appends_and_keeps_the_rest_in_order(world):
    before = doc("Context from PO")
    world.set_ticket(before)
    answer = world.preview()
    assert world.writes() == []
    assert world.ticket()["description"] == before
    assert answer["action"] == "appends the block at the end of the description"
    assert answer["already_published"] is False
    assert world.verbs() == ["issue-get", "md-to-adf", "md-to-adf", "attachment-list"]
    world.clear_calls()

    done = world.publish(answer)
    assert world.verbs() == ["issue-get", "attachment-list", "attachment-put", "md-to-adf", "description-put",
                             "issue-get", "attachment-list"]
    assert done["published"] is True and done["replaced"] is None
    content = world.ticket()["description"]["content"]
    assert content[0] == before["content"][0]
    assert publish_text(content[1]) == BEGIN and publish_text(content[-1]) == END
    assert world.names() == [picture(answer)]


def test_a_ticket_with_no_description_gets_the_block(world):
    done = world.preview_and_publish()[1]
    assert done["published"] is True
    assert "AC-001" in world.block_text()


def test_a_no_answer_writes_nothing(world):
    world.set_ticket(doc("Context"))
    state = world.state_file.read_bytes()
    world.preview()
    assert world.state_file.read_bytes() == state
    assert not (world.lines())


def test_preview_page_shows_the_exact_text_and_the_pictures(world):
    answer = world.preview()
    page = Path(answer["page"]).read_text("utf-8")
    picture = Path(answer["pictures"][0])
    assert answer["page_url"].startswith("file:")
    assert base64.b64encode(picture.read_bytes()).decode("ascii") in page
    preview = json.loads(Path(answer["preview"]).read_text("utf-8"))
    for line in preview["block_text"].split("\n"):
        assert line.replace("&", "&amp;") in page
    assert answer["receipt"][:8] in page
    assert picture.name == publish.picture_name(answer["receipt"], 1)
    assert preview["picture_hashes"] == [hashlib.sha256(picture.read_bytes()).hexdigest()]
    assert (world.run_dir / ".gitignore").read_text("utf-8") == "*\n"


def test_preview_page_escapes_the_text():
    html_text = publish._html([paragraph('<script>alert("x")</script>')], {})
    assert "<script>" not in html_text and "&lt;script&gt;" in html_text


def test_v1_block_is_replaced_and_v1_pictures_go_after_the_read_back(world):
    before = {"type": "doc", "version": 1, "content": [
        paragraph("Before"), paragraph(V1.BEGIN_LINE_NOTE), paragraph("old PRD"), paragraph(V1.END_LINE), paragraph("After")]}
    attachments = [{"id": "1", "filename": V1.PICTURE}, {"id": "2", "filename": V1.SECOND_PICTURE},
                   {"id": "3", "filename": V1.LOOKALIKE_PICTURE}, {"id": "4", "filename": "design.pdf"}]
    world.set_ticket(before, attachments)
    answer = world.preview()
    assert answer["action"] == "replaces the v1 block"
    world.clear_calls()
    done = world.publish(answer)
    assert done["replaced"] == "v1"
    assert sorted(done["deleted"]) == sorted([V1.PICTURE, V1.SECOND_PICTURE])
    verbs = world.verbs()
    assert verbs.index("description-put") < len(verbs) - 1 - verbs[::-1].index("issue-get") < verbs.index("attachment-delete")
    assert set(world.names()) == {V1.LOOKALIKE_PICTURE, "design.pdf", picture(answer)}
    content = world.ticket()["description"]["content"]
    assert content[0] == before["content"][0] and content[-1] == before["content"][-1]
    assert "old PRD" not in json.dumps(content)


def test_republish_replaces_the_pictures_and_adds_no_copy(world):
    world.set_ticket(doc("Context"))
    first = world.preview_and_publish()[0]
    world.prd.write_text(PRD.replace("A[start]", "A[begin]").replace("Total 5", "Total 6"), "utf-8")
    second, done = world.preview_and_publish()
    assert done["replaced"] == "afkv2"
    assert second["receipt"] != first["receipt"]
    assert world.names() == [picture(second)]
    assert done["deleted"] == [picture(first)]
    text = json.dumps(world.ticket()["description"])
    assert text.count(BEGIN) == 1
    assert "Total 6" in text and "Total 5" not in text


def test_rerun_after_success_writes_nothing(world):
    world.set_ticket(doc("Context"))
    answer, _ = world.preview_and_publish()
    assert len(world.lines()) == 1
    world.clear_calls()
    state = world.state_file.read_bytes()
    done = world.publish(answer)
    assert done["published"] is False and done["already_published"] is True
    assert world.writes() == [] and world.state_file.read_bytes() == state
    assert len(world.lines()) == 1

    again = world.preview()
    assert again["already_published"] is True and again["receipt"] == answer["receipt"]
    assert world.writes() == []


def test_rerun_with_a_renderer_that_varies_keeps_the_receipt(world):
    world.env["FAKE_MMDC_VARY"] = "1"
    answer, _ = world.preview_and_publish()
    world.clear_calls()
    again = world.preview()
    assert again["receipt"] == answer["receipt"] and again["already_published"] is True


def test_equal_text_with_another_picture_is_not_already_published(world):
    answer, _ = world.preview_and_publish()
    state = json.loads(world.state_file.read_text("utf-8"))
    for item in state["issues"][KEY]["description"]["content"]:
        for child in item.get("content") or []:
            if child.get("type") == "media":
                child["attrs"]["id"] = "someone-elses-media"
    world.state_file.write_text(json.dumps(state), "utf-8")
    assert world.preview()["already_published"] is False


def test_each_publish_appends_one_line(world):
    world.set_ticket(doc("Context"))
    first = world.preview_and_publish()[0]
    world.prd.write_text(PRD.replace("Total 5", "Total 6"), "utf-8")
    second = world.preview_and_publish()[0]
    lines = world.lines()
    assert [line.split()[1:] for line in lines] == [[KEY, first["receipt"][:8]], [KEY, second["receipt"][:8]]]
    assert all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", line.split()[0]) for line in lines)


def test_index_row_reads_published_after_the_read_back(world):
    index = world.spec / "INDEX.md"
    index.write_text("# PROJ-1\n\n## Artifacts\n\n| Artifact | Where | State |\n|---|---|---|\n| PRD | PRD.md | draft |\n", "utf-8")
    world.env["FAKE_JIRA_CORRUPT"] = "text"
    answer = world.preview()
    world.publish(answer, expect=1)
    assert "| PRD | PRD.md | draft |" in index.read_text("utf-8")
    del world.env["FAKE_JIRA_CORRUPT"]
    world.preview_and_publish()
    assert re.search(r"\| PRD \| PRD\.md \| published to Jira \d{4}-\d\d-\d\d \|", index.read_text("utf-8"))


def test_stale_after_the_preview_uploads_nothing_and_asks_again(world):
    world.set_ticket(doc("Context"))
    answer = world.preview()
    world.edit_ticket("the PO edited")
    world.clear_calls()
    assert world.publish(answer, expect=1)["error"]["code"] == "stale"
    assert world.writes() == []
    again = world.preview()
    world.publish(again)
    assert "the PO edited" in json.dumps(world.ticket()["description"])
    assert world.block_text()


def test_stale_at_the_write_writes_no_block_and_the_rerun_adds_no_copy(world):
    world.set_ticket(doc("Context"))
    answer = world.preview()
    world.env["FAKE_JIRA_EDIT_ON_PUT"] = "edited at that moment"
    assert world.publish(answer, expect=1)["error"]["code"] == "stale"
    del world.env["FAKE_JIRA_EDIT_ON_PUT"]
    assert BEGIN not in json.dumps(world.ticket()["description"])
    assert len(world.names()) == 1
    world.clear_calls()
    again = world.preview()
    assert again["receipt"] == answer["receipt"]
    done = world.publish(again)
    assert "attachment-put" not in world.verbs()
    assert done["published"] is True and len(world.names()) == 1


@pytest.mark.parametrize("texts, word", [
    (["x", BEGIN, "y"], "without an end"),
    (["x", END, "y"], "without a begin"),
    ([BEGIN, "a", END, BEGIN, "b", END], "doubled"),
])
def test_bad_block_is_named_and_nothing_is_written(world, texts, word):
    world.set_ticket(doc(*texts))
    state = world.state_file.read_bytes()
    error = world.preview(expect=1)["error"]
    assert error["code"] == "bad-block" and word in error["reason"]
    assert world.writes() == [] and world.state_file.read_bytes() == state


def test_bad_block_from_the_port_is_named(world):
    answer = world.preview()
    world.env["FAKE_JIRA_FAIL"] = "description-put:bad-block"
    assert world.publish(answer, expect=1)["error"]["code"] == "bad-block"
    assert world.lines() == []


def test_a_marker_as_a_part_of_a_line_is_no_block(world):
    world.set_ticket(doc(f"see {BEGIN} in the notes"))
    assert world.preview()["action"].startswith("appends")


def test_wrong_receipt_is_refused_and_nothing_is_written(world):
    answer = world.preview()
    world.clear_calls()
    assert world.publish(answer, expect=1, receipt="0" * 64)["error"]["code"] == "bad-receipt"
    assert world.verbs() == []


def test_a_changed_picture_or_preview_is_refused(world):
    answer = world.preview()
    picture = Path(answer["pictures"][0])
    good = picture.read_bytes()
    picture.write_bytes(good + b"x")
    assert world.publish(answer, expect=1)["error"]["code"] == "bad-receipt"
    picture.write_bytes(good)
    preview_file = Path(answer["preview"])
    preview = json.loads(preview_file.read_text("utf-8"))
    preview["block_text"] = "other"
    preview_file.write_text(json.dumps(preview), "utf-8")
    assert world.publish(answer, expect=1)["error"]["code"] == "bad-receipt"
    assert world.verbs().count("attachment-put") == 0


def test_bad_receipt_from_the_port_stops_the_publish(world):
    answer = world.preview()
    world.env["FAKE_JIRA_FAIL"] = "description-put:bad-receipt"
    assert world.publish(answer, expect=1)["error"]["code"] == "bad-receipt"
    assert BEGIN not in json.dumps(world.ticket()["description"] or {})
    assert world.lines() == []


@pytest.mark.parametrize("corrupt, field", [("text", "text"), ("media", "media ids")])
def test_read_back_mismatch_is_a_failed_publish_and_old_pictures_stay(world, corrupt, field):
    world.set_ticket(doc("Context"), [{"id": "1", "filename": V1.PICTURE}])
    answer = world.preview()
    world.env["FAKE_JIRA_CORRUPT"] = corrupt
    error = world.publish(answer, expect=1)["error"]
    assert error["code"] == "read-back-mismatch" and field in error["differs"]
    assert V1.PICTURE in world.names()
    assert "attachment-delete" not in world.verbs()
    assert world.lines() == []


def test_short_sections_around_the_block_stay_unchanged(world):
    before = {"type": "doc", "version": 1, "content": [
        paragraph("TBD"), paragraph(BEGIN), paragraph("old"), paragraph(END), paragraph("x")]}
    world.set_ticket(before)
    world.preview_and_publish()
    content = world.ticket()["description"]["content"]
    assert json.dumps(content[0]) == json.dumps(before["content"][0])
    assert json.dumps(content[-1]) == json.dumps(before["content"][-1])


def test_short_description_with_no_block_stays(world):
    before = doc("TBD")
    world.set_ticket(before)
    world.preview_and_publish()
    assert world.ticket()["description"]["content"][0] == before["content"][0]


def test_a_missing_id_refuses_before_any_write(world):
    world.env["FAKE_JIRA_DROP"] = "AC-002"
    error = world.preview(expect=1)["error"]
    assert error["code"] == "missing-ids" and error["missing"] == ["AC-002"]
    assert world.writes() == []


def test_an_id_lost_after_the_preview_refuses_before_the_write(world):
    answer = world.preview()
    world.env["FAKE_JIRA_DROP"] = "WE-01"
    error = world.publish(answer, expect=1)["error"]
    assert error["code"] == "missing-ids" and error["missing"] == ["WE-01"]
    assert "description-put" not in world.verbs()


def test_upload_failure_writes_no_block(world):
    world.set_ticket(doc("Context"))
    answer = world.preview()
    world.env["FAKE_JIRA_FAIL"] = "attachment-put:server-error"
    assert world.publish(answer, expect=1)["error"]["code"] == "server-error"
    assert "description-put" not in world.verbs()


def test_write_failure_after_uploads_is_safe_to_run_again(world):
    world.set_ticket(doc("Context"))
    answer = world.preview()
    world.env["FAKE_JIRA_FAIL"] = "description-put:server-error"
    world.publish(answer, expect=1)
    del world.env["FAKE_JIRA_FAIL"]
    done = world.publish(answer)
    assert done["published"] is True and done["uploaded"] == []
    assert len(world.names()) == 1


def test_a_lost_upload_record_leaves_no_copy(world):
    world.set_ticket(doc("Context"))
    answer = world.preview()
    world.env["FAKE_JIRA_FAIL"] = "description-put:server-error"
    world.publish(answer, expect=1)
    del world.env["FAKE_JIRA_FAIL"]
    (world.run_dir / "uploads.json").unlink()
    done = world.publish(answer)
    assert done["uploaded"] and done["deleted"]
    assert len(world.names()) == 1


def _block_media(world):
    state = json.loads(world.state_file.read_text("utf-8"))
    return [child["attrs"]["id"] for item in state["issues"][KEY]["description"]["content"]
            for child in item.get("content") or [] if child.get("type") == "media"]


def test_no_upload_record_does_not_count_as_published_and_the_picture_in_use_stays(world):
    first, _ = world.preview_and_publish()
    old_media = _block_media(world)
    world.prd.write_text(PRD.replace(DIAGRAM, DIAGRAM + "\n  B --> C[more]"), "utf-8")
    second = world.preview()
    assert second["receipt"] != first["receipt"]
    world.env["FAKE_JIRA_FAIL"] = "description-put:server-error"
    world.publish(second, expect=1)
    del world.env["FAKE_JIRA_FAIL"]
    (world.run_dir / "uploads.json").unlink()
    assert _block_media(world) == old_media and picture(first) in world.names()

    world.clear_calls()
    again = world.preview()
    assert again["receipt"] == second["receipt"] and again["already_published"] is False
    assert world.writes() == []
    done = world.publish(again)
    assert done["published"] is True and done["already_published"] is False
    assert _block_media(world) != old_media
    assert picture(first) in done["deleted"] and world.names() == [picture(second)]


def test_a_failed_delete_is_reported_and_the_next_run_removes_it(world):
    world.set_ticket(doc("Context"), [{"id": "1", "filename": V1.PICTURE}])
    answer = world.preview()
    world.env["FAKE_JIRA_FAIL"] = "attachment-delete:server-error"
    done = world.publish(answer)
    assert done["published"] is True and done["not_deleted"][0]["filename"] == V1.PICTURE
    assert len(world.lines()) == 1
    del world.env["FAKE_JIRA_FAIL"]
    again = world.publish(answer)
    assert again["already_published"] is True and again["deleted"] == [V1.PICTURE]
    assert len(world.lines()) == 1


def test_a_prd_with_no_diagram_publishes_with_no_picture(world):
    world.prd.write_text(PRD.replace(f"```mermaid\n{DIAGRAM}\n```\n", ""), "utf-8")
    answer, done = world.preview_and_publish()
    assert answer["pictures"] == [] and done["published"] is True and world.names() == []
    world.clear_calls()
    assert world.publish(answer)["already_published"] is True


def test_2_equal_diagrams_get_2_pictures(world):
    world.prd.write_text(PRD.replace("Total 5", f"```mermaid\n{DIAGRAM}\n```\n\nTotal 5"), "utf-8")
    answer, _ = world.preview_and_publish()
    assert len(answer["pictures"]) == 2 and len(world.names()) == 2


def test_a_render_failure_is_named(world):
    world.env["FAKE_MMDC_FAIL"] = "1"
    error = world.preview(expect=1)["error"]
    assert error["code"] == "render-failed" and "refused" in error["reason"]
    assert world.writes() == []


def test_no_renderer_is_named(tmp_path, monkeypatch):
    monkeypatch.setattr(publish.shutil, "which", lambda name: None)
    with pytest.raises(publish.Refusal) as refused:
        publish.render_mermaid("x", tmp_path / "out.png", tmp_path)
    assert refused.value.code == "render-failed" and "mermaid-cli" in refused.value.reason
    assert not (tmp_path / "diagram.mmd").exists()


def test_a_failed_mmdc_does_not_fall_back_to_a_download(tmp_path, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command[0])
        return subprocess.CompletedProcess(command, 1, "", "syntax error in the diagram")

    monkeypatch.setattr(publish.shutil, "which", lambda name: name)
    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    with pytest.raises(publish.Refusal) as refused:
        publish.render_mermaid("x", tmp_path / "out.png", tmp_path)
    assert calls == ["mmdc"] and "syntax error" in refused.value.reason


def test_a_github_tracker_publishes_nothing(tmp_path):
    world = World(tmp_path, {"spec_folder": "specs", "tracker": {"kind": "github-issues", "repo": "acme/shop"}})
    assert world.preview(expect=1)["error"]["code"] == "not-jira"
    assert world.verbs() == []


def test_a_crlf_prd_gives_the_same_receipt(world):
    first = world.preview()["receipt"]
    world.prd.write_bytes(PRD.replace("\n", "\r\n").encode("utf-8"))
    assert world.preview()["receipt"] == first


# --- the real port against a local stand-in for Jira ---


def _port_tree():
    tree = os.environ.get("AFKV2_TEST_PORT_TREE")
    return Path(tree) if tree else PLUGIN / "ports" / "tracker"


class _LocalJira(BaseHTTPRequestHandler):
    issue = {"description": None}
    attachments = {}
    counter = [0]

    def log_message(self, *args):
        pass

    def _send(self, code, body=None, headers=()):
        self.send_response(code)
        for name, value in headers:
            self.send_header(name, value)
        data = b"" if body is None else json.dumps(body).encode("utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/rest/api/3/issue/"):
            fields = {"description": self.issue["description"],
                      "attachment": [{"id": key, "filename": name} for key, name in self.attachments.items()]}
            return self._send(200, {"key": KEY, "id": "1", "fields": fields})
        number = path.rsplit("/", 1)[1]
        if "/attachment/content/" in path:
            location = f"http://127.0.0.1/file/{'0' * 32}{int(number):04d}/binary"
            location = location.replace("0" * 36, "00000000-0000-0000-0000-" + f"{int(number):012d}")
            return self._send(303, None, [("Location", location)])
        if number in self.attachments:
            return self._send(200, {"id": number, "filename": self.attachments[number]})
        return self._send(404, {})

    def do_PUT(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).issue = {"description": body["fields"]["description"]}
        self._send(204)

    def do_POST(self):
        data = self.rfile.read(int(self.headers["Content-Length"]))
        name = re.search(rb'filename="([^"]+)"', data).group(1).decode()
        self.counter[0] += 1
        key = str(self.counter[0])
        self.attachments[key] = name
        self._send(200, [{"id": key, "filename": name}])

    def do_DELETE(self):
        self.attachments.pop(self.path.rsplit("/", 1)[1], None)
        self._send(204)


@pytest.fixture
def real_port_world(tmp_path):
    tree = _port_tree()
    if not (tree / "jira.py").is_file():
        pytest.skip("the tracker port is not on this branch yet")
    pytest.importorskip("markdown_it")
    world = World(tmp_path)
    target = world.plugin / "ports" / "tracker"
    shutil.rmtree(target)
    shutil.copytree(tree, target, ignore=shutil.ignore_patterns("__pycache__"))
    _LocalJira.issue = {"description": doc("Context from PO", "TBD")}
    _LocalJira.attachments = {}
    _LocalJira.counter[0] = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _LocalJira)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    world.env.update(JIRA_BASE_URL=f"http://127.0.0.1:{server.server_address[1]}", JIRA_EMAIL="test@example.invalid",
                     JIRA_API_TOKEN="not-a-token", NO_PROXY="127.0.0.1", no_proxy="127.0.0.1")
    yield world
    server.shutdown()
    server.server_close()


def test_real_port_runs_the_same_sequence(real_port_world):
    world = real_port_world
    before = json.loads(json.dumps(_LocalJira.issue["description"]["content"]))
    first, done = world.preview_and_publish()
    assert done["published"] is True and done["replaced"] is None
    content = _LocalJira.issue["description"]["content"]
    assert content[:2] == before
    assert list(_LocalJira.attachments.values()) == [picture(first)]

    again = world.publish(first)
    assert again["already_published"] is True and len(_LocalJira.attachments) == 1

    world.prd.write_text(PRD.replace("A[start]", "A[begin]").replace("Total 5", "Total 6"), "utf-8")
    second, redone = world.preview_and_publish()
    assert redone["replaced"] == "afkv2"
    assert list(_LocalJira.attachments.values()) == [picture(second)]
    assert _LocalJira.issue["description"]["content"][:2] == before
    assert json.dumps(_LocalJira.issue).count(BEGIN) == 1

    world.prd.write_text(PRD.replace("Total 5", "Total 7"), "utf-8")
    fresh = world.preview()
    _LocalJira.issue["description"]["content"].append(paragraph("edited"))
    assert world.publish(fresh, expect=1)["error"]["code"] == "stale"


def test_real_port_replaces_a_v1_block(real_port_world):
    world = real_port_world
    outside = [paragraph("Before"), paragraph("After")]
    _LocalJira.issue = {"description": {"type": "doc", "version": 1, "content": [
        outside[0], paragraph(V1.BEGIN_LINE), paragraph("old PRD"), paragraph(V1.END_LINE), outside[1]]}}
    _LocalJira.attachments = {"900": V1.PICTURE, "901": "design.pdf"}
    _LocalJira.counter[0] = 901
    answer = world.preview()
    assert answer["action"] == "replaces the v1 block"
    done = world.publish(answer)
    assert done["replaced"] == "v1" and done["deleted"] == [V1.PICTURE]
    content = _LocalJira.issue["description"]["content"]
    assert content[0] == outside[0] and content[-1] == outside[1]
    assert sorted(_LocalJira.attachments.values()) == sorted(["design.pdf", picture(answer)])
