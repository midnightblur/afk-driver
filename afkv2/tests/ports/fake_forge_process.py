"""gh or glab as a real process: `fake_forge_process.py <rules file> <record file> <tool> <arguments>`.

It records its arguments and the bytes on stdin, and writes the raw answer bytes of the first rule that matches.
"""

from __future__ import annotations

import json
import sys


def main(rules_file, record_file, tool, *args):
    stdin = sys.stdin.buffer.read()
    with open(record_file, "a", encoding="utf-8") as record:
        record.write(json.dumps({"tool": tool, "args": list(args), "stdin": stdin.hex()}) + "\n")
    with open(rules_file, encoding="utf-8") as rules:
        for rule_tool, prefix, answer in json.load(rules):
            if rule_tool == tool and args[:len(prefix)] == tuple(prefix):
                sys.stdout.buffer.write(bytes.fromhex(answer))
                return 0
    sys.stderr.write(f"no fake answer for {tool} {' '.join(args)[:200]}")
    return 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
