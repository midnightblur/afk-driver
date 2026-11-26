"""The live start rows of /afkv2:dogfood: `dogfood_live_start.py --row VR-NNN`.

An agent or the end gate runs it from a herdr pane. Each run builds its own world in a scratch folder outside every
repository: D-WORK (a throwaway work repository with 1 commit and no remote) and D-SRC (a local clone of this plugin
build with the base branch verify/df-base and no remote, so nothing reaches a forge). It opens 1 new herdr tab, starts
a real Claude or Codex main agent in it as the developer would, plays the developer's turns, and checks the Then of
the row. At the end, also after a failure, it closes the tab with every pane in it, deletes the session state of
that tab's main pane, puts the install record back byte for byte, and removes the scratch folder with D-SRC and its
worktrees. It writes 1 JSON answer to stdout and to `$AFKV2_EVIDENCE/<row>.json` (else the scratch results file), with
what it saw. Exit 0: the Then holds; 1: it does not, or the run failed; 2: bad input.

Rows:
  VR-007, VR-008   dogfood.py start from a real herdr shell pane, with a scratch install record (E-HERDR)
  VR-001, VR-003, VR-004, VR-009, VR-010, VR-011
                   a Claude main agent with the feature build loaded by --plugin-dir (E-LIVE-C)
  VR-002           a Codex main agent that runs the skill file of the feature build (E-LIVE-X)
  VR-056, VR-057   the plugin source step of setup in a Claude session, with a scratch install record
  VR-065           the same step in a Codex session

The agent rows use the real afkv2 data folder: herdr starts the afkv2 pane with its own environment, so the afkv2
agent reads the real install record and state. The run adds the line `source <D-SRC>` to the real install record
and puts the original bytes back at its end; a backup beside it survives a killed run, and the next run puts it back
first.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AFKV2 = Path(__file__).resolve().parents[2]
PLUGIN_REPOSITORY = AFKV2.parent
DOGFOOD = Path("afkv2") / "skills" / "dogfood"
SETUP_SKILL = Path("afkv2") / "skills" / "setup" / "SKILL.md"
BASE = "verify/df-base"
SUGGESTED_BASE = "feat/afkv2"
TICKET = "DF-1"
ASK_WE01 = "step 4 of small-change is unclear"
ASK_WE02_2 = "the gc refusal text is unclear"
ASK_FEATURE = "add a new skill that lists my open Draft changes"
ROLE_LINE = "You are the afkv2 agent of a dogfood session."
FORWARD_LINE = "A new ask from the main pane:"
SMALL_BRANCH = re.compile(r"feat/afkv2-df-\d{8}-\d{4}")
SETUP_ONLY = ("Run only step 1 of it, and of step 1 only `setup.py status` (not `claude-cli`), and step 3, Plugin "
              "source. Skip every other step and change nothing else.")
START_LIMIT_S, EXISTING_LIMIT_S = 120, 35
AGENT_READY_MS = 120000
TURN_LIMIT_S, WORK_LIMIT_S = 300, 600
POLL_S = 3
COMMAND_LIMIT_S = 180
SCRATCH_PREFIX = "afkv2-df-live"
RECORD_BACKUP = "install.txt.dogfood-live-backup"
ROWS = ("VR-001", "VR-002", "VR-003", "VR-004", "VR-007", "VR-008", "VR-009", "VR-010", "VR-011", "VR-056", "VR-057",
        "VR-065")


class Failed(Exception):
    """The run cannot go on: `code` and `reason` go into the answer."""

    def __init__(self, code, reason):
        super().__init__(reason)
        self.code, self.reason = code, reason


# Processes.

def run_command(args, cwd=None, env=None, limit=COMMAND_LIMIT_S):
    """(exit code, output, error) of 1 command, by argument list. No command reads the terminal."""
    try:
        done = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=limit)
    except subprocess.TimeoutExpired:
        return 124, "", f"ran past {limit} s"
    except OSError as error:
        return 127, "", str(error)
    return done.returncode, done.stdout.strip(), done.stderr.strip()


def git(*args, cwd=None):
    code, out, err = run_command(["git", "-c", "user.name=afkv2 live", "-c", "user.email=afkv2-live@invalid",
                                  "-c", "core.autocrlf=false", *args], cwd=cwd)
    if code != 0:
        raise Failed("git-failed", f"git {' '.join(map(str, args[:3]))}: {err or out}")
    return out


def pause(seconds):
    time.sleep(seconds)


def flat(text):
    """`text` with every whitespace run removed: a match that survives the line wraps of a pane."""
    return "".join((text or "").split())


def same_path(a, b):
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


class Herdr:
    def __init__(self, env):
        self.binary = env.get("HERDR_BIN_PATH") or shutil.which("herdr")
        if env.get("HERDR_ENV") != "1" or not env.get("HERDR_WORKSPACE_ID") or not self.binary:
            raise Failed("outside-herdr", "the live rows run from a herdr pane with herdr on PATH")
        self.workspace = env["HERDR_WORKSPACE_ID"]

    def call(self, *args, limit=COMMAND_LIMIT_S):
        code, out, err = run_command([self.binary, *args], limit=limit)
        try:
            data = json.loads(out) if out else None
        except ValueError:
            data = None
        return code, data, err or out

    def ok(self, *args, limit=COMMAND_LIMIT_S):
        code, data, text = self.call(*args, limit=limit)
        if code != 0:
            raise Failed("herdr-failed", f"herdr {' '.join(args[:2])}: {text}")
        return (data or {}).get("result") or {}

    def panes(self, tab):
        return [pane for pane in self.ok("pane", "list", "--workspace", self.workspace).get("panes", [])
                if pane.get("tab_id") == tab]

    def agent(self, name):
        code, data, _ = self.call("agent", "get", name)
        return ((data or {}).get("result") or {}).get("agent") if code == 0 else None

    def read(self, pane, lines=200, source="recent-unwrapped"):
        code, out, err = run_command([self.binary, "pane", "read", pane, "--source", source, "--lines", str(lines)])
        return out if code == 0 else ""


# The world of 1 run.

class World:
    """The scratch folder, the panes and the files of 1 run; `clean_up` undoes each of them."""

    def __init__(self, row, env, stamp):
        self.row, self.env, self.stamp = row, env, stamp
        self.herdr = Herdr(env)
        base = Path(tempfile.gettempdir()) / SCRATCH_PREFIX
        self.results = base / "results.jsonl"
        self.root = base / f"{row}-{stamp}"
        if any(char.isspace() for char in str(self.root)):
            raise Failed("bad-input", f"the scratch folder {self.root} holds a space; shell panes need a plain path")
        self.root.mkdir(parents=True)
        self.tabs, self.main_panes, self.record, self.original = [], [], None, None
        self.seen = {}
        self.python = Path(sys.executable)

    # The data folder and the install record.

    def real_data(self):
        local = self.env.get("LOCALAPPDATA")
        return (Path(local) if local else Path.home() / ".local" / "share") / "afkv2"

    def put_back_record(self, data):
        """Put back a backup that a killed run left."""
        backup = data / RECORD_BACKUP
        if backup.is_file():
            (data / "install.txt").write_bytes(backup.read_bytes())
            backup.unlink()

    def use_real_record(self, source):
        """Add `source <D-SRC>` to the real install record; `clean_up` puts the original bytes back."""
        data = self.real_data()
        self.put_back_record(data)
        record = data / "install.txt"
        self.original = record.read_bytes() if record.is_file() else None
        if self.original is None:
            raise Failed("no-install-record", f"{record} is absent: run /afkv2:setup first")
        (data / RECORD_BACKUP).write_bytes(self.original)
        lines = [line for line in self.original.decode("utf-8").splitlines() if line.partition(" ")[0] != "source"]
        if not any(line.partition(" ")[0] == "python" for line in lines):
            lines.append(f"python {self.python}")
        record.write_text("\n".join([*lines, f"source {source}"]) + "\n", encoding="utf-8")
        self.record = record

    def scratch_record(self, source=None):
        """A scratch LOCALAPPDATA whose install record has the python line and, when given, the source line."""
        local = self.root / "local"
        (local / "afkv2").mkdir(parents=True, exist_ok=True)
        lines = [f"installed {time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())}", f"python {self.python}"]
        if source is not None:
            lines.append(f"source {source}")
        (local / "afkv2" / "install.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return local

    # The repositories.

    def make_work(self, folder):
        """D-WORK: git init, 1 committed README.md, no remote."""
        folder.mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=folder)
        (folder / "README.md").write_text("# df-work\n", encoding="utf-8")
        git("add", "README.md", cwd=folder)
        git("commit", "-q", "-m", "init", cwd=folder)
        return folder

    def make_source(self, folder):
        """D-SRC: a local clone of this build at HEAD, the base branch verify/df-base, and no remote."""
        head = git("rev-parse", "HEAD", cwd=AFKV2)
        branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=AFKV2)
        folder.parent.mkdir(parents=True, exist_ok=True)
        git("clone", "-q", "--single-branch", "--branch", branch, str(PLUGIN_REPOSITORY), str(folder))
        git("checkout", "-q", head, cwd=folder)
        git("checkout", "-q", "-B", branch, cwd=folder)
        git("branch", BASE, head, cwd=folder)
        git("remote", "remove", "origin", cwd=folder)
        return folder

    # Panes and agents.

    def open_tab(self, cwd, env=None):
        args = ["tab", "create", "--workspace", self.herdr.workspace, "--cwd", str(cwd), "--label",
                f"df-live-{self.row}", "--no-focus"]
        for key, value in (env or {}).items():
            args += ["--env", f"{key}={value}"]
        result = self.herdr.ok(*args)
        tab, pane = (result.get("tab") or {}).get("tab_id"), (result.get("root_pane") or {}).get("pane_id")
        if not tab or not pane:
            raise Failed("herdr-failed", f"tab create answered no tab or pane id: {result}")
        self.tabs.append(tab)
        self.main_panes.append(pane)
        return tab, pane

    def start_main(self, harness, pane, source):
        """Start the main agent as the developer would, in auto mode, and accept a folder trust dialog."""
        name = f"dfmain-{secrets.token_hex(2)}"
        if harness == "claude":
            args = ["--plugin-dir", str(source / "afkv2"), "--permission-mode", "auto"]
        else:
            args = ["--approve-for-me"]
        code, _, text = self.herdr.call("agent", "start", name, "--kind", harness, "--pane", pane, "--timeout",
                                        str(AGENT_READY_MS), "--", *args, limit=AGENT_READY_MS // 1000 + 30)
        if code != 0:
            for _ in range(2):  # a trust dialog of a new folder: the developer accepts it
                screen = self.herdr.read(pane, 40, "visible")
                if "trust" not in screen.lower():
                    break
                self.herdr.call("pane", "send-keys", pane, "enter")
                pause(5)
            if not self.wait_status(name, ("idle", "done"), 60):
                raise Failed("main-not-ready", f"the {harness} main agent did not get ready: {text}")
        self.seen["main_agent"] = {"name": name, "harness": harness, "args": args}
        return name

    def status(self, name):
        agent = self.herdr.agent(name)
        return agent.get("agent_status") if agent else None

    def wait_status(self, name, wanted, limit, watch=None):
        """Poll until the agent shows a wanted status; `watch` collects every status seen."""
        end = time.monotonic() + limit
        while time.monotonic() < end:
            now = self.status(name)
            if watch is not None:
                watch.append(now)
            if now in wanted:
                return now
            pause(POLL_S)
        return None

    def prompt(self, name, text):
        code, _, out = self.herdr.call("agent", "prompt", name, text, "--wait", "--until", "working", "--timeout",
                                       "30000", limit=60)
        self.seen.setdefault("prompts", []).append({"to": name, "text": text, "exit": code, "answer": out[:300]})
        return code

    def turn(self, name, text, limit=TURN_LIMIT_S, watch=None):
        """Give 1 developer turn and wait until the agent waits for input again."""
        self.prompt(name, text)
        pause(POLL_S)
        return self.wait_status(name, ("idle", "done", "blocked"), limit, watch)

    def afkv2_agent(self, tab):
        agents = self.herdr.ok("agent", "list").get("agents", [])
        return next((agent for agent in agents if agent.get("tab_id") == tab
                     and str(agent.get("name") or "").startswith("dogfood-")), None)

    def state(self, data, main_pane):
        safe = "".join(char if char.isascii() and (char.isalnum() or char in "_-") else "_" for char in main_pane)
        path = data / f"dogfood-{safe}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    # The end.

    def keep_screens(self, folder):
        for tab in self.tabs:
            for pane in self.herdr.panes(tab):
                text = self.herdr.read(pane["pane_id"], 400)
                (folder / f"pane-{pane['pane_id'].replace(':', '_')}.txt").write_text(text, encoding="utf-8")

    def clean_up(self):
        """Undo each thing this run made; 1 entry per item."""
        done = []

        def step(item, name, action):
            try:
                action()
                done.append({"item": item, "name": str(name), "result": "removed"})
            except Exception as error:  # every item is tried, also after another one failed
                done.append({"item": item, "name": str(name), "result": "failed", "reason": f"{type(error).__name__}: {error}"})

        for tab in self.tabs:
            step("herdr tab", tab, lambda tab=tab: self._close_tab(tab))
        data = self.real_data()
        for pane in self.main_panes:
            safe = "".join(char if char.isascii() and (char.isalnum() or char in "_-") else "_" for char in pane)
            for path in (data / f"dogfood-{safe}.json", data / f"dogfood-{safe}"):
                if path.exists():
                    step("session state", path, lambda path=path: _remove(path))
        if self.record is not None:
            step("install record", self.record, lambda: self._restore_record())
        step("scratch folder", self.root, lambda: _remove(self.root))
        return done

    def _close_tab(self, tab):
        code, _, text = self.herdr.call("tab", "close", tab)
        if code != 0 and "not_found" not in text:
            raise Failed("herdr-failed", f"tab close {tab}: {text}")
        pause(2)
        left = [pane["pane_id"] for pane in self.herdr.panes(tab)]
        if left:
            raise Failed("herdr-failed", f"tab {tab} still holds panes {left}")

    def _restore_record(self):
        self.record.write_bytes(self.original)
        (self.record.parent / RECORD_BACKUP).unlink(missing_ok=True)
        if self.record.read_bytes() != self.original:
            raise Failed("record-changed", f"{self.record} differs from its original bytes")


def _remove(path):
    def writable(function, name, _):
        os.chmod(name, stat.S_IWRITE)
        function(name)

    for attempt in range(5):  # a closed agent can hold a file for a moment
        try:
            if Path(path).is_dir():
                shutil.rmtree(path, onerror=writable)
            elif Path(path).exists():
                Path(path).unlink()
            return
        except OSError:
            if attempt == 4:
                raise
            pause(3)


# The rows.

def check(seen, name, holds, saw):
    seen.setdefault("checks", []).append({"then": name, "holds": bool(holds), "saw": saw})
    return bool(holds)


def refusal_row(world, gone):
    """VR-007 (no source line) and VR-008 (a source line whose path no longer exists): start from a shell pane."""
    source = None
    if gone:
        source = world.root / "gone-src"
        source.mkdir()
        source.rmdir()
    local = world.scratch_record(source)
    ask = world.root / "ask.txt"
    ask.write_text(ASK_WE01, encoding="utf-8")
    out, token = world.root / "start.json", secrets.token_hex(6)
    runner = world.root / "start_once.py"
    runner.write_text(
        "import json, subprocess, sys\n"
        f"done = subprocess.run([sys.executable, {str(AFKV2.parent / DOGFOOD / 'scripts' / 'dogfood.py')!r}, 'start', "
        f"'--ask-file', {str(ask)!r}], capture_output=True, text=True, encoding='utf-8')\n"
        f"open({str(out)!r}, 'w', encoding='utf-8').write(json.dumps({{'exit': done.returncode, 'stdout': done.stdout, "
        "'stderr': done.stderr}))\n"
        f"print('DFLIVE-' + {token[:6]!r} + '-' + {token[6:]!r})\n", encoding="utf-8")
    tab, pane = world.open_tab(world.root, {"LOCALAPPDATA": str(local)})
    pause(3)
    before = sorted(item["pane_id"] for item in world.herdr.panes(tab))
    world.herdr.ok("pane", "run", pane, f"{world.python.as_posix()} {runner.as_posix()}")
    world.herdr.call("pane", "wait-output", pane, "--match", f"DFLIVE-{token[:6]}-{token[6:]}", "--timeout", "90000",
                     limit=120)
    after = sorted(item["pane_id"] for item in world.herdr.panes(tab))
    try:
        result = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Failed("no-answer", f"dogfood.py start wrote no answer; the pane shows: {world.herdr.read(pane, 30)[-800:]}")
    lines = result["stdout"].strip().splitlines()
    answer = json.loads(lines[0]) if len(lines) == 1 else None
    seen = world.seen
    seen.update(start=result, panes_before=before, panes_after=after)
    error = (answer or {}).get("error") or {}
    code, words = ("source-broken", "setup") if gone else ("no-source", "/afkv2:setup")
    holds = [check(seen, "1 JSON answer", answer is not None, result["stdout"][:400]),
             check(seen, f"code {code}", error.get("code") == code, error.get("code")),
             check(seen, f"reason names {words}", words in (error.get("reason") or ""), error.get("reason")),
             check(seen, "no new pane", before == after, {"before": before, "after": after}),
             check(seen, "no state file", not list((local / "afkv2").glob("dogfood-*.json")),
                   sorted(path.name for path in (local / "afkv2").iterdir()))]
    if not gone:
        holds.append(check(seen, "exit 1", result["exit"] == 1, result["exit"]))
    return all(holds)


def open_session(world, harness, work_parent=None):
    """VR-001 and VR-002 as the Given of later rows: the main agent runs the skill with the WE-01 ask, and the afkv2
    pane opens. Answers (tab, main pane, main agent, afkv2 agent, holds)."""
    work = world.make_work((work_parent or world.root) / "df-work")
    source = world.make_source(world.root / "df-src")
    world.seen.update(work=str(work), source=str(source))
    world.use_real_record(source)
    tab, main_pane = world.open_tab(work)
    main = world.start_main(harness, main_pane, source)
    if harness == "claude":
        text = f"/afkv2:dogfood {ASK_WE01}"
    else:
        text = f"Use the dogfood skill in {source / DOGFOOD / 'SKILL.md'} with this ask: {ASK_WE01}"
    statuses = []
    started = time.monotonic()
    world.prompt(main, text)
    afkv2 = None
    while time.monotonic() - started < START_LIMIT_S + 60 and afkv2 is None:
        statuses.append(world.status(main))
        afkv2 = world.afkv2_agent(tab)
        if afkv2 is None:
            pause(POLL_S)
    opened_s = round(time.monotonic() - started, 1)
    seen = world.seen
    holds = [check(seen, f"the afkv2 pane opens within {START_LIMIT_S} s", afkv2 is not None and opened_s <= START_LIMIT_S,
                   {"seconds": opened_s, "agent": afkv2 and afkv2.get("name")})]
    if afkv2 is None:
        return tab, main_pane, main, None, False
    name, pane = afkv2["name"], afkv2["pane_id"]
    holds.append(check(seen, "the agent is dogfood-<4 hex>", re.fullmatch(r"dogfood-[0-9a-f]{4}", name), name))
    got = world.herdr.agent(name) or {}
    holds.append(check(seen, "herdr agent get: working folder D-SRC", same_path(got.get("cwd", ""), source), got.get("cwd")))
    holds.append(check(seen, "beside the main pane, in its tab", got.get("tab_id") == tab and pane != main_pane,
                       {"tab": got.get("tab_id"), "pane": pane}))
    back = world.wait_status(main, ("idle", "done", "blocked"), TURN_LIMIT_S, statuses)
    holds.append(check(seen, "the main agent hands the turn back", back in ("idle", "done"), back))
    if harness == "codex":
        holds.append(check(seen, "no approval prompt blocks the main agent", "blocked" not in statuses,
                           sorted(set(map(str, statuses)))))
    screen = world.herdr.read(pane, 300)
    holds.append(check(seen, "the first prompt holds the role line and the ask",
                       flat(ROLE_LINE) in flat(screen) and flat(ASK_WE01) in flat(screen), screen[-1500:]))
    return tab, main_pane, main, afkv2, all(holds)


def answer_base(world, afkv2, watch=None):
    """The afkv2 agent asks for the base: the developer gives verify/df-base."""
    asked = world.wait_status(afkv2["name"], ("idle", "done", "blocked"), TURN_LIMIT_S, watch)
    screen = world.herdr.read(afkv2["pane_id"], 200)
    world.prompt(afkv2["name"], f"Use {BASE} as the integration branch.")
    return asked, screen


def row_live(world, row):
    harness = "codex" if row == "VR-002" else "claude"
    tab, main_pane, main, afkv2, opened = open_session(world, harness)
    seen = world.seen
    if row in ("VR-001", "VR-002") or afkv2 is None:
        return opened
    data = world.real_data()
    if row == "VR-011":
        asked = world.wait_status(afkv2["name"], ("idle", "done", "blocked"), TURN_LIMIT_S)
        screen = world.herdr.read(afkv2["pane_id"], 200)
        before = (world.state(data, main_pane) or {}).get("worktrees")
        holds = [check(seen, "the afkv2 agent waits for the developer", asked in ("idle", "done"), asked),
                 check(seen, f"it asks which integration branch and suggests {SUGGESTED_BASE}",
                       SUGGESTED_BASE in screen and "?" in screen[-3000:], screen[-1500:]),
                 check(seen, "no worktree before the answer", before == [], before)]
        world.prompt(afkv2["name"], f"Use {BASE} as the integration branch.")
        worktrees = wait_worktree(world, data, main_pane, "small")
        holds.append(check(seen, "worktree runs after the answer", worktrees, worktrees))
        return all(holds)
    statuses = []
    asked, _ = answer_base(world, afkv2, statuses)
    if row == "VR-010":
        worktree = wait_worktree(world, data, main_pane, "small")
        branch = (worktree or {}).get("branch", "")
        screen = wait_screen(world, afkv2["pane_id"], "small-change")
        holds = [check(seen, "a small-asks worktree on feat/afkv2-df-<yyyymmdd-hhmm>",
                       worktree and SMALL_BRANCH.fullmatch(branch), worktree),
                 check(seen, f"its branch is cut from {BASE}", worktree and _cut_from(world, branch), branch),
                 check(seen, "the afkv2 pane shows /afkv2:small-change", screen is not None,
                       (screen or world.herdr.read(afkv2["pane_id"], 120))[-1500:])]
        return all(holds)
    if row == "VR-003":
        world.wait_status(afkv2["name"], ("working",), 60)
        started = time.monotonic()
        world.prompt(main, f"/afkv2:dogfood {ASK_WE02_2}")
        counts, shown = [], None
        while time.monotonic() - started < EXISTING_LIMIT_S + 60 and shown is None:
            counts.append(len(world.herdr.panes(tab)))
            screen = world.herdr.read(afkv2["pane_id"], 200)
            if flat(FORWARD_LINE) in flat(screen) and flat(ASK_WE02_2) in flat(screen):
                shown = round(time.monotonic() - started, 1)
            else:
                pause(POLL_S)
        world.wait_status(main, ("idle", "done", "blocked"), TURN_LIMIT_S)
        counts.append(len(world.herdr.panes(tab)))
        main_screen = world.herdr.read(main_pane, 200)
        holds = [check(seen, f"the afkv2 pane shows ask 2 within {EXISTING_LIMIT_S} s",
                       shown is not None and shown <= EXISTING_LIMIT_S, shown),
                 check(seen, "the tab still holds 2 panes", set(counts) == {2}, counts),
                 check(seen, "start answers existing", "existing" in main_screen.lower(), main_screen[-1500:])]
        return all(holds)
    if row == "VR-004":
        screen = world.herdr.read(afkv2["pane_id"], 400, "recent")
        model = check(seen, "the pane shows Claude Opus at the highest effort",
                      "opus" in screen.lower() and re.search(r"\bmax\b", screen.lower()), screen[:1500])
        end, edit, shell = time.monotonic() + WORK_LIMIT_S, False, False
        while time.monotonic() < end and not (edit and shell):
            statuses.append(world.status(afkv2["name"]))
            text = world.herdr.read(afkv2["pane_id"], 400)
            edit = edit or bool(re.search(r"(Write|Edit|Update|Create)\(", text))
            shell = shell or bool(re.search(r"(Bash|PowerShell)\(", text))
            if not (edit and shell):
                pause(POLL_S)
        holds = [model,
                 check(seen, "a first file edit and a first shell command", edit and shell, {"edit": edit, "shell": shell}),
                 check(seen, "no approval dialog", "blocked" not in statuses, sorted(set(map(str, statuses))))]
        return all(holds)
    if row == "VR-009":
        world.wait_status(afkv2["name"], ("working",), 60)
        world.prompt(afkv2["name"], f"Drop the first ask. A feature ask replaces it: {ASK_FEATURE}")
        medium = wait_worktree(world, data, main_pane, "medium", TURN_LIMIT_S)
        if medium is None:  # the afkv2 agent asks for the ticket key
            world.wait_status(afkv2["name"], ("idle", "done", "blocked"), TURN_LIMIT_S)
            world.prompt(afkv2["name"], f"The ticket key is {TICKET}.")
            medium = wait_worktree(world, data, main_pane, "medium", TURN_LIMIT_S)
        branch = (medium or {}).get("branch", "")
        small = [item.get("branch") for item in (world.state(data, main_pane) or {}).get("worktrees", [])
                 if item.get("lane") == "small"]
        branches = git("branch", "--list", "--format=%(refname:short)", cwd=world.seen["source"]).splitlines()
        screen = wait_screen(world, afkv2["pane_id"], "grill-requirements")
        holds = [check(seen, "the afkv2 agent calls worktree --lane medium --branch <name>", medium, medium),
                 check(seen, "git branch in D-SRC shows a branch apart from the small-asks branch",
                       branch in branches and branch not in small, {"branches": branches, "small": small}),
                 check(seen, "the afkv2 pane shows /afkv2:grill-requirements", screen is not None,
                       (screen or world.herdr.read(afkv2["pane_id"], 120))[-1500:])]
        return all(holds)
    raise Failed("bad-input", f"no live flow for {row}")


def wait_worktree(world, data, main_pane, lane, limit=WORK_LIMIT_S):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        state = world.state(data, main_pane) or {}
        found = next((item for item in state.get("worktrees", []) if item.get("lane") == lane), None)
        if found:
            world.seen.setdefault("state", {})[lane] = state
            return found
        pause(POLL_S)
    return None


def wait_screen(world, pane, text, limit=WORK_LIMIT_S):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        screen = world.herdr.read(pane, 300)
        if text in screen:
            return screen
        pause(POLL_S)
    return None


def _cut_from(world, branch):
    code, _, _ = run_command(["git", "merge-base", "--is-ancestor", BASE, branch], cwd=world.seen["source"])
    return code == 0


def record_lines(path):
    try:
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line.partition(" ")[0] == "source"]
    except OSError:
        return []


def after_text(screen, typed):
    """The part of `screen` from the last line that holds `typed`: what came after a developer turn."""
    at = screen.rfind(typed)
    return screen[at:] if at >= 0 else screen


def setup_row(world, row):
    """VR-056, VR-065 (the suggested D-SRC is confirmed) and VR-057 (a linked worktree, then D-WORK, are refused)."""
    harness = "codex" if row == "VR-065" else "claude"
    seen = world.seen
    if row == "VR-057":
        work = world.make_work(world.root / "work" / "df-work")
        source = world.make_source(world.root / "elsewhere" / "df-src")
        linked = world.root / "elsewhere" / "df-src-linked"
        git("worktree", "add", "-q", "-b", "df-linked", str(linked), BASE, cwd=source)
    else:
        work = world.make_work(world.root / "df-work")
        source = world.make_source(world.root / "df-src")
    local = world.scratch_record()
    record = local / "afkv2" / "install.txt"
    seen.update(work=str(work), source=str(source), record=str(record))
    tab, pane = world.open_tab(work, {"LOCALAPPDATA": str(local)})
    main = world.start_main(harness, pane, source)
    if harness == "claude":
        ask = f"/afkv2:setup {SETUP_ONLY}"
    else:
        ask = f"Use the setup skill in {source / SETUP_SKILL}. {SETUP_ONLY}"
    statuses = []
    world.turn(main, ask, watch=statuses)
    first = world.herdr.read(pane, 300)
    if row == "VR-057":
        world.turn(main, f"No. The path is {linked}", watch=statuses)
        second = world.herdr.read(pane, 300)
        world.turn(main, f"The path is {work}", watch=statuses)
        third = world.herdr.read(pane, 300)
        tail2, tail3 = after_text(second, "No. The path is"), after_text(third, f"The path is {work.name}")
        holds = [check(seen, "setup asks for a path", "?" in first, first[-1500:]),
                 check(seen, "the linked worktree is not a main checkout",
                       re.search(r"not-main-checkout|not a main checkout|linked worktree", tail2, re.I), tail2[-1500:]),
                 check(seen, "D-WORK is not the plugin source",
                       re.search(r"not-plugin-source|not the plugin source", tail3, re.I), tail3[-1500:]),
                 check(seen, "the install record holds no source line", record_lines(record) == [], record_lines(record))]
        return all(holds)
    holds = [check(seen, "setup suggests the D-SRC path and asks to confirm or type another",
                   flat(str(source)).lower() in flat(first).lower() and "?" in first, first[-1500:])]
    world.turn(main, "Yes, use that path.", watch=statuses)
    holds.append(check(seen, "the install record holds source <D-SRC>",
                       [line.partition(" ")[2].strip() for line in record_lines(record)] == [str(source)],
                       record_lines(record)))
    if row == "VR-056":
        world.turn(main, f"/afkv2:setup {SETUP_ONLY}", watch=statuses)
        tail = after_text(world.herdr.read(pane, 400), "/afkv2:setup")
        asked = [line for line in tail.splitlines() if "?" in line and re.search(r"source|path|checkout", line, re.I)]
        holds.append(check(seen, "a second setup asks nothing about the source", not asked and len(record_lines(record)) == 1,
                           {"questions": asked, "record": record_lines(record)}))
    holds.append(check(seen, "no dialog blocked the session", "blocked" not in statuses, sorted(set(map(str, statuses)))))
    return all(holds)


def run_start_row(row, env=None, stamp=None):
    """Run 1 live plan row and answer its result: {"ok", "row", "passed", "seen", "cleanup"}."""
    env = dict(os.environ if env is None else env)
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + secrets.token_hex(2)
    if row not in ROWS:
        return {"ok": False, "row": row, "error": {"code": "bad-input", "reason": f"--row is {row!r}, not one of "
                                                                                 f"{', '.join(ROWS)}"}}
    world, answer = None, None
    started = time.monotonic()
    try:
        try:
            world = World(row, env, stamp)
            if row in ("VR-007", "VR-008"):
                passed = refusal_row(world, gone=row == "VR-008")
            elif row in ("VR-056", "VR-057", "VR-065"):
                passed = setup_row(world, row)
            else:
                passed = row_live(world, row)
            answer = {"ok": True, "row": row, "passed": bool(passed)}
        except Failed as failure:
            answer = {"ok": False, "row": row, "error": {"code": failure.code, "reason": failure.reason}}
        except Exception as error:
            answer = {"ok": False, "row": row, "error": {"code": "internal", "reason": f"{type(error).__name__}: {error}"}}
        if world is not None:
            evidence = Path(env["AFKV2_EVIDENCE"]) if env.get("AFKV2_EVIDENCE") else world.root.parent / f"{row}-{stamp}-screens"
            evidence.mkdir(parents=True, exist_ok=True)
            try:
                world.keep_screens(evidence)
            except Failed:
                pass
            answer["seen"] = world.seen
    finally:  # also on an interrupt: the tab, the state, the install record and the scratch folder go
        cleanup = world.clean_up() if world is not None else []
    answer["cleanup"] = cleanup
    answer["seconds"] = round(time.monotonic() - started, 1)
    if any(entry["result"] == "failed" for entry in cleanup):
        answer["ok"], answer["passed"] = False, False
        answer.setdefault("error", {"code": "cleanup-failed", "reason": "the end left items; delete them by hand"})
    if world is not None:
        _keep(world, env, answer)
    return answer


def _keep(world, env, answer):
    text = json.dumps(answer, indent=1)
    if env.get("AFKV2_EVIDENCE"):
        (Path(env["AFKV2_EVIDENCE"]) / f"{answer['row']}.json").write_text(text, encoding="utf-8")
    with open(world.results, "a", encoding="utf-8") as results:
        results.write(json.dumps({"stamp": world.stamp, "row": answer["row"], "passed": answer.get("passed", False),
                                  "error": answer.get("error"), "seconds": answer["seconds"]}) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dogfood_live_start.py")
    parser.add_argument("--row", required=True)
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        print(json.dumps({"ok": False, "error": {"code": "bad-input", "reason": "usage: --row VR-NNN"}}))
        return 2
    answer = run_start_row(args.row)
    print(json.dumps(answer, indent=1))
    if not answer["ok"] and (answer.get("error") or {}).get("code") == "bad-input":
        return 2
    return 0 if answer["ok"] and answer.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
