"""Recorded fake of mermaid-cli: `fake_mmdc.py -i IN -o OUT -b white` writes a small PNG from the source text.

Environment: FAKE_MMDC_FAIL makes it exit 1. FAKE_MMDC_LOG gets one line per render. FAKE_MMDC_VARY puts a
fresh value in each file, as a real renderer may.
"""

import hashlib
import os
import struct
import sys
import uuid


def main(argv):
    with open(argv[argv.index("-i") + 1], "rb") as source_file:
        source = source_file.read()
    if os.environ.get("FAKE_MMDC_FAIL"):
        print("the fake renderer refused", file=sys.stderr)
        return 1
    if os.environ.get("FAKE_MMDC_LOG"):
        with open(os.environ["FAKE_MMDC_LOG"], "a", encoding="utf-8") as out:
            out.write("render\n")
    tail = uuid.uuid4().bytes if os.environ.get("FAKE_MMDC_VARY") else b""
    with open(argv[argv.index("-o") + 1], "wb") as out:
        out.write(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 640, 480)
                  + hashlib.sha256(source).digest() + tail)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
