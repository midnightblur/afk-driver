"""Black-box acceptance tests for the protected-branch guard (PRD AC-001..AC-030).

Written from docs/afk/protected-branch-guard/PRD.md. Each test drives an entry point a
harness or a human reaches (the hook commands registered in hooks/hooks*.json, the
installed git hooks, scripts/create-worktree, the behavior registry CLI) and checks only
what is visible outside: the verdict for an envelope, the worktrees and branches that
exist afterwards, the text a human reads. The forge is stubbed at the CLI boundary
(`gh`, `glab` shims first on PATH); herdr is stubbed the same way. Live-only criteria
are skipped with the reason.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from git_floor import NEEDS_HEAD_SWITCH_HOOK

ROOT = Path(__file__).resolve().parents[2]
RUN_HOOK = ROOT / "hooks" / "run-hook.py"
PY = sys.executable


def _bash() -> str:
    """The launcher's own resolution: never the System32 (WSL) bash on Windows."""
    spec = importlib.util.spec_from_file_location("afk_run_hook", RUN_HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found = module.find_bash()
    return str(found) if found else (shutil.which("bash") or "bash")


BASH = _bash()

# Variables a harness or herdr sets; scrubbed so the test process's own session
# never leaks into the envelope under test.
SCRUBBED_PREFIXES = ("CLAUDE", "CODEX", "HERDR", "AFK_")
SCRUBBED_NAMES = {"PLUGIN_ROOT", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                  "GH_TOKEN", "GITHUB_TOKEN", "GITLAB_TOKEN"}  # a real token sends the lookup to the live forge

LIVE_ONLY = "live-only: needs a real harness session in herdr (Phase 2 live run)"


# --------------------------------------------------------------------------- stubs

STUB_PY = r'''
import json, os, re, sys
state = json.load(open(os.environ["PBG_STUB_STATE"], encoding="utf-8"))
tool, args = sys.argv[1], sys.argv[2:]
with open(os.environ["PBG_STUB_STATE"] + ".calls", "a", encoding="utf-8") as log:
    log.write(json.dumps([tool] + args) + "\n")
if tool == "herdr":
    if args[:2] == ["agent", "get"]:
        # the pane's agent as herdr reports it; the helper types only into the refused session's own pane (P-10)
        print(json.dumps({"result": {"agent": {"agent": os.environ.get("PBG_PANE_KIND", "codex"), "agent_status": "idle",
              "agent_session": {"value": os.environ.get("PBG_PANE_SESSION", "")}, "cwd": os.environ.get("PBG_PANE_CWD", "")}}}))
    elif args[:2] == ["agent", "read"]:  # an idle codex screen: empty composer, placeholder painted dim (P-3)
        ansi = "ansi" in args
        hint = "\x1b[0m\x1b[1m› \x1b[0m\x1b[2mAsk Codex to do anything\x1b[0m" if ansi else "› Ask Codex to do anything"
        sys.stdout.buffer.write(f"• Done.\r\n\r\n{hint}\r\n\r\n  ? for shortcuts\r\n".encode("utf-8"))
    else:
        print(json.dumps({"result": {"type": "ok"}}))
    sys.exit(0)
if state.get("offline"):
    sys.stderr.write("error connecting to api\n"); sys.exit(1)
if not args or args[0] != "api":
    sys.exit(0 if tool == "gh" and args[:2] == ["auth", "status"] else 1)
rest = [a for a in args[1:]]
jq = None
if "--jq" in rest:
    i = rest.index("--jq"); jq = rest[i + 1]; del rest[i:i + 2]
path = next(a for a in rest if not a.startswith("-"))
path = path.split("?", 1)[0]
path = re.sub(r"^repos/[^/]+/[^/]+/", "", path)
path = re.sub(r"^projects/[^/]+/", "", path)
path = path.replace("%2F", "/").replace("%2f", "/")
table = state.get(tool, {})
if path not in table:
    sys.stderr.write('{"message":"Not Found","status":"404"}\n'); sys.exit(1)
answer = table[path]
if tool == "glab":
    pages = answer if answer and isinstance(answer[0], list) else [answer]
    sys.stdout.write("".join(json.dumps(p) for p in pages)); sys.exit(0)
if jq:
    m = re.fullmatch(r"\.([A-Za-z_]+)", jq)
    if m:
        v = answer.get(m.group(1)); print(json.dumps(v) if not isinstance(v, str) else v); sys.exit(0)
    if jq == ".[].name":
        for b in answer: print(b["name"])
        sys.exit(0)
print(json.dumps(answer))
'''


class Stubs:
    """`gh`, `glab` and `herdr` shims driven by one JSON state file."""

    def __init__(self, base: Path):
        self.dir = base / "stub-bin"
        self.dir.mkdir(parents=True)
        self.state_file = base / "stub-state.json"
        script = self.dir / "stub.py"
        script.write_text(STUB_PY, encoding="utf-8")
        for tool in ("gh", "glab", "herdr"):
            sh = self.dir / tool
            sh.write_text(f'#!/bin/sh\nexec "{Path(PY).as_posix()}" "{script.as_posix()}" {tool} "$@"\n',
                          encoding="utf-8", newline="\n")
            sh.chmod(0o755)
            (self.dir / f"{tool}.cmd").write_text(f'@"{PY}" "{script}" {tool} %*\r\n', encoding="utf-8")
        self.set({})

    def set(self, state: dict) -> None:
        self.state_file.write_text(json.dumps(state), encoding="utf-8")

    def github(self, protected=(), unprotected=(), rules=None) -> None:
        table = {}
        for name in protected:
            table[f"branches/{name}"] = {"name": name, "protected": True}
            table[f"rules/branches/{name}"] = []
        for name in unprotected:
            table[f"branches/{name}"] = {"name": name, "protected": False}
            table[f"rules/branches/{name}"] = []
        for name, kinds in (rules or {}).items():
            table[f"rules/branches/{name}"] = [{"type": k} for k in kinds]
        self.set({"gh": table})

    def gitlab(self, pages) -> None:
        entries = [[{"id": i, "name": n} for i, n in enumerate(page)] for page in pages]
        self.set({"glab": {"protected_branches": entries}})

    def calls(self) -> list[list[str]]:
        log = Path(str(self.state_file) + ".calls")
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]


# --------------------------------------------------------------------------- env

def base_env(stubs: Stubs | None, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(SCRUBBED_PREFIXES) and k not in SCRUBBED_NAMES}
    if stubs is not None:
        env["PATH"] = str(stubs.dir) + os.pathsep + env.get("PATH", "")
        env["PBG_STUB_STATE"] = str(stubs.state_file)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["AFK_PROTECTED_TIMEOUT"] = "60"  # behavior, not latency: a stubbed read takes ~9 s on Windows
    env.update(extra)
    return env


def harness_env(harness: str, stubs: Stubs | None, **extra: str) -> dict[str, str]:
    env = base_env(stubs, **extra)
    if harness == "claude":
        env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
        env["CLAUDECODE"] = "1"
    else:
        env["PLUGIN_ROOT"] = str(ROOT)
    return env


# --------------------------------------------------------------------------- git

def git(cwd: Path, *args: str, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    done = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                          env=env or base_env(None), timeout=120)
    if check and done.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {done.stderr}")
    return done


def make_repo(base: Path, name: str = "repo", remote: str = "git@github.com:acme/widget.git",
              default: str = "main") -> Path:
    repo = base / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", default)
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "tester")
    git(repo, "config", "core.autocrlf", "false")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", remote)
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "update-ref", f"refs/remotes/origin/{default}", head)
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{default}")
    return repo


