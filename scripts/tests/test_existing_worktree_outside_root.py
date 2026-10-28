"""A worktree that already sits outside the worktree root keeps working with every plugin hook, gate and script.

Each member runs on real outside worktrees (cut while the repository was unlisted) and on twins
cut the same way under the root; outputs are normalised and compared, and the worktree folder must
not change; a crash under the root fails even when both twins match. Temporary home and repositories
only; members that cannot run in a sandbox are in EXCLUDED, whose files a test checks exist.
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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parent
SCRUB = ("AFK_", "CLAUDE", "CODEX", "PLUGIN_ROOT", "GIT_", "HERDR")
DEAD = "2147483000:1"  # an owner that is provably dead


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASH = _load("afk_run_hook_for_outside_tests", PLUGIN_ROOT / "hooks" / "run-hook.py").find_bash()
rl = _load("afk_repo_list_for_outside_tests", PLUGIN_ROOT / "scripts" / "repo_list.py")
OWNER = _load("afk_owner_for_outside_tests", PLUGIN_ROOT / "scripts" / "worktree_owner.py")
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")

EXCLUDED = {
    "adapters/build-gate/maven/maven-compile-gate.sh": "the compile runs ./mvnw over a Maven reactor with a JDK",
    "adapters/build-gate/maven/java-format-gate.sh": "the format check runs the formatter plugin through ./mvnw",
    "adapters/build-gate/maven/app-start-gate.sh": "boots the application through ./mvnw and Java on a free port",
    "adapters/build-gate/maven/mutation-probe.sh": "runs PIT mutation testing through ./mvnw",
    "adapters/build-gate/npm/ui-lint-gate.sh (lint)": "the lint runs eslint from node_modules via npx",
    "adapters/build-gate/npm/worktree-provision.sh (install)": "`npm ci` downloads packages; the skip path is covered",
    "scripts/afk-move.py (typing)": "types into a terminal pane through the herdr binary; the create part is covered",
    "skills/afk/review/scripts/forge_ledger.py (forge calls)": "post, reply, reconstruct and rationale-post call a "
                                                               "forge CLI over the network; cache and pending dirs "
                                                               "are covered",
    "skills/utils/report-issue/scripts/publish.sh (publish)": "publishing and --dry-run call gh against GitHub; "
                                                              "--list is covered",
    "adapters/tracker/jira/api.py": "every operation calls the Jira REST API; config-root resolution is covered "
                                    "through tracker none",
    "adapters/tracker/github-issues/api.py": "every operation calls the GitHub API; config-root resolution is "
                                             "covered through tracker none",
}

CONFIG = """schema: 1
tracker: none
forge: none
build-gates:
  - maven
  - npm
git:
  base-branch: dev
  branch-pattern: '^(worktree-|b-|main$|master$)'
maven:
  worktree-seed: none
repo-files:
  spec-dir: docs/specs
