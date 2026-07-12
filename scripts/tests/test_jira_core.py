#!/usr/bin/env python3
"""Payload-shape unit tests for jira_core — no network.

Covers the shared Jira machinery extracted from to-ticket's publish_prd.py:
ADF conversion, multipart attachment-body construction, media-UUID extraction,
and creds resolution. Every test that would otherwise touch the network stubs
Jira._req; nothing here opens a socket.
"""

import os
import sys
import tempfile
import unittest

# jira_core lives one directory up (the scripts/ dir); make it importable no
# matter what cwd `python -m unittest discover` runs from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jira_core  # noqa: E402


class FakeResp:
    """Minimal stand-in for an http.client.HTTPResponse."""

    def __init__(self, body=b"", location=None):
        self._body = body
        self.headers = {"Location": location} if location is not None else {}

    def read(self):
        return self._body


# ---------------------------------------------------------------------------
# ADF conversion
# ---------------------------------------------------------------------------
class TestMdToAdf(unittest.TestCase):
    def adf(self, md, fig_nodes=None):
        return jira_core.md_to_adf_content(md, fig_nodes or {})

    def test_heading(self):
        nodes = self.adf("# Title")
        self.assertEqual(nodes, [{
            "type": "heading", "attrs": {"level": 1},
            "content": [{"type": "text", "text": "Title"}],
        }])

    def test_heading_level(self):
        nodes = self.adf("### Deep")
        self.assertEqual(nodes[0]["attrs"]["level"], 3)

    def test_paragraph_with_marks(self):
        nodes = self.adf("plain **bold** and *em* and `code`")
        self.assertEqual(nodes[0]["type"], "paragraph")
        texts = {tuple(sorted(m["type"] for m in n.get("marks", []))): n["text"]
                 for n in nodes[0]["content"]}
        self.assertIn("bold", texts[("strong",)])
        self.assertIn("em", texts[("em",)])
        self.assertIn("code", texts[("code",)])

    def test_code_mark_is_exclusive(self):
        # `code` mark may only co-exist with `link`; strong/em are dropped.
        nodes = self.adf("**`bolded code`**")
        code_node = nodes[0]["content"][0]
        self.assertEqual([m["type"] for m in code_node["marks"]], ["code"])

    def test_absolute_link_kept_relative_dropped(self):
        nodes = self.adf("[abs](https://x.test/y) and [rel](../foo.md)")
        marks_by_text = {n["text"]: [m["type"] for m in n.get("marks", [])]
                         for n in nodes[0]["content"]}
        self.assertIn("link", marks_by_text["abs"])
        self.assertNotIn("link", marks_by_text.get("rel", []))

    def test_bullet_list(self):
        nodes = self.adf("- one\n- two")
        self.assertEqual(nodes[0]["type"], "bulletList")
        self.assertEqual(len(nodes[0]["content"]), 2)
        self.assertEqual(nodes[0]["content"][0]["type"], "listItem")

    def test_ordered_list_start_attr(self):
        nodes = self.adf("3. three\n4. four")
        self.assertEqual(nodes[0]["type"], "orderedList")
        self.assertEqual(nodes[0]["attrs"], {"order": 3})

    def test_code_fence_language(self):
        nodes = self.adf("```python\nx = 1\n```")
        self.assertEqual(nodes[0]["type"], "codeBlock")
        self.assertEqual(nodes[0]["attrs"], {"language": "python"})
        self.assertEqual(nodes[0]["content"][0]["text"], "x = 1")

    def test_table(self):
        nodes = self.adf("| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertEqual(nodes[0]["type"], "table")
        rows = nodes[0]["content"]
        self.assertEqual(rows[0]["content"][0]["type"], "tableHeader")
        self.assertEqual(rows[1]["content"][0]["type"], "tableCell")

    def test_mermaid_placeholder_substitution(self):
        # A lone-paragraph placeholder token is replaced by the supplied fig node.
        token = jira_core.FIG_TOKEN.format(0)
        fig = [{"type": "mediaSingle", "attrs": {"layout": "center"},
                "content": [{"type": "media", "attrs": {"type": "file", "id": "u"}}]}]
        nodes = self.adf(f"before\n\n{token}\n\nafter", fig_nodes={0: fig})
        self.assertIn(fig[0], nodes)
        # the placeholder text must not survive as a paragraph
        joined = str(nodes)
        self.assertNotIn("AFKMERMAIDFIGURE", joined)


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------
class TestCreds(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k)
                       for k in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_env_wins_and_base_trailing_slash_stripped(self):
        os.environ["JIRA_BASE_URL"] = "https://n.atlassian.net/"
        os.environ["JIRA_EMAIL"] = "me@x.test"
        os.environ["JIRA_API_TOKEN"] = "tok123"
        base, email, token = jira_core.load_creds()
        self.assertEqual(base, "https://n.atlassian.net")
        self.assertEqual(email, "me@x.test")
        self.assertEqual(token, "tok123")

    def test_walk_for_jira_env_nested(self):
        cfg = {"mcpServers": {"jira": {"env": {"JIRA_BASE_URL": "https://n.test"}}}}
        env = jira_core._walk_for_jira_env(cfg)
        self.assertEqual(env, {"JIRA_BASE_URL": "https://n.test"})

    def test_walk_for_jira_env_absent(self):
        self.assertIsNone(jira_core._walk_for_jira_env({"other": {"x": 1}}))


# ---------------------------------------------------------------------------
# REST client — attachment upload + media-UUID (no network; _req stubbed)
# ---------------------------------------------------------------------------
class TestJiraClient(unittest.TestCase):
    def make(self):
        return jira_core.Jira("https://n.atlassian.net", "me@x.test", "tok")

    def test_auth_header_is_basic_base64(self):
        import base64
        j = self.make()
        expected = "Basic " + base64.b64encode(b"me@x.test:tok").decode()
        self.assertEqual(j.auth, expected)

    def test_upload_attachment_multipart_body(self):
        j = self.make()
        captured = {}

        def fake_req(method, path, data=None, headers=None, follow=True):
            captured.update(method=method, path=path, data=data, headers=headers)
            return FakeResp(body=b'[{"id":"9001"}]')

        j._req = fake_req
        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\nDATA")
            png = f.name
        try:
            att_id = j.upload_attachment("P2P-1", png)
        finally:
            os.unlink(png)

        self.assertEqual(att_id, "9001")
        self.assertEqual(captured["method"], "POST")
        self.assertTrue(captured["path"].endswith("/issue/P2P-1/attachments"))
        self.assertEqual(captured["headers"]["X-Atlassian-Token"], "no-check")
        self.assertIn("multipart/form-data; boundary=",
                      captured["headers"]["Content-Type"])
        body = captured["data"]
        self.assertIn(b'Content-Disposition: form-data; name="file"; filename="',
                      body)
        self.assertIn(b"Content-Type: image/png", body)
        self.assertIn(b"DATA", body)  # file payload embedded verbatim

    def test_resolve_media_uuid_from_location(self):
        j = self.make()
        uuid = "0123abcd-4567-89ab-cdef-0123456789ab"
        loc = f"https://api.media.atlassian.com/file/{uuid}/binary?token=x"

        def fake_req(method, path, data=None, headers=None, follow=True):
            self.assertFalse(follow)  # must NOT follow the 303
            return FakeResp(location=loc)

        j._req = fake_req
        self.assertEqual(j.resolve_media_uuid("9001"), uuid)


# ---------------------------------------------------------------------------
# PNG dimensions
# ---------------------------------------------------------------------------
class TestPngSize(unittest.TestCase):
    def test_reads_ihdr_dimensions(self):
        # PNG signature + IHDR length/type + 32x16 width/height.
        import struct
        head = (b"\x89PNG\r\n\x1a\n"
                + struct.pack(">I", 13) + b"IHDR"
                + struct.pack(">II", 32, 16))
        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as f:
            f.write(head + b"\x00" * 16)
            png = f.name
        try:
            self.assertEqual(jira_core.png_size(png), (32, 16))
        finally:
            os.unlink(png)

    def test_non_png_returns_none(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".bin", delete=False) as f:
            f.write(b"not a png at all here")
            p = f.name
        try:
            self.assertIsNone(jira_core.png_size(p))
        finally:
            os.unlink(p)


if __name__ == "__main__":
    unittest.main()
