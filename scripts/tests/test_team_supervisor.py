"""The job supervisor: its message ids, the parked body, the exited message and the one-supervisor rule.

The transport and the permission check are stand-ins; the watched processes and the run folder are real.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from team import entry, manifest, supervisor  # noqa: E402

RUN = "agent-team-topology"
UTC_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


class Team:
    """A run folder with a manifest, and a stand-in transport that answers agent-status with `exit_code`."""

    def __init__(self, tmp: Path):
        self.main, self.root = tmp / "main", tmp / "team"
        self.main.mkdir()
        self.exit_code: int | None = 1
        self.calls: list[tuple[str, dict]] = []
        self.host = entry.Host(root=self.root, main=self.main, cwd=self.main, env={}, dispatch=self.dispatch,
                               resolve_kind=lambda cwd, env=None: {"kind": "headless"},
                               check_permission=lambda root, env=None: {"ok": True, "says": "ok"},
                               config=lambda key: None)
        manifest.adopt_manifest(self.root, RUN, "contact-session")
        self.dir = self.root / RUN
        (self.dir / "inbox").mkdir()

    def dispatch(self, kind, verb, payload, root=None, env=None):
        self.calls.append((verb, payload))
        body = {"alive": False, "state": "exited", "since": None, "exit_code": self.exit_code}
        return 0, json.dumps(body) + "\n", ""

    def agent(self, agent_id: str, kind: str, pid: int | None, **fields) -> None:
        manifest.record_entry(self.root, RUN, {"agent_id": agent_id, "stage": "execute", "pattern_step": "build",
                                               "role": "builder", "model": "implementation@claude",
                                               "lifespan": "Step", "transport_kind": kind,
                                               **({"pid": pid, "handle": str(pid)} if pid else {}), **fields})
        manifest.move_entry(self.root, RUN, agent_id, "working")

    def log(self, agent_id: str, text: str) -> None:
        path = self.dir / "logs" / f"{agent_id}.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def supervise(self, agent_id: str = "a1", **extra) -> tuple[int, dict]:
        extra.setdefault("poll_s", 0.02)
        return supervisor.supervise_agent(self.host, RUN, agent_id, **extra)

    def inbox(self) -> list[str]:
        return sorted(p.name for p in (self.dir / "inbox").iterdir())

    def envelope(self, message_id: str) -> dict:
        return json.loads((self.dir / "inbox" / f"{message_id}.json").read_text(encoding="utf-8"))


@pytest.fixture
def team(tmp_path):
    return Team(tmp_path)


def ended() -> int:
    """The id of a process that has already ended."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


@pytest.fixture
def running():
    procs = []

    def start(seconds: float) -> subprocess.Popen:
        proc = subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({seconds})"])
        procs.append(proc)
        return proc

    yield start
    for proc in procs:
        proc.kill()
        proc.wait()


LIMIT = "Claude AI usage limit reached|1759140900"


# ---- the message and its id ------------------------------------------------------------------------------

def test_an_ended_agent_gets_exited_with_id_watched_agent_then_sup_then_counter(team):
    team.agent("a1", "multiplexer", ended())
    code, answer = team.supervise()
    assert code == 0 and answer["kind"] == "exited" and answer["message_id"] == "a1-sup-1"
    assert team.inbox() == ["a1-sup-1.json"]
    envelope = team.envelope("a1-sup-1")
    assert envelope["agent_id"] == "a1" and envelope["from_role"] == "builder" and envelope["kind"] == "exited"
    assert envelope["generation"] == manifest.read_manifest(team.root, RUN)["owner_generation"]
    assert envelope["body_path"] == ""


def test_it_sends_only_to_the_contact_inbox_and_never_through_a_pane(team):
    team.agent("a1", "multiplexer", ended())
    team.supervise()
    assert "agent-send" not in [verb for verb, _ in team.calls]
    assert team.inbox() == ["a1-sup-1.json"]


def test_the_counter_starts_above_every_id_an_earlier_supervisor_of_the_agent_used(team):
    team.agent("a1", "multiplexer", ended())
    for folder, name in (("processed", "a1-sup-4.json"), ("bodies", "a1-sup-2"), ("inbox", "a1-7.json"),
                         ("processed", "a10-sup-9.json")):
        (team.dir / folder).mkdir(exist_ok=True)
        (team.dir / folder / name).write_text("{}", encoding="utf-8")
    assert team.supervise()[1]["message_id"] == "a1-sup-5"


