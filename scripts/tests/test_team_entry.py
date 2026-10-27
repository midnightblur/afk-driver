"""The team entry script: its checks, names, manifest writes, stops, deliveries and charter files.

The transport, the kind probe and the permission check are stand-ins; processes for the identity check are real.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from team import entry, manifest, naming  # noqa: E402
import worktree_owner  # noqa: E402

spec = importlib.util.spec_from_file_location("afk_team_cli", PLUGIN_ROOT / "scripts" / "afk-team.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

RUN = "agent-team-topology"
TIERS = """# Fixture

## Model tiers

| Tier | Claude Code | Codex CLI | Codex effort |
|---|---|---|---|
| Frontier | `claude-opus-9` | `gpt-9-sun` | `high` |
| Implementation | `opus` | `gpt-6-sol` | `medium` |
| Digest | `sonnet` | `gpt-5.6-terra` | `low` |

| Agent | Tier |
|---|---|
| `afk-implementor` | Implementation |
| `afk-reader` | Digest |

## Next
"""


class Transport:
    """A stand-in transport kind: records each call and answers from `answers`."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self.echo = True
        self.answers = {
            "agent-start": (0, {"kind": "multiplexer", "tool": "herdr", "handle": "p9", "pid": None,
                                "started_at": "2026-10-22T10:00:00Z", "session_id": "s-1", "tab_id": "t1"}),
            "agent-send": (0, {"delivered": True, "at": "2026-10-22T10:00:01Z", "way": "agent prompt"}),
            "agent-stop": (0, {"stopped": True, "method": "killed the process tree", "pane_closed": True,
                               "pane_id": "p9"}),
            "agent-list": (0, {"agents": []}),
            "agent-status": (0, {"alive": True, "state": "working", "since": ""}),
        }

    def __call__(self, kind, verb, payload, root=None, env=None):
        self.calls.append((kind, verb, payload))
        code, body = self.answers[verb]
        if callable(body):
            body = body(payload)
        if verb == "agent-start" and code == 0 and self.echo:
            body = {**body, "pane_label": payload["label"], "agent_name": payload["name"]}
        if verb == "agent-stop" and "pane_id" in body and payload.get("handle"):
            body = {**body, "pane_id": payload["handle"]}   # a pane kind names the pane it was given
        return code, json.dumps(body) + "\n", ""

    def verbs(self) -> list[str]:
        return [verb for _, verb, _ in self.calls]


class Team:
    def __init__(self, tmp: Path):
        self.main, self.worktree, self.root = tmp / "main", tmp / "wt", tmp / "team"
        for folder in (self.main, self.worktree):
            folder.mkdir()
        (tmp / "PROVIDERS.md").write_text(TIERS, encoding="utf-8")
        self.brief = tmp / "brief.md"
        self.brief.write_text("do the work", encoding="utf-8")
        self.transport = Transport()
        self.settings: dict = {}
        self.permission_calls = 0
        self.host = entry.Host(root=self.root, main=self.main, cwd=self.worktree, env={},
                               dispatch=self.transport, resolve_kind=self.kind, check_permission=self.permission,
                               config=self.settings.get, providers=tmp / "PROVIDERS.md")
        self.kind_answer = {"kind": "multiplexer", "harnesses": ["claude", "codex"], "says": "herdr runs"}
        manifest.adopt_manifest(self.root, RUN, "contact-session")
        (self.root / RUN / "inbox").mkdir()

    def kind(self, cwd, env=None):
        return self.kind_answer

    def permission(self, root, env=None):
        self.permission_calls += 1
        return {"ok": True, "provider": "claude", "rule": "r", "problem": None, "says": "ok", "files": []}

    def call(self, verb: str, **data) -> tuple[int, dict]:
        return cli.dispatch_verb(verb, json.dumps({"run": RUN, **data}), self.host)

    def agent(self, agent_id: str, role: str, state: str = "working", **fields) -> dict:
        manifest.record_entry(self.root, RUN, {"agent_id": agent_id, "stage": "execute", "pattern_step": "build",
                                               "role": role, "model": "implementation@claude", "lifespan": "Step",
                                               **fields})
        path = {"starting": [], "working": ["working"], "parked": ["working", "parked"],
                "finished": ["working", "finished"], "lost": ["lost"], "cleaned": ["lost", "cleaned"]}[state]
        for to in path:
            manifest.move_entry(self.root, RUN, agent_id, to)
        return self.entry(agent_id)

    def pane(self, agent_id: str, role: str, **fields) -> dict:
        return self.agent(agent_id, role, handle=f"pane-{agent_id}", transport_kind="multiplexer", **fields)

    def entry(self, agent_id: str) -> dict:
        data = manifest.read_manifest(self.root, RUN)
        return next(a for a in data["agents"] if a["agent_id"] == agent_id)

    def pattern(self, roles: dict, edges: list | None = None, steps: list | None = None) -> None:
        implied = [e for r, f in roles.items() for e in (
            {"from": r, "to": f["report-target"], "kinds": ["message"], "implied": True},
            {"from": f["report-target"], "to": r, "kinds": ["message"], "implied": True})]
        team = {"roles": roles, "edges": (edges or []) + implied,
                "steps": steps or [{"name": "build", "roles": list(roles), "debate": False, "moderator": None}]}
        (self.root / RUN / "pattern.json").write_text(json.dumps({"format_version": 1, "team": team}), "utf-8")

    def body(self, name: str, content) -> str:
        path = self.root.parent / name
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return str(path)

    def inbox(self) -> list[str]:
        return sorted(p.name for p in (self.root / RUN / "inbox").iterdir())


def role(target: str = "") -> dict:
    return {"model": "implementation@claude", "lifespan": "Step", "count": 1, "report-target": target, "hub": False}


@pytest.fixture
def team(tmp_path):
    return Team(tmp_path)


def sleeper() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])


@pytest.fixture
def child():
    proc = sleeper()
    yield proc
    proc.kill()
    proc.wait()


def start(team: Team, agent_id: str = "a1", role_name: str = "builder", **extra) -> tuple[int, dict]:
    return team.call("agent-start", agent_id=agent_id, role=role_name, model=extra.pop("model", "implementation@claude"),
                     brief_path=str(team.brief), cwd=str(team.worktree), **extra)


# ---- payload shape ---------------------------------------------------------------------------------------

def test_a_payload_that_is_not_one_json_object_answers_exit_2(team):
    assert cli.dispatch_verb("agent-send", "not json", team.host)[0] == 2
    code, body = cli.dispatch_verb("agent-send", "[1]", team.host)
    assert code == 2 and body["error"] and body["operation"] == "agent-send" and "reason" in body


def test_an_unknown_field_answers_exit_2_naming_it(team):
    team.agent("a1", "builder")
    code, body = team.call("agent-status", agent_id="a1", colour="red")
    assert code == 2 and "colour" in body["reason"] and body["operation"] == "agent-status"


