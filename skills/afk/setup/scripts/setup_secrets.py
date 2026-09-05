#!/usr/bin/env python3
"""Interactive fixer for the register's human-gated entries. Usage: python setup_secrets.py

Covers the MANIFEST.md entries whose Fix names this script: the tracker MCP
registration and whatever credential the configured tracker needs, the per-dev
config file, the forge CLI login, and the git long-path flag. Each entry's own Fix states what it needs; this
script only automates placing it.

MUST be run by the human, from their own terminal, NOT by the agent:
  - it prompts interactively (the agent has no tty)
  - an agent shell would put the secret in the agent's transcript
  - it refuses outright when CLAUDECODE is set

Secrets discipline (MANIFEST.md): the token is read with getpass, never echoed,
never passed as an argv (which would expose it in the process table), never
printed even partially, and validated against the tracker before anything is
written. On an auth failure nothing is saved.

Idempotent: every prompt offers to keep the current value; re-running after a
partial run finishes the rest. Backs up the harness config before editing it.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path

# Paths derive from this file's location + git — never hardcoded.
PLUGIN_ROOT = Path(__file__).resolve().parents[4]
SERVER = PLUGIN_ROOT / "mcp-servers" / "tracker" / "server.py"
CLAUDE_JSON = Path.home() / ".claude.json"
MCP_KEY = "tracker"
LEGACY_MCP_KEY = "jira"        # a machine set up before the server was renamed


def config_kind(family: str, root: Path) -> str:
    """The adapter kind `.afk/config.yaml` selects for a family, or "none"."""
    path = PLUGIN_ROOT / "scripts" / "afk-config.py"
    spec = importlib.util.spec_from_file_location("afk_config", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return str(module.get(module.load(root), family) or "none")

C = {"cyan": "\033[36m", "green": "\033[32m", "yellow": "\033[33m", "grey": "\033[90m", "off": "\033[0m"}


def head(t: str) -> None:
    print(f"\n{C['cyan']}=== {t} ==={C['off']}")


def ok(t: str) -> None:
    print(f"  {C['green']}[ok]{C['off']} {t}")


def warn(t: str) -> None:
    print(f"  {C['yellow']}[!!]{C['off']} {t}")


def skip(t: str) -> None:
    print(f"  {C['grey']}[--] {t}{C['off']}")


def die(t: str) -> None:
    print(f"\n  {C['yellow']}ABORTED{C['off']} — {t}\n")
    sys.exit(1)


def ask(prompt: str, current: str | None = None) -> str:
    if current:
        r = input(f"  {prompt}\n    [{current}] (Enter = keep): ").strip()
        return r or current
    while True:
        r = input(f"  {prompt}: ").strip()
        if r:
            return r


def yes(prompt: str, default_yes: bool = True) -> bool:
    r = input(f"  {prompt} {'(Y/n)' if default_yes else '(y/N)'}: ").strip().lower()
    return (r != "n") if default_yes else (r == "y")


def read_json(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        die(f"{p} is not valid JSON ({e}). Fix or move it, then re-run.")
    return {}


def resolved_default(key: str):
    """What `key` resolves to right now.

    Asks the one reader rather than reimplementing the order, so "already set"
    and "git can derive this" are answered the way every other caller answers
    them. A key naming a person resolves only from a `developer:` block.
    """
    script = Path(__file__).resolve().parents[4] / "scripts" / "afk-config.py"
    if not script.is_file():
        return None
    try:
        out = subprocess.run(
            [sys.executable, str(script), "resolve", key],
            cwd=str(REPO), capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = out.stdout.strip()
    return value if out.returncode == 0 and value else None


DEVELOPER_KEYS = ("trackerAssignee", "mrReviewer", "worktreeBasePath", "ideBinary")


def read_developer_block(p: Path) -> dict:
    """The `developer:` mapping of a config overlay, or an empty dict.

    Deliberately small: one flat block of `key: value` lines under one heading,
    which is all this block is ever allowed to be. Anything richer belongs in
    the repository's committed config, not in a per-developer overlay.
    """
    if not p.is_file():
        return {}
    out, inside = {}, False
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[:1].isspace():
            inside = line.strip() == "developer:"
            continue
        if inside and ":" in line:
            key, _, value = line.strip().partition(":")
            value = value.strip().strip("'\"")
            if key.strip() in DEVELOPER_KEYS and value:
                out[key.strip()] = value
    return out


def write_developer_block(p: Path, values: dict) -> None:
    """Replace the `developer:` block, leaving every other line untouched.

    The overlay may hold keys this script knows nothing about, so it is edited
    rather than rewritten.
    """
    lines = p.read_text(encoding="utf-8").splitlines() if p.is_file() else []
    kept, skipping = [], False
    for line in lines:
        if not line[:1].isspace() and line.strip():
            skipping = line.strip() == "developer:"
            if skipping:
                continue
        elif skipping:
            continue
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()

    block = ["developer:"]
    for key in DEVELOPER_KEYS:
        value = values.get(key)
        if value:
            needs_quotes = any(c in str(value) for c in ":#") or str(value).strip() != str(value)
            block.append("  %s: %s" % (key, ('"%s"' % value) if needs_quotes else value))

    body = "\n".join(kept + ([""] if kept else []) + block) + "\n"
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(p)


def write_json_atomic(p: Path, data: dict) -> None:
    """temp + replace: an interrupted run must never truncate the target."""
    tmp = p.with_suffix(p.suffix + ".afk-tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=15, cwd=str(PLUGIN_ROOT),
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except Exception:
        pass
    die("not inside a git checkout — run from the repo the workflow targets.")
    return Path()


def harness_running() -> bool:
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq claude.exe", "/NH"],
            capture_output=True, text=True, timeout=15,
        ).stdout
        return "claude.exe" in out
    except Exception:
        return False


# ---------------------------------------------------------------- preflight
head("Preflight")

if os.environ.get("CLAUDECODE"):
    die("CLAUDECODE is set — this is an agent shell. Run from your own terminal.")

REPO = repo_root()
ok(f"repo {REPO}")

# Which adapters this repository selected decides what there is to provision.
TRACKER_KIND = config_kind("tracker", REPO)
FORGE_KIND = config_kind("forge", REPO)
ok(f"tracker: {TRACKER_KIND}   forge: {FORGE_KIND}")

if not SERVER.exists():
    die(f"MCP server missing at {SERVER} — pull a revision that ships it, then re-run.")
ok("MCP server source present")

if TRACKER_KIND == "jira":
    try:
        import httpx  # noqa: F401
    except ImportError:
        die("Python dep 'httpx' missing (register P3). Run: pip install mcp httpx")
    ok("tracker-client deps importable")

if harness_running():
    warn("The agent harness is RUNNING and writes the same config file.")
    warn("A concurrent write here can clobber its state, or be clobbered.")
    if not yes("Quit it first. Continue anyway?", default_yes=False):
        die("Quit the harness and re-run.")

# ---------------------------------------- tracker MCP server + credentials
head("Tracker MCP server + credentials")

account_id = None

if TRACKER_KIND == "none":
    skip("tracker: none — no server to register")
else:
    cj = read_json(CLAUDE_JSON)
    servers = cj.get("mcpServers") or {}
    prior = servers.get(MCP_KEY) or servers.get(LEGACY_MCP_KEY)
    existing_env = (prior.get("env") or {}) if isinstance(prior, dict) else {}
    if existing_env:
        skip("An existing server entry was found — it will be updated in place.")

    env = dict(existing_env)

    if TRACKER_KIND == "jira":
        # Jira authenticates per user with a REST token, so this script places
        # it. Every other kind authenticates through its own CLI, and that
        # adapter's CONTRACT.md says which one.
        base_url = ask("Tracker base URL (https://<site>.atlassian.net)",
                       existing_env.get("JIRA_BASE_URL")).rstrip("/")
        if not base_url.startswith("https://"):
            die(f"Base URL must start with https:// — got {base_url!r}")

        email = ask("Tracker account email", existing_env.get("JIRA_EMAIL"))
        if "@" not in email or "." not in email.split("@")[-1]:
            die(f"That does not look like an email: {email!r}")

        token = existing_env.get("JIRA_API_TOKEN") or ""
        if token:
            skip("An API token is already present.")
            if yes("Replace it?", default_yes=False):
                token = ""
        if not token:
            print(f"  {C['grey']}Create one: Atlassian account -> Security -> API tokens{C['off']}")
            token = getpass("  API token (input hidden): ").strip()
        if not token:
            die("Empty token.")

        # Validate BEFORE writing. The response also carries the account id the
        # per-dev config's assignee key wants, so a valid token pre-fills it.
        import httpx

        try:
            r = httpx.get(
                f"{base_url}/rest/api/3/myself",
                auth=(email, token),
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            if r.status_code in (401, 403):
                die(f"Tracker rejected the credentials ({r.status_code}). Nothing was written.")
            r.raise_for_status()
            me = r.json()
            account_id = me.get("accountId")
            ok(f"authenticated as {me.get('displayName')}")
        except SystemExit:
            raise
        except Exception as e:
            die(f"could not reach {base_url} — {e}. Nothing was written.")

        env.update({"JIRA_BASE_URL": base_url, "JIRA_EMAIL": email, "JIRA_API_TOKEN": token})
    else:
        skip(f"tracker: {TRACKER_KIND} — the adapter authenticates through its own CLI")

    if CLAUDE_JSON.exists():
        backup = CLAUDE_JSON.with_suffix(f".json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(CLAUDE_JSON, backup)
        ok(f"backed up harness config -> {backup.name}")

    entry = {
        "type": "stdio",
        # Absolute interpreter, not bare "python": a freshly installed interpreter
        # is absent from any process whose environment predates the install.
        "command": sys.executable,
        "args": [str(SERVER)],
        "env": env,
    }

    servers[MCP_KEY] = entry               # key + user scope are load-bearing (register H2 Notes)
    servers.pop(LEGACY_MCP_KEY, None)      # the rename must not leave a duplicate behind
    cj["mcpServers"] = servers
    write_json_atomic(CLAUDE_JSON, cj)
    ok(f"server registered user-scoped under key '{MCP_KEY}' (no secret shown)")

# ------------------------------------------------------- per-dev config file
head("Per-dev config")

# The machine layer by default: one file covers every repository and every
# worktree on this machine, so a new checkout needs no config step at all. A
# per-checkout overlay is only for a value that differs in ONE checkout.
home_path = Path.home() / ".afk" / "config.yaml"
overlay_path = REPO / ".afk" / "config.local.yaml"
cfg_path = home_path
if read_developer_block(overlay_path):
    skip(f"This checkout already has its own developer block in {overlay_path} — keeping it there.")
    cfg_path = overlay_path
elif not yes(f"Write personal values to {home_path} (covers every repository)?"):
    cfg_path = overlay_path
cfg_path.parent.mkdir(parents=True, exist_ok=True)
cfg = read_developer_block(cfg_path)
if cfg:
    skip("Existing config — Enter keeps each current value.")

# These two name a PERSON, so nothing defaults them: not the repository, not
# this script. Each developer answers for themselves, and an empty answer is
# re-asked rather than quietly meaning someone else.
if TRACKER_KIND == "none":
    skip("tracker: none — nothing is assigned, so no assignee is asked for")
    cfg.pop("trackerAssignee", None)
else:
    # Pre-filled with the account the token itself belongs to: the common answer
    # is "me", and it is the one value this script can know without guessing.
    cfg["trackerAssignee"] = ask(
        "assignee account id or email (yours, unless work goes to someone else)",
        cfg.get("trackerAssignee") or account_id,
    )

if FORGE_KIND == "none":
    skip("forge: none — no change is reviewed, so no reviewer is asked for")
    cfg.pop("mrReviewer", None)
else:
    # No pre-fill: who reviews your work is not something anyone else may pick.
    # `none` is the way to say "nobody", and the Ready flip then fails closed.
    answer = ask("reviewer (forge username, or `none` to leave it unset)",
                 cfg.get("mrReviewer"))
    if answer.strip().lower() == "none":
        # Recorded, not dropped: `none` is an answer, and a recorded answer is
        # what tells the doctor this developer was asked. Every consumer reads
        # `none` as "no reviewer" and fails closed exactly as an absent key does.
        cfg["mrReviewer"] = "none"
        skip("reviewer recorded as none — the change Ready flip will fail closed")
    else:
        cfg["mrReviewer"] = answer

# The worktree base is derived from git when unset, so it is asked for only when
# the derivation cannot answer or the developer wants somewhere else.
wt_derived = resolved_default("worktreeBasePath")
if cfg.get("worktreeBasePath"):
    wt = ask("worktree base path", cfg["worktreeBasePath"]).replace("\\", "/")
    cfg["worktreeBasePath"] = wt
elif wt_derived:
    ok(f"worktree base path derives to {wt_derived} — leaving it unset")
    wt = wt_derived
else:
    wt = ask("worktree base path (cannot be derived here)", "").replace("\\", "/")
    if wt:
        cfg["worktreeBasePath"] = wt
if wt and not Path(wt).exists() and yes(f"{wt} does not exist. Create it?"):
    Path(wt).mkdir(parents=True, exist_ok=True)
    ok(f"created {wt}")

ide = None
if os.name == "nt":
    for pf in filter(None, (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"))):
        ide = next(iter(sorted(Path(pf).glob("JetBrains/*/bin/idea64.exe"), reverse=True)), None)
        if ide:
            break
ide_default = cfg.get("ideBinary") or (ide.as_posix() if ide else None)
if ide_default:
    cfg["ideBinary"] = ask("IDE binary (optional)", ide_default).replace("\\", "/")

write_developer_block(cfg_path, {k: cfg[k] for k in ("trackerAssignee", "mrReviewer", "worktreeBasePath", "ideBinary") if cfg.get(k)})
ok(f"wrote the developer block in {cfg_path}")

# ------------------------------------------------------------- forge CLI auth
head("Forge CLI auth")

# Only the CONFIGURED forge is provisioned: a repository on GitHub must not be
# asked to log into GitLab. The CLI each kind needs is its own contract's.
FORGE_CLI = {"gitlab": "glab", "github": "gh"}
_cli = FORGE_CLI.get(FORGE_KIND)
if not _cli:
    skip(f"forge: {FORGE_KIND} — nothing to authenticate")
else:
    _bin = shutil.which(_cli)
    if not _bin:
        warn(f"{_cli} not on PATH. If just installed, open a NEW terminal and re-run.")
    elif subprocess.run([_bin, "auth", "status"], capture_output=True).returncode == 0:
        ok("already authenticated")
    elif yes(f"Run {_cli} auth login now?"):
        print(f"  {C['grey']}{_cli} stores its own token; this script never sees it.{C['off']}")
        subprocess.run([_bin, "auth", "login"])
        if subprocess.run([_bin, "auth", "status"], capture_output=True).returncode == 0:
            ok("authenticated")
        else:
            warn("still not authenticated")
    else:
        skip("skipped")

# ------------------------------------------------------------- git long paths
if os.name == "nt":
    head("git long paths")
    cur = subprocess.run(["git", "config", "--global", "--get", "core.longpaths"],
                         capture_output=True, text=True).stdout.strip()
    if cur == "true":
        ok("already true")
    elif yes("Set git core.longpaths=true?"):
        subprocess.run(["git", "config", "--global", "core.longpaths", "true"], check=True)
        ok("set")
    else:
        skip("skipped")

# ------------------------------------------------------------------ re-probe
head("Re-probe (presence only)")

entry2 = (read_json(CLAUDE_JSON).get("mcpServers") or {}).get(MCP_KEY)
if TRACKER_KIND == "none":
    skip("tracker: none — nothing registered")
elif not isinstance(entry2, dict):
    warn(f"MCP server '{MCP_KEY}' NOT registered")
else:
    ok(f"MCP server '{MCP_KEY}' registered")
    env2 = entry2.get("env") or {}
    for v in (("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN") if TRACKER_KIND == "jira" else ()):
        ok(f"{v} set") if env2.get(v) else warn(f"{v} MISSING")

# Re-probe the way H6 does — through `resolve`, not by reading the file — so
# this line and the doctor row can never disagree.
wanted = ["worktreeBasePath"]
if TRACKER_KIND != "none":
    wanted.insert(0, "trackerAssignee")
if FORGE_KIND != "none":
    wanted.append("mrReviewer")
missing = [k for k in wanted if not resolved_default(k)]
warn(f"config missing: {', '.join(missing)}") if missing else ok("config complete")

print(f"""
{C['cyan']}Done.{C['off']} Start the harness in a NEW terminal, then re-run the doctor.
A restart is required: the MCP tools only register at launch, and a terminal
opened before an install still carries the pre-install PATH.

If the server fails to connect, run it directly to see the real error:
  {sys.executable} {SERVER}
""")
