"""The team entry script's logic: one JSON object in, one JSON object out, for every command agents call.

The six transport verbs (agent-start, agent-send, agent-status, agent-read, agent-stop, agent-list) and the run's
own commands run-open and wait (plan D-116). A call names its run by `run`, else AFK_TEAM_RUN; the run directory
is `<main checkout>/.claude/afk-team/<run>` (plan D-113), its files named by plan D-115. Exit codes: 0 done;
2 a bad payload or a refused check (error true, operation, reason); 3 unsupported; 4 unavailable; 5 an agent
started but the write after its transport call failed, so the script stopped it (SDD §3 agent-start).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from team import manifest, naming, permission, probe, resolver  # noqa: E402
import contract  # noqa: E402  (on the path through team.probe)
import launch  # noqa: E402
import process  # noqa: E402
import worktree_owner  # noqa: E402

PLUGIN = Path(__file__).resolve().parents[2]
SUPERVISOR = PLUGIN / "scripts" / "team" / "supervisor.py"
INBOX_WAIT = PLUGIN / "hooks" / "inbox-wait.sh"
FORMAT_VERSION = 1
CONTACT = "contact"
LIFECYCLE = ("finished", "parked", "exited")
LIVE = ("starting", "working", "parked")
WAIT_LABEL = "inbox wait"
START_BUDGET_S = contract.BUDGET_MS["agent-start"] / 1000
STOP_RESERVE_S = 5
SAFE = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")
ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
# Effort as the start names it -> (Claude Code value, Codex value); plan D-117
EFFORTS = {"lo": ("low", "low"), "med": ("medium", "medium"), "hi": ("high", "high"), "max": ("max", "xhigh")}
TIER_EFFORTS = {"low": "lo", "medium": "med", "high": "hi", "xhigh": "max"}
# Launch flags per harness: a Codex agent runs with full access, a Claude agent reads the user's settings; plan D-124
LAUNCH_ARGS = {"claude": (), "codex": ("--dangerously-bypass-approvals-and-sandbox",)}
ABILITIES = {"multiplexer": resolver.ABILITIES, "headless": ("worker-to-contact", "exit-signal", "limit-signal")}
# The launch-only values a started agent's environment carries (SDD §13 V39, Q54)
AFK_PROVIDER = "AFK_PROVIDER"
AFK_CHARTER_FILE = "AFK_CHARTER_FILE"
AFK_TEAM_RUN = "AFK_TEAM_RUN"


def _git_common(cwd: Path) -> Path:
    done = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                          capture_output=True, encoding="utf-8", errors="replace", timeout=30)
    if done.returncode != 0 or not done.stdout.strip():
        raise contract.unavailable(f"{cwd} is not inside a git repository, so the run has no main checkout")
    return Path(done.stdout.strip())


@dataclass
class Host:
    """What a run uses around it: its folders, the transport, the permission check and the configuration."""

    root: Path
    main: Path
    cwd: Path
    env: dict
    dispatch: Callable = probe.dispatch
    resolve_kind: Callable = probe.resolve_kind
    check_permission: Callable = permission.check_spawn_permission
    config: Callable[[str], object] | None = None
    providers: Path = PLUGIN / "PROVIDERS.md"
    clock: Callable[[], float] = time.monotonic
    tiers: dict = field(default_factory=dict)

    @classmethod
    def discover(cls, cwd: Path | None = None, env: Mapping[str, str] | None = None) -> "Host":
        cwd = Path(cwd or Path.cwd())
        env = dict(os.environ if env is None else env)
        common = _git_common(cwd)
        main = common.parent if common.name == ".git" else common
        root = Path(env["AFK_TEAM_ROOT"]) if env.get("AFK_TEAM_ROOT") else main / ".claude" / "afk-team"
        return cls(root=root, main=main, cwd=cwd, env=env)

    def setting(self, key: str) -> object:
        """One configured value through the configuration reader; None when absent."""
        if self.config is not None:
            return self.config(key)
        done = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "afk-config.py"), "get", key],
                              cwd=str(self.cwd), capture_output=True, text=True, timeout=30, env=self.env)
        if done.returncode == 1 and not done.stderr.strip():
            return None
        if done.returncode != 0:
            raise contract.unavailable(f"the configuration reader failed on {key}: {done.stderr.strip()[:300]}")
        text = done.stdout.strip()
        return json.loads(text) if text[:1] in "{[" else text

    def model_tiers(self) -> dict:
        if not self.tiers:
            self.tiers = model_tiers(self.providers)
        return self.tiers


def model_tiers(providers: Path) -> dict:
    """PROVIDERS.md "Model tiers": {"tiers": {tier: {claude, codex, effort}}, "agents": {agent: tier}}."""
    tiers, agents, header, inside = {}, {}, None, False
    for line in providers.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside, header = line.strip() == "## Model tiers", None
            continue
        if not line.startswith("|"):
            header = None
            continue
        if not inside:
            continue
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        row = dict(zip(header, cells))
        if "Claude Code" in row:
            tiers[row["Tier"].lower()] = {"claude": row["Claude Code"], "codex": row["Codex CLI"],
                                          "effort": row.get("Codex effort", "")}
        elif "Agent" in row:
            agents[row["Agent"]] = row["Tier"].lower()
    return {"tiers": tiers, "agents": agents}


def _fields(p: contract.Payload, allowed: tuple[str, ...]) -> None:
    extra = sorted(set(p.data) - set(allowed) - {"run"})
    if extra:
        raise contract.bad(p.verb, f"field `{extra[0]}` is not a field of {p.verb}")


def _safe(p: contract.Payload, key: str, required: bool = True) -> str | None:
    value = p.text(key, required)
    if value is not None and not SAFE.fullmatch(value):
        raise contract.bad(p.verb, f"field `{key}`: {value!r} may hold only letters, digits, '.', '_' and '-'")
    return value


def _publish(path: Path, data: bytes) -> None:
    """Write `data` under a temporary name the wait job skips, then rename it to `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _json(data: dict) -> bytes:
    return (json.dumps(data, sort_keys=True) + "\n").encode("utf-8")


class Run:
    """One team run: its feature identifier and its folder."""

    def __init__(self, host: Host, feature: str):
        self.host, self.feature = host, feature
        self.dir = host.root / feature
        self.inbox, self.processed = self.dir / "inbox", self.dir / "processed"

    def manifest(self, required: bool = True) -> dict | None:
        try:
            found = manifest.read_manifest(self.host.root, self.feature)
        except manifest.ForeignManifest as foreign:
            raise contract.unavailable(str(foreign)) from None
        if found is None and required:
            raise contract.bad("", f"run {self.feature} has no manifest; run-open opens it")
        return found

    def pattern(self) -> dict | None:
        path = resolver.resolved_path(self.host.root, self.feature)
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def charter(self, role: str) -> Path:
        return self.dir / "charters" / f"{role}.md"

    def permitted(self) -> None:
        """The spawn permission check, once per run, before its first transport command (plan D-121)."""
        record = self.dir / "permission.json"
        if record.is_file():
            return
        check = self.host.check_permission(self.host.cwd, env=self.host.env)
        if not check.get("ok"):
            raise contract.unavailable(check.get("says", "the spawn permission check refused"),
                                       **{k: check.get(k) for k in ("provider", "rule", "problem")})
        _publish(record, _json(check))

    def kind(self) -> str:
        found = self.host.resolve_kind(self.host.cwd, env=self.host.env)
        if found.get("conflict"):
            raise contract.unavailable(found["conflict"]["detail"], conflict=found["conflict"]["name"])
        return found["kind"]

    def transport(self, kind: str, verb: str, payload: dict) -> tuple[int, dict]:
        self.permitted()
        code, out, err = self.host.dispatch(kind, verb, payload, root=self.host.cwd, env=self.host.env)
        try:
            body = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
        except ValueError:
            body = {}
        if not isinstance(body, dict) or (not body and code != 0):
            body = {"unavailable": True, "reason": f"{verb} answered no JSON object: {(err or out).strip()[:300]}"}
            code = code or 4
        return code, body


def write_charter_files(run_dir: Path, charters: Mapping[str, str]) -> dict:
    """One charter file per role in the run directory, the pattern part then the role's part; role -> path."""
    written = {}
    for role, text in charters.items():
        path = run_dir / "charters" / f"{role}.md"
        _publish(path, text.encode("utf-8"))
        written[role] = str(path)
    return written


def build_launch_prompt(brief_path: str, charter: Path | None, identity: str) -> str:
    """The launch prompt: the role's charter file before the brief, then who the agent is; one line."""
    parts = []
    if charter is not None:
        parts.append(f"Read your charter file first, {charter}: it is your standing instruction for this run.")
    parts.append(f"{'Then read' if charter is not None else 'Read'} your brief, {brief_path}: it is your task.")
    return " ".join([*parts, identity])


def _identity(run: Run, entry: dict) -> str:
    return (f"You are agent {entry['agent_id']}, role {entry['role']}, owner generation {entry['owner_generation']},"
            f" of team run {run.feature}. Send each message with {permission.INVOCATION} agent-send"
            " and one JSON object: agent_id, generation, target, kind, message_id, body_path.")


def _model(host: Host, verb: str, model: str) -> tuple[str, str, str]:
    """`<tier>@<provider>` -> (tier, harness, model cell)."""
    tier, _, harness = model.partition("@")
    found = host.model_tiers()["tiers"].get(tier.lower())
    if found is None or harness not in launch.HARNESSES:
        raise contract.bad(verb, f"field `model`: {model!r} is not <tier>@<provider> with a tier of PROVIDERS.md "
                                 f"\"Model tiers\" and a provider of {', '.join(launch.HARNESSES)}")
    if not found[harness]:
        raise contract.bad(verb, f"field `model`: the {tier} tier names no {harness} model")
    return tier.lower(), harness, found[harness]


def copy_settings(main: Path, worktree: Path) -> str:
    """Copy the main checkout's .claude/settings.local.json into `worktree`, never overwriting; what happened."""
    source, target = main / ".claude" / "settings.local.json", worktree / ".claude" / "settings.local.json"
    if os.path.normcase(os.path.realpath(main)) == os.path.normcase(os.path.realpath(worktree)):
        return "the agent starts in the main checkout, so no settings copy is needed"
    if not source.is_file():
        return f"no copy: the main checkout has no {source.name}"
    if target.exists():
        return f"skipped the copy: {target} exists"
    try:
        data = source.read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "xb") as out:
            try:
                out.write(data)
            except OSError:
                out.close()
                target.unlink(missing_ok=True)
                raise
    except OSError as problem:
        raise contract.unavailable(f"the settings copy to {target} failed, so no agent started: {problem}",
                                   copy=str(target)) from None
    return f"copied {source} to {target}"


def agent_start(run: Run, p: contract.Payload) -> tuple[int, dict]:
    """Start one agent for the entry the contact agent wrote, or a job supervisor when watched_agent_id is set."""
    if "watched_agent_id" in p.data:
        return _start_supervisor(run, p)
    began = run.host.clock()
    _fields(p, ("agent_id", "role", "model", "brief_path", "cwd", "effort", "resume"))
    agent_id, role, model = _safe(p, "agent_id"), p.text("role"), p.text("model")
    brief, cwd, resume = p.text("brief_path"), Path(p.text("cwd")), p.text("resume", False)
    effort = p.text("effort", False)
    data = run.manifest()
    entry = next((a for a in data["agents"] if a["agent_id"] == agent_id), None)
    if entry is None or entry["state"] != "starting":
        state = "no entry" if entry is None else f"an entry in state {entry['state']}"
        raise contract.bad(p.verb, f"agent-id {agent_id} has {state}; agent-start needs an entry in state starting")
    if entry["role"] != role:
        raise contract.bad(p.verb, f"field `role`: {role} is not the role {entry['role']} of entry {agent_id}")
    if effort is not None and effort not in EFFORTS:
        raise contract.bad(p.verb, f"field `effort`: {effort!r} is not one of {', '.join(EFFORTS)}")
    tier, harness, cell = _model(run.host, p.verb, model)
    effort = effort or TIER_EFFORTS.get(run.host.model_tiers()["tiers"][tier]["effort"], "med")
    if not cwd.is_dir():
        raise contract.bad(p.verb, f"field `cwd`: {cwd} is not a folder")
    if not Path(brief).is_file():
        raise contract.bad(p.verb, f"field `brief_path`: {brief} is not a file")
    taken = {v for a in data["agents"] if a["agent_id"] != agent_id for v in (a["pane_label"], a["agent_name"]) if v}
    try:
        label, name = naming.build_agent_name(run.feature, role, cell, effort, taken)
    except naming.NameRefused as refused:
        raise contract.bad(p.verb, str(refused)) from None
    kind = run.kind()
    run.permitted()
    settings = copy_settings(run.host.main, cwd)
    try:
        manifest.record_entry(run.host.root, run.feature, {"agent_id": agent_id, "pane_label": label,
                                                           "agent_name": name})
    except manifest.ManifestError as problem:
        raise contract.unavailable(f"the write of the pane label and agent name into entry {agent_id} failed, "
                                   f"so no agent started: {problem}", write="before the transport call") from None
    charter = run.charter(role)
    charter = charter if charter.is_file() else None
    env = {AFK_PROVIDER: harness, AFK_TEAM_RUN: run.feature, "AFK_PLUGIN_ROOT": str(PLUGIN)}
    if charter is not None:
        env[AFK_CHARTER_FILE] = str(charter)
    payload = {"harness": harness, "name": name, "label": label, "cwd": str(cwd), "model": cell,
               "tab": f"{naming.goal_of(run.feature)} {entry['pattern_step']}",
               "effort": EFFORTS[effort][launch.HARNESSES.index(harness)], "env": env,
               **({"args": list(LAUNCH_ARGS[harness])} if LAUNCH_ARGS[harness] else {}),
               "prompt": build_launch_prompt(brief, charter, _identity(run, entry)),
               "log": str(run.dir / "logs" / f"{agent_id}.log"), **({"resume": resume} if resume else {})}
    (run.dir / "logs").mkdir(parents=True, exist_ok=True)
    code, answer = run.transport(kind, "agent-start", payload)
    if code != 0:
        return code, {**answer, "agent_id": agent_id}
    pid = answer.get("pid") if isinstance(answer.get("pid"), int) else None
    after = {"agent_id": agent_id, **({"pid": pid} if pid is not None else {}),
             **({"session_id": answer["session_id"]} if answer.get("session_id") else {})}
    try:
        manifest.record_entry(run.host.root, run.feature, after)
    except manifest.ManifestError as problem:
        left = START_BUDGET_S - STOP_RESERVE_S - (run.host.clock() - began)
        stop = _stop_within(run, {"transport_kind": kind, "pid": pid, "handle": answer.get("handle"),
                                  "terminal_id": answer.get("terminal_id"),
                                  "started_at": answer.get("started_at")}, left)
        return 5, {**{("stop_reason" if k == "reason" else k): v for k, v in stop.items()},
                   "error": True, "operation": p.verb, "agent_id": agent_id, "pid": pid, "kind": kind,
                   "started_at": answer.get("started_at"),
                   "reason": f"agent {agent_id} started, but the write of its process id and session id failed, "
                             f"so the script stopped it: {problem}",
                   **({"terminal_id": answer["terminal_id"]} if answer.get("terminal_id") else {})}
    if pid is not None:
        try:
            if worktree_owner.add_owner(str(cwd), pid, worktree_owner.creation_time(pid) or "") is None:
                sys.stderr.write(f"afk-team: no owner record names {cwd}; its prune does not wait for {name}\n")
        except (OSError, ValueError, subprocess.SubprocessError) as problem:
            sys.stderr.write(f"afk-team: could not add {name} to the owners of {cwd}: {problem}\n")
    return 0, {**answer, "agent_id": agent_id, "settings": settings}


def _start_supervisor(run: Run, p: contract.Payload) -> tuple[int, dict]:
    _fields(p, ("watched_agent_id",))
    watched = _safe(p, "watched_agent_id")
    data = run.manifest()
    entry = next((a for a in data["agents"] if a["agent_id"] == watched), None)
    if entry is None:
        raise contract.bad(p.verb, f"field `watched_agent_id`: no entry holds agent-id {watched}")
    label = f"{entry['pane_label'] or watched} supervisor"
    for other in data["processes"]:
        if other["label"] == label and _same_process(other["pid"], other["started_at"]) != "gone":
            raise contract.bad(p.verb, f"agent {watched} already has a job supervisor, process {other['pid']}")
    if not SUPERVISOR.is_file():
        raise contract.unavailable(f"the job supervisor {SUPERVISOR} is not installed")
    argv = [sys.executable, str(SUPERVISOR), json.dumps({"run": run.feature, "watched_agent_id": watched})]
    flags = ({"creationflags": 0x00000008 | 0x00000200} if process.WINDOWS else {"start_new_session": True})
    child = subprocess.Popen(argv, cwd=str(run.host.cwd), env={**run.host.env, AFK_TEAM_RUN: run.feature},
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
    return 0, {"pid": child.pid, "label": label}


def _same_process(pid: int, started_at: object) -> str:
    """same | gone | unknown: whether `pid` is still the process the entry recorded."""
    if not process.alive(pid):
        return "gone"
    if started_at in (None, ""):
        return "unknown"
    if isinstance(started_at, str) and ISO.fullmatch(started_at):
        now = process.creation_time(pid)
    else:
        now = worktree_owner.creation_time(pid)
    if now is None:
        return "unknown"
    return "same" if str(now) == str(started_at) else "gone"


def _stop_steps(run: Run, entry: dict, force: bool) -> dict:
    """agent-stop's steps on one entry: the identity check, then the kill, then the pane or terminal close."""
    pid, handle, terminal = entry.get("pid"), entry.get("handle"), entry.get("terminal_id")
    kind = entry.get("transport_kind")
    if pid is None and not handle and not terminal:
        return {"stopped": True, "method": "nothing recorded"}
    gone = None
    target = {}
    if pid is not None:
        who = _same_process(pid, entry.get("started_at"))
        if who == "unknown":
            return {"stopped": False, "reason": f"identity unknown: process {pid} runs, and its creation time "
                                                f"cannot be matched to the entry, so nothing was killed"}
        if who == "gone":
            gone = {"stopped": True, "method": "already gone"}
        else:
            target["pid"] = pid
    if kind and (handle or terminal):
        target.update({k: v for k, v in (("handle", handle), ("terminal_id", terminal)) if v})
    if not target:
        return gone
    if kind:
        code, answer = run.transport(kind, "agent-stop", {**target, "force": force})
        if code != 0:
            answer = {"stopped": False, "reason": answer.get("reason", f"agent-stop answered exit {code}")}
    else:
        answer = process.stop(target["pid"], force=force, wait_s=50)
    if gone is not None:
        return {**answer, **gone}
    return answer


def _stop_within(run: Run, entry: dict, seconds: float) -> dict:
    """agent-stop's steps, ended after `seconds` with stopped false (SDD §13 Q47)."""
    result: list[dict] = []
    worker = threading.Thread(target=lambda: result.append(_stop_steps(run, entry, True)), daemon=True)
    if seconds > 0:
        worker.start()
        worker.join(seconds)
    if result:
        return result[0]
    return {"stopped": False, "reason": "the stop ran out of agent-start's 120 s budget, ended 5 s before it"}


def agent_stop(run: Run, p: contract.Payload) -> tuple[int, dict]:
    """Stop one manifest entry: an agent entry by agent_id, or a process entry by pid. Never refuses."""
    _fields(p, ("agent_id", "pid", "force"))
    force = p.boolean("force")
    if ("agent_id" in p.data) == ("pid" in p.data):
        raise contract.bad(p.verb, "give exactly one of `agent_id` (an agent entry) or `pid` (a process entry)")
    data = run.manifest()
    if "pid" in p.data:
        pid = p.integer("pid")
        found = next((row for row in data["processes"] if row["pid"] == pid), None)
        if found is None:
            return 0, {"stopped": False, "reason": f"no entry holds process id {pid}"}
        return 0, _stop_steps(run, {"pid": pid, "started_at": found["started_at"]}, force)
    agent_id = _safe(p, "agent_id")
    entry = next((a for a in data["agents"] if a["agent_id"] == agent_id), None)
    if entry is None:
        return 0, {"stopped": False, "reason": f"no entry holds agent-id {agent_id}"}
    answer = _stop_steps(run, entry, force)
    to = "cleaned" if answer["stopped"] and answer.get("pane_closed") is not False else "unkillable"
    if entry["state"] not in (to, "cleaned"):
        try:
            manifest.move_entry(run.host.root, run.feature, agent_id, to)
        except manifest.ManifestError as refused:
            answer["move_refused"] = str(refused)
    return 0, answer


def _agent(data: dict, agent_id: str) -> dict | None:
    return next((a for a in data["agents"] if a["agent_id"] == agent_id), None)


def _report_target(data: dict, pattern: dict | None, entry: dict) -> dict | None:
    """The agent that gets this agent's result: its role's report target, else its requester; None is the contact."""
    roles = (pattern or {}).get("team", {}).get("roles", {})
    named = roles.get(entry["role"], {}).get("report-target", "")
    if named:
        holders = [a for a in data["agents"] if a["role"] == named]
        live = [a for a in holders if a["state"] in LIVE]
        mine = next((a for a in live if a["agent_id"] == entry.get("requester")), None)
        return mine or (live or holders or [None])[0]
    return _agent(data, entry["requester"]) if entry.get("requester") else None


def _receiver(data: dict, verb: str, target: str) -> dict | None:
    """The agent a target names: an agent-id, else the one live agent holding that role; None is the contact."""
    if target == CONTACT:
        return None
    found = _agent(data, target)
    if found is not None:
        return found
    live = [a for a in data["agents"] if a["role"] == target and a["state"] in LIVE]
    if len(live) == 1:
        return live[0]
    if not live:
        raise contract.unavailable(f"target {target} names no live agent", receiver_gone=True, target=target)
    raise contract.bad(verb, f"field `target`: role {target} has {len(live)} live agents; name one by agent-id")


def _edge_ok(pattern: dict | None, data: dict, sender: dict, receiver: dict | None, kind: str) -> bool:
    """A declared edge listing `kind`, or the implied pair of a role and its report target for kind message."""
    mine = _report_target(data, pattern, sender)
    if receiver is None:
        return kind == "message" and mine is None
    if kind == "message":
        theirs = _report_target(data, pattern, receiver)
        if (mine or {}).get("agent_id") == receiver["agent_id"] or (theirs or {}).get("agent_id") == sender["agent_id"]:
            return True
    edges = (pattern or {}).get("team", {}).get("edges", [])
    return any(not e.get("implied") and e["from"] == sender["role"] and e["to"] == receiver["role"]
               and kind in e["kinds"] for e in edges)


def _body(run: Run, p: contract.Payload, kind: str) -> tuple[bytes | None, str]:
    path = p.text("body_path", kind not in ("exited", "parked"))
    if path is None:
        return None, ""
    try:
        return Path(path).read_bytes(), path
    except OSError as problem:
        raise contract.bad(p.verb, f"field `body_path`: cannot read {path}: {problem}") from None


def _versioned(verb: str, raw: bytes, kind: str, keys: dict) -> dict:
    """A start-request or finished body: one JSON object of format version 1 with exactly `keys` (name -> required)."""
    try:
        body = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as problem:
        raise contract.bad(verb, f"the {kind} body is not one JSON object: {problem}") from None
    if not isinstance(body, dict):
        raise contract.bad(verb, f"the {kind} body is not one JSON object")
    if body.get("format_version") != FORMAT_VERSION or isinstance(body.get("format_version"), bool):
        raise contract.bad(verb, f"the {kind} body has an unknown format version {body.get('format_version')!r}")
    extra = sorted(set(body) - set(keys) - {"format_version"})
    if extra:
        raise contract.bad(verb, f"the {kind} body has an unknown field `{extra[0]}`")
    for key, required in keys.items():
        if required and key not in body:
            raise contract.bad(verb, f"the {kind} body lacks the field `{key}`")
    return body


def _fold(name: str) -> str:
    return re.sub(r"[-._]", "_", name.lower())


def _check_start_request(run: Run, verb: str, raw: bytes, data: dict, pattern: dict | None) -> None:
    """SDD §3 "Validation: start-request": refuse naming the failed check."""
    body = _versioned(verb, raw, "start-request", {"pattern_step": True, "requester": True, "lifespan": True,
                                                  "effort": False, "agents": True})
    for key in ("pattern_step", "requester", "lifespan"):
        if not isinstance(body[key], str) or not body[key]:
            raise contract.bad(verb, f"the start-request field `{key}` must be non-empty text")
    if body["lifespan"] not in manifest.LIFESPANS:
        raise contract.bad(verb, f"the start-request lifespan {body['lifespan']!r} is not one of "
                                 f"{', '.join(manifest.LIFESPANS)}")
    if body.get("effort") is not None and body["effort"] not in EFFORTS:
        raise contract.bad(verb, f"the start-request field `effort`: {body['effort']!r} is not one of "
                                 f"{', '.join(EFFORTS)}")
    agents = body["agents"]
    if not isinstance(agents, list) or not agents or not all(
            isinstance(a, dict) and set(a) == {"role", "brief_path"}
            and all(isinstance(v, str) and v for v in a.values()) for a in agents):
        raise contract.bad(verb, "the start-request field `agents` must be a non-empty list of {role, brief_path}")
    requester = _agent(data, body["requester"])
    if requester is None or requester["state"] not in LIVE:
        raise contract.bad(verb, f"requester {body['requester']} is not a live agent in the run manifest; a helper "
                                 "has no agent-id, so its start would pass the 3-level nesting limit")
    step, roles = body["pattern_step"], {a["role"] for a in agents}
    if step.startswith("solo:"):
        role = step[len("solo:"):]
        stages = run.host.setting("stage-map") or {}
        if any(_fold(s) == _fold(requester["stage"]) for s in (stages if isinstance(stages, dict) else {})):
            raise contract.bad(verb, f"step {step}: stage {requester['stage']} has a stage map entry, so a solo: "
                                     "step is refused")
        if role not in run.host.model_tiers()["agents"]:
            raise contract.bad(verb, f"step {step}: {role} is not a known role agent type")
        if roles != {role}:
            raise contract.bad(verb, f"step {step}: every agent's role must be {role}")
        return
    steps = {s["name"]: s for s in (pattern or {}).get("team", {}).get("steps", [])}
    if step not in steps:
        raise contract.bad(verb, f"step {step} is not a step of the resolved pattern")
    stray = sorted(roles - set(steps[step]["roles"]))
    if stray:
        raise contract.bad(verb, f"role {stray[0]} is not a role of step {step}")


def agent_send(run: Run, p: contract.Payload) -> tuple[int, dict]:
    """Deliver one envelope: into the contact agent's inbox, or into another agent's pane (SDD §3 agent-send)."""
    _fields(p, ("agent_id", "generation", "target", "kind", "message_id", "body_path"))
    sender_id, generation, target = _safe(p, "agent_id"), p.integer("generation"), p.text("target")
    kind, message_id = p.choice("kind", resolver.KINDS), _safe(p, "message_id")
    data = run.manifest()
    pattern = run.pattern()
    sender = None if sender_id == CONTACT else _agent(data, sender_id)
    if sender_id != CONTACT and sender is None:
        raise contract.bad(p.verb, f"field `agent_id`: no entry holds agent-id {sender_id}")
    raw, _ = _body(run, p, kind)
    edge = f"edge {sender['role'] if sender else CONTACT} -> {target} ({kind})"
    if sender is None:
        if kind != "message" or target == CONTACT:
            raise contract.bad(p.verb, f"{edge}: the contact agent sends only kind message to an agent it started")
        receiver = _receiver(data, p.verb, target)
    elif kind == "finished":
        _versioned(p.verb, raw, "finished", {"result_path": True})
        receiver = _report_target(data, pattern, sender)
    elif kind == "start-request":
        if target != CONTACT:
            raise contract.bad(p.verb, f"{edge}: a start request goes only to the contact agent")
        _check_start_request(run, p.verb, raw, data, pattern)
        receiver = None
    else:
        receiver = _receiver(data, p.verb, target)
        if not (kind in LIFECYCLE and receiver is None) and not _edge_ok(pattern, data, sender, receiver, kind):
            raise contract.bad(p.verb, f"{edge}: the resolved pattern declares no such edge for that kind")
    body_path = ""
    if raw is not None:
        copy = run.dir / "bodies" / message_id
        _publish(copy, raw)
        body_path = str(copy)
    envelope = {"format_version": FORMAT_VERSION, "run": run.feature, "generation": generation,
                "from_role": sender["role"] if sender else CONTACT, "agent_id": sender_id, "kind": kind,
                "message_id": message_id, "body_path": body_path}
    if kind == "finished":
        result = json.loads(raw.decode("utf-8"))["result_path"]
        _publish(run.dir / "signals" / f"{sender_id}.json", _json({
            "format_version": FORMAT_VERSION, "agent_id": sender_id, "written_at": contract.now(),
            "finished_message_id": message_id, "result_path": result}))
    pane = _to_pane(run, receiver, envelope) if receiver is not None else None
    inbox = _to_inbox(run, envelope) if receiver is None or kind in LIFECYCLE else None
    named = receiver["agent_id"] if receiver else CONTACT
    if pane is not None and pane[0] != 0:
        return pane[0], {**pane[1], "target": named, "inbox_copy": inbox is None or inbox[0] == 0}
    if inbox is not None and inbox[0] != 0:
        return inbox
    way = pane[1].get("way", "") if pane else "inbox"
    at = (inbox[1]["at"] if inbox else pane[1].get("at", contract.now()))
    return 0, {"delivered": True, "at": at, "target": named, "way": way}


def _to_pane(run: Run, receiver: dict, envelope: dict) -> tuple[int, dict]:
    if receiver["state"] not in LIVE or not receiver.get("handle") or not receiver.get("transport_kind"):
        return 4, {"unavailable": True, "receiver_gone": True,
                   "reason": f"target {receiver['agent_id']} is not a live agent with a pane"}
    code, answer = run.transport(receiver["transport_kind"], "agent-send",
                                 {"handle": receiver["handle"], "text": json.dumps(envelope, sort_keys=True)})
    if code != 0:
        answer = {**answer, "reason": f"delivery to target {receiver['agent_id']} failed: {answer.get('reason', '')}"}
    return code, answer


def _to_inbox(run: Run, envelope: dict) -> tuple[int, dict]:
    path = run.inbox / f"{envelope['message_id']}.json"
    try:
        _publish(path, _json(envelope))
    except OSError as problem:
        return 4, {"unavailable": True, "inbox": str(run.inbox),
                   "reason": f"the copy into the contact agent's inbox {run.inbox} failed: {problem}"}
    return 0, {"at": contract.now()}


def _entry_call(run: Run, p: contract.Payload, extra: tuple[str, ...]) -> tuple[int, dict]:
    _fields(p, ("agent_id", *extra))
    agent_id = _safe(p, "agent_id")
    entry = _agent(run.manifest(), agent_id)
    if entry is None:
        raise contract.bad(p.verb, f"field `agent_id`: no entry holds agent-id {agent_id}")
    kind = entry.get("transport_kind") or run.kind()
    payload = {k: v for k, v in (("handle", entry.get("handle")), ("pid", entry.get("pid")),
                                 ("log", str(run.dir / "logs" / f"{agent_id}.log"))) if v}
    payload.update({k: p.data[k] for k in extra if k in p.data})
    code, answer = run.transport(kind, p.verb, payload)
    return code, {**answer, "agent_id": agent_id}


def agent_status(run: Run, p: contract.Payload) -> tuple[int, dict]:
    return _entry_call(run, p, ())


def agent_read(run: Run, p: contract.Payload) -> tuple[int, dict]:
    return _entry_call(run, p, ("since_marker",))


def agent_list(run: Run, p: contract.Payload) -> tuple[int, dict]:
    """List the run's agents by goal prefix, strays included, each joined to its manifest entry."""
    _fields(p, ())
    data = run.manifest(required=False) or {"agents": []}
    prefix = naming.legal(naming.goal_of(run.feature))
    for name in (a["agent_name"] for a in data["agents"] if a["agent_name"]):
        prefix = os.path.commonprefix([prefix, name])
    code, answer = run.transport(run.kind(), p.verb, {"prefix": prefix})
    if code == 0:
        known = {a["agent_name"]: a for a in data["agents"] if a["agent_name"]}
        answer["agents"] = [{**item, "agent_id": known.get(item.get("agent_name"), {}).get("agent_id", ""),
                             "state": known.get(item.get("agent_name"), {}).get("state", "")}
                            for item in answer.get("agents", [])]
    return code, {**answer, "prefix": prefix}


def run_open(run: Run, p: contract.Payload) -> tuple[int, dict]:
    """Open or take over the run, resolve its pattern and write one charter file per role (plan D-116)."""
    _fields(p, ("session", "pick", "moderator_model"))
    session = p.text("session")
    try:
        opened = manifest.adopt_manifest(run.host.root, run.feature, session)
    except manifest.ManifestError as problem:
        raise contract.unavailable(f"could not open the manifest of run {run.feature}: {problem}") from None
    run.inbox.mkdir(parents=True, exist_ok=True)
    run.processed.mkdir(parents=True, exist_ok=True)
    found = run.host.resolve_kind(run.host.cwd, env=run.host.env)
    if found.get("conflict"):
        raise contract.unavailable(found["conflict"]["detail"], conflict=found["conflict"]["name"])
    answer = {"run": run.feature, "generation": opened["owner_generation"], "kind": found["kind"],
              "says": found.get("says", ""), "pattern": "", "charters": {}}
    if "pick" in p.data:
        pick = p.data["pick"]
        moderator = p.text("moderator_model")
        harnesses = set(found.get("harnesses") or launch.HARNESSES)

        def can_fill(model: str) -> bool:
            tier, _, harness = model.partition("@")
            cell = run.host.model_tiers()["tiers"].get(tier.lower(), {}).get(harness)
            return bool(cell) and harness in harnesses

        try:
            resolved = resolver.resolve_pattern(run.host.root, run.feature, pick, session=session, can_fill=can_fill,
                                                abilities=ABILITIES.get(found["kind"], ()), moderator_model=moderator,
                                                saved=run.host.setting("patterns") or {})
        except resolver.PatternRefused as refused:
            raise contract.bad(p.verb, str(refused)) from None
        answer.update(pattern=str(resolved.path), charters=write_charter_files(run.dir, resolved.charters))
    run.permitted()
    return 0, answer


def wait(run: Run, p: contract.Payload) -> tuple[int, dict]:
    """The run's one wait job: wait on the contact inbox until a message lands or the earliest park-until."""
    _fields(p, ())
    data = run.manifest()
    for row in data["processes"]:
        if row["label"] == WAIT_LABEL:
            if _same_process(row["pid"], row["started_at"]) != "gone":
                raise contract.bad(p.verb, f"run {run.feature} already has a wait job, process {row['pid']}")
            manifest.remove_process(run.host.root, run.feature, row["pid"])
    me = os.getpid()
    manifest.record_entry(run.host.root, run.feature, {"pid": me, "owner": CONTACT, "label": WAIT_LABEL,
                                                       "started_at": worktree_owner.creation_time(me) or "unknown"})
    until = min((a["park_until"] for a in data["agents"] if a["state"] == "parked" and a["park_until"]),
                default=None)
    run.inbox.mkdir(parents=True, exist_ok=True)
    try:
        bash = probe._bash()
        if bash is None:
            raise contract.unavailable("no POSIX shell found to run the inbox wait")
        done = subprocess.run([str(bash), str(INBOX_WAIT), str(run.inbox), *([until] if until else [])],
                              capture_output=True, text=True)
    finally:
        manifest.remove_process(run.host.root, run.feature, me)
    if done.returncode == 0:
        return 0, {"woke": "message", "inbox": str(run.inbox)}
    if done.returncode == 3:
        return 0, {"woke": "park-until", "park_until": until}
    raise contract.unavailable(f"the inbox wait failed: {done.stderr.strip()[:300]}", inbox=str(run.inbox))


COMMANDS = {"agent-start": agent_start, "agent-send": agent_send, "agent-status": agent_status,
            "agent-read": agent_read, "agent-stop": agent_stop, "agent-list": agent_list,
            "run-open": run_open, "wait": wait}


def run_command(verb: str, data: dict, host: Host | None = None) -> tuple[int, dict]:
    """Answer one command: (exit code, answer object)."""
    if verb not in COMMANDS:
        return 3, {"unsupported": True, "reason": f"`{verb}` is not a command; the commands are {', '.join(COMMANDS)}"}
    try:
        host = host or Host.discover()
        feature = data.get("run") or host.env.get(AFK_TEAM_RUN)
        if not isinstance(feature, str) or not SAFE.fullmatch(feature):
            raise contract.bad(verb, f"field `run`: {feature!r} is not a feature identifier, and AFK_TEAM_RUN is unset")
        return COMMANDS[verb](Run(host, feature), contract.Payload(verb, data))
    except contract.Answer as answer:
        body = answer.body
        if body.get("error"):
            body["operation"] = verb
        return answer.code, body
    except manifest.ManifestError as problem:
        return 4, {"unavailable": True, "operation": verb, "reason": f"the manifest refused: {problem}"}
    except Exception as error:      # every other failure still answers in a house shape
        return 4, {"unavailable": True, "operation": verb, "reason": f"{verb} failed: {type(error).__name__}: {error}"}