"""
HELLO = '#!/usr/bin/env bash\nprintf \'{"hookSpecificOutput":{"hookEventName":"SessionStart",' \
        '"additionalContext":"hello from %s"}}\\n\' "$PWD"\n'
FILES = {
    "a.txt": "hello\nanchor-for-validation-probe\n",
    "AGENTS.md": "# Root steering\n",
    "GLOSSARY.md": "# Glossary\n\n**Zorblax**: a probe term only this repository defines.\n",
    "sub/AGENTS.md": "Sub steering: probe line.\n",
    "sub/x.txt": "x\n",
    ".afk/config.yaml": CONFIG,
    ".afk/hooks.json": json.dumps([{"event": "SessionStart", "matcher": "*", "timeout": 20,
                                    "script": "tools/hello.sh"}]),
    "tools/hello.sh": HELLO,
    "docs/specs/feat/PRD.md": "# PRD\n",
    "docs/specs/feat/plan/PLAN.md": "# Plan\n\n> Feature: complete (2026-10-28)\n",
    "docs/specs/feat/plan/0001-probe.md": "# 0001 probe\n\n## Produces\n\n"
                                          "- a.txt#anchor-for-validation-probe — the probe anchor\n",
}


def git(cwd: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          check=check, capture_output=True, text=True).stdout.strip()


def make_repo(folder: Path, files: dict | None = None) -> Path:
    folder.mkdir(parents=True)
    git(folder, "init", "-q", "-b", "dev")
    for rel, text in (files or {"a.txt": "a\n"}).items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_bytes(text.encode("utf-8"))
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", "seed")
    return folder


@dataclass
class Site:
    label: str
    path: Path
    branch: str
    protected: bool = False


@dataclass
class Forest:
    base: Path
    home: Path
    root: Path
    main: Path
    owner: str
    other: str
    pairs: dict = field(default_factory=dict)
    disposable: dict = field(default_factory=dict)

    def env(self, **extra) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(SCRUB)}
        env.update(HOME=str(self.home), USERPROFILE=str(self.home), AFK_PLUGIN_ROOT=str(PLUGIN_ROOT),
                   AFK_PYTHON=sys.executable, AFK_PROVIDER="claude", AFK_MOVE_SPAWN="0",
                   AFK_WORKTREE_OWNER=self.owner, PYTHONIOENCODING="utf-8")
        for key, value in extra.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return env

    def norm(self, text: str, site: Site) -> str:
        subs = []
        for path, tag in ((site.path, "<WT>"), (self.main, "<MAIN>"), (self.root, "<ROOT>"),
                          (self.home, "<HOME>"), (self.base, "<BASE>"), (PLUGIN_ROOT, "<PLUGIN>")):
            for form in forms(path):
                subs.append((form, tag))
        for form, tag in sorted(set(subs), key=lambda item: -len(item[0])):
            text = re.sub(re.escape(form) + r"(?![A-Za-z0-9_])", tag, text, flags=re.I)
        text = text.replace(site.label, "<L>")
        text = re.sub(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", "<TS>", text)
        text = re.sub(r"\x1b\[[0-9;]*m", "", text)
        if site.protected:  # the twins are on `main` and `master`, both protected by the fallback
            text = re.sub(r"\b(main|master)\b", "<PB>", text)
        return text


def forms(path: Path) -> set[str]:
    found = set()
    for item in {Path(path), Path(os.path.realpath(path))}:
        text, posix = str(item), item.as_posix()
        found.update({text, posix, text.replace("\\", "\\\\")})
        if len(posix) > 2 and posix[1] == ":":
            found.add("/" + posix[0].lower() + posix[2:])
    return found


def create(forest_env: dict, repo: Path, *args: str) -> Path:
    done = subprocess.run([str(BASH), str(PLUGIN_ROOT / "scripts" / "create-worktree"), "--repo", repo.as_posix(),
                           "--no-open", *args], capture_output=True, text=True, cwd=repo, env=forest_env,
                          timeout=600)
    lines = done.stdout.strip().splitlines()
    assert done.returncode == 0 and lines and lines[-1].startswith("WORKTREE_PATH="), done.stdout + done.stderr
    return Path(lines[-1].removeprefix("WORKTREE_PATH="))


def parallel(jobs: list[Callable]) -> list:
    with ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        return [future.result() for future in [pool.submit(job) for job in jobs]]


def below(child: Path, parent: Path) -> bool:
    try:
        Path(os.path.realpath(child)).relative_to(os.path.realpath(parent))
        return True
    except ValueError:
        return False


@pytest.fixture(scope="module")
def forest(tmp_path_factory):
    base = tmp_path_factory.mktemp("w")
    home, root, src = base / "h", base / "r", base / "s"
    (home / ".afk").mkdir(parents=True)
    (home / ".claude").mkdir()
    (home / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
    root.mkdir()
    patch = pytest.MonkeyPatch()
    patch.setenv("HOME", str(home))
    patch.setenv("USERPROFILE", str(home))
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(900)"])
    try:
        main = make_repo(src / "proj", FILES)
        (main / ".claude").mkdir()  # every cut then copies the same `.claude/`, whatever the order
        throwaway = {name: make_repo(src / name) for name in ("rmhook", "rmpy", "prune")}
        me = f"{os.getpid()}:{OWNER.creation_time(os.getpid())}"
        forest = Forest(base, home, root, main, me, f"{other.pid}:{OWNER.creation_time(other.pid)}")
        live, dead = forest.env(), forest.env(AFK_WORKTREE_OWNER=DEAD)
        cuts = {"name": ("--name", "{label}"), "dir": ("--branch", "b-{label}", "--dir", "{label}", "--base", "dev"),
                "prot": ("--branch", "{branch}", "--dir", "{label}", "--base", "dev")}

        def cut(kind: str, label: str, branch: str = "") -> Path:
            return create(live, main, *(a.format(label=label, branch=branch) for a in cuts[kind]))

        outside = parallel([lambda: cut("name", "wq-on"), lambda: cut("dir", "wq-od"),
                            lambda: cut("prot", "wq-op", "main")]
                           + [lambda r=r: create(dead, r, "--name", "wq-on") for r in throwaway.values()])
        (home / ".afk" / "config.yaml").write_text(f"developer:\n  worktreeRoot: '{root.as_posix()}'\n",
                                                   encoding="utf-8")
        for repo in (main, *throwaway.values()):
            rl.add_repository(repo, root)
        inside = parallel([lambda: cut("name", "wq-in"), lambda: cut("dir", "wq-id"),
                           lambda: cut("prot", "wq-ip", "master")]
                          + [lambda r=r: create(dead, r, "--name", "wq-in") for r in throwaway.values()])
        for path in outside:
            assert not below(path, root), path
        for path in inside:
            assert below(path, root), path
        forest.pairs = {
            "name": (Site("wq-on", outside[0], "worktree-wq-on"), Site("wq-in", inside[0], "worktree-wq-in")),
            "dir": (Site("wq-od", outside[1], "b-wq-od"), Site("wq-id", inside[1], "b-wq-id")),
            "prot": (Site("wq-op", outside[2], "main", True), Site("wq-ip", inside[2], "master", True)),
        }
        forest.disposable = {name: (repo, outside[3 + i], inside[3 + i])
                             for i, (name, repo) in enumerate(throwaway.items())}
        queue = main / ".claude" / "afk-issues"
        queue.mkdir(parents=True)
        (queue / ".gitignore").write_text("*\n", encoding="utf-8")
        (queue / "abc.md").write_text("<!-- afk-issue-meta\ntitle: queued probe\n-->\nbody\n", encoding="utf-8")
        yield forest
    finally:
        other.kill()
        patch.undo()


@pytest.fixture(autouse=True)
def fresh_occupancy(forest):
    yield
    shutil.rmtree(forest.main / ".git" / "afk-occupancy", ignore_errors=True)


# --- running members -----------------------------------------------------------------

def run(f: Forest, argv: list, cwd: Path, stdin: str | None = None, **extra) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in argv], cwd=str(cwd), input=stdin if stdin is not None else "",
                          capture_output=True, encoding="utf-8", errors="replace", env=f.env(**extra), timeout=600)


def sh(f, rel: str, *args, cwd: Path, stdin=None, **extra):
    return run(f, [BASH, PLUGIN_ROOT / rel, *args], cwd, stdin, **extra)


def py(f, rel: str, *args, cwd: Path, stdin=None, **extra):
    return run(f, [sys.executable, PLUGIN_ROOT / rel, *args], cwd, stdin, **extra)


def bash_code(f, code: str, cwd: Path, **extra):
    return run(f, [BASH, "-c", code], cwd, None, P=PLUGIN_ROOT.as_posix(), **extra)


PRELUDE = """
import importlib.util, json, os, sys
from pathlib import Path
P = Path(os.environ["AFK_PLUGIN_ROOT"])
S = Path(os.environ["PROBE_SITE"])
def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, P / rel)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
"""


def snippet(f, site: Site, code: str, cwd: Path | None = None, **extra):
    done = run(f, [sys.executable, "-c", PRELUDE + code], cwd or site.path, None, PROBE_SITE=str(site.path),
               PROBE_ROOT=str(f.root), PROBE_MAIN=str(f.main), **extra)
    assert done.returncode == 0, done.stderr
    return f.norm(done.stdout, site)


def outcome(f, site, done, streams="oe") -> tuple:
    return (done.returncode, *(f.norm(done.stdout if s == "o" else done.stderr, site).strip() for s in streams))


def gitdir(site: Site) -> str:
    return git(site.path, "rev-parse", "--absolute-git-dir")


class staged:
    """Stage a blob in the worktree's index only; the folder itself never changes."""

    def __init__(self, site: Site, rel: str, text: str):
        self.site, self.rel, self.text = site, rel, text

    def __enter__(self):
        sha = subprocess.run(["git", "-C", str(self.site.path), "hash-object", "-w", "--stdin"], input=self.text,
                             capture_output=True, text=True, check=True).stdout.strip()
        git(self.site.path, "update-index", "--add", "--cacheinfo", f"100644,{sha},{self.rel}")

    def __exit__(self, *_):
        git(self.site.path, "update-index", "--force-remove", self.rel)