def test_the_supervisor_id_never_matches_an_id_the_agent_makes():
    assert not re.fullmatch(r"a1-[0-9]+", supervisor.message_id_for("a1", 3))
    assert supervisor.message_id_for("a1", 3) == "a1-sup-3"


# ---- parked, from the headless kind ----------------------------------------------------------------------

def test_a_headless_run_ended_by_a_provider_limit_gets_parked_with_a_utc_iso_reset_time(team):
    team.agent("a1", "headless", ended())
    team.log("a1", f"working on it\n{LIMIT}\n")
    code, answer = team.supervise()
    assert code == 0 and answer["kind"] == "parked" and answer["reset"] == "2025-09-29T10:15:00Z"
    envelope = team.envelope("a1-sup-1")
    assert envelope["kind"] == "parked" and envelope["body_path"]
    body = Path(envelope["body_path"]).read_text(encoding="utf-8")
    assert "2025-09-29T10:15:00Z" in body and UTC_ISO.search(body)
    assert "claude" in body and "a1" in body, "the body names the provider and the agent"


def test_a_limit_with_no_readable_reset_time_gets_parked_with_an_empty_body_path(team):
    team.agent("a1", "headless", ended())
    team.log("a1", "You've hit your usage limit. Upgrade your plan to continue.\n")
    code, answer = team.supervise()
    assert code == 0 and answer["kind"] == "parked" and answer["reset"] is None
    assert team.envelope("a1-sup-1")["body_path"] == ""


def test_a_headless_run_that_ended_with_exit_0_gets_exited_even_when_its_log_names_a_limit(team):
    team.exit_code = 0
    team.agent("a1", "headless", ended())
    team.log("a1", f"{LIMIT}\n")
    assert team.supervise()[1]["kind"] == "exited"
    assert team.envelope("a1-sup-1")["body_path"] == ""


def test_an_unknown_exit_code_still_reads_the_limit(team):
    team.exit_code = None
    team.agent("a1", "headless", ended())
    team.log("a1", f"{LIMIT}\n")
    assert team.supervise()[1]["kind"] == "parked"


def test_a_kind_whose_output_the_supervisor_does_not_own_gets_exited(team):
    team.agent("a1", "multiplexer", ended())
    team.log("a1", f"{LIMIT}\n")
    assert team.supervise()[1]["kind"] == "exited"
    assert "agent-status" not in [verb for verb, _ in team.calls]


def test_a_limit_line_above_the_last_20_lines_is_not_read(team):
    team.agent("a1", "headless", ended())
    team.log("a1", LIMIT + "\n" + "".join(f"line {n}\n" for n in range(25)))
    assert team.supervise()[1]["kind"] == "exited"


def test_a_headless_run_with_no_log_gets_exited(team):
    team.agent("a1", "headless", ended())
    assert team.supervise()[1]["kind"] == "exited"


# ---- reading the reset time ------------------------------------------------------------------------------

