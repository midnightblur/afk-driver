"""The A-suite's home (subtask 0003-mc-renderer's ## Produces anchor):
A1 full-fixture golden, A2 path-fence exit 2 + nothing written, A3
absent-per-panel x5, A4 self-containment, A5 GET-only/read-only, A6
idempotent re-render. Fixture layout below is executor latitude (SDD §0).
"""
from __future__ import annotations

import http.client
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import mission_control  # noqa: E402
from mc import server  # noqa: E402
from mc.vm import Absent  # noqa: E402

_SDD_TEXT = """# SDD - fixture

## S2 L1 - System Topology

```mermaid
flowchart LR
    A --> B
```

## S8 L7 - Module Decomposition

```mermaid
flowchart TB
    M1 --> M2
```
"""

_PROGRESS_SECTION = """## Progress tracker

| # | Subtask | Title | Status |
|---|---------|-------|--------|
| 1 | 0001-sample | Sample subtask | done |
"""

_SEAM_SECTION = """## Seam register

| # | Seam (SDD §9b row) | Implemented by | Used by |
|---|--------------------|-----------------|---------|
| 1 | "git binary" | 0001-sample | 0002-sample |
"""

_SMOKE_SECTION = """## Feature smoke gate

| # | Scenario (integrated) | Modality | Status |
|---|------------------------|----------|--------|
| 1 | Sample scenario | api | pending |
"""

_PREFLIGHT_SECTION = """## Preflight

| # | Step | Status | Cycle | Evidence |
|---|------|--------|-------|----------|
| 1 | PF-1 merge origin/master | green | 0 | commit abc123 |
"""

_JOURNAL_TEXT = (
    "# Journal - append-only event log "
    "(format: skills/afk/to-subtasks/JOURNAL-FORMAT.md). Newest last.\n\n"
    "2026-07-07 09:00 | execute | 0001-sample | done "
    "— fixture event for the timeline panel test\n"
)

_REVIEW_INDEX_TEXT = """| Subtask | Latest report | Verdict | crit/high/med/low | Open advisories |
|---|---|---|---|---|
| 0001-sample | 0001-sample-abc123.md | clean | 0/0/0/0 | none |
"""

# A well-formed understanding artifact — a frozen shell copy carrying the one
# `afk-understanding` meta element (both fields populated), mirroring the shell
# asset the panel parses. Toy data only.
_UNDERSTANDING_GENERATED = "2026-07-14"
_UNDERSTANDING_DIFF_RANGE = "abc1234..def5678"
_UNDERSTANDING_HTML = (
    "<!doctype html>\n"
    '<html lang="en" data-theme="dark">\n'
    "<head>\n"
    '<meta charset="utf-8">\n'
    '<meta name="afk-understanding"\n'
    f'      data-generated="{_UNDERSTANDING_GENERATED}"\n'
    f'      data-diff-range="{_UNDERSTANDING_DIFF_RANGE}"\n'
    f'      content="generated={_UNDERSTANDING_GENERATED}; diff-range={_UNDERSTANDING_DIFF_RANGE}">\n'
    "<title>Understanding &mdash; fixture</title>\n"
    "</head>\n"
    "<body><main>toy understanding artifact</main></body>\n"
    "</html>\n"
)

# Malformed artifacts — present file, but the panel must return Absent (never
# raise) per the lockstep format contract's well-formedness rule.
_UNDERSTANDING_HTML_NO_META = (
    "<!doctype html>\n"
    '<html lang="en"><head><meta charset="utf-8">'
    "<title>no meta</title></head><body><main>artifact without the header</main></body></html>\n"
)
_UNDERSTANDING_HTML_EMPTY_FIELDS = (
    "<!doctype html>\n"
    "<html><head>\n"
    '<meta name="afk-understanding" data-generated="" data-diff-range="">\n'
    "</head><body><main>empty fields</main></body></html>\n"
)
# content=-only variant — exercises the panel's fallback extraction when the
# shell carries the fields on `content=` without the data-* attributes.
_UNDERSTANDING_HTML_CONTENT_ONLY = (
    "<!doctype html>\n"
    "<html><head>\n"
    '<meta name="afk-understanding" '
    f'content="generated={_UNDERSTANDING_GENERATED}; diff-range={_UNDERSTANDING_DIFF_RANGE}">\n'
    "</head><body><main>content-only</main></body></html>\n"
)