# --- the member table ------------------------------------------------------------------

@dataclass
class Case:
    member: str
    probe: Callable
    writes: bool = False      # the member writes into the worktree by design: compare the change sets
    serial: bool = False      # shared state: run the sites one after another
    kinds: tuple = ("name", "dir")
    expect: Callable = lambda f, site, inside: inside  # expected outside value from the inside one


CASES: list[Case] = []
PROT = ("name", "dir", "prot")  # cases where a protected branch can change the verdict
CREATOR = ("name",)  # each run cuts a worktree; one pair keeps the run short


def case(member: str, **options):
    def register(probe):
        CASES.append(Case(member, probe, **options))
        return probe
    return register


@case("hooks/worktree-create.sh", kinds=CREATOR)
def _(f, s):
    envelope = {"session_id": "s-wc", "transcript_path": "", "cwd": str(s.path),
                "hook_event_name": "WorktreeCreate", "name": f"wc-{s.label}"}
    return outcome(f, s, sh(f, "hooks/worktree-create.sh", cwd=s.path, stdin=json.dumps(envelope),
                            CLAUDE_PLUGIN_ROOT=str(PLUGIN_ROOT)), "o")


@case("hooks/worktree-prune.sh:adopt")
def _(f, s):
    """A session that starts in the worktree keeps it and becomes an owner of it."""
    done = sh(f, "hooks/worktree-prune.sh", cwd=s.path)
    record = f.main / ".git" / "afk-worktrees" / f"{s.label}.json"
    owners = None
    if record.is_file():
        owners = [f"{o['pid']}:{o['ctime']}" for o in OWNER.owners_of(json.loads(record.read_text("utf-8")))]
    return done.returncode, f.norm(done.stdout, s), s.path.is_dir(), owners and f.owner in owners


@case("hooks/protected-branch-occupancy.py+hooks/lib/occupancy.py")
def _(f, s):
    def start(session, owner):
        envelope = {"session_id": session, "cwd": str(s.path), "hook_event_name": "SessionStart"}
        return py(f, "hooks/protected-branch-occupancy.py", cwd=s.path, stdin=json.dumps(envelope),
                  AFK_WORKTREE_OWNER=owner)
    first, second = start("s-occ-a", f.owner), start("s-occ-b", f.other)
    return outcome(f, s, first, "o") + outcome(f, s, second, "o")


def guard(f, s, tool: str, tool_input: dict, cwd: Path | None = None):
    # one session per site: the guard's once-per-session fallback notice then lands on the same call for both
    envelope = {"session_id": f"s-guard-{s.label}", "cwd": str(cwd or s.path), "hook_event_name": "PreToolUse",
                "tool_name": tool, "tool_input": tool_input}
    done = py(f, "hooks/protected-branch-guard.py", cwd=cwd or s.path, stdin=json.dumps(envelope))
    reason = ""
    if '"permissionDecision": "deny"' in done.stdout:
        reason = json.loads(done.stdout)["hookSpecificOutput"].get("permissionDecisionReason", "deny")
    return done.returncode, "deny" if reason else "allow", f.norm(reason, s)


@case("hooks/protected-branch-guard.py+hooks/lib/protected_branch_guard.py", kinds=PROT)
def _(f, s):
    return [guard(f, s, "Edit", {"file_path": str(s.path / "a.txt")}),
            guard(f, s, "Write", {"file_path": str(s.path / "sub" / "new.txt")}),
            guard(f, s, "Bash", {"command": "touch changed"}),
            guard(f, s, "Edit", {"file_path": str(f.main / "a.txt")})]


@case("hooks/lib/shell_mutations.py", kinds=PROT)
def _(f, s):
    here, away = s.path.as_posix(), (f.base / f"moved-{s.label}").as_posix()
    seen = [guard(f, s, "Bash", {"command": f"git worktree remove {here}"}, cwd=f.main),
            guard(f, s, "Bash", {"command": f"git worktree move {here} {away}"}, cwd=f.main),
            guard(f, s, "Bash", {"command": f"git -C {here} commit --allow-empty -m x"}, cwd=f.main)]
    # The guard cuts the echoed command at 80 characters, and the twins' paths differ in length.
    return [(code, verdict, re.sub(r"run `[^`]*`", "run `<CMD>`", text)) for code, verdict, text in seen]