def test_an_unknown_command_is_unsupported(team):
    assert team.call("agent-dance")[0] == 3


# ---- names -----------------------------------------------------------------------------------------------

def test_the_name_has_four_parts_and_the_label_the_same_parts_spaced():
    assert naming.build_agent_name("PROJ-1220-export", "reviewer", "opus", "hi") == (
        "PROJ-1220 reviewer opus hi", "proj-1220-reviewer-opus-hi")
    assert naming.goal_of("agent-team-topology") == "agent-team-topol"


def test_the_model_part_drops_the_vendor_prefix_then_is_made_legal_then_cut_to_8():
    assert naming.model_part("gpt-6-sol") == "g-6-sol"
    assert naming.model_part("claude-opus-4-8") == "opus-4-8"
    assert naming.model_part("gpt-5.6-terra") == "g-5-6-te"
    label, name = naming.build_agent_name("PROJ-1", "builder", "gpt-6-sol", "med")
    assert label == "PROJ-1 builder g-6-sol med" and name == "proj-1-builder-g-6-sol-med"


def test_every_part_is_made_legal_by_one_rule():
    assert naming.legal("Re_view er") == "re_view-er"
    assert naming.legal("_x") == "g-_x" and naming.legal("9a") == "g-9a"


def test_the_goal_is_cut_first_to_fit_32_characters_with_the_suffix():
    first = naming.build_agent_name("agent-team-topology", "reviewer-b", "gpt-6-sol", "max")[1]
    assert first == "agent-tea-reviewer-b-g-6-sol-max"
    label, name = naming.build_agent_name("agent-team-topology", "reviewer-b", "gpt-6-sol", "max", {first})
    assert name == "agent-t-reviewer-b-g-6-sol-max-2" and label.endswith(" #2")


def test_matching_names_end_in_2_and_3():
    taken = {"proj-1-builder-opus-med", "proj-1-builder-opus-med-2"}
    label, name = naming.build_agent_name("PROJ-1", "builder", "opus", "med", taken)
    assert name == "proj-1-builder-opus-med-3" and label == "PROJ-1 builder opus med #3"


def test_a_name_with_no_room_for_1_goal_character_is_refused_naming_it():
    with pytest.raises(naming.NameRefused, match="agent name"):
        naming.build_agent_name("PROJ-1", "r" * 20, "opus-4-8", "med")
    with pytest.raises(naming.NameRefused, match="room for the goal part"):
        naming.build_agent_name("PROJ-1", "r" * 18, "opus-4-8", "med")    # room 0
    naming.build_agent_name("PROJ-1", "r" * 17, "opus-4-8", "med")    # room for exactly 1


def test_a_refusal_with_negative_room_names_a_name_the_rule_builds():
    with pytest.raises(naming.NameRefused) as refused:
        naming.build_agent_name("0010-live-feature", "r" * 25, "haiku", "lo")
    assert "'-" + "r" * 25 + "-haiku-lo'" in str(refused.value)


def test_a_goal_that_needs_g_needs_room_for_g_and_1_character():
    with pytest.raises(naming.NameRefused):
        naming.build_agent_name("1-ticket", "r" * 16, "opus-4-8", "med")
    assert naming.build_agent_name("1-ticket", "r" * 14, "opus-4-8", "med")[1].startswith("g-1-")


def test_agent_start_refuses_a_name_with_no_room_with_exit_2(team):
    team.agent("a1", "r" * 25, state="starting")
    code, body = start(team, role_name="r" * 25)
    assert code == 2 and "agent name" in body["reason"] and team.transport.calls == []


# ---- agent-start -----------------------------------------------------------------------------------------

def test_agent_start_refuses_an_agent_id_with_no_entry_or_not_starting(team):
    code, body = start(team, agent_id="ghost")
    assert code == 2 and "ghost" in body["reason"]
    team.agent("a2", "builder", state="working")
    code, body = start(team, agent_id="a2")
    assert code == 2 and "a2" in body["reason"] and "working" in body["reason"]
    assert team.transport.calls == []


def test_an_unknown_effort_is_refused_naming_the_field(team):
    team.agent("a1", "builder", state="starting")
    code, body = start(team, effort="turbo")
    assert code == 2 and "`effort`" in body["reason"] and team.transport.calls == []


def test_agent_start_writes_label_and_name_before_and_pid_and_session_after(team, child):
    team.agent("a1", "builder", state="starting")
    team.transport.answers["agent-start"][1]["pid"] = child.pid
    code, body = start(team)
    assert code == 0, body
    entry_ = team.entry("a1")
    assert entry_["pane_label"] == "agent-team-topol builder opus med" == body["pane_label"]
    assert entry_["agent_name"] == "agent-team-topo-builder-opus-med" == body["agent_name"]
    assert entry_["pid"] == child.pid and entry_["session_id"] == "s-1" and body["agent_id"] == "a1"
    kind, verb, payload = team.transport.calls[0]
    assert (kind, verb) == ("multiplexer", "agent-start")
    assert payload["tab"] == "agent-team-topol build" and payload["label"] == entry_["pane_label"]


def test_exit_4_and_no_transport_call_when_the_write_before_fails(team, monkeypatch):
    team.agent("a1", "builder", state="starting")
    real = manifest.record_entry

    def refuse(root, feature, entry_):
        if "pane_label" in entry_:
            raise manifest.ManifestBusy("busy")
        return real(root, feature, entry_)

    monkeypatch.setattr(manifest, "record_entry", refuse)
    code, body = start(team)
    assert code == 4 and body["unavailable"] and "write" in body["reason"] and body["write"]
    assert "agent-start" not in team.transport.verbs()


def test_exit_5_with_its_fields_when_the_write_after_fails(team, monkeypatch, child):
    team.agent("a1", "builder", state="starting")
    team.transport.answers["agent-start"][1].update(pid=child.pid, started_at=entry.process.creation_time(child.pid))
    real = manifest.record_entry

    def refuse(root, feature, entry_):
        if "pid" in entry_ or "session_id" in entry_:
            raise manifest.ManifestBusy("busy")
        return real(root, feature, entry_)

    monkeypatch.setattr(manifest, "record_entry", refuse)
    code, body = start(team)
    assert code == 5 and body["error"] and body["agent_id"] == "a1" and "a1" in body["reason"]
    assert body["stopped"] is True and body["pane_closed"] is True and body["pane_id"] == "p9"
    assert body["handle"] == "p9"
    assert body["pid"] == child.pid and body["kind"] == "multiplexer" and body["started_at"]
    stop = [p for _, v, p in team.transport.calls if v == "agent-stop"]
    assert stop and stop[0]["pid"] == child.pid and stop[0]["handle"] == "p9"
    assert team.entry("a1")["state"] == "starting", "exit 5 moves nothing; the contact agent moves it to lost"