def _write_understanding(spec_dir: Path, html_text: str) -> None:
    u_dir = spec_dir / "understanding"
    u_dir.mkdir(parents=True, exist_ok=True)
    (u_dir / "index.html").write_text(html_text, encoding="utf-8")


_SUBTASK_TEXT = """# 0001-sample

## Produces
- scripts/sample.py#`SAMPLE_ANCHOR` — a fixture anchor for the design-map panel test

## Consumes
- 0000-other scripts/other.py#`OTHER_ANCHOR` — a fixture consumed anchor
"""


def _git(base: Path, args: list) -> None:
    result = subprocess.run(
        ["git", "-C", str(base), *args], capture_output=True, text=True
    )
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"


def _build_fixture(
    base: Path,
    *,
    plan_progress: bool = True,
    plan_smoke: bool = True,
    plan_preflight: bool = False,
    journal: bool = True,
    sdd: bool = True,
    review_index: bool = True,
    understanding: bool = True,
    git_init: bool = True,
    git_commit: bool = True,
) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    if sdd:
        (base / "SDD.md").write_text(_SDD_TEXT, encoding="utf-8")

    if understanding:
        u_dir = base / "understanding"
        u_dir.mkdir(parents=True, exist_ok=True)
        (u_dir / "index.html").write_text(_UNDERSTANDING_HTML, encoding="utf-8")

    plan_dir = base / "plan"
    any_plan_section = plan_progress or plan_smoke or plan_preflight
    if any_plan_section or journal or review_index:
        plan_dir.mkdir(parents=True, exist_ok=True)

    if any_plan_section:
        sections = []
        if plan_progress:
            sections.append(_PROGRESS_SECTION)
            sections.append(_SEAM_SECTION)
        if plan_smoke:
            sections.append(_SMOKE_SECTION)
        if plan_preflight:
            sections.append(_PREFLIGHT_SECTION)
        (plan_dir / "PLAN.md").write_text("# Plan\n\n" + "\n\n".join(sections) + "\n", encoding="utf-8")

    if journal:
        (plan_dir / "JOURNAL.md").write_text(_JOURNAL_TEXT, encoding="utf-8")

    if review_index:
        review_dir = plan_dir / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "INDEX.md").write_text(_REVIEW_INDEX_TEXT, encoding="utf-8")

    if any_plan_section or journal or review_index:
        (plan_dir / "0001-sample.md").write_text(_SUBTASK_TEXT, encoding="utf-8")

    if git_init:
        _git(base, ["init", "-q"])
        _git(base, ["config", "user.email", "mc-tests@example.com"])
        _git(base, ["config", "user.name", "MC Tests"])
        if git_commit:
            (base / "README-fixture.md").write_text("fixture\n", encoding="utf-8")
            _git(base, ["add", "-A"])
            _git(base, ["commit", "-q", "-m", "[0001-sample] fixture commit"])

    return base


def _panel_fragment(html_text: str, panel_id: str) -> str:
    """The `<section …>…</section>` card for one panel (cards don't nest)."""
    match = re.search(
        r'<section[^>]*data-panel="' + re.escape(panel_id) + r'".*?</section>',
        html_text,
        re.DOTALL,
    )
    return match.group(0) if match else ""


class MissionControlContractTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    # A1 - full fixture render -> exit 0, golden HTML per panel
    def test_full_fixture_golden(self):
        spec_dir = _build_fixture(self.base / "feature", plan_preflight=True)
        out_dir = spec_dir / "plan" / "mission-control"

        exit_code = mission_control.main(["--once", str(spec_dir)])

        self.assertEqual(exit_code, mission_control.EXIT_OK)
        html_text = (out_dir / "index.html").read_text(encoding="utf-8")

        self.assertIn('data-panel="progress"', html_text)
        self.assertIn("0001-sample", html_text)
        self.assertIn("Sample subtask", html_text)

        self.assertIn('data-panel="timeline"', html_text)
        self.assertIn("fixture event for the timeline panel test", html_text)

        self.assertIn('data-panel="design_map"', html_text)
        self.assertIn("2 design diagram(s) in SDD.md", html_text)
        self.assertIn("SAMPLE_ANCHOR", html_text)

        self.assertIn('data-panel="diffs"', html_text)
        self.assertIn("[0001-sample] fixture commit", html_text)

        self.assertIn('data-panel="gates"', html_text)
        self.assertIn("PF-1 merge origin/master", html_text)
        self.assertIn("0001-sample-abc123.md", html_text)

        # Understanding panel: repo-relative path as plain text + the two chips
        # parsed from the afk-understanding meta header. No hyperlink.
        self.assertIn('data-panel="understanding"', html_text)
        self.assertIn("understanding/index.html", html_text)
        self.assertIn(_UNDERSTANDING_GENERATED, html_text)
        self.assertIn(_UNDERSTANDING_DIFF_RANGE, html_text)
        understanding_card = _panel_fragment(html_text, "understanding")
        self.assertNotIn("<a ", understanding_card)
        self.assertNotIn("href", understanding_card)

        self.assertNotIn("mc-card-absent", html_text)

    # A2 - path outside fence -> exit 2, nothing written
    def test_path_fence_exit_2(self):
        outside = Path(tempfile.mkdtemp())
        try:
            with self.assertRaises(SystemExit) as ctx:
                mission_control.main(["--once", str(outside)])
            self.assertEqual(ctx.exception.code, mission_control.EXIT_PATH_FENCE)
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    # A3 - missing source per panel -> Absent card, others golden, exit 0
    def test_absent_state_per_panel(self):
        def panels_for(spec_dir):
            return {p.panel_id: p for p in (parser(spec_dir) for parser in mission_control.PANEL_PARSERS)}

        spec = _build_fixture(self.base / "no-plan", plan_progress=False, plan_smoke=False)
        panels = panels_for(spec)
        self.assertIsInstance(panels["progress"], Absent)
        self.assertNotIsInstance(panels["timeline"], Absent)

        spec = _build_fixture(self.base / "no-journal", journal=False)
        panels = panels_for(spec)
        self.assertIsInstance(panels["timeline"], Absent)
        self.assertNotIsInstance(panels["progress"], Absent)

        spec = _build_fixture(self.base / "no-sdd", sdd=False)
        panels = panels_for(spec)
        self.assertIsInstance(panels["design_map"], Absent)
        self.assertNotIsInstance(panels["progress"], Absent)

        spec = _build_fixture(self.base / "no-commits", git_commit=False)
        panels = panels_for(spec)
        self.assertIsInstance(panels["diffs"], Absent)
        self.assertNotIsInstance(panels["progress"], Absent)

        spec = _build_fixture(self.base / "no-gates", plan_smoke=False, plan_preflight=False, review_index=False)
        panels = panels_for(spec)
        self.assertIsInstance(panels["gates"], Absent)
        self.assertNotIsInstance(panels["progress"], Absent)

        spec = _build_fixture(self.base / "no-understanding", understanding=False)
        panels = panels_for(spec)
        self.assertIsInstance(panels["understanding"], Absent)
        self.assertNotIsInstance(panels["progress"], Absent)

        # Present file but no afk-understanding meta element -> Absent, no raise
        # (panels_for calls every parser; a raise would fail the comprehension).
        spec = _build_fixture(self.base / "understanding-no-meta", understanding=False)
        _write_understanding(spec, _UNDERSTANDING_HTML_NO_META)
        panels = panels_for(spec)
        self.assertIsInstance(panels["understanding"], Absent)

        # Meta present but both fields empty -> Absent (malformed header).
        spec = _build_fixture(self.base / "understanding-empty-fields", understanding=False)
        _write_understanding(spec, _UNDERSTANDING_HTML_EMPTY_FIELDS)
        panels = panels_for(spec)
        self.assertIsInstance(panels["understanding"], Absent)

    # A4 - page self-contained: zero external refs, opens via file://
    def test_page_self_contained(self):
        spec_dir = _build_fixture(self.base / "contained")
        out_dir = spec_dir / "plan" / "mission-control"

        mission_control.main(["--once", str(spec_dir)])

        html_text = (out_dir / "index.html").read_text(encoding="utf-8")
        self.assertNotRegex(html_text, r'(src|href)\s*=\s*"https?://')
        self.assertNotIn("<link", html_text)
        self.assertNotIn("<script src", html_text)

        # The understanding panel's fragment is part of the self-contained page
        # and carries no reference out (no external ref, no relocatable link).
        understanding_card = _panel_fragment(html_text, "understanding")
        self.assertIn("understanding/index.html", understanding_card)
        self.assertNotRegex(understanding_card, r'(src|href)\s*=')

    # Understanding panel: fields carried on `content=` only (no data-* attrs)
    # still render via the fallback extraction.
    def test_understanding_content_only_fallback(self):
        from mc.panels import understanding as understanding_panel

        spec = _build_fixture(self.base / "content-only", understanding=False)
        _write_understanding(spec, _UNDERSTANDING_HTML_CONTENT_ONLY)

        panel = understanding_panel.parse(spec)
        self.assertNotIsInstance(panel, Absent)
        self.assertIn(_UNDERSTANDING_GENERATED, panel.html)
        self.assertIn(_UNDERSTANDING_DIFF_RANGE, panel.html)

    # A5 - GET-only server; page has no mutating control
    def test_get_only_read_only(self):
        spec_dir = _build_fixture(self.base / "serve")
        out_dir = spec_dir / "plan" / "mission-control"

        httpd = server.watch_and_serve(spec_dir, out_dir, 0, mission_control.PANEL_PARSERS)
        self.assertEqual(httpd.server_address[0], "127.0.0.1")
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            port = httpd.server_address[1]

            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/index.html")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            body = resp.read()
            conn.close()
            self.assertNotIn(b"<button", body)
            self.assertNotIn(b"onclick=", body)

            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("POST", "/index.html")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 501)
            resp.read()
            conn.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # A7 - watch mode detects an edit and re-renders, even when the feature's
    # own spec_dir is literally named "mission-control" (regression: the
    # watcher's self-exclusion previously matched on that bare path
    # component, silently excluding every file whenever spec_dir itself was
    # named "mission-control" and permanently disabling change detection).
    def test_watch_detects_edit_when_spec_dir_named_mission_control(self):
        spec_dir = _build_fixture(self.base / "mission-control")
        out_dir = spec_dir / "plan" / "mission-control"

        httpd = server.watch_and_serve(spec_dir, out_dir, 0, mission_control.PANEL_PARSERS, debounce=0.1)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            port = httpd.server_address[1]
            time.sleep(0.3)  # let the watcher take its initial snapshot before we edit
            (spec_dir / "plan" / "JOURNAL.md").write_text(
                _JOURNAL_TEXT + "2026-07-07 10:00 | execute | 0001-sample | edited for watch-mode test\n",
                encoding="utf-8",
            )

            deadline = time.monotonic() + 5
            updated = False
            while time.monotonic() < deadline:
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                conn.request("GET", "/index.html")
                resp = conn.getresponse()
                body = resp.read()
                conn.close()
                if b"edited for watch-mode test" in body:
                    updated = True
                    break
                time.sleep(0.2)

            self.assertTrue(updated, "watch mode never re-rendered after the JOURNAL.md edit")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # A6 - unchanged fixture re-render -> byte-identical
    def test_idempotent_rerender(self):
        spec_dir = _build_fixture(self.base / "idem")
        out_dir = spec_dir / "plan" / "mission-control"

        mission_control.main(["--once", str(spec_dir)])
        first = (out_dir / "index.html").read_bytes()
        mission_control.main(["--once", str(spec_dir)])
        second = (out_dir / "index.html").read_bytes()

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