@case("hooks/lib/read_only.py", kinds=PROT)
def _(f, s):
    return [guard(f, s, "Bash", {"command": "git status --short"}),
            guard(f, s, "Bash", {"command": "git log -1 --format=%s && cat a.txt"}),
            guard(f, s, "Bash", {"command": "echo x > a.txt"})]


@case("hooks/lib/main_sync.py")
def _(f, s):
    return snippet(f, s, """
sys.path.insert(0, str(P / "hooks" / "lib"))
import protected_branch_guard as guard, main_sync
place = guard.placement(S)
print(json.dumps([place["kind"], main_sync.check(place, None, None)[0], str(main_sync.directory(place))]))
""")


@case("hooks/run-hook.py:repo-list")
def _(f, s):
    envelope = {"session_id": "s-rh", "cwd": str(s.path), "hook_event_name": "SessionStart", "source": "startup"}
    return outcome(f, s, py(f, "hooks/run-hook.py", "repo-list", "SessionStart", cwd=s.path,
                            stdin=json.dumps(envelope)))


@case("hooks/nested-steering.sh+hooks/lib/nested_steering.py")
def _(f, s):
    envelope = {"session_id": f"ns-{s.label}", "cwd": str(s.path), "hook_event_name": "PostToolUse",
                "tool_name": "Read", "tool_input": {"file_path": str(s.path / "sub" / "x.txt")}}
    return outcome(f, s, sh(f, "hooks/nested-steering.sh", cwd=s.path, stdin=json.dumps(envelope),
                            AFK_PROVIDER="codex"), "o")


@case("hooks/install-git-hooks.sh", serial=True)
def _(f, s):
    """Installs into the shared hooks folder; the installed stubs are removed after each run."""
    done = sh(f, "hooks/install-git-hooks.sh", cwd=s.path)
    folder = Path(git(s.path, "rev-parse", "--path-format=absolute", "--git-path", "hooks"))
    made = sorted(p.name for p in folder.iterdir() if p.is_file() and "afk-" in p.read_text("utf-8", "replace"))
    for name in made:
        (folder / name).unlink()
    return outcome(f, s, done) + (f.norm(folder.as_posix(), s), made)


@case("hooks/agents-md-config-check.sh")
def _(f, s):
    return outcome(f, s, sh(f, "hooks/agents-md-config-check.sh", cwd=s.path))


@case("hooks/branch-name-gate.sh", kinds=PROT)
def _(f, s):
    head = git(s.path, "rev-parse", "HEAD")
    runs = []
    for arg, line in (("prepared", f"{'0' * 40} {head} refs/heads/bad-name-{s.label}"),
                      ("prepared", f"{'0' * 40} {head} refs/heads/b-ok-{s.label}"),
                      ("prepared", f"{head} {'1' * 40} refs/heads/{s.branch}"),
                      ("committed", f"{head} {'1' * 40} refs/heads/{s.branch}")):
        runs.append(outcome(f, s, sh(f, "hooks/branch-name-gate.sh", arg, cwd=s.path, stdin=line + "\n",
                                     GIT_DIR=gitdir(s))))
    return runs


@case("hooks/git-backstop.py", kinds=PROT)
def _(f, s):
    head = git(s.path, "rev-parse", "HEAD")
    return [outcome(f, s, py(f, "hooks/git-backstop.py", "pre-commit", cwd=s.path)),
            outcome(f, s, py(f, "hooks/git-backstop.py", "reference-transaction", "prepared", cwd=s.path,
                             stdin=f"{head} {'1' * 40} refs/heads/{s.branch}\n"))]


@case("hooks/precommit-gates.sh", kinds=PROT)
def _(f, s):
    return outcome(f, s, sh(f, "hooks/precommit-gates.sh", cwd=s.path))


GATE_LIBS = """
. "$P/hooks/gate-context.sh"; gate_ctx_build
echo "cache=$AFK_CTX_CACHE_DIR common=$AFK_CTX_COMMON_DIR head=$AFK_CTX_HEAD base=$AFK_CTX_BASE"
echo "changed=[$AFK_CTX_CHANGED] tree=$AFK_CTX_TREE"
"""


@case("hooks/gate-context.sh")
def _(f, s):
    return outcome(f, s, bash_code(f, GATE_LIBS, s.path))


@case("hooks/gate-cache.sh")
def _(f, s):
    code = GATE_LIBS + """. "$P/hooks/gate-cache.sh"
key=$(gate_cache_key probe); gate_cache_hit probe "$key"; echo "first=$?"
gate_cache_store probe "$key"; gate_cache_hit probe "$key"; echo "second=$?"; ls "$AFK_CTX_CACHE_DIR"
rm -f "$AFK_CTX_CACHE_DIR/probe"
"""
    return outcome(f, s, bash_code(f, code, s.path))


@case("hooks/gate-metrics.sh+hooks/gate-metrics-report.sh")
def _(f, s):
    code = f""". "$P/hooks/gate-metrics.sh"; gate_metrics_file; echo "file=$_GATE_METRICS_PATH"
gate_metrics_begin; gate_metrics_emit probe-{s.label} pass
bash "$P/hooks/gate-metrics-report.sh" | grep 'probe-{s.label}' | sed 's/p50=.*//'
"""
    return outcome(f, s, bash_code(f, code, s.path))


COMMENTED = "# one\n# two\n# three\ndef probe():\n    return 1\n"


