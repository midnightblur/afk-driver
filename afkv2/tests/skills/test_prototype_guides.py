"""The prototype guides: SKILL.md and its canvas rules MOCKUP.md (SDD §5, §6, §8; ticket 207 VR-004, VR-005, VR-006,
VR-016).

The quality of the rules is proved by the owner's live check; these tests pin that each rule is stated, in the file
and the section that owns it, and that every verb the guides name exists in its script.
"""

import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
HOME = PLUGIN / "skills" / "prototype"
SKILL_MD = HOME / "SKILL.md"
MOCKUP_MD = HOME / "MOCKUP.md"


def _flat(text):
    return " ".join(text.split())


def _text(path):
    assert path.is_file(), f"no {path.name} in {HOME}"
    return path.read_text("utf-8")


def _section(path, heading):
    """The text under `heading` up to the next heading of the same or a higher level, on 1 line."""
    text = _text(path)
    level, title = heading.split(" ", 1)
    found = re.search(rf"^{level} +{re.escape(title.strip())}[ \t]*\n", text, re.M)
    assert found, f"{path.name}: no heading {heading!r}"
    rest = text[found.end():]
    stop = re.search(rf"^#{{1,{len(level)}}} ", rest, re.M)
    return _flat(rest[:stop.start()] if stop else rest)


# --- VR-005 (PRD AC-001): a PRD with no screen story stops with no_ui and writes nothing

def test_no_screen_story_stops_with_no_ui():
    gate = _section(SKILL_MD, "## No screen, no mockup")
    assert "`no_ui`" in gate
    assert "no story adds or changes a screen" in gate
    assert "writes no file" in gate
    assert "leaves the `INDEX.md` Prototype row as it is" in gate


# --- VR-006 (PRD AC-014): "chat only", at any time, ends lavish and takes every later note in chat

def test_chat_only_ends_lavish_for_the_run():
    loop = _section(SKILL_MD, "## Notes loop")
    chat_only = _section(SKILL_MD, "### Chat only")
    assert '"chat only"' in chat_only and "at any time" in chat_only
    assert "run `end`" in chat_only
    assert "every later note of this run in chat" in chat_only
    assert "never shows the mockup in lavish again" in chat_only
    assert "chat only" in loop.split("### Chat only")[0], "the loop picks lavish only when the developer did not ask for chat only"


# --- VR-016 (PRD AC-007, AC-013): clickable from the entry screen, and each note gets an edit or a reply

def test_each_note_gets_an_edit_or_a_reply_and_a_new_show():
    loop = _section(SKILL_MD, "## Notes loop")
    assert "an edit of the mockup or a reply" in loop
    assert "run `show` again" in loop
    assert "selector" in loop and "tag" in loop and "text" in loop
    chat = _section(SKILL_MD, "### In chat")
    assert "`file://` path" in chat and "an edit of the mockup or a reply" in chat


def test_mockup_is_clickable_from_the_entry_screen_inside_the_shell():
    shell = _section(MOCKUP_MD, "## App shell and neighbours")
    assert "clickable from the entry screen" in shell
    assert "inside the app shell" in shell
    assert "stub" in shell and "neighbour" in shell


def test_every_verb_the_guides_name_exists():
    """Each `<script> <verb>` the guides name is a `cmd_<verb>` of that script; the notes loop calls `wait`."""
    scripts = HOME / "scripts"
    named = re.findall(r"(\w+)\.py\"? (\w+)", _text(SKILL_MD) + _text(MOCKUP_MD))
    assert ("mockup_show", "wait") in named
    for script, verb in named:
        source = (scripts / f"{script}.py").read_text("utf-8")
        assert re.search(rf"^def cmd_{verb}\(", source, re.M), f"{script}.py has no verb {verb}"


# --- VR-004 (PRD AC-008, AC-020; SDD §8): only made-up rows, at most 50 per screen, an id on each region

def test_only_made_up_rows_at_most_50_per_screen():
    data = _section(MOCKUP_MD, "## Made-up data")
    assert "every row is made up" in data
    assert "at most 50 rows per screen" in data
    assert "1 JSON script" in data
    assert "never a record copied from the live app or its database" in data
    regions = _section(MOCKUP_MD, "## Regions")
    assert "an `id` on every region the developer may note" in regions
    draft = _section(SKILL_MD, "## Steps")
    assert "made-up data" in draft and "never copy a record" in draft
