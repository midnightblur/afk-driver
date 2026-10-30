"""A recorded fake of `afkv2/skills/to-subtasks/scripts/check_plan.py`, the plan check of subtask 0010.

Built from the 0010 contract: one JSON object that lists every failure, exit 0, 1 or 2, the SDD section 3
envelope, and the `> Division: approved <date>` line, which the check reads. `FAKE_CHECK_PLAN_ANSWER` names
one recorded answer in `answers/`. The file `not-json` prints text that is no JSON.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ANSWERS = Path(__file__).resolve().parent / "answers"
APPROVAL = re.compile(r"^> Division: approved \d{4}-\d{2}-\d{2}\s*$", re.MULTILINE)


def main():
    name = os.environ.get("FAKE_CHECK_PLAN_ANSWER", "pass")
    if name == "not-json":
        print("Traceback: the check crashed")
        return 1
    recorded = json.loads((ANSWERS / f"{name}.json").read_text(encoding="utf-8"))
    answer, code = recorded["answer"], recorded["exit"]
    plan_text = (Path(sys.argv[1]) / "PLAN.md").read_text(encoding="utf-8")
    if code != 2 and not APPROVAL.search(plan_text):
        failure = {"code": "no-approval", "where": "PLAN.md", "reason": "no `> Division: approved <date>` line"}
        answer = {"ok": False, "error": {"code": "plan-check-failed", "reason": "the plan check found failures"},
                  "failures": [*answer.get("failures", []), failure]}
        code = 1
    print(json.dumps(answer))
    return code


if __name__ == "__main__":
    sys.exit(main())