def test_exit_5_omits_pane_fields_for_a_kind_with_no_panes(team, monkeypatch, child):
    team.agent("a1", "builder", state="starting")
    team.kind_answer = {"kind": "headless", "harnesses": ["claude"]}
    team.transport.answers["agent-start"] = (0, {"kind": "headless", "handle": str(child.pid), "pid": child.pid,
                                                 "started_at": entry.process.creation_time(child.pid),
                                                 "session_id": ""})
    team.transport.answers["agent-stop"] = (0, {"stopped": True, "method": "killed the process tree"})
    real = manifest.record_entry
    monkeypatch.setattr(manifest, "record_entry",
                        lambda r, f, e: (_ for _ in ()).throw(manifest.ManifestBusy("x")) if "pid" in e else real(r, f, e))
    code, body = start(team)
    assert code == 5 and "pane_closed" not in body and "pane_id" not in body and body["kind"] == "headless"
    assert body["handle"] == str(child.pid)


def refuse_the_write_after(monkeypatch):
    real = manifest.record_entry
    monkeypatch.setattr(manifest, "record_entry",
                        lambda r, f, e: (_ for _ in ()).throw(manifest.ManifestBusy("x")) if "pid" in e else real(r, f, e))


def test_the_exit_5_stop_ends_5_s_before_the_120_s_budget(team, monkeypatch, child):
    team.agent("a1", "builder", state="starting")
    team.transport.answers["agent-start"][1].update(pid=child.pid, started_at=entry.process.creation_time(child.pid))
    team.transport.answers["agent-stop"] = (0, lambda payload: (time.sleep(2), {"stopped": True, "method": "k"})[1])
    ticks = iter([0.0])
    team.host.clock = lambda: next(ticks, 114.5)    # 114.5 s spent: 0.5 s left before the 5 s reserve
    refuse_the_write_after(monkeypatch)
    began = time.monotonic()
    code, body = start(team)
    assert code == 5 and body["stopped"] is False and "120 s" in body["stop_reason"]
    assert body["handle"] == "p9" and body["pane_id"] == "p9", "a pane kind names its pane whatever the stop did"
    assert time.monotonic() - began < 2


def test_the_start_answer_names_the_label_and_name_even_when_the_kind_does_not(team, child, monkeypatch):
    team.agent("a1", "builder", state="starting")
    team.kind_answer = {"kind": "headless", "harnesses": ["claude"]}
    team.transport.answers["agent-start"] = (0, {"kind": "headless", "handle": str(child.pid), "pid": child.pid,
                                                 "started_at": entry.process.creation_time(child.pid)})
    team.transport.echo = False
    code, body = start(team)
    assert code == 0 and body["pane_label"] == "agent-team-topol builder opus med"
    assert body["agent_name"] == "agent-team-topo-builder-opus-med"


def test_a_relative_brief_and_cwd_reach_the_agent_as_absolute_paths(team, monkeypatch):
    team.agent("a1", "builder", state="starting")
    monkeypatch.chdir(team.brief.parent)
    team.host.cwd = team.brief.parent
    code, body = team.call("agent-start", agent_id="a1", role="builder", model="implementation@claude",
                           brief_path=team.brief.name, cwd=team.worktree.name)
    assert code == 0, body
    payload = team.transport.calls[-1][2]
    assert f"Read your brief, {team.brief}" in payload["prompt"] and payload["cwd"] == str(team.worktree)


def test_the_launch_environment_carries_the_run_root_the_contact_uses(team):
    team.agent("a1", "builder", state="starting")
    team.host.env["AFK_TEAM_ROOT"] = str(team.root)
    assert start(team)[0] == 0
    assert team.transport.calls[-1][2]["env"]["AFK_TEAM_ROOT"] == str(team.root)
    team.agent("a2", "builder", state="starting")
    del team.host.env["AFK_TEAM_ROOT"]
    assert start(team, agent_id="a2")[0] == 0
    assert "AFK_TEAM_ROOT" not in team.transport.calls[-1][2]["env"]


@pytest.mark.parametrize("mine, other", [("a2", "a1"), ("a1", "a2")])
def test_two_starts_that_pick_the_same_name_end_with_different_names(team, monkeypatch, mine, other):
    team.agent("a1", "builder", state="starting")
    team.agent("a2", "builder", state="starting")
    real = manifest.record_entry

    def racing(root, feature, entry_):
        if entry_.get("agent_id") == mine and "agent_name" in entry_ and not team.entry(other)["agent_name"]:
            real(root, feature, {"agent_id": other, "pane_label": entry_["pane_label"],
                                 "agent_name": entry_["agent_name"]})     # the other start wrote the name first
        return real(root, feature, entry_)

    monkeypatch.setattr(manifest, "record_entry", racing)
    code, body = start(team, agent_id=mine)
    assert code == 0, body
    assert team.entry(mine)["agent_name"] == "agent-team-to-builder-opus-med-2" == body["agent_name"]
    assert team.entry(other)["agent_name"] == "agent-team-topo-builder-opus-med"


def test_a_name_lost_5_times_answers_exit_4_and_starts_nothing(team, monkeypatch):
    team.agent("a1", "builder", state="starting")

    tries = []

    def taken(root, feature, entry_):
        tries.append(entry_["agent_name"])
        raise manifest.NameTaken(f"agent a9 already holds the name {entry_['agent_name']!r}")

    monkeypatch.setattr(manifest, "record_entry", taken)
    code, body = start(team)
    assert code == 4 and "a9" in body["reason"] and "agent-start" not in team.transport.verbs()
    assert len(tries) == 5


@pytest.mark.parametrize("agent_id, words", [("x-sup", "-sup"), ("contact", "contact")])
def test_an_agent_id_that_overlaps_another_senders_message_ids_is_refused(team, agent_id, words):
    team.agent(agent_id, "builder", state="starting")
    code, body = start(team, agent_id=agent_id)
    assert code == 2 and words in body["reason"] and team.transport.calls == []


def test_a_first_run_dialog_answers_exit_4_naming_the_dialog(team):
    team.agent("a1", "builder", state="starting")
    team.transport.answers["agent-start"] = (4, {"unavailable": True, "dialog": True,
                                                 "reason": "a dialog blocks the agent's start: Teach auto mode"})
    code, body = start(team)
    assert code == 4 and body["dialog"] and "dialog" in body["reason"] and body["agent_id"] == "a1"
    assert team.entry("a1")["pid"] is None


def test_agent_start_takes_the_model_cell_and_on_codex_the_effort_cell(team):
    team.agent("a1", "builder", state="starting")
    team.agent("a2", "verifier", state="starting")
    assert start(team, model="implementation@claude")[0] == 0
    code, body = start(team, agent_id="a2", role_name="verifier", model="frontier@codex")
    assert code == 0, body
    claude, codex = [p for _, v, p in team.transport.calls if v == "agent-start"]
    assert claude["model"] == "opus" and claude["harness"] == "claude" and claude["effort"] == "medium"
    assert codex["model"] == "gpt-9-sun" and codex["harness"] == "codex" and codex["effort"] == "high"
    assert body["agent_name"].endswith("-verifier-g-9-sun-hi")


