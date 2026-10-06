"""bounded_scan.py: resolution rule, staging, bounds, failure and lock behaviour (temp repos only)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

HELPER = Path(__file__).resolve().parents[2] / "hooks" / "lib" / "bounded_scan.py"
spec = importlib.util.spec_from_file_location("bounded_scan", HELPER)
bs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bs)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    return root


def put(repo: Path, rel: str, body: str | bytes = "") -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
    return rel


def track(repo: Path) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "x", "--allow-empty")


def pairs_of(*cands: str) -> list[tuple[str, str]]:
    return [(c, Path(c).stem) for c in cands]


def do_scan(repo: Path, pairs, local=(), excludes=(), deadline=60, **kw) -> dict:
    return bs.scan(str(repo), list(pairs), list(local), list(excludes), deadline, **kw)


def cli(repo: Path, tmp: Path, pairs, local=(), *extra: str, env=None):
    cand = tmp / "cand.bin"
    cand.write_bytes(b"".join(c.encode() + b"\0" + t.encode() + b"\0" for c, t in pairs))
    loc = tmp / "local.bin"
    loc.write_bytes(b"".join(p.encode() + b"\0" for p in local))
    result = tmp / "result.json"
    lock = tmp / "scan.lock"
    full_env = dict(os.environ, **(env or {}))
    done = subprocess.run(
        [sys.executable, str(HELPER), "--repo", str(repo), "--candidates", str(cand),
         "--local", str(loc), "--result", str(result), "--lock", str(lock), *extra],
        capture_output=True, text=True, env=full_env,
    )
    payload = json.loads(result.read_text()) if result.exists() else None
    return done.returncode, payload


# ---- resolution rule ---------------------------------------------------------

def test_self_only_reference_is_not_wired(repo):
    put(repo, "lib/widget_core.py", "widget_core = 1\n")
    track(repo)
    out = do_scan(repo, pairs_of("lib/widget_core.py"))
    assert out["status"] == "complete"
    assert out["wired"] == [] and out["unresolved"] == ["lib/widget_core.py"]


def test_other_file_reference_wires(repo):
    put(repo, "lib/widget_core.py", "x\n")
    put(repo, "app/main.py", "import widget_core\n")
    track(repo)
    out = do_scan(repo, pairs_of("lib/widget_core.py"))
    assert out["wired"] == ["lib/widget_core.py"]


def test_duplicate_basenames_need_a_third_file(repo):
    put(repo, "a/shared_name.py", "shared_name\n")
    put(repo, "b/shared_name.py", "shared_name\n")
    track(repo)
    pairs = pairs_of("a/shared_name.py", "b/shared_name.py")
    out = do_scan(repo, pairs)
    # each candidate is referenced by the other
    assert sorted(out["wired"]) == ["a/shared_name.py", "b/shared_name.py"]
    git(repo, "rm", "-q", "--cached", "b/shared_name.py")
    (repo / "b" / "shared_name.py").write_text("nothing\n")
    out = do_scan(repo, pairs_of("a/shared_name.py"))
    assert out["wired"] == []


def test_overlapping_tokens(repo):
    put(repo, "x/validate.py", "def f(): pass\n")
    put(repo, "x/validate_glossary.py", "def g(): pass\n")
    track(repo)
    out = do_scan(repo, pairs_of("x/validate.py", "x/validate_glossary.py"))
    # `validate` is a substring of validate_glossary.py's own name? Only in content:
    # file contents hold neither token, so neither is wired.
    assert out["wired"] == []
    put(repo, "x/caller.py", "validate_glossary()\n")
    out = do_scan(repo, pairs_of("x/validate.py", "x/validate_glossary.py"))
    assert sorted(out["wired"]) == ["x/validate.py", "x/validate_glossary.py"]


def test_substring_match_wires(repo):
    put(repo, "src/hook.py", "pass\n")
    put(repo, "docs/webhooks.md", "see webhooks\n")
    track(repo)
    out = do_scan(repo, pairs_of("src/hook.py"))
    assert out["wired"] == ["src/hook.py"]


# ---- file kinds & exclusions -------------------------------------------------

def test_untracked_wires_and_ignored_does_not(repo):
    put(repo, ".gitignore", "build/\n")
    put(repo, "lib/gadget_thing.py", "x\n")
    track(repo)
    put(repo, "notes/new.md", "gadget_thing\n")  # untracked
    assert do_scan(repo, pairs_of("lib/gadget_thing.py"))["wired"] == ["lib/gadget_thing.py"]
    (repo / "notes" / "new.md").unlink()
    put(repo, "build/out.md", "gadget_thing\n")  # ignored
    assert do_scan(repo, pairs_of("lib/gadget_thing.py"))["wired"] == []


def test_binary_and_missing_files(repo):
    put(repo, "lib/gizmo_part.py", "x\n")
    put(repo, "blob.bin", b"\0\0gizmo_part\0")
    track(repo)
    out = do_scan(repo, pairs_of("lib/gizmo_part.py"), local=["blob.bin", "gone.txt"])
    assert out["wired"] == []


def test_exclusions(repo):
    put(repo, "lib/gizmo_part.py", "x\n")
    put(repo, ".claude/wiring-ious.md", "gizmo_part\n")
    put(repo, ".claude/hooks/h.sh", "gizmo_part\n")
    put(repo, "skip/ref.md", "gizmo_part\n")
    track(repo)
    out = do_scan(repo, pairs_of("lib/gizmo_part.py"),
                  local=[".claude/wiring-ious.md", ".claude/hooks/h.sh", "skip/ref.md"], excludes=["skip/*"])
    assert out["wired"] == []
    out = do_scan(repo, pairs_of("lib/gizmo_part.py"), excludes=["skip/*"])
    assert out["wired"] == []
    out = do_scan(repo, pairs_of("lib/gizmo_part.py"))
    assert out["wired"] == ["lib/gizmo_part.py"]


@pytest.mark.parametrize("name", ["naïve ünï/ref file.md", "tab\tdir/ref.md"])
def test_odd_paths(repo, name):
    if "\t" in name and os.name == "nt":
        pytest.skip("tab is not a legal Windows path character")
    put(repo, "lib/oddname_tok.py", "x\n")
    put(repo, name, "oddname_tok\n")
    track(repo)
    out = do_scan(repo, pairs_of("lib/oddname_tok.py"))
    assert out["wired"] == ["lib/oddname_tok.py"]
    out = do_scan(repo, pairs_of("lib/oddname_tok.py"), local=[name])
    assert out["wired"] == ["lib/oddname_tok.py"] and out["tokens_tree"] == 0


def test_large_pattern_set_beyond_argv(repo):
    names = [f"tokenfile_{i:05d}_{'x' * 40}" for i in range(1500)]
    for n in names:
        put(repo, f"gen/{n}.txt", "x\n")
    put(repo, "ref/all.md", "\n".join(names) + "\n")
    track(repo)
    cands = [f"gen/{n}.txt" for n in names]
    assert sum(len(n) for n in names) > 60_000
    out = do_scan(repo, pairs_of(*cands))
    assert len(out["wired"]) == 1500


# ---- staging & bounds --------------------------------------------------------

def test_output_bound(repo):
    for i in range(40):
        put(repo, f"gen/dense_{i:03d}.txt", "x\n")
    body = "\n".join(f"dense_{i:03d}" for i in range(40)) * 1
    for j in range(30):
        put(repo, f"ref/r{j}.md", body + "\n")
    track(repo)
    out = do_scan(repo, pairs_of(*[f"gen/dense_{i:03d}.txt" for i in range(40)]))
    assert len(out["wired"]) + len(out["unresolved"]) == 40
    assert len(json.dumps(out)) < 20_000


def test_stage_one_resolves_generic_tokens(repo):
    put(repo, "lib/commonname.py", "x\n")
    put(repo, "lib/raretoken.py", "x\n")
    put(repo, "changed/ref.md", "commonname\n")
    put(repo, "far/away.md", "raretoken\n")
    track(repo)
    out = do_scan(repo, pairs_of("lib/commonname.py", "lib/raretoken.py"), local=["changed/ref.md"])
    assert out["tokens_total"] == 2 and out["tokens_local_resolved"] == 1 and out["tokens_tree"] == 1
    assert sorted(out["wired"]) == ["lib/commonname.py", "lib/raretoken.py"]


def test_restart_on_shrink_reads_fewer_files(repo):
    put(repo, "lib/alphatok.py", "x\n")
    put(repo, "lib/betatok.py", "x\n")
    for i in range(300):
        put(repo, f"aaa/f{i:03d}.txt", "alphatok\n")
    put(repo, "zzz/last.txt", "betatok\n")
    put(repo, "zzz/second.txt", "betatok alphatok\n")
    track(repo)
    pairs = pairs_of("lib/alphatok.py", "lib/betatok.py")
    plain = do_scan(repo, pairs, max_restarts=0)
    fast = do_scan(repo, pairs)
    assert sorted(plain["wired"]) == sorted(fast["wired"]) == ["lib/alphatok.py", "lib/betatok.py"]
    assert plain["restarts"] == 0 and fast["restarts"] >= 1
    assert fast["files_read"] < plain["files_read"]


def test_early_termination_is_complete(repo):
    put(repo, "lib/solotok.py", "x\n")
    for i in range(50):
        put(repo, f"d/f{i:02d}.txt", "solotok\n")
    track(repo)
    out = do_scan(repo, pairs_of("lib/solotok.py"))
    assert out["status"] == "complete" and out["files_read"] < 50


# ---- failure modes -----------------------------------------------------------

def fake_git(tmp_path: Path, body: str) -> list[str]:
    script = tmp_path / "fakegit.py"
    script.write_text(textwrap.dedent(body))
    return [sys.executable, str(script)]


def test_git_failure_is_scan_failure(repo, tmp_path):
    put(repo, "lib/failtok.py", "x\n")
    track(repo)
    cmd = fake_git(tmp_path, "import sys\nsys.exit(128)\n")
    with pytest.raises(bs.Unknown) as caught:
        do_scan(repo, pairs_of("lib/failtok.py"), git_cmd=cmd)
    assert caught.value.detail == "scan_failure"


def test_killed_git_is_scan_failure(repo, tmp_path):
    put(repo, "lib/failtok.py", "x\n")
    track(repo)
    cmd = fake_git(tmp_path, "import sys\nsys.exit(143)\n")
    with pytest.raises(bs.Unknown) as caught:
        do_scan(repo, pairs_of("lib/failtok.py"), git_cmd=cmd)
    assert caught.value.detail == "scan_failure"


def test_deadline_is_timeout_and_git_is_gone(repo, tmp_path):
    put(repo, "lib/slowtok.py", "x\n")
    track(repo)
    marker = tmp_path / "pid.txt"
    cmd = fake_git(tmp_path, f"import os, time\nopen({str(marker)!r}, 'w').write(str(os.getpid()))\ntime.sleep(60)\n")
    start = time.monotonic()
    with pytest.raises(bs.Unknown) as caught:
        do_scan(repo, pairs_of("lib/slowtok.py"), deadline=2, git_cmd=cmd)
    assert caught.value.detail == "timeout"
    assert time.monotonic() - start < 15
    pid = int(marker.read_text())
    assert not pid_alive(pid)


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_bad_input(repo, tmp_path):
    cand = tmp_path / "c.bin"
    cand.write_bytes(b"onlypath\0")
    result = tmp_path / "r.json"
    loc = tmp_path / "l.bin"
    loc.write_bytes(b"")
    code = bs.run(["--repo", str(repo), "--candidates", str(cand), "--local", str(loc),
                   "--result", str(result), "--lock", str(tmp_path / "l.lock")])
    assert code == 75 and json.loads(result.read_text())["detail"] == "bad_input"
    cand.write_bytes(b"a.py\0tokx\0a.py\0tokx\0")
    code = bs.run(["--repo", str(repo), "--candidates", str(cand), "--local", str(loc),
                   "--result", str(result), "--lock", str(tmp_path / "l.lock")])
    assert code == 75


def test_cli_complete_verdict(repo, tmp_path):
    put(repo, "lib/clitok.py", "x\n")
    put(repo, "ref.md", "clitok\n")
    track(repo)
    code, payload = cli(repo, tmp_path, pairs_of("lib/clitok.py"))
    assert code == 0 and payload["status"] == "complete" and payload["wired"] == ["lib/clitok.py"]


HOLDER = """
import sys, time
sys.path.insert(0, {lib!r})
import bounded_scan as bs
lock = bs.LockFile({path!r})
assert lock.acquire()
print("held", flush=True)
time.sleep(120)
"""


def test_lock_busy_then_released_after_holder_killed(repo, tmp_path):
    put(repo, "lib/locktok.py", "x\n")
    track(repo)
    lock_path = tmp_path / "scan.lock"
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLDER.format(lib=str(HELPER.parent), path=str(lock_path))],
        stdout=subprocess.PIPE, text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "held"
        code, payload = cli(repo, tmp_path, pairs_of("lib/locktok.py"))
        assert code == 75 and payload["detail"] == "lock_busy" and payload["files_read"] == 0
    finally:
        holder.kill()
        holder.wait()
    code, payload = cli(repo, tmp_path, pairs_of("lib/locktok.py"))
    assert code == 0 and payload["status"] == "complete"


# ---- performance (diagnostic-tolerant) ---------------------------------------

def test_serial_perf_ratio_vs_legacy_pipeline(repo):
    for d in range(60):
        for i in range(200):
            put(repo, f"src/d{d:02d}/file{i:03d}.txt", f"line {d} {i}\nmore filler text here\n")
    cands = []
    for i in range(30):
        name = f"lib/perfcand{i:02d}.py"
        put(repo, name, "x\n")
        put(repo, f"src/d00/refs{i:02d}.txt", f"perfcand{i:02d} generic_x\n")
        cands.append(name)
    track(repo)
    pairs = pairs_of(*cands)
    t0 = time.monotonic()
    legacy_args = [a for _, t in pairs for a in ("-e", t)]
    subprocess.run(["git", "-C", str(repo), "grep", "-o", "-I", "--untracked", "-F", *legacy_args],
                   capture_output=True)
    legacy = time.monotonic() - t0
    t0 = time.monotonic()
    out = do_scan(repo, pairs, deadline=100)
    new = time.monotonic() - t0
    assert len(out["wired"]) == 30
    print(f"legacy={legacy:.2f}s new={new:.2f}s files=12000")
    assert new < max(legacy * 3, 20)
