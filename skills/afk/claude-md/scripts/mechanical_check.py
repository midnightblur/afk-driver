#!/usr/bin/env python3
"""Deterministic CLAUDE.md mechanical checks. Usage: python mechanical_check.py <repo_root>
Reports: files >200 lines, broken @import paths. Scoped to <repo_root>; never scans system roots."""
import os, re, sys

SIZE_LIMIT = 200
MEMORY_NAMES = ("CLAUDE.md", "CLAUDE.local.md")
SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", "out", "vendor", ".idea", ".gradle"}
IMPORT_RE = re.compile(r"(?:^|\s)@([~./][^\s]+\.md)")


def find_memory_files(root):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if fn in MEMORY_NAMES or (fn.endswith(".md") and os.path.basename(dp) == "rules"):
                yield os.path.join(dp, fn)


def resolve_import(p, base):
    p = os.path.expanduser(p)
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(os.path.dirname(base), p))


def main():
    if len(sys.argv) != 2:
        print("usage: mechanical_check.py <repo_root>"); sys.exit(2)
    root = os.path.abspath(sys.argv[1])
    big, broken = [], []
    for f in find_memory_files(root):
        try:
            lines = open(f, encoding="utf-8").read().splitlines()
        except OSError:
            continue
        if len(lines) > SIZE_LIMIT:
            big.append((f, len(lines)))
        for ln in lines:
            for m in IMPORT_RE.finditer(ln):
                tgt = resolve_import(m.group(1), f)
                if not os.path.exists(tgt):
                    broken.append((f, m.group(1)))
    print(f"== mechanical_check: {root} ==")
    print(f"\n[size > {SIZE_LIMIT}]" + ("" if big else " none"))
    for f, n in big:
        print(f"  {n:>4}  {f}")
    print(f"\n[broken @import]" + ("" if broken else " none"))
    for f, imp in broken:
        print(f"  {imp}  (in {f})")
    print(f"\nsummary: {len(big)} oversized, {len(broken)} broken imports")


if __name__ == "__main__":
    main()