def test_a_named_effort_wins_and_max_maps_per_harness(team):
    team.agent("a1", "builder", state="starting")
    team.agent("a2", "builder", state="starting")
    start(team, effort="max")
    start(team, agent_id="a2", model="implementation@codex", effort="max")
    claude, codex = [p for _, v, p in team.transport.calls if v == "agent-start"]
    assert claude["effort"] == "max" and codex["effort"] == "xhigh" and claude["label"].endswith(" max")


def test_a_model_that_is_not_tier_at_provider_is_refused(team):
    team.agent("a1", "builder", state="starting")
    assert start(team, model="opus")[0] == 2
    assert start(team, model="frontier@gemini")[0] == 2


@pytest.mark.parametrize("harness", ["claude", "codex"])
def test_the_launch_environment_holds_afk_provider_equal_to_the_launched_kind(team, harness, monkeypatch):
    monkeypatch.delenv(entry.AFK_PROVIDER, raising=False)
    team.agent("a1", "builder", state="starting")
    assert start(team, model=f"implementation@{harness}")[0] == 0
    payload = team.transport.calls[-1][2]
    assert payload["env"][entry.AFK_PROVIDER] == harness and payload["env"][entry.AFK_TEAM_RUN] == RUN
    assert entry.AFK_PROVIDER not in os.environ and entry.AFK_PROVIDER not in team.host.env


def test_a_codex_agent_launches_with_full_access_and_a_claude_agent_with_no_flag(team):
    team.agent("a1", "builder", state="starting")
    team.agent("a2", "builder", state="starting")
    start(team, model="implementation@claude")
    start(team, agent_id="a2", model="implementation@codex")
    claude, codex = [p for _, v, p in team.transport.calls if v == "agent-start"]
    assert "args" not in claude and codex["args"] == ["--dangerously-bypass-approvals-and-sandbox"]


def test_the_launch_prompt_names_the_bare_afk_team_command(team):
    team.agent("a1", "builder", state="starting")
    start(team, model="implementation@codex")
    prompt = team.transport.calls[-1][2]["prompt"]
    assert "Send each message with afk-team agent-send and one JSON object" in prompt
    assert "AFK_PLUGIN_ROOT" not in prompt and "afk-team.py" not in prompt


def test_the_spawn_permission_check_runs_once_before_the_first_transport_command(team):
    team.agent("a1", "builder", state="starting")
    team.agent("a2", "builder", state="starting")
    start(team)
    start(team, agent_id="a2")
    assert team.permission_calls == 1 and (team.root / RUN / "permission.json").is_file()


def test_a_refused_permission_check_starts_nothing(team):
    team.agent("a1", "builder", state="starting")
    team.host.check_permission = lambda root, env=None: {"ok": False, "provider": "claude", "rule": "r",
                                                         "problem": "missing", "says": "add the rule", "files": []}
    code, body = start(team)
    assert code == 4 and body["problem"] == "missing" and team.transport.calls == []


# ---- settings copy and owners ----------------------------------------------------------------------------

def test_the_settings_copy_copies_once_and_never_overwrites(team):
    (team.main / ".claude").mkdir()
    (team.main / ".claude" / "settings.local.json").write_text('{"a": 1}', encoding="utf-8")
    team.agent("a1", "builder", state="starting")
    team.agent("a2", "builder", state="starting")
    code, body = start(team)
    assert code == 0 and "copied" in body["settings"]
    (team.worktree / ".claude" / "settings.local.json").write_text('{"mine": 1}', encoding="utf-8")
    code, body = start(team, agent_id="a2")
    assert code == 0 and "skipped" in body["settings"]
    assert json.loads((team.worktree / ".claude" / "settings.local.json").read_text()) == {"mine": 1}


@pytest.mark.parametrize("at", ["write", "close"])
def test_a_failed_settings_copy_leaves_no_file_and_starts_nothing(team, monkeypatch, at):
    (team.main / ".claude").mkdir()
    (team.main / ".claude" / "settings.local.json").write_text('{"a": 1}', encoding="utf-8")
    team.agent("a1", "builder", state="starting")
    real = open

    class Full:
        def __init__(self, handle):
            self.handle = handle

        def write(self, data):
            self.handle.write(data[:1])
            if at == "write":
                raise OSError("disk full")

        def close(self):
            self.handle.close()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()
            if at == "close":
                raise OSError("disk full at the flush")

    monkeypatch.setattr("builtins.open", lambda path, mode="r", *a, **k: Full(real(path, mode, *a, **k))
                        if mode == "xb" else real(path, mode, *a, **k))
    code, body = start(team)
    assert code == 4 and body["copy"].endswith("settings.local.json") and "copy" in body["reason"]
    assert not (team.worktree / ".claude" / "settings.local.json").exists(), "the half-written file is removed"
    assert "agent-start" not in team.transport.verbs()


def test_a_settings_file_made_by_a_parallel_start_skips_the_copy(team, monkeypatch):
    (team.main / ".claude").mkdir()
    (team.main / ".claude" / "settings.local.json").write_text('{"a": 1}', encoding="utf-8")
    target = team.worktree / ".claude" / "settings.local.json"
    real = Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: False if self == target else real(self))
    target.parent.mkdir()
    target.write_text('{"theirs": 1}', encoding="utf-8")
    team.agent("a1", "builder", state="starting")
    code, body = start(team)
    assert code == 0 and "skipped" in body["settings"] and json.loads(target.read_text()) == {"theirs": 1}


def test_agent_start_appends_no_owner_whose_creation_time_cannot_be_read(team, child, monkeypatch):
    seen = []
    monkeypatch.setattr(worktree_owner, "add_owner", lambda path, pid, ctime: seen.append((path, pid, ctime)))
    monkeypatch.setattr(worktree_owner, "creation_time", lambda pid: None)
    team.agent("a1", "builder", state="starting")
    team.transport.answers["agent-start"][1]["pid"] = child.pid
    assert start(team)[0] == 0 and seen == []


def test_agent_start_appends_the_pane_agent_to_the_worktree_owners(team, child, monkeypatch):
    seen = []
    monkeypatch.setattr(worktree_owner, "add_owner", lambda path, pid, ctime: seen.append((path, pid, ctime)))
    team.agent("a1", "builder", state="starting")
    team.transport.answers["agent-start"][1]["pid"] = child.pid
    assert start(team)[0] == 0
    assert seen == [(str(team.worktree), child.pid, worktree_owner.creation_time(child.pid))]


# ---- job supervisor --------------------------------------------------------------------------------------

def test_a_supervisor_start_takes_only_watched_agent_id(team):
    team.agent("a1", "builder")
    code, body = team.call("agent-start", watched_agent_id="a1", role="builder")
    assert code == 2 and "`role`" in body["reason"]
    code, body = team.call("agent-start", watched_agent_id="ghost")
    assert code == 2 and "watched_agent_id" in body["reason"]


