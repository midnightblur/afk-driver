#!/usr/bin/env python3
"""Replace one sentinel-delimited block in a steering file with the source's.

    install_block.py <source.md> <target.md> [sentinel]

The block is `<!-- afk:<sentinel>:start -->` to `<!-- afk:<sentinel>:end -->`,
default sentinel `plain-language`. Only those lines change: the file's own line
endings and everything outside the sentinels are preserved byte for byte, so a
refresh never rewrites what the human wrote around the block.

Exit 0 replaced or already identical, 1 the target has no block (the caller
appends instead), 2 the source has none.
"""
import pathlib
import re
import sys

src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
name = sys.argv[3] if len(sys.argv) > 3 else "plain-language"
pattern = re.compile(
    ("<!-- afk:%s:start -->.*?<!-- afk:%s:end -->" % (name, name)).encode(), re.S)

block = pattern.search(src.read_bytes())
if not block:
    sys.exit("install_block: %s carries no %s block" % (src, name))

target = dst.read_bytes()
if not pattern.search(target):
    sys.exit(1)

# The target decides the line endings: a CRLF file stays CRLF.
text = block.group(0).replace(b"\r\n", b"\n")
if b"\r\n" in target:
    text = text.replace(b"\n", b"\r\n")

updated = pattern.sub(lambda _: text, target, count=1)
if updated != target:
    dst.write_bytes(updated)
    print("refreshed %s block in %s" % (name, dst))
else:
    print("%s block in %s is already current" % (name, dst))
