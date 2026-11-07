"""Tests for the proposers script: the plan with its fallbacks, start, wait, critique and cleanup (SDD §3 rows S-6
to S-8; design ADR-0003).

herdr, git and the host facts run in process only: each test hands the script a fake Runner. No real pane, agent or
worktree starts.
"""

import ast
import json
import shutil
import sys
from fnmatch import fnmatchcase
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "skills" / "propose-solution" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import design_round as dr  # noqa: E402
import proposers  # noqa: E402
from grill_common import Refusal  # noqa: E402

BASE = "abc123"
SESSION_PANE = "w1:p0"
BRIEF_TEXT = "Design the order store. Settled aspects: entities, keys."


def _json(value):
    return json.dumps(value)


def _error(code):
    return 1, "", _json({"error": {"code": code, "message": code}})


class FakeRunner:
    """herdr, git and the host facts in process. Each command lands in `calls`; `on` may answer one first."""

    def __init__(self, root):
        self.root = root
        self.env = {"HERDR_ENV": "1", "HERDR_PANE_ID": SESSION_PANE, "CLAUDECODE": "1"}
        self.tools = {"herdr", "claude", "codex"}
        self.platform = "linux"
        self.files = {}
        self.calls = []
        self.on = None
        self.panes = {}
        self.agents = {}
        self.lazy = set()
        self.locked = set()
        self.screen = ""

    # The host facts.
    def which(self, name):
        return f"/bin/{name}" if name in self.tools else None

    def read_text(self, path):
        return self.files.get(str(Path(path)))

    def glob(self, folder, pattern):
        return sorted(Path(key) for key in self.files
                      if Path(key).parent == Path(folder) and fnmatchcase(Path(key).name, pattern))

    # The commands.
    def run(self, argv, timeout=None):
        self.calls.append(list(argv))
        if self.on:
            answer = self.on(list(argv))
            if answer is not None:
                return answer
        tool, args = Path(argv[0]).name, list(argv[1:])
        return self._git(args) if tool == "git" else self._herdr(args)

    def commands(self, *head):
        return [call[1:] for call in self.calls if call[1:1 + len(head)] == list(head)]

    def _git(self, args):
        if args[:1] == ["rev-parse"]:
            return 0, str(self.root / "repo" / ".git") + "\n", ""
        if args[:2] == ["worktree", "add"]:
            Path(args[3]).mkdir(parents=True)
            return 0, "", ""
        if args[:2] == ["worktree", "remove"]:
            path, force = Path(args[-1]), "--force" in args
            if str(path) in self.locked:
                return 1, "", "error: failed to delete: Permission denied"
            if any(path.iterdir()) and not force:
                return 128, "", f"fatal: '{path}' contains modified or untracked files, use --force to delete it"
            shutil.rmtree(path)
            return 0, "", ""
        if args[:2] == ["worktree", "prune"]:
            return 0, "", ""
        raise AssertionError(f"unexpected git {args}")

    def _herdr(self, args):
        verb = args[:2]
        if verb == ["pane", "split"]:
            pane = f"w1:p{len(self.panes) + 1}"
            self.panes[pane] = {"cwd": args[args.index("--cwd") + 1], "status": "idle"}
            return 0, _json({"id": "cli:pane:split", "result": {"pane": {"pane_id": pane}}}), ""
        if verb == ["agent", "start"]:
            self.agents[args[2]] = args[args.index("--pane") + 1]
            return 0, _json({"result": {}}), ""
        if verb == ["agent", "prompt"]:
            self._work(args[2], args[3])
            return 0, _json({"result": {}}), ""
        if verb == ["agent", "wait"]:
            return (0, _json({"result": {}}), "") if self.agents.get(args[2]) in self.panes else _error("agent_not_found")
        if verb == ["pane", "get"]:
            if args[2] not in self.panes:
                return _error("pane_not_found")
            return 0, _json({"result": {"pane": {"pane_id": args[2], "agent_status": self.panes[args[2]]["status"]}}}), ""
        if verb == ["pane", "read"]:
            return 0, self.screen, ""
        if verb == ["pane", "send-keys"]:
            return 0, _json({"result": {}}), ""
        if verb == ["pane", "close"]:
            return (0, _json({"result": {}}), "") if self.panes.pop(args[2], None) else _error("pane_not_found")
        raise AssertionError(f"unexpected herdr {args}")

    def _work(self, agent, text):
        """The tool behind a pane writes the file its prompt names, unless the test made it lazy."""
        cwd = Path(self.panes[self.agents[agent]]["cwd"])
        tool = agent.rsplit("-", 1)[-1]
        if tool in self.lazy:
            return
        for name in ("CRITIQUE.md", "DRAFT.md"):
            if name in text:
                (cwd / name).write_text(f"{tool} {name}", "utf-8")
                return


