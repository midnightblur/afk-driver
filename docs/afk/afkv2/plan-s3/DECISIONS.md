# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — ground diff exit 1 for the INV-004 seams
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — re-run /afk:investigate for both seams vs B — accept the ground as held
- Chosen: B — `git diff 8e6ef1cfd1bd..HEAD` outside `docs/afk/afkv2/` is empty, so no v1 line moved; the reported drift comes from per-subject seeding against a ledger that ran 3 roots together, plus new spec files
- Supersedes: none
- To reverse: run /afk:investigate for the two §14 seams and compare its claims with setup.py

## D-2 — what the hook proof covers before the v1 block goes
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — proof of the current session's provider only vs B — a fired record for every provider that still uses v1, plus the current session's end marker
- Chosen: B — SDD §14 removes the block from both files in one run, and requirement ADR-0004 forbids a session with no rules; an untrusted Codex hook writes no fired record, so B catches it
- Supersedes: none
- To reverse: shrink `required_providers` in setup.py to the current provider

## D-3 — file names in the afkv2 data folder
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — wait for S1 to name the fired record vs B — use `hook-fired-<provider>.txt` and compare its modification time with the install record
- Chosen: B — SDD §4 fixes only "one file per provider, plain text"; the name is one constant in `places.py`, and S4 0016 runs the proof against the real hook
- Supersedes: none
- To reverse: change `Places.fired_record` to the name S1's hook writes

## D-4 — where the expected sha12 comes from
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — recompute SHA-256 over the text between the markers vs B — read the sha12 from the full begin and end lines of the prebuilt files in the plugin tree
- Chosen: B — S1's build check owns the hash and refuses a stale file (SDD §8 "marker hash"); a second hash implementation can disagree on line ends
- Supersedes: none
- To reverse: add a recompute in `expected_sha12s`

## D-5 — where setup stores the Jira values
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — always the environment vs B — the v1 tracker entry in `~/.claude.json` when it exists, else the user environment
- Chosen: B — SDD §5 Secrets: "looked up as v1 does (environment, then the Claude user config's tracker entry, then the Codex config)"; B keeps v1's place when v1 set it up and uses the first lookup source otherwise; afkv2 has no server entry of its own to write
- Supersedes: none
- To reverse: change `store_jira_values` in `jira_values.py`

## D-6 — the `.afkv2` config file setup writes
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — wait for S1's reader format vs B — `.afkv2/config.yaml`, v1's YAML subset, v1 top-level key names for copied blocks, a new `ownership:` block with `own` and `shared` lists
- Chosen: B — the reader (S1 0001) and the copy must agree on one file; v1's names keep the copy a verbatim block move; S4 0016 runs setup against the real reader
- Supersedes: none
- To reverse: change `AFKV2_CONFIG`, `COPIED_KEYS` and `write_ownership` in `repo_config.py`

## D-7 — Codex plugin switch is a config edit
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — a Codex command-line enable/disable vs B — edit `[plugins."<id>"] enabled` in the global `config.toml` with a backup
- Chosen: B — `codex plugin --help` (codex-cli 0.164.0) lists only add, list, marketplace and remove; this answers SDD §13 "Does Codex have a command-line plugin enable/disable?" with no
- Supersedes: none
- To reverse: call the command in `_switch_codex` when Codex adds one

## D-8 — both plugins enabled before the proof
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — turn afkv2 off when the proof fails vs B — leave both on until the proof passes, report it, refuse to finish the takeover with both on
- Chosen: B — the afkv2 hook can fire only while afkv2 is on, so A makes the proof impossible; AC-017's refusal applies to the switch step's read-back
- Supersedes: none
- To reverse: turn afkv2 off in the proof-failed branch of `takeover`

## D-9 — switch-back leaves one plugin on
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — restore every backup byte-identical and stop vs B — restore every backup byte-identical, then turn afkv2 off where the restored state still turns both on
- Chosen: B — the state before setup has both plugins on (D-8), so A leaves two rule sets per session (AC-017, requirement ADR-0004); the integration test checks byte-identity for every file and allows only the afkv2 enable value to differ
- Supersedes: 0011 contract `## Verification` integration row "switch-back → every file byte-identical to before" (the afkv2 enable value is the one difference)
- To reverse: drop `_leave_v1_only` from `switch_back`

## D-10 — switch-back keeps the exclude line and the local settings file
- 2026-10-30 · decided by execute (0011-setup-skill)
- Options: A — also remove the `info/exclude` line and delete the local settings file at switch-back vs B — keep both, with values that leave only v1 on
- Chosen: B — exclude is repository state git needs while `.claude/settings.local.json` exists, and the file must hold `afkv2: false` to keep AC-017 where the restored state turns both plugins on; D-9's "only the afkv2 enable value differs" holds for every file the developer had, and these two are the switch's own carrier
- Supersedes: D-9 phrase "allows only the afkv2 enable value to differ" (adds the exclude line and the local settings file that carry the value)
- To reverse: drop `_ensure_local_ignored` from the switch-back path of `_switch_claude`