def test_a_supervisor_start_answers_pid_and_label_and_refuses_a_second(team, monkeypatch, tmp_path):
    script = tmp_path / "supervisor.py"
    script.write_text("import time; time.sleep(60)", encoding="utf-8")
    monkeypatch.setattr(entry, "SUPERVISOR", script)
    team.agent("a1", "builder", pane_label="G builder opus med")
    before = manifest.read_manifest(team.root, RUN)
    code, body = team.call("agent-start", watched_agent_id="a1")
    try:
        assert code == 0 and set(body) == {"pid", "label"} and body["label"] == "G builder opus med supervisor"
        assert manifest.read_manifest(team.root, RUN) == before, "a supervisor start writes nothing"
        manifest.record_entry(team.root, RUN, {"pid": body["pid"], "owner": "contact", "label": body["label"],
                                               "started_at": worktree_owner.creation_time(body["pid"])})
        code, again = team.call("agent-start", watched_agent_id="a1")
        assert code == 2 and "a1" in again["reason"]
    finally:
        entry.process.kill_tree(body["pid"], force=True, wait_s=5)


# ---- agent-send ------------------------------------------------------------------------------------------

def send(team: Team, sender: str, target: str, kind: str, mid: str, body=None) -> tuple[int, dict]:
    path = team.body(f"{mid}.body", body if body is not None else "hello")
    return team.call("agent-send", agent_id=sender, generation=1, target=target, kind=kind, message_id=mid,
                     body_path=path)


def test_a_message_to_the_contact_agent_lands_in_its_inbox_never_its_pane(team):
    team.pattern({"builder": role()})
    team.pane("b1", "builder")
    code, body = send(team, "b1", "contact", "message", "b1-1")
    assert code == 0 and body["delivered"] and body["way"] == "inbox"
    assert team.inbox() == ["b1-1.json"] and "agent-send" not in team.transport.verbs()
    envelope = json.loads((team.root / RUN / "inbox" / "b1-1.json").read_text())
    assert envelope == {"format_version": 1, "run": RUN, "generation": 1, "from_role": "builder",
                        "agent_id": "b1", "kind": "message", "message_id": "b1-1",
                        "body_path": str(team.root / RUN / "bodies" / "b1-1")}
    assert (team.root / RUN / "bodies" / "b1-1").read_text() == "hello"


def test_finished_goes_only_to_the_report_target_whatever_the_sender_wrote(team):
    team.pattern({"builder": role(), "reviewer-a": role("builder"), "reviewer-b": role("builder")})
    team.pane("b1", "builder")
    team.pane("r1", "reviewer-a")
    team.pane("r2", "reviewer-b")
    code, body = send(team, "r1", "reviewer-b", "finished", "r1-9", {"format_version": 1, "result_path": "x.md"})
    assert code == 0 and body["target"] == "b1", body
    sent = [p for _, v, p in team.transport.calls if v == "agent-send"]
    assert [p["handle"] for p in sent] == ["pane-b1"]
    assert team.inbox() == ["r1-9.json"], "the contact agent gets the copy with the same id"
    signal = json.loads((team.root / RUN / "signals" / "r1.json").read_text())
    assert signal["finished_message_id"] == "r1-9" and signal["result_path"] == "x.md"
    assert signal["format_version"] == 1 and signal["agent_id"] == "r1" and signal["written_at"]


def test_finished_with_the_contact_agent_as_target_is_one_inbox_file(team):
    team.pattern({"builder": role()})
    team.pane("b1", "builder")
    code, body = send(team, "b1", "reviewer", "finished", "b1-2", {"format_version": 1, "result_path": ""})
    assert code == 0 and body["target"] == "contact" and team.inbox() == ["b1-2.json"]
    assert "agent-send" not in team.transport.verbs()


def test_finished_goes_to_the_requester_when_the_role_names_no_target(team):
    team.pattern({"builder": role()})
    team.pane("x1", "lead")
    team.pane("b1", "builder", requester="x1")
    code, body = send(team, "b1", "contact", "finished", "b1-3", {"format_version": 1, "result_path": "r"})
    assert code == 0 and body["target"] == "x1" and team.transport.calls[-1][2]["handle"] == "pane-x1"


def test_a_failed_pane_delivery_still_writes_the_inbox_copy_and_answers_exit_4_naming_the_target(team):
    team.pattern({"builder": role(), "reviewer-a": role("builder")})
    team.pane("b1", "builder")
    team.pane("r1", "reviewer-a")
    team.transport.answers["agent-send"] = (4, {"unavailable": True, "receiver_gone": True, "reason": "gone"})
    code, body = send(team, "r1", "builder", "finished", "r1-1", {"format_version": 1, "result_path": ""})
    assert code == 4 and body["target"] == "b1" and "b1" in body["reason"] and team.inbox() == ["r1-1.json"]


def test_a_failed_pane_delivery_of_a_message_claims_no_inbox_copy(team):
    team.pattern({"builder": role(), "reviewer-a": role("builder")})
    team.pane("b1", "builder")
    team.pane("r1", "reviewer-a")
    team.transport.answers["agent-send"] = (4, {"unavailable": True, "receiver_gone": True, "reason": "gone"})
    code, body = send(team, "r1", "builder", "message", "r1-1")
    assert code == 4 and "inbox_copy" not in body and team.inbox() == []
    code, body = send(team, "r1", "builder", "finished", "r1-2", {"format_version": 1, "result_path": ""})
    assert code == 4 and body["inbox_copy"] is True and team.inbox() == ["r1-2.json"]


@pytest.mark.parametrize("sender, mid", [("b1", "m1"), ("b1", "b2-1"), ("b1", "b1-x"), ("b1", "b10-1"),
                                         ("contact", "c-1"), ("b1", "b1-sup")])
def test_a_message_id_not_built_from_the_senders_agent_id_is_refused(team, sender, mid):
    team.pattern({"builder": role()})
    team.pane("b1", "builder")
    team.pane("b2", "builder")
    code, body = send(team, sender, "contact" if sender != "contact" else "b1", "message", mid)
    assert code == 2 and "`message_id`" in body["reason"] and team.inbox() == []


def test_the_message_id_forms_of_an_agent_its_supervisor_and_the_contact_are_accepted(team):
    team.pattern({"builder": role()})
    team.pane("b1", "builder")
    assert send(team, "b1", "contact", "message", "b1-7")[0] == 0
    assert send(team, "b1", "contact", "parked", "b1-sup-2")[0] == 0
    assert send(team, "contact", "b1", "message", "contact-3")[0] == 0


def test_the_launch_prompt_states_the_message_id_rule(team):
    team.agent("a1", "builder", state="starting")
    start(team)
    assert "message_id is a1-<n>" in team.transport.calls[-1][2]["prompt"]


