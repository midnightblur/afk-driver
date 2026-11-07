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

import estimate  # noqa: E402
import plan_files  # noqa: E402
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
    assert "low 1.00, likely 1.00, high 1.00" in total and "1 earlier run" in total


def test_the_division_card_says_no_earlier_run_exists(world):
    started = world.committed_plan()
    world.division(started)
    total = world.card(started)["body"]["children"][1]["props"]["text"]
    assert "estimated" in total and "no earlier run exists" in total and "low 0.50, likely 1.00, high 2.00" in total
