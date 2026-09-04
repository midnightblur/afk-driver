"""Pins the frontmatter defect that hid `/afk:diagnose` from one harness.

Its description was a plain YAML scalar carrying `": "`, which parses as a
nested mapping rather than a string. The harness reported nothing: the skill
was simply not in the catalog, one entry short of the manifest, and every other
gate passed. These are fixtures, plus a live pin on the shipped tree.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hooks" / "lib"))

import skill_frontmatter_check as fc  # noqa: E402

GOOD = """---
name: widget
description: Does a thing. Use when the user asks for a thing.
---

body
"""


def write(tmp_path, name, text):
    d = tmp_path / "skills" / "utils" / name
    d.mkdir(parents=True)
    p = d / "SKILL.md"
    p.write_text(text, encoding="utf-8", newline="")
    return p


def test_a_well_formed_skill_has_no_problems(tmp_path):
    assert fc.check(write(tmp_path, "widget", GOOD)) == []


def test_colon_space_in_an_unquoted_description_is_reported(tmp_path):
    text = GOOD.replace("description: Does a thing.",
                        "description: Widget loop: does a thing.")
    problems = fc.check(write(tmp_path, "widget", text))
    assert len(problems) == 1
    assert "YAML" in problems[0] or "nested mapping" in problems[0]


def test_the_same_description_quoted_is_accepted(tmp_path):
    text = GOOD.replace("description: Does a thing. Use when the user asks for a thing.",
                        'description: "Widget loop: does a thing."')
    assert fc.check(write(tmp_path, "widget", text)) == []


def test_a_block_scalar_description_is_accepted(tmp_path):
    text = """---
name: widget
description: >
  Widget loop: does a thing.
  Use when the user asks for a thing.
---

body
"""
    assert fc.check(write(tmp_path, "widget", text)) == []


def test_name_must_match_the_directory(tmp_path):
    text = GOOD.replace("name: widget", "name: gadget")
    problems = fc.check(write(tmp_path, "widget", text))
    assert any("does not match its directory" in p for p in problems)


def test_a_missing_description_is_reported(tmp_path):
    text = "---\nname: widget\n---\n\nbody\n"
    problems = fc.check(write(tmp_path, "widget", text))
    assert any("no `description`" in p for p in problems)


def test_a_file_without_frontmatter_is_reported(tmp_path):
    problems = fc.check(write(tmp_path, "widget", "# Widget\n\nbody\n"))
    assert len(problems) == 1
    assert "no YAML frontmatter" in problems[0]


def test_a_byte_order_mark_is_reported(tmp_path):
    problems = fc.check(write(tmp_path, "widget", "﻿" + GOOD))
    assert any("byte-order mark" in p for p in problems)


def test_every_shipped_skill_frontmatter_loads():
    """Live pin: the tree as shipped must have nothing to report."""
    root = Path(__file__).resolve().parents[2]
    problems = []
    for skill in sorted((root / "skills").glob("*/*/SKILL.md")):
        problems += fc.check(skill)
    assert problems == []
