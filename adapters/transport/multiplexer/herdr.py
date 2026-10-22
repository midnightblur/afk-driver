"""The herdr tool of the multiplexer kind, as its recipe herdr.md states it.

`detect` says whether herdr is usable in this session. `Herdr` maps the six verbs to herdr commands: tabs
and panes for a start, `agent prompt` for a message, process kill then `pane close` for a stop. Every herdr
call has its own timeout inside the verb's budget, and a failure answers in the family's shapes.
"""
from __future__ import annotations

import hashlib
import json
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contract  # noqa: E402
import launch  # noqa: E402
import process  # noqa: E402
from contract import Answer, Deadline, Payload, bad, unavailable  # noqa: E402

RECIPE = "adapters/transport/multiplexer/herdr.md"
GRID = 4                                  # panes per tab, a 2 by 2 grid
READ_LINES = 2000
MARKER_LINES = 3                          # lines one marker window holds
MARKER_DEPTH = 16                         # last non-empty lines a marker records, one short hash each
HASH_HEX = 8
GONE = ("pane_not_found", "agent_not_found", "tab_not_found")
DIALOG_LINES = 6                          # a dialog's question sits a few lines above its last line
START_RESERVE_S = 40                     # left in the start budget after herdr's wait, for the checks and a cleanup


@dataclass
class Detection:
    tool: str
    status: str                           # usable, fixable, outside, broken or absent
    reason: str
    settings: list[dict] = field(default_factory=list)
    tabs: bool = True
    delivery: str = "agent-prompt"        # the one way herdr delivers into a pane
    contact_delivery: str = "inbox"       # agent prompt types into an input box, so the contact gets an inbox

    def as_dict(self) -> dict:
        return {"tool": self.tool, "status": self.status, "reason": self.reason, "settings": self.settings,
                "tabs": self.tabs, "delivery": self.delivery, "contact_delivery": self.contact_delivery,
                "recipe": RECIPE}


def detect(env: Mapping[str, str], harnesses: tuple[str, ...], *, which: Callable = shutil.which,
           run: Callable = subprocess.run, timeout: float = 10.0) -> Detection:
    """Usable means: herdr on PATH, this session inside a herdr pane, its server answering, and its
    agent-state integration current for every harness the run starts. Each herdr call waits `timeout` s."""
    binary = which("herdr", path=env.get("PATH"))
    if not binary:
        return Detection("herdr", "absent", "the herdr command is not on PATH")
    if env.get("HERDR_ENV") != "1" or not env.get("HERDR_PANE_ID"):
        return Detection("herdr", "outside",
                         "herdr is installed, but this session does not run inside a herdr pane")
    status = _plain(run, [binary, "status"], env, timeout)
    if status is None or "status: running" not in status:
        return Detection("herdr", "broken", "the herdr server of this session does not answer `herdr status`")
    integrations = _plain(run, [binary, "integration", "status"], env, timeout) or ""
    current = {line.split(":", 1)[0].strip() for line in integrations.splitlines()
               if ": current" in line}
    missing = [{"name": f"herdr integration for {h}", "fix": f"herdr integration install {h}"}
               for h in harnesses if h not in current]
    if missing:
        return Detection("herdr", "fixable", "herdr cannot report the state of "
                         + ", ".join(m["name"].rsplit(" ", 1)[1] for m in missing)
                         + " agents until its integration is installed", missing)
    return Detection("herdr", "usable", "herdr runs this session")


