"""Tests for the proposers script: the plan with its fallbacks, start, wait, critique and cleanup (SDD §3 rows S-6
to S-8; design ADR-0003).

herdr, git and the host facts run in process only: each test hands the script a fake Runner. No real pane, agent or
worktree starts.
"""

import ast
import base64
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
        self.worktrees = set()
        self.queries = {}
        self.screen = ""
        self.timeouts = []
        self.slept = []

    # The host facts.
    def which(self, name):
        return f"/bin/{name}" if name in self.tools else None

    def read_text(self, path):
        return self.files.get(str(Path(path)))

    def glob(self, folder, pattern):
        return sorted(Path(key) for key in self.files
                      if Path(key).parent == Path(folder) and fnmatchcase(Path(key).name, pattern))

    # The commands.
    def sleep(self, seconds):
        self.slept.append((seconds, len(self.calls)))

    def run(self, argv, timeout=None):
        self.calls.append(list(argv))
        self.timeouts.append(timeout)
        if self.on:
            answer = self.on(list(argv))
            if answer is not None:
                return answer
        tool, args = Path(argv[0]).name, list(argv[1:])
        if tool in ("reg", "plutil"):
            return self.queries.get(tuple(argv), (1, "", "ERROR: The system was unable to find the specified value."))
        return self._git(args) if tool == "git" else self._herdr(args)

    def spawned(self):
        """The herdr and git calls: the commands that start or change something."""
        return [call for call in self.calls if Path(call[0]).name not in ("reg", "plutil")]

    def commands(self, *head):
        return [call[1:] for call in self.calls if call[1:1 + len(head)] == list(head)]

    def _git(self, args):
        if args[:1] == ["rev-parse"]:
            return 0, str(self.root / "repo" / ".git") + "\n", ""
        if args[:2] == ["worktree", "add"]:
            Path(args[3]).mkdir(parents=True)
            self.worktrees.add(str(Path(args[3])))
            return 0, "", ""
        if args[:2] == ["worktree", "remove"]:
            path, force = Path(args[-1]), "--force" in args
            if str(path) not in self.worktrees:
                return 128, "", f"fatal: '{path}' is not a working tree"
            if str(path) in self.locked:
                return 1, "", "error: failed to delete: Permission denied"
            if any(path.iterdir()) and not force:
                return 128, "", f"fatal: '{path}' contains modified or untracked files, use --force to delete it"
            shutil.rmtree(path)
            self.worktrees.discard(str(path))
            return 0, "", ""
        if args[:2] == ["worktree", "prune"]:
            self.worktrees = {tree for tree in self.worktrees if Path(tree).exists()}
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


CLAUDE_LINUX = str(Path("/etc/claude-code/managed-settings.json"))
CODEX_LINUX = str(Path("/etc/codex/requirements.toml"))
DISABLE = _json({"permissions": {"disableBypassPermissionsMode": "disable"}})
CLAUDE_PLIST = "/Library/Managed Preferences/com.anthropic.claudecode.plist"
CODEX_PLIST = "/Library/Managed Preferences/com.openai.codex.plist"


def _file(path, text):
    def setup(runner):
        runner.files[path] = text
    return setup


def _claude_macos(runner):
    runner.platform = "darwin"
    runner.files[str(Path("/Library/Application Support/ClaudeCode/managed-settings.json"))] = DISABLE


def _codex_windows(runner):
    runner.platform = "win32"
    runner.env["ProgramData"] = r"D:\Data"
    runner.files[str(Path(r"D:\Data\OpenAI\Codex\requirements.toml"))] = 'allowed_sandbox_modes = ["read-only"]\n'


def _registry(hive, data, kind="REG_SZ"):
    def setup(runner):
        runner.platform = "win32"
        out = f"\r\n{hive}\\SOFTWARE\\Policies\\ClaudeCode\r\n    Settings    {kind}    {data}\r\n\r\n"
        runner.queries[("reg", "query", rf"{hive}\SOFTWARE\Policies\ClaudeCode", "/v", "Settings")] = (0, out, "")
    return setup


