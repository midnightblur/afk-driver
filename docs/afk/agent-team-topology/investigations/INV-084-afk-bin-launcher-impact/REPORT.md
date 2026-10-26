midnightblur/afk-driver@b6de5e1968543666dc2d19573cecc355d9ef5b34 · closed-with-frontier · boundaries 13/14 · unverified 2 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-084-afk-bin-launcher-impact/COVERAGE.json

## Answer
- Step order: uv, python, environment (`uv sync`), launcher (`place_entry`), path (python_runtime.py:262-268, loop :316-350). place_entry runs only after the sync exits 0, so a launcher written there follows any wipe.
- A compatible environment: sync keeps it and afk-bin survives (inference: uv installer crate not read; project/mod.rs:1772-1786).
- An incompatible one (Python pin change, pyvenv.cfg conflict, broken link): sync calls `clear_virtualenv` on UV_PROJECT_ENVIRONMENT = `python/`, deleting every entry, afk-bin included, then recreates it (uv 0.12.23 project/mod.rs:1789-1808, :1878-1887; uv-fs lib.rs:964-1033). Fact.
- `check` (`sync --check --offline`) is a dry run and never touches the real root (settings.rs:2029-2033, mod.rs:1855-1874). Fact.
- No repository code runs `uv venv`, `--clear` or UV_VENV_CLEAR; uv_env strips other UV_* (:73-74, :163-165).
- Sync wipes then fails: install returns 1 before place_entry with the stamp already gone (:312, :344-349); both commands are absent until setup re-runs. Untested.
- Windows (inference): a rebuild fails while a hook or the MCP server runs afk-bin/afk-python.exe; uv guards only its own exe.
- Removal: only the MANIFEST P1 note (:727-730), delete the afk data folder, then drop afk-bin from PATH. It covers afk-team. No code deletes afk-bin.
## Sites that break
- scripts/tests/test_afk_python_entry.py:72 asserts every afk-bin entry starts with `afk-python`; CI runs it after a real install (tests.yml:37-42, :64), red on every platform.
- python_runtime.py:20-21 "holds nothing else"; :266 plan line; :272 place_entry docstring.
- python_runtime.py:500: check probes only afk-python; signed HL6-10 wants afk-team reported.
- test_python_runtime_setup.py fixtures :200-204, :442-443, :543-547 build an afk-bin with afk-python only (inference: :216, :242, :255, :450, :464, :540 go red once check probes afk-team).
- MANIFEST.md P1 Probe/Fix :684-694, :699-704 omit the launcher.
- README.md:350 "exposed only as the `afk-python` command"; FRESHNESS.md:69 does not list README.md.
- skills/afk/setup/AUDIT.md:142-149 lists check fail kinds, all afk-python (inference).
- Layout key `launcher` means afk-python (setup_secrets.py:45, stamp :352, check); afk-team needs its own key (inference).
## Unchanged
- team invocation sites (entry.py:237, scripts/afk-team.py:4, test_team_entry.py:368) never touch afk-bin; no shipped `bin/` or command competes with afk-team.
- every other site: COVERAGE.json nodes table.
## Frontier
- B14: other machines' existing afk-bin contents, uv installer-crate uninstall, cmd.exe locking of a running afk-team.cmd, other repositories.
## Unverified
- c-7ba11357 (not load-bearing): hit set complete over the name forms searched.
- c-1201e9ba (not load-bearing): whether cmd.exe holds a running .cmd open.