def test_a_finished_body_whose_result_path_is_not_text_is_refused(team):
    team.pattern({"builder": role()})
    team.pane("b1", "builder")
    for bad in (None, 3, ["x"]):
        code, body = send(team, "b1", "contact", "finished", "b1-1", {"format_version": 1, "result_path": bad})
        assert code == 2 and "result_path" in body["reason"]
    assert team.inbox() == [] and not (team.root / RUN / "signals").exists()


def test_finished_goes_to_the_live_holder_of_the_report_target_role_over_a_lost_one(team):
    team.pattern({"builder": role(), "reviewer-a": role("builder")})
    team.pane("b0", "builder", state="lost")
    team.pane("b1", "builder")
    team.pane("r1", "reviewer-a")
    code, body = send(team, "r1", "builder", "finished", "r1-1", {"format_version": 1, "result_path": ""})
    assert code == 0 and body["target"] == "b1" and team.transport.calls[-1][2]["handle"] == "pane-b1"


def test_a_role_with_a_report_target_may_not_message_the_contact_agent(team):
    team.pattern({"builder": role(), "reviewer-a": role("builder")})
    team.pane("b1", "builder")
    team.pane("r1", "reviewer-a")
    code, body = send(team, "r1", "contact", "message", "r1-1")
    assert code == 2 and "edge reviewer-a -> contact (message)" in body["reason"] and team.inbox() == []


def test_a_failed_inbox_copy_answers_exit_4_naming_the_inbox(team, monkeypatch):
    team.pattern({"builder": role()})
    team.pane("b1", "builder")
    real = entry._publish
    monkeypatch.setattr(entry, "_publish", lambda path, data: (_ for _ in ()).throw(OSError("full"))
                        if path.parent.name == "inbox" else real(path, data))
    code, body = send(team, "b1", "contact", "parked", "b1-4")
    assert code == 4 and body["inbox"] and "inbox" in body["reason"]


def test_an_unknown_finished_or_start_request_version_is_refused(team):
    team.pattern({"builder": role()})
    team.pane("b1", "builder")
    assert send(team, "b1", "contact", "finished", "b1-5", {"format_version": 2, "result_path": ""})[0] == 2
    assert send(team, "b1", "contact", "start-request", "b1-6", {"format_version": 9})[0] == 2


def test_a_message_off_a_declared_edge_or_of_an_unlisted_kind_is_refused_naming_the_edge(team):
    team.pattern({"builder": role(), "reviewer-a": role(), "reviewer-b": role()},
                 edges=[{"from": "reviewer-a", "to": "reviewer-b", "kinds": ["message"]}])
    team.pane("r1", "reviewer-a")
    team.pane("r2", "reviewer-b")
    assert send(team, "r1", "reviewer-b", "message", "r1-1")[0] == 0
    code, body = send(team, "r2", "reviewer-a", "message", "r2-1")
    assert code == 2 and "edge reviewer-b -> reviewer-a (message)" in body["reason"]
    code, body = send(team, "r1", "reviewer-b", "parked", "r1-2")
    assert code == 2 and "edge" in body["reason"]


def test_a_role_and_its_report_target_message_each_other_both_ways_and_siblings_do_not(team):
    team.pattern({"builder": role(), "reviewer-a": role("builder"), "reviewer-b": role("builder")})
    team.pane("b1", "builder")
    team.pane("r1", "reviewer-a")
    team.pane("r2", "reviewer-b")
    assert send(team, "r1", "builder", "message", "r1-1")[0] == 0
    assert send(team, "b1", "reviewer-a", "message", "b1-1")[0] == 0
    assert send(team, "r1", "reviewer-b", "message", "r1-2")[0] == 2
    assert send(team, "r1", "builder", "parked", "r1-3")[0] == 2, "the implied pair carries kind message only"


def test_a_progress_message_to_the_report_target_gets_no_contact_copy(team):
    team.pattern({"builder": role(), "reviewer-a": role("builder")})
    team.pane("b1", "builder")
    team.pane("r1", "reviewer-a")
    assert send(team, "r1", "b1", "message", "r1-1", "progress: read — done")[0] == 0
    assert team.inbox() == []


def test_lifecycle_kinds_to_the_contact_agent_are_always_allowed(team):
    team.pattern({"builder": role("builder2"), "builder2": role()})
    team.pane("b1", "builder")
    for number, kind in enumerate(("parked", "exited")):
        assert send(team, "b1", "contact", kind, f"b1-{number}")[0] == 0
    assert team.inbox() == ["b1-0.json", "b1-1.json"]


def test_the_contact_agent_may_message_any_agent_it_started(team):
    team.pattern({"builder": role()})
    team.pane("b1", "builder")
    code, body = send(team, "contact", "b1", "message", "contact-1")
    assert code == 0 and team.transport.calls[-1][2]["handle"] == "pane-b1"
    assert json.loads(team.transport.calls[-1][2]["text"])["from_role"] == "contact"


def test_a_receiver_that_is_gone_answers_exit_4_and_an_unknown_sender_exit_2(team):
    team.pattern({"builder": role(), "reviewer-a": role("builder")})
    team.pane("b1", "builder", state="lost")
    team.pane("r1", "reviewer-a")
    code, body = send(team, "r1", "b1", "message", "r1-1")
    assert code == 4 and body["receiver_gone"]
    assert send(team, "nobody", "contact", "message", "n-1")[0] == 2


# ---- start requests --------------------------------------------------------------------------------------

def request(**changes) -> dict:
    return {"format_version": 1, "pattern_step": "review", "requester": "b1", "lifespan": "Turn",
            "agents": [{"role": "reviewer-a", "brief_path": "brief.md"}], **changes}


@pytest.fixture
def asking(team):
    team.pattern({"builder": role(), "reviewer-a": role("builder")},
                 steps=[{"name": "build", "roles": ["builder"]}, {"name": "review", "roles": ["reviewer-a"]}])
    team.pane("b1", "builder")
    return team


def test_a_valid_start_request_is_delivered_to_the_contact_inbox(asking):
    assert send(asking, "b1", "contact", "start-request", "b1-1", request())[0] == 0
    assert asking.inbox() == ["b1-1.json"]


def test_an_empty_start_request_effort_reads_as_none_named(asking):
    assert send(asking, "b1", "contact", "start-request", "b1-1", request(effort=""))[0] == 0


@pytest.mark.parametrize("changes, words", [
    ({"lifespan": "Forever"}, "lifespan"),
    ({"effort": "turbo"}, "effort"),
    ({"effort": ["hi"]}, "effort"),
    ({"pattern_step": "ship"}, "step ship"),
    ({"agents": [{"role": "builder2", "brief_path": "b"}]}, "role builder2"),
    ({"agents": []}, "agents"),
    ({"requester": ""}, "requester"),
    ({"colour": 1}, "colour"),
])
def test_a_start_request_is_refused_naming_the_failed_check(asking, changes, words):
    code, body = send(asking, "b1", "contact", "start-request", "b1-1", request(**changes))
    assert code == 2 and words in body["reason"] and asking.inbox() == []