def _plain(run: Callable, argv: list[str], env: Mapping[str, str], timeout: float = 10.0) -> str | None:
    try:
        done = run(argv, capture_output=True, text=True, timeout=timeout, env=dict(env), check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


class HerdrError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class Herdr:
    def __init__(self, env: Mapping[str, str], binary: str = "herdr"):
        self.env = dict(env)
        self.binary = shutil.which(binary, path=self.env.get("PATH")) or binary

    # ---- one herdr call: JSON in the answer, a JSON error on failure
    def call(self, args: list[str], deadline: Deadline, cap: float = 30.0) -> dict:
        budget = min(cap, deadline.left())
        if budget <= 0:
            raise HerdrError("timeout", f"no time left in the {deadline.verb} budget")
        try:
            done = subprocess.run([self.binary, *args], capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=budget, env=self.env, check=False)
        except subprocess.TimeoutExpired:
            raise HerdrError("timeout", f"`herdr {' '.join(args[:2])}` took over {budget:.0f} s") from None
        except OSError as error:
            raise HerdrError("absent", str(error)) from None
        for text in (done.stdout, done.stderr):
            try:
                data = json.loads(text)
            except ValueError:
                continue
            if isinstance(data, dict) and "error" in data:
                error = data["error"] or {}
                raise HerdrError(error.get("code", "error"), error.get("message", ""))
            if done.returncode == 0 and isinstance(data, dict):
                return data.get("result", data)
        if done.returncode == 0:
            return {"text": done.stdout}          # `pane read` answers plain text, not JSON
        raise HerdrError("error", (done.stderr or done.stdout).strip()[:400])

    # ---- agent-start
    def agent_start(self, p: Payload, deadline: Deadline) -> dict:
        harness = p.choice("harness", launch.HARNESSES)
        name, label, cwd, tab = p.text("name"), p.text("label"), p.text("cwd"), p.text("tab")
        prompt, resume = p.text("prompt", False), p.text("resume", False)
        run = launch.interactive(harness, prompt, model=p.text("model", False), effort=p.text("effort", False),
                                 resume=resume, args=p.texts("args"))
        env = {**run.env, **p.mapping("env")}
        workspace, contact_tab = self.env.get("HERDR_WORKSPACE_ID"), self.env.get("HERDR_TAB_ID")
        if not workspace or not contact_tab:
            raise unavailable("this session does not run inside a herdr pane", recipe=RECIPE)
        pane, tab_id = self._open_pane(workspace, contact_tab, tab, cwd, env, deadline)
        try:
            self.call(["pane", "rename", pane, label], deadline)
            if resume and harness == "codex":
                self._resume_by_pane_run(pane, name, run, deadline)
            else:
                timeout = int(max(1000, min(300000, (deadline.left() - START_RESERVE_S) * 1000)))
                try:
                    self.call(["agent", "start", name, "--kind", run.binary, "--pane", pane,
                               "--timeout", str(timeout), "--", *run.args], deadline, cap=timeout / 1000 + 10)
                except HerdrError as error:
                    if error.code != "timeout" or not self._started(pane, run.binary, deadline):
                        raise
        except HerdrError as error:
            screen = self._screen_line(pane, deadline) if error.code == "agent_not_ready" else ""
            self._discard(pane, deadline)
            if error.code == "agent_not_ready":
                raise unavailable(f"a dialog blocks the agent's start: {screen}",
                                  dialog=True, recipe=RECIPE) from None
            if resume:
                raise unavailable(f"the resume of session {resume} failed: {error}", recipe=RECIPE) from None
            raise unavailable(f"herdr could not start the agent: {error}", recipe=RECIPE) from None
        pid = self._agent_pid(pane, deadline)
        return {"kind": "multiplexer", "tool": "herdr", "handle": pane, "pid": pid,
                "started_at": (process.creation_time(pid) if pid else None) or contract.now(),
                "pane_label": label, "agent_name": name, "session_id": self._session_id(pane, deadline),
                "tab_id": tab_id}

    def _open_pane(self, workspace: str, contact_tab: str, tab: str, cwd: str, env: dict,
                   deadline: Deadline) -> tuple[str, str]:
        """A pane in a tab of this step that has room, else in a new tab; never in the contact's tab."""
        flags = [arg for key, value in env.items() for arg in ("--env", f"{key}={value}")]
        try:
            tabs = self.call(["tab", "list", "--workspace", workspace], deadline).get("tabs", [])
        except HerdrError as error:
            raise unavailable(f"herdr could not list the tabs for tab {tab!r}: {error}", tab=tab) from None
        ours = [t for t in tabs if t.get("tab_id") != contact_tab and _tab_number(t.get("label", ""), tab)]
        room = next((t for t in ours if int(t.get("pane_count", GRID)) < GRID), None)
        if room is None:
            label = tab if not ours else f"{tab} {max(_tab_number(t.get('label', ''), tab) for t in ours) + 1}"
            try:
                made = self.call(["tab", "create", "--workspace", workspace, "--cwd", cwd, "--label", label,
                                  "--no-focus", *flags], deadline)
                return made["root_pane"]["pane_id"], made["tab"]["tab_id"]
            except (HerdrError, KeyError, TypeError) as error:
                raise unavailable(f"herdr could not make tab {label!r}: {error}", tab=label) from None
        try:
            panes = [q["pane_id"] for q in self.call(["pane", "list", "--workspace", workspace],
                                                     deadline).get("panes", [])
                     if q.get("tab_id") == room["tab_id"]]
            target, direction = _grid_split(panes)
            made = self.call(["pane", "split", target, "--direction", direction, "--cwd", cwd, "--no-focus",
                              *flags], deadline)
            return made["pane"]["pane_id"], room["tab_id"]
        except (HerdrError, KeyError, TypeError, IndexError) as error:
            raise unavailable(f"herdr could not add a pane to tab {room.get('label')!r}: {error}",
                              tab=room.get("label")) from None

    def _resume_by_pane_run(self, pane: str, name: str, run: launch.Launch, deadline: Deadline) -> None:
        """Codex resume through `herdr agent start` left no pane; typed by `pane run`, it works."""
        shell = self._shell_name(pane, deadline)
        line = _command_line(run.argv(), powershell="pwsh" in shell or "powershell" in shell)
        self.call(["pane", "run", pane, line], deadline)
        while deadline.left() > START_RESERVE_S:
            try:
                agent = self.call(["agent", "get", pane], deadline).get("agent", {})
                if agent.get("agent") == run.binary and agent.get("agent_status") in ("idle", "done"):
                    self.call(["agent", "rename", pane, name], deadline)
                    return
                if agent.get("agent_status") == "blocked":
                    raise HerdrError("agent_not_ready", "blocked at start")
            except HerdrError as error:
                if error.code not in GONE:
                    raise
            time.sleep(1)
        raise HerdrError("timeout", "the resumed agent never became ready")

    def _started(self, pane: str, binary: str, deadline: Deadline) -> bool:
        """herdr waits for an idle agent, so a launch prompt's first turn can outlast the wait; a working
        agent has started. A blocked one is a dialog."""
        try:
            agent = self.call(["agent", "get", pane], deadline).get("agent", {})
        except HerdrError:
            return False
        if agent.get("agent") == binary and agent.get("agent_status") == "blocked":
            raise HerdrError("agent_not_ready", "blocked at start")
        return agent.get("agent") == binary and agent.get("agent_status") in ("working", "idle", "done")

    def _shell_name(self, pane: str, deadline: Deadline) -> str:
        try:
            info = self.call(["pane", "process-info", "--pane", pane], deadline).get("process_info", {})
            names = [proc.get("name", "") for proc in info.get("foreground_processes", [])]
            return " ".join(names).lower()
        except HerdrError:
            return ""

    def _agent_pid(self, pane: str, deadline: Deadline) -> int | None:
        try:
            info = self.call(["pane", "process-info", "--pane", pane], deadline).get("process_info", {})
        except HerdrError:
            return None
        procs = info.get("foreground_processes") or []
        return procs[0].get("pid") if procs else info.get("shell_pid")

    def _session_id(self, pane: str, deadline: Deadline) -> str:
        try:
            agent = self.call(["agent", "get", pane], deadline).get("agent", {})
        except HerdrError:
            return ""
        return (agent.get("agent_session") or {}).get("value", "")

    def _screen_line(self, pane: str, deadline: Deadline) -> str:
        try:
            text = self.call(["pane", "read", pane, "--source", "visible"], deadline).get("text", "")
        except HerdrError:
            return "the screen could not be read"
        lines = [line.strip() for line in str(text).splitlines() if line.strip()]
        return " / ".join(lines[-DIALOG_LINES:])[:400] if lines else "the screen is empty"

    def _discard(self, pane: str, deadline: Deadline) -> None:
        pid = self._agent_pid(pane, deadline)
        if pid:
            process.kill_tree(pid, force=True, wait_s=min(10.0, deadline.left()))
        self._close(pane, deadline)

    # ---- agent-send
    def agent_send(self, p: Payload, deadline: Deadline) -> dict:
        handle, text = p.text("handle"), p.text("text")
        try:
            self.call(["agent", "prompt", handle, text], deadline)
        except HerdrError as error:
            if error.code in GONE:
                raise unavailable(f"the receiver's pane {handle} is gone", receiver_gone=True) from None
            raise unavailable(f"herdr could not deliver into pane {handle}: {error}") from None
        return {"delivered": True, "at": contract.now(), "way": "agent-prompt"}

    # ---- agent-status
    def agent_status(self, p: Payload, deadline: Deadline) -> dict:
        handle = p.text("handle")
        try:
            agent = self.call(["agent", "get", handle], deadline).get("agent", {})
            return {"alive": True, "state": agent.get("agent_status", "unknown"), "since": None}
        except HerdrError as error:
            if error.code not in GONE:
                raise unavailable(f"herdr could not read pane {handle}: {error}") from None
        try:
            self.call(["pane", "get", handle], deadline)
            return {"alive": False, "state": "exited", "since": None}
        except HerdrError as error:
            if error.code in GONE:
                return {"alive": False, "state": "gone", "since": None}
            raise unavailable(f"herdr could not read pane {handle}: {error}") from None

    # ---- agent-read
    def agent_read(self, p: Payload, deadline: Deadline) -> dict:
        handle, marker = p.text("handle"), p.text("since_marker", False)
        if marker is not None and not _is_marker(marker):
            raise bad(p.verb, f"field `since_marker`: {marker!r} is not a marker this kind gave")
        try:
            result = self.call(["pane", "read", handle, "--source", "recent-unwrapped",
                                "--lines", str(READ_LINES)], deadline)
        except HerdrError as error:
            if error.code in GONE:
                raise bad(p.verb, f"field `handle`: pane {handle} is gone") from None
            raise unavailable(f"herdr could not read pane {handle}: {error}") from None
        lines = str(result.get("text", "")).splitlines()
        start, complete = 0, True
        if marker:
            found = _after(lines, marker)
            start, complete = (found, True) if found is not None else (0, False)
        return {"text": "\n".join(lines[start:]), "marker": _marker(lines), "complete": complete}

    # ---- agent-stop
    def agent_stop(self, p: Payload, deadline: Deadline) -> dict:
        pid, handle, force = p.integer("pid", False), p.text("handle", False), p.boolean("force")
        answer = process.stop(pid, force=force, wait_s=min(20.0, max(1.0, deadline.left() - 20)),
                              none="pane close" if handle else "nothing to kill", with_kin=True)
        if handle:
            closed = self._close(handle, deadline)
            answer.update({"pane_closed": closed, "pane_id": handle})
            if pid is None and not closed:          # nothing was killed, and the agent runs on in its pane
                answer.pop("method", None)
                answer.update({"stopped": False, "survivors": [],
                               "reason": f"no process id was given and pane {handle} did not close"})
        return answer

    def _close(self, pane: str, deadline: Deadline) -> bool:
        """Close the pane, then its tab when no pane is left; a pane already gone counts as closed."""
        try:
            tab = self.call(["pane", "get", pane], deadline).get("pane", {}).get("tab_id")
        except HerdrError as error:
            return error.code in GONE
        try:
            self.call(["pane", "close", pane], deadline)
        except HerdrError as error:
            if error.code not in GONE:
                return False
        if tab and tab != self.env.get("HERDR_TAB_ID"):
            try:
                left = self.call(["tab", "get", tab], deadline).get("tab", {}).get("pane_count", 0)
                if int(left) == 0:
                    self.call(["tab", "close", tab], deadline)
            except HerdrError:
                pass                        # a tab herdr already closed with its last pane
        return True

    # ---- agent-list
    def agent_list(self, p: Payload, deadline: Deadline) -> dict:
        prefix = p.text("prefix")
        try:
            agents = self.call(["agent", "list"], deadline).get("agents", [])
        except HerdrError as error:
            raise unavailable(f"herdr could not list agents: {error}") from None
        return {"agents": [{"agent_name": a["name"], "pane_id": a.get("pane_id", "")} for a in agents
                           if str(a.get("name", "")).startswith(prefix)]}


def _tab_number(label: str, tab: str) -> int:
    """1 for the step's first tab, N for its successor `<tab> N`, 0 for another step's tab."""
    if label == tab:
        return 1
    head, _, tail = label.rpartition(" ")
    return int(tail) if head == tab and tail.isdigit() else 0


def _grid_split(panes: list[str]) -> tuple[str, str]:
    """Which pane to split so a tab fills as a 2 by 2 grid."""
    count = len(panes)
    if count == 1:
        return panes[0], "right"
    if count == 2:
        return panes[0], "down"
    return panes[1], "down"


def _command_line(argv: list[str], powershell: bool) -> str:
    if not powershell:
        return shlex.join(argv)
    return "& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in argv)


def _line_hash(line: str) -> str:
    return hashlib.sha1(line.encode("utf-8")).hexdigest()[:HASH_HEX]


def _marker(lines: list[str]) -> str:
    """`m`, then a short hash of each of the last non-empty lines, oldest first."""
    tail = [line for line in lines if line.strip()][-MARKER_DEPTH:]
    return "m" + "".join(_line_hash(line) for line in tail)


def _is_marker(text: str) -> bool:
    body = text[1:]
    return (text[:1] == "m" and len(body) % HASH_HEX == 0 and len(body) <= MARKER_DEPTH * HASH_HEX
            and all(c in "0123456789abcdef" for c in body))


def _after(lines: list[str], marker: str) -> int | None:
    """The index where the text after the marker starts. A TUI keeps a footer under new output, so each
    split of the marked lines into body and footer is tried; marked lines that still follow the body's
    window are old text, and the earliest start wins."""
    old = [marker[i:i + HASH_HEX] for i in range(1, len(marker), HASH_HEX)]
    filled = [(i, line) for i, line in enumerate(lines) if line.strip()]
    new = [_line_hash(line) for _, line in filled]
    if not old:
        return 0
    best = None
    for footer in range(len(old)):
        window = old[max(0, len(old) - footer - MARKER_LINES):len(old) - footer]
        for end in range(len(new), len(window) - 1, -1):
            if new[end - len(window):end] == window:
                rest, kept = old[len(old) - footer:], 0
                while kept < len(rest) and end + kept < len(new) and new[end + kept] == rest[kept]:
                    kept += 1
                best = end + kept if best is None else min(best, end + kept)
                break
    if best is None or (best == len(new) and new[-len(old):] != old):
        return None                 # only a footer matched: the marked body is gone, so nothing is known new
    return filled[best - 1][0] + 1 if best else 0