def _claude_plist(answer):
    def setup(runner):
        runner.platform = "darwin"
        runner.files[str(Path(CLAUDE_PLIST))] = "plist"
        runner.queries[("plutil", "-convert", "json", "-o", "-", CLAUDE_PLIST)] = answer
    return setup


def _codex_plist(payload):
    def setup(runner):
        runner.platform = "darwin"
        runner.files[str(Path(CODEX_PLIST))] = "plist"
        runner.queries[("plutil", "-extract", "requirements_toml_base64", "raw", "-o", "-", CODEX_PLIST)] = (
            0, payload + "\n", "")
    return setup


def _b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


@pytest.mark.parametrize("setup, reason", [
    (_no_herdr, "no-herdr"),
    (_outside, "outside-herdr"),
    (_no_codex, "no-other-tool"),
    (_claude_managed, "bypass-forbidden"),
    (_claude_drop_in_windows, "bypass-forbidden"),
    (_codex_requirements, "bypass-forbidden"),
    (_file(CLAUDE_LINUX, "{not json"), "bypass-forbidden"),
    (_file(CLAUDE_LINUX, "[1]"), "bypass-forbidden"),
    (_file(CLAUDE_LINUX, proposers.UNREADABLE), "bypass-forbidden"),
    (_file(CODEX_LINUX, "allowed_sandbox_modes = ["), "bypass-forbidden"),
    (_file(CODEX_LINUX, proposers.UNREADABLE), "bypass-forbidden"),
    (_file(CODEX_LINUX, 'allowed_sandbox_modes = "read-only"\n'), "bypass-forbidden"),
    (_file(CODEX_LINUX, 'allowed_approval_policies = ["untrusted", "on-request"]\n'), "bypass-forbidden"),
    (_file(CODEX_LINUX, '[allowed_permission_profiles]\n":workspace" = true\n'), "bypass-forbidden"),
    (_file(CODEX_LINUX, '[allowed_permission_profiles]\n":danger-full-access" = false\n'), "bypass-forbidden"),
    (_claude_macos, "bypass-forbidden"),
    (_codex_windows, "bypass-forbidden"),
    (_registry("HKLM", DISABLE), "bypass-forbidden"),
    (_registry("HKCU", DISABLE, "REG_EXPAND_SZ"), "bypass-forbidden"),
    (_registry("HKLM", "{not json"), "bypass-forbidden"),
    (_claude_plist((0, DISABLE, "")), "bypass-forbidden"),
    (_claude_plist((1, "", "Property List error")), "bypass-forbidden"),
    (_codex_plist(_b64('allowed_sandbox_modes = ["read-only"]\n')), "bypass-forbidden"),
    (_codex_plist("%%% not base64"), "bypass-forbidden"),
])
def test_plan_falls_back_to_one_proposer_and_starts_nothing(runner, doc, phase, setup, reason):
    setup(runner)

    answer = run(runner, "plan", doc)

    assert answer == {"count": 1, "tools": ["claude"], "reason": reason}
    assert dr._proposers_banner(answer) == [
        f"1 solution proposer drafted the design alone (Claude): {dr.SOLO_REASONS[reason]}."]
    assert state(doc)["count"] == 1 and dr._proposers_done(state(doc))
    assert runner.spawned() == []


@pytest.mark.parametrize("setup", [
    _file(CLAUDE_LINUX, _json({"permissions": {"disableBypassPermissionsMode": "enable"}})),
    _file(CLAUDE_LINUX, _json({"permissions": {"deny": ["Read(./.env)"]}})),
    _file(CODEX_LINUX, 'allowed_approval_policies = ["on-request", "never"]\n'),
    _file(CODEX_LINUX, '[features]\nunified_exec = true\n'),
    _file(CODEX_LINUX, '[allowed_permission_profiles]\n":danger-full-access" = true\n'),
    _registry("HKLM", _json({"model": "opus"})),
    _claude_plist((0, _json({"model": "opus"}), "")),
    _codex_plist(_b64('[features]\nunified_exec = true\n')),
])
def test_plan_keeps_two_when_no_policy_turns_full_auto_approval_off(runner, doc, phase, setup):
    setup(runner)

    assert run(runner, "plan", doc)["count"] == 2


