"""The precedent rule: 1 home in the core behaviors, and a pointer in each skill that proposes or judges a model."""

from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
POINTER = '"Precedent" in the core behaviors'


def test_the_core_behaviors_own_the_precedent_rule():
    text = (PLUGIN / "core" / "CORE-BEHAVIORS.md").read_text("utf-8")
    assert "- Precedent: before you propose a model, a screen, a rule or a test" in text
    assert "Read it each time, because it changes." in text


@pytest.mark.parametrize("path", ["skills/grill-requirements/SKILL.md", "skills/propose-solution/SKILL.md",
                                  "skills/prototype/SKILL.md", "skills/code-review/REVIEWER.md",
                                  "skills/review-qa-tests/SKILL.md"])
def test_each_proposing_or_judging_skill_points_at_the_rule(path):
    assert POINTER in (PLUGIN / path).read_text("utf-8"), f"{path} lacks the pointer {POINTER!r}"
