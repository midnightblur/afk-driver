#!/usr/bin/env python3
"""The dedup key of one plugin defect.

    fingerprint.py --kind bug|feedback --file <plugin-relative path> --signature <text>

Prints 12 hex characters: sha256 over the kind, the owning plugin file, and the
error signature normalized so two runs of the same defect agree — case, paths,
quoted values, hex ids, and numbers do not move it. Exit 2 on a usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys

KINDS = ("bug", "feedback")


def normalize_file(path: str) -> str:
    text = path.strip().replace("\\", "/")
    text = re.sub(r"^(?:\$\{?AFK_PLUGIN_ROOT\}?/|\./)", "", text)
    return re.sub(r"/{2,}", "/", text).strip("/")


def normalize_signature(signature: str) -> str:
    text = signature.strip().lower()
    text = re.sub(r"<[a-z-]+>", "<x>", text)
    text = re.sub(r"\"[^\"]*\"|'[^']*'|`[^`]*`", "<s>", text)
    text = re.sub(r"(?:\b[a-z]:)?[\w.~$-]*[/\\][\w./\\${}~-]*", "<p>", text)
    text = re.sub(r"\b[0-9a-f]{7,}\b", "<h>", text)
    text = re.sub(r"\d+", "0", text)
    return re.sub(r"\s+", " ", text).strip()


def fingerprint(kind: str, path: str, signature: str) -> str:
    material = "\n".join((kind, normalize_file(path), normalize_signature(signature)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="fingerprint.py")
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--file", required=True)
    parser.add_argument("--signature", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    if not normalize_file(args.file) or not normalize_signature(args.signature):
        sys.stderr.write("fingerprint: --file and --signature must be non-empty\n")
        return 2
    print(fingerprint(args.kind, args.file, args.signature))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
