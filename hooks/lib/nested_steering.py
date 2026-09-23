#!/usr/bin/env python3
"""Collect the AGENTS.md (+ matching `.claude/rules`) below the launch directory.

    nested_steering.py --provider P --mode M --rules 0|1 --data-dir DIR < envelope

Reads a hook envelope on stdin and prints, on stdout, the instruction files a
harness that loaded only the launch-directory chain has not seen: every
`AGENTS.md` in a directory strictly below the launch directory (`cwd`) on the
path down to a directory the tool touched, deepest last, plus — when
`--rules 1` — the body of every `.claude/rules/*.md` whose `paths:` frontmatter
matches a touched path (matcher: rule_paths_match.py). Prints nothing when there
is nothing to add. Always exits 0; a failure or a hit deadline is logged to
stderr, never a silent skip.

Deduplication: one marker per (session, agent, directory), created atomically
with a directory `mkdir`, under `<data-dir>/nested-steering/`. The marker is
claimed BEFORE the file is read, so a crash mid-run never re-injects. The whole
session subtree is removed on a reset event (SessionStart / PostCompact), which
the caller routes here.

Mode/rules are the provider's policy, passed in by the caller (owned in
hooks/lib/providers/<name>.sh). This module is provider-agnostic mechanics.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rule_paths_match as rpm  # noqa: E402

PER_FILE_BYTES = 8192           # cap per injected file
PER_INJECTION_BYTES = 32768     # cap across one injection
DEADLINE_S = 8.0                # shorter than the registered hook timeout
RESET_EVENTS = ("SessionStart", "PostCompact")
INJECT_EVENTS = ("PostToolUse", "PreToolUse")


def log(msg):
    sys.stderr.write("nested-steering: %s\n" % msg)


def casefold(text):
    return text.lower() if os.name == "nt" else text


def digest(text):
    return hashlib.sha1(casefold(text).encode("utf-8", "replace")).hexdigest()[:16]


def marker_root(data_dir):
    return Path(data_dir) / "nested-steering"


def reset(data_dir, session):
    tree = marker_root(data_dir) / digest(session)
    if tree.is_dir():
        shutil.rmtree(tree, ignore_errors=True)


def claim(data_dir, session, agent, key):
    """Atomically claim (session, agent, key); True when newly claimed."""
    parent = marker_root(data_dir) / digest(session) / digest(agent)
    try:
        parent.mkdir(parents=True, exist_ok=True)
        (parent / digest(key)).mkdir(exist_ok=False)
        return True
    except FileExistsError:
        return False
    except OSError:
        return False


def repo_root(cwd):
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return Path(cwd).resolve()


def collect_strings(obj, out):
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            collect_strings(value, out)
    elif isinstance(obj, list):
        for value in obj:
            collect_strings(value, out)


def candidate_strings(tool_input):
    """Path-like strings from a tool input: path fields and command tokens."""
    raw = []
    collect_strings(tool_input, raw)
    cands = set()
    for s in raw:
        s = s.strip()
        if not s:
            continue
        cands.add(s)                      # a whole path field
        for tok in s.replace("\\", "/").split():
            tok = tok.strip("'\"`()<>|;,")
            if "/" in tok:
                cands.add(tok)            # a path named inside a command line
    return cands


def touched_paths(cands, cwd, root):
    """Resolved paths under `root` that a candidate string names."""
    out = []
    seen = set()
    root = root.resolve()
    for c in cands:
        c = c.replace("\\", "/")
        try:
            p = (Path(cwd) / c).resolve()
        except OSError:
            continue
        anchor = p if p.exists() else (p.parent if p.parent.exists() else None)
        if anchor is None:
            continue
        try:
            anchor.relative_to(root)
        except ValueError:
            continue
        key = casefold(str(p))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def chain_below(directory, ceiling):
    """Directories strictly below `ceiling` on the path down to `directory`.

    Shallow first, so the caller emits deepest last. Empty when `directory` is
    not strictly below `ceiling`.
    """
    directory = directory.resolve()
    ceiling = ceiling.resolve()
    try:
        directory.relative_to(ceiling)
    except ValueError:
        return []
    if directory == ceiling:
        return []
    chain = []
    cur = directory
    while cur != ceiling:
        chain.append(cur)
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    chain.reverse()
    return chain


def rel_posix(path, root):
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def read_capped(path):
    try:
        return path.read_bytes()[:PER_FILE_BYTES].decode("utf-8", "replace")
    except OSError:
        return None


def gather(paths, cwd, root, inject_rules, data_dir, session, agent, start):
    ceiling = Path(cwd).resolve()
    pieces = []          # (kind, rel, body)
    total = 0

    # AGENTS.md chain below the launch directory.
    dirs = []
    seen = set()
    for p in paths:
        d = p if p.is_dir() else p.parent
        for g in chain_below(d, ceiling):
            key = casefold(str(g))
            if key not in seen:
                seen.add(key)
                dirs.append(g)
    dirs.sort(key=lambda g: len(g.parts))       # shallow first, deepest last
    for g in dirs:
        if time.monotonic() - start > DEADLINE_S:
            log("internal deadline %.0fs reached; emitting partial context" % DEADLINE_S)
            break
        f = g / "AGENTS.md"
        if not f.is_file():
            continue
        if not claim(data_dir, session, agent, "agents:" + casefold(str(g))):
            continue
        body = read_capped(f)
        if body is None:
            continue
        if total + len(body) > PER_INJECTION_BYTES:
            log("per-injection budget reached; stopping")
            break
        pieces.append(("AGENTS.md", rel_posix(f, root), body))
        total += len(body)

    if not inject_rules:
        return pieces

    # Path-scoped `.claude/rules` bodies, matched per touched path.
    for p in sorted(paths, key=lambda x: len(x.parts)):
        if time.monotonic() - start > DEADLINE_S:
            log("internal deadline %.0fs reached; emitting partial context" % DEADLINE_S)
            break
        anchor = p if p.is_dir() else p.parent
        for base in [anchor] + list(anchor.parents):
            try:
                base.relative_to(root)
            except ValueError:
                break                                # above the repo root
            rules_dir = base / ".claude" / "rules"
            if not rules_dir.is_dir():
                continue
            rel = rel_posix(p, base)
            for rule in sorted(rules_dir.glob("*.md")):
                body = read_capped(rule)
                if body is None:
                    continue
                if not rpm.rule_matches(body, rel):
                    continue
                if not claim(data_dir, session, agent, "rule:" + casefold(str(rule))):
                    continue
                if total + len(body) > PER_INJECTION_BYTES:
                    log("per-injection budget reached; stopping")
                    return pieces
                pieces.append(("rule", rel_posix(rule, root), body))
                total += len(body)
    return pieces


def render(pieces):
    if not pieces:
        return ""
    lines = [
        "[afk nested steering] Instruction files below your working directory "
        "that were not loaded at the start of this run. Follow them for work in "
        "their directories, deepest last winning:"
    ]
    for kind, rel, body in pieces:
        lines.append("")
        lines.append("===== %s (%s) =====" % (rel, kind))
        lines.append(body.rstrip("\n"))
    return "\n".join(lines) + "\n"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="unknown")
    ap.add_argument("--mode", default="never")
    ap.add_argument("--rules", default="0")
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args(argv)

    data_dir = args.data_dir or str(Path.home() / ".afk" / "data" / "nested-steering-fallback")

    try:
        envelope = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except ValueError:
        return 0
    if not isinstance(envelope, dict):
        return 0

    event = str(envelope.get("hook_event_name") or "")
    session = str(envelope.get("session_id") or "default")
    agent_id = str(envelope.get("agent_id") or "").strip()
    agent = agent_id or "main"
    cwd = envelope.get("cwd") or os.getcwd()
    start = time.monotonic()

    try:
        if event in RESET_EVENTS:
            reset(data_dir, session)
            return 0
        if event not in INJECT_EVENTS:
            return 0
        if args.mode == "never":
            return 0
        if args.mode == "agent-only" and not agent_id:
            return 0
        tool_input = envelope.get("tool_input") or {}
        root = repo_root(cwd)
        cands = candidate_strings(tool_input)
        paths = touched_paths(cands, cwd, root)
        pieces = gather(paths, cwd, root, args.rules == "1",
                        data_dir, session, agent, start)
        text = render(pieces)
        if text:
            sys.stdout.write(text)
    except Exception as problem:                        # never crash a turn silently
        log("error: %s" % problem)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