@case("hooks/comment-gate.sh+hooks/lib/comment_gate.py", serial=True)
def _(f, s):
    """The staged blob lives in the worktree's index, never in its folder."""
    clean = sh(f, "hooks/comment-gate.sh", cwd=s.path)
    with staged(s, "probe_comment.py", COMMENTED):
        blocked = sh(f, "hooks/comment-gate.sh", cwd=s.path)
    return outcome(f, s, clean) + outcome(f, s, blocked)


@case("hooks/plugin-source-gates.sh")
def _(f, s):
    return outcome(f, s, sh(f, "hooks/plugin-source-gates.sh", "--staged", cwd=s.path))


for _gate in ("skill-registry", "native-contract", "genericity", "behavior-registry"):
    case(f"hooks/{_gate}-gate.sh")(lambda f, s, g=_gate: outcome(f, s, sh(f, f"hooks/{g}-gate.sh", cwd=s.path)))


@case("hooks/wiring-gate.sh+hooks/lib/bounded_scan.py", serial=True)
def _(f, s):
    plain = sh(f, "hooks/wiring-gate.sh", cwd=s.path)
    with staged(s, "orphan_probe_artifact.py", "VALUE = 1\n"):
        listed = sh(f, "hooks/wiring-gate.sh", "--list-candidates", cwd=s.path)
        judged = sh(f, "hooks/wiring-gate.sh", cwd=s.path)
    return outcome(f, s, plain) + outcome(f, s, listed) + outcome(f, s, judged)


@case("hooks/lib/provider.sh")
def _(f, s):
    code = """. "$P/hooks/lib/provider.sh"
echo "dir=[$(afk_plugin_dir)] provider=$(afk_provider) data=$(afk_plugin_data)"; afk_agent_session && echo agent
"""
    return outcome(f, s, bash_code(f, code, s.path))


def payload(f: Forest, s: Site, dry: bool) -> str:
    return json.dumps({"source": f.main.as_posix(), "worktree": s.path.as_posix(),
                       "worktree_native": s.path.as_posix(), "dry_run": dry})


@case("adapters/build-gate/maven/gates.sh")
def _(f, s):
    gates = "adapters/build-gate/maven/gates.sh"
    return [outcome(f, s, sh(f, gates, "gate-discover", cwd=s.path)),
            outcome(f, s, sh(f, gates, "gate-run", "maven-compile", cwd=s.path)),
            outcome(f, s, sh(f, gates, "worktree-provision", payload(f, s, True), cwd=s.path))]


@case("adapters/build-gate/maven/maven-lock.sh", writes=True)
def _(f, s):
    """Writes its lock folder `.claude/hooks/.maven.lock` into the worktree by design."""
    code = """. "$P/adapters/build-gate/maven/maven-lock.sh"
acquire_maven_lock 5 && echo acquired; ls -a .claude/hooks; release_maven_lock; ls -a .claude/hooks
"""
    return outcome(f, s, bash_code(f, code, s.path))


@case("adapters/build-gate/maven/worktree-provision.sh")
def _(f, s):
    """Already provisioned by the creator: the second run adopts and changes nothing."""
    return outcome(f, s, sh(f, "adapters/build-gate/maven/worktree-provision.sh", payload(f, s, False), cwd=s.path,
                            AFK_CFG_MAVEN_WORKTREE_SEED="none"))


@case("adapters/build-gate/npm/gates.sh+adapters/build-gate/npm/ui-lint-gate.sh")
def _(f, s):
    gates = "adapters/build-gate/npm/gates.sh"
    return [outcome(f, s, sh(f, gates, "gate-discover", cwd=s.path)),
            outcome(f, s, sh(f, gates, "gate-run", "ui-lint", cwd=s.path))]


@case("adapters/build-gate/npm/worktree-provision.sh")
def _(f, s):
    return outcome(f, s, sh(f, "adapters/build-gate/npm/worktree-provision.sh", payload(f, s, False), cwd=s.path))


@case("adapters/notes/common.sh+adapters/notes/repo-files/notes.sh", writes=True)
def _(f, s):
    """`note-create` writes the note into the worktree's spec folder by design."""
    notes = "adapters/notes/repo-files/notes.sh"
    note = json.dumps({"name": "probe-note.md", "content": "probe\n"})
    return [outcome(f, s, sh(f, notes, "resolve", "{}", cwd=s.path), "o"),
            outcome(f, s, sh(f, notes, "note-create", note, cwd=s.path), "o"),
            outcome(f, s, sh(f, notes, "note-read", note, cwd=s.path), "o")]


TRACKER = """
import types
class FastMCP:
    def __init__(self, name): pass
    def tool(self): return lambda fn: fn
for name, attrs in (("mcp", {}), ("mcp.server", {}), ("mcp.server.fastmcp", {"FastMCP": FastMCP})):
    module = types.ModuleType(name); module.__dict__.update(attrs); sys.modules[name] = module
sys.argv = ["server.py"]
"""


@case("scripts/tracker_api.py")
def _(f, s):
    return snippet(f, s, """
api = load("afk_tracker_api_probe", "scripts/tracker_api.py")
print(json.dumps([api.configured_kind(), api.load().call("tracker_get", {})]))
""")


@case("mcp-servers/tracker/server.py+adapters/tracker/none/api.py")
def _(f, s):
    return snippet(f, s, TRACKER + """
server = load("afk_tracker_server_probe", "mcp-servers/tracker/server.py")
print(json.dumps(server._call("tracker_get", ticket_key="X-1")))
""")


@case("scripts/create-worktree", kinds=CREATOR)
def _(f, s):
    done = sh(f, "scripts/create-worktree", "--name", f"cw-{s.label}", "--no-open", cwd=s.path)
    return done.returncode, f.norm(done.stdout.strip().splitlines()[-1], s)


@case("scripts/worktree-provision")
def _(f, s):
    return outcome(f, s, sh(f, "scripts/worktree-provision", "--worktree", s.path.as_posix(), cwd=s.path))