@pytest.fixture
def runner(tmp_path):
    return FakeRunner(tmp_path)


@pytest.fixture
def doc(tmp_path):
    pages = tmp_path / "repo" / "docs" / "specs" / "PROJ-1" / "pages"
    pages.mkdir(parents=True)
    return pages / "propose-solution-s-1.json"


@pytest.fixture
def phase(monkeypatch):
    """The design phase the page document is in; the proposers phase unless a test sets another."""
    current = {"phase": dr.PROPOSERS_PHASE}
    real = dr.next_step

    def next_step(doc_value, state=None):
        return {**real(doc_value, state), "phase": current["phase"]}

    monkeypatch.setattr(proposers.dr, "next_step", next_step)
    return current


@pytest.fixture
def brief(tmp_path):
    path = tmp_path / "brief.md"
    path.write_text(BRIEF_TEXT, "utf-8")
    return path


def run(runner, verb, doc, *extra):
    return proposers.main([verb, "--doc", str(doc), *extra], runner=runner)


def refused(runner, verb, doc, *extra):
    with pytest.raises(Refusal) as caught:
        run(runner, verb, doc, *extra)
    return caught.value


def state(doc):
    return dr.proposers_state(doc)


def started(runner, doc, brief):
    run(runner, "plan", doc)
    return run(runner, "start", doc, "--brief", str(brief), "--base", BASE)


# plan: count 2, or count 1 with the reason (PRD AC-017, AC-018, AC-024).

def test_plan_answers_both_tools_when_herdr_both_tools_and_bypass_are_there(runner, doc, phase):
    answer = run(runner, "plan", doc)

    assert answer == {"count": 2, "tools": ["claude", "codex"], "reason": None}
    assert dr._proposers_banner(answer)[1] == dr.FENCE
    recorded = state(doc)
    assert recorded["count"] == 2 and recorded["proposers"] == [] and recorded["cleaned"] is False
    assert not dr._proposers_done(recorded)
    assert runner.calls == []


def _no_herdr(runner):
    runner.tools.discard("herdr")


def _outside(runner):
    del runner.env["HERDR_ENV"]


def _no_codex(runner):
    runner.tools.discard("codex")


def _claude_managed(runner):
    runner.files[str(Path("/etc/claude-code/managed-settings.json"))] = _json(
        {"permissions": {"disableBypassPermissionsMode": "disable"}})


def _claude_drop_in_windows(runner):
    runner.platform = "win32"
    runner.env["ProgramFiles"] = r"C:\Program Files"
    runner.files[str(Path(r"C:\Program Files\ClaudeCode\managed-settings.d\20-security.json"))] = _json(
        {"permissions": {"disableBypassPermissionsMode": "disable"}})


def _codex_requirements(runner):
    runner.files[str(Path("/etc/codex/requirements.toml"))] = 'allowed_sandbox_modes = ["read-only", "workspace-write"]\n'