SEEN = datetime(2026, 9, 29, 8, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("line, expected", [
    ("Claude AI usage limit reached|1759140900", datetime(2025, 9, 29, 10, 15, tzinfo=timezone.utc)),
    ("usage limit reached; resets at 2026-09-29T12:15:00+02:00", datetime(2026, 9, 29, 10, 15, tzinfo=timezone.utc)),
    ("usage limit reached; resets at 2026-09-29T10:15:00Z", datetime(2026, 9, 29, 10, 15, tzinfo=timezone.utc)),
    ("You've hit your usage limit. Try again in 2 hours 15 minutes.", SEEN + timedelta(hours=2, minutes=15)),
    ("You've hit your usage limit, try again in 1 day 3h", SEEN + timedelta(days=1, hours=3)),
    ("5-hour limit reached - resets 10:15am (UTC)", datetime(2026, 9, 29, 10, 15, tzinfo=timezone.utc)),
    ("5-hour limit reached - resets 7am (UTC)", datetime(2026, 9, 30, 7, 0, tzinfo=timezone.utc)),
    ("usage limit reached, try again at Sep 30th, 2026 3:05 PM (UTC)",
     datetime(2026, 9, 30, 15, 5, tzinfo=timezone.utc)),
])
def test_the_reset_time_forms_the_supervisor_reads(line, expected):
    assert supervisor.reset_time(line, SEEN) == expected


def test_a_clock_time_with_no_zone_is_the_machine_local_time():
    found = supervisor.reset_time("limit reached - resets at 11:30 PM", SEEN)
    local = SEEN.astimezone().replace(tzinfo=None)
    want = local.replace(hour=23, minute=30, second=0)
    want = want if want > local else want + timedelta(days=1)
    assert found == want.astimezone(timezone.utc)


def test_a_date_with_no_time_is_the_start_of_that_day_in_local_time():
    found = supervisor.reset_time("You've hit your usage limit ... try again at Oct 2nd, 2026", SEEN)
    assert found == datetime(2026, 10, 2).astimezone(timezone.utc)


@pytest.mark.parametrize("line", [
    "You've hit your usage limit. Upgrade to continue.",
    "usage limit reached - resets 3pm (Nowhere/Atlantis)",
    "usage limit reached, see https://example.invalid/limits for 2 options",
])
def test_a_reset_time_the_supervisor_cannot_read_is_none(line):
    assert supervisor.reset_time(line, SEEN) is None


def test_the_limit_line_is_the_last_one_that_names_a_limit():
    text = "rate limit hit, retrying\nok\nusage limit reached|1759140900\nbye\n"
    assert supervisor.limit_line(text) == "usage limit reached|1759140900"
    assert supervisor.limit_line("all done\n") is None


# ---- watching --------------------------------------------------------------------------------------------

def test_it_sends_nothing_until_the_watched_process_ends(team, running):
    proc = running(1.5)
    team.agent("a1", "multiplexer", proc.pid)
    seen: list[list[str]] = []

    def sleep(seconds):
        seen.append(team.inbox())
        time.sleep(seconds)

    code, answer = team.supervise(sleep=sleep, poll_s=0.1)
    assert code == 0 and answer["kind"] == "exited" and proc.poll() is not None
    assert seen and all(names == [] for names in seen)


def test_it_reads_the_process_id_once_the_entry_holds_one(team):
    manifest.record_entry(team.root, RUN, {"agent_id": "a1", "stage": "execute", "pattern_step": "build",
                                           "role": "builder", "model": "implementation@claude", "lifespan": "Step"})
    pid = ended()
    polls = []

    def sleep(seconds):
        polls.append(seconds)
        if len(polls) == 2:
            manifest.record_entry(team.root, RUN, {"agent_id": "a1", "pid": pid, "transport_kind": "multiplexer"})

    code, answer = team.supervise(sleep=sleep)
    assert code == 0 and answer["kind"] == "exited" and len(polls) == 2


def test_a_run_whose_manifest_is_gone_ends_the_supervisor_with_nothing_sent(team):
    team.agent("a1", "multiplexer", None)

    def sleep(seconds):
        (team.dir / "manifest.json").unlink()

    code, answer = team.supervise(sleep=sleep)
    assert code == 0 and answer["sent"] is False and team.inbox() == []


# ---- one supervisor per agent ----------------------------------------------------------------------------

def claim(team: Team, agent_id: str, slot: int, pid: int, started_at) -> Path:
    path = team.dir / "supervisors" / agent_id / f"{slot}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pid": pid, "started_at": started_at}), encoding="utf-8")
    return path


def test_a_second_supervisor_for_one_agent_is_refused_with_exit_2_naming_the_agent(team):
    team.agent("a1", "multiplexer", ended())
    claim(team, "a1", 1, os.getpid(), entry.process.creation_time(os.getpid()))
    code, answer = team.supervise()
    assert code == 2 and answer["error"] and "a1" in answer["reason"] and str(os.getpid()) in answer["reason"]
    assert team.inbox() == [] and sorted(p.name for p in (team.dir / "supervisors" / "a1").iterdir()) == ["1.json"]


