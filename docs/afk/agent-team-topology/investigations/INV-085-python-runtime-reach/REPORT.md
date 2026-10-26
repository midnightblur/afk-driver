midnightblur/afk-driver@6b322daf4e1cf9652e5deb6934a45d32b1df1de8 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-085-python-runtime-reach/COVERAGE.json

## Answer
- Entry actions: python_runtime.py `main` (:541) takes plan, install, check. install runs steps() (:316), places the entry in the `launcher` branch (:336) after the sync, probes through check() (:354), then writes the stamp (:351-352).
- /afk:setup: SKILL.md:45-47 runs register P1's probe `afk-python …/python_runtime.py check` (MANIFEST.md:684; base probe `--test` :719). On a miss it runs the P1 fix: bootstrap.sh or bootstrap.ps1 `install` (MANIFEST.md:696, :698). Each bootstrap forwards the action to python_runtime.py (bootstrap.sh:46-47, bootstrap.ps1:55).
- /afk:setup audit runs the same P1 probe (AUDIT.md:142).
- CI (continuous integration): tests.yml:38/:41 runs a real `bootstrap install --test` on Ubuntu and Windows and adds afk-bin to GITHUB_PATH (:39/:42). release.yml:41-42 and release-gate.yml:28-29 run `install`. Later afk-python steps rely on afk-bin on PATH: tests.yml:64, :67, :105; release-gate.yml:39; release.yml:50, :80. Every CI job creates the new launcher.
- Hooks, gates, SessionStart handlers and skill scripts never run `check` or read the AFK-RUNTIME stamp. Hooks and MCP (Model Context Protocol) servers reach afk-bin only by the bare `afk-python` name (hooks.json:9, hooks.codex.json:9, .mcp.json:4, .mcp.codex.json:4).
- setup_secrets.py:45 is the one non-test reader of `layout()["launcher"]`; it registers the afk-python absolute path (:248-250). It stays correct only while afk-team takes its own layout key (plan 0027:44). Unguarded.
- afk-bin reaches PATH only through install's `path` step (:261, :324-335): a startup-file export line on POSIX (:227), `uv tool update-shell` with UV_TOOL_BIN_DIR on Windows (:167). Inference: afk-team in the same folder needs no new PATH change.
- The data folder is spelled only in layout() (:129-144), bootstrap.sh:12, bootstrap.ps1:18 and CI's GITHUB_PATH lines.
- Team code does not use afk-bin yet: permission.py:28, entry.py:237, claude.sh:78, PROVIDERS.md:180 name afk-python plus scripts/afk-team.py. Plan 0027 changes them in the same slice.
## Sites that break
- scripts/tests/test_afk_python_entry.py:72 asserts every afk-bin entry starts with afk-python; red after CI's real install (tests.yml:64), both runners. Fact.
- test_python_runtime_setup.py stamped() fixture :438-443 writes afk-python only; :453 and :467 expect check to pass and go red once check reports afk-team missing. Inference.
- Documents: python_runtime.py:20-21, :266, :272; README.md:350; MANIFEST.md P1 probe :684-694 and fix :699-704; AUDIT.md:142-148 fail-kind list.
- Inference: a new step in steps() without its own branch falls to the subprocess branch (:342-343) and fails install.
## Unchanged, with conditions
- Stubs :199-204 and :543-547 replace place_entry only; stamp test :139-141 compares named keys. Green while place_team_launcher stays separate from place_entry and the stamp gains no key (plan 0027 design; inference, c-7b8b6366).
- Tests that find afk-python by folder (test_git_backstop.py:276, test_wiring_gate.py:138, test_protected_lookup.py:479, test_tracker_server.py:212, plugin-source-gates.sh:229) stay green.
- runtime/pyproject.toml:23 `package = false`: uv writes no console scripts, so python_runtime.py writes the launcher itself (inference).
- Every other site: COVERAGE.json nodes table.
## Deployment order (inference)
- A runtime installed before the change fails the P1 probe, so the next /afk:setup re-runs the install (human-asked). The rule change and the launcher write ship in one commit, or team runs refuse until setup runs again.
- A launcher names python_runtime.py's own PLUGIN_ROOT (:63), a versioned folder; a setup from another plugin copy repoints it, and check from another copy reports it stale.
## Frontier
- B14: afk-bin folders on other machines and older runtimes; PATH inheritance in Claude Code and Codex; cmd.exe locking of a running afk-team.cmd; other repositories.
## Unverified
- c-31d4f10c (not load-bearing): hit set complete over the searched name forms; the agent counter-search found 54 more sites by reading, none changing the break list.