@case("scripts/worktree_owner.py", writes=True)
def _(f, s):
    """`append` writes the named file into the worktree by design; the manifest stays in the git dir."""
    copied = py(f, "scripts/worktree_owner.py", "copied", "--worktree", str(s.path), cwd=s.path)
    added = py(f, "scripts/worktree_owner.py", "append", "--worktree", str(s.path), ".probe-append", cwd=s.path,
               stdin="probe\n")
    manifest = json.loads((Path(gitdir(s)) / "afk-copied.json").read_text("utf-8"))
    return outcome(f, s, copied) + outcome(f, s, added) + (".probe-append" in manifest,)


@case("scripts/remove-worktree.py:report-kept")
def _(f, s):
    return outcome(f, s, py(f, "scripts/remove-worktree.py", "--report-kept", cwd=s.path))


@case("scripts/afk-move.py", kinds=CREATOR)
def _(f, s):
    marker = f.base / f"move-{s.label}.json"
    marker.write_text("{}", encoding="utf-8")
    done = py(f, "scripts/afk-move.py", "--repo", str(f.main), "--name", f"mv-{s.label}", "--session", "s-mv",
              "--provider", "claude", "--cwd", str(s.path), "--marker", str(marker), cwd=s.path)
    return done.returncode, f.norm(marker.read_text("utf-8"), s)


@case("scripts/afk-launch.py", kinds=PROT)
def _(f, s):
    """From a protected worktree it cuts a session worktree under the root, runs there, then removes it."""
    done = py(f, "scripts/afk-launch.py", sys.executable, "-c", "import os; print(os.getcwd())", cwd=s.path)
    return done.returncode, re.sub(r"session-[0-9a-f]{8}", "session-<ID>", f.norm(done.stdout, s).strip())


@case("scripts/placement.py")
def _(f, s):
    return snippet(f, s, """
placement = load("afk_placement_probe", "scripts/placement.py")
root, main = Path(os.environ["PROBE_ROOT"]), Path(os.environ["PROBE_MAIN"])
named = placement.target_for(str(S), "pl-probe")
inside = placement.check_target(str(root / "proj" / "x"), str(S))
outside = placement.check_target(str(main.parent / "elsewhere"), str(S))
print(json.dumps([named.state, named.target, named.folder, inside.state, outside.state, outside.rule]))
""")


@case("scripts/repo_list.py")
def _(f, s):
    return snippet(f, s, """
repo_list = load("afk_repo_list_probe", "scripts/repo_list.py")
main = repo_list.main_checkout(S)
print(json.dumps([main, repo_list.find_entry(main).short_name]))
""")


@case("scripts/protected-lookup.py", kinds=PROT)
def _(f, s):
    return [outcome(f, s, py(f, "scripts/protected-lookup.py", "--branch", s.branch, "--checkout", str(s.path),
                             cwd=s.path)),
            outcome(f, s, py(f, "scripts/protected-lookup.py", "--branch", "b-unprotected", "--checkout",
                             str(s.path), cwd=s.path))]


@case("scripts/afk-config.py")
def _(f, s):
    config = "scripts/afk-config.py"
    return [outcome(f, s, py(f, config, "get", "git.branch-pattern", cwd=s.path)),
            outcome(f, s, py(f, config, "resolve", "worktreeRoot", cwd=s.path)),
            outcome(f, s, py(f, config, "validate", cwd=s.path)),
            outcome(f, s, py(f, config, "init", cwd=s.path)),
            snippet(f, s, """
config = load("afk_config_probe", "scripts/afk-config.py")
top = config.git_root(S)
print(json.dumps([str(top), str(config.shared_overlay(top)), str(config.worktree_base(top)),
                  str(config.project_root())]))
""")]


@case("skills/afk/setup/scripts/ancestor_instruction_files.py",
      expect=lambda f, s, inside: (1, "<MAIN>/AGENTS.md") if s.label == "wq-on" else inside)
def _(f, s):
    """Inside the main checkout the main checkout's AGENTS.md really is above the worktree: a true report."""
    done = py(f, "skills/afk/setup/scripts/ancestor_instruction_files.py", str(s.path), cwd=s.path)
    strays = [line.strip().split("  (")[0] for line in done.stdout.splitlines() if line.startswith("  ")]
    return done.returncode, f.norm(";".join(Path(p).as_posix() for p in strays), s)


@case("skills/afk/setup/scripts/background_git_hooks.py")
def _(f, s):
    return [outcome(f, s, py(f, "skills/afk/setup/scripts/background_git_hooks.py", str(s.path), "--check",
                             cwd=s.path)),
            outcome(f, s, py(f, "skills/afk/setup/scripts/background_git_hooks.py", cwd=s.path))]


@case("skills/afk/setup/scripts/setup_secrets.py")
def _(f, s):
    """Answers: continue past the running-harness warning, decline git long paths."""
    return outcome(f, s, py(f, "skills/afk/setup/scripts/setup_secrets.py", cwd=s.path, stdin="y\nn\nn\n"))


@case("skills/afk/setup/scripts/developer_values.py")
def _(f, s):
    return [outcome(f, s, py(f, "skills/afk/setup/scripts/developer_values.py", "status", cwd=s.path)),
            outcome(f, s, py(f, "skills/afk/setup/scripts/developer_values.py", "status", "--repo", str(s.path),
                             cwd=f.base))]


@case("skills/afk/gc/scripts/gc-check.sh")
def _(f, s):
    done = sh(f, "skills/afk/gc/scripts/gc-check.sh", str(f.main / "docs" / "specs" / "feat"), s.branch, cwd=f.main)
    return outcome(f, s, done)[0], re.sub(r"WORKTREE_SIZE=\S+", "WORKTREE_SIZE=<SIZE>", f.norm(done.stdout, s))


