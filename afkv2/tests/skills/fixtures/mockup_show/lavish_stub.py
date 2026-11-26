"""A stand-in for lavish-axi 0.1.86, as a .py file: it logs each argument list and prints the recorded output.

The launcher runs it with the lavish arguments: `[page, ...]` for open, `[op, page, ...]` for poll, reply and end. The
output of an operation is `<op>.txt` beside this file, its exit code `<op>.code` (0 when absent). As lavish does, an
operation on a page file that does not exist prints an ENOENT error and exits 1.
"""

import json
import sys
from pathlib import Path

HERE = Path(sys.argv[0]).resolve().parent
args = sys.argv[1:]
op = args[0] if args and args[0] in ("poll", "reply", "end") else "open"
with (HERE / "calls.jsonl").open("a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
page = args[1] if op != "open" and len(args) > 1 else (args[0] if args else "")
if page and not Path(page).exists():  # lavish resolves the file of every operation first
    sys.stdout.write(f'error: "ENOENT: no such file or directory, realpath {page!r}"\ncode: UNKNOWN\n')
    sys.exit(1)
output, code = HERE / f"{op}.txt", HERE / f"{op}.code"
sys.stdout.buffer.write(output.read_bytes() if output.is_file() else b"")
sys.exit(int(code.read_text("utf-8")) if code.is_file() else 0)
