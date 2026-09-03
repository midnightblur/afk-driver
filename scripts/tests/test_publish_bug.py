#!/usr/bin/env python3
"""Payload-shape unit tests for publish_bug — no network.

The seam-test for the "Jira REST v3" boundary (SDD §9b): every test asserts on
the real payload shapes the publisher would POST/PUT (issue-create fields, the
Dev-Pending transition, evidence comment ADF, and the screenshot media embed),
built from a fixture bundle, without opening a socket. Also pins the failure
affordances the contract mandates: FixVersion validated before any write,
non-2xx surfaced with the response body (never swallowed), and the 2-retry
exponential-backoff posture (SDD §5).

Jira._req is never called for real — a recording fake stands in for the shared
client, so nothing here touches the network.
"""

import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

# publish_bug.py lives under the bug skill's scripts dir; tracker_api lives at
# the plugin-root scripts dir. Make both importable regardless of cwd.
_TESTS = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_SCRIPTS = os.path.dirname(_TESTS)                       # <root>/scripts
_WORKFLOW = os.path.dirname(_PLUGIN_SCRIPTS)                    # <root>
_BUG_SCRIPTS = os.path.join(_WORKFLOW, "skills", "afk", "bug", "scripts")
for _p in (_PLUGIN_SCRIPTS, _BUG_SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# publish_bug resolves the CONFIGURED tracker at import time. This suite tests
# the Jira publisher, so it names a configuration that selects Jira instead of
# depending on whatever this repository happens to be set to — and it puts the
# environment back, because a variable left set here would follow every other
# test module in the same interpreter.
_PRIOR_AFK_CONFIG = os.environ.get("AFK_CONFIG")
os.environ["AFK_CONFIG"] = os.path.join(_TESTS, "samples", "monorepo-config.yaml")
try:
    import publish_bug  # noqa: E402
finally:
    if _PRIOR_AFK_CONFIG is None:
        os.environ.pop("AFK_CONFIG", None)
    else:
        os.environ["AFK_CONFIG"] = _PRIOR_AFK_CONFIG


def _http_error(code, body):
    """Build a real urllib HTTPError whose .read() yields body — matches what
    urlopen raises for a non-2xx response."""
    fp = io.BytesIO(body.encode() if isinstance(body, str) else body)
    return urllib.error.HTTPError("http://x/y", code, "err", {}, fp)


class FakeResp:
    def __init__(self, status=200, body=b"", location=None):
        self.status = status
        self._body = body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode()
        self.headers = {"Location": location} if location is not None else {}

    def read(self):
        return self._body


class RecordingJira:
    """Stands in for the adapter's Jira client. Records every _req call; returns a scripted
    response (FakeResp) or raises a scripted HTTPError, matched by call order or
    by a handler."""

    def __init__(self, handler=None):
        self.calls = []          # list of (method, path, payload-or-None, headers)
        self.handler = handler   # fn(method, path) -> FakeResp | HTTPError | Exception
        self.base = "https://nakisa.example/jira"
        self.resolved = []       # att_ids passed to resolve_media_uuid
        self.embed_error = None  # if set, resolve_media_uuid raises it (degrade path)

    def _req(self, method, path, data=None, headers=None, follow=True):
        payload = json.loads(data) if data else None
        self.calls.append((method, path, payload, headers or {}))
        r = self.handler(method, path) if self.handler else FakeResp(200, {})
        if isinstance(r, BaseException):
            raise r
        return r

    # bug embed uses these two shared-client methods
    def upload_attachment(self, key, filepath):
        self.calls.append(("UPLOAD", f"/issue/{key}/attachments", os.path.basename(filepath), {}))
        return f"att-{os.path.basename(filepath)}"

    def resolve_media_uuid(self, att_id):
        self.resolved.append(att_id)
        if self.embed_error is not None:
            raise self.embed_error
        # Echo the att_id so a wiring bug (wrong id passed) is observable.
        return f"uuid-for-{att_id}"

    def update_description(self, key, adf):
        self.calls.append(("PUT", f"/rest/api/3/issue/{key}", {"fields": {"description": adf}}, {}))

    def posts_to(self, needle):
        return [c for c in self.calls if needle in c[1]]


FIXTURE_BUNDLE = """# Bug: totals off by one

## Summary
Invoice total shows one cent too high.

## Facts
- The rounding happens in TotalService (verified)
- Likely a half-even vs half-up mismatch (inferred)
- Could be locale-driven (guessed)

## Repro
1. Open invoice INV-9
2. Read the footer total
"""


# ---------------------------------------------------------------------------
# Pure payload builders
# ---------------------------------------------------------------------------
class TestCreateFields(unittest.TestCase):
    def test_full_create_fields_shape(self):
        desc = publish_bug.description_doc(publish_bug.bundle_to_adf(FIXTURE_BUNDLE))
        fields = publish_bug.build_create_fields(
            "P2P", "totals off by one", desc,
            assignee_account_id="acc-123", labels=["afk-bug", "mvu"],
            fix_version="2026.r1")
        f = fields["fields"]
        self.assertEqual(f["project"], {"key": "P2P"})
        self.assertEqual(f["summary"], "totals off by one")
        self.assertEqual(f["issuetype"], {"name": "Bug"})
        self.assertEqual(f["assignee"], {"accountId": "acc-123"})
        self.assertEqual(f["labels"], ["afk-bug", "mvu"])
        self.assertEqual(f["fixVersions"], [{"name": "2026.r1"}])
        self.assertEqual(f["description"]["type"], "doc")

    def test_optional_fields_omitted(self):
        desc = publish_bug.description_doc(publish_bug.bundle_to_adf("# x"))
        f = publish_bug.build_create_fields("P2P", "s", desc)["fields"]
        for k in ("assignee", "labels", "fixVersions"):
            self.assertNotIn(k, f)

    def test_confidence_labels_render_in_body(self):
        # AC-005: verified/inferred/guessed labels visible in the ticket body.
        adf = publish_bug.bundle_to_adf(FIXTURE_BUNDLE)
        blob = json.dumps(adf)
        for label in ("verified", "inferred", "guessed"):
            self.assertIn(label, blob)


class TestTransitionAndComment(unittest.TestCase):
    def test_transition_payload(self):
        self.assertEqual(publish_bug.build_transition_payload(),
                         {"transition": {"id": publish_bug.DEV_PENDING_TRANSITION_ID}})
        self.assertEqual(publish_bug.DEV_PENDING_TRANSITION_ID, "12463")

    def test_comment_payload_is_adf_doc(self):
        p = publish_bug.build_comment_payload("MR posted: **link**")
        self.assertEqual(p["body"]["type"], "doc")
        self.assertEqual(p["body"]["version"], 1)
        self.assertTrue(p["body"]["content"])


# ---------------------------------------------------------------------------
# create_bug — POST wiring, key return, screenshot embed
# ---------------------------------------------------------------------------
class TestCreateBug(unittest.TestCase):
    def _created(self, method, path):
        if method == "POST" and path.endswith("/issue"):
            return FakeResp(201, {"key": "P2P-777"})
        return FakeResp(200, {})

    @staticmethod
    def _png(path):
        # 24-byte valid PNG header so png_size reads 1x1 without a real image
        with open(path, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 +
                     (1).to_bytes(4, "big") + (1).to_bytes(4, "big"))
        return path

    def test_posts_issue_and_returns_key(self):
        j = RecordingJira(self._created)
        key = publish_bug.create_bug(j, "P2P", "totals", FIXTURE_BUNDLE,
                                     assignee_account_id="acc-1", labels=["afk-bug"])
        self.assertEqual(key, "P2P-777")
        create = [c for c in j.calls if c[0] == "POST" and c[1].endswith("/issue")]
        self.assertEqual(len(create), 1)
        fields = create[0][2]["fields"]
        self.assertEqual(fields["summary"], "totals")
        self.assertEqual(fields["issuetype"], {"name": "Bug"})
        # §9b payload contract: JSON body carries the JSON content-type header.
        self.assertEqual(create[0][3].get("Content-Type"), "application/json")

    def test_no_key_in_response_surfaces_error(self):
        # A 2xx create with no key must fail cleanly, not TypeError-crash.
        j = RecordingJira(lambda m, p: FakeResp(201, b""))
        with self.assertRaises(publish_bug.BugPublishError):
            publish_bug.create_bug(j, "P2P", "s", FIXTURE_BUNDLE)

    def test_screenshot_embedded_as_media_node(self):
        j = RecordingJira(self._created)
        with tempfile.TemporaryDirectory() as td:
            png = self._png(os.path.join(td, "shot.png"))
            key = publish_bug.create_bug(j, "P2P", "s", FIXTURE_BUNDLE, screenshots=[png])
        self.assertEqual(key, "P2P-777")
        uploads = [c for c in j.calls if c[0] == "UPLOAD"]
        self.assertEqual(len(uploads), 1)
        # the att_id from upload flows into resolve_media_uuid (wiring pinned)
        self.assertEqual(j.resolved, ["att-shot.png"])
        puts = [c for c in j.calls if c[0] == "PUT"]
        self.assertTrue(puts, "description update with embedded media expected")
        media = puts[-1][2]["fields"]["description"]["content"][-1]
        self.assertEqual(media["type"], "mediaSingle")
        attrs = media["content"][0]["attrs"]
        self.assertEqual(attrs["id"], "uuid-for-att-shot.png")
        self.assertEqual((attrs["width"], attrs["height"]), (1, 1))

    def test_embed_failure_degrades_ticket_kept(self):
        # SDD §3 embed edge: a 303 with no media UUID must NOT abort create —
        # the ticket is returned, the attachment stays listed, no inline node.
        j = RecordingJira(self._created)
        j.embed_error = RuntimeError("could not resolve media UUID")
        with tempfile.TemporaryDirectory() as td:
            png = self._png(os.path.join(td, "shot.png"))
            key = publish_bug.create_bug(j, "P2P", "s", FIXTURE_BUNDLE, screenshots=[png])
        self.assertEqual(key, "P2P-777")                  # ticket kept
        self.assertEqual(len([c for c in j.calls if c[0] == "UPLOAD"]), 1)  # attached
        self.assertEqual([c for c in j.calls if c[0] == "PUT"], [])  # no inline embed


# ---------------------------------------------------------------------------
# FixVersion validation — nothing written when unknown (AC-004)
# ---------------------------------------------------------------------------
class TestFixVersion(unittest.TestCase):
    def _versions(self, method, path):
        if method == "GET" and path.endswith("/versions"):
            return FakeResp(200, [{"name": "2026.r1"}, {"name": "2026.r2"}])
        if method == "POST" and path.endswith("/issue"):
            return FakeResp(201, {"key": "P2P-9"})
        return FakeResp(200, {})

    def test_unknown_fix_version_rejected_nothing_written(self):
        j = RecordingJira(self._versions)
        with self.assertRaises(publish_bug.FixVersionError) as ctx:
            publish_bug.create_bug(j, "P2P", "s", FIXTURE_BUNDLE, fix_version="9.9.9")
        self.assertIn("9.9.9", str(ctx.exception))
        # nothing written: no issue POST happened
        self.assertEqual([c for c in j.calls if c[0] == "POST" and c[1].endswith("/issue")], [])

    def test_known_fix_version_accepted(self):
        j = RecordingJira(self._versions)
        key = publish_bug.create_bug(j, "P2P", "s", FIXTURE_BUNDLE, fix_version="2026.r1")
        self.assertEqual(key, "P2P-9")

    def test_backfill_unknown_rejected(self):
        j = RecordingJira(self._versions)
        with self.assertRaises(publish_bug.FixVersionError):
            publish_bug.backfill_fix_version(j, "P2P-9", "P2P", "does-not-exist")
        self.assertEqual([c for c in j.calls if c[0] == "PUT"], [])

    def test_backfill_known_puts_fix_version(self):
        j = RecordingJira(self._versions)
        publish_bug.backfill_fix_version(j, "P2P-9", "P2P", "2026.r2")
        puts = [c for c in j.calls if c[0] == "PUT" and c[1].endswith("/issue/P2P-9")]
        self.assertEqual(len(puts), 1)
        self.assertEqual(puts[0][2]["fields"]["fixVersions"], [{"name": "2026.r2"}])


# ---------------------------------------------------------------------------
# Failure affordance — non-2xx surfaced with body, never swallowed (SDD §9b)
# ---------------------------------------------------------------------------
class TestFailureSurfaced(unittest.TestCase):
    def test_create_400_surfaces_response_body(self):
        body = json.dumps({"errors": {"fixVersions": "Version name is not valid"}})
        j = RecordingJira(lambda m, p: _http_error(400, body))
        with self.assertRaises(publish_bug.BugPublishError) as ctx:
            publish_bug.create_bug(j, "P2P", "s", FIXTURE_BUNDLE)
        self.assertIn("Version name is not valid", str(ctx.exception))

    def test_transition_failure_surfaced_not_swallowed(self):
        body = json.dumps({"errorMessages": ["transition not available"]})
        j = RecordingJira(lambda m, p: _http_error(400, body))
        with self.assertRaises(publish_bug.BugPublishError) as ctx:
            publish_bug.transition_to_dev_pending(j, "P2P-1")
        self.assertIn("transition not available", str(ctx.exception))

    def test_comment_failure_surfaced(self):
        j = RecordingJira(lambda m, p: _http_error(404, "gone"))
        with self.assertRaises(publish_bug.BugPublishError):
            publish_bug.append_evidence_comment(j, "P2P-1", "MR: x")

    def test_4xx_not_retried(self):
        seen = {"n": 0}

        def handler(m, p):
            seen["n"] += 1
            return _http_error(400, "bad")

        j = RecordingJira(handler)
        with self.assertRaises(publish_bug.BugPublishError):
            publish_bug.transition_to_dev_pending(j, "P2P-1")
        self.assertEqual(seen["n"], 1)  # deterministic 4xx: no retry


# ---------------------------------------------------------------------------
# Retry posture — 2 retries, exponential backoff, then fail (SDD §5)
# ---------------------------------------------------------------------------
class TestRetry(unittest.TestCase):
    def test_5xx_retried_twice_then_fails(self):
        seen = {"n": 0}

        def handler(m, p):
            seen["n"] += 1
            return _http_error(503, "unavailable")

        j = RecordingJira(handler)
        with mock.patch("publish_bug.time.sleep") as slept:
            with self.assertRaises(publish_bug.BugPublishError) as ctx:
                publish_bug.transition_to_dev_pending(j, "P2P-1")
        self.assertEqual(seen["n"], 3)          # 1 attempt + 2 retries
        self.assertEqual(slept.call_count, 2)   # backoff between attempts
        # never-swallowed: the exhausted transient failure still carries the body
        self.assertIn("unavailable", str(ctx.exception))

    def test_5xx_then_success(self):
        seq = {"n": 0}

        def handler(m, p):
            seq["n"] += 1
            if seq["n"] == 1:
                return _http_error(500, "boom")
            return FakeResp(204, b"")

        j = RecordingJira(handler)
        with mock.patch("publish_bug.time.sleep"):
            publish_bug.transition_to_dev_pending(j, "P2P-1")
        self.assertEqual(seq["n"], 2)

    def test_backoff_is_exponential(self):
        j = RecordingJira(lambda m, p: _http_error(503, "x"))
        with mock.patch("publish_bug.time.sleep") as slept:
            with self.assertRaises(publish_bug.BugPublishError):
                publish_bug.transition_to_dev_pending(j, "P2P-1")
        waits = [c.args[0] for c in slept.call_args_list]
        self.assertEqual(len(waits), 2)
        self.assertLess(waits[0], waits[1])  # grows


class TestComment(unittest.TestCase):
    def test_append_evidence_comment_posts_201(self):
        j = RecordingJira(lambda m, p: FakeResp(201, {"id": "10"}))
        publish_bug.append_evidence_comment(j, "P2P-1", "MR opened: http://x")
        posts = [c for c in j.calls if c[0] == "POST" and c[1].endswith("/comment")]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][2]["body"]["type"], "doc")


class TestCli(unittest.TestCase):
    def test_missing_bundle_file_clean_exit(self):
        # An operational input error (missing --bundle) exits non-zero with a
        # clean ERROR message, not a raw traceback — and never touches Jira.
        with self.assertRaises(SystemExit) as ctx:
            publish_bug.main(["create", "--project", "P2P", "--summary", "x",
                              "--bundle", "definitely-not-here.md", "--dry-run"])
        self.assertNotEqual(ctx.exception.code, 0)
        self.assertIn("ERROR", str(ctx.exception.code))

    def test_create_dry_run_builds_payload_no_network(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = os.path.join(td, "b.md")
            with open(bundle, "w", encoding="utf-8") as fh:
                fh.write("# Bug\n- fact (verified)\n")
            # dry-run must not call load_creds / open a socket
            with mock.patch("publish_bug.load_creds",
                            side_effect=AssertionError("no network in dry-run")):
                publish_bug.main(["create", "--project", "P2P", "--summary", "s",
                                  "--bundle", bundle, "--fix-version", "2026.r1",
                                  "--dry-run"])


if __name__ == "__main__":
    unittest.main()
