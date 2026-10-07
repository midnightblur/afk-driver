"""Focused tests for the Windows Wave host helper."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "lavish" / "wave_host.py"
SPEC = importlib.util.spec_from_file_location("wave_host", MODULE_PATH)
wave_host = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wave_host
SPEC.loader.exec_module(wave_host)

URL = "http://127.0.0.1:43127/session/abc123"


def result(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class RecordingRun:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, argv, timeout):
        self.calls.append((list(argv), timeout))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class SecretGuard(dict):
    def get(self, key, default=None):
        if "JWT" in key or "TOKEN" in key or "CREDENTIAL" in key:
            raise AssertionError("secret accessed")
        return super().get(key, default)


class Eligibility(unittest.TestCase):
    def base(self):
        return SecretGuard({
            "WAVETERM": "1",
            "WAVETERM_CONN": "",
            "WAVETERM_TABID": "tab-1",
            "WAVETERM_BLOCKID": "block-1",
            "WAVETERM_JWT": "never-read",
        })

    def test_all_local_scope_checks_are_required(self):
        for platform, patch in (
            ("linux", {}),
            ("win32", {"WAVETERM": "0"}),
            ("win32", {"WAVETERM_CONN": "remote"}),
            ("win32", {"WAVETERM_TABID": ""}),
            ("win32", {"WAVETERM_BLOCKID": ""}),
        ):
            env = self.base()
            env.update(patch)
            self.assertIsNone(wave_host._resolve_scope_candidate(
                env, platform, lambda _: "wsh.exe"))

    def test_path_wsh_resolves_a_scope_candidate_without_secret_access(self):
        scope = wave_host._resolve_scope_candidate(
            self.base(), "win32", lambda _: "C:\\bin\\wsh.exe")
        self.assertEqual(scope, wave_host.WaveScope("C:\\bin\\wsh.exe", "tab-1", "block-1"))

    def test_localappdata_fallback_is_generic(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "waveterm" / "Data" / "bin" / "wsh.exe"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"")
            env = self.base()
            env["LOCALAPPDATA"] = directory
            scope = wave_host._resolve_scope_candidate(env, "win32", lambda _: None)
            self.assertEqual(scope.wsh, str(binary))

    def test_eligibility_requires_usable_current_tab_json(self):
        run = RecordingRun([result(stdout="[]")])
        scope = wave_host.working_scope(
            self.base(), "win32", lambda _: "wsh.exe", run)
        self.assertIsNotNone(scope)
        self.assertEqual(
            run.calls[0][0],
            ["wsh.exe", "blocks", "list", "--view", "web", "--json", "--tab", "tab-1"],
        )
        self.assertEqual(run.calls[0][1], wave_host.LIST_TIMEOUT_SECONDS)

    def test_eligibility_accepts_wsh_no_blocks_message(self):
        run = RecordingRun([result(stdout="No blocks found\n")])
        scope = wave_host.working_scope(
            self.base(), "win32", lambda _: "wsh.exe", run)
        self.assertIsNotNone(scope)

    def test_eligibility_rejects_failed_or_unusable_wsh_output(self):
        for reply in (
            result(returncode=1),
            result(stdout="{}"),
            result(stdout="not-json"),
            subprocess.TimeoutExpired(["wsh.exe"], 8),
            FileNotFoundError("private path"),
        ):
            with self.subTest(reply=reply):
                run = RecordingRun([reply])
                self.assertIsNone(wave_host.working_scope(
                    self.base(), "win32", lambda _: "wsh.exe", run))


class UrlContract(unittest.TestCase):
    def test_accepts_only_exact_http_ipv4_loopback_with_explicit_port(self):
        self.assertEqual(wave_host.validate_lavish_url(URL), URL)
        rejected = (
            "https://127.0.0.1:43127/session/a",
            "http://localhost:43127/session/a",
            "http://127.0.0.1/session/a",
            "http://127.0.0.1:0/session/a",
            "http://127.0.0.1:70000/session/a",
            "http://user@127.0.0.1:43127/session/a",
            "http://127.0.0.1:43127/session/a#fragment",
            "http://127.0.0.1:43127/session/a\nnext",
            "http://127.0.0.1:43127/session/a next",
            "http://[::1]:43127/session/a",
        )
        for value in rejected:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    wave_host.validate_lavish_url(value)


class WaveOpen(unittest.TestCase):
    def setUp(self):
        self.scope = wave_host.WaveScope("wsh.exe", "tab-secret", "block-secret")

    def blocks(self, *items):
        return result(stdout=json.dumps(list(items)))

    def test_matching_web_block_is_reused_with_replace(self):
        before = {"blockid": "web-1", "meta": {"view": "web", "url": URL}}
        after = {"blockid": "web-2", "meta": {"view": "web", "url": URL}}
        run = RecordingRun([self.blocks(before), result(), self.blocks(after)])
        outcome = wave_host.open_in_wave(URL, self.scope, run)
        self.assertEqual(outcome.status, "reused")
        self.assertEqual(run.calls[1][0], ["wsh.exe", "web", "open", URL, "--replace", "web-1"])
        self.assertEqual(run.calls[0][0],
                         ["wsh.exe", "blocks", "list", "--view", "web", "--json", "--tab", "tab-secret"])

    def test_closed_block_opens_a_new_web_block(self):
        run = RecordingRun([self.blocks(), result(), self.blocks(
            {"blockid": "web-new", "meta": {"view": "web", "url": URL}})])
        outcome = wave_host.open_in_wave(URL, self.scope, run)
        self.assertEqual(outcome.status, "opened")
        self.assertEqual(run.calls[1][0], ["wsh.exe", "web", "open", URL])

    def test_no_blocks_message_allows_first_open(self):
        created = {"blockid": "web-first", "meta": {"view": "web", "url": URL}}
        run = RecordingRun([
            result(stdout="No blocks found\n"), result(), self.blocks(created)])
        outcome = wave_host.open_in_wave(URL, self.scope, run)
        self.assertEqual(outcome.status, "opened")
        self.assertEqual(run.calls[1][0], ["wsh.exe", "web", "open", URL])

    def test_no_blocks_message_reopens_after_closure(self):
        first = RecordingRun([
            result(stdout="No blocks found\n"), result(),
            self.blocks({"blockid": "web-first", "meta": {"view": "web", "url": URL}}),
        ])
        self.assertEqual(wave_host.open_in_wave(URL, self.scope, first).status, "opened")
        reopened = RecordingRun([
            result(stdout="No blocks found\n"), result(),
            self.blocks({"blockid": "web-second", "meta": {"view": "web", "url": URL}}),
        ])
        outcome = wave_host.open_in_wave(URL, self.scope, reopened)
        self.assertEqual(outcome.status, "opened")
        self.assertEqual(reopened.calls[1][0], ["wsh.exe", "web", "open", URL])

    def test_successful_open_with_failed_confirmation_prevents_second_view(self):
        run = RecordingRun([self.blocks(), result(), result(returncode=1, stderr="secret")])
        outcome = wave_host.open_in_wave(URL, self.scope, run)
        self.assertEqual(outcome.status, "opened-unconfirmed")
        self.assertEqual(outcome.exit_code, 2)
        self.assertNotIn(URL, outcome.message)
        self.assertNotIn("secret", outcome.message)

    def test_failed_replace_does_not_open_a_second_view(self):
        existing = {"blockid": "web-1", "meta": {"view": "web", "url": URL}}
        run = RecordingRun([self.blocks(existing), result(returncode=9)])
        outcome = wave_host.open_in_wave(URL, self.scope, run)
        self.assertEqual(outcome.status, "opened-unconfirmed")
        self.assertEqual(outcome.exit_code, 2)

    def test_unusable_json_fails_closed_before_open(self):
        for stdout in ("not json", "No blocks found", "{}", '[{"blockid":"x"}]'):
            with self.subTest(stdout=stdout):
                run = RecordingRun([result(stdout=stdout)])
                outcome = wave_host.open_in_wave(URL, self.scope, run)
                self.assertEqual(outcome.status, "definitely-not-opened")
                self.assertEqual(len(run.calls), 1)

    def test_initial_discovery_oserror_allows_browser_fallback(self):
        run = RecordingRun([PermissionError("private path")])
        outcome = wave_host.open_in_wave(URL, self.scope, run)
        self.assertEqual(outcome.status, "definitely-not-opened")
        self.assertEqual(outcome.exit_code, 1)
        self.assertNotIn("private", outcome.message)
        self.assertEqual(len(run.calls), 1)

    def test_open_failure_is_sanitized_and_prevents_browser_fallback(self):
        run = RecordingRun([self.blocks(), result(returncode=9, stderr="JWT=secret")])
        outcome = wave_host.open_in_wave(URL, self.scope, run)
        self.assertEqual(outcome.status, "opened-unconfirmed")
        self.assertEqual(outcome.exit_code, 2)
        self.assertNotIn(URL, outcome.message)
        self.assertNotIn("secret", outcome.message)

    def test_open_timeout_prevents_browser_fallback(self):
        run = RecordingRun([
            self.blocks(), subprocess.TimeoutExpired(["wsh.exe", "web", "open"], 12)])
        outcome = wave_host.open_in_wave(URL, self.scope, run)
        self.assertEqual(outcome.status, "opened-unconfirmed")
        self.assertEqual(outcome.exit_code, 2)
        self.assertEqual(len(run.calls), 2)

    def test_open_oserror_prevents_browser_fallback(self):
        run = RecordingRun([self.blocks(), FileNotFoundError("private path")])
        outcome = wave_host.open_in_wave(URL, self.scope, run)
        self.assertEqual(outcome.status, "opened-unconfirmed")
        self.assertEqual(outcome.exit_code, 2)
        self.assertNotIn("private", outcome.message)
        self.assertEqual(len(run.calls), 2)

    def test_post_open_discovery_oserror_prevents_browser_fallback(self):
        run = RecordingRun([self.blocks(), result(), PermissionError("private path")])
        outcome = wave_host.open_in_wave(URL, self.scope, run)
        self.assertEqual(outcome.status, "opened-unconfirmed")
        self.assertEqual(outcome.exit_code, 2)
        self.assertNotIn("private", outcome.message)
        self.assertEqual(len(run.calls), 3)

    def test_only_pre_open_failure_allows_browser_fallback(self):
        run = RecordingRun([result(returncode=9)])
        outcome = wave_host.open_in_wave(URL, self.scope, run)
        self.assertEqual(outcome.status, "definitely-not-opened")
        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(len(run.calls), 1)

    def test_subprocess_runner_uses_argv_without_a_shell(self):
        completed = result()
        with mock.patch.object(subprocess, "run", return_value=completed) as run:
            self.assertIs(wave_host._run(["wsh.exe", "web", "open", URL], 4), completed)
        kwargs = run.call_args.kwargs
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["capture_output"])
        self.assertEqual(kwargs["timeout"], 4)


class SetupContract(unittest.TestCase):
    def test_wave_opt_in_uses_exact_install_and_verification_commands(self):
        manifest = (ROOT / "skills" / "afk" / "setup" / "MANIFEST.md").read_text(encoding="utf-8")
        start = manifest.index("### C12 · Wave Terminal")
        end = manifest.index("\n### ", start + 5)
        row = manifest[start:end]
        self.assertIn("**[opt-in]**", row)
        self.assertIn("winget install --id CommandLine.Wave --exact --source winget", row)
        self.assertIn("winget list --id CommandLine.Wave --exact --source winget", row)
        for forbidden in ("wsh ", "restart", "launch Wave", "move session"):
            self.assertNotIn(forbidden, row)

    def test_warmup_never_calls_the_wave_helper(self):
        doctrine = (ROOT / "LAVISH.md").read_text(encoding="utf-8")
        warmup = doctrine[doctrine.index("**Warm-up.**"):doctrine.index("**Re-render cadence.")]
        self.assertIn("--no-open", warmup)
        self.assertIn("Warm-up never\nchecks Wave", warmup)
        self.assertNotIn("wave_host.py", warmup)


if __name__ == "__main__":
    unittest.main()
