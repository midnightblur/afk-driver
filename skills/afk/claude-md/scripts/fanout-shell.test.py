"""Unit + integration suite for the fan-out shell (subtask 0009).

  unit         : drive _propagate over a FAKE worktree set (planner real, I/O
                 injected) — primary-first ordering, summary content, the
                 primary-failure abort, and fail-closed boundary refuse. No disk.
  integration  : run propagateSteeringNote against a THROWAWAY git repo with
                 several real worktrees — the note lands in clean worktrees, a
                 dirty-conflict sibling is skipped+warned, and no write escapes
                 the 11xxx boundary.

Run directly:  python fanout-shell.test.py
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


shell = _load("fanout_shell", "fanout-shell.py")
planner = shell._planner
WorktreeState = planner.WorktreeState
DESIRED = "note v2\n"
IN_PATH = "11700-payable/CLAUDE.md"


# --------------------------------------------------------------------------- #
# unit tier — fake I/O, real planner
# --------------------------------------------------------------------------- #
class FakeIO:
    """Records write calls and serves canned per-worktree states."""

    def __init__(self, states_by_wt, fail_on=()):
        self._states = states_by_wt          # {worktree: WorktreeState}
        self._fail_on = set(fail_on)
        self.writes = []                     # ordered list of worktrees written

    def read_state(self, wt, rel):
        st = self._states[wt]
        return WorktreeState(worktree=wt, dirty=st.dirty, current_content=st.current_content)

    def write_file(self, wt, rel, content):
        if wt in self._fail_on:
            raise OSError(f"permission denied: {wt}")
        self.writes.append(wt)


def _state(wt, dirty=False, content=None):
    return WorktreeState(worktree=wt, dirty=dirty, current_content=content)


class UnitPropagate(unittest.TestCase):
    def _run(self, worktrees, primary, states_by_wt, fail_on=()):
        io = FakeIO(states_by_wt, fail_on=fail_on)
        summ = shell._propagate(
            IN_PATH, DESIRED,
            worktrees=worktrees, primary=primary,
            read_state=io.read_state, write_file=io.write_file,
            boundary=shell.BAKED_BOUNDARY,
        )
        return summ, io

    def test_primary_is_ordered_first(self):
        wts = ["wt-b", "wt-primary", "wt-c"]
        states = {w: _state(w) for w in wts}              # all clean/absent -> write
        summ, io = self._run(wts, "wt-primary", states)
        self.assertEqual(io.writes[0], "wt-primary", "primary must be written first")
        self.assertEqual(set(io.writes), set(wts))
        self.assertTrue(summ.primary_ok)

    def test_matrix_across_siblings(self):
        wts = ["wt-primary", "wt-clean", "wt-dirty-diff", "wt-dirty-eq"]
        states = {
            "wt-primary": _state("wt-primary"),                                  # absent -> write
            "wt-clean": _state("wt-clean", dirty=False, content="old\n"),        # clean -> write
            "wt-dirty-diff": _state("wt-dirty-diff", dirty=True, content="x\n"), # dirty,differs -> skip
            "wt-dirty-eq": _state("wt-dirty-eq", dirty=True, content=DESIRED),   # dirty,equal -> noop
        }
        summ, io = self._run(wts, "wt-primary", states)
        self.assertEqual(set(summ.written), {"wt-primary", "wt-clean"})
        self.assertEqual(summ.noop, ["wt-dirty-eq"])
        self.assertEqual([wt for wt, _ in summ.skipped], ["wt-dirty-diff"])
        self.assertIn("dirty-conflict", summ.skipped[0][1])
        self.assertNotIn("wt-dirty-diff", io.writes)
        self.assertNotIn("wt-dirty-eq", io.writes)

    def test_primary_write_failure_aborts_whole_op(self):
        wts = ["wt-primary", "wt-sibling"]
        states = {w: _state(w) for w in wts}
        summ, io = self._run(wts, "wt-primary", states, fail_on=["wt-primary"])
        self.assertFalse(summ.primary_ok)
        self.assertEqual([wt for wt, _ in summ.failed], ["wt-primary"])
        self.assertEqual(io.writes, [])                   # aborted before any sibling write
        self.assertTrue(any("aborting" in w for w in summ.warnings))

    def test_sibling_write_failure_warns_and_continues(self):
        wts = ["wt-primary", "wt-bad", "wt-good"]
        states = {w: _state(w) for w in wts}
        summ, io = self._run(wts, "wt-primary", states, fail_on=["wt-bad"])
        self.assertTrue(summ.primary_ok)
        self.assertIn("wt-good", summ.written)            # sibling failure did not stop others
        self.assertEqual([wt for wt, _ in summ.failed], ["wt-bad"])

    def test_out_of_boundary_refuses_fail_closed(self):
        wts = ["wt-primary", "wt-sibling"]
        states = {w: _state(w) for w in wts}
        io = FakeIO(states)
        summ = shell._propagate(
            "CLAUDE.md", DESIRED,                          # root file -> outside boundary
            worktrees=wts, primary="wt-primary",
            read_state=io.read_state, write_file=io.write_file,
            boundary=shell.BAKED_BOUNDARY,
        )
        self.assertEqual(summ.boundary_verdict, planner.REFUSE)
        self.assertEqual(set(summ.refused), set(wts))
        self.assertEqual(io.writes, [], "fail-closed: nothing is written out of boundary")

    def test_single_worktree_writes_primary_only(self):
        summ, io = self._run(["wt-primary"], "wt-primary", {"wt-primary": _state("wt-primary")})
        self.assertEqual(io.writes, ["wt-primary"])


# --------------------------------------------------------------------------- #
# integration tier — real git worktrees on a throwaway repo
# --------------------------------------------------------------------------- #
def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@unittest.skipUnless(
    subprocess.run(["git", "--version"], capture_output=True).returncode == 0, "git required"
)
class IntegrationWorktrees(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fanout-it-")
        self.primary = os.path.join(self.tmp, "primary")
        os.makedirs(os.path.join(self.primary, "11700-payable"))
        _git(["init", "-b", "main", self.primary], cwd=self.tmp)
        _git(["config", "user.email", "t@t.t"], cwd=self.primary)
        _git(["config", "user.name", "t"], cwd=self.primary)
        # baseline so the service dir is tracked and worktrees can branch off HEAD
        open(os.path.join(self.primary, "11700-payable", "README.md"), "w").close()
        _git(["add", "-A"], cwd=self.primary)
        _git(["commit", "-m", "baseline"], cwd=self.primary)
        self.clean = os.path.join(self.tmp, "wt-clean")
        self.dirty = os.path.join(self.tmp, "wt-dirty")
        _git(["worktree", "add", "-b", "b-clean", self.clean], cwd=self.primary)
        _git(["worktree", "add", "-b", "b-dirty", self.dirty], cwd=self.primary)
        # dirty sibling: an uncommitted, conflicting target -> must be skipped
        with open(os.path.join(self.dirty, "11700-payable", "CLAUDE.md"), "w") as fh:
            fh.write("LOCAL UNCOMMITTED EDITS\n")
        self._cwd = os.getcwd()
        os.chdir(self.primary)

    def tearDown(self):
        os.chdir(self._cwd)
        # best-effort cleanup of the throwaway tree
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _read(self, wt):
        p = os.path.join(wt, "11700-payable", "CLAUDE.md")
        if not os.path.isfile(p):
            return None
        with open(p, encoding="utf-8") as fh:
            return fh.read()

    def test_note_lands_in_clean_skips_dirty(self):
        summ = shell.propagateSteeringNote(IN_PATH, DESIRED)
        self.assertEqual(summ.boundary_verdict, planner.ALLOW)
        self.assertTrue(summ.primary_ok)
        # clean primary + clean sibling get the note
        self.assertEqual(self._read(self.primary), DESIRED)
        self.assertEqual(self._read(self.clean), DESIRED)
        # dirty-conflict sibling untouched + reported skipped
        self.assertEqual(self._read(self.dirty), "LOCAL UNCOMMITTED EDITS\n")
        self.assertIn(os.path.normpath(self.dirty), [os.path.normpath(w) for w, _ in summ.skipped])

    def test_out_of_boundary_writes_nothing(self):
        summ = shell.propagateSteeringNote("CLAUDE.md", DESIRED)   # repo-root file
        self.assertEqual(summ.boundary_verdict, planner.REFUSE)
        for wt in (self.primary, self.clean, self.dirty):
            self.assertFalse(os.path.isfile(os.path.join(wt, "CLAUDE.md")),
                             f"no write should escape the boundary into {wt}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
