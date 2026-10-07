#!/usr/bin/env python3
"""`rule_paths_match.py` matches `.claude/rules` `paths:` globs.

The module's own FIXTURES table is the specification; this drives it and adds the
brace-budget and base-relative edge cases the plan calls out.
"""
import importlib.util
from pathlib import Path

import pytest

MODULE = (Path(__file__).resolve().parents[2]
          / "hooks" / "lib" / "rule_paths_match.py")


def _module():
    spec = importlib.util.spec_from_file_location("afk_rule_paths_match", MODULE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rpm = _module()


@pytest.mark.parametrize("text,rel,expected", rpm.FIXTURES)
def test_fixture_table(text, rel, expected):
    assert rpm.rule_matches(text, rel) is expected


def test_double_star_crosses_slashes_single_star_does_not():
    assert rpm.matches(["**/*.ts"], "a/b/c.ts")
    assert not rpm.matches(["*.ts"], "a/b.ts")
    assert rpm.matches(["*.ts"], "b.ts")


def test_brace_over_budget_matches_nothing():
    # A brace product past the 1,000-pattern cap is refused, so it matches
    # nothing rather than expanding into a denial-of-service.
    huge = "{" + ",".join(str(i) for i in range(40)) + "}" \
           + "{" + ",".join(str(i) for i in range(40)) + "}"  # 1,600 > 1,000
    assert rpm.brace_expand(huge) is None
    assert not rpm.matches([huge], "3535")


def test_comma_string_and_list_parse_the_same():
    p1, _ = rpm.parse_paths("---\npaths: a.md, b.md\n---\n")
    p2, _ = rpm.parse_paths('---\npaths: ["a.md", "b.md"]\n---\n')
    assert p1 == p2 == ["a.md", "b.md"]


def test_windows_separators_normalized():
    assert rpm.matches(["src/**/*.ts"], "src\\a\\b.ts")


def test_unclosed_class_is_invalid_not_a_crash():
    assert rpm._translate("src/[abc") is None
    assert not rpm.matches(["src/[abc"], "src/x")