@pytest.mark.parametrize("setup, reason", [
    (_no_herdr, "no-herdr"),
    (_outside, "outside-herdr"),
    (_no_codex, "no-other-tool"),
    (_claude_managed, "bypass-forbidden"),
    (_claude_drop_in_windows, "bypass-forbidden"),
    (_codex_requirements, "bypass-forbidden"),
])
def test_plan_falls_back_to_one_proposer_and_starts_nothing(runner, doc, phase, setup, reason):
    setup(runner)

    answer = run(runner, "plan", doc)

    assert answer == {"count": 1, "tools": ["claude"], "reason": reason}
    assert dr._proposers_banner(answer) == [
        f"1 solution proposer drafted the design alone (Claude): {dr.SOLO_REASONS[reason]}."]
    assert state(doc)["count"] == 1 and dr._proposers_done(state(doc))
    assert runner.calls == []


def test_plan_names_the_session_tool_when_it_drafts_alone(runner, doc, phase):
    del runner.env["CLAUDECODE"]
    runner.env["CODEX_THREAD_ID"] = "t-1"
    _no_herdr(runner)

    assert run(runner, "plan", doc)["tools"] == ["codex"]


def test_plan_keeps_two_when_the_codex_requirements_allow_full_access(runner, doc, phase):
    runner.files[str(Path("/etc/codex/requirements.toml"))] = 'allowed_sandbox_modes = ["workspace-write", "danger-full-access"]\n'

    assert run(runner, "plan", doc)["count"] == 2


def test_plan_refuses_before_every_aspect_settles(runner, doc):
    assert refused(runner, "plan", doc).code == "aspects-open"
    assert not dr.proposers_state_path(doc).exists()


def test_plan_answers_the_recorded_plan_again(runner, doc, phase):
    run(runner, "plan", doc)
    runner.tools.discard("codex")

    assert run(runner, "plan", doc)["count"] == 2


# start: 1 call launches both tools (PRD AC-019, AC-020, AC-025).

def test_start_launches_both_tools_each_in_its_own_worktree_and_pane(runner, doc, phase, brief):
    answer = started(runner, doc, brief)

    entries = answer["proposers"]
    assert [entry["tool"] for entry in entries] == ["claude", "codex"]
    assert all(entry["submitted"] is True and entry["pane"] for entry in entries)
    trees = [Path(entry["worktree"]) for entry in entries]
    assert trees[0] != trees[1] and all(tree.parent == runner.root / "repo-worktrees" for tree in trees)
    assert [args for args in runner.commands("worktree", "add")] == [
        ["worktree", "add", "--detach", str(tree), BASE] for tree in trees]
    assert all((tree / "BRIEF.md").read_text("utf-8") == BRIEF_TEXT for tree in trees)
    splits = runner.commands("pane", "split")
    assert [split[split.index("--cwd") + 1] for split in splits] == [str(tree) for tree in trees]
    assert all(split[split.index("--pane") + 1] == SESSION_PANE and "right" in split for split in splits)
    starts = runner.commands("agent", "start")
    assert [(s[s.index("--kind") + 1], s[s.index("--") + 1:]) for s in starts] == [
        ("claude", ["--dangerously-skip-permissions"]), ("codex", ["--yolo"])]
    prompts = runner.commands("agent", "prompt")
    assert len(prompts) == 2 and all("BRIEF.md" in p[3] and "DRAFT.md" in p[3] for p in prompts)
    assert all(p[4:6] == ["--wait", "--until"] and p[6] == "working" for p in prompts)
    assert sorted(dr._open_resources(state(doc))) == sorted([entry["pane"] for entry in entries] + [str(t) for t in trees])


def test_a_second_start_refuses_same_tool(runner, doc, phase, brief):
    started(runner, doc, brief)
    before = len(runner.calls)

    assert refused(runner, "start", doc, "--brief", str(brief), "--base", BASE).code == "same-tool"
    assert len(runner.calls) == before


def test_start_refuses_after_a_one_proposer_plan(runner, doc, phase, brief):
    _no_codex(runner)
    run(runner, "plan", doc)

    assert refused(runner, "start", doc, "--brief", str(brief), "--base", BASE).code == "not-planned"
    assert runner.calls == []


def test_start_refuses_before_every_aspect_settles(runner, doc, phase, brief):
    run(runner, "plan", doc)
    phase["phase"] = "aspects"

    assert refused(runner, "start", doc, "--brief", str(brief), "--base", BASE).code == "aspects-open"


