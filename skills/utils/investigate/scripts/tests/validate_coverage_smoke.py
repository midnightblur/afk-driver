#!/usr/bin/env python3
"""Smoke test for validate_coverage.py.

Run directly: python validate_coverage_smoke.py
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VALIDATOR = HERE.parent / "validate_coverage.py"

VALID = {
    "run": {
        "repository": "/tmp/fixture",
        "head": "0" * 40,
        "question": "what depends on Widget",
        "type": "Q2",
        "roots": ["Widget"],
        "aliases": {"Widget": ["Widget"]},
        "inventory_hash": "a" * 64,
        "inventory_count": 7,
        "design_phase": False,
        "started": "2026-01-01T00:00:00Z",
        "finished": "2026-01-01T00:01:00Z",
    },
    "boundaries": [
        {"class": f"B{n}", "mechanism": "default", "method": "name forms",
         "hits": 0, "status": "closed"}
        for n in range(1, 14)
    ] + [{"class": "B14", "mechanism": "default", "method": "none", "hits": 0,
          "status": "frontier", "reason": "another repository"}],
    "nodes": [
        {"id": "n1", "class": "B1", "site": "src/Caller.java:3", "disposition": "traced",
         "pinned_by": "unguarded", "evidence": "Widget w;", "parent": None},
    ],
    "queries": [{"command": "git grep -n Widget", "universe": "tracked files",
                 "count": 1, "evidence": None}],
    "claims": [
        {"text": "Caller holds a Widget", "kind": "fact", "load_bearing": True,
         "supporting_nodes": ["n1"], "citations": ["src/Caller.java:3"]},
    ],
    "counter_checks": [
        {"method": "qualified name", "targeted_claims": [], "new_nodes": [],
         "state": "complete"},
    ],
}


def run(ledger: dict, tmp: Path, name: str) -> tuple[int, str]:
    path = tmp / name
    path.write_text(json.dumps(ledger), encoding="utf-8")
    done = subprocess.run([sys.executable, str(VALIDATOR), "--ledger", str(path)],
                          capture_output=True, text=True)
    return done.returncode, done.stderr


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        code, err = run(VALID, tmp, "valid.json")
        assert code == 0, err

        missing_class = copy.deepcopy(VALID)
        missing_class["boundaries"] = [row for row in missing_class["boundaries"]
                                       if row["class"] != "B9"]
        code, err = run(missing_class, tmp, "missing.json")
        assert code == 1 and "B9" in err, err

        pending_node = copy.deepcopy(VALID)
        pending_node["nodes"][0]["disposition"] = "pending"
        code, err = run(pending_node, tmp, "pending-node.json")
        assert code == 1 and "disposition" in err, err

        uncited = copy.deepcopy(VALID)
        uncited["claims"][0]["citations"] = []
        code, err = run(uncited, tmp, "uncited.json")
        assert code == 1 and "citation" in err, err

        pending_check = copy.deepcopy(VALID)
        pending_check["counter_checks"][0]["state"] = "pending"
        code, err = run(pending_check, tmp, "pending-check.json")
        assert code == 1 and "pending" in err, err

        # A Q4 run needs a code/test/gap verdict on every node.
        q4 = copy.deepcopy(VALID)
        q4["run"]["type"] = "Q4"
        code, err = run(q4, tmp, "q4.json")
        assert code == 1 and "code/test/gap" in err, err

        # A table missing entirely is one defect, not a crash.
        no_table = copy.deepcopy(VALID)
        del no_table["queries"]
        code, err = run(no_table, tmp, "no-table.json")
        assert code == 1 and "queries" in err, err

    print("validate_coverage_smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
