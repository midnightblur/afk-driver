#!/usr/bin/env python3
"""Deterministic instruction-file mechanical checks for the AGENTS.md standard.

    python mechanical_check.py <repo_root>

Discovers only the instruction files the standard governs, scoped to
<repo_root> (never scans system roots): AGENTS.md, .claude/AGENTS.md,
CLAUDE.md, .claude/CLAUDE.md, CLAUDE.local.md, AGENTS.override.md, and
.claude/rules/**/*.md. Reports one line per finding under a stable tag; the
steward judges. Exit 0 always (a report, not a gate); exit 2 only on wrong argv.

Findings (tags):
  [size > 200]     file over 200 lines
  [bytes > N]      file over 32768 bytes (Codex per-file budget)
  [chain > 32768]  a root -> directory chain (one file per directory, candidate
                   order AGENTS.override.md, AGENTS.md, CLAUDE.md) over 32768 B
  [import]         an @path import inside an AGENTS.md / .claude/AGENTS.md
  [bridge]         a root CLAUDE.md that is not exactly `@AGENTS.md`, when a
                   root AGENTS.md exists
  [migrate]        a CLAUDE.md / .claude/CLAUDE.md other than the root bridge
                   (advisory migration list, not a failure)
  [override]       an AGENTS.override.md anywhere in the repo
  [tracked-local]  a git-tracked CLAUDE.local.md or AGENTS.override.md
  [rule-paths]     a .claude/rules/*.md with no `paths:` frontmatter key
  [broken-import]  an @path import in a CLAUDE.md that resolves to no file

claudeMdExcludes: read from <root>/.claude/settings.json and
settings.local.json (union of the two `claudeMdExcludes` arrays). A discovered
file is dropped from every finding when a pattern matches. Match semantics: the
pattern is tested with fnmatch against the repo-root-relative POSIX path; a
pattern with no `/` is also tested against the file's basename.
"""
import fnmatch
import json
import os
import re
import subprocess
import sys

SIZE_LIMIT = 200
BYTE_LIMIT = 32768
SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", "out", "vendor", ".idea", ".gradle"}
CHAIN_CANDIDATES = ("AGENTS.override.md", "AGENTS.md", "CLAUDE.md")
INSTRUCTION_NAMES = {"AGENTS.md", "CLAUDE.md", "CLAUDE.local.md", "AGENTS.override.md"}
# `@path` import: `@` then a path ending in `.md`. Broadened past the old
# `[~./]`-only anchor so a bare import (`@AGENTS.md`, `@shared/rules.md`) is
# caught too — the root bridge's `@AGENTS.md` is itself a bare import.
IMPORT_RE = re.compile(r"(?:^|\s)@([~./\w][^\s]*\.md)")
PATHS_KEY_RE = re.compile(r"(?m)^paths\s*:")


def rel_posix(path, root):
    return os.path.relpath(path, root).replace(os.sep, "/")


def under_claude_rules(dp, root):
    """True when dp is `.claude/rules` or below it (the `rules` dir's parent is `.claude`)."""
    rel = rel_posix(dp, root)
    if rel == ".":
        return False
    parts = rel.split("/")
    return any(parts[i] == "rules" and i > 0 and parts[i - 1] == ".claude"
               for i in range(len(parts)))


def discover(root):
    """Yield (full_path, kind) for every governed instruction file under root.

    kind is one of: agents, claude, claude_local, override, rule.
    """
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        in_rules = under_claude_rules(dp, root)
        for fn in fns:
            full = os.path.join(dp, fn)
            if fn == "AGENTS.md":
                yield full, "agents"
            elif fn == "CLAUDE.md":
                yield full, "claude"
            elif fn == "CLAUDE.local.md":
                yield full, "claude_local"
            elif fn == "AGENTS.override.md":
                yield full, "override"
            elif in_rules and fn.endswith(".md"):
                yield full, "rule"


def load_excludes(root):
    patterns = []
    for name in (".claude/settings.json", ".claude/settings.local.json"):
        p = os.path.join(root, name)
        try:
            data = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        val = data.get("claudeMdExcludes")
        if isinstance(val, list):
            patterns += [x for x in val if isinstance(x, str)]
    return patterns


def excluded(relpath, patterns):
    base = relpath.rsplit("/", 1)[-1]
    for pat in patterns:
        if fnmatch.fnmatch(relpath, pat):
            return True
        if "/" not in pat and fnmatch.fnmatch(base, pat):
            return True
    return False


def resolve_import(p, base):
    p = os.path.expanduser(p)
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(os.path.dirname(base), p))