def test_a_start_request_lacking_a_field_is_refused_naming_it(asking):
    body = request()
    del body["lifespan"]
    code, answer = send(asking, "b1", "contact", "start-request", "b1-1", body)
    assert code == 2 and "lifespan" in answer["reason"]


def test_a_start_request_from_an_agent_not_live_in_the_manifest_is_refused(asking):
    asking.pane("old", "builder", state="lost")
    for requester in ("old", "helper-without-an-id"):
        code, body = send(asking, "b1", "contact", "start-request", "b1-1", request(requester=requester))
        assert code == 2 and "not a live agent" in body["reason"] and "3-level nesting limit" in body["reason"]


def test_a_start_request_goes_only_to_the_contact_agent(asking):
    asking.pane("x1", "reviewer-a")
    assert send(asking, "b1", "x1", "start-request", "b1-1", request())[0] == 2


def test_a_solo_step_is_accepted_only_from_a_stage_with_no_stage_map_entry(asking):
    solo = request(pattern_step="solo:afk-implementor", agents=[{"role": "afk-implementor", "brief_path": "b"}])
    assert send(asking, "b1", "contact", "start-request", "b1-1", solo)[0] == 0
    asking.settings["stage-map"] = {"Execute": "build-verify"}
    code, body = send(asking, "b1", "contact", "start-request", "b1-2", solo)
    assert code == 2 and "stage map entry" in body["reason"]


def test_a_solo_step_needs_a_known_role_agent_type_for_every_agent(asking):
    code, body = send(asking, "b1", "contact", "start-request", "b1-1",
                      request(pattern_step="solo:painter", agents=[{"role": "painter", "brief_path": "b"}]))
    assert code == 2 and "known role agent type" in body["reason"]
    code, body = send(asking, "b1", "contact", "start-request", "b1-2",
                      request(pattern_step="solo:afk-reader", agents=[{"role": "afk-implementor", "brief_path": "b"}]))
    assert code == 2 and "afk-reader" in body["reason"]


# ---- charter files and launch prompt ---------------------------------------------------------------------

def test_run_open_writes_one_charter_file_per_role(team):
    code, body = team.call("run-open", session="contact-session", pick="build-verify",
                           moderator_model="frontier@claude")
    assert code == 0, body
    assert sorted(body["charters"]) == ["builder", "reviewer-a", "reviewer-b", "verifier"]
    builder = Path(body["charters"]["builder"]).read_text(encoding="utf-8")
    assert builder.startswith("Purpose: build one unit of work") and "Responsibility: write the tests" in builder
    assert (team.root / RUN / "inbox").is_dir() and (team.root / RUN / "processed").is_dir()
    assert team.permission_calls == 1


def test_the_launch_prompt_names_the_charter_file_before_the_brief_and_sets_it_on_that_launch(team):
    team.call("run-open", session="contact-session", pick="build-verify", moderator_model="frontier@claude")
    team.agent("a1", "builder", state="starting")
    team.agent("a2", "builder", state="starting")
    assert start(team)[0] == 0
    assert start(team, agent_id="a2", resume="session-7")[0] == 0
    charter = str(team.root / RUN / "charters" / "builder.md")
    for payload in [p for _, v, p in team.transport.calls if v == "agent-start"]:
        prompt = payload["prompt"]
        assert prompt.index(charter) < prompt.index(str(team.brief))
        assert payload["env"][entry.AFK_CHARTER_FILE] == charter
    assert team.transport.calls[-1][2]["resume"] == "session-7"
    assert entry.AFK_CHARTER_FILE not in os.environ


def test_an_agent_with_no_charter_file_gets_a_prompt_naming_only_its_brief(team):
    team.agent("a1", "afk-implementor", state="starting")
    assert start(team, role_name="afk-implementor")[0] == 0
    payload = team.transport.calls[-1][2]
    assert entry.AFK_CHARTER_FILE not in payload["env"] and "charter file" not in payload["prompt"]
    assert payload["prompt"].startswith(f"Read your brief, {team.brief}")


# ---- agent-stop ------------------------------------------------------------------------------------------

def stop(team: Team, **data) -> dict:
    code, body = team.call("agent-stop", **data)
    assert code == 0, body
    return body


def test_agent_stop_for_an_agent_id_with_no_entry_answers_stopped_false(team):
    body = stop(team, agent_id="ghost")
    assert body == {"stopped": False, "reason": "no entry holds agent-id ghost"}


def test_a_live_process_whose_creation_time_differs_is_not_killed_and_is_already_gone(team, child):
    team.agent("a1", "builder", pid=child.pid, started_at="2000-01-01T00:00:00Z", transport_kind="multiplexer")
    body = stop(team, agent_id="a1")
    assert body == {"stopped": True, "method": "already gone"} and child.poll() is None
    assert team.entry("a1")["state"] == "cleaned" and team.transport.calls == []


def test_no_live_process_answers_already_gone(team):
    dead = sleeper()
    dead.kill()
    dead.wait()
    team.agent("a1", "builder", pid=dead.pid, started_at="2026-10-22T10:00:00Z", transport_kind="multiplexer")
    assert stop(team, agent_id="a1")["method"] == "already gone"


def test_a_process_id_with_no_started_at_is_already_gone_or_identity_unknown(team, child):
    dead = sleeper()
    dead.kill()
    dead.wait()
    team.agent("a1", "builder", pid=dead.pid)
    assert stop(team, agent_id="a1") == {"stopped": True, "method": "already gone"}
    team.agent("a2", "builder", pid=child.pid)
    body = stop(team, agent_id="a2")
    assert body["stopped"] is False and body["reason"].startswith("identity unknown") and child.poll() is None
    assert team.entry("a2")["state"] == "unkillable"


def test_an_entry_with_neither_pid_nor_handle_answers_nothing_recorded(team):
    team.agent("a1", "builder")
    assert stop(team, agent_id="a1") == {"stopped": True, "method": "nothing recorded"}


def test_a_matching_live_agent_is_stopped_by_its_kind_and_moves_to_cleaned(team, child):
    team.pane("a1", "builder", pid=child.pid, started_at=entry.process.creation_time(child.pid))
    body = stop(team, agent_id="a1", force=True)
    assert body["stopped"] and body["pane_closed"] and body["pane_id"] == "pane-a1"
    assert team.transport.calls[-1][2] == {"pid": child.pid, "handle": "pane-a1", "force": True}
    assert team.entry("a1")["state"] == "cleaned"


def gone_pid() -> int:
    dead = sleeper()
    dead.kill()
    dead.wait()
    return dead.pid