def test_a_claim_slot_another_supervisor_took_first_refuses_with_exit_2(team, monkeypatch):
    team.agent("a1", "multiplexer", ended())
    real = os.link

    def raced(source, target):
        claim(team, "a1", 1, os.getpid(), entry.process.creation_time(os.getpid()))
        return real(source, target)

    monkeypatch.setattr(supervisor.os, "link", raced)
    code, answer = team.supervise()
    assert code == 2 and "a1" in answer["reason"] and team.inbox() == []


def test_the_claim_of_a_supervisor_that_is_gone_does_not_block_the_next(team):
    team.agent("a1", "multiplexer", ended())
    claim(team, "a1", 1, ended(), "2026-01-01T00:00:00Z")
    assert team.supervise()[0] == 0 and team.inbox() == ["a1-sup-1.json"]
    held = json.loads((team.dir / "supervisors" / "a1" / "2.json").read_text(encoding="utf-8"))
    assert held["pid"] == os.getpid()


def test_another_agent_s_claim_does_not_block_this_one(team):
    team.agent("a1", "multiplexer", ended())
    claim(team, "a2", 1, os.getpid(), entry.process.creation_time(os.getpid()))
    assert team.supervise()[0] == 0


def test_an_agent_id_with_no_entry_is_refused_with_exit_2_naming_it(team):
    code, answer = team.supervise("ghost")
    assert code == 2 and "ghost" in answer["reason"]
    assert not (team.dir / "supervisors" / "ghost").exists()


def test_a_send_that_keeps_failing_answers_exit_4_after_its_retries(team):
    team.agent("a1", "multiplexer", ended())
    (team.dir / "inbox").rmdir()
    (team.dir / "inbox").write_text("not a folder", encoding="utf-8")
    naps = []
    code, answer = team.supervise(sleep=naps.append)
    assert code == 4 and answer["unavailable"] and len(naps) == supervisor.SEND_TRIES - 1


# ---- started by agent-start ------------------------------------------------------------------------------

def test_main_refuses_an_argument_that_is_not_the_start_object(capsys):
    assert supervisor.main(["not json"]) == 2
    assert supervisor.main([json.dumps({"run": RUN})]) == 2
    assert supervisor.main([json.dumps({"run": RUN, "watched_agent_id": "a1", "role": "x"})]) == 2
    assert "`role`" in capsys.readouterr().out


def test_agent_start_starts_this_supervisor_which_sends_exited_for_its_agent(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    root = tmp_path / "team"
    env = {**os.environ, "AFK_TEAM_ROOT": str(root)}
    host = entry.Host.discover(cwd=repo, env=env)
    manifest.adopt_manifest(root, RUN, "contact-session")
    manifest.record_entry(root, RUN, {"agent_id": "a1", "stage": "execute", "pattern_step": "build",
                                      "role": "builder", "model": "implementation@claude", "lifespan": "Step",
                                      "transport_kind": "multiplexer", "pid": ended()})
    code, answer = entry.run_command("agent-start", {"run": RUN, "watched_agent_id": "a1"}, host)
    assert code == 0 and answer["label"] == "a1 supervisor"
    landed = root / RUN / "inbox" / "a1-sup-1.json"
    end = time.monotonic() + 60
    while not landed.is_file() and time.monotonic() < end:
        time.sleep(0.2)
    assert landed.is_file(), "the supervisor agent-start started sent no exited message"
    assert json.loads(landed.read_text(encoding="utf-8"))["kind"] == "exited"


def test_an_entry_with_a_handle_and_no_process_id_is_watched_through_agent_status(team):
    team.agent("a1", "desktop", None, handle="t-7")
    code, answer = team.supervise()
    assert code == 0 and answer["kind"] == "exited"
    assert [verb for verb, _ in team.calls] == ["agent-status"]


def test_an_entry_that_left_the_live_states_with_no_process_ends_the_supervisor_quietly(team):
    manifest.record_entry(team.root, RUN, {"agent_id": "a1", "stage": "execute", "pattern_step": "build",
                                           "role": "builder", "model": "implementation@claude", "lifespan": "Step"})
    manifest.move_entry(team.root, RUN, "a1", "lost")
    code, answer = team.supervise(sleep=lambda s: pytest.fail("no poll for an agent that never ran"))
    assert code == 0 and answer["sent"] is False and team.inbox() == []
