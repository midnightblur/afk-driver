"""The agent run time of a plan, in days, per subtask and in total (method: ADR-0005 of ticket 178).

`estimate.py --plan DIR --spec-root DIR`: reads every journal copy `<spec root>/*/runs/*.md`; read-only.
A sample runs from the first `developing` line of a subject to its next `done` line in one journal; a `parked(...)`
line between them, or no `done`, gives no sample. A line that does not follow the journal grammar is skipped.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS.parents[1] / "use-lavish" / "scripts")]

import check_plan as cp  # noqa: E402
from grill_common import Parser, serve  # noqa: E402

WEIGHTS = {"mechanical": 0.5, "standard": 1.0, "complex": 2.0}
SIZE_TABLE = {"mechanical": (0.05, 0.125, 0.25), "standard": (0.25, 0.5, 1.0), "complex": (0.5, 1.0, 2.0)}
PERCENTILES = (0.2, 0.5, 0.8)
KEYS = ("low", "likely", "high")
DECIMALS = 2
MINUTES_A_DAY = 1440
JOURNAL_GLOB = "*/runs/*.md"
LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| [^|]+? \| ([^|]+?) \| (.+)$")
STAMP = "%Y-%m-%d %H:%M"


def class_of(text):
    """The first word of a `## Complexity` section or a `complexity` event; `standard` when it names no class."""
    words = (text or "").lower().split()
    word = words[0].strip("`*_.,;:") if words else ""
    return word if word in WEIGHTS else "standard"


def _events(path, notes):
    """[(time, subject, event)] of one journal; each unreadable line becomes a `bad-journal` note."""
    found = []
    for number, text in enumerate(path.read_text("utf-8", errors="replace").splitlines(), 1):
        if not text.strip() or text.startswith("#"):
            continue
        match = LINE.match(text)
        try:
            stamp = datetime.strptime(match.group(1), STAMP) if match else None
        except ValueError:
            stamp = None
        if stamp is None:
            notes.append(f"bad-journal: {path.as_posix()}:{number} is no journal line")
            continue
        found.append((stamp, match.group(2).strip(), match.group(3).split(" — ")[0].strip()))
    return found


def _samples(events):
    """Minutes per subtask run divided by the weight of its class."""
    started, classes, parked, minutes = {}, {}, set(), {}
    for stamp, subject, event in events:
        if event.startswith("complexity "):
            classes[subject] = class_of(event.removeprefix("complexity "))
        elif event == "developing" and subject not in started:
            started[subject] = stamp
        elif event.startswith("parked(") and subject in started:
            parked.add(subject)
        elif event == "done" and subject in started and subject not in minutes and subject not in parked:
            minutes[subject] = (stamp - started[subject]).total_seconds() / 60
    return [value / WEIGHTS[classes.get(subject, "standard")] for subject, value in minutes.items() if value >= 0]


def _percentile(ordered, fraction):
    """Linear interpolation between the closest ranks."""
    rank = fraction * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _days(value):
    return round(value, DECIMALS)


def estimate(plan, spec_root):
    """{"ok", "rows": [{subtask, low, likely, high}], "total", "runs", "basis", "skipped", "notes"}; days."""
    notes, samples, runs = [], [], 0
    for path in sorted(Path(spec_root).glob(JOURNAL_GLOB)):
        found = _samples(_events(path, notes))
        runs += bool(found)
        samples += found
    ordered = sorted(samples)
    rows, total = [], [0.0, 0.0, 0.0]
    for subtask in cp.read_subtasks(plan):
        complexity = class_of(subtask.sections.get("Complexity", ""))
        if ordered:
            spread = [_percentile(ordered, fraction) * WEIGHTS[complexity] / MINUTES_A_DAY for fraction in PERCENTILES]
        else:
            spread = list(SIZE_TABLE[complexity])
        total = [whole + part for whole, part in zip(total, spread)]
        rows.append({"subtask": subtask.id, **{key: _days(value) for key, value in zip(KEYS, spread)}})
    return {"ok": True, "rows": rows, "total": {key: _days(value) for key, value in zip(KEYS, total)}, "runs": runs,
            "basis": "journals" if ordered else "estimated", "skipped": len(notes), "notes": notes}


def main(argv):
    parser = Parser(add_help=False)
    for name in ("--plan", "--spec-root"):
        parser.add_argument(name, required=True)
    args = parser.parse_args(argv)
    return estimate(args.plan, args.spec_root)


if __name__ == "__main__":
    sys.exit(serve(main))
