"""Setup against the real code that reads what setup writes and writes what setup reads."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

import setup
import tools

PLUGIN = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def publish():
    return load(PLUGIN / "skills" / "to-prd" / "scripts" / "publish.py", "seam_publish")


def test_to_prd_finds_the_renderer_config_that_setup_writes(publish, places, env, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", env["LOCALAPPDATA"])
    assert publish._renderer_config() is None
    places.puppeteer_config.parent.mkdir(parents=True)
    places.puppeteer_config.write_text("{}", encoding="utf-8")
    assert publish._renderer_config() == places.puppeteer_config


def test_setup_reads_the_ticket_lines_that_to_prd_writes(publish, places):
    now = datetime(2026, 11, 2, 12, 0, 5, tzinfo=timezone.utc)
    places.published_tickets.parent.mkdir(parents=True)
    places.published_tickets.write_text(publish.published_line(now, "PROJ-1", "abcdef0123") + "\n", encoding="utf-8")
    assert setup.published_tickets(places) == ["PROJ-1"]


def test_setup_installs_the_lavish_version_the_engine_pins():
    assert f'PIN = "{tools.LAVISH_PIN}"' in (PLUGIN / "engine" / "launcher.py").read_text(encoding="utf-8")