def add_worktree(repo: Path, path: Path, branch: str) -> Path:
    exists = git(repo, "rev-parse", "--verify", "-q", f"refs/heads/{branch}", check=False).returncode == 0
    if exists:
        git(repo, "worktree", "add", "-q", str(path), branch)
    else:
        git(repo, "worktree", "add", "-q", "-b", branch, str(path))
    return path


def worktrees(repo: Path) -> list[tuple[str, str]]:
    """(path, branch) of every worktree, branch '' when detached."""
    out, rows, path = git(repo, "worktree", "list", "--porcelain").stdout, [], None
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line.startswith("branch "):
            rows.append((path, line[len("branch refs/heads/"):]))
            path = None
        elif line == "detached" and path:
            rows.append((path, "")); path = None
    return rows


H2_WAIT = 300  # s: the H-2 worktree is made by a detached helper (R3-6); slow under load


def wait_for(probe, secs: float = H2_WAIT):
    """Poll `probe()` until it is truthy or `secs` pass; return its last value."""
    end = time.time() + secs
    value = probe()
    while not value and time.time() < end:
        time.sleep(1)
        value = probe()
    return value


def same_path(a: str | Path, b: str | Path) -> bool:
    norm = lambda p: os.path.normcase(os.path.normpath(str(Path(p).resolve())))
    return norm(a) == norm(b)


def commit_config(repo: Path, text: str) -> None:
    (repo / ".afk").mkdir(exist_ok=True)
    (repo / ".afk" / "config.yaml").write_text(text, encoding="utf-8")
    git(repo, "add", ".afk")
    git(repo, "commit", "-q", "-m", "afk config")


# --------------------------------------------------------------------------- hooks

def registered(manifest: str, event: str, needle: str | None = None) -> list[str]:
    data = json.loads((ROOT / "hooks" / manifest).read_text(encoding="utf-8"))["hooks"]
    commands = [h["command"] for g in data.get(event, []) for h in g["hooks"]]
    if needle:
        commands = [c for c in commands if needle in c]
    return commands


def hook_argv(command: str) -> list[str]:
    """A registered hook command as argv, the plugin-root variable resolved."""
    expanded = command.replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT)).replace("${PLUGIN_ROOT}", str(ROOT))
    parts = re.findall(r'"([^"]*)"|(\S+)', expanded)
    argv = [a or b for a, b in parts]
    if argv and argv[0] in ("python", "python3"):
        argv[0] = PY
    return argv


