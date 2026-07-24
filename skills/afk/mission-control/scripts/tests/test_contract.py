"""The A-suite (drift alarm for the lockstep formats + the two-layer page):
A1 full-fixture golden (asserted on the embedded mc-data JSON), A2 path-fence
exit 2 + nothing written, A3 absent-per-section, A4 self-containment, A5
GET-only/read-only (no form, no fetch in inert output), A6 idempotent
re-render, A7 watch re-render, A8 digest staleness fence, A9 malformed
digest degrades not crashes, A10 sub-phase derivation. Fixture layout is
executor latitude (SDD §0).
"""
from __future__ import annotations

import hashlib
import http.client
import json
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

_PLAN_HEADER = """# Plan - fixture feature

> Parent ticket: TIX-1   Mode: cited
> Branch (for /afk:execute): dev/fixture
> Feature: complete (smoke green 2026-07-07, target=local)
"""

_PROGRESS_SECTION = """## Progress tracker

| # | Subtask | Title | Status | Blocked by | Tiers | Seams |
|---|---------|-------|--------|------------|-------|-------|
| 1 | 0001-sample | Sample subtask | done | — | static, unit | — |
| 2 | 0002-follow | Follow-up subtask | reviewing | 0001 | static | — |
"""

_SEAM_SECTION = """## Seam register

| # | Seam (SDD §9b row) | Implemented by | Used by |
|---|--------------------|-----------------|---------|
| 1 | "git binary" | 0001-sample | 0002-follow |
"""

_SMOKE_SECTION = """## Feature smoke gate

> Gate: smoke   Suite: fixture
> Last run: 2026-07-07, target=local - smoke green
> Run history:
> - 2026-07-06 local - smoke-failing, failing: S1

| # | Scenario (integrated) | Modality | Status |
|---|------------------------|----------|--------|
| 1 | Sample scenario | api | pending |
"""

_PREFLIGHT_SECTION = """## Preflight   <!-- created on first run -->

| # | Step | Status | Cycle | Evidence |
|---|------|--------|-------|----------|
| 1 | PF-1 merge origin/master | green | 0 | commit abc123 |
"""

_JOURNAL_TEXT = (
    "# Journal - append-only event log "
    "(format: skills/afk/to-subtasks/JOURNAL-FORMAT.md). Newest last.\n\n"
    "2026-07-07 09:00 | execute | 0001-sample | done "
    "— fixture event for the timeline panel test\n"
    "2026-07-07 09:30 | execute | 0002-follow | reviewing "
    "— independent review spawned\n"
)

_REVIEW_INDEX_TEXT = """| Subtask | Latest report | Verdict | crit/high/med/low | Open advisories |
|---|---|---|---|---|
| 0001-sample | 0001-sample-abc123.md | clean | 0/0/0/0 | none |
| 0002-follow | 0002-follow-abc123.md | advisory (cycle 2) | 0/0/1/0 | one medium kept |
"""

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
_UNDERSTANDING_HTML_CONTENT_ONLY = (
    "<!doctype html>\n"
    "<html><head>\n"
    '<meta name="afk-understanding" '
    f'content="generated={_UNDERSTANDING_GENERATED}; diff-range={_UNDERSTANDING_DIFF_RANGE}">\n'
    "</head><body><main>content-only</main></body></html>\n"
)

_SUBTASK_TEXT = """# 0001-sample

## Complexity
standard

## Produces
- scripts/sample.py#`SAMPLE_ANCHOR` — a fixture anchor for the architecture live overlay

## Consumes
- 0000-other scripts/other.py#OTHER_ANCHOR — a fixture consumed anchor

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | grep SAMPLE_ANCHOR | anchor present |
"""

