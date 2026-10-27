from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hooks" / "lib"))

import provider_facts  # noqa: E402


@pytest.mark.parametrize("environ,provider,supported", [
    ({"CODEX_THREAD_ID": "thread"}, "codex", False),
    ({"PLUGIN_ROOT": "/plugin"}, "codex", False),
    ({"CLAUDE_PLUGIN_ROOT": "/plugin"}, "claude", True),
    ({"CLAUDECODE": "1"}, "claude", True),
    ({"CODEX_THREAD_ID": "thread", "CLAUDECODE": "1"}, "codex", False),
    ({"AFK_PROVIDER": "claude", "CODEX_THREAD_ID": "thread"}, "claude", True),
])
def test_detected_provider_declares_poll_capability(environ, provider, supported):
    declared = provider_facts.facts(environ)
    assert declared["name"] == provider
    assert declared["lavish_poll"] is supported


@pytest.mark.parametrize("environ", [{}, {"AFK_PROVIDER": "unknown"}, {"CODEX_THREAD_ID": ""}])
def test_unknown_provider_has_no_poll_capability(environ):
    assert provider_facts.facts(environ) == {}
