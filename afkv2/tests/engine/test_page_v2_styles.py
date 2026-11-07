"""Every style class the version 2 page parts write has a rule in the inlined stylesheet, so sections, worked
examples, change lines and questions for others never render as bare text."""

import re
from pathlib import Path

SHELL = Path(__file__).resolve().parents[2] / "engine" / "shell"
TOKEN = re.compile(r"afkv2-v2-[a-z0-9-]*[a-z0-9]|afkv2-who-filter")


def _written_classes():
    source = (SHELL / "parts_v2.py").read_text(encoding="utf-8")
    return sorted(set(TOKEN.findall(source)))


def test_parts_v2_writes_style_classes():
    assert "afkv2-v2-section" in _written_classes()


def test_every_version_2_class_has_a_rule():
    css = (SHELL / "kit.css").read_text(encoding="utf-8")
    missing = [name for name in _written_classes() if not re.search(rf"\.{re.escape(name)}(?![\w-])", css)]
    assert missing == []