@case("skills/afk/execute/scripts/verify-contract.sh")
def _(f, s):
    contract = s.path / "docs" / "specs" / "feat" / "plan" / "0001-probe.md"
    return [outcome(f, s, sh(f, "skills/afk/execute/scripts/verify-contract.sh", str(contract), "--direction",
                             "produces", "--root", str(s.path), cwd=f.base)),
            outcome(f, s, sh(f, "skills/afk/execute/scripts/verify-contract.sh", str(contract), "--direction",
                             "produces", cwd=s.path))]


@case("skills/afk/mission-control/scripts/mission_control.py", writes=True)
def _(f, s):
    """`--once` writes the dashboard into `<spec>/plan/mission-control` by design."""
    spec = s.path / "docs" / "specs" / "feat"
    script = "skills/afk/mission-control/scripts/mission_control.py"
    return [outcome(f, s, py(f, script, str(spec), "--check-digests", cwd=s.path), "o"),
            outcome(f, s, py(f, script, str(spec), "--once", cwd=s.path), "")]


@case("skills/afk/mission-control/scripts/mc/sections/understanding.py")
def _(f, s):
    return snippet(f, s, """
sys.path.insert(0, str(P / "skills" / "afk" / "mission-control" / "scripts"))
from mc.sections import understanding
spec = S / "docs" / "specs" / "feat"
print(understanding._repo_relative(spec, spec / "UNDERSTANDING.html"))
""")


@case("skills/afk/to-subtasks/scripts/validate_plan.py")
def _(f, s):
    return outcome(f, s, py(f, "skills/afk/to-subtasks/scripts/validate_plan.py",
                            str(s.path / "docs" / "specs" / "feat" / "plan"), cwd=s.path))


@case("skills/afk/review/scripts/forge_ledger.py")
def _(f, s):
    return snippet(f, s, """
ledger = load("afk_forge_ledger_probe", "skills/afk/review/scripts/forge_ledger.py")
print(json.dumps([str(ledger.cache_root(str(S)).parent), str(ledger.pending_dir(str(S)))]))
""", AFK_RATIONALE_CACHE=str(f.base / "rationale-cache"))


@case("skills/utils/investigate/scripts/write_report.py", writes=True)
def _(f, s):
    """Writes REPORT.md beside the ledger, inside the worktree, by design."""
    sys.path.insert(0, str(TESTS))
    from test_validate_coverage import ledger
    document = ledger()
    document["run"]["verdict"] = "closed"
    folder = s.path / "docs" / "inv" / "INV-001-probe"
    folder.mkdir(parents=True)
    (folder / "COVERAGE.json").write_text(json.dumps(document), encoding="utf-8")
    done = py(f, "skills/utils/investigate/scripts/write_report.py", "--ledger", str(folder / "COVERAGE.json"),
              cwd=s.path, stdin="## Answer\n\nprobe\n")
    return outcome(f, s, done) + (f.norm((folder / "REPORT.md").read_text("utf-8").splitlines()[0], s),)


@case("skills/utils/report-issue/scripts/publish.sh:list")
def _(f, s):
    return outcome(f, s, sh(f, "skills/utils/report-issue/scripts/publish.sh", "--list", cwd=s.path))


@case("hooks/lesson-append.sh", serial=True)
def _(f, s):
    done = sh(f, "hooks/lesson-append.sh", "opened", "--class", "wrong-term", "--target", "a.txt", "--summary",
              "probe", cwd=s.path)
    ledger = f.main / ".claude" / "lessons" / "LEDGER.jsonl"
    last = json.loads(ledger.read_text("utf-8").splitlines()[-1])
    return done.returncode, re.sub(r"L-\d+", "L-<N>", done.stdout.strip()), last.get("target")


@case("hooks/lesson-digest.sh")
def _(f, s):
    return [outcome(f, s, sh(f, "hooks/lesson-digest.sh", "--count", cwd=s.path)),
            outcome(f, s, sh(f, "hooks/lesson-digest.sh", "--all", cwd=s.path))]


@case("hooks/stall-watchdog.sh")
def _(f, s):
    return outcome(f, s, sh(f, "hooks/stall-watchdog.sh", "--path", gitdir(s), "--stale-min", "0", "--cap-min", "1",
                            "--poll-sec", "1", "--label", "probe", cwd=s.path))


@case("scripts/lavish/inject.py", writes=True)
def _(f, s):
    """Rewrites the page it injects, inside the worktree, by design."""
    page = s.path / "docs" / "specs" / "feat" / "probe-page.html"
    page.write_text("<html><head></head><body>Zorblax</body></html>\n", encoding="utf-8")
    changed = snippet(f, s, """
inject = load("afk_inject_probe", "scripts/lavish/inject.py")
print(json.dumps(inject.inject_file(str(S / "docs" / "specs" / "feat" / "probe-page.html"))))
""")
    return changed, "a probe term only this repository defines" in page.read_text("utf-8")


@case("skills/utils/investigate/scripts/seed_map.py")
def _(f, s):
    out = f.base / f"seed-{s.label}.json"
    done = py(f, "skills/utils/investigate/scripts/seed_map.py", "--repo", str(s.path), "--subject", "Zorblax",
              "--type", "Q1", "--out", str(out), cwd=s.path)
    found = json.loads(out.read_text("utf-8")) if out.is_file() else {}
    run_block = {k: v for k, v in (found.get("run") or {}).items() if k not in ("started", "finished", "at")}
    return done.returncode, f.norm(json.dumps([run_block, sorted(found)], sort_keys=True), s)


# --- comparing an outside worktree with its twin under the root -----------------------------------