def _stalled(runner, still_working=True):
    def on(argv):
        if argv[1:3] == ["agent", "prompt"]:
            return _error("agent_prompt_stalled")
        if argv[1:3] == ["agent", "wait"] and "working" in argv and not still_working:
            return _error("timeout")
        return None
    runner.on = on


def test_a_stalled_prompt_gets_one_enter_when_the_brief_is_still_in_the_input_line(runner, doc, phase, brief):
    _stalled(runner)
    runner.screen = "Claude Code\n\n> Read BRIEF.md in your working folder and follow it. Write your\n  design draft\n"

    answer = started(runner, doc, brief)

    assert all(entry["submitted"] for entry in answer["proposers"])
    assert runner.commands("pane", "send-keys") == [["pane", "send-keys", entry["pane"], "enter"]
                                                     for entry in answer["proposers"]]


def test_a_stalled_prompt_gets_no_enter_when_the_brief_left_the_input_line(runner, doc, phase, brief):
    _stalled(runner)
    runner.screen = "Working on the draft\n\n> \n"

    answer = started(runner, doc, brief)

    assert all(entry["submitted"] for entry in answer["proposers"])
    assert runner.commands("pane", "send-keys") == []


def test_a_prompt_still_stalled_after_the_enter_refuses_not_submitted(runner, doc, phase, brief):
    _stalled(runner, still_working=False)
    runner.screen = "> Read BRIEF.md in your working folder and follow it.\n"

    run(runner, "plan", doc)

    assert refused(runner, "start", doc, "--brief", str(brief), "--base", BASE).code == "not-submitted"
    assert len(runner.commands("pane", "send-keys")) == 1
    assert dr._open_resources(state(doc))


def test_a_failed_worktree_refuses_worktree_failed(runner, doc, phase, brief):
    runner.on = lambda argv: (128, "", "fatal: invalid reference") if argv[1:3] == ["worktree", "add"] else None
    run(runner, "plan", doc)

    assert refused(runner, "start", doc, "--brief", str(brief), "--base", BASE).code == "worktree-failed"
    assert runner.commands("pane", "split") == []


def _boxed(text, width):
    """A Claude-style input box that wraps `text` at `width`, with a footer under it."""
    words, lines, line = text.split(), [], "> "
    for word in words:
        if len(line) + len(word) + 1 > width:
            lines.append(line)
            line = "  "
        line += word + " "
    lines.append(line)
    return "\n".join(["Claude Code", "╭" + "─" * (width + 2) + "╮", *(f"│ {item:<{width}} │" for item in lines),
                      "╰" + "─" * (width + 2) + "╯", "  ? for shortcuts", "  ⏵⏵ bypass permissions on (shift+tab)"])


@pytest.mark.parametrize("width", [40, 60, 80])
def test_a_stalled_prompt_wrapped_in_a_narrow_input_box_still_gets_its_enter(width):
    text = proposers.CRITIQUE_PROMPT.format(other=r"C:\work\repo-worktrees\proposer-s-1-codex\DRAFT.md",
                                            brief=proposers.BRIEF, critique=proposers.CRITIQUE)

    assert proposers._in_input_line(_boxed(text, width), text)
    assert proposers._in_input_line(_boxed(proposers.DRAFT_PROMPT, width), proposers.DRAFT_PROMPT)


def test_a_brief_above_an_empty_input_line_counts_as_submitted():
    screen = "\n".join([f"> {proposers.DRAFT_PROMPT}", "", "Reading BRIEF.md", *(f"line {n}" for n in range(8)),
                        _boxed("", 60)])

    assert not proposers._in_input_line(screen, proposers.DRAFT_PROMPT)


def test_after_a_partial_start_wait_and_critique_refuse_not_started(runner, doc, phase, brief):
    runner.on = lambda argv: ((128, "", "fatal: busy") if argv[1:3] == ["worktree", "add"] and "codex" in argv[4]
                              else None)
    run(runner, "plan", doc)
    refused(runner, "start", doc, "--brief", str(brief), "--base", BASE)

    assert refused(runner, "wait", doc).code == "not-started"
    assert refused(runner, "critique", doc).code == "not-started"