def test_plan_reads_both_registry_hives_and_no_plist_on_windows(runner, doc, phase):
    runner.platform = "win32"

    assert run(runner, "plan", doc)["count"] == 2
    assert [call[2] for call in runner.calls if call[0] == "reg"] == [
        r"HKLM\SOFTWARE\Policies\ClaudeCode", r"HKCU\SOFTWARE\Policies\ClaudeCode"]
    assert not [call for call in runner.calls if call[0] == "plutil"]


def test_plan_runs_no_plutil_for_an_absent_managed_profile(runner, doc, phase):
    runner.platform = "darwin"

    assert run(runner, "plan", doc)["count"] == 2
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
    assert state(doc)["stage"] == "drafting" and "failed" not in state(doc)
    assert run(runner, "plan", doc)["count"] == 2


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
    runner.screen = f"> {proposers.DRAFT_PROMPT}\n\nWorking on the draft\n\n> \n"

    answer = started(runner, doc, brief)

    assert all(entry["submitted"] for entry in answer["proposers"])
    assert runner.commands("pane", "send-keys") == []
    confirms = [c for c in runner.commands("agent", "wait") if "working" in c]
    assert [c[2] for c in confirms] == [f"propose-solution-s-1-{tool}" for tool in ("claude", "codex")]
    assert all(c[c.index("--timeout") + 1] == proposers.ENTER_MS for c in confirms)


def test_a_stalled_prompt_behind_a_start_up_dialog_refuses_not_submitted(runner, doc, phase, brief):
    _stalled(runner, still_working=False)
    runner.screen = "Do you trust the files in this folder?\n\n❯ 1. Yes, proceed\n  2. No, exit\n"
    run(runner, "plan", doc)

    error = refused(runner, "start", doc, "--brief", str(brief), "--base", BASE)
    assert error.code == "not-submitted" and "claude" in error.reason
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


def test_the_herdr_waits_follow_the_retry_and_timeout_table(runner, doc, phase, brief):
    _stalled(runner)
    runner.screen = "> Read BRIEF.md in your working folder and follow it.\n"

    started(runner, doc, brief)

    starts = runner.commands("agent", "start")
    assert all(s[s.index("--timeout") + 1] == "90000" for s in starts)
    prompts = runner.commands("agent", "prompt")
    assert all(p[p.index("--timeout") + 1] == "30000" for p in prompts)
    after = [c for c in runner.commands("agent", "wait") if "working" in c]
    assert len(after) == 2 and all(c[c.index("--timeout") + 1] == "30000" for c in after)
    keys = [n for n, call in enumerate(runner.calls) if call[1:3] == ["pane", "send-keys"]]
    assert [seconds for seconds, _ in runner.slept] == [2, 2] and [at for _, at in runner.slept] == keys


def test_a_failed_pane_read_after_a_stall_refuses_not_submitted(runner, doc, phase, brief):
    _stalled(runner)
    stalled = runner.on
    runner.on = lambda argv: _error("timeout") if argv[1:3] == ["pane", "read"] else stalled(argv)
    run(runner, "plan", doc)

    error = refused(runner, "start", doc, "--brief", str(brief), "--base", BASE)
    assert error.code == "not-submitted" and "timeout" in error.reason
    assert runner.commands("pane", "send-keys") == []


