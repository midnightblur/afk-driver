"""Tests for the estimate of to-subtasks: past run times from journal copies, else the size table (ADR-0005).

The plan is a plain folder of contracts; the journal copies sit at `<spec root>/<ticket>/runs/*.md`.
The division card tests reuse the to-subtasks world: a temporary repository with the page engine fake.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "skills" / "to-subtasks" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE))

import check_plan  # noqa: E402
import estimate  # noqa: E402
import plan_files  # noqa: E402
from grill_common import Refusal  # noqa: E402
from test_to_subtasks import World, programs_on_the_path  # noqa: E402,F401

HEADER = "# Journal: append-only event log, one line per event. Newest last."


def line(stamp, subject, event, writer="autopilot"):
    return f"{stamp} | {writer} | {subject} | {event} — what happened"


def ran(subject, start, end, complexity=None):
    """The journal lines of one subtask that ran from `start` to `end`."""
    lines = [line(start, subject, "developing")]
    if complexity:
        lines.append(line(start, subject, f"complexity {complexity}"))
    return lines + [line(start, subject, "verifying", "execute"), line(end, subject, "done", "execute")]


def journal(spec_root, ticket, name, lines, header=HEADER):
    path = Path(spec_root) / ticket / "runs" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *lines]) + "\n", "utf-8")
    return path


def plan_of(root, classes):
    plan = Path(root) / "plan"
    plan.mkdir()
    for rank, complexity in enumerate(classes, 1):
        (plan / f"{rank:04d}-part-{rank}.md").write_text(f"# {rank:04d}-part-{rank}\n\n## Complexity\n{complexity}\n", "utf-8")
    return plan


def values(row):
    return row["low"], row["likely"], row["high"]


# Past run times.

def test_journal_copies_give_weighted_percentiles_and_the_run_count(tmp_path):
    specs = tmp_path / "specs"
    journal(specs, "A-1", "feat-a-run", ran("0001-x", "2026-01-01 10:00", "2026-01-01 13:00", "mechanical")
            + ran("0002-y", "2026-01-02 08:00", "2026-01-02 20:00", "standard"))
    journal(specs, "B-2", "feat-b-run", ran("0001-z", "2026-01-03 00:00", "2026-01-05 00:00", "complex"))
    plan = plan_of(tmp_path, ["standard", "complex"])
    answer = estimate.estimate(plan, specs)
    assert answer["ok"] is True and answer["basis"] == "journals" and answer["runs"] == 2
    assert [row["subtask"] for row in answer["rows"]] == ["0001-part-1", "0002-part-2"]
    assert values(answer["rows"][0]) == (0.35, 0.5, 0.8)
    assert values(answer["rows"][1]) == (0.7, 1.0, 1.6)
    assert values(answer["total"]) == (1.05, 1.5, 2.4)


def test_the_command_answers_one_json_object(tmp_path):
    specs = tmp_path / "specs"
    journal(specs, "A-1", "feat-a-run", ran("0001-x", "2026-01-02 08:00", "2026-01-02 20:00", "standard"))
    plan = plan_of(tmp_path, ["standard"])
    done = subprocess.run([sys.executable, str(SCRIPTS / "estimate.py"), "--plan", str(plan), "--spec-root", str(specs)],
                          capture_output=True, text=True)
    answer = json.loads(done.stdout)
    assert done.returncode == 0 and answer["runs"] == 1 and values(answer["rows"][0]) == (0.5, 0.5, 0.5)


# No past run time.

@pytest.mark.parametrize("with_header_only", [False, True])
def test_with_no_journal_copy_the_size_table_applies_marked_estimated(tmp_path, with_header_only):
    specs = tmp_path / "specs"
    specs.mkdir()
    if with_header_only:
        journal(specs, "A-1", "feat-a-run", [])
    plan = plan_of(tmp_path, ["standard", "complex"])
    answer = estimate.estimate(plan, specs)
    assert (answer["basis"], answer["runs"]) == ("estimated", 0)
    assert values(answer["rows"][0]) == (0.25, 0.5, 1.0)
    assert values(answer["rows"][1]) == (0.5, 1.0, 2.0)
    assert values(answer["total"]) == (0.75, 1.5, 3.0)


# Compatible lines.

def test_old_lines_count_as_standard_and_bad_parked_or_open_lines_are_no_sample(tmp_path):
    specs = tmp_path / "specs"
    lines = [*ran("0001-old", "2026-01-01 00:00", "2026-01-02 00:00"),
             "not a journal line",
             line("2026-01-03 00:00", "0002-parked", "developing"),
             line("2026-01-03 01:00", "0002-parked", "parked(review_fail: stalemate)"),
             line("2026-01-03 02:00", "0002-parked", "done"),
             line("2026-01-04 00:00", "0003-open", "developing")]
    journal(specs, "A-1", "feat-a-run", lines, header="# Journal — append-only event log (format: v1). Newest last.")
    plan = plan_of(tmp_path, ["standard"])
    answer = estimate.estimate(plan, specs)
    assert (answer["basis"], answer["runs"], answer["skipped"]) == ("journals", 1, 1)
    assert values(answer["rows"][0]) == (1.0, 1.0, 1.0)
    assert "feat-a-run.md:5" in answer["notes"][0] and answer["notes"][0].startswith("bad-journal")


# The division card.

@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_the_division_card_shows_the_estimate_from_earlier_runs_and_keeps_the_digest(world):
    started = world.committed_plan()
    digest = plan_files.plan_digest(started["plan"])
    journal(world.spec.parent, "PROJ-0", "feat-old-run", ran("0001-x", "2026-01-02 08:00", "2026-01-02 20:00", "standard"))
    answer = world.division(started)
    card = world.card(started)
    assert answer["digest"] == digest == plan_files.plan_digest(started["plan"])
    assert card["body"]["props"]["columns"][-3:] == ["Low days", "Likely days", "High days"]
    assert [row[-3:] for row in card["body"]["props"]["rows"]] == [["0.50", "0.50", "0.50"]] * 2
    assert "app: none" in card["body"]["children"][0]["props"]["text"]
    total = card["body"]["children"][1]["props"]["text"]
    assert total == "Agent run time in days, in total: low 1.00, likely 1.00, high 1.00. Basis: past run times from 1 earlier run."
    assert answer["estimate_notes"] == []


def test_the_division_card_says_no_earlier_run_exists(world):
    started = world.committed_plan()
    world.division(started)
    card = world.card(started)
    assert [row[-3:] for row in card["body"]["props"]["rows"]] == [["0.25", "0.50", "1.00"]] * 2
    total = card["body"]["children"][1]["props"]["text"]
    assert total == ("Agent run time in days, in total: low 0.50, likely 1.00, high 2.00. "
                     "Basis: estimated from the size of each subtask, because no earlier run exists.")



# Bad input.

def test_an_unreadable_journal_copy_is_a_bad_journal_note_not_a_crash(tmp_path):
    specs = tmp_path / "specs"
    journal(specs, "A-1", "feat-a-run", ran("0001-x", "2026-01-02 08:00", "2026-01-02 20:00", "standard"))
    (specs / "B-2" / "runs" / "folder.md").mkdir(parents=True)
    unreadable = journal(specs, "C-3", "feat-c-run", [])
    real_read = Path.read_text

    def read_text(self, *args, **kwargs):
        if self == unreadable:
            raise PermissionError("denied")
        return real_read(self, *args, **kwargs)

    plan = plan_of(tmp_path, ["standard"])
    from unittest import mock
    with mock.patch.object(Path, "read_text", read_text):
        answer = estimate.estimate(plan, specs)
    assert answer["ok"] and answer["runs"] == 1 and answer["skipped"] == 1
    assert answer["notes"][0].startswith("bad-journal: ") and "feat-c-run.md" in answer["notes"][0]


@pytest.mark.parametrize("missing", ["plan", "spec_root"])
def test_a_missing_folder_refuses(tmp_path, missing):
    specs = tmp_path / "specs"
    specs.mkdir()
    plan = plan_of(tmp_path, ["standard"])
    args = {"plan": plan, "spec_root": specs, missing: tmp_path / "nowhere"}
    with pytest.raises(Refusal) as caught:
        estimate.estimate(args["plan"], args["spec_root"])
    assert caught.value.code == ("no-plan" if missing == "plan" else "no-spec-root")


def test_the_command_refuses_a_missing_plan_with_one_json_object(tmp_path):
    specs = tmp_path / "specs"
    specs.mkdir()
    done = subprocess.run([sys.executable, str(SCRIPTS / "estimate.py"), "--plan", str(tmp_path / "nowhere"), "--spec-root", str(specs)],
                          capture_output=True, text=True)
    assert done.returncode == 1 and json.loads(done.stdout)["error"]["code"] == "no-plan"


def test_journal_copies_with_no_finished_run_are_told_apart_from_no_copy(tmp_path):
    specs = tmp_path / "specs"
    journal(specs, "A-1", "feat-a-run", [line("2026-01-04 00:00", "0003-open", "developing")])
    journal(specs, "B-2", "feat-b-run", [])
    answer = estimate.estimate(plan_of(tmp_path, ["standard"]), specs)
    assert (answer["basis"], answer["runs"], answer["copies"]) == ("estimated", 0, 2)
    assert plan_files._estimate_line(answer).endswith(
        "Basis: estimated from the size of each subtask, because the 2 journal copies hold no finished run.")


def test_the_total_is_the_sum_of_the_shown_rows(tmp_path):
    specs = tmp_path / "specs"
    specs.mkdir()
    answer = estimate.estimate(plan_of(tmp_path, ["mechanical"] * 3), specs)
    assert [row["likely"] for row in answer["rows"]] == [0.12] * 3
    assert answer["total"]["likely"] == 0.36


@pytest.mark.parametrize("runs, copies, skipped, basis, tail", [
    (1, 1, 0, "journals", "Basis: past run times from 1 earlier run."),
    (2, 2, 0, "journals", "Basis: past run times from 2 earlier runs."),
    (2, 3, 1, "journals", "Basis: past run times from 2 earlier runs. 1 unreadable journal line skipped."),
    (1, 1, 3, "journals", "Basis: past run times from 1 earlier run. 3 unreadable journal lines skipped."),
    (0, 1, 0, "estimated", "Basis: estimated from the size of each subtask, because the 1 journal copy holds no finished run."),
])
def test_the_estimate_line_counts_runs_copies_and_skipped_lines(runs, copies, skipped, basis, tail):
    answer = {"total": {"low": 1, "likely": 2, "high": 3}, "runs": runs, "copies": copies, "skipped": skipped, "basis": basis}
    assert plan_files._estimate_line(answer) == f"Agent run time in days, in total: low 1.00, likely 2.00, high 3.00. {tail}"


def test_the_card_puts_low_likely_and_high_in_order_per_subtask(tmp_path):
    specs = tmp_path / "specs"
    specs.mkdir()
    plan = plan_of(tmp_path, ["mechanical", "complex"])
    (plan / "PLAN.md").write_text("# Plan\n\n> Feature: x\n", "utf-8")
    subtasks = check_plan.read_subtasks(plan)
    card, _ = plan_files._division_card(plan, subtasks, {s.id: "why" for s in subtasks}, "card-1", "d", [], specs)
    rows = card["body"]["props"]["rows"]
    assert [row[-3:] for row in rows] == [["0.05", "0.12", "0.25"], ["0.50", "1.00", "2.00"]]