def test_after_cleanup_critique_refuses_not_started(runner, doc, phase, brief):
    started(runner, doc, brief)
    run(runner, "wait", doc)
    run(runner, "cleanup", doc)

    assert refused(runner, "critique", doc).code == "not-started"
    assert refused(runner, "wait", doc).code == "not-started"


# wait and critique: only the 4 declared files come back (PRD AC-020).

def test_wait_then_critique_then_wait_answers_the_four_files(runner, doc, phase, brief):
    entries = started(runner, doc, brief)["proposers"]
    trees = {entry["tool"]: Path(entry["worktree"]) for entry in entries}

    first = run(runner, "wait", doc)
    assert first["states"] == {"claude": "idle", "codex": "idle"} and "files" not in first
    assert run(runner, "critique", doc) == {"ok": True, "submitted": {"claude": True, "codex": True}}
    critiques = runner.commands("agent", "prompt")[2:]
    assert str(trees["codex"] / "DRAFT.md") in critiques[0][3] and str(trees["claude"] / "DRAFT.md") in critiques[1][3]
    second = run(runner, "wait", doc)

    assert second["files"] == [str(trees[tool] / name) for tool in ("claude", "codex")
                               for name in ("DRAFT.md", "CRITIQUE.md")]
    assert all(Path(path).is_file() for path in second["files"])


def test_wait_refuses_no_draft_when_a_draft_is_missing(runner, doc, phase, brief):
    runner.lazy.add("codex")
    entries = started(runner, doc, brief)["proposers"]

    error = refused(runner, "wait", doc)
    assert error.code == "no-draft" and str(Path(entries[1]["worktree"]) / "DRAFT.md") in error.reason


def test_wait_refuses_no_draft_when_a_critique_is_missing(runner, doc, phase, brief):
    started(runner, doc, brief)
    run(runner, "wait", doc)
    runner.lazy.add("claude")
    run(runner, "critique", doc)

    error = refused(runner, "wait", doc)
    assert error.code == "no-draft" and "CRITIQUE.md" in error.reason


def test_wait_refuses_pane_gone_when_a_pane_closed(runner, doc, phase, brief):
    entries = started(runner, doc, brief)["proposers"]
    runner.panes.pop(entries[0]["pane"])

    assert refused(runner, "wait", doc).code == "pane-gone"


# A failure after start: the agent in charge drafts alone, and the banner says why (SDD §6, §7; decision D-10).

def _fail_codex_worktree(runner, doc, brief):
    runner.on = lambda argv: ((128, "", "fatal: busy") if argv[1:3] == ["worktree", "add"] and "codex" in argv[4]
                              else None)
    run(runner, "plan", doc)
    return refused(runner, "start", doc, "--brief", str(brief), "--base", BASE)


def _fail_draft(runner, doc, brief):
    runner.lazy.add("codex")
    started(runner, doc, brief)
    return refused(runner, "wait", doc)


def _fail_pane(runner, doc, brief):
    entries = started(runner, doc, brief)["proposers"]
    runner.panes.pop(entries[1]["pane"])
    return refused(runner, "wait", doc)


def _fail_critique(runner, doc, brief):
    started(runner, doc, brief)
    run(runner, "wait", doc)
    runner.on = lambda argv: _error("agent_blocked") if argv[1:3] == ["agent", "prompt"] and "codex" in argv[3] else None
    return refused(runner, "critique", doc)


