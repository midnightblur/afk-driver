#!/usr/bin/env python3
"""Contract tests for scripts/validate_agenda.py.

The rules under test are the script's docstring. Each test names the finding it
pins, so a failure says which rule moved.

    python3 scripts/tests/test_validate_agenda.py
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import validate_agenda  # noqa: E402


def plan(profile="Profile: company-meeting", rows=None, headers=None):
    """A minimal plan carrying one agenda section."""
    headers = headers or "| Presenter min | Objection min | Total min | Segment |"
    rows = rows or ["| 30 | 20 | 50 | One |", "| 5 | 5 | 10 | Two |"]
    body = ["# A plan", "", "## Agenda", "", profile, "",
            headers, "|---:|---:|---:|---|"] + rows + ["", "## After", "", "text"]
    return "\n".join(body)


def rules(text):
    return sorted(finding.split(":", 1)[0] for finding in validate_agenda.check(text))


class Clean(unittest.TestCase):

    def test_an_agenda_that_adds_to_sixty_passes(self):
        self.assertEqual(validate_agenda.check(plan()), [])

    def test_a_single_minute_column_named_min_is_the_budget(self):
        text = plan(headers="| Min | Segment |",
                    rows=["| 45 | Demo |", "| 10 | Questions |", "| 5 | Next steps |"])
        self.assertEqual(validate_agenda.check(text), [])


class Findings(unittest.TestCase):

    def test_no_agenda_section(self):
        self.assertEqual(rules("# A plan\n\n## Something else\n"), ["NO-AGENDA"])

    def test_no_profile_line(self):
        self.assertIn("NO-PROFILE", rules(plan(profile="Runs for an hour.")))

    def test_a_plan_outside_the_company_profile_is_not_held_to_sixty(self):
        """The profile is what imposes the hour; nothing else may."""
        found = rules(plan(profile="Runs to a 45 minute ceiling.",
                           rows=["| 20 | 5 | 25 | One |"]))
        self.assertEqual(found, ["NO-PROFILE"])

    def test_no_table(self):
        text = "# A plan\n\n## Agenda\n\nProfile: company-meeting\n\nNo table here.\n"
        self.assertEqual(rules(text), ["NO-TABLE"])

    def test_no_budget_column(self):
        text = plan(headers="| Segment | Purpose |", rows=["| One | Align |"])
        self.assertEqual(rules(text), ["NO-BUDGET-COL"])

    def test_a_budget_cell_that_is_not_a_number(self):
        self.assertIn("BAD-MINUTE", rules(plan(rows=["| 30 | 20 | fifty | One |"])))

    def test_a_row_whose_parts_do_not_make_its_total(self):
        """The hour can be right while a row lies; this is the only check that sees it."""
        found = validate_agenda.check(plan(rows=["| 30 | 20 | 51 | One |",
                                                 "| 5 | 4 | 9 | Two |"]))
        self.assertEqual([f.split(":", 1)[0] for f in found], ["ROW-SUM"])

    def test_a_numbered_agenda_heading_is_still_the_agenda(self):
        self.assertEqual(validate_agenda.check(plan().replace("## Agenda", "## 3. Agenda")), [])

    def test_a_budget_that_is_not_sixty(self):
        self.assertEqual(rules(plan(rows=["| 30 | 20 | 50 | One |"])), ["TOTAL"])

    def test_the_finding_names_both_numbers(self):
        """A total that only says wrong makes the author count by hand."""
        found = validate_agenda.check(plan(rows=["| 30 | 20 | 50 | One |"]))
        self.assertIn("50", found[0])
        self.assertIn("60", found[0])


class Section(unittest.TestCase):

    def test_the_agenda_stops_at_the_next_heading(self):
        """A later section's table must not be read as the agenda."""
        text = plan() + "\n| Min | Other |\n|---:|---|\n| 99 | Not the agenda |\n"
        self.assertEqual(validate_agenda.check(text), [])


class Cli(unittest.TestCase):

    def test_a_missing_file_exits_two(self):
        self.assertEqual(validate_agenda.main([os.path.join(HERE, "no-such-plan.md")]), 2)

    def test_wrong_argument_count_exits_two(self):
        self.assertEqual(validate_agenda.main([]), 2)

    def shipped(self, *parts):
        path = os.path.join(os.path.dirname(os.path.dirname(HERE)), *parts)
        with open(path, encoding="utf-8") as handle:
            return validate_agenda.check(handle.read())

    def test_the_shipped_templates_add_up(self):
        """Templates ship the agenda authors start from; both must be correct."""
        self.assertEqual(self.shipped("skills", "afk", "to-design-review-plan",
                                      "PLAN-TEMPLATE.md"), [])
        self.assertEqual(self.shipped("skills", "afk", "to-demo-plan",
                                      "DEMO-PLAN-TEMPLATE.md"), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
