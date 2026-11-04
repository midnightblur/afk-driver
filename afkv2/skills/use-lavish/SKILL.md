---
name: use-lavish
description: /afkv2:use-lavish — the one home of the page round commands. Shows, waits for, reads and ends a round of a page document, and builds the round. Use when a skill shows a page round.
---

# /afkv2:use-lavish

The page skills run these commands from this folder. Write the page document by `/afkv2:visualize` ([../visualize/SKILL.md](../visualize/SKILL.md)).

## The commands

Run each command from the repository root: `<python> "<this skill's folder>/<command>"`. Every answer is one JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input.

| Command | Does |
|---------|------|
| `scripts/round_document.py build --doc D --session S --ticket K --round-input F --ticket-file T [--replace]` | writes the round into the page document |
| `scripts/page_round.py present --doc D` | checks, renders and shows the round |
| `scripts/page_round.py wait --doc D --raw-file F` | waits for the round answer and writes it to F |
| `scripts/page_round.py reply --doc D --reply-file F` | shows the Markdown in F on the page |
| `scripts/page_round.py ingest --doc D --raw-file F` | reads the answer into the page document |
| `scripts/round_document.py apply-readings --doc D --readings F` | writes the readings of the round pass |
| `scripts/page_round.py end --doc D` | ends the page session |
