"""The design-system guides: SKILL.md and the catalog format CATALOG-FORMAT.md (SDD §4, §5, §8; ticket 207 VR-022,
VR-029; decision D-8).

The quality of the steps is proved by the owner's live check; these tests pin that each rule is stated in the file
that owns it, that the format names what catalog_files.py reads, and that every verb the guides name exists.
"""

import re
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
HOME = SKILLS / "design-system"
SKILL_MD = HOME / "SKILL.md"
FORMAT_MD = HOME / "CATALOG-FORMAT.md"
sys.path.insert(0, str(HOME / "scripts"))


def _flat(text):
    return " ".join(text.split())


def _text(path):
    assert path.is_file(), f"no {path.name} in {path.parent}"
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


# --- VR-029 (PRD AC-025): neither skill names the outward design host or its tools

FORBIDDEN = ("claude.ai/design", "DesignSync", "@dsCard")


def test_neither_skill_names_the_outward_design_host():
    assert SKILL_MD.is_file() and FORMAT_MD.is_file()
    for folder in (SKILLS / "design-system", SKILLS / "prototype"):
        for path in folder.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                text = path.read_bytes().decode("utf-8", "replace").lower()
                for name in FORBIDDEN:
                    assert name.lower() not in text, f"{path.relative_to(PLUGIN).as_posix()} names {name}"


def test_the_skill_sends_nothing_to_any_host():
    assert "sends nothing to any host" in _flat(_text(SKILL_MD))


def test_every_verb_the_guide_names_exists():
    """Each `catalog_files.py <verb>` the guides name is a `cmd_<verb>` of the script."""
    source = (HOME / "scripts" / "catalog_files.py").read_text("utf-8")
    named = set(re.findall(r"catalog_files\.py\"? ([a-z][\w-]*)", _text(SKILL_MD) + _text(FORMAT_MD)))
    assert {"start", "add-frontend", "check"} <= named
    for verb in named:
        assert re.search(rf"^def cmd_{verb.replace('-', '_')}\(", source, re.M), f"catalog_files.py has no verb {verb}"


def test_the_format_names_each_section_kind_and_state_check_reads():
    import catalog_files

    text = _text(FORMAT_MD)
    for name in (*catalog_files.SECTIONS, *catalog_files.COLUMNS, *catalog_files.KINDS, *catalog_files.STATES):
        assert f"`{name}`" in text, f"CATALOG-FORMAT.md does not name `{name}`"
    assert f"`{catalog_files.TOKENS}`" in text and f"`{catalog_files.README}`" in text


# --- VR-022 (PRD AC-026): a hands-off subagent opens no page, writes no file, and parks

HANDS_OFF = "opens no page, writes no file, and parks with the reason that a developer must run"


def test_both_skills_park_a_hands_off_subagent():
    for path in (SKILL_MD, SKILLS / "prototype" / "SKILL.md"):
        hands_off = _section(path, "## Hands-off")
        assert "A hands-off subagent" in hands_off, path
        assert HANDS_OFF in hands_off, path