def test_a_partial_worktree_add_is_recorded_and_never_force_removed(runner, doc, phase, brief):
    def on(argv):
        if argv[1:3] == ["worktree", "add"]:
            Path(argv[4]).mkdir(parents=True)
            (Path(argv[4]) / "half").write_text("x", "utf-8")
            return 128, "", "fatal: checkout failed"
        return None
    runner.on = on
    run(runner, "plan", doc)

    assert refused(runner, "start", doc, "--brief", str(brief), "--base", BASE).code == "worktree-failed"
    tree = state(doc)["proposers"][0]["worktree"]
    assert Path(tree).is_dir() and dr._open_resources(state(doc)) == [tree]
    assert state(doc)["proposers"][0]["created"] is False
    runner.on = None

    error = refused(runner, "cleanup", doc)
    assert error.code == "cleanup-failed" and error.extra["left"] == [tree] and Path(tree).is_dir()
    assert runner.commands("worktree", "remove") == [["worktree", "remove", tree]]
    shutil.rmtree(tree)
    assert run(runner, "cleanup", doc)["removed"] == [tree] and runner.commands("worktree", "prune")


def test_start_records_created_only_after_the_worktree_add_succeeds(runner, doc, phase, brief):
    started(runner, doc, brief)

    assert all(entry["created"] is True for entry in state(doc)["proposers"])


def test_a_brief_that_cannot_be_written_refuses_worktree_failed(runner, doc, phase, brief):
    def on(argv):
        if argv[1:3] == ["worktree", "add"]:
            (Path(argv[4]) / "BRIEF.md").mkdir(parents=True)
            return 0, "", ""
        return None
    runner.on = on
    run(runner, "plan", doc)

    assert refused(runner, "start", doc, "--brief", str(brief), "--base", BASE).code == "worktree-failed"
    assert runner.commands("pane", "split") == []


def test_wait_waits_without_a_limit_until_idle_done_or_blocked(runner, doc, phase, brief):
    started(runner, doc, brief)
    before = len(runner.calls)

    run(runner, "wait", doc)

    waits = [(call, runner.timeouts[before + n]) for n, call in enumerate(runner.calls[before:])
             if call[1:3] == ["agent", "wait"]]
    assert len(waits) == 2
    assert all(call[4:] == ["--until", "idle", "--until", "done", "--until", "blocked"] and timeout is None
               for call, timeout in waits)


def test_critique_out_of_order_refuses_not_drafted_and_keeps_the_run(runner, doc, phase, brief):
    started(runner, doc, brief)
    before = len(runner.commands("agent", "prompt"))

    assert refused(runner, "critique", doc).code == "not-drafted"
    assert len(runner.commands("agent", "prompt")) == before
    assert state(doc)["stage"] == "drafting" and "failed" not in state(doc)
    run(runner, "wait", doc)
    run(runner, "critique", doc)
    assert refused(runner, "critique", doc).code == "not-drafted"
    assert state(doc)["stage"] == "critiquing" and "failed" not in state(doc)


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
        "1 solution proposer drafted the design alone (Claude): a solution proposer failed before the drafts and "
        "critiques were done."]


def test_a_failure_in_a_codex_session_names_codex(runner, doc, phase, brief):
    del runner.env["CLAUDECODE"]
    runner.env["CODEX_THREAD_ID"] = "t-1"
    _fail_draft(runner, doc, brief)

    assert run(runner, "plan", doc) == {"count": 1, "tools": ["codex"], "reason": "proposer-failed"}


def test_cleanup_of_a_two_proposer_plan_that_never_started_answers_proposer_failed(runner, doc, phase, brief):
    run(runner, "plan", doc)
    refused(runner, "start", doc, "--brief", str(brief.with_name("missing.md")), "--base", BASE)

    answer = run(runner, "cleanup", doc)

    assert answer["proposers"] == {"count": 1, "tools": ["claude"], "reason": "proposer-failed"}
    assert state(doc)["failed"] == {"stage": "planned", "code": "not-finished"} and state(doc)["cleaned"] is True