@pytest.mark.parametrize("kind, fields, named, state", [
    ("multiplexer", {"handle": "pane-a1"}, {"pane_closed": False, "pane_id": "pane-a1"}, "unkillable"),
    ("desktop", {"terminal_id": "term-3"}, {"pane_closed": False, "terminal_id": "term-3"}, "unkillable"),
    ("headless", {"handle": "12"}, {}, "cleaned"),
])
def test_a_gone_agent_whose_close_fails_names_the_pane_or_terminal_only_for_its_kind(team, kind, fields, named,
                                                                                      state):
    team.agent("a1", "builder", pid=gone_pid(), started_at="2026-10-22T10:00:00Z", transport_kind=kind, **fields)
    team.transport.answers["agent-stop"] = (4, {"unavailable": True, "reason": "the close failed"})
    body = stop(team, agent_id="a1")
    assert body["stopped"] is True and body["method"] == "already gone"
    assert {k: body[k] for k in ("pane_closed", "pane_id", "terminal_id") if k in body} == named
    assert team.entry("a1")["state"] == state


def test_tr4_sends_the_terminal_identifier_to_the_kind(team):
    team.agent("a1", "builder", transport_kind="desktop", terminal_id="term-3")
    team.transport.answers["agent-stop"] = (0, {"stopped": True, "method": "closed", "pane_closed": True,
                                                "terminal_id": "term-3"})
    stop(team, agent_id="a1")
    assert team.transport.calls[-1][2] == {"terminal_id": "term-3", "force": False}


def test_an_entry_with_a_handle_and_no_kind_answers_stopped_false(team):
    team.agent("a1", "builder", handle="pane-a1")
    body = stop(team, agent_id="a1")
    assert body["stopped"] is False and "kind" in body["reason"] and team.transport.calls == []


def test_a_failed_close_answers_pane_closed_false_naming_the_pane(team):
    team.pane("a1", "builder", pid=2147483000, started_at="2026-10-22T10:00:00Z")
    team.transport.answers["agent-stop"] = (0, {"stopped": False, "pane_closed": False, "pane_id": "pane-a1",
                                                "reason": "herdr could not close pane pane-a1"})
    body = stop(team, agent_id="a1")
    assert body["stopped"] is True and body["method"] == "already gone"
    assert body["pane_closed"] is False and body["pane_id"] == "pane-a1"
    assert team.entry("a1")["state"] == "unkillable"


def test_a_second_stop_does_nothing_and_answers_success(team):
    team.agent("a1", "builder")
    stop(team, agent_id="a1")
    assert stop(team, agent_id="a1")["stopped"] and team.entry("a1")["state"] == "cleaned"


def test_a_stop_the_lifecycle_table_refuses_leaves_the_state_and_says_so(team):
    team.agent("a1", "builder", state="starting")
    body = stop(team, agent_id="a1")
    assert body["stopped"] and "move_refused" in body and team.entry("a1")["state"] == "starting"


def test_a_matching_process_entry_is_killed_by_its_process_id(team):
    proc = sleeper()
    try:
        manifest.record_entry(team.root, RUN, {"pid": proc.pid, "owner": "contact", "label": "inbox wait",
                                               "started_at": worktree_owner.creation_time(proc.pid)})
        before = manifest.read_manifest(team.root, RUN)["processes"]
        body = stop(team, pid=proc.pid)
        assert body["stopped"] and proc.wait(timeout=20) is not None
        assert manifest.read_manifest(team.root, RUN)["processes"] == before, "no state is written to a process entry"
    finally:
        proc.kill()


def test_a_process_entry_whose_creation_time_differs_is_already_gone_and_not_killed(team, child):
    manifest.record_entry(team.root, RUN, {"pid": child.pid, "owner": "contact", "label": "x supervisor",
                                           "started_at": "1"})
    assert stop(team, pid=child.pid) == {"stopped": True, "method": "already gone"} and child.poll() is None
    assert stop(team, pid=12345678)["stopped"] is False


# ---- agent-list, status, wait ----------------------------------------------------------------------------

def test_agent_list_uses_the_goal_cut_to_the_shortest_common_prefix_and_joins_the_manifest(team):
    team.agent("a1", "builder", agent_name="agent-team-topo-builder-opus-med")
    team.agent("a2", "reviewer-b", agent_name="agent-team-reviewer-b-g-6-sol-hi")
    team.transport.answers["agent-list"] = (0, {"agents": [
        {"agent_name": "agent-team-topo-builder-opus-med", "pane_id": "p1"},
        {"agent_name": "agent-team-stray", "pane_id": "p7"}]})
    code, body = team.call("agent-list")
    assert code == 0 and team.transport.calls[-1][2] == {"prefix": "agent-team-"}
    assert body["agents"] == [
        {"agent_name": "agent-team-topo-builder-opus-med", "pane_id": "p1", "agent_id": "a1", "state": "working"},
        {"agent_name": "agent-team-stray", "pane_id": "p7", "agent_id": "", "state": ""}]


@pytest.mark.parametrize("verb", ["agent-status", "agent-read"])
def test_status_or_read_of_an_entry_with_nothing_recorded_answers_in_the_scripts_words(team, verb):
    team.agent("a1", "builder", state="starting")
    code, body = team.call(verb, agent_id="a1")
    assert code == 4 and body["unavailable"] and "a1" in body["reason"] and "starting" in body["reason"]
    assert team.transport.calls == []


def test_an_empty_configured_value_reads_as_empty_text(team, monkeypatch):
    team.host.config = None
    done = subprocess.CompletedProcess([], 0, stdout="\n", stderr="")
    monkeypatch.setattr(entry.subprocess, "run", lambda *a, **k: done)
    assert team.host.setting("stage-map") == ""


def test_agent_status_maps_the_agent_id_to_its_handle_and_refuses_an_unknown_one(team):
    team.pane("a1", "builder")
    code, body = team.call("agent-status", agent_id="a1")
    assert code == 0 and team.transport.calls[-1][2]["handle"] == "pane-a1" and body["agent_id"] == "a1"
    assert team.call("agent-status", agent_id="ghost")[0] == 2


def test_the_wait_job_wakes_on_an_inbox_file_and_one_runs_per_run(team, child):
    (team.root / RUN / "inbox" / "m-1.json").write_text("{}", encoding="utf-8")
    code, body = team.call("wait")
    assert code == 0 and body["woke"] == "message"
    assert manifest.read_manifest(team.root, RUN)["processes"] == [], "the wait job removes its own entry"
    manifest.record_entry(team.root, RUN, {"pid": child.pid, "owner": "contact", "label": entry.WAIT_LABEL,
                                           "started_at": worktree_owner.creation_time(child.pid)})
    code, body = team.call("wait")
    assert code == 2 and str(child.pid) in body["reason"]


def test_every_call_names_its_run(team):
    code, body = cli.dispatch_verb("agent-list", "{}", team.host)
    assert code == 2 and "AFK_TEAM_RUN" in body["reason"]
    team.host.env[entry.AFK_TEAM_RUN] = RUN
    assert cli.dispatch_verb("agent-list", "{}", team.host)[0] == 0