def snapshot(folder: Path) -> dict:
    found = {}
    for top, dirs, files in os.walk(folder):
        rel = Path(top).relative_to(folder).as_posix()
        for name in dirs:
            found[f"{rel}/{name}/"] = None
        for name in files:
            found[f"{rel}/{name}"] = (Path(top) / name).read_bytes()
    return found


def changes(before: dict, after: dict) -> set:
    found = {(k, "added") for k in after.keys() - before.keys()}
    found |= {(k, "removed") for k in before.keys() - after.keys()}
    return found | {(k, "changed") for k in before.keys() & after.keys() if before[k] != after[k]}


def restore(folder: Path, before: dict, after: dict) -> None:
    for key in sorted(after.keys() - before.keys(), key=len, reverse=True):
        target = folder / key
        shutil.rmtree(target) if key.endswith("/") else target.unlink()
    for key, data in sorted(before.items()):
        target = folder / key
        if key.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        elif after.get(key) != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


_LOCK = threading.Lock()


def observe(forest: Forest, item: Case, site: Site):
    before = snapshot(site.path)
    value = item.probe(forest, site)
    after = snapshot(site.path)
    if item.writes:
        restore(site.path, before, after)
    if os.environ.get("OUTSIDE_DUMP"):  # debugging aid: write each observed value to this file
        with _LOCK, open(os.environ["OUTSIDE_DUMP"], "a", encoding="utf-8") as out:
            out.write(f"{item.member} {site.label}: {value!r}\n")
    return value, changes(before, after)


CRASHES = ("Traceback (most recent call last)", ": command not found", "SyntaxError", "unexpected failure near line",
           "No such file or directory", "usage: ")


def crash_in(value) -> str | None:
    """A crash text inside an observed value: a member broken on both twins must not pass as parity."""
    text = repr(value)
    return next((mark for mark in CRASHES if mark in text), None)


def observe_pairs(forest: Forest, item: Case) -> list[tuple]:
    sites = [site for kind in item.kinds for site in forest.pairs[kind]]
    jobs = [lambda s=s: observe(forest, item, s) for s in sites]
    seen = dict(zip([s.label for s in sites], [job() for job in jobs] if item.serial else parallel(jobs)))
    pairs = []
    for kind in item.kinds:
        outside, inside = forest.pairs[kind]
        (out_value, out_changes), (in_value, in_changes) = seen[outside.label], seen[inside.label]
        assert crash_in(in_value) is None, f"{kind}: the member crashed under the root\n{in_value!r}"
        expected = item.expect(forest, outside, in_value)
        assert out_value == expected, f"{kind}: outside {outside.path}\n{out_value!r}\n!= inside\n{in_value!r}"
        pairs.append((kind, out_changes, in_changes))
    return pairs


@pytest.mark.parametrize("item", [c for c in CASES if not c.writes], ids=lambda c: c.member)
def test_a_reading_member_behaves_on_an_outside_worktree_as_on_its_twin_and_changes_neither(forest, item):
    for kind, out_changes, in_changes in observe_pairs(forest, item):
        assert not out_changes and not in_changes, f"{kind}: {sorted(out_changes)} / {sorted(in_changes)}"


@pytest.mark.parametrize("item", [c for c in CASES if c.writes], ids=lambda c: c.member)
def test_a_writing_member_makes_the_same_changes_in_an_outside_worktree_as_in_its_twin(forest, item):
    for kind, out_changes, in_changes in observe_pairs(forest, item):
        assert in_changes, f"{kind}: the member wrote nothing under the root"
        assert out_changes == in_changes, f"{kind}: {sorted(out_changes)} != {sorted(in_changes)}"


def test_every_excluded_member_names_a_plugin_file_and_a_part_exclusion_names_a_tested_member():
    tested = {part.split(":")[0] for case in CASES for part in case.member.split("+")}
    for key in EXCLUDED:
        path, _, part = key.partition(" (")
        assert (PLUGIN_ROOT / path).is_file(), key
        assert (path in tested) == bool(part), f"{key}: a '(part)' key needs a case for the rest, a whole key none"


# --- cleanup removes an outside worktree as it removes one under the root -------------------------

def removal_state(repo: Path, path: Path, label: str) -> tuple:
    record = repo / ".git" / "afk-worktrees" / f"{label}.json"
    return path.exists(), git(repo, "branch", "--list", f"worktree-{label}") != "", record.exists()


@pytest.mark.parametrize("member", ["hooks/worktree-remove.sh", "scripts/remove-worktree.py",
                                    "hooks/worktree-prune.sh:dead-owner"])
def test_cleanup_removes_an_outside_worktree_as_it_removes_one_under_the_root(forest, member):
    name = {"hooks/worktree-remove.sh": "rmhook", "scripts/remove-worktree.py": "rmpy"}.get(member, "prune")
    repo, outside, inside = forest.disposable[name]
    assert removal_state(repo, outside, "wq-on") == removal_state(repo, inside, "wq-in") == (True, True, True)
    codes = []
    if member == "hooks/worktree-prune.sh:dead-owner":
        codes.append(sh(forest, "hooks/worktree-prune.sh", cwd=repo).returncode)
    for path in (outside, inside):
        if member == "hooks/worktree-remove.sh":
            envelope = {"session_id": "s-rm", "cwd": str(repo), "hook_event_name": "WorktreeRemove",
                        "worktree_path": str(path)}
            codes.append(sh(forest, "hooks/worktree-remove.sh", cwd=repo, stdin=json.dumps(envelope)).returncode)
        elif member == "scripts/remove-worktree.py":
            codes.append(py(forest, "scripts/remove-worktree.py", "--path", str(path), cwd=repo).returncode)
    assert set(codes) == {0}
    assert removal_state(repo, outside, "wq-on") == removal_state(repo, inside, "wq-in") == (False, False, False)
    assert git(repo, "worktree", "list", "--porcelain").count("worktree ") == 1
