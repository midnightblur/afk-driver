#!/usr/bin/env python3
"""Interactive fixer for the register's human-gated entries. Usage: python setup_secrets.py

Covers the MANIFEST.md entries whose Fix names this script: the Jira MCP
registration + REST credentials, the per-dev config file, the GitLab CLI login,
and the git long-path flag. Each entry's own Fix states what it needs; this
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
SERVER = PLUGIN_ROOT / "mcp-servers" / "jira" / "server.py"
CLAUDE_JSON = Path.home() / ".claude.json"

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

if not SERVER.exists():
    die(f"MCP server missing at {SERVER} — pull a revision that ships it, then re-run.")
ok("MCP server source present")

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

# ------------------------------------------ tracker MCP server + REST creds
head("Tracker MCP server + REST credentials")

cj = read_json(CLAUDE_JSON)
servers = cj.get("mcpServers") or {}
existing_env = servers["jira"].get("env") or {} if isinstance(servers.get("jira"), dict) else {}
if existing_env:
    skip("An existing server entry was found — it will be updated in place.")

base_url = ask("Tracker base URL (https://<site>.atlassian.net)", existing_env.get("JIRA_BASE_URL")).rstrip("/")
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

account_id = None
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

if CLAUDE_JSON.exists():
    backup = CLAUDE_JSON.with_suffix(f".json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(CLAUDE_JSON, backup)
    ok(f"backed up harness config -> {backup.name}")

entry = {
    "type": "stdio",
    # Absolute interpreter, not bare "python": a freshly installed interpreter is
    # absent from any process whose environment predates the install.
    "command": sys.executable,
    "args": [str(SERVER)],
    "env": {"JIRA_BASE_URL": base_url, "JIRA_EMAIL": email, "JIRA_API_TOKEN": token},
}
for k, v in existing_env.items():          # keep optional extras a prior run set
    entry["env"].setdefault(k, v)

servers["jira"] = entry                    # key + user scope are load-bearing (register H2 Notes)
cj["mcpServers"] = servers
write_json_atomic(CLAUDE_JSON, cj)
ok("server registered user-scoped under key 'jira' (token not shown)")

# ------------------------------------------------------- per-dev config file
head("Per-dev config")

cfg_path = REPO / ".claude" / "afk.local.json"
cfg_path.parent.mkdir(parents=True, exist_ok=True)
cfg = read_json(cfg_path)
if cfg:
    skip("Existing config — Enter keeps each current value.")

cfg["jiraAssignee"] = ask("assignee account id", cfg.get("jiraAssignee") or account_id)
cfg["mrReviewer"] = ask("MR reviewer (SCM username)", cfg.get("mrReviewer"))

wt_default = cfg.get("worktreeBasePath") or (REPO.parent / f"{REPO.name}-worktrees").as_posix()
wt = ask("worktree base path", wt_default).replace("\\", "/")
cfg["worktreeBasePath"] = wt
if not Path(wt).exists() and yes(f"{wt} does not exist. Create it?"):
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

write_json_atomic(cfg_path, {k: cfg[k] for k in ("jiraAssignee", "mrReviewer", "worktreeBasePath", "ideBinary") if cfg.get(k)})
ok(f"wrote {cfg_path}")

# ------------------------------------------------------------- SCM CLI auth
head("SCM CLI auth")

glab = shutil.which("glab")
if not glab:
    warn("glab not on PATH. If just installed, open a NEW terminal and re-run.")
elif subprocess.run([glab, "auth", "status"], capture_output=True).returncode == 0:
    ok("already authenticated")
elif yes("Run glab auth login now?"):
    print(f"  {C['grey']}glab stores its own token; this script never sees it.{C['off']}")
    subprocess.run([glab, "auth", "login"])
    if subprocess.run([glab, "auth", "status"], capture_output=True).returncode == 0:
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

env2 = ((read_json(CLAUDE_JSON).get("mcpServers") or {}).get("jira") or {}).get("env") or {}
for v in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
    ok(f"{v} set") if env2.get(v) else warn(f"{v} MISSING")

cfg2 = read_json(cfg_path)
missing = [k for k in ("jiraAssignee", "mrReviewer", "worktreeBasePath") if not cfg2.get(k)]
warn(f"config missing: {', '.join(missing)}") if missing else ok("config complete")

print(f"""
{C['cyan']}Done.{C['off']} Start the harness in a NEW terminal, then re-run the doctor.
A restart is required: the MCP tools only register at launch, and a terminal
opened before an install still carries the pre-install PATH.

If the server fails to connect, run it directly to see the real error:
  {sys.executable} {SERVER}
""")
