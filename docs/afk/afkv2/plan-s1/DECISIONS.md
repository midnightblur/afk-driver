# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — 0001 needs a core-behaviors source and prebuilt files that 0002 owns
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — seed a short placeholder `afkv2/core/CORE-BEHAVIORS.md` and its generated `afkv2/hooks/built/*` vs B — leave both out; the plugin check fails on the tree and the hooks print nothing
- Chosen: A — the 0001 static tier needs `plugin_check.py` exit 0 on the tree and the 0001 live check needs a printed end marker; neither holds without a source and its prebuilt files. 0002 replaces the placeholder text and rebuilds the files with the 0001 build verb.
- Supersedes: none (0001 `## Scope` does not list the two paths; 0002 `## Scope` keeps them)
- To reverse: delete the two seeded paths; the plugin check then reports the missing source

## D-2 — file and shape of the `.afkv2` config
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — `.afkv2/config.json`, JSON, keys `spec_folder`, `tracker` {kind, ...}, `ownership` {own, shared} vs B — `.afkv2/config.yaml` with a hand-written YAML subset reader (v1 way)
- Chosen: A — the Python standard library reads JSON, so the reader has no parser of its own to maintain; SDD §8 fixes only "one read command, JSON answer" and the three values.
- Supersedes: none
- To reverse: change `CONFIG_FILE` and the loader in `afkv2/scripts/afkv2_config.py` and the tests

## D-3 — one hooks file for both harnesses
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — `afkv2/hooks/hooks.json` serves both: Claude runs `cmd.exe` with `args` (exec form), Codex runs `commandWindows` vs B — Claude file plus an inline hooks object in the Codex manifest
- Chosen: A — Claude docs (code.claude.com/docs/en/hooks): shell form runs through Git Bash on Windows (97 ms start, over the 50 ms rule) and exec form needs a real executable, so `cmd.exe` + `args`; Codex docs (learn.chatgpt.com/docs/hooks): `commandWindows` is the Windows command, the default file is `hooks/hooks.json`, and the inline-object shape is not documented. Codex ignoring `args` is unverified: owner-run check 1 proves it.
- Supersedes: none
- To reverse: move the Codex handlers to an inline `hooks` object in `afkv2/.codex-plugin/plugin.json`

## D-4 — how the plugin check finds a prefix or substring marker match
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — flag a code line that holds a marker token (`afkv2-…` or `afkv2:…`, and the v1 form) together with a substring or prefix operator (`startswith`, `in`, `find`, `search`, `match`, `includes`, `findstr`, …); `==` and `fullmatch` pass vs B — data-flow analysis of marker strings
- Chosen: A — a same-line rule is deterministic and cheap; the author writes a full-line compare with `==` or `fullmatch`. Data flow through a variable is not traced (known gap).
- Supersedes: none
- To reverse: change `check_marker_matching` in `afkv2/scripts/plugin_check.py`