@pytest.mark.parametrize("fail, stage, code", [
    (_fail_codex_worktree, "drafting", "worktree-failed"),
    (_fail_draft, "drafting", "no-draft"),
    (_fail_pane, "drafting", "pane-gone"),
    (_fail_critique, "drafted", "not-submitted"),
])
def test_a_failure_after_start_records_proposer_failed(runner, doc, phase, brief, fail, stage, code):
    assert fail(runner, doc, brief).code == code

    recorded = state(doc)
    assert recorded["stage"] == "failed" and recorded["failed"] == {"stage": stage, "code": code}
    solo = {"count": 1, "tools": ["claude"], "reason": "proposer-failed"}
    assert run(runner, "plan", doc) == solo
    assert refused(runner, "wait", doc).code == "not-started"
    assert refused(runner, "critique", doc).code == "not-started"
    runner.on = None
    assert run(runner, "cleanup", doc)["proposers"] == solo
    assert dr._proposers_banner(solo) == [
        f"1 solution proposer drafted the design alone (Claude): {dr.SOLO_REASONS['proposer-failed']}."]


def test_a_refusal_before_start_records_no_failure(runner, doc, phase, brief):
    run(runner, "plan", doc)
    refused(runner, "start", doc, "--brief", str(brief.with_name("missing.md")), "--base", BASE)

    assert state(doc)["stage"] == "planned" and "failed" not in state(doc)
    assert run(runner, "plan", doc)["count"] == 2


# cleanup: every recorded pane and worktree goes (PRD AC-026; decision D-7).

def test_cleanup_closes_each_pane_removes_each_worktree_and_keeps_the_state_file_cleaned(runner, doc, phase, brief):
    entries = started(runner, doc, brief)["proposers"]
    run(runner, "wait", doc)

    answer = run(runner, "cleanup", doc)

    assert answer == {"ok": True, "closed": [entry["pane"] for entry in entries],
                      "removed": [entry["worktree"] for entry in entries],
                      "proposers": {"count": 2, "tools": ["claude", "codex"], "reason": None}}
    assert not any(Path(entry["worktree"]).exists() for entry in entries) and runner.panes == {}
    assert len(runner.commands("worktree", "remove", "--force")) == 2
    recorded = state(doc)
    assert recorded["cleaned"] is True and dr._open_resources(recorded) == [] and dr._proposers_done(recorded)
    assert all(entry["pane"] is None and entry["worktree"] is None for entry in recorded["proposers"])


def test_cleanup_refuses_cleanup_failed_naming_what_is_left_then_runs_again(runner, doc, phase, brief):
    entries = started(runner, doc, brief)["proposers"]
    stuck = entries[1]["worktree"]
    runner.locked.add(stuck)

    error = refused(runner, "cleanup", doc)
    assert error.code == "cleanup-failed" and error.extra["left"] == [stuck]
    assert dr._open_resources(state(doc)) == [stuck] and not state(doc)["cleaned"]

    runner.locked.clear()
    assert run(runner, "cleanup", doc)["removed"] == [stuck]
    assert state(doc)["cleaned"] is True


def test_cleanup_prunes_a_worktree_deleted_by_hand(runner, doc, phase, brief):
    entries = started(runner, doc, brief)["proposers"]
    shutil.rmtree(entries[0]["worktree"])

    assert run(runner, "cleanup", doc)["removed"] == [entry["worktree"] for entry in entries]
    assert runner.commands("worktree", "prune")


def test_cleanup_after_a_one_proposer_plan_records_cleaned(runner, doc, phase):
    _no_herdr(runner)
    run(runner, "plan", doc)

    assert run(runner, "cleanup", doc) == {"ok": True, "closed": [], "removed": [],
                                           "proposers": {"count": 1, "tools": ["claude"], "reason": "no-herdr"}}
    assert state(doc)["cleaned"] is True and runner.calls == []


# The Runner and the slot it replaces (PRD AC-017; SDD §14 row "second-provider slot").

def test_only_the_runner_starts_a_process():
    tree = ast.parse((SCRIPTS / "proposers.py").read_text("utf-8"))
    runner_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HerdrRunner")
    inside = {id(node) for node in ast.walk(runner_class)}
    outside = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Attribute)
               and isinstance(node.value, ast.Name) and node.value.id in {"subprocess", "shutil", "os"}
               and id(node) not in inside and node.attr not in {"replace", "path"}]
    assert outside == []


def test_the_second_provider_slot_is_gone():
    assert not (SCRIPTS / "second_provider.py").exists()
