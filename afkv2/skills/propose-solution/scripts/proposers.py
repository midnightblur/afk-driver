"""Drive 2 solution proposers, 1 Claude and 1 Codex, through herdr (SDD §3 rows S-6 to S-8; design ADR-0003).

Verbs, run from the repository root; each answers one JSON object:
  plan     --doc D                        count 2 with both tools, or count 1 with the reason; starts nothing
  start    --doc D --brief F --base REF   per tool: a detached throwaway worktree, a pane, the tool, the brief
  wait     --doc D                        each proposer settles; after `critique` also the 4 file paths
  critique --doc D                        each proposer critiques the DRAFT.md of the other
  cleanup  --doc D                        closes each recorded pane and removes each recorded worktree

Refusal codes: plan `aspects-open`; start `same-tool`, `not-planned`, `aspects-open`, `no-herdr`, `missing-input`,
`worktree-failed`, `herdr-failed`, `not-submitted`; wait `not-started`, `pane-gone`, `herdr-failed`, `no-draft`;
critique `not-started`, `not-drafted`, `no-draft`, `not-submitted`; cleanup `cleanup-failed`.

`plan` answers exactly the `proposers` input of the design build: {count, tools, reason}. `cleanup` answers it
again under `proposers`, except when no plan was recorded. A proposer failure is a refusal coded in `FAILURES`
once the proposers started, or a cleanup of a count 2 plan before `wait` answered the critiques; after it, both
answer count 1 with reason `proposer-failed`: the agent in charge drafts alone (SDD §6, §7; decision D-10).

The state file `<doc stem>.proposers.json` beside the page document is the ledger, version 1:
{version, count, tools, reason, stage, brief, proposers: [{tool, agent, pane, worktree, created}], cleaned, failed}.
`stage` is planned, drafting, drafted, critiquing, critiqued or failed. `failed`, present only after a failure, is
{stage, code}: the stage the failure stopped, and the refusal code or `not-finished` from cleanup. A pane or a worktree
that is not null is open. `created` turns true once `git worktree add` exits 0; cleanup force-removes only such a
worktree, and a folder that a failed add left counts as open until a plain remove or a removal by hand.
`cleanup` keeps the file with `cleaned` true (decision D-7). Every herdr and git call, and every host fact, goes
through `HerdrRunner`.

Full auto-approval counts as forbidden when a local policy source turns it off:
- Claude managed settings with `permissions.disableBypassPermissionsMode: "disable"`, from `managed-settings.json`,
  `managed-settings.d/*.json`, the Windows registry value `Settings` under `HKLM` or `HKCU`
  `\\SOFTWARE\\Policies\\ClaudeCode`, or the macOS managed profile `com.anthropic.claudecode`.
- Codex requirements, from the system `requirements.toml` or the macOS managed profile key
  `com.openai.codex:requirements_toml_base64`, whose `allowed_sandbox_modes` leaves out `danger-full-access`, whose
  `allowed_approval_policies` leaves out `never`, or whose `allowed_permission_profiles` table does not set
  `:danger-full-access` to true.
Any one source that forbids is enough; a source that exists but cannot be read or parsed counts as forbidden. A
policy from a server (Claude server-managed settings, Codex cloud requirements) is not read: no documented local
copy exists.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "use-lavish" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import design_round as dr  # noqa: E402
from grill_common import Parser, Refusal, serve, write_json  # noqa: E402

TOOLS = ("claude", "codex")
BYPASS = {"claude": ["--dangerously-skip-permissions"], "codex": ["--yolo"]}
DRAFT, CRITIQUE, BRIEF = "DRAFT.md", "CRITIQUE.md", "BRIEF.md"
START_MS, PROMPT_MS, ENTER_MS = "90000", "30000", "30000"
ENTER_PAUSE_S = 2
COMMAND_S = 120
INPUT_LINES = 6
PREFIX = 40
MARKERS = (">", "›", "❯")
FRAME = str.maketrans("", "", "│┃║|╭╮╰╯─━>›❯")
UNREADABLE = object()
MANAGED_PREFERENCES = "/Library/Managed Preferences"
CLAUDE_DOMAIN, CODEX_DOMAIN = "com.anthropic.claudecode", "com.openai.codex"
CLAUDE_KEY = r"SOFTWARE\Policies\ClaudeCode"
DRAFT_PROMPT = (f"Read {BRIEF} in your working folder and follow it. Write your design draft to {DRAFT} in your "
                f"working folder. Write no other file.")
CRITIQUE_PROMPT = ("Read {other}, the design draft of the other solution proposer. Critique it against {brief} in "
                   "your working folder: name each point you accept and each point you dispute, with the reason. "
                   "Write the critique to {critique} in your working folder. Write no other file.")


class HerdrRunner:
    """The one door to herdr, git and the host facts. Tests replace it with an in-process fake."""

    def __init__(self):
        self.env = dict(os.environ)
        self.platform = sys.platform

    def which(self, name):
        return shutil.which(name)

    def read_text(self, path):
        """The text, None for an absent file, or UNREADABLE."""
        try:
            return Path(path).read_text("utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError):
            return UNREADABLE

    def glob(self, folder, pattern):
        return sorted(Path(folder).glob(pattern)) if Path(folder).is_dir() else []

    def sleep(self, seconds):
        time.sleep(seconds)

    def run(self, argv, timeout=COMMAND_S):
        """`(exit code, stdout, stderr)`. A timeout of None waits without a limit."""
        try:
            done = subprocess.run(argv, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as problem:
            return 1, "", str(problem)
        return done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace")


# The plan (SDD §3 row S-6; PRD AC-024).

def _own_tool(runner):
    if runner.env.get("CODEX_THREAD_ID") and not runner.env.get("CLAUDECODE"):
        return "codex"
    if runner.env.get("CLAUDECODE"):
        return "claude"
    return next((tool for tool in TOOLS if runner.which(tool)), TOOLS[0])


def _settings_forbid(text):
    """Whether one Claude managed settings document turns bypass off; an unparsable one counts as forbidden."""
    try:
        permissions = json.loads(text).get("permissions") or {}
    except (TypeError, ValueError, AttributeError):
        return True
    return not isinstance(permissions, dict) or permissions.get("disableBypassPermissionsMode") == "disable"


def _registry_value(out):
    """The data of the `Settings` value in a `reg query` answer, or None."""
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0] == "Settings" and parts[1] in ("REG_SZ", "REG_EXPAND_SZ"):
            return parts[2]
    return None


def _profile(runner, domain):
    """The path of a macOS managed profile, or None when the profile is absent."""
    found = runner.glob(Path(MANAGED_PREFERENCES), f"{domain}.plist")
    return f"{MANAGED_PREFERENCES}/{domain}.plist" if found else None


def _claude_documents(runner):
    """Each Claude managed settings document of this host: its text, or UNREADABLE."""
    if runner.platform == "win32":
        folder = Path(runner.env.get("ProgramFiles") or r"C:\Program Files") / "ClaudeCode"
    elif runner.platform == "darwin":
        folder = Path("/Library/Application Support/ClaudeCode")
    else:
        folder = Path("/etc/claude-code")
    for path in [folder / "managed-settings.json", *runner.glob(folder / "managed-settings.d", "*.json")]:
        text = runner.read_text(path)
        if text is not None:
            yield text
    if runner.platform == "win32":
        for hive in ("HKLM", "HKCU"):
            code, out, _ = runner.run(["reg", "query", rf"{hive}\{CLAUDE_KEY}", "/v", "Settings"])
            if code == 0:
                yield _registry_value(out) or UNREADABLE
    elif runner.platform == "darwin" and (plist := _profile(runner, CLAUDE_DOMAIN)):
        code, out, _ = runner.run(["plutil", "-convert", "json", "-o", "-", plist])
        yield out if code == 0 else UNREADABLE


def _claude_forbids(runner):
    return any(text is UNREADABLE or _settings_forbid(text) for text in _claude_documents(runner))


def _requirements_forbid(text):
    """Whether one Codex requirements document forbids `--yolo`; an unparsable one counts as forbidden."""
    try:
        data = tomllib.loads(text)
    except (TypeError, tomllib.TOMLDecodeError):
        return True
    modes, approvals = data.get("allowed_sandbox_modes"), data.get("allowed_approval_policies")
    profiles = data.get("allowed_permission_profiles")
    return ((modes is not None and (not isinstance(modes, list) or "danger-full-access" not in modes))
            or (approvals is not None and (not isinstance(approvals, list) or "never" not in approvals))
            or (profiles is not None and (not isinstance(profiles, dict)
                                          or profiles.get(":danger-full-access") is not True)))


def _codex_documents(runner):
    """Each Codex requirements document of this host: its text, or UNREADABLE."""
    if runner.platform == "win32":
        path = Path(runner.env.get("ProgramData") or r"C:\ProgramData") / "OpenAI" / "Codex" / "requirements.toml"
    else:
        path = Path("/etc/codex/requirements.toml")
    text = runner.read_text(path)
    if text is not None:
        yield text
    if runner.platform == "darwin" and (plist := _profile(runner, CODEX_DOMAIN)):
        code, out, _ = runner.run(["plutil", "-extract", "requirements_toml_base64", "raw", "-o", "-", plist])
        if code == 0:
            try:
                yield base64.b64decode(out.strip(), validate=True).decode("utf-8")
            except (binascii.Error, ValueError):
                yield UNREADABLE


def _codex_forbids(runner):
    return any(text is UNREADABLE or _requirements_forbid(text) for text in _codex_documents(runner))


def plan_proposers(runner):
    """How many solution proposers draft: `{count, tools, reason}`. Count 1 names the first missing condition."""
    if not _herdr(runner):
        reason = "no-herdr"
    elif runner.env.get("HERDR_ENV") != "1":
        reason = "outside-herdr"
    elif not all(runner.which(tool) for tool in TOOLS):
        reason = "no-other-tool"
    elif _claude_forbids(runner) or _codex_forbids(runner):
        reason = "bypass-forbidden"
    else:
        return {"count": 2, "tools": list(TOOLS), "reason": None}
    return {"count": 1, "tools": [_own_tool(runner)], "reason": reason}


# The commands.

def _herdr(runner):
    return runner.env.get("HERDR_BIN_PATH") or runner.which("herdr")


def _parsed(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def _error_code(out, err):
    for text in (err, out):
        data = _parsed(text)
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            return data["error"].get("code")
    return None


def _call(runner, *args, timeout=COMMAND_S):
    binary = _herdr(runner)
    if not binary:
        raise Refusal("no-herdr", "herdr is not on PATH")
    return runner.run([binary, *args], timeout=timeout)


def _herdr_ok(runner, *args, timeout=COMMAND_S):
    code, out, err = _call(runner, *args, timeout=timeout)
    if code != 0:
        raise Refusal("herdr-failed", f"herdr {' '.join(args[:2])}: {_error_code(out, err) or (err or out).strip()}")
    return _parsed(out) or {}


def _git(runner, *args):
    return runner.run(["git", *args])


# The state file.

def _load(doc):
    return dr.proposers_state(doc)


def _save(doc, state):
    write_json(dr.proposers_state_path(doc), state)


LIVE = ("drafting", "drafted", "critiquing", "critiqued")
FAILURES = {"no-herdr", "worktree-failed", "herdr-failed", "not-submitted", "pane-gone", "no-draft"}


def _recording(verb):
    """Run a verb; a refusal once the proposers started records the failure (SDD §6: drafting/critiquing -> failed)."""
    def run(args, runner):
        try:
            return verb(args, runner)
        except Refusal as refusal:
            state = _load(args.doc)
            if (refusal.code in FAILURES and state and state["count"] == 2 and not state.get("cleaned")
                    and not state.get("failed") and state.get("stage") in LIVE):
                state["failed"] = {"stage": state["stage"], "code": refusal.code}
                state["stage"] = "failed"
                _save(args.doc, state)
            raise
    return run


def _answer(state, runner):
    """The `proposers` input of the design build, from the state file."""
    if state.get("failed"):
        return {"count": 1, "tools": [_own_tool(runner)], "reason": dr.PROPOSER_FAILED}
    tools = state.get("tools") or (list(TOOLS) if state["count"] == 2 else [_own_tool(runner)])
    return {"count": state["count"], "tools": tools, "reason": state.get("reason")}


def _started(doc):
    """The state of a session whose 2 proposers both run: each tool recorded with a pane and a worktree."""
    state = _load(doc)
    entries = (state or {}).get("proposers") or []
    running = [entry for entry in entries if entry.get("pane") and entry.get("worktree")]
    if (state is None or state.get("cleaned") or state.get("failed")
            or sorted(entry.get("tool") for entry in running) != sorted(TOOLS)):
        raise Refusal("not-started", "both solution proposers must run, each with a pane and a worktree: run "
                                     "`cleanup`, and the agent in charge drafts alone")
    return state


def _check_aspects(doc, state):
    if dr.next_step(dr._view(doc), state)["phase"] == "aspects":
        raise Refusal("aspects-open", "the solution proposers start after every critical aspect settles")


# The verbs.

def plan(args, runner):
    state = _load(args.doc)
    _check_aspects(args.doc, state)
    if state is None:
        state = {"version": dr.STATE_VERSION, **plan_proposers(runner), "stage": "planned", "proposers": [],
                 "cleaned": False}
        _save(args.doc, state)
    return _answer(state, runner)


def _compact(text):
    return "".join(text.translate(FRAME).split())


def _in_input_line(screen, text):
    """Whether `text` still sits in the input line: the last line that opens with a prompt marker, and the lines
    it wraps onto. With no marker on the screen, the last INPUT_LINES lines count."""
    lines = (screen or "").replace("\r\n", "\n").split("\n")
    marked = [n for n, line in enumerate(lines) if line.lstrip(" │┃║|").startswith(MARKERS)]
    tail = lines[marked[-1]:] if marked else [line for line in lines if line.strip()][-INPUT_LINES:]
    return _compact(text)[:PREFIX] in _compact("".join(tail))


def _submit(runner, entry, text):
    """Send one prompt; on `agent_prompt_stalled`, 1 Enter only while the prompt still sits in the input line.

    A prompt gone from the input line counts as submitted only when the agent then reaches working: a start-up
    dialog line can open with a prompt marker and pass for the input line."""
    code, out, err = _call(runner, "agent", "prompt", entry["agent"], text, "--wait", "--until", "working",
                           "--timeout", PROMPT_MS)
    if code == 0:
        return True
    if _error_code(out, err) != "agent_prompt_stalled":
        raise Refusal("not-submitted", f"{entry['tool']}: {_error_code(out, err) or (err or out).strip()}")
    code, screen, err = _call(runner, "pane", "read", entry["pane"], "--source", "visible", "--lines", "40")
    if code != 0:
        raise Refusal("not-submitted", f"{entry['tool']}: the prompt stalled, and herdr pane read failed: "
                                       f"{_error_code(screen, err) or (err or screen).strip()}")
    if not _in_input_line(screen, text):
        code, _, _ = _call(runner, "agent", "wait", entry["agent"], "--until", "working", "--timeout", ENTER_MS)
        if code != 0:
            raise Refusal("not-submitted", f"{entry['tool']}: the prompt stalled and left the input line, but the "
                                           f"agent did not start work; a dialog may hold the pane")
        return True
    runner.sleep(ENTER_PAUSE_S)
    _herdr_ok(runner, "pane", "send-keys", entry["pane"], "enter")
    code, _, _ = _call(runner, "agent", "wait", entry["agent"], "--until", "working", "--timeout", ENTER_MS)
    if code != 0:
        raise Refusal("not-submitted", f"{entry['tool']}: the prompt stalled in the input line after 1 Enter")
    return True


def _main_checkout(runner):
    code, out, err = _git(runner, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if code != 0:
        raise Refusal("worktree-failed", f"git rev-parse: {err.strip()}")
    return Path(out.strip()).parent


def start(args, runner):
    state = _load(args.doc)
    if state and state.get("proposers"):
        tools = [entry.get("tool") for entry in state["proposers"]]
        raise Refusal("same-tool", f"this session already started its solution proposers: {', '.join(tools)}")
    if not state or state["count"] != 2 or state.get("cleaned") or state.get("failed"):
        raise Refusal("not-planned", "start needs a `plan` answer of count 2 that has not failed or been cleaned "
                                     "up; otherwise the agent in charge drafts")
    _check_aspects(args.doc, state)
    if not _herdr(runner):
        raise Refusal("no-herdr", "herdr is not on PATH")
    try:
        brief = Path(args.brief).read_text("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise Refusal("missing-input", f"brief {args.brief}: {error}") from None
    state.update(brief=hashlib.sha256(brief.encode("utf-8")).hexdigest(), stage="drafting")
    _save(args.doc, state)
    main = _main_checkout(runner)
    stem = Path(args.doc).stem
    answer = []
    for tool in TOOLS:
        worktree = main.parent / f"{main.name}-worktrees" / f"proposer-{stem}-{tool}"
        if worktree.exists():
            raise Refusal("worktree-failed", f"{tool}: {worktree} already exists; start leaves it as it is")
        entry = {"tool": tool, "agent": f"{stem}-{tool}", "pane": None, "worktree": str(worktree), "created": False}
        state["proposers"].append(entry)
        _save(args.doc, state)
        code, _, err = _git(runner, "worktree", "add", "--detach", str(worktree), args.base)
        if code != 0:
            raise Refusal("worktree-failed", f"{tool}: git worktree add: {err.strip()}")
        entry["created"] = True
        _save(args.doc, state)
        try:
            (worktree / BRIEF).write_text(brief, "utf-8")
        except OSError as error:
            raise Refusal("worktree-failed", f"{tool}: {BRIEF}: {error}") from None
        where = ["--pane", runner.env["HERDR_PANE_ID"]] if runner.env.get("HERDR_PANE_ID") else ["--current"]
        split = _herdr_ok(runner, "pane", "split", *where, "--direction", "right", "--cwd", str(worktree), "--no-focus")
        entry["pane"] = ((split.get("result") or {}).get("pane") or {}).get("pane_id")
        _save(args.doc, state)
        if not entry["pane"]:
            raise Refusal("herdr-failed", f"{tool}: herdr pane split answered no pane id")
        _herdr_ok(runner, "agent", "start", entry["agent"], "--kind", tool, "--pane", entry["pane"],
                  "--timeout", START_MS, "--", *BYPASS[tool])
        answer.append({"tool": tool, "pane": entry["pane"], "worktree": entry["worktree"],
                       "submitted": _submit(runner, entry, DRAFT_PROMPT)})
    return {"ok": True, "proposers": answer}


def _status(runner, entry):
    code, out, err = _call(runner, "pane", "get", entry["pane"]) if entry.get("pane") else (1, "", "")
    if code != 0:
        if not entry.get("pane") or _error_code(out, err) == "pane_not_found":
            raise Refusal("pane-gone", f"{entry['tool']}: the pane {entry.get('pane')} is gone")
        raise Refusal("herdr-failed", f"herdr pane get: {_error_code(out, err) or err.strip()}")
    return (((_parsed(out) or {}).get("result") or {}).get("pane") or {}).get("agent_status")


def _missing(state, names):
    return [str(Path(entry["worktree"]) / name) for entry in state["proposers"] for name in names
            if not (Path(entry["worktree"]) / name).is_file()]


def wait(args, runner):
    state = _started(args.doc)
    states = {}
    for entry in state["proposers"]:
        _status(runner, entry)
        code, out, err = _call(runner, "agent", "wait", entry["agent"], "--until", "idle", "--until", "done",
                               "--until", "blocked", timeout=None)
        if code != 0:
            _status(runner, entry)
            raise Refusal("herdr-failed", f"herdr agent wait: {_error_code(out, err) or err.strip()}")
        states[entry["tool"]] = _status(runner, entry)
    critiqued = state.get("stage") in ("critiquing", "critiqued")
    names = (DRAFT, CRITIQUE) if critiqued else (DRAFT,)
    missing = _missing(state, names)
    if missing:
        raise Refusal("no-draft", f"a solution proposer wrote no file: {', '.join(missing)}", missing=missing)
    state["stage"] = "critiqued" if critiqued else "drafted"
    _save(args.doc, state)
    answer = {"ok": True, "states": states}
    if critiqued:
        answer["files"] = [str(Path(entry["worktree"]) / name) for entry in state["proposers"] for name in names]
    return answer


def critique(args, runner):
    state = _started(args.doc)
    if state.get("stage") != "drafted":
        raise Refusal("not-drafted", f"critique runs once, after `wait` answers both drafts; the stage is "
                                     f"{state.get('stage')}")
    missing = _missing(state, (DRAFT,))
    if missing:
        raise Refusal("no-draft", f"critique needs both drafts: {', '.join(missing)}", missing=missing)
    entries, submitted = state["proposers"], {}
    for entry in entries:
        other = next(item for item in entries if item is not entry)
        text = CRITIQUE_PROMPT.format(other=Path(other["worktree"]) / DRAFT, brief=BRIEF, critique=CRITIQUE)
        submitted[entry["tool"]] = _submit(runner, entry, text)
    state["stage"] = "critiquing"
    _save(args.doc, state)
    return {"ok": True, "submitted": submitted}


def _close(runner, pane):
    code, out, err = _call(runner, "pane", "close", pane)
    return code == 0 or _error_code(out, err) == "pane_not_found"


def _remove(runner, worktree, created):
    """A plain remove first; `--force` only for a worktree that start created."""
    if not Path(worktree).exists():
        return _git(runner, "worktree", "prune")[0] == 0
    return (_git(runner, "worktree", "remove", worktree)[0] == 0
            or (created and _git(runner, "worktree", "remove", "--force", worktree)[0] == 0))


def cleanup(args, runner):
    state = _load(args.doc)
    if state is None:
        return {"ok": True, "closed": [], "removed": []}
    closed, removed, left = [], [], []
    for entry in state.get("proposers") or []:
        if entry.get("pane"):
            if _close(runner, entry["pane"]):
                closed.append(entry["pane"])
                entry["pane"] = None
                _save(args.doc, state)
            else:
                left.append(entry["pane"])
        if entry.get("pane"):
            if entry.get("worktree"):
                left.append(entry["worktree"])
        elif entry.get("worktree"):
            if _remove(runner, entry["worktree"], entry.get("created") is True):
                removed.append(entry["worktree"])
                entry["worktree"] = None
                _save(args.doc, state)
            else:
                left.append(entry["worktree"])
    if left:
        raise Refusal("cleanup-failed", f"still open: {', '.join(left)}; close or delete each by hand, then run "
                                        f"cleanup again", left=left, closed=closed, removed=removed)
    if state["count"] == 2 and state.get("stage") != "critiqued" and not state.get("failed"):
        state["failed"] = {"stage": state.get("stage"), "code": "not-finished"}
    state["cleaned"] = True
    _save(args.doc, state)
    return {"ok": True, "closed": closed, "removed": removed, "proposers": _answer(state, runner)}


VERBS = {"plan": plan, "start": _recording(start), "wait": _recording(wait), "critique": _recording(critique),
         "cleanup": cleanup}


def main(argv, runner=None):
    parser = Parser(add_help=False)
    parser.add_argument("verb", choices=sorted(VERBS))
    parser.add_argument("--doc", required=True)
    parser.add_argument("--brief")
    parser.add_argument("--base")
    args = parser.parse_args(argv)
    if args.verb == "start" and not (args.brief and args.base):
        raise Refusal("usage", "start needs --brief and --base", 2)
    return VERBS[args.verb](args, runner or HerdrRunner())


if __name__ == "__main__":
    sys.exit(serve(main))
