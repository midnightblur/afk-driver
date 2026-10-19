C:\Users\mvu\PersonalProjects\afk-driver\.claude\worktrees\setup-per-repo@17ec3223985388dab50ffdc5d04b1b1f27dc99ce · closed-with-frontier · boundaries 13/14 · unverified 2 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-004-config-without-commit/COVERAGE.json

## Answer

The shared overlay may set every key except `schema`, and the config reader merges it like any layer. Commit gates, setup checks, `init` and managed behaviors still test for the committed file and skip or fail without it. An unreadable `.git` file or `commondir` crashes the reader and the tracker server, with or without a committed file.

## Sites

- `scripts/afk-config.py:53-59,394-395` — overlay refuses only `schema`; `:575` validate sees the merged result; `:133` `schema` defaults to 1. Overlay `schema`: `get`, `effective`, `export-shell`, `validate` exit 2; `validate <overlay file>` exits 0 (probe).
- `scripts/afk-config.py:342-385` — layer order home < committed < shared < local < `AFK_CONFIG`; tests `scripts/tests/test_afk_config.py:179-195,208`. Linked worktrees read the same overlay (probe).
- `scripts/afk-config.py:351,356` — unreadable `.git` file or `commondir`: uncaught PermissionError, exit 1 (probe). `mcp-servers/tracker/server.py:80-83` misses it; server start-up exits 1. A `commondir` that is a directory misses the overlay with no message.
- Layer-blind readers: `hooks/lib/config.sh:29`, `hooks/lib/adapter.sh:29-51`, `mcp-servers/tracker/server.py:62,69`, `scripts/tracker_api.py:32-33`, `scripts/protected-lookup.py:109-116`, `skills/afk/setup/scripts/setup_secrets.py:51`.
- Sites that locate the overlay themselves and include it: `hooks/precommit-gates.sh:190-191` (untested), `scripts/protected-lookup.py:66-67,207`, `skills/afk/setup/scripts/developer_values.py:53`, `skills/afk/setup/MANIFEST.md:141`.
- `mcp-servers/tracker/server.py:69` overlay read is unguarded: `scripts/tests/test_tracker_server.py:73` passes when `:69` reads only the committed file (mutation).
- H6 probe reads the merged config: `skills/afk/setup/MANIFEST.md:139-163` (test `scripts/tests/test_setup_h6_probe.py:149-150`).
- Need the committed file:
  - `hooks/precommit-gates.sh:59` — no `.afk/` directory skips comment gate, build gates, PreCommit handlers (probe); pinned by `scripts/tests/test_git_backstop.py:227`.
  - `scripts/behavior_registry.py:227,871` (test `scripts/tests/test_behavior_registry.py:64`), `GLOSSARY.md:87`, `adr/0005-managed-behavior-transport.md:21` — configured-repos behaviors.
  - `skills/afk/setup/MANIFEST.md:42,51` — H0 `test -f`; `:72` H2 reports `needs-human: see H0` under overlay `tracker: none`; `:185` H6 Fix skips.
  - `skills/afk/setup/SKILL.md:50-54,68` — step 0 runs `init`.
  - `scripts/afk-config.py:1129-1168` — `init` ignores the overlay; `:939,985,993` scaffold inherits only from the machine file; `:1278` `validate FILE` ignores the overlay, and no caller passes a FILE.
  - `skills/afk/setup/scripts/developer_values.py:177` — `configured` means committed file exists.
  - `skills/utils/investigate/scripts/seed_map.py:286,1228` — stamps `defaults` while applying the overlay.
  - Messages naming the committed file: `setup_secrets.py:157-160`, `scripts/tracker_api.py:42,49`, `hooks/lib/adapter.sh:41,47,128`, `adapters/notes/notion/NOTES.md:12`, `mcp-servers/tracker/server.py:162`.
- No CI workflow, manifest or HTML page needs the committed file (B7, B10).
- Docs the reader refutes: `CONFIG.md:3-5`, `README.md:314,323`.

## Frontier

- B14 — other repositories and live consumers, not checked.

## Unverified

- Whether agents skip configured-repos behaviors or follow file-naming messages literally — model behavior, outside this repository (load-bearing inference).
- Claim "unreadable `.git` raises OSError" stays `unverified`: the fold keeps the worse kind; a fact claim with its own text settles it.
- Seed claim "the hit set holds every reference" — no method; not load-bearing.
- Two refuted inferences stay in the ledger: "no test pins the `.afk` guard", "no test sets tracker or forge in the overlay alone".
