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
