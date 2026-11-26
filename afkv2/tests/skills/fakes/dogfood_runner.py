"""The in-process fake of herdr and git for the dogfood tests, shaped as `HerdrRunner` of the proposer engine.

It keeps a small model: panes, agents, prompts, keys, branches and worktrees. A test can replace any answer with
`answer(words, result)`, run a check at a call with `on(words, fn)`, and read every call in `calls`. A command that
the model does not know fails the test. It starts no process.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "skills" / "use-lavish" / "scripts"))

from proposer_engine import HerdrRunner  # noqa: E402

HERDR = "C:/fake/herdr/herdr.exe"
AGENT_NAME = re.compile(r"[a-z][a-z0-9_-]{0,31}")


def herdr_error(code, message=""):
    """The answer of a refused herdr command: exit 1, the error JSON on stderr."""
    return 1, "", json.dumps({"error": {"code": code, "message": message or code}})


def _ok(result):
    return 0, json.dumps({"result": result}), ""


def _option(args, name):
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


class DogfoodFakeRunner(HerdrRunner):
    """herdr and git in memory. `env` is the environment of the caller; the platform is pinned to `platform`."""

    def __init__(self, env, *, platform="win32", herdr=HERDR, main_pane=None, branches=("feat/afkv2",)):
        super().__init__()
        self.env = dict(env)
        self.platform = platform
        self.herdr = herdr
        self.calls = []
        self.panes = {}
        self.agents = {}
        self.prompts = []
        self.keys = []
        self.started = []
        self.sleeps = []
        self.screens = {}
        self.branches = set(branches)
        self.worktrees = {}
        self.linked = set()
        self._rules = []
        self._hooks = []
        self._next = 100
        main = main_pane or self.env.get("HERDR_PANE_ID")
        if main:
            self.add_pane(main, kind="claude")

    # The set-up a test uses.

    def add_pane(self, pane, *, cwd="", kind=None, name=None, status="idle"):
        """A pane; with `kind`, an agent runs in it, named or not."""
        self.panes[pane] = {"cwd": cwd, "kind": kind, "name": name, "status": status, "blocked": False,
                            "stall": False}
        if name:
            self.agents[name] = pane
        return pane

    def add_agent(self, name, pane=None):
        """A live named agent in its own pane."""
        pane = pane or self._new_pane_id()
        return self.add_pane(pane, kind="claude", name=name)

    def answer(self, words, result, times=None):
        """Answer each call whose command words start with `words` by `result`: `(code, out, err)` or a function of
        the argv. `times` limits the answers; then the model answers again."""
        self._rules.append({"words": tuple(words), "result": result, "times": times})

    def on(self, words, fn):
        """Call `fn(argv)` before each call whose command words start with `words`."""
        self._hooks.append((tuple(words), fn))

    def calls_of(self, *words):
        return [argv for argv in self.calls if self._words(argv)[:len(words)] == list(words)]

    # The HerdrRunner shape.

    def which(self, name):
        return {"herdr": self.herdr, "git": "git"}.get(name)

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def run(self, argv, timeout=None):
        argv = [str(part) for part in argv]
        self.calls.append(argv)
        words = self._words(argv)
        for prefix, fn in self._hooks:
            if words[:len(prefix)] == list(prefix):
                fn(argv)
        for rule in self._rules:
            if words[:len(rule["words"])] == list(rule["words"]) and rule["times"] != 0:
                if rule["times"]:
                    rule["times"] -= 1
                result = rule["result"]
                return result(argv) if callable(result) else result
        if argv[0] == self.herdr:
            return self._herdr(argv[1:])
        if argv[0] == "git":
            return self._git(argv[1:])
        if argv[0] == "reg":
            return 1, "", "ERROR: The system was unable to find the specified registry key or value."
        raise AssertionError(f"the fake runner has no answer for {argv}")

    def _words(self, argv):
        if argv[0] == "git":
            rest = argv[1:]
            while rest[:1] == ["-C"]:
                rest = rest[2:]
            return ["git", *rest]
        return argv[1:] if argv[0] == self.herdr else argv

    # herdr.

    def _new_pane_id(self):
        self._next += 1
        return f"w9:p{self._next}"

    def _target(self, target):
        """The pane of an agent named `target`, or of the pane `target` when an agent runs in it."""
        if target in self.agents:
            return self.agents[target]
        if target in self.panes and self.panes[target]["kind"]:
            return target
        return None

    def _agent_info(self, pane):
        entry = self.panes[pane]
        info = {"agent": entry["kind"], "pane_id": pane, "agent_status": entry["status"], "cwd": entry["cwd"]}
        if entry["name"]:
            info["name"] = entry["name"]
        return info

    def _herdr(self, args):
        group, verb, rest = (args + ["", ""])[0], (args + ["", ""])[1], args[2:]
        handler = getattr(self, f"_{group}_{verb.replace('-', '_')}", None)
        if handler is None:
            raise AssertionError(f"the fake herdr has no command {group} {verb}")
        return handler(rest)

    def _pane_split(self, rest):
        source = _option(rest, "--pane") or (self.env.get("HERDR_PANE_ID") if "--current" in rest else None)
        if source is None and rest and not rest[0].startswith("--"):
            source = rest[0]
        if source not in self.panes:
            return herdr_error("pane_not_found", f"pane {source} not found")
        pane = self.add_pane(self._new_pane_id(), cwd=_option(rest, "--cwd") or "")
        return _ok({"pane": {"pane_id": pane, "cwd": self.panes[pane]["cwd"]}})

    def _pane_close(self, rest):
        entry = self.panes.pop(rest[0], None)
        if entry is None:
            return herdr_error("pane_not_found", f"pane {rest[0]} not found")
        if entry["name"]:
            self.agents.pop(entry["name"], None)
        return _ok({"closed": rest[0]})

    def _pane_get(self, rest):
        if rest[0] not in self.panes:
            return herdr_error("pane_not_found", f"pane {rest[0]} not found")
        return _ok({"pane": {"pane_id": rest[0], "agent_status": self.panes[rest[0]]["status"]}})

    def _pane_read(self, rest):
        if rest[0] not in self.panes:
            return herdr_error("pane_not_found", f"pane {rest[0]} not found")
        return 0, self.screens.get(rest[0], ""), ""

    def _pane_send_keys(self, rest):
        if rest[0] not in self.panes:
            return herdr_error("pane_not_found", f"pane {rest[0]} not found")
        self.keys.append((rest[0], rest[1:]))
        return _ok({"sent": True})

    def _agent_start(self, rest):
        name, pane = rest[0], _option(rest, "--pane")
        if not AGENT_NAME.fullmatch(name):
            return herdr_error("invalid_agent_name", name)
        if name in self.agents:
            return herdr_error("agent_name_in_use", name)
        if pane not in self.panes:
            return herdr_error("pane_not_found", f"pane {pane} not found")
        args = rest[rest.index("--") + 1:] if "--" in rest else []
        self.panes[pane].update(kind=_option(rest, "--kind"), name=name, status="idle")
        self.agents[name] = pane
        self.started.append({"name": name, "kind": _option(rest, "--kind"), "pane": pane, "args": args})
        return _ok({"agent": self._agent_info(pane)})

    def _agent_get(self, rest):
        pane = self._target(rest[0])
        if pane is None:
            return herdr_error("agent_not_found", f"agent target {rest[0]} not found")
        return _ok({"agent": self._agent_info(pane)})

    def _agent_list(self, rest):
        return _ok({"agents": [self._agent_info(pane) for pane in self.panes if self.panes[pane]["kind"]]})

    def _agent_prompt(self, rest):
        pane = self._target(rest[0])
        if pane is None:
            return herdr_error("agent_not_found", f"agent target {rest[0]} not found")
        if self.panes[pane]["blocked"]:
            return herdr_error("agent_blocked", "the agent shows a dialog")
        self.prompts.append({"target": rest[0], "pane": pane, "text": rest[1]})
        if self.panes[pane]["stall"]:
            return herdr_error("agent_prompt_stalled", "no work within 5 seconds")
        return _ok({"sent": True})

    def _agent_wait(self, rest):
        if self._target(rest[0]) is None:
            return herdr_error("agent_not_found", f"agent target {rest[0]} not found")
        return _ok({"agent": self._agent_info(self._target(rest[0]))})

    # git.

    def _git(self, args):
        if args[:2] == ["rev-parse", "--path-format=absolute"] and args[2:] == ["--git-dir", "--git-common-dir"]:
            return self._rev_parse_dirs()
        if args[:3] == ["rev-parse", "--verify", "--quiet"]:
            ref = args[3].removeprefix("refs/heads/")
            return (0, "0" * 40 + "\n", "") if ref in self.branches else (1, "", "")
        if args[:3] == ["worktree", "add", "-b"]:
            branch, path, base = args[3], args[4], args[5]
            if base not in self.branches:
                return 128, "", f"fatal: invalid reference: {base}"
            if branch in self.branches:
                return 128, "", f"fatal: a branch named '{branch}' already exists"
            Path(path).mkdir(parents=True, exist_ok=True)
            self.branches.add(branch)
            self.worktrees[path] = branch
            return 0, "", f"Preparing worktree (new branch '{branch}')"
        raise AssertionError(f"the fake git has no command {args}")

    def _rev_parse_dirs(self):
        cwd = self.calls[-1][2] if self.calls[-1][1:2] == ["-C"] else "."
        if not Path(cwd).is_dir():
            return 128, "", f"fatal: cannot change to '{cwd}': No such file or directory"
        common = Path(cwd) / ".git"
        git_dir = common / "worktrees" / Path(cwd).name if str(Path(cwd)) in self.linked else common
        return 0, f"{git_dir.as_posix()}\n{common.as_posix()}\n", ""