def tracked_set(root):
    """Git-tracked paths (repo-root-relative POSIX), or None when root is not a git repo."""
    try:
        inside = subprocess.run(
            ["git", "-C", root, "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True)
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return None
        out = subprocess.run(
            ["git", "-C", root, "ls-files"],
            capture_output=True, text=True, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return set(out.stdout.splitlines())


def chain_dirs(files_by_rel, root):
    """Directories holding a chain candidate (AGENTS.override.md/AGENTS.md/CLAUDE.md)."""
    dirs = set()
    for rel, (full, kind) in files_by_rel.items():
        if kind in ("agents", "claude", "override"):
            dirs.add(os.path.dirname(full))
    return dirs


def chain_total(directory, root, byte_cache):
    """Sum bytes of the root -> directory chain, one file per directory in candidate order."""
    total = 0
    ancestors = []
    d = directory
    while True:
        ancestors.append(d)
        if os.path.normcase(os.path.abspath(d)) == os.path.normcase(os.path.abspath(root)):
            break
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    for anc in reversed(ancestors):
        for cand in CHAIN_CANDIDATES:
            f = os.path.join(anc, cand)
            if f in byte_cache:
                total += byte_cache[f]
                break
    return total


def main():
    if len(sys.argv) != 2:
        print("usage: mechanical_check.py <repo_root>")
        sys.exit(2)
    root = os.path.abspath(sys.argv[1])
    patterns = load_excludes(root)
    tracked = tracked_set(root)
    root_bridge = os.path.join(root, "CLAUDE.md")
    root_agents = os.path.join(root, "AGENTS.md")

    files = {}   # rel -> (full, kind)
    byte_cache = {}  # full -> bytes (chain candidates only)
    big, over_bytes, imports, migrate, override = [], [], [], [], []
    tracked_local, rule_paths, broken = [], [], []

    for full, kind in discover(root):
        rel = rel_posix(full, root)
        if excluded(rel, patterns):
            continue
        files[rel] = (full, kind)
        try:
            raw = open(full, "rb").read()
        except OSError:
            continue
        nbytes = len(raw)
        if kind in ("agents", "claude", "override"):
            byte_cache[full] = nbytes
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if len(lines) > SIZE_LIMIT:
            big.append((full, len(lines)))
        if nbytes > BYTE_LIMIT:
            over_bytes.append((full, nbytes))
        if kind == "override":
            override.append(full)
        if kind == "agents":
            for ln in lines:
                for m in IMPORT_RE.finditer(ln):
                    imports.append((full, m.group(1)))
        if kind == "claude":
            if os.path.normcase(full) != os.path.normcase(root_bridge):
                migrate.append(full)
            for ln in lines:
                for m in IMPORT_RE.finditer(ln):
                    if not os.path.exists(resolve_import(m.group(1), full)):
                        broken.append((full, m.group(1)))
        if kind == "rule" and not PATHS_KEY_RE.search(text):
            rule_paths.append(full)
        if kind in ("claude_local", "override") and tracked is not None and rel in tracked:
            tracked_local.append(full)

    # [bridge]: root CLAUDE.md not exactly `@AGENTS.md`, only when a root AGENTS.md exists.
    bridge = []
    if os.path.exists(root_agents) and os.path.exists(root_bridge) \
            and rel_posix(root_bridge, root) in files:
        try:
            content = open(root_bridge, encoding="utf-8", errors="replace").read()
            if content.strip() != "@AGENTS.md":
                bridge.append(root_bridge)
        except OSError:
            pass

    # [chain > N]: every root -> directory chain.
    chains = []
    for d in chain_dirs(files, root):
        total = chain_total(d, root, byte_cache)
        if total > BYTE_LIMIT:
            chains.append((d, total))

    print("== mechanical_check: %s ==" % root)

    def section(tag, rows, fmt):
        print("\n[%s]%s" % (tag, "" if rows else " none"))
        for r in rows:
            print("  " + fmt(r))

    section("size > %d" % SIZE_LIMIT, sorted(big), lambda r: "%4d  %s" % (r[1], r[0]))
    section("bytes > %d" % BYTE_LIMIT, sorted(over_bytes), lambda r: "%6d  %s" % (r[1], r[0]))
    section("chain > %d" % BYTE_LIMIT, sorted(chains), lambda r: "%6d  %s" % (r[1], r[0]))
    section("import", imports, lambda r: "@%s  (in %s)" % (r[1], r[0]))
    section("bridge", sorted(bridge), lambda r: r)
    section("migrate", sorted(migrate), lambda r: r)
    section("override", sorted(override), lambda r: r)
    if tracked is None:
        print("\n[tracked-local] skipped (not a git repo)")
    else:
        section("tracked-local", sorted(tracked_local), lambda r: r)
    section("rule-paths", sorted(rule_paths), lambda r: r)
    section("broken-import", broken, lambda r: "@%s  (in %s)" % (r[1], r[0]))

    print("\nsummary: %d oversized, %d over-bytes, %d over-chain, %d imports, "
          "%d bridge, %d migrate, %d override, %d tracked-local, %d rule-paths, "
          "%d broken-imports" % (
              len(big), len(over_bytes), len(chains), len(imports), len(bridge),
              len(migrate), len(override), len(tracked_local), len(rule_paths),
              len(broken)))


if __name__ == "__main__":
    main()
