"""The live milestone rows of /afkv2:dogfood: `dogfood_live_milestone.py --row VR-NNN`.

An agent or the end gate runs it from a herdr pane. It builds its world as `dogfood_live_start.py` does (D-WORK,
D-SRC, 1 new herdr tab, a real Claude or Codex main agent, the real install record put back at the end) and reuses
its `World`. It writes 1 JSON answer to stdout and to `$AFKV2_EVIDENCE/<row>.json` (else the scratch results file),
with what it saw. Exit 0: the Then holds; 1: it does not, or the run failed; 2: bad input.

Rows and their sessions:
  VR-032, VR-034, VR-052
      shell rows: a real herdr shell pane is the main pane of a fixture state in a scratch LOCALAPPDATA (E-HERDR).
  VR-023 to VR-026, VR-029 to VR-031, VR-033, VR-035, VR-044, VR-064
      stand-in rows: a real main agent and a fixture state whose afkv2 pane is a split pane beside it. The afkv2 side
      runs the real `dogfood.py` verbs with that pane as its caller, as the afkv2 agent's own shell does. Where a row
      needs a live afkv2 agent as the receiver of `tell`, a small inert Claude agent holds the afkv2 pane.
  VR-027, VR-028, VR-045, VR-047, VR-048, VR-050, VR-051
      session rows: the main agent runs the dogfood skill and the real afkv2 agent builds the asks. D-SRC gets the
      origin of this build, so the afkv2 agent pushes and opens its Draft changes into verify/df-base (plan decision
      D-21); the end closes each change into verify/df-base, deletes its branch and deletes verify/df-base.

The script plays the developer: it answers the base question, takes the agent's own pick at a question, and gives
the go of a page round in the agent's pane as a round send, since no browser runs here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dogfood_live_start as live  # noqa: E402
from dogfood_live_start import (AFKV2, BASE, DOGFOOD, POLL_S, TURN_LIMIT_S, Failed, World, check, flat,  # noqa: E402
                                git, pause, run_command)

DOGFOOD_PY = AFKV2.parent / DOGFOOD / "scripts" / "dogfood.py"
NOTE_LINE = "A note from the afkv2 pane:"
HEADER = "afkv2-note v1"
FORWARD_LINE = "A new ask from the main pane:"
FEEDBACK_LINE = "Feedback from the main pane:"
WRAP_LINE = "The wrap-up request from the main pane:"
ASK_WE01 = live.ASK_WE01
ASK_WE02_1, ASK_WE02_2 = "add a link to the ticket on the review page", live.ASK_WE02_2
INERT = ("You stand in for the afkv2 agent of a test. Run no tool and change nothing. Answer each message with the "
         "1 word NOTED.")
TRIAL_ERROR = "small_lane.py: refused no-go-mark: card go-1 holds no sign mark of the developer (exit 1)"
BUSY_S, BUSY_STEPS = 25, 3
SESSION_LIMIT_S, MILESTONE_LIMIT_S, WRAP_LIMIT_S = 2400, 1500, 1200
NUDGES = 12
CODEX_EMPTY = re.compile(r"[^\n]*\b0% left[^\n]*")
SHELL_ROWS = ("VR-032", "VR-034", "VR-052")
CODEX_ROWS = ("VR-024", "VR-026", "VR-028", "VR-030", "VR-051", "VR-064")
ROWS = ("VR-023", "VR-024", "VR-025", "VR-026", "VR-027", "VR-028", "VR-029", "VR-030", "VR-031", "VR-032", "VR-033",
        "VR-034", "VR-035", "VR-044", "VR-045", "VR-047", "VR-048", "VR-050", "VR-051", "VR-052", "VR-064")


# The dogfood verbs, with a given pane as the caller.

def as_pane(world, pane, *args, local=None):
    """(exit, answer) of 1 dogfood.py verb whose caller is `pane`: the shell of that pane runs it so."""
    env = dict(world.env, HERDR_ENV="1", HERDR_PANE_ID=pane)
    if local is not None:
        env["LOCALAPPDATA"] = str(local)
    code, out, err = run_command([world.python, DOGFOOD_PY, *args], env=env)
    try:
        answer = json.loads(out.splitlines()[-1]) if out else None
    except ValueError:
        answer = None
    world.seen.setdefault("verbs", []).append({"pane": pane, "args": [str(arg) for arg in args], "exit": code,
                                               "answer": answer, "stderr": err[-300:]})
    return code, answer


def in_pane(world, pane, args, name):
    """(exit, answer, stdout) of 1 dogfood.py verb typed in the shell `pane`: a runner file runs it there and
    writes the result, then prints a token the wait matches."""
    out, token = world.root / f"{name}.json", secrets.token_hex(6)
    runner = world.root / f"{name}.py"
    runner.write_text(
        "import json, subprocess, sys\n"
        f"done = subprocess.run([sys.executable, {str(DOGFOOD_PY)!r}, *{[str(arg) for arg in args]!r}], "
        "capture_output=True, text=True, encoding='utf-8')\n"
        f"open({str(out)!r}, 'w', encoding='utf-8').write(json.dumps({{'exit': done.returncode, 'stdout': done.stdout, "
        "'stderr': done.stderr}))\n"
        f"print('DFLIVE-' + {token[:6]!r} + '-' + {token[6:]!r})\n", encoding="utf-8")
    world.herdr.ok("pane", "run", pane, f"{world.python.as_posix()} {runner.as_posix()}")
    world.herdr.call("pane", "wait-output", pane, "--match", f"DFLIVE-{token[:6]}-{token[6:]}", "--timeout", "90000",
                     limit=120)
    try:
        result = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Failed("no-answer", f"dogfood.py {args[0]} wrote no answer; the pane shows: "
                                  f"{world.herdr.read(pane, 30)[-800:]}")
    lines = result["stdout"].strip().splitlines()
    try:
        answer = json.loads(lines[0]) if len(lines) == 1 else None
    except ValueError:
        answer = None
    world.seen.setdefault("verbs", []).append({"pane": pane, "args": [str(arg) for arg in args],
                                               "exit": result["exit"], "answer": answer})
    return result["exit"], answer, result["stdout"]


# The fixture state and the notes.

def safe(pane):
    return "".join(char if char.isascii() and (char.isalnum() or char in "_-") else "_" for char in pane)


def state_file(data, main_pane):
    return Path(data) / f"dogfood-{safe(main_pane)}.json"


def notes_folder(data, main_pane):
    return Path(data) / f"dogfood-{safe(main_pane)}" / "notes"


def write_state(data, main_pane, afkv2_pane, agent, source, worktrees):
    """A version 1 state as `dogfood.py start` and `worktree` write it."""
    now = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    state = {"version": 1, "main_pane": main_pane, "agent": agent, "afkv2_pane": afkv2_pane, "harness": "claude",
             "source": str(source), "base": BASE,
             "worktrees": [{"path": str(path), "branch": branch, "lane": "small", "created": now}
                           for path, branch in worktrees],
             "notes": [], "wrap_reported": False, "started": now}
    path = state_file(data, main_pane)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return path


def small_worktree(world, source):
    """1 small-asks worktree of D-SRC on its own branch from verify/df-base, where `worktree` puts it."""
    branch = f"feat/afkv2-df-live-{secrets.token_hex(2)}"
    path = Path(source).parent / f"{Path(source).name}-worktrees" / branch.replace("/", "-")
    git("worktree", "add", "-q", "-b", branch, str(path), BASE, cwd=source)
    return path, branch


def skill_file(tree, name="small-change"):
    return Path(tree) / "afkv2" / "skills" / name / "SKILL.md"


def edit_step(path, step, line):
    """Add `line` to the end of step `step` of a skill file, and answer the new text."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    at = next(index for index, value in enumerate(lines) if value.startswith(f"{step}. "))
    end = next((index for index in range(at + 1, len(lines)) if re.match(r"\d+\. |## ", lines[index])), len(lines))
    while end > at + 1 and not lines[end - 1].strip():
        end -= 1
    lines.insert(end, "")
    lines.insert(end + 1, f"   {line}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def commit_all(tree, message):
    git("add", "-A", cwd=tree)
    git("commit", "-q", "-m", message, cwd=tree)


STEP4_LINE = "Show the round before any code. The go is the sign mark of the developer on the go card."
STEP3_LINE = "Write the test plan as a table with 1 row per test: Level, Test, Proves. The high-level test comes first."


def we01_note(tree):
    path = skill_file(tree)
    return "\n".join([HEADER, "kind: milestone", f"ask: {ASK_WE01}", "purpose: a clear step 4 for the next small change",
                      "changed:", f"- {path} | CK-1 | changed | step 4 says what the round shows and what the go is",
                      "use: Your next small change reads step 4 from this file.", "redo: none"]) + "\n"


def we03_note(tree):
    skill, hooks = skill_file(tree), Path(tree) / "afkv2" / "hooks" / "hooks.json"
    return "\n".join([
        HEADER, "kind: milestone", "ask: write the test plan of step 3 as a table",
        "purpose: a test plan table in each small change", "changed:",
        f"- {skill} | CK-1 | changed | step 3 writes the test plan as a table: Level, Test, Proves",
        f"- {hooks} | CK-4 | changed | the session start hook prints the test plan rule",
        "use: Run any small change. Its step 3 writes the test plan as a table.",
        f"best-effort: {hooks} - the hook runs from the installed plugin and may not apply in this session",
        "redo: the test plan of step 3 that you already wrote: write it again as a table, by the new step 3"]) + "\n"


def write_note(world, name, text):
    path = world.root / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


# The sessions of the agents, as events.

def events(world, name):
    """The session of the agent `name` as a list of {"kind", "text", "name"}: kind user (a typed or queued prompt),
    text (an assistant text), tool (a tool call), result (a tool result) or end (a Codex turn end)."""
    agent = world.herdr.agent(name) or {}
    session = (agent.get("agent_session") or {}).get("value")
    if not session:
        return []
    if agent.get("agent") == "codex":
        return _codex_events(world, name, session)
    found = []
    for entry in live.transcript(world, name):
        kind = entry.get("type")
        if kind == "attachment" and (entry.get("attachment") or {}).get("type") == "queued_command":
            found.append({"kind": "user", "text": str(entry["attachment"].get("prompt") or ""), "queued": True})
        elif kind == "user":
            content = (entry.get("message") or {}).get("content")
            if isinstance(content, str):
                found.append({"kind": "user", "text": content})
                continue
            for block in content or []:
                if block.get("type") == "text":
                    found.append({"kind": "user", "text": block.get("text", "")})
                elif block.get("type") == "tool_result":
                    found.append({"kind": "result", "text": json.dumps(block.get("content"), ensure_ascii=False)})
        elif kind == "assistant":
            for block in live.blocks(entry, "text"):
                found.append({"kind": "text", "text": block.get("text", "")})
            for block in live.blocks(entry, "tool_use"):
                found.append({"kind": "tool", "name": block.get("name"),
                              "text": json.dumps(block.get("input"), ensure_ascii=False)})
    return found


def _codex_events(world, name, session):
    found = []
    for path in (Path.home() / ".codex" / "sessions").glob(f"*/*/*/rollout-*{session}.jsonl"):
        world.seen.setdefault("transcript", {})[name] = str(path)
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            payload = entry.get("payload") or {}
            kind = payload.get("type")
            if entry.get("type") == "response_item" and kind == "message":
                text = "".join(part.get("text", "") for part in payload.get("content") or [])
                found.append({"kind": "user" if payload.get("role") == "user" else "text", "text": text})
            elif entry.get("type") == "response_item" and kind in ("function_call", "custom_tool_call", "local_shell_call"):
                found.append({"kind": "tool", "name": payload.get("name"),
                              "text": str(payload.get("arguments") or payload.get("input") or payload.get("action"))})
            elif entry.get("type") == "response_item" and kind in ("function_call_output", "custom_tool_call_output"):
                found.append({"kind": "result", "text": str(payload.get("output"))})
            elif entry.get("type") == "event_msg" and kind == "task_complete":
                found.append({"kind": "end", "text": str(payload.get("last_agent_message") or "")})
    return found


def first(found, kind, text, start=0):
    """The index of the first event of `kind` from `start` on whose text holds `text` (whitespace ignored), or None."""
    words = flat(text).lower()
    return next((index for index in range(start, len(found)) if found[index]["kind"] == kind
                 and words in flat(found[index]["text"]).lower().replace("\\\\", "\\")), None)


def user_prompts(found, text):
    return [event for event in found if event["kind"] == "user" and flat(text).lower() in flat(event["text"]).lower()]


def said_after(found, start):
    """The assistant texts after event `start`, joined."""
    return "\n".join(event["text"] for event in found[start + 1:] if event["kind"] in ("text", "end"))


def tools_after(found, start):
    return [event for event in found[start + 1:] if event["kind"] == "tool"]


# The harness and the developer.

def harness_up(world, name):
    """A usage limit or a sign-in prompt of the harness: the row did not run."""
    world.harness_up(name)
    pane = (world.herdr.agent(name) or {}).get("pane_id")
    hit = CODEX_EMPTY.search(world.herdr.read(pane, 40, "visible") if pane else "")
    if hit and (world.herdr.agent(name) or {}).get("agent") == "codex":
        raise Failed("harness-unavailable", f"the {name} harness shows: {hit.group(0).strip()}; run the row again when "
                                            f"the account can run turns")


def turn(world, name, text, limit=TURN_LIMIT_S):
    """1 developer turn, then wait until the agent waits for input again."""
    world.reply(name, text)
    pause(POLL_S)
    now = world.wait_status(name, ("idle", "done", "blocked"), limit)
    harness_up(world, name)
    return now


def wait_turn_end(world, name, limit=TURN_LIMIT_S):
    pause(POLL_S)
    now = world.wait_status(name, ("idle", "done", "blocked"), limit)
    harness_up(world, name)
    return now


def page_docs(world, since):
    """The page documents written since `since` in the real page folders, newest first."""
    folder = world.real_data() / "pages"
    docs = [path for path in folder.glob("*/**/*.json") if path.stat().st_mtime >= since] if folder.is_dir() else []
    found = []
    for path in sorted(docs, key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and isinstance(doc.get("rounds"), list) and doc["rounds"]:
            found.append((path, doc))
    return found


def round_send(doc):
    """The developer's send for the last round of `doc`: sign each open signoff card, accept each open card that
    takes accept. None when the round holds no open card that the developer can settle."""
    last = doc["rounds"][-1]
    lines = []
    for item in last.get("items") or []:
        if item.get("state") in ("settled_by_mark", "settled_by_note"):
            continue
        mark = {"signoff": "sign", "decided": "accept", "confirm": "accept"}.get(item.get("kind"))
        if mark:
            lines.append(f"{item['id']} {mark}")
    return f"[round R-{last['n']}]\n" + "\n".join(lines) if any(line.endswith(" sign") for line in lines) else None


def drive(world, agent, until, limit, since):
    """Play the developer until `until()` holds: the go of each open page round as a round send in the agent's pane,
    else the agent's own pick. Answers whether `until()` held."""
    name, pane = agent["name"], agent["pane_id"]
    end, nudges, sent = time.monotonic() + limit, 0, set()
    while time.monotonic() < end:
        if until():
            return True
        now = world.status(name)
        if now in ("idle", "done", "blocked") and nudges < NUDGES and not world.approved(name):
            harness_up(world, name)
            pause(POLL_S * 2)
            if until() or world.status(name) not in ("idle", "done", "blocked"):
                continue
            doc = next(((path, doc) for path, doc in page_docs(world, since)
                        if (str(path), doc["rounds"][-1]["n"]) not in sent and round_send(doc)), None)
            if doc:
                path, body = doc
                sent.add((str(path), body["rounds"][-1]["n"]))
                world.reply(name, "I cannot open the page in a browser, so I give my round send here. Stop the wait, "
                                  "write this text word for word to the raw file of the round, and go on from step 5 "
                                  f"of /afkv2:use-lavish:\n\n{round_send(body)}")
            elif live.menu(world.herdr.read(pane, 40, "visible")) and now == "blocked":
                world.herdr.call("pane", "send-keys", pane, "enter")
            else:
                world.reply(name, "Go on with your own recommendation.")
            nudges += 1
            world.seen.setdefault("nudges", {})[name] = nudges
        pause(POLL_S)
    return until()


def plugin_hashes():
    """SHA-256 of each file under the installed afkv2 plugin root of Claude."""
    record = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    roots = {entry.get("installPath") for key, entries in json.loads(record.read_text(encoding="utf-8"))
             .get("plugins", {}).items() if key.startswith("afkv2@") for entry in entries}
    hashes = {}
    for root in sorted(filter(None, roots)):
        for path in Path(root).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def porcelain(folder):
    code, out, _ = run_command(["git", "status", "--porcelain"], cwd=folder)
    return out if code == 0 else f"git status failed in {folder}"


def wait_for(predicate, limit, step=POLL_S):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        pause(step)
    return predicate()


# The worlds of the rows.

class Run(World):
    """The world of 1 milestone row: `World` with a forge cleanup and the page folders this run made."""

    def __init__(self, row, env, stamp):
        super().__init__(row, env, stamp)
        pages = self.real_data() / "pages"
        self.pages_kept = {path.name for path in pages.iterdir()} if pages.is_dir() else set()
        self.remote = None
        self.started = time.time()

    def with_remote(self, source):
        """D-SRC with the origin of this build and verify/df-base pushed from the build head (plan decision D-21)."""
        url = git("remote", "get-url", "origin", cwd=AFKV2)
        self.remote = url
        self.clear_forge()
        git("remote", "add", "origin", url, cwd=source)
        git("push", "-q", "origin", f"{BASE}:refs/heads/{BASE}", cwd=source)
        self.seen["remote"] = url
        return source

    def slug(self):
        hit = re.search(r"github\.com[:/](.+?)(\.git)?$", self.remote or "")
        return hit.group(1) if hit else None

    def changes(self, state="all"):
        code, out, err = run_command(["gh", "pr", "list", "--repo", self.slug(), "--base", BASE, "--state", state,
                                      "--json", "number,url,isDraft,state,headRefName,body,mergedAt"])
        if code != 0:
            raise Failed("gh-failed", f"gh pr list: {err or out}")
        return json.loads(out or "[]")

    def clear_forge(self):
        """Close each open change into verify/df-base, delete its branch, and delete verify/df-base."""
        if not self.slug():
            return
        for change in self.changes("open"):
            run_command(["gh", "pr", "close", str(change["number"]), "--repo", self.slug(), "--delete-branch",
                         "--comment", "Closed by the dogfood live test after its run."])
        code, out, _ = run_command(["git", "ls-remote", "--heads", self.remote, BASE])
        if code == 0 and out.strip():
            run_command(["git", "push", "-q", self.remote, "--delete", BASE], cwd=AFKV2)

    def clean_up(self):
        done = []
        if self.remote:
            try:
                self.clear_forge()
                done.append({"item": "forge", "name": BASE, "result": "removed"})
            except Exception as error:  # every item is tried
                done.append({"item": "forge", "name": BASE, "result": "failed", "reason": str(error)})
        done += super().clean_up()
        pages = self.real_data() / "pages"
        for path in (pages.iterdir() if pages.is_dir() else []):
            if path.name not in self.pages_kept and path.stat().st_mtime >= self.started:
                try:
                    live._remove(path)
                    done.append({"item": "page folder", "name": str(path), "result": "removed"})
                except OSError as error:
                    done.append({"item": "page folder", "name": str(path), "result": "failed", "reason": str(error)})
        return done


def shell_world(world, afkv2=True):
    """A scratch LOCALAPPDATA, 1 tab whose root shell pane is the main pane, and 1 split shell pane for the afkv2
    pane, with the same LOCALAPPDATA."""
    local = world.scratch_record()
    tab, main_pane = world.open_tab(world.root, {"LOCALAPPDATA": str(local)})
    pane = None
    if afkv2:
        split = world.herdr.ok("pane", "split", "--pane", main_pane, "--direction", "right", "--cwd", str(world.root),
                               "--env", f"LOCALAPPDATA={local}", "--no-focus")
        pane = (split.get("pane") or {}).get("pane_id")
    pause(3)
    return local, tab, main_pane, pane


def stand_in(world, harness, receiver=False, prime=False, work_parent=None):
    """A main agent in D-WORK and a fixture state whose afkv2 pane is a split pane beside it, with 1 small-asks
    worktree of D-SRC that holds the WE-01 edit. `receiver`: an inert Claude agent holds the afkv2 pane, so `tell`
    reaches a live agent. `prime`: the main agent runs the dogfood skill once, so it knows the session."""
    work = world.make_work((work_parent or world.root) / "df-work")
    source = world.make_source(world.root / "df-src")
    tree, branch = small_worktree(world, source)
    edit_step(skill_file(tree), 4, STEP4_LINE)
    commit_all(tree, "Make step 4 of small-change clear")
    world.use_real_record(source)
    tab, main_pane = world.open_tab(work)
    split = world.herdr.ok("pane", "split", "--pane", main_pane, "--direction", "right", "--cwd", str(world.root),
                           "--no-focus")
    pane = (split.get("pane") or {}).get("pane_id")
    agent = f"dogfood-{secrets.token_hex(2)}"
    if receiver:
        world._start(agent, "claude", pane, ["--model", "haiku"])
        turn(world, agent, INERT, 120)
    write_state(world.real_data(), main_pane, pane, agent, source, [(tree, branch)])
    main = world.start_main(harness, main_pane, source)
    world.seen.update(work=str(work), source=str(source), worktree=str(tree), afkv2_pane=pane, agent=agent)
    if prime:
        ask = "Keep each refusal line short."
        text = (f"/afkv2:dogfood {ask}" if harness == "claude"
                else f"Use the dogfood skill in {source / DOGFOOD / 'SKILL.md'} with this ask: {ask}")
        turn(world, main, text)
    return {"work": work, "source": source, "tree": tree, "branch": branch, "tab": tab, "main_pane": main_pane,
            "main": main, "pane": pane, "agent": agent}


def session(world, harness, ask):
    """The main agent runs the dogfood skill with `ask`; the real afkv2 agent opens, and the developer gives the
    base. Answers the session, with `afkv2` None when no afkv2 pane opened."""
    work = world.make_work(world.root / "df-work")
    source = world.with_remote(world.make_source(world.root / "df-src"))
    world.use_real_record(source)
    world.trust(source)
    tab, main_pane = world.open_tab(work)
    main = world.start_main(harness, main_pane, source)
    world.seen.update(work=str(work), source=str(source))
    text = (f"/afkv2:dogfood {ask}" if harness == "claude"
            else f"Use the dogfood skill in {source / DOGFOOD / 'SKILL.md'} with this ask: {ask}")
    world.prompt(main, text)
    pause(POLL_S)
    harness_up(world, main)
    afkv2 = wait_for(lambda: world.afkv2_agent(tab), live.START_LIMIT_S + 60)
    found = {"work": work, "source": source, "tab": tab, "main_pane": main_pane, "main": main, "afkv2": afkv2}
    if afkv2:
        wait_turn_end(world, main)
        live.answer_base(world, afkv2)
    return found


def note_record(world, main_pane, number):
    path = notes_folder(world.real_data(), main_pane) / f"{number:04d}.md"
    return path if path.is_file() else None


def small_branch(world, main_pane):
    state = world.state(world.real_data(), main_pane) or {}
    return next((item for item in state.get("worktrees", []) if item.get("lane") == "small"), None)


def ahead(source, branch):
    code, out, _ = run_command(["git", "log", "--format=%H %ct %s", f"{BASE}..{branch}"], cwd=source)
    return [line.split(" ", 2) for line in out.splitlines()] if code == 0 else []


def files_of(source, commit):
    code, out, _ = run_command(["git", "show", "--name-only", "--format=", commit], cwd=source)
    return out.splitlines() if code == 0 else []


# The rows.

def shell_row(world, row):
    """VR-032 (check-note of 2 invalid notes), VR-034 (note from the main pane) and VR-052 (close --force after the
    afkv2 pane was closed by hand), each from a real herdr shell pane."""
    seen = world.seen
    if row == "VR-052":
        source = world.make_source(world.root / "df-src")
        tree, branch = small_worktree(world, source)
        local, tab, main_pane, pane = shell_world(world)
        data = Path(local) / "afkv2"
        write_state(data, main_pane, pane, f"dogfood-{secrets.token_hex(2)}", source, [(tree, branch)])
        before = git("worktree", "list", "--porcelain", cwd=source)
        world.herdr.ok("pane", "close", pane)
        pause(2)
        code, answer, out = in_pane(world, main_pane, ["close", "--force"], "close")
        after = git("worktree", "list", "--porcelain", cwd=source)
        answer = answer or {}
        return all([
            check(seen, "close --force answers ok", code == 0 and answer.get("ok") is True, out[:400]),
            check(seen, "the worktrees and branches are listed as kept",
                  [str(path) for path in answer.get("worktrees", [])] == [str(tree)]
                  and answer.get("branches") == [branch], answer),
            check(seen, "no pane was closed by close", answer.get("pane_closed") is False, answer.get("pane_closed")),
            check(seen, "git worktree list of D-SRC is unchanged", before == after, {"before": before, "after": after}),
            check(seen, "the branch stays", branch in git("branch", "--list", "--format=%(refname:short)", cwd=source)
                  .splitlines(), branch),
            check(seen, "the state file is gone", not state_file(data, main_pane).exists(), str(state_file(data, main_pane)))])
    tree = world.root / "df-src-worktrees" / "feat-afkv2-df-live"
    skill_file(tree).parent.mkdir(parents=True)
    skill_file(tree).write_text("# small-change\n", encoding="utf-8")
    local, tab, main_pane, pane = shell_world(world)
    data = Path(local) / "afkv2"
    path = write_state(data, main_pane, pane, "dogfood-0000", world.root / "df-src", [(tree, "feat/afkv2-df-live")])
    state_before = path.read_bytes()
    if row == "VR-034":
        refused = "not-afkv2-pane"
        note = write_note(world, "note", we01_note(tree))
        code, answer, out = in_pane(world, main_pane, ["note", "--note-file", note], "note")
        screen = world.herdr.read(main_pane, 200)
        error = (answer or {}).get("error") or {}
        return all([
            check(seen, "note answers not-afkv2-pane", error.get("code") == refused, answer),
            check(seen, "exit 1", code == 1, code),
            check(seen, "no prompt reached the main pane", flat(NOTE_LINE) not in flat(screen), screen[-800:]),
            check(seen, "no note stored or recorded", not notes_folder(data, main_pane).exists()
                  and path.read_bytes() == state_before, sorted(str(item) for item in data.rglob("*")))])
    bad = {"N-NO-PATH": we01_note(tree).replace(f"- {skill_file(tree)} | CK-1 | changed | step 4 says what the round "
                                                f"shows and what the go is\n", ""),
           "N-NO-USE": we01_note(tree).replace("use: Your next small change reads step 4 from this file.\n", "")}
    holds = []
    for code_name, text in bad.items():
        note = write_note(world, code_name.lower(), text)
        code, answer, out = in_pane(world, main_pane, ["check-note", "--note-file", note], code_name.lower())
        answer = answer or {}
        failures = answer.get("failures") or []
        holds += [check(seen, f"{code_name}: note-check-failed, exit 1",
                        (answer.get("error") or {}).get("code") == "note-check-failed" and code == 1, out[:400]),
                  check(seen, f"{code_name}: the failure names its code, where and reason",
                        any(item.get("code") == code_name and item.get("where") and item.get("reason") for item in failures)
                        and all({"code", "where", "reason"} <= set(item) for item in failures), failures)]
    holds.append(check(seen, "the notes folder and the state file are unchanged",
                       not notes_folder(data, main_pane).parent.exists() and path.read_bytes() == state_before,
                       sorted(str(item) for item in data.rglob("*"))))
    return all(holds)


def queue_row(world, row):
    """VR-023 to VR-026: a note sent during a busy turn of the main agent; VR-025 and VR-026 then press Ctrl+Enter."""
    harness = "codex" if row in ("VR-024", "VR-026") else "claude"
    seen = world.seen
    found = stand_in(world, harness)
    main, main_pane = found["main"], found["main_pane"]
    token = f"TURN-DONE-{secrets.token_hex(3)}"
    sleep = f'"{world.python.as_posix()}" -c "import time; time.sleep({BUSY_S})"'
    world.prompt(main, f"Run this shell command {BUSY_STEPS} times, one after the other, each in its own tool call, and "
                       f"wait for each to finish: {sleep}. Then reply with only the word {token}.")
    harness_up(world, main)
    busy = wait_for(lambda: world.status(main) == "working" and any(event["kind"] == "tool" for event in events(world, main)),
                    90)
    started = time.monotonic()
    note = write_note(world, "note", we01_note(found["tree"]))
    code, answer = as_pane(world, found["pane"], "note", "--note-file", note)
    queued_screen = world.herdr.read(main_pane, 40, "visible")
    if row in ("VR-025", "VR-026"):
        pause(2)
        keys = world.herdr.call("pane", "send-keys", main_pane, "ctrl+enter")
        seen["ctrl_enter"] = {"exit": keys[0], "answer": str(keys[2])[:300]}
    end = wait_turn_end(world, main, BUSY_S * BUSY_STEPS + TURN_LIMIT_S)
    seen["turn_seconds"] = round(time.monotonic() - started, 1)

    def taken():
        found_now = events(world, main)
        at = first(found_now, "user", NOTE_LINE)
        return found_now if at is not None and any(event["kind"] in ("text", "tool") for event in found_now[at + 1:]) else None

    session_events = wait_for(taken, TURN_LIMIT_S) or events(world, main)
    wait_turn_end(world, main)
    session_events = events(world, main)
    asked = first(session_events, "user", token)
    done_at = first(session_events, "text", token, (asked or 0) + 1)
    note_at = first(session_events, "user", NOTE_LINE)
    turn_text = " ".join(event["text"] for event in session_events[(asked or 0) + 1:(done_at or 0)])
    seen["order"] = {"asked": asked, "turn_end_text": done_at, "note_prompt": note_at,
                     "queued": bool(note_at is not None and session_events[note_at].get("queued"))}
    holds = [check(seen, "the main agent was in a working turn with a tool call when the note went", busy, busy),
             check(seen, "note answers ok", code == 0 and (answer or {}).get("ok"), answer)]
    if row in ("VR-023", "VR-024"):
        holds += [check(seen, "the main pane shows the 1-line prompt as queued input",
                        flat(NOTE_LINE).lower() in flat(queued_screen).lower(), queued_screen[-1200:]),
                  check(seen, "the current turn ends with no mention of the note",
                        done_at is not None and (note_at is None or note_at > done_at)
                        and "note" not in turn_text.lower(), seen["order"]),
                  check(seen, "the main agent takes the note as its next turn",
                        note_at is not None and done_at is not None and note_at > done_at
                        and any(event["kind"] in ("text", "tool") for event in session_events[note_at + 1:]),
                        seen["order"])]
    else:
        holds += [check(seen, "Ctrl+Enter was sent", seen["ctrl_enter"]["exit"] == 0, seen["ctrl_enter"]),
                  check(seen, "the main agent takes the note inside the current turn, before that turn ends",
                        note_at is not None and done_at is not None and note_at < done_at, seen["order"])]
    holds.append(check(seen, "D-WORK is clean", porcelain(found["work"]) == "", porcelain(found["work"])))
    return all(holds) and end is not None


def apply_note(world, found, text, name="note"):
    """Send a milestone note as the afkv2 pane, wait for the main agent's apply turn, and answer
    (verb answer, events, index of the note prompt)."""
    note = write_note(world, name, text)
    code, answer = as_pane(world, found["pane"], "note", "--note-file", note)
    pause(POLL_S)
    wait_turn_end(world, found["main"], TURN_LIMIT_S * 2)
    found_now = events(world, found["main"])
    path = (answer or {}).get("path") or ""
    at = next((index for index in range(len(found_now) - 1, -1, -1) if found_now[index]["kind"] == "user"
               and flat(path).lower() in flat(found_now[index]["text"]).lower().replace("\\\\", "\\")), None)
    return code, answer, found_now, at


def checked_note(found_now, at):
    """The check-note calls after the note prompt, and their results."""
    calls = [index for index in range(at + 1, len(found_now)) if found_now[index]["kind"] == "tool"
             and "check-note" in found_now[index]["text"]]
    results = [found_now[index + 1]["text"] for index in calls if index + 1 < len(found_now)
               and found_now[index + 1]["kind"] == "result"]
    return calls, results


def we03_row(world, row):
    """VR-029 and VR-030: the main agent is at step 6 of a throwaway small change in D-WORK when the WE-03 note
    arrives."""
    harness = "codex" if row == "VR-030" else "claude"
    seen = world.seen
    found = stand_in(world, harness)
    main = found["main"]
    tree = found["tree"]
    edit_step(skill_file(tree), 3, STEP3_LINE)
    hooks = Path(tree) / "afkv2" / "hooks" / "hooks.json"
    body = json.loads(hooks.read_text(encoding="utf-8"))
    body["description"] = "afkv2 hooks; the session start hook prints the test plan rule"
    hooks.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    commit_all(tree, "Write the test plan of step 3 as a table")
    ask = "Add the line 'Run make test to test.' to README.md, as a small enhancement."
    text = f"/afkv2:small-change {ask}" if harness == "claude" else \
        f"Use the small-change skill in {found['source'] / 'afkv2' / 'skills' / 'small-change' / 'SKILL.md'}: {ask}"
    since = time.time()
    world.prompt(main, text)
    harness_up(world, main)
    agent = world.herdr.agent(main)

    def at_step6():
        return any(event["kind"] == "result" and '"go"' in event["text"] and '"ok": true' in event["text"]
                   for event in events(world, main))

    reached = drive(world, agent, at_step6, SESSION_LIMIT_S, since)
    holds = [check(seen, "the main agent reached step 6 (the go is on record)", reached, reached)]
    if not reached:
        return False
    wait_turn_end(world, main, TURN_LIMIT_S * 2)
    code, answer, found_now, at = apply_note(world, found, we03_note(tree), "we03")
    note_text = we03_note(tree)
    told = said_after(found_now, at) if at is not None else ""
    reads = [event for event in tools_after(found_now, at or 0) if flat(str(skill_file(tree))).lower().replace("\\", "/")
             in flat(event["text"]).lower().replace("\\\\", "/").replace("\\", "/")]
    holds += [check(seen, "the note holds a redo line for the step-3 test plan and a best-effort line for the hook",
                    "redo: the test plan of step 3" in note_text and f"best-effort: {hooks}" in note_text
                    and code == 0, answer),
              check(seen, "the main agent took the note", at is not None, at),
              check(seen, "it reads step 3 from the worktree", bool(reads), [event["text"][:200] for event in reads[:3]]),
              check(seen, "it says it follows the new text from now on",
                    re.search(r"new text|from now on|switch|now follow", told, re.I), told[-1500:]),
              check(seen, "it shows the step-3 test plan rewritten as the table",
                    re.search(r"test plan", told, re.I) and re.search(r"level", told, re.I)
                    and re.search(r"redo|redid|rewr|again", told, re.I), told[-1500:]),
              check(seen, "it names the hook part best effort, as maybe not applying in this session",
                    re.search(r"best.effort", told, re.I) and re.search(r"(may not|might not|not) appl", told, re.I),
                    told[-1500:]),
              check(seen, "it asked the developer nothing about the redo",
                    not re.search(r"\b(shall|should|do you want|want me to)\b[^\n]*\bredo", told, re.I), told[-600:]),
              check(seen, "D-WORK holds only the work of the small change", True, porcelain(found["work"]))]
    return all(holds)


def path_missing_row(world):
    """VR-031: the note names a file that the afkv2 side deletes before the main agent's turn ends."""
    seen = world.seen
    found = stand_in(world, "claude", receiver=True, prime=True)
    gone = skill_file(found["tree"], "gc")
    text = we01_note(found["tree"]).replace("redo: none", "redo: none").replace(
        "changed:\n", f"changed:\n- {gone} | CK-1 | changed | the gc refusal text is clear\n")
    note = write_note(world, "note", text)
    before = len(user_prompts(events(world, found["agent"]), FEEDBACK_LINE))
    code, answer = as_pane(world, found["pane"], "note", "--note-file", note)
    gone.unlink()
    wait_turn_end(world, found["main"], TURN_LIMIT_S * 2)
    found_now = events(world, found["main"])
    at = first(found_now, "user", NOTE_LINE)
    calls, results = checked_note(found_now, at or 0)
    applied = [event for event in tools_after(found_now, at or 0) if event.get("name") in ("Read", "Skill")
               and flat(str(found["tree"])).lower().replace("\\", "/")
               in flat(event["text"]).lower().replace("\\\\", "/").replace("\\", "/")]
    feedback = wait_for(lambda: user_prompts(events(world, found["agent"]), FEEDBACK_LINE)[before:], 60) or []
    return all([
        check(seen, "note answers ok", code == 0, answer),
        check(seen, "the main agent runs check-note", calls, len(calls)),
        check(seen, "check-note answers N-PATH-MISSING", any("N-PATH-MISSING" in result for result in results),
              [result[:400] for result in results]),
        check(seen, "the main agent applies nothing", not applied, [event["text"][:200] for event in applied]),
        check(seen, "the afkv2 pane receives 1 tell --kind feedback that asks for a complete note",
              len(feedback) == 1 and re.search(r"complete|N-PATH-MISSING|again|resend", feedback[0]["text"], re.I),
              [event["text"][:600] for event in feedback])])


def target_row(world):
    """VR-033: the main pane, the afkv2 pane and a bystander shell pane; note reaches only the main pane."""
    seen = world.seen
    found = stand_in(world, "claude")
    split = world.herdr.ok("pane", "split", "--pane", found["main_pane"], "--direction", "down", "--cwd",
                           str(world.root), "--no-focus")
    bystander = (split.get("pane") or {}).get("pane_id")
    pause(3)
    before = world.herdr.read(bystander, 200)
    afkv2_before = world.herdr.read(found["pane"], 200)
    note = write_note(world, "note", we01_note(found["tree"]))
    code, answer = as_pane(world, found["pane"], "note", "--note-file", note)
    pause(POLL_S)
    main_screen = world.herdr.read(found["main_pane"], 200)
    taken = wait_for(lambda: first(events(world, found["main"]), "user", NOTE_LINE) is not None, 60)
    after = world.herdr.read(bystander, 200)
    target_code, target = as_pane(world, found["pane"], "note", "--note-file", note, "--target", bystander)
    wait_turn_end(world, found["main"])
    return all([
        check(seen, "note answers ok", code == 0 and (answer or {}).get("ok"), answer),
        check(seen, "the main pane shows the 1-line prompt", taken or flat(NOTE_LINE) in flat(main_screen),
              main_screen[-800:]),
        check(seen, "herdr pane read of the bystander pane is unchanged", before == after, {"before": before[-300:],
                                                                                           "after": after[-300:]}),
        check(seen, "the afkv2 pane shows no prompt", flat(NOTE_LINE) not in flat(world.herdr.read(found["pane"], 200))
              and afkv2_before is not None, None),
        check(seen, "note --target <pane> refuses as an unknown argument",
              target_code == 2 and ((target or {}).get("error") or {}).get("code") == "usage", target)])


def isolation_row(world):
    """VR-035: the installed plugin and the worktrees stay unchanged after the WE-01 and WE-03 applies, and a new
    Claude session in D-WORK reads the installed small-change text."""
    seen = world.seen
    hashes = plugin_hashes()
    found = stand_in(world, "claude")
    tree = found["tree"]
    head_before = git("rev-parse", "HEAD", cwd=tree)
    code1, _, events1, at1 = apply_note(world, found, we01_note(tree), "we01")
    edit_step(skill_file(tree), 3, STEP3_LINE)
    hooks = Path(tree) / "afkv2" / "hooks" / "hooks.json"
    hooks.write_text(hooks.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
    commit_all(tree, "Write the test plan of step 3 as a table")
    head_before = git("rev-parse", "HEAD", cwd=tree)
    code3, _, events3, at3 = apply_note(world, found, we03_note(tree), "we03")
    writes = [event for event in events3 if event["kind"] == "tool" and event.get("name") in live.EDIT_TOOLS
              and re.search(r"afkv2|plugins", event["text"], re.I)]
    after = plugin_hashes()
    changed = sorted(path for path in set(hashes) | set(after) if hashes.get(path) != after.get(path))
    tab, pane = world.open_tab(found["work"])
    fresh = f"dffresh-{secrets.token_hex(2)}"
    world._start(fresh, "claude", pane, ["--permission-mode", "auto"])
    turn(world, fresh, "Invoke the Skill tool with the skill afkv2:small-change and the args 'look only'. Then stop at "
                       "once: run no step of it, and reply with only the word LOOKED.")
    base_lines = [event["text"].splitlines()[0] for event in events(world, fresh) if event["kind"] == "user"
                  and event["text"].startswith("Base directory for this skill")]
    installed = [root for root in {str(Path(path).parents[0]) for path in hashes} if "small-change" in root]
    return all([
        check(seen, "both notes went and were taken", code1 == 0 and code3 == 0 and at1 is not None and at3 is not None,
              {"we01": at1, "we03": at3}),
        check(seen, "every installed file hash is the same", hashes and not changed, changed[:20]),
        check(seen, "the worktree shows no change by the main agent",
              porcelain(tree) == "" and git("rev-parse", "HEAD", cwd=tree) == head_before and not writes,
              {"status": porcelain(tree), "writes": [event["text"][:200] for event in writes]}),
        check(seen, "a new Claude session in D-WORK reads the installed small-change text",
              base_lines and "plugins" in base_lines[-1] and flat(str(tree)).lower() not in flat(base_lines[-1]).lower(),
              {"base": base_lines, "installed": installed[:2]}),
        check(seen, "D-WORK is clean", porcelain(found["work"]) == "", porcelain(found["work"]))])


def trial_row(world, row):
    """VR-044 and VR-064: the WE-01 change is applied, a trial of it printed an error, and the developer tells the
    main agent that the trial failed."""
    harness = "codex" if row == "VR-064" else "claude"
    seen = world.seen
    found = stand_in(world, harness, receiver=True, prime=True)
    code, _, _, at = apply_note(world, found, we01_note(found["tree"]))
    before = len(user_prompts(events(world, found["agent"]), FEEDBACK_LINE))
    words = "I tried the new step 4 in a small change and the trial failed."
    turn(world, found["main"], f"{words} It printed:\n{TRIAL_ERROR}", TURN_LIMIT_S * 2)
    feedback = wait_for(lambda: user_prompts(events(world, found["agent"]), FEEDBACK_LINE)[before:], 60) or []
    body = feedback[0]["text"] if feedback else ""
    return all([
        check(seen, "the WE-01 note was applied", code == 0 and at is not None, at),
        check(seen, "the afkv2 pane receives 1 prompt", len(feedback) == 1, [event["text"][:800] for event in feedback]),
        check(seen, "it holds the developer's words", re.search(r"trial", body, re.I) and re.search(r"fail", body, re.I),
              body[:800]),
        check(seen, "it holds the error text as it was printed", flat(TRIAL_ERROR) in flat(body), body[:800])])


def feedback_row(world):
    """VR-045: the developer types feedback in the afkv2 pane."""
    seen = world.seen
    found = session(world, "claude", ASK_WE01)
    afkv2 = found["afkv2"]
    if not afkv2:
        return check(seen, "the afkv2 pane opens", False, None)
    world.wait_status(afkv2["name"], ("working",), 120)
    main_before = events(world, found["main"])
    words = "Feedback: keep the new text of step 4 to at most 3 sentences."
    world.reply(afkv2["name"], words)

    def acted():
        found_now = events(world, afkv2["name"])
        at = first(found_now, "user", words)
        return found_now if at is not None and any(event["kind"] in ("text", "tool") for event in found_now[at + 1:]) else None

    afkv2_events = wait_for(acted, TURN_LIMIT_S) or []
    main_after = events(world, found["main"])
    new = main_after[len(main_before):]
    return all([
        check(seen, "the afkv2 agent acts on it in its next turn", afkv2_events, len(afkv2_events)),
        check(seen, "the main pane shows no prompt", not [event for event in new if event["kind"] == "user"
                                                          and not event["text"].startswith(NOTE_LINE)],
              [event["text"][:200] for event in new if event["kind"] == "user"]),
        check(seen, "the main agent's tool log shows no dogfood.py call",
              not [event for event in new if event["kind"] == "tool" and "dogfood.py" in event["text"]],
              [event["text"][:200] for event in new if event["kind"] == "tool"]),
        check(seen, "D-WORK is clean", porcelain(found["work"]) == "", porcelain(found["work"]))])


def milestone_row(world, row):
    """VR-027 and VR-028: the WE-01 session; after the afkv2 agent commits the step-4 edit, the note comes and the
    main agent applies it with no developer input."""
    harness = "codex" if row == "VR-028" else "claude"
    seen = world.seen
    hashes = plugin_hashes()
    found = session(world, harness, ASK_WE01)
    afkv2 = found["afkv2"]
    if not afkv2:
        return check(seen, "the afkv2 pane opens", False, None)
    main_pane, source = found["main_pane"], found["source"]

    def committed():
        small = small_branch(world, main_pane)
        return small and ahead(source, small["branch"])

    built = drive(world, afkv2, committed, SESSION_LIMIT_S, world.started)
    small = small_branch(world, main_pane) or {}
    note = wait_for(lambda: note_record(world, main_pane, 1), MILESTONE_LIMIT_S, POLL_S * 2)
    text = note.read_text(encoding="utf-8") if note else ""
    path = str(skill_file(small.get("path", "?")))
    wait_turn_end(world, found["main"], TURN_LIMIT_S * 2)
    main_events = events(world, found["main"])
    at = first(main_events, "user", NOTE_LINE)
    told = said_after(main_events, at) if at is not None else ""
    calls, _ = checked_note(main_events, at or 0)
    holds = [check(seen, "the afkv2 agent commits the step-4 edit", built, ahead(source, small.get("branch", "?"))),
             check(seen, "notes/0001.md appears with no developer input after the commit", note is not None, str(note)),
             check(seen, "it names <worktree>/afkv2/skills/small-change/SKILL.md and a use line",
                   flat(path).lower() in flat(text).lower() and re.search(r"^use: \S", text, re.M), text[:1500]),
             check(seen, "the main agent runs check-note", calls, len(calls)),
             check(seen, "the main pane says it applied the small-change update and that the next small change uses it",
                   re.search(r"appl", told, re.I) and "small-change" in told.lower() and re.search(r"next", told, re.I),
                   told[-1500:]),
             check(seen, "D-WORK is clean", porcelain(found["work"]) == "", porcelain(found["work"])),
             check(seen, "the installed plugin is unchanged", plugin_hashes() == hashes, None)]
    if harness == "codex":
        later = [event for event in tools_after(main_events, at or 0) if "small-change" in event["text"]]
        holds.append(check(seen, "its next small change reads the worktree SKILL.md",
                           any(flat(str(small.get("path", "?"))).lower().replace("\\", "/")
                               in flat(event["text"]).lower().replace("\\\\", "/").replace("\\", "/") for event in later),
                           [event["text"][:200] for event in later]))
    return all(holds)


def queue_ask_row(world, row):
    """VR-047, VR-048 and VR-050: WE-02, a second ask while the first is half built, then the Draft change and the
    wrap-up."""
    seen = world.seen
    found = session(world, "claude", ASK_WE02_1)
    afkv2 = found["afkv2"]
    if not afkv2:
        return check(seen, "the afkv2 pane opens", False, None)
    main, main_pane, source = found["main"], found["main_pane"], found["source"]
    name = afkv2["name"]
    world.wait_status(name, ("working",), 120)
    turn(world, main, f"/afkv2:dogfood {ASK_WE02_2}")
    sent_at = time.time()
    holds = []
    queued = wait_for(lambda: (lambda found_now: (lambda at: at is not None and re.search(
        r"queue", said_after(found_now, at), re.I))(first(found_now, "user", FORWARD_LINE)))(events(world, name)), 300)
    holds.append(check(seen, "the afkv2 pane says ask 2 is queued", queued, None))
    note1 = drive(world, afkv2, lambda: note_record(world, main_pane, 1), SESSION_LIMIT_S, world.started)
    small = small_branch(world, main_pane) or {}
    state = world.state(world.real_data(), main_pane) or {}
    first_note = next((note for note in state.get("notes", []) if note["id"] == 1), {})
    holds.append(check(seen, "milestone 1 comes: notes/0001.md exists", note1, first_note))
    if row == "VR-047":
        sent = first_note.get("sent_at", "")
        early = [commit for commit in ahead(source, small.get("branch", "?"))
                 if time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(int(commit[1]))) < sent
                 and any("/gc/" in path for path in files_of(source, commit[0]))]
        afkv2_events = events(world, name)
        note_call = next((index for index in range(len(afkv2_events)) if afkv2_events[index]["kind"] == "tool"
                          and "dogfood.py" in afkv2_events[index]["text"] and " note " in afkv2_events[index]["text"]), None)
        started2 = note_call is not None and any("gc" in event["text"].lower() for event in afkv2_events[note_call + 1:]
                                                 if event["kind"] in ("tool", "text"))
        holds += [check(seen, "the small branch has no ask-2 commit before notes/0001.md", note1 and not early, early),
                  check(seen, "the afkv2 agent starts ask 2 right after that note", wait_for(
                      lambda: (lambda found_now, at: at is not None and any(
                          "gc" in event["text"].lower() for event in found_now[at + 1:] if event["kind"] in ("tool", "text")))(
                          events(world, name), note_call), 600) if note_call is not None else started2, note_call),
                  check(seen, "the afkv2 pane stays open after the note",
                        any(pane["pane_id"] == afkv2["pane_id"] for pane in world.herdr.panes(found["tab"])), None)]
        return all(holds)
    if row == "VR-048":
        note2 = drive(world, afkv2, lambda: note_record(world, main_pane, 2), SESSION_LIMIT_S, world.started)
        changes = [change for change in world.changes("all") if change["headRefName"] == small.get("branch")]
        body = (changes[0]["body"] if changes else "").lower()
        holds += [check(seen, "milestone 2 comes: notes/0002.md exists", note2, None),
                  check(seen, f"1 Draft change from the 1 small-asks branch into {BASE}",
                        len(changes) == 1 and changes[0]["isDraft"] and len(world.changes("all")) == 1,
                        [{key: change[key] for key in ("number", "url", "isDraft", "headRefName")} for change in changes]),
                  check(seen, "1 section per ask", "ticket" in body and "review page" in body and "gc" in body
                        and body.count("\n## ") + body.startswith("## ") >= 2, body[:1500])]
        return all(holds)
    turn(world, main, "The main work is done.", TURN_LIMIT_S * 2)
    closed = wait_for(lambda: not any(pane["pane_id"] == afkv2["pane_id"] for pane in world.herdr.panes(found["tab"])),
                      WRAP_LIMIT_S, POLL_S * 3)
    wait_turn_end(world, main, TURN_LIMIT_S * 2)
    main_events = events(world, main)
    wrap_at = first(main_events, "user", "The main work is done")
    told = said_after(main_events, wrap_at or 0)
    changes = world.changes("all")
    url = changes[0]["url"] if changes else "(none)"
    branches = git("branch", "--list", "--format=%(refname:short)", cwd=source).splitlines()
    worktrees = git("worktree", "list", "--porcelain", cwd=source)
    data = world.real_data()
    holds += [check(seen, "the afkv2 agent pushed and updated the Draft change",
                    len(changes) == 1 and changes[0]["isDraft"] and git("ls-remote", "--heads", world.remote,
                                                                        small.get("branch", "?"), cwd=source), changes),
              check(seen, "the main pane reports the change URL and the open ask",
                    url in told and re.search(r"gc", told, re.I), told[-1500:]),
              check(seen, "the afkv2 pane closes", closed, None),
              check(seen, "D-SRC still lists each dogfood worktree and branch",
                    small.get("branch") in branches and flat(small.get("path", "?")).lower().replace("\\", "/")
                    in flat(worktrees).lower().replace("\\", "/"), {"branches": branches}),
              check(seen, "the Draft change is not merged", changes and not changes[0].get("mergedAt"), changes),
              check(seen, "D-WORK is clean", porcelain(found["work"]) == "", porcelain(found["work"])),
              check(seen, "the state file and the notes folder are gone",
                    not state_file(data, main_pane).exists() and not notes_folder(data, main_pane).exists(), None)]
    return all(holds)


def wrap_row(world):
    """VR-051: a WE-01 session with a Codex main agent; the developer says the main work is done."""
    seen = world.seen
    found = session(world, "codex", ASK_WE01)
    afkv2 = found["afkv2"]
    if not afkv2:
        return check(seen, "the afkv2 pane opens", False, None)
    main_pane = found["main_pane"]
    drive(world, afkv2, lambda: note_record(world, main_pane, 1), SESSION_LIMIT_S, world.started)
    turn(world, found["main"], "The main work is done.", TURN_LIMIT_S * 2)
    closed = wait_for(lambda: not any(pane["pane_id"] == afkv2["pane_id"] for pane in world.herdr.panes(found["tab"])),
                      WRAP_LIMIT_S, POLL_S * 3)
    main_events = events(world, found["main"])
    tools = [event["text"] for event in main_events if event["kind"] == "tool"]
    wrap = next((index for index, text in enumerate(tools) if "tell" in text and "wrap" in text), None)
    close = next((index for index, text in enumerate(tools) if "dogfood.py" in text and " close" in text), None)
    return all([
        check(seen, "the main agent sends the wrap", wrap is not None, tools[-6:]),
        check(seen, "it reports the wrap note", first(main_events, "user", NOTE_LINE) is not None, None),
        check(seen, "then it runs close", close is not None and wrap is not None and close > wrap, {"wrap": wrap, "close": close}),
        check(seen, "the afkv2 pane closes", closed, None)])


def run_row(world, row):
    if row in SHELL_ROWS:
        return shell_row(world, row)
    if row in ("VR-023", "VR-024", "VR-025", "VR-026"):
        return queue_row(world, row)
    if row in ("VR-027", "VR-028"):
        return milestone_row(world, row)
    if row in ("VR-029", "VR-030"):
        return we03_row(world, row)
    if row == "VR-031":
        return path_missing_row(world)
    if row == "VR-033":
        return target_row(world)
    if row == "VR-035":
        return isolation_row(world)
    if row in ("VR-044", "VR-064"):
        return trial_row(world, row)
    if row == "VR-045":
        return feedback_row(world)
    if row in ("VR-047", "VR-048", "VR-050"):
        return queue_ask_row(world, row)
    return wrap_row(world)


def run_milestone_row(row, env=None, stamp=None):
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
            world = Run(row, env, stamp)
            passed = run_row(world, row)
            for agent in [world.seen.get("main_agent", {}).get("name")]:
                if not passed and agent:  # a usage limit that showed after the last turn check: the row did not run
                    harness_up(world, agent)
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
    finally:  # also on an interrupt: the tab, the state, the record, the forge and the scratch folder go
        cleanup = world.clean_up() if world is not None else []
    answer["cleanup"] = cleanup
    answer["seconds"] = round(time.monotonic() - started, 1)
    if any(entry["result"] == "failed" for entry in cleanup):
        answer["ok"], answer["passed"] = False, False
        answer.setdefault("error", {"code": "cleanup-failed", "reason": "the end left items; delete them by hand"})
    if world is not None:
        live._keep(world, env, answer)
    return answer


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dogfood_live_milestone.py")
    parser.add_argument("--row", required=True)
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        print(json.dumps({"ok": False, "error": {"code": "bad-input", "reason": "usage: --row VR-NNN"}}))
        return 2
    answer = run_milestone_row(args.row)
    print(json.dumps(answer, indent=1, default=str))
    if not answer["ok"] and (answer.get("error") or {}).get("code") == "bad-input":
        return 2
    return 0 if answer["ok"] and answer.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
