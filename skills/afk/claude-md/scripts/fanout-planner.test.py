"""Unit suite for the pure fan-out planner (subtask 0008).

Exercises the full ADR-0002 decision matrix on synthetic worktree facts -- no
git, no filesystem. Run directly:  python fanout-planner.test.py

The module under test has a hyphen in its name (not a valid Python identifier),
so it is loaded by file path via importlib.
"""

import importlib.util
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "fanout_planner", os.path.join(_HERE, "fanout-planner.py")
)
planner = importlib.util.module_from_spec(_spec)
# Register before exec: dataclasses resolves cls.__module__ via sys.modules, and
# a path-loaded module is otherwise absent there (raises on @dataclass).
sys.modules["fanout_planner"] = planner
_spec.loader.exec_module(planner)

WorktreeState = planner.WorktreeState
computeFanOutPlan = planner.computeFanOutPlan
WRITE, SKIP, NOOP, REFUSE = planner.WRITE, planner.SKIP, planner.NOOP, planner.REFUSE
ALLOW = planner.ALLOW

# A representative baked-style boundary (ADR-0005). The planner is agnostic; this
# is just a synthetic instance for the tests.
BOUNDARY = ["11700-payable/**", "11999-common/**", "tools/payable/**"]
IN_PATH = "11700-payable/component/matching/CLAUDE.md"
DESIRED = "note v2\n"


class BoundaryMatrix(unittest.TestCase):
    def test_clean_file_writes(self):
        plan = computeFanOutPlan(
            IN_PATH, DESIRED, [WorktreeState("wt-a", dirty=False, current_content="old\n")], BOUNDARY
        )
        self.assertEqual(plan.boundary_verdict, ALLOW)
        self.assertEqual([d.action for d in plan.per_worktree], [WRITE])

    def test_absent_file_writes(self):
        plan = computeFanOutPlan(
            IN_PATH, DESIRED, [WorktreeState("wt-a", dirty=False, current_content=None)], BOUNDARY
        )
        self.assertEqual(plan.per_worktree[0].action, WRITE)

    def test_dirty_equal_is_noop(self):
        plan = computeFanOutPlan(
            IN_PATH, DESIRED, [WorktreeState("wt-a", dirty=True, current_content=DESIRED)], BOUNDARY
        )
        self.assertEqual(plan.per_worktree[0].action, NOOP)

    def test_dirty_differs_is_skip(self):
        plan = computeFanOutPlan(
            IN_PATH, DESIRED, [WorktreeState("wt-a", dirty=True, current_content="local edits\n")], BOUNDARY
        )
        d = plan.per_worktree[0]
        self.assertEqual(d.action, SKIP)
        self.assertIn("dirty-conflict", d.reason)

    def test_outside_boundary_refuses_fail_closed(self):
        # root CLAUDE.md and root GLOSSARY* are deliberately excluded (ADR-0005)
        for bad in ("CLAUDE.md", "GLOSSARY.md", "16800-real-estate/CLAUDE.md", "../escape/CLAUDE.md"):
            plan = computeFanOutPlan(
                bad, DESIRED, [WorktreeState("wt-a", dirty=False, current_content=None)], BOUNDARY
            )
            self.assertEqual(plan.boundary_verdict, REFUSE, bad)
            # fail-closed: NO write decision is ever emitted for an out-of-bounds path
            self.assertTrue(all(d.action == REFUSE for d in plan.per_worktree), bad)

    def test_tools_payable_subtree_allowed(self):
        plan = computeFanOutPlan(
            "tools/payable/ai-agents/harness/shared/coding-standards.md",
            DESIRED,
            [WorktreeState("wt-a", dirty=False)],
            BOUNDARY,
        )
        self.assertEqual(plan.boundary_verdict, ALLOW)
        self.assertEqual(plan.per_worktree[0].action, WRITE)


class MultiWorktree(unittest.TestCase):
    def test_mixed_decisions_preserve_order(self):
        states = [
            WorktreeState("wt-clean", dirty=False, current_content=None),
            WorktreeState("wt-dirty-diff", dirty=True, current_content="x\n"),
            WorktreeState("wt-dirty-eq", dirty=True, current_content=DESIRED),
        ]
        plan = computeFanOutPlan(IN_PATH, DESIRED, states, BOUNDARY)
        self.assertEqual(
            [(d.worktree, d.action) for d in plan.per_worktree],
            [("wt-clean", WRITE), ("wt-dirty-diff", SKIP), ("wt-dirty-eq", NOOP)],
        )

    def test_no_worktrees_allowed_path_is_empty_allow(self):
        plan = computeFanOutPlan(IN_PATH, DESIRED, [], BOUNDARY)
        self.assertEqual(plan.boundary_verdict, ALLOW)
        self.assertEqual(plan.per_worktree, [])


class PathNormalization(unittest.TestCase):
    def test_backslashes_and_dot_prefix_normalize(self):
        for variant in (r"11700-payable\component\CLAUDE.md", "./11700-payable/component/CLAUDE.md"):
            plan = computeFanOutPlan(
                variant, DESIRED, [WorktreeState("wt-a", dirty=False)], BOUNDARY
            )
            self.assertEqual(plan.boundary_verdict, ALLOW, variant)


if __name__ == "__main__":
    unittest.main(verbosity=2)
