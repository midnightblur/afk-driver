#!/usr/bin/env python3
"""Smoke test for seed_map.py against a disposable fixture repository.

Run directly: python seed_map_smoke.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED_MAP = HERE.parent / "seed_map.py"

FILES = {
    "moduleone/src/Widget.java": "class Widget extends BaseWidget {\n  void run() {}\n}\n",
    "moduleone/src/WidgetListener.java": "@EventListener\nclass WidgetListener {\n  void on(Widget w) {}\n}\n",
    "moduletwo/src/Caller.java": 'class Caller {\n  String key = "Widget";\n  Widget w;\n}\n',
    "moduleone/src/test/WidgetTest.java": "class WidgetTest {\n  void t() { new Widget(); }\n}\n",
    "config/application.yml": "widget:\n  enabled: true\n  name: Widget\n",
    "docs/overview.md": "The Widget carries the run.\n",
    "pom.xml": (
        "<project><modules>\n"
        "  <module>moduleone</module>\n"
        "  <!-- <module>moduletwo</module> -->\n"
        "</modules></project>\n"
    ),
    ".afk/config.yaml": (
        "schema: 1\n"
        "tracker: none\n"
        "forge: none\n"
        "notes: repo-files\n"
        "investigation:\n"
        "  boundaries:\n"
        "    - name: event-listener\n"
        "      class: B11\n"
        "      pattern: '@EventListener'\n"
        "    - name: message-name\n"
        "      class: B4\n"
        "      judgment-only: true\n"
        "      site: moduletwo/src/Caller.java\n"
        "  generated:\n"
        "    - target/generated\n"
        "  reactor:\n"
        "    - pom.xml\n"
    ),
}


def build(root: Path) -> None:
    for name, body in FILES.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    run = lambda *a: subprocess.run(["git", *a], cwd=str(root), check=True,
                                    capture_output=True, text=True)
    run("init", "-q")
    run("config", "user.email", "smoke@example.invalid")
    run("config", "user.name", "smoke")
    run("add", "-A")
    run("commit", "-qm", "fixture")


def seed(root: Path, out: Path, config: str) -> dict:
    done = subprocess.run(
        [sys.executable, str(SEED_MAP), "--repo", str(root), "--subject", "Widget",
         "--type", "Q2", "--config", config, "--out", str(out)],
        capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def by_class(result: dict) -> dict:
    return {row["class"]: row for row in result["boundaries"]}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        build(root)
        out = Path(tmp) / "seed.json"

        declared = by_class(seed(root, out, "auto"))
        # B1 sees the name in source, test, config, doc and the string literal.
        assert declared["B1"]["count"] >= 6, declared["B1"]["count"]
        assert declared["B2"]["status"] == "closed" and declared["B2"]["count"] >= 1
        assert declared["B4"]["status"] == "judgment-only", declared["B4"]
        assert declared["B4"]["sites"] == ["moduletwo/src/Caller.java"]
        # The generated directory is absent, so it is frontier, never absence.
        assert declared["B6"]["status"] == "frontier", declared["B6"]
        assert "unbuilt" in declared["B6"]["reason"]
        assert declared["B7"]["modules"]["declared"] == ["moduleone"]
        assert declared["B7"]["modules"]["commented_out"] == ["moduletwo"]
        assert declared["B8"]["count"] >= 1, declared["B8"]
        assert declared["B11"]["count"] >= 1, declared["B11"]
        assert declared["B12"]["count"] >= 1, declared["B12"]
        assert declared["B13"]["count"] >= 1, declared["B13"]
        assert declared["B14"]["status"] == "frontier"
        for klass in ("B3", "B5", "B10"):
            assert declared[klass]["status"] == "unverified", declared[klass]
            assert declared[klass]["reason"] == "no enumeration method"

        # The same tree twice: the inventory hash is stable.
        again = seed(root, Path(tmp) / "seed2.json", "auto")
        first = json.loads(out.read_text(encoding="utf-8"))
        assert again["run"]["inventory_hash"] == first["run"]["inventory_hash"]
        assert again["run"]["inventory_count"] == len(FILES)

        # No config: the defaults run alone and every class without one says so.
        empty = Path(tmp) / "empty.yaml"
        empty.write_text("schema: 1\ntracker: none\nforge: none\nnotes: repo-files\n",
                         encoding="utf-8")
        defaults = by_class(seed(root, Path(tmp) / "seed3.json", str(empty)))
        for klass in ("B3", "B5", "B6", "B7", "B10"):
            assert defaults[klass]["status"] == "unverified", defaults[klass]
            assert defaults[klass]["reason"] == "no enumeration method"
        assert defaults["B1"]["count"] == declared["B1"]["count"]

    print("seed_map_smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