def run_hook_command(command: str, envelope: dict, cwd: Path, env: dict,
                     timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(hook_argv(command), input=json.dumps(envelope), capture_output=True,
                          text=True, cwd=str(cwd), env=env, timeout=timeout)


def guard_command(harness: str) -> str:
    manifest = "hooks.json" if harness == "claude" else "hooks.codex.json"
    found = registered(manifest, "PreToolUse", "protected-branch-guard")
    assert found, f"no protected-branch guard registered for PreToolUse in hooks/{manifest}"
    return found[0]


class Verdict:
    def __init__(self, done: subprocess.CompletedProcess):
        self.rc, self.out, self.err = done.returncode, done.stdout, done.stderr
        self.text = done.stdout + "\n" + done.stderr
        self.denied = done.returncode == 2 or self._json_deny(done.stdout)

    @staticmethod
    def _json_deny(stdout: str) -> bool:
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                doc = json.loads(line)
            except ValueError:
                continue
            spec = doc.get("hookSpecificOutput") or {}
            if spec.get("permissionDecision") == "deny" or doc.get("decision") in ("block", "deny"):
                return True
        return False

    def __repr__(self) -> str:
        return f"Verdict(rc={self.rc}, denied={self.denied}, text={self.text[-600:]!r})"


SESSION = iter(range(10_000))


def envelope(harness: str, tool: str, cwd: Path, tool_input: dict, session: str | None = None) -> dict:
    session = session or f"sess-{next(SESSION)}"
    if harness == "claude":
        return {"session_id": session, "transcript_path": "", "cwd": str(cwd),
                "hook_event_name": "PreToolUse", "permission_mode": "default",
                "tool_name": tool, "tool_input": tool_input}
    return {"session_id": session, "turn_id": "turn-1", "cwd": str(cwd), "hook_event_name": "PreToolUse",
            "model": "gpt-5.6", "permission_mode": "bypassPermissions", "tool_name": tool,
            "tool_input": tool_input, "tool_use_id": "exec-1"}


def patch_text(*targets: Path) -> str:
    body = ["*** Begin Patch"]
    for target in targets:
        body += [f"*** Update File: {target}", "@@", "-hello", "+changed"]
    body.append("*** End Patch")
    return "\n".join(body)


def edit_call(harness: str, cwd: Path, target: Path, session: str | None = None) -> dict:
    if harness == "claude":
        return envelope(harness, "Edit", cwd, {"file_path": str(target), "old_string": "hello",
                                                "new_string": "changed"}, session)
    return envelope(harness, "apply_patch", cwd, {"command": patch_text(target)}, session)


def shell_call(harness: str, cwd: Path, session: str | None = None) -> dict:
    return envelope(harness, "Bash", cwd, {"command": "touch changed.txt"}, session)


def guard(harness: str, call: dict, cwd: Path, stubs: Stubs | None, **extra: str) -> Verdict:
    env = harness_env(harness, stubs, **extra)
    return Verdict(run_hook_command(guard_command(harness), call, cwd, env))


# --------------------------------------------------------------------------- fixtures

@pytest.fixture
def stubs(tmp_path: Path) -> Stubs:
    s = Stubs(tmp_path)
    s.github(protected=["main", "release"], unprotected=["feature-x", "feature"])
    return s


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


def placement(row: str, repo: Path, tmp: Path) -> Path:
    """The session folder for a catalog P row (P-6 reuses P-1)."""
    if row in ("P-1", "P-6"):
        return repo
    if row == "P-2":
        git(repo, "switch", "-q", "-c", "feature")
        return repo
    if row == "P-3":
        return add_worktree(repo, tmp / "wts" / "rel", "release")
    if row == "P-4":
        return add_worktree(repo, tmp / "wts" / "fx", "feature-x")
    if row == "P-5":
        plain = tmp / "plain"
        plain.mkdir()
        (plain / "README.md").write_text("hello\n", encoding="utf-8")
        return plain
    raise ValueError(row)


EXPECTED = {"P-1": True, "P-2": True, "P-3": True, "P-4": False, "P-5": False, "P-6": False}


# =========================================================================== Guard

@pytest.mark.parametrize("harness", ["claude", "codex"])
@pytest.mark.parametrize("action", ["edit", "shell"])
@pytest.mark.parametrize("row", sorted(EXPECTED))
def test_ac001_catalog_p_verdicts(row, action, harness, repo, tmp_path, stubs):
    cwd = placement(row, repo, tmp_path)
    call = edit_call(harness, cwd, cwd / "README.md") if action == "edit" else shell_call(harness, cwd)
    extra = {"AFK_ALLOW_PROTECTED": "1"} if row == "P-6" else {}
    verdict = guard(harness, call, cwd, stubs, **extra)
    assert verdict.denied is EXPECTED[row], verdict


@pytest.mark.parametrize("harness", ["claude", "codex"])
@pytest.mark.parametrize("target_row", ["P-1", "P-3"])
def test_ac002_edit_target_in_guarded_place_refused_from_p4_session(harness, target_row, repo, tmp_path, stubs):
    target_dir = repo if target_row == "P-1" else add_worktree(repo, tmp_path / "wts" / "rel", "release")
    session = add_worktree(repo, tmp_path / "wts" / "fx", "feature-x")
    verdict = guard(harness, edit_call(harness, session, target_dir / "README.md"), session, stubs)
    assert verdict.denied, verdict


@pytest.mark.parametrize("harness", ["claude", "codex"])
def test_ac003_refusal_names_main_checkout_and_move(harness, repo, stubs):
    verdict = guard(harness, shell_call(harness, repo), repo, stubs)
    assert verdict.denied, verdict
    assert "main checkout" in verdict.text.lower(), verdict
    if harness == "claude":  # H-1: the native worktree tool, never a /cd line
        assert "worktree" in verdict.text.lower() and "/cd " not in verdict.text, verdict
    else:  # H-2 outside herdr: M-4 prints the /cd line
        assert "/cd " in verdict.text, verdict


@pytest.mark.parametrize("harness", ["claude", "codex"])
def test_ac003_refusal_names_protected_branch(harness, repo, tmp_path, stubs):
    wt = add_worktree(repo, tmp_path / "wts" / "rel", "release")
    verdict = guard(harness, shell_call(harness, wt), wt, stubs)
    assert verdict.denied, verdict
    assert "release" in verdict.text, verdict


@pytest.mark.parametrize("tool,tool_input", [
    ("Read", {"file_path": "README.md"}),
    ("Grep", {"pattern": "hello"}),
    ("Glob", {"pattern": "*.md"}),
    ("EnterWorktree", {"name": "w1"}),
])
@pytest.mark.parametrize("row", ["P-1", "P-2", "P-3"])
def test_ac004_read_search_and_worktree_tool_allowed(row, tool, tool_input, repo, tmp_path, stubs):
    cwd = placement(row, repo, tmp_path)
    tool_input = {k: (str(cwd / v) if k == "file_path" else v) for k, v in tool_input.items()}
    verdict = guard("claude", envelope("claude", tool, cwd, tool_input), cwd, stubs)
    assert not verdict.denied, verdict


@pytest.mark.parametrize("harness,tool", [("claude", "Bash"), ("codex", "exec_command")])
@pytest.mark.parametrize("command", ["Get-Content README.md", "git status --short", "gh issue list"])
def test_ac031_read_only_shell_command_allowed_in_guarded_place(harness, tool, command, repo, stubs):
    verdict = guard(harness, envelope(harness, tool, repo, {"command": command}), repo, stubs)
    assert not verdict.denied, verdict


@pytest.mark.parametrize("command", ["git status && git log -1 2>&1", "git fetch origin", "herdr agent list",
                                     "unknown-reader README.md", "ls | head"])
def test_ac031_composed_or_unknown_commands_allowed_in_guarded_place(command, repo, stubs):
    verdict = guard("claude", envelope("claude", "Bash", repo, {"command": command}), repo, stubs)
    assert not verdict.denied, verdict


def test_ac031_codex_exec_command_reads_its_native_cmd_field(repo, stubs):
    verdict = guard("codex", envelope("codex", "exec_command", repo, {"cmd": "git status --short"}), repo, stubs)
    assert not verdict.denied, verdict


@pytest.mark.parametrize("command", [
    "Set-Content README.md changed",
    "Get-Content README.md > copy.txt",
    "Get-Content README.md; Remove-Item README.md",
    "Get-Content README.md | Set-Content copy.txt",
    "Get-Content @(Set-Content copy.txt changed)",
    "Get-Content (Set-Content copy.txt changed)",
    "Get-ChildItem -Filter { Set-Content copy.txt changed }",
    "git add . && git status",
])
def test_ac031_identified_mutation_refused_in_guarded_place(command, repo, stubs):
    verdict = guard("codex", envelope("codex", "exec_command", repo, {"command": command}), repo, stubs)
    assert verdict.denied, verdict


@pytest.mark.parametrize("tool", ["web__run", "webrun", "mcp__web__run"])
def test_ac004_read_only_web_tools_allowed_in_guarded_place(tool, repo, stubs):
    verdict = guard("codex", envelope("codex", tool, repo, {}), repo, stubs)
    assert not verdict.denied, verdict


def test_ac005_patch_refused_in_main_checkout(repo, stubs):
    verdict = guard("codex", edit_call("codex", repo, repo / "README.md"), repo, stubs)
    assert verdict.denied, verdict


def test_ac005_patch_allowed_in_p4_worktree_with_space_in_path(tmp_path, stubs):
    repo = make_repo(tmp_path, "my repo")
    wt = add_worktree(repo, tmp_path / "wt dir" / "fx", "feature-x")
    call = envelope("codex", "apply_patch", wt,
                    {"command": patch_text(wt / "README.md", wt / "sub dir" / "new.txt")})
    verdict = guard("codex", call, wt, stubs)
    assert not verdict.denied, verdict


@pytest.mark.parametrize("harness", ["claude", "codex"])
def test_ac006_active_without_afk_configuration(harness, repo, stubs):
    assert not (repo / ".afk").exists()
    verdict = guard(harness, edit_call(harness, repo, repo / "README.md"), repo, stubs)
    assert verdict.denied, verdict


# =========================================================================== Protected branches

def lookup(branch: str, checkout: Path, stubs: Stubs) -> dict:
    done = subprocess.run([PY, str(ROOT / "scripts" / "protected-lookup.py"), "--branch", branch,
                           "--checkout", str(checkout)], capture_output=True, text=True,
                          env=base_env(stubs), timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_ac007_github_listed_protected_and_unlisted_not(repo, tmp_path, stubs):
    stubs.github(protected=["release"], unprotected=["feature-x"], rules={"hotfix": ["pull_request"]})
    for branch, protected in (("release", True), ("feature-x", False), ("hotfix", True)):  # hotfix: ruleset only
        answer = lookup(branch, repo, stubs)
        assert answer["protected"] is protected and answer["source"] == "github", (branch, answer)
    wt = add_worktree(repo, tmp_path / "wts" / "rel", "release")
    assert guard("claude", shell_call("claude", wt), wt, stubs).denied
    fx = add_worktree(repo, tmp_path / "wts" / "fx", "feature-x")
    assert not guard("claude", shell_call("claude", fx), fx, stubs).denied


def test_ac007_unpushed_branch_is_not_a_forge_failure(repo, stubs):
    """PROBES P0-g: the branch read 404s for a branch not on the remote; the rules read answers."""
    stubs.set({"gh": {"rules/branches/brand-new": []}})
    answer = lookup("brand-new", repo, stubs)
    assert answer["protected"] is False and answer["source"] == "github", answer


# master: exact, page 1; rel/2026/q3: `*` spans `/`, page 2; hotfix-9: suffix wildcard, page 3
@pytest.mark.parametrize("branch,protected", [
    ("master", True),
    ("rel/2026/q3", True),
    ("hotfix-9", True),
    ("feature-x", False),
    ("rel", False),
])
def test_ac008_gitlab_exact_and_wildcard_on_any_page(branch, protected, tmp_path, stubs):
    repo = make_repo(tmp_path, remote="git@gitlab.com:acme/widget.git")
    stubs.gitlab([["master", "develop"], ["rel/*"], ["hotfix-*"]])
    answer = lookup(branch, repo, stubs)
    assert answer["source"] == "gitlab" and answer["protected"] is protected, answer


@pytest.mark.parametrize("remote", ["git@example.org:acme/widget.git", "git@github.com:acme/widget.git"])
def test_ac009_fallback_default_main_master_only(remote, tmp_path, stubs):
    repo = make_repo(tmp_path, remote=remote, default="trunk")
    stubs.set({"offline": True})
    for branch in ("trunk", "main", "master"):
        answer = lookup(branch, repo, stubs)
        assert answer["protected"] is True and answer["source"] == "fallback", (branch, answer)
    for branch in ("feature-x", "release"):
        answer = lookup(branch, repo, stubs)
        assert answer["protected"] is False and answer["source"] == "fallback", (branch, answer)


def test_ac009_fallback_notice_once_per_session(tmp_path, stubs):
    repo = make_repo(tmp_path, remote="git@example.org:acme/widget.git")
    wt = add_worktree(repo, tmp_path / "wts" / "fx", "feature-x")
    first = guard("claude", shell_call("claude", wt, "same-session"), wt, stubs)
    second = guard("claude", shell_call("claude", wt, "same-session"), wt, stubs)
    assert not first.denied and not second.denied, (first, second)
    assert "fallback" in first.text.lower(), first
    assert "fallback" not in second.text.lower(), second
    master = add_worktree(repo, tmp_path / "wts" / "ms", "master")
    assert guard("claude", shell_call("claude", master, "other"), master, stubs).denied


def test_ac010_protection_added_mid_session_refuses_once_the_cached_answer_expires(repo, tmp_path, stubs):
    wt = add_worktree(repo, tmp_path / "wts" / "fx", "feature-x")
    assert not guard("claude", shell_call("claude", wt, "s1"), wt, stubs).denied
    stubs.github(protected=["feature-x"])
    assert not guard("claude", shell_call("claude", wt, "s1"), wt, stubs).denied, "within 5 minutes"
    cache = repo / ".git" / "afk" / "protection-cache.json"
    entries = json.loads(cache.read_text(encoding="utf-8"))
    cache.write_text(json.dumps({k: {**v, "at": v["at"] - 300} for k, v in entries.items()}), encoding="utf-8")
    assert guard("claude", shell_call("claude", wt, "s1"), wt, stubs).denied


def test_ac010_protection_added_mid_session_refuses_next_action_with_the_cache_off(repo, tmp_path, stubs):
    wt = add_worktree(repo, tmp_path / "wts" / "fx", "feature-x")
    assert not guard("claude", shell_call("claude", wt, "s1"), wt, stubs, AFK_PROTECTION_CACHE_TTL="0").denied
    stubs.github(protected=["feature-x"])
    assert guard("claude", shell_call("claude", wt, "s1"), wt, stubs, AFK_PROTECTION_CACHE_TTL="0").denied


# =========================================================================== Moving and creation

@pytest.mark.skip(reason=LIVE_ONLY + " (AC-011: H-1 native worktree tool, no prompt in any mode)")
def test_ac011_h1_native_move_live():
    pass


def launch_command() -> Path:
    found = sorted(p for p in (ROOT / "scripts").glob("*launch*") if p.is_file())
    assert found, "no launch command under scripts/ (D12 M-2 not landed)"
    return found[0]


def fake_harness(base: Path, name: str) -> Path:
    """A stand-in harness binary that records its working directory and argv."""
    bin_dir = base / "fake-bin"
    bin_dir.mkdir(exist_ok=True)
    record = base / f"{name}-ran.json"
    body = ('import json, os, subprocess, sys\n'
            'g = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()\n'
            'json.dump({"cwd": os.getcwd(), "argv": sys.argv[1:],'
            ' "git_dir": g("rev-parse", "--path-format=absolute", "--git-dir"),'
            ' "common_dir": g("rev-parse", "--path-format=absolute", "--git-common-dir"),'
            ' "branch": g("branch", "--show-current")}, '
            f'open(r"{record}", "w"))\n')
    (bin_dir / f"{name}.py").write_text(body, encoding="utf-8")
    sh = bin_dir / name
    sh.write_text(f'#!/bin/sh\nexec "{Path(PY).as_posix()}" "{(bin_dir / (name + ".py")).as_posix()}" "$@"\n',
                  encoding="utf-8", newline="\n")
    sh.chmod(0o755)
    (bin_dir / f"{name}.cmd").write_text(f'@"{PY}" "{bin_dir / (name + ".py")}" %*\r\n', encoding="utf-8")
    return record


def test_ac012_launch_command_starts_h2_harness_in_new_worktree(repo, tmp_path, stubs):
    """Offline half of AC-012; herdr's kind detection is live-only (PROBES P0-b: verified for wrappers)."""
    record = fake_harness(tmp_path, "codex")
    env = base_env(stubs)
    env["PATH"] = str(tmp_path / "fake-bin") + os.pathsep + env["PATH"]
    before = worktrees(repo)
    cmd = launch_command()
    argv = ([PY, str(cmd)] if cmd.suffix == ".py" else [BASH, str(cmd)]) + ["codex", "--model", "x"]
    done = subprocess.run(argv, capture_output=True, text=True, cwd=str(repo), env=env, timeout=600)
    assert record.exists(), done.stdout + done.stderr
    ran = json.loads(record.read_text(encoding="utf-8"))
    assert ran["argv"][-2:] == ["--model", "x"], ran
    # read at run time: a clean launched worktree is removed when the session ends (AC-027)
    assert not same_path(ran["cwd"], repo), ran
    assert ran["git_dir"] and not same_path(ran["git_dir"], ran["common_dir"]), f"not a linked worktree: {ran}"
    assert ran["branch"] not in ("", "main"), ran


@pytest.mark.skip(reason=LIVE_ONLY + " (AC-012: herdr still detects the agent kind)")
def test_ac012_herdr_detects_kind_live():
    pass


def cd_target(text: str) -> str:
    for line in text.splitlines():  # a codex refusal is deny JSON on stdout (P-2): read its decoded reason
        if line.startswith("{"):
            try:
                text = json.loads(line)["hookSpecificOutput"]["permissionDecisionReason"] + "\n" + text
            except (ValueError, KeyError, TypeError):
                pass
    match = re.search(r"/cd (.+?)\s*$", text, re.MULTILINE)
    assert match, text
    return match.group(1).strip().rstrip("`").rstrip("'\"")


def test_ac013_h2_refusal_in_herdr_types_cd_into_own_pane(tmp_path, stubs):
    """Offline half of AC-013: the detached helper types an unquoted `/cd <worktree>` into
    the refused session's own pane once herdr reports the agent idle. Conversation kept is live-only."""
    repo = make_repo(tmp_path, "my repo")
    herdr = str(stubs.dir / "herdr.cmd") if os.name == "nt" else str(stubs.dir / "herdr")
    verdict = guard("codex", shell_call("codex", repo, "sess-ac013"), repo, stubs,
                    HERDR_ENV="1", HERDR_PANE_ID="wT:p7", HERDR_BIN_PATH=herdr,
                    PBG_PANE_SESSION="sess-ac013", PBG_PANE_CWD=str(repo))
    assert verdict.denied, verdict
    deadline, prompts = time.time() + H2_WAIT, []
    while time.time() < deadline and not prompts:
        prompts = [c for c in stubs.calls() if c[:3] == ["herdr", "agent", "prompt"]]
        time.sleep(0.5)
    assert prompts, stubs.calls()
    call = prompts[0]
    assert call[3] == "wT:p7", call
    assert call[4].startswith("/cd "), call
    target = call[4][len("/cd "):]
    assert not target.startswith(('"', "'")), f"codex takes the /cd argument raw; quotes break it: {call}"
    assert any(same_path(target, p) for p, _ in worktrees(repo)[1:]), (target, worktrees(repo))
    assert len(prompts) == 1


@pytest.mark.parametrize("kind,session", [("claude", "sess-other"), ("codex", "sess-other"), ("codex", "")])
def test_ac013_h2_helper_types_nothing_into_a_pane_that_is_not_the_sessions(tmp_path, stubs, kind, session):
    """P-10: a codex child inherits its parent pane's id; the helper must not type into that pane."""
    repo = make_repo(tmp_path, "my repo")
    herdr = str(stubs.dir / "herdr.cmd") if os.name == "nt" else str(stubs.dir / "herdr")
    verdict = guard("codex", shell_call("codex", repo, "sess-ac013n"), repo, stubs,
                    HERDR_ENV="1", HERDR_PANE_ID="wT:p8", HERDR_BIN_PATH=herdr,
                    PBG_PANE_KIND=kind, PBG_PANE_SESSION=session, PBG_PANE_CWD=str(repo))
    assert verdict.denied, verdict
    assert wait_for(lambda: list((repo / ".git" / "afk-worktrees").glob("*.log")) and
                    "nothing typed" in "".join(f.read_text(encoding="utf-8", errors="replace")
                                               for f in (repo / ".git" / "afk-worktrees").glob("*.log")),
                    secs=H2_WAIT), stubs.calls()
    assert not [c for c in stubs.calls() if c[:3] == ["herdr", "agent", "prompt"]], stubs.calls()


@pytest.mark.skip(reason=LIVE_ONLY + " (AC-013: session ends in the worktree with its conversation kept)")
def test_ac013_conversation_kept_live():
    pass


def test_ac014_h2_refusal_outside_herdr_prints_working_cd_line(tmp_path, stubs):
    repo = make_repo(tmp_path, "my repo")
    verdict = guard("codex", shell_call("codex", repo), repo, stubs)
    assert verdict.denied, verdict
    target = cd_target(verdict.text)
    match = wait_for(lambda: [b for p, b in worktrees(repo)[1:] if same_path(p, target)])
    rows = worktrees(repo)
    assert match and match[0] not in ("main", ""), (target, rows)
    assert not [c for c in stubs.calls() if c[:1] == ["herdr"]], "outside herdr nothing is typed"


@pytest.mark.skip(reason=LIVE_ONLY + " (AC-014: typing the line moves the session, conversation kept)")
def test_ac014_typed_cd_moves_session_live():
    pass


def create_worktree(repo: Path, branch: str, dirname: str, parent: Path, stubs: Stubs | None,
                    *extra: str) -> subprocess.CompletedProcess:
    argv = [BASH, str(ROOT / "scripts" / "create-worktree"), "--branch", branch, "--dir", dirname,
            "--base", "main", "--repo", str(repo), "--parent", str(parent), "--no-open", *extra]
    return subprocess.run(argv, capture_output=True, text=True, cwd=str(repo), env=base_env(stubs),
                          timeout=600)


def worktree_create_hook(repo: Path, name: str, stubs: Stubs, session: str = "s-create",
                         wrapper: list[str] | None = None,
                         extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    found = registered("hooks.json", "WorktreeCreate")
    assert found, "no WorktreeCreate hook registered in hooks/hooks.json (D8 not landed)"
    call = {"session_id": session, "transcript_path": "", "cwd": str(repo), "prompt_id": "p1",
            "hook_event_name": "WorktreeCreate", "name": name}
    argv = (wrapper or []) + hook_argv(found[0])
    return subprocess.run(argv, input=json.dumps(call), capture_output=True, text=True, cwd=str(repo),
                          env={**harness_env("claude", stubs), **(extra_env or {})}, timeout=600)


PATTERN_CONFIG = "git:\n  branch-pattern: '^feat/[a-z0-9-]+$'\n  branch-template: 'feat/{name}'\n"


def test_ac015_create_worktree_rejects_nonmatching_branch_before_any_worktree(repo, tmp_path, stubs):
    commit_config(repo, PATTERN_CONFIG)
    before = worktrees(repo)
    bad = create_worktree(repo, "Bad_Name", "bad", tmp_path / "wts", stubs)
    assert bad.returncode != 0
    assert worktrees(repo) == before and not (tmp_path / "wts" / "bad").exists()
    assert git(repo, "branch", "--list", "Bad_Name").stdout.strip() == ""
    good = create_worktree(repo, "feat/ok", "ok", tmp_path / "wts", stubs)
    assert good.returncode == 0, good.stderr
    assert ("feat/ok" in [b for _, b in worktrees(repo)])


@pytest.mark.parametrize("name", ["../escape", "has space", "a..b", "-dash"])
def test_ac015_h1_creation_hook_rejects_bad_names(name, repo, stubs):
    commit_config(repo, PATTERN_CONFIG)
    before = worktrees(repo)
    done = worktree_create_hook(repo, name, stubs)
    assert done.returncode != 0, done.stdout
    assert worktrees(repo) == before


def test_ac015_h1_creation_hook_branch_matches_pattern(repo, stubs):
    commit_config(repo, PATTERN_CONFIG)
    done = worktree_create_hook(repo, "good-one", stubs)
    assert done.returncode == 0, done.stderr
    lines = [l for l in done.stdout.splitlines() if l.strip()]
    assert len(lines) == 1, f"WorktreeCreate must print exactly the path: {done.stdout!r}"
    branch = [b for p, b in worktrees(repo) if same_path(p, lines[0])]
    assert branch and re.fullmatch(r"feat/[a-z0-9-]+", branch[0]), (lines, worktrees(repo))


def test_ac016_new_worktree_carries_copy_list(repo, tmp_path, stubs):
    commit_config(repo, "worktree:\n  copy:\n    - .personal\n")
    (repo / ".personal").mkdir()
    (repo / ".personal" / "notes.txt").write_text("mine\n", encoding="utf-8")
    done = create_worktree(repo, "feature-copy", "copy", tmp_path / "wts", stubs)
    assert done.returncode == 0, done.stderr
    assert (tmp_path / "wts" / "copy" / ".personal" / "notes.txt").read_text(encoding="utf-8") == "mine\n"
    hook = worktree_create_hook(repo, "copy2", stubs)
    assert hook.returncode == 0, hook.stderr
    path = Path(hook.stdout.strip().splitlines()[-1])
    assert (path / ".personal" / "notes.txt").is_file()


@pytest.mark.parametrize("harness", ["claude", "codex"])
def test_ac017_session_in_unprotected_worktree_works_in_place(harness, repo, tmp_path, stubs):
    wt = add_worktree(repo, tmp_path / "wts" / "fx", "feature-x")
    before = worktrees(repo)
    for call in (edit_call(harness, wt, wt / "README.md"), shell_call(harness, wt)):
        assert not guard(harness, call, wt, stubs).denied
    assert worktrees(repo) == before


def test_ac018_two_simultaneous_h2_sessions_get_two_worktrees(repo, stubs):
    before = worktrees(repo)
    results: dict[str, Verdict] = {}

    def refuse(session: str) -> None:
        results[session] = guard("codex", shell_call("codex", repo, session), repo, stubs)

    threads = [threading.Thread(target=refuse, args=(s,)) for s in ("sa", "sb")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert all(v.denied for v in results.values()), results
    wait_for(lambda: len([w for w in worktrees(repo) if w not in before]) >= 2)
    new = [w for w in worktrees(repo) if w not in before]
    assert len(new) == 2 and new[0][1] != new[1][1] and new[0][0] != new[1][0], new
    assert cd_target(results["sa"].text) != cd_target(results["sb"].text)


def test_ac018_two_simultaneous_h1_creations_get_two_worktrees(repo, stubs):
    before = worktrees(repo)
    out: dict[str, subprocess.CompletedProcess] = {}
    threads = [threading.Thread(target=lambda n=n: out.__setitem__(n, worktree_create_hook(repo, n, stubs, n)))
               for n in ("alpha", "beta")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert all(d.returncode == 0 for d in out.values()), {k: v.stderr for k, v in out.items()}
    new = [w for w in worktrees(repo) if w not in before]
    assert len(new) == 2 and new[0][1] != new[1][1], new


def test_ac019_in_repository_worktrees_hidden_from_main_status(repo, stubs):
    assert git(repo, "status", "--porcelain").stdout == ""
    assert worktree_create_hook(repo, "hidden", stubs).returncode == 0
    assert len(worktrees(repo)) == 2
    assert git(repo, "status", "--porcelain").stdout == "", git(repo, "status", "--porcelain").stdout


def test_ac019_h1_worktree_lands_in_the_claude_folder(repo, stubs):
    done = worktree_create_hook(repo, "where", stubs)
    assert done.returncode == 0, done.stderr
    assert Path(done.stdout.strip().splitlines()[-1]).parent.as_posix().endswith(".claude/worktrees"), done.stdout


def test_ac019_h2_refusal_worktree_hidden_from_main_status(repo, stubs):
    """Slice 6 (D12): the H-2 refusal makes a worktree; main status stays clean."""
    guard("codex", shell_call("codex", repo, "h2"), repo, stubs)
    # the owner record is written after the exclude entry, which follows `worktree add`
    wait_for(lambda: list((repo / ".git" / "afk-worktrees").glob("*.json")))
    assert len(worktrees(repo)) >= 2
    assert git(repo, "status", "--porcelain").stdout == "", git(repo, "status", "--porcelain").stdout


# =========================================================================== Setup scripts

def register_scripts(repo: Path, log: Path, entries: list[tuple[str, str]]) -> None:
    """entries: (script path in manifest, script body or '' for none)."""
    (repo / ".afk").mkdir(exist_ok=True)
    manifest = []
    for rel, body in entries:
        manifest.append({"event": "WorktreeCreated", "matcher": "*", "timeout": 60, "script": rel})
        if body:
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body.replace("@LOG@", log.as_posix()), encoding="utf-8", newline="\n")
    (repo / ".afk" / "hooks.json").write_text(json.dumps(manifest), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "setup scripts")


LOGGER = '#!/usr/bin/env bash\nprintf "%s|%s|%s\\n" "{tag}" "$AFK_WORKTREE_PATH" "$AFK_WORKTREE_BRANCH" >> "@LOG@"\n'


def test_ac020_registered_scripts_run_once_in_order_with_folder_and_branch(repo, tmp_path, stubs):
    log = tmp_path / "setup.log"
    register_scripts(repo, log, [("tools/one.sh", LOGGER.format(tag="one")),
                                 ("tools/two.sh", LOGGER.format(tag="two"))])
    done = create_worktree(repo, "feature-setup", "setup", tmp_path / "wts", stubs)
    assert done.returncode == 0, done.stderr
    rows = [l.split("|") for l in log.read_text(encoding="utf-8").splitlines()]
    assert [r[0] for r in rows] == ["one", "two"], rows
    for _, path, branch in rows:
        assert same_path(path, tmp_path / "wts" / "setup") and branch == "feature-setup", rows


def test_ac021_failing_script_warns_and_keeps_worktree(repo, tmp_path, stubs):
    log = tmp_path / "setup.log"
    register_scripts(repo, log, [("tools/broken.sh", "#!/usr/bin/env bash\nexit 3\n"),
                                 ("tools/two.sh", LOGGER.format(tag="two"))])
    done = create_worktree(repo, "feature-broken", "broken", tmp_path / "wts", stubs)
    assert (tmp_path / "wts" / "broken").is_dir()
    assert "feature-broken" in [b for _, b in worktrees(repo)]
    assert "broken.sh" in done.stdout + done.stderr


def test_ac022_script_outside_repository_not_run(repo, tmp_path, stubs):
    log = tmp_path / "setup.log"
    outside = tmp_path / "outside.sh"
    outside.write_text(LOGGER.format(tag="outside").replace("@LOG@", log.as_posix()), encoding="utf-8",
                       newline="\n")
    register_scripts(repo, log, [("../outside.sh", "")])
    done = create_worktree(repo, "feature-out", "out", tmp_path / "wts", stubs)
    assert not log.exists(), log.read_text(encoding="utf-8")
    assert "outside.sh" in done.stdout + done.stderr
    assert (tmp_path / "wts" / "out").is_dir()


def test_ac023_without_plugin_no_script_and_no_guard(repo, tmp_path):
    log = tmp_path / "setup.log"
    register_scripts(repo, log, [("tools/one.sh", LOGGER.format(tag="one"))])
    env = base_env(None)
    git(repo, "worktree", "add", "-q", "-b", "plain", str(tmp_path / "plain-wt"), env=env)
    assert not log.exists()
    (repo / "README.md").write_text("human edit\n", encoding="utf-8")
    assert git(repo, "commit", "-qam", "human", env=env).returncode == 0


# =========================================================================== Git backstop

def install_backstop(repo: Path) -> None:
    done = subprocess.run([BASH, str(ROOT / "hooks" / "install-git-hooks.sh")], capture_output=True,
                          text=True, cwd=str(repo), env=harness_env("claude", None), timeout=120)
    assert done.returncode == 0, done.stderr
    hooks_dir = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path", "hooks").stdout.strip())
    assert any((hooks_dir / h).is_file() for h in ("pre-commit", "reference-transaction")), \
        "the backstop installs into a repository with no .afk/ (A2)"


def agent_env(stubs: Stubs) -> dict:
    return harness_env("claude", stubs)


def test_ac024_agent_commit_refused_human_commit_passes_in_main_checkout(repo, stubs):
    install_backstop(repo)
    head = git(repo, "rev-parse", "HEAD").stdout
    agent = git(repo, "commit", "-q", "--allow-empty", "-m", "agent", env=agent_env(stubs), check=False)
    assert agent.returncode != 0 and git(repo, "rev-parse", "HEAD").stdout == head
    git(repo, "switch", "-q", "-c", "feature", env=base_env(stubs))
    agent = git(repo, "commit", "-q", "--allow-empty", "-m", "agent", env=agent_env(stubs), check=False)
    assert agent.returncode != 0, "main checkout is refused on any branch (P-2)"
    human = git(repo, "commit", "-q", "--allow-empty", "-m", "human", env=base_env(stubs), check=False)
    assert human.returncode == 0, human.stderr


def test_ac024_agent_commit_refused_on_protected_branch_in_worktree(repo, tmp_path, stubs):
    install_backstop(repo)
    wt = add_worktree(repo, tmp_path / "wts" / "rel", "release")
    agent = git(wt, "commit", "-q", "--allow-empty", "-m", "agent", env=agent_env(stubs), check=False)
    assert agent.returncode != 0
    human = git(wt, "commit", "-q", "--allow-empty", "-m", "human", env=base_env(stubs), check=False)
    assert human.returncode == 0, human.stderr
    fx = add_worktree(repo, tmp_path / "wts" / "fx", "feature-x")
    ok = git(fx, "commit", "-q", "--allow-empty", "-m", "agent", env=agent_env(stubs), check=False)
    assert ok.returncode == 0, ok.stderr


def prepare_moves(repo: Path, stubs: Stubs) -> None:
    human = base_env(stubs)
    git(repo, "switch", "-q", "-c", "other", env=human)
    (repo / "other.txt").write_text("o\n", encoding="utf-8")
    git(repo, "add", ".", env=human)
    git(repo, "commit", "-q", "-m", "other", env=human)
    git(repo, "switch", "-q", "main", env=human)
    git(repo, "commit", "-q", "--allow-empty", "-m", "second", env=human)


MOVES = {
    "checkout": ["checkout", "-q", "other"],
    "switch": ["switch", "-q", "other"],
    "reset": ["reset", "-q", "--hard", "HEAD~1"],
    "merge": ["merge", "-q", "--no-edit", "other"],
    "rebase": ["rebase", "-q", "other"],
}


@pytest.mark.parametrize("move", [pytest.param(m, marks=NEEDS_HEAD_SWITCH_HOOK) if m in ("checkout", "switch") else m
                                  for m in sorted(MOVES)])
def test_ac025_agent_branch_move_refused_human_passes(move, repo, stubs):
    prepare_moves(repo, stubs)
    install_backstop(repo)
    head = (git(repo, "symbolic-ref", "-q", "HEAD", check=False).stdout, git(repo, "rev-parse", "HEAD").stdout)
    agent = git(repo, *MOVES[move], env=agent_env(stubs), check=False)
    assert agent.returncode != 0, agent.stdout
    git(repo, "rebase", "--abort", check=False)
    git(repo, "reset", "-q", "--hard", env=base_env(stubs))  # a vetoed checkout leaves the tree switched
    assert (git(repo, "symbolic-ref", "-q", "HEAD", check=False).stdout,
            git(repo, "rev-parse", "HEAD").stdout) == head
    human = git(repo, *MOVES[move], env=base_env(stubs), check=False)
    assert human.returncode == 0, human.stderr


def test_ac025_new_worktree_branch_from_main_checkout_is_not_a_move(repo, tmp_path, stubs):
    """A9: creating a ref passes. PROBES P0-e finding 5: `worktree add -b` updates the new
    worktree's HEAD inside the main checkout's hook context."""
    install_backstop(repo)
    done = git(repo, "worktree", "add", "-q", "-b", "feature-new", str(tmp_path / "wts" / "new"),
               env=agent_env(stubs), check=False)
    assert done.returncode == 0, done.stderr
    assert git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip() == "main"


# =========================================================================== Override

def test_ac026_override_is_per_launch(repo, tmp_path, stubs):
    wt = add_worktree(repo, tmp_path / "wts" / "rel", "release")
    results: dict[str, Verdict] = {}
    jobs = {
        "allowed-main": lambda: guard("claude", shell_call("claude", repo, "o1"), repo, stubs, AFK_ALLOW_PROTECTED="1"),
        "allowed-rel": lambda: guard("codex", edit_call("codex", wt, wt / "README.md", "o2"), wt, stubs,
                                     AFK_ALLOW_PROTECTED="1"),
        "plain-main": lambda: guard("claude", shell_call("claude", repo, "o3"), repo, stubs),
        "plain-rel": lambda: guard("codex", edit_call("codex", wt, wt / "README.md", "o4"), wt, stubs),
    }
    threads = [threading.Thread(target=lambda k=k, f=f: results.__setitem__(k, f())) for k, f in jobs.items()]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not results["allowed-main"].denied and not results["allowed-rel"].denied, results
    assert results["plain-main"].denied and results["plain-rel"].denied, results


def test_ac026_override_passes_git_backstop(repo, stubs):
    install_backstop(repo)
    env = agent_env(stubs) | {"AFK_ALLOW_PROTECTED": "1"}
    assert git(repo, "commit", "-q", "--allow-empty", "-m", "ok", env=env, check=False).returncode == 0


# =========================================================================== Cleanup

def worktree_remove_hook(repo: Path, path: Path, stubs: Stubs) -> subprocess.CompletedProcess:
    found = registered("hooks.json", "WorktreeRemove")
    assert found, "no WorktreeRemove hook registered in hooks/hooks.json (D8/D11 not landed)"
    call = {"session_id": "s-create", "transcript_path": "", "cwd": str(path), "prompt_id": "p9",
            "hook_event_name": "WorktreeRemove", "worktree_path": str(path)}
    return run_hook_command(found[0], call, repo, harness_env("claude", stubs))


def plugin_worktree(repo: Path, name: str, stubs: Stubs, wrapper: list[str] | None = None,
                    extra_env: dict[str, str] | None = None) -> tuple[Path, str]:
    done = worktree_create_hook(repo, name, stubs, wrapper=wrapper, extra_env=extra_env)
    assert done.returncode == 0, done.stderr
    path = Path(done.stdout.strip().splitlines()[-1])
    branch = [b for p, b in worktrees(repo) if same_path(p, path)][0]
    return path, branch


def test_ac027_clean_plugin_worktree_removed_with_its_branch(repo, stubs):
    path, branch = plugin_worktree(repo, "clean", stubs)
    done = worktree_remove_hook(repo, path, stubs)
    assert done.returncode == 0, done.stderr
    assert not path.exists() and not any(same_path(p, path) for p, _ in worktrees(repo))
    assert git(repo, "branch", "--list", branch).stdout.strip() == ""


@pytest.mark.parametrize("dirt", ["uncommitted", "unpushed"])
def test_ac028_dirty_plugin_worktree_kept_with_resume_and_remove_commands(dirt, repo, stubs):
    path, branch = plugin_worktree(repo, f"dirty-{dirt}", stubs)
    (path / "work.txt").write_text("unsaved\n", encoding="utf-8")
    if dirt == "unpushed":
        git(path, "add", ".")
        git(path, "commit", "-q", "-m", "local only", env=base_env(stubs))
    done = worktree_remove_hook(repo, path, stubs)
    assert path.is_dir() and branch in [b for _, b in worktrees(repo)]
    text = done.stdout + done.stderr
    assert "remove" in text.lower() and (str(path) in text or path.as_posix() in text), text
    assert re.search(r"resume|--worktree|cd ", text, re.IGNORECASE), text


def session_start_prune() -> str:
    found = [c for c in registered("hooks.json", "SessionStart")
             if re.search(r"prune|worktree", c, re.IGNORECASE)]
    assert found, "no SessionStart stale-worktree prune registered (D11 not landed)"
    return found[0]


def run_prune(repo: Path, stubs: Stubs) -> subprocess.CompletedProcess:
    call = {"session_id": "s-later", "transcript_path": "", "cwd": str(repo),
            "hook_event_name": "SessionStart", "source": "startup"}
    return run_hook_command(session_start_prune(), call, repo, harness_env("claude", stubs))


# The launcher resolves the owner itself (run-hook owner_env), so a passed AFK_WORKTREE_OWNER is
# overridden; name a short-lived python wrapper as the owner process instead (A20 opt-in name).
DEAD_OWNER_WRAPPER = [PY, "-c", "import subprocess, sys; sys.exit(subprocess.run(sys.argv[1:]).returncode)"]
DEAD_OWNER_ENV = {"AFK_OWNER_PROCESS": "python"}


def test_ac029_stale_prune_rules(repo, tmp_path, stubs):
    stale_clean, _ = plugin_worktree(repo, "stale-clean", stubs, wrapper=DEAD_OWNER_WRAPPER, extra_env=DEAD_OWNER_ENV)
    stale_dirty, _ = plugin_worktree(repo, "stale-dirty", stubs, wrapper=DEAD_OWNER_WRAPPER, extra_env=DEAD_OWNER_ENV)
    (stale_dirty / "wip.txt").write_text("x\n", encoding="utf-8")
    live, _ = plugin_worktree(repo, "live-owner", stubs)  # owner = an ancestor of this test, alive
    foreign = add_worktree(repo, tmp_path / "wts" / "foreign", "foreign-branch")
    time.sleep(1)
    run_prune(repo, stubs)
    paths = [p for p, _ in worktrees(repo)]
    assert not any(same_path(p, stale_clean) for p in paths), paths
    assert any(same_path(p, stale_dirty) for p in paths), paths
    assert any(same_path(p, live) for p in paths), paths
    assert any(same_path(p, foreign) for p in paths), paths


# =========================================================================== Behavior line

def test_ac030_behavior_block_carries_worktree_rule_and_audits_current(tmp_path):
    registry = ROOT / "BEHAVIORS.md"
    target = tmp_path / "CLAUDE.md"
    render = subprocess.run([PY, str(ROOT / "scripts" / "behavior_registry.py"), "render", str(registry),
                             "--plugin-root", str(ROOT), "--output", str(target)],
                            capture_output=True, text=True, timeout=60)
    assert render.returncode == 0, render.stderr
    block = target.read_text(encoding="utf-8")
    assert re.search(r"worktree", block, re.IGNORECASE), "the managed block carries the worktree rule"
    assert re.search(r"protected", block, re.IGNORECASE)
    audit = subprocess.run([PY, str(ROOT / "scripts" / "behavior_registry.py"), "audit", str(registry),
                            "--plugin-root", str(ROOT), "--target", str(target)],
                           capture_output=True, text=True, timeout=60)
    assert audit.returncode == 0, audit.stdout + audit.stderr


# =========================================================================== Amendments (PLAN.md A5, A8, A12, A18)

@pytest.mark.parametrize("harness", ["claude", "codex"])
@pytest.mark.parametrize("tool,denied", [
    ("mcp__files__write_file", True),
    ("mcp__db__execute_query", True),
    ("mcp__git__commit", True),
    ("mcp__tracker__update_issue", True),
    ("mcp__files__read_file", False),
    ("mcp__docs__search", False),
    ("mcp__tracker__get_issue", False),
])
def test_a12_mcp_tool_denied_by_mutating_verb_in_guarded_place(harness, tool, denied, repo, stubs):
    verdict = guard(harness, envelope(harness, tool, repo, {"path": "README.md"}), repo, stubs)
    assert verdict.denied is denied, verdict


@pytest.mark.parametrize("tool,denied", [
    ("TodoWrite", False), ("AskUserQuestion", False), ("WebFetch", False), ("WebSearch", False),
    ("Skill", False), ("ToolSearch", False), ("Agent", False), ("EnterPlanMode", False),
    ("NotebookEdit", True), ("MultiEdit", True), ("Write", True), ("PowerShell", False),
    ("SomeFutureBuiltinTool", True),
])
def test_a12_claude_builtin_allowlist_in_guarded_place(tool, denied, repo, stubs):
    verdict = guard("claude", envelope("claude", tool, repo, {"file_path": str(repo / "README.md")}), repo, stubs)
    assert verdict.denied is denied, verdict


@pytest.mark.parametrize("tool", ["mcp__files__write_file", "SomeFutureBuiltinTool"])
def test_a12_same_tools_allowed_in_p4_worktree(tool, repo, tmp_path, stubs):
    wt = add_worktree(repo, tmp_path / "wts" / "fx", "feature-x")
    assert not guard("claude", envelope("claude", tool, wt, {"path": "README.md"}), wt, stubs).denied


@pytest.mark.parametrize("name", ["a" * 65, ".hidden", "a..b", "semi;colon"])
def test_a5_bad_worktree_names_rejected_before_anything_exists(name, repo, stubs):
    before = worktrees(repo)
    done = worktree_create_hook(repo, name, stubs)
    assert done.returncode != 0, done.stdout
    assert worktrees(repo) == before
    assert git(repo, "branch", "--list").stdout.count("\n") == 1


def test_a5_slash_in_name_maps_to_dash(repo, stubs):
    """MSG-builder-2 R2-5: `/` maps to `-` before validation."""
    done = worktree_create_hook(repo, "x/y", stubs)
    assert done.returncode == 0, done.stderr
    assert Path(done.stdout.strip().splitlines()[-1]).name == "x-y"


def test_a5_longest_valid_name_accepted(repo, stubs):
    name = "a" + "b" * 63
    done = worktree_create_hook(repo, name, stubs)
    assert done.returncode == 0, done.stderr


def test_a5_template_with_name_placeholder_and_rejection_text(repo, tmp_path, stubs):
    commit_config(repo, PATTERN_CONFIG)
    done = worktree_create_hook(repo, "neat-thing", stubs)
    assert done.returncode == 0, done.stderr
    assert "feat/neat-thing" in [b for _, b in worktrees(repo)]
    bad = create_worktree(repo, "Bad_Name", "bad", tmp_path / "wts", stubs)
    text = bad.stdout + bad.stderr
    # MSG-builder-2 R2-3 (c): the refusal names the pattern and the template
    assert bad.returncode != 0 and "^feat/[a-z0-9-]+$" in text and "feat/{name}" in text, text


def test_a5_unresolvable_placeholder_is_filled_with_the_name(repo, stubs):
    """MSG-builder-2 R2-3 (b): a placeholder the plugin cannot resolve takes the name."""
    commit_config(repo, "git:\n  branch-template: '{ticket}/{name}'\n")
    done = worktree_create_hook(repo, "PROJ-12", stubs)
    assert done.returncode == 0, done.stderr
    assert "PROJ-12/PROJ-12" in [b for _, b in worktrees(repo)]


def test_a8_launch_from_p4_worktree_makes_no_worktree(repo, tmp_path, stubs):
    wt = add_worktree(repo, tmp_path / "wts" / "fx", "feature-x")
    record = fake_harness(tmp_path, "codex")
    env = base_env(stubs)
    env["PATH"] = str(tmp_path / "fake-bin") + os.pathsep + env["PATH"]
    before = worktrees(repo)
    cmd = launch_command()
    argv = ([PY, str(cmd)] if cmd.suffix == ".py" else [BASH, str(cmd)]) + ["codex"]
    done = subprocess.run(argv, capture_output=True, text=True, cwd=str(wt), env=env, timeout=600)
    assert record.exists(), done.stdout + done.stderr
    assert same_path(json.loads(record.read_text(encoding="utf-8"))["cwd"], wt)
    assert worktrees(repo) == before


def test_a18_plugin_creation_passes_backstop_under_agent_env(repo, tmp_path, stubs):
    install_backstop(repo)
    done = subprocess.run([BASH, str(ROOT / "scripts" / "create-worktree"), "--branch", "feature-agent",
                           "--dir", "agent", "--base", "main", "--repo", str(repo), "--parent",
                           str(tmp_path / "wts"), "--no-open"], capture_output=True, text=True,
                          cwd=str(repo), env=agent_env(stubs), timeout=600)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "feature-agent" in [b for _, b in worktrees(repo)]
    assert git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip() == "main"
    hook = worktree_create_hook(repo, "agent-hook", stubs)
    assert hook.returncode == 0, hook.stderr


@NEEDS_HEAD_SWITCH_HOOK
def test_a18_agent_env_marker_does_not_leak_to_plain_git(repo, stubs):
    """The backstop pass is for the plugin's own git calls, not an agent that sets nothing."""
    prepare_moves(repo, stubs)
    install_backstop(repo)
    assert git(repo, "switch", "-q", "other", env=agent_env(stubs), check=False).returncode != 0