@pytest.mark.parametrize("steps", [[], ["wait"], ["wait", "critique"]])
def test_cleanup_before_the_critiques_are_back_answers_proposer_failed(runner, doc, phase, brief, steps):
    started(runner, doc, brief)
    for verb in steps:
        run(runner, verb, doc)
    stage = state(doc)["stage"]

    assert run(runner, "cleanup", doc)["proposers"] == {"count": 1, "tools": ["claude"], "reason": "proposer-failed"}
    assert state(doc)["failed"] == {"stage": stage, "code": "not-finished"}


def test_start_after_a_failure_refuses_and_starts_nothing(runner, doc, phase, brief):
    runner.on = lambda argv: (128, "", "fatal: not a git repository") if argv[1:2] == ["rev-parse"] else None
    run(runner, "plan", doc)
    assert refused(runner, "start", doc, "--brief", str(brief), "--base", BASE).code == "worktree-failed"
    assert state(doc)["failed"] == {"stage": "drafting", "code": "worktree-failed"}
    runner.on = None
    before = len(runner.calls)

    assert refused(runner, "start", doc, "--brief", str(brief), "--base", BASE).code == "not-planned"
    assert len(runner.calls) == before


def test_start_leaves_a_folder_that_was_there_before_it(runner, doc, phase, brief):
    held = runner.root / "repo-worktrees" / "proposer-propose-solution-s-1-codex"
    held.mkdir(parents=True)
    (held / "work.txt").write_text("keep", "utf-8")
    run(runner, "plan", doc)

    assert refused(runner, "start", doc, "--brief", str(brief), "--base", BASE).code == "worktree-failed"
    assert [args[3] for args in runner.commands("worktree", "add")] == [
        str(runner.root / "repo-worktrees" / "proposer-propose-solution-s-1-claude")]
    run(runner, "cleanup", doc)
    assert (held / "work.txt").read_text("utf-8") == "keep"
    assert all(str(held) not in call for call in runner.commands("worktree", "remove"))


def test_start_after_a_cleaned_plan_with_no_proposers_refuses_not_planned(runner, doc, phase, brief):
    _no_codex(runner)
    run(runner, "plan", doc)
    run(runner, "cleanup", doc)

    assert refused(runner, "start", doc, "--brief", str(brief), "--base", BASE).code == "not-planned"


def test_a_refusal_before_start_records_no_failure(runner, doc, phase, brief):
    run(runner, "plan", doc)
    refused(runner, "start", doc, "--brief", str(brief.with_name("missing.md")), "--base", BASE)

    assert state(doc)["stage"] == "planned" and "failed" not in state(doc)
    assert run(runner, "plan", doc)["count"] == 2


# cleanup: every recorded pane and worktree goes (PRD AC-026; decision D-7).

def test_cleanup_closes_each_pane_removes_each_worktree_and_keeps_the_state_file_cleaned(runner, doc, phase, brief):
    entries = started(runner, doc, brief)["proposers"]
    run(runner, "wait", doc)
    run(runner, "critique", doc)
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


def test_cleanup_keeps_the_worktree_of_a_pane_it_could_not_close(runner, doc, phase, brief):
    entries = started(runner, doc, brief)["proposers"]
    stuck = entries[0]["pane"]
    runner.on = lambda argv: _error("timeout") if argv[1:3] == ["pane", "close"] and argv[3] == stuck else None

    error = refused(runner, "cleanup", doc)
    assert error.code == "cleanup-failed" and error.extra["left"] == [stuck, entries[0]["worktree"]]
    assert Path(entries[0]["worktree"]).is_dir() and not Path(entries[1]["worktree"]).exists()


def test_cleanup_counts_a_pane_already_gone_as_closed_and_tries_a_plain_remove_first(runner, doc, phase, brief):
    entries = started(runner, doc, brief)["proposers"]
    runner.panes.pop(entries[0]["pane"])
    for item in Path(entries[1]["worktree"]).iterdir():
        item.unlink()

    answer = run(runner, "cleanup", doc)

    assert answer["closed"] == [entry["pane"] for entry in entries]
    assert runner.commands("worktree", "remove")[-1] == ["worktree", "remove", entries[1]["worktree"]]


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