# minimal valid digest per type (structural floor per mc/digests.DIGEST_SPECS)
_DIGESTS = {
    "architecture": {"modules": [{"id": "M1", "name": "core", "responsibility": "does the fixture work",
                                  "depends_on": [], "subtasks": ["0001-sample"]}]},
    "flows": {"flows": [{"id": "f1", "title": "happy path", "kind": "linear",
                         "steps": [{"t": "1 · Start", "who": "you", "d": "kick it off"}]}]},
    "entities": {"entities": [{"id": "E1", "name": "Sample", "essence": "the fixture entity",
                               "fields": [{"name": "id", "type": "long", "essential": True}]}]},
    "adrs": {"adrs": [{"id": "0001", "tier": "design", "title": "fixture decision",
                       "essence": "decide the fixture way"}]},
    "critical-logic": {"items": [{"id": "c1", "kind": "invariant", "title": "fixture invariant",
                                  "statement": "the fixture must not break"}]},
    "legend": {"terms": [{"term": "done", "definition": "the subtask finished every gate"}]},
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(base: Path, args: list) -> None:
    result = subprocess.run(
        ["git", "-C", str(base), *args], capture_output=True, text=True
    )
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"


def _write_understanding(spec_dir: Path, html_text: str) -> None:
    u_dir = spec_dir / "understanding"
    u_dir.mkdir(parents=True, exist_ok=True)
    (u_dir / "index.html").write_text(html_text, encoding="utf-8")


def _write_digests(spec_dir: Path, names=None, manifest_ok: bool = True) -> None:
    d_dir = spec_dir / "plan" / "digests"
    d_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in (names or _DIGESTS):
        (d_dir / f"{name}.json").write_text(json.dumps(_DIGESTS[name]), encoding="utf-8")
        source = spec_dir / "SDD.md"
        digest_hash = _sha256(source) if (manifest_ok and source.is_file()) else "0" * 64
        manifest[name] = {"sources": [{"path": "SDD.md", "sha256": digest_hash}],
                          "built_at": "2026-07-07 09:00"}
    (d_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


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
    digests: bool = False,
    digests_stale: bool = False,
    git_init: bool = True,
    git_commit: bool = True,
) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    if sdd:
        (base / "SDD.md").write_text(_SDD_TEXT, encoding="utf-8")

    if understanding:
        _write_understanding(base, _UNDERSTANDING_HTML)

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
        (plan_dir / "PLAN.md").write_text(_PLAN_HEADER + "\n" + "\n\n".join(sections) + "\n", encoding="utf-8")

    if journal:
        (plan_dir / "JOURNAL.md").write_text(_JOURNAL_TEXT, encoding="utf-8")

    if review_index:
        review_dir = plan_dir / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "INDEX.md").write_text(_REVIEW_INDEX_TEXT, encoding="utf-8")

    if any_plan_section or journal or review_index:
        (plan_dir / "0001-sample.md").write_text(_SUBTASK_TEXT, encoding="utf-8")

    if digests:
        _write_digests(base, manifest_ok=not digests_stale)

    if git_init:
        _git(base, ["init", "-q"])
        _git(base, ["config", "user.email", "mc-tests@example.com"])
        _git(base, ["config", "user.name", "MC Tests"])
        if git_commit:
            (base / "README-fixture.md").write_text("fixture\n", encoding="utf-8")
            _git(base, ["add", "-A"])
            _git(base, ["commit", "-q", "-m", "[0001-sample] fixture commit"])

    return base


def _mc_data(html_text: str) -> dict:
    match = re.search(
        r'<script id="mc-data" type="application/json">(.*?)</script>',
        html_text,
        re.DOTALL,
    )
    assert match, "no mc-data blob in the page"
    return json.loads(match.group(1).replace("<\\/", "</"))


def _sections(html_text: str) -> dict:
    return {s["id"]: s for s in _mc_data(html_text)["sections"]}


def _parse_all(spec_dir: Path) -> dict:
    return {
        (vm.section_id): vm
        for vm in (parser(spec_dir) for parser in mission_control.SECTION_PARSERS)
    }


class MissionControlContractTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    # A1 - full fixture render -> exit 0, every section present + populated
    def test_full_fixture_golden(self):
        spec_dir = _build_fixture(self.base / "feature", plan_preflight=True, digests=True)
        out_dir = spec_dir / "plan" / "mission-control"

        exit_code = mission_control.main(["--once", str(spec_dir)])
        self.assertEqual(exit_code, mission_control.EXIT_OK)

        sections = _sections((out_dir / "index.html").read_text(encoding="utf-8"))
        expected = ["overview", "architecture", "flows", "entities", "decisions",
                    "critical-logic", "progress", "timeline", "gates", "insights",
                    "diffs", "legend"]
        self.assertEqual([s for s in expected if s in sections], expected)
        for sid in expected:
            self.assertNotEqual(sections[sid]["state"], "absent", sid)

        # live layer content
        progress = sections["progress"]["data"]
        self.assertEqual(len(progress["subtasks"]), 2)
        self.assertEqual(progress["subtasks"][0]["id"], "0001-sample")
        self.assertEqual(progress["subtasks"][0]["complexity"], "standard")
        self.assertEqual(progress["subtasks"][0]["commits"][0]["subject"], "[0001-sample] fixture commit")
        self.assertEqual(progress["subtasks"][1]["blocked_by"], ["0001-sample"])

        timeline = sections["timeline"]["data"]
        self.assertIn("fixture event for the timeline panel test",
                      json.dumps(timeline["events"]))

        gates = sections["gates"]["data"]
        self.assertEqual(gates["preflight"]["rows"][0]["Step"], "PF-1 merge origin/master")
        self.assertEqual(gates["smoke"]["rows"][0]["Modality"], "api")
        self.assertTrue(gates["smoke"]["last_run"].startswith("2026-07-07"))
        self.assertEqual(len(gates["review_rollup"]["rows"]), 2)

        arch = sections["architecture"]["data"]
        self.assertEqual(sections["architecture"]["state"], "ok")
        self.assertEqual(arch["digest"]["modules"][0]["id"], "M1")
        anchors = arch["live"]["anchors"]
        self.assertIn("SAMPLE_ANCHOR", json.dumps(anchors))
        self.assertEqual(arch["live"]["sdd_diagram_count"], 2)

        overview = sections["overview"]["data"]
        self.assertEqual(overview["header"]["parent_ticket"], "TIX-1")
        self.assertEqual(overview["understanding"]["generated"], _UNDERSTANDING_GENERATED)
        self.assertEqual(overview["understanding"]["diff_range"], _UNDERSTANDING_DIFF_RANGE)

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

    # A3 - missing source per live section -> Absent, others unaffected
    def test_absent_state_per_section(self):
        spec = _build_fixture(self.base / "no-plan", plan_progress=False, plan_smoke=False, review_index=False)
        vms = _parse_all(spec)
        self.assertIsInstance(vms["progress"], Absent)
        self.assertNotIsInstance(vms["timeline"], Absent)

        spec = _build_fixture(self.base / "no-journal", journal=False)
        vms = _parse_all(spec)
        self.assertIsInstance(vms["timeline"], Absent)
        self.assertNotIsInstance(vms["progress"], Absent)

        spec = _build_fixture(self.base / "no-commits", git_commit=False)
        vms = _parse_all(spec)
        self.assertIsInstance(vms["diffs"], Absent)
        self.assertNotIsInstance(vms["progress"], Absent)

        spec = _build_fixture(self.base / "no-gates", plan_smoke=False, plan_preflight=False, review_index=False)
        vms = _parse_all(spec)
        self.assertIsInstance(vms["gates"], Absent)
        self.assertNotIsInstance(vms["progress"], Absent)

        # digest sections without digests are missing-state, never Absent/crash
        spec = _build_fixture(self.base / "no-digests")
        vms = _parse_all(spec)
        for sid in ("flows", "entities", "decisions", "critical-logic", "legend", "architecture"):
            self.assertNotIsInstance(vms[sid], Absent, sid)
            self.assertEqual(vms[sid].state, "missing", sid)
        # architecture's live overlay still renders without the digest
        self.assertTrue(vms["architecture"].data["live"]["seams"])

    # A4 - page self-contained: zero external refs, opens via file://
    def test_page_self_contained(self):
        spec_dir = _build_fixture(self.base / "contained", digests=True)
        out_dir = spec_dir / "plan" / "mission-control"

        mission_control.main(["--once", str(spec_dir)])

        html_text = (out_dir / "index.html").read_text(encoding="utf-8")
        self.assertNotRegex(html_text, r'(src|href)\s*=\s*"https?://')
        self.assertNotIn("<link", html_text)
        self.assertNotIn("<script src", html_text)

    # A5 - GET-only server; inert --once page has no form and no fetch at all
    def test_get_only_read_only(self):
        spec_dir = _build_fixture(self.base / "serve")
        out_dir = spec_dir / "plan" / "mission-control"

        # inert retro output: no reload poller, no fetch, no form
        mission_control.main(["--once", str(spec_dir)])
        once_text = (out_dir / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<form", once_text)
        self.assertNotIn("fetch(", once_text)

        httpd = server.watch_and_serve(spec_dir, out_dir, 0, mission_control.SECTION_PARSERS)
        self.assertEqual(httpd.server_address[0], "127.0.0.1")
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            port = httpd.server_address[1]

            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/index.html")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            body = resp.read().decode("utf-8")
            conn.close()
            self.assertNotIn("<form", body)
            # watch mode's only network call is the GET reload-token poll
            self.assertEqual(body.count("fetch("), 1)
            self.assertIn("/__mc_token", body)

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

    # A6 - unchanged fixture re-render -> byte-identical
    def test_idempotent_rerender(self):
        spec_dir = _build_fixture(self.base / "idem", digests=True)
        out_dir = spec_dir / "plan" / "mission-control"

        mission_control.main(["--once", str(spec_dir)])
        first = (out_dir / "index.html").read_bytes()
        mission_control.main(["--once", str(spec_dir)])
        second = (out_dir / "index.html").read_bytes()

        self.assertEqual(first, second)

    # A7 - watch mode detects an edit and re-renders, even when the feature's
    # own spec_dir is literally named "mission-control" (regression guard)
    def test_watch_detects_edit_when_spec_dir_named_mission_control(self):
        spec_dir = _build_fixture(self.base / "mission-control")
        out_dir = spec_dir / "plan" / "mission-control"

        httpd = server.watch_and_serve(spec_dir, out_dir, 0, mission_control.SECTION_PARSERS, debounce=0.1)
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

    # A8 - digest staleness fence: wrong source hash -> stale + reason; also
    # surfaced by --check-digests
    def test_digest_staleness_fence(self):
        spec_dir = _build_fixture(self.base / "stale", digests=True, digests_stale=True)
        vms = _parse_all(spec_dir)
        for sid in ("flows", "architecture", "legend"):
            self.assertEqual(vms[sid].state, "stale", sid)
            self.assertIn("SDD.md", vms[sid].reason)
        # stale still carries the old data — shown behind the banner
        self.assertIsNotNone(vms["flows"].data)

        from mc import digests as digests_mod
        report = digests_mod.status(spec_dir)
        self.assertEqual(report["flows"]["state"], "stale")
        self.assertEqual(report["flows"]["stale_sources"], ["SDD.md"])

        # fixing the manifest hash flips everything to ok
        _write_digests(spec_dir, manifest_ok=True)
        vms = _parse_all(spec_dir)
        self.assertEqual(vms["flows"].state, "ok")

    # A9 - malformed digest -> invalid state, exit 0, other sections fine
    def test_malformed_digest_degrades(self):
        spec_dir = _build_fixture(self.base / "malformed", digests=True)
        d_dir = spec_dir / "plan" / "digests"
        (d_dir / "flows.json").write_text("{not json", encoding="utf-8")
        (d_dir / "adrs.json").write_text(json.dumps({"adrs": [{"id": "0001"}]}), encoding="utf-8")

        exit_code = mission_control.main(["--once", str(spec_dir)])
        self.assertEqual(exit_code, mission_control.EXIT_OK)
        sections = _sections(
            (spec_dir / "plan" / "mission-control" / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(sections["flows"]["state"], "invalid")
        self.assertEqual(sections["decisions"]["state"], "invalid")
        self.assertIn("missing required string field", sections["decisions"]["reason"])
        self.assertEqual(sections["entities"]["state"], "ok")

    # A10 - sub-phase derivation: reviewing + round file + verdict-cell cycle
    def test_sub_phase_derivation(self):
        spec_dir = _build_fixture(self.base / "subphase")
        review_dir = spec_dir / "plan" / "review"
        (review_dir / "0002-follow-abc123-r2.outcomes.json").write_text(
            json.dumps({"r-001": "fixed"}), encoding="utf-8")

        vms = _parse_all(spec_dir)
        subtasks = {s["id"]: s for s in vms["progress"].data["subtasks"]}
        self.assertEqual(subtasks["0002-follow"]["rounds"], 2)
        self.assertEqual(subtasks["0002-follow"]["sub_phase"], "settle round 2")
        # done subtask summarizes its review verdict
        self.assertIn("review clean", subtasks["0001-sample"]["sub_phase"])

    # understanding meta fields carried on `content=` only still parse
    def test_understanding_content_only_fallback(self):
        from mc.sections import understanding as understanding_section

        spec = _build_fixture(self.base / "content-only", understanding=False)
        _write_understanding(spec, _UNDERSTANDING_HTML_CONTENT_ONLY)

        card, reason = understanding_section.parse(spec)
        self.assertEqual(reason, "")
        self.assertEqual(card["generated"], _UNDERSTANDING_GENERATED)
        self.assertEqual(card["diff_range"], _UNDERSTANDING_DIFF_RANGE)


if __name__ == "__main__":
    unittest.main()
