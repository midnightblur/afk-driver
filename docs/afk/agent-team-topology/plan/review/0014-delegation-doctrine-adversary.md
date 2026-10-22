# Adversary report — 0014-delegation-doctrine

- Date: 2026-10-22 · Mode: driven · Target: `cli:C:/Users/mvu/PersonalProjects/afk-driver-agent-teams` (plan D-40: the plugin command line is the running system)
- Scratch copies of HEAD (`git archive HEAD`): `…/scratchpad/0014/adversary/repo` (git-initialised for the gates) and `…/scratchpad/0014/adversary/p4` (plain). The repository was not run or changed.
- Verdict: `findings` — 34 scenarios probed, 1 low finding, 0 critical, high or medium.

## Findings

### F1 — low · spec — the helper type list reads as what a pane start names

- Promise: Acceptance "The type and tier lines DELEGATION.md:26 and :43 narrow to helpers and the subagent fallback: a pane start names a role and a brief path only", and Acceptance "DELEGATION.md:26's list of named types and what each does … stay unchanged (only its scope narrows)".
- Repro: `sed -n '27p' DELEGATION.md` prints: "**Named types first** for helpers and the subagent fallback; a pane start names a role and a brief path only: `afk-reader` (read-only digester …), `afk-runner` (…), …".
- Actual: the inserted clause sits between "Named types first" and the colon that opens the type list. The colon now follows "a role and a brief path only", so the list of agent types reads as what a pane start names.
- Expected: the type list attaches to helpers and the subagent fallback only, because a pane role loads no agent definition (`CAPABILITIES.md:12`, `PROVIDERS.md:23`). Example fix: put the pane-start clause after the list, or in its own sentence.
- Effect: an agent that reads line 27 can pass an agent type name such as `afk-implementor` as the pane role. This conflicts with `PROVIDERS.md:23` ("a pane role agent loads no definition").

## Scenarios that held

| # | Promise (Acceptance or Seam) | Class | Probe | Result |
|---|---|---|---|---|
| 1 | BEHAVIORS.md entry + inventory row + id agree | happy | `behavior_registry.py validate --registry BEHAVIORS.md --plugin-root . --dispositions hooks/behavior-dispositions.tsv --parity-root . --verbose` | exit 0, "valid: 18 rows; revision=3; bytes=4018" |
| 2 | Rendered block ≤ 6,000 bytes | boundary | `render --plugin-root . --output block.md`; `wc -c` | 4018 bytes with a 150-character root path (10 root expansions; headroom to a ~348-character root) |
| 3 | Scope all-repos | happy | read rendered block | short form sits under `## All repositories`, not `## Configured repositories` |
| 4 | Inventory row required | invalid | validate with the `pane-agent-rule` row removed from the dispositions file | exit 1, "inventory set mismatch; missing=pane-agent-rule" |
| 5 | Doctrine heading required | invalid | render against a root whose DELEGATION.md heading is renamed | exit 1, "doctrine section does not exist in DELEGATION.md: Spawn rules"; no output file |
| 6 | Byte cap refuses, never truncates | boundary | `render --byte-limit 4000` | exit 1, "rendered block is 4018 bytes; limit is 4000 bytes"; no output file |
| 7 | Byte cap at exact size | boundary | `render --byte-limit 4018` | exit 0, 4018 bytes |
| 8 | Another installed root still has the heading | cross-effect | `validate --plugin-root <AFK_PLUGIN_ROOT>` | exit 0 (`## Spawn rules` at its DELEGATION.md:22) |
| 9 | Installed blocks report drift | state | `audit --target` on a block rendered from the registry without the entry | exit 1, "stale behaviors block" |
| 10 | Fresh block is clean | state | `audit --target` on the new block | exit 0 |
| 11 | Drift shows at session start | cross-effect | `AFK_PROVIDER=claude HOME=<scratch> bash hooks/behavior-drift.sh` with the old block | prints "[afk] Managed behavior is stale; run /afk:setup." |
| 12 | No drift message for a current block | state | same hook, new block | silent, exit 0 |
| 13 | No SessionStart handler prints the short form | cross-effect | list SessionStart commands of `hooks/hooks.json` and `hooks/hooks.codex.json`; grep `hooks/*.sh|*.py|*.json` for the short-form text | 8 handlers each, none pane-related; grep exit 1 |
| 14 | Short form names no harness | invalid | validate a registry copy with "Claude Code" in the short form | exit 1, "body contains provider-specific text: Claude" |
| 15 | Short form names no harness | happy | grep short form for claude, codex, herdr, tmux, mcp, wezterm, zellij | 0 matches |
| 16 | No harness word in spawn, watchdog and model text | invalid | grep DELEGATION.md:22-55 for the contract's banned list plus `herdr` | 0 matches |
| 17 | Watchdog unchanged: stale exit | state | `stall-watchdog.sh --path <idle> --stale-min 1 --poll-sec 5` | exit 3 after 1 min, "STALL-WATCHDOG: stale …" |
| 18 | Watchdog unchanged: cap exit | state | `--path <touched every 5 s> --cap-min 1` | exit 4, "STALL-WATCHDOG: cap …" |
| 19 | A kill disarms (park = kill) | state | start in background, kill after 3 s | no output, process gone |
| 20 | Watchdog usage error | invalid | no `--path` | exit 2 |
| 21 | Wait job: message wakes | happy | `inbox-wait.sh <inbox with msg-1.md> 2026-12-01T00:00:00Z` | exit 0, "INBOX-WAIT: message" |
| 22 | Wait job: park-until passes | boundary | past park-until, empty inbox | exit 3 |
| 23 | Wait job: impossible date | invalid | `2026-02-30T00:00:00Z` | exit 2, usage line |
| 24 | Wait job: ignored files | boundary | only `.hidden` and `x.tmp` present | exit 3 (not woken) |
| 25 | Wait job: missing inbox | invalid | `inbox-wait.sh nowhere` | exit 2 |
| 26 | Consumed anchor `park_until_utc` | happy | `grep -n park_until_utc hooks/inbox-wait.sh` | present; exercised by 22-23 |
| 27 | Wait job is a manifest process entry | cross-effect | read `scripts/team/manifest.py` writers | `record_entry` keys a process entry by `pid`; `remove_process` drops it |
| 28 | Pane switch key exists | cross-effect | `AFK_CONFIG=<file> afk-config.py get transport.pane-switch` for `subagent`, `pane`; `validate` for `panes` | reads back both; `panes` refused, exit 2 |
| 29 | Setup re-render clears drift | cross-effect | `install_block.py install block.md <stale target>`, then `audit` | exit 0 both; user text above the block kept |
| 30 | Gates pass on the committed tree | happy | `hooks/native-contract-gate.sh` (checks A-M, incl. L), `skill-registry-gate.sh`, `behavior-registry-gate.sh` in the git scratch copy | exit 0 each |
| 31 | Produces anchors once | happy | `grep -c 'pane-agent rule' DELEGATION.md`; `grep -c 'doctrine: DELEGATION.md §Spawn rules' BEHAVIORS.md`; `grep -c 'suite/build runners' DELEGATION.md` | 1, 1, 1 |
| 32 | Rule stated once (AC-047) | state | grep all non-docs `*.md` for the rule's wording | DELEGATION.md:24 (full rule) and BEHAVIORS.md:16 (short form) only |
| 33 | CHANGELOG line | happy | read CHANGELOG.md:70-77 | names `pane-agent-rule`, all repositories, setup row H7, drift until re-render |
| 34 | Doctrine lines updated | happy | read DELEGATION.md:24-54, CAPABILITIES.md:3/:12/:15, PROVIDERS.md:23/:159/:164, AGENTS.md:22, autopilot SKILL.md:40 | carve-out, contact-agent watchdog, runner arm, park and resume, wait job, agent-start exception present; F1 aside, no contradiction found |

## Not probed

- unverified: seam-test of §9b row "Named agent definitions and pinned models in a pane agent" (`providers/CONFORMANCE.md:436`, `:437`). It needs live pane agents on both harnesses; this run may start no agent or pane.
- unverified: PRD AC-001 (a whole run behaves as before with no pane transport). It needs a full run.
- `scripts/tests/test_model_tier_gate.py`: 3 failures in the plain copy, cause "git ls-files failed" (no git there). The same check L passed through `native-contract-gate.sh` in the git copy (row 30).

## Observations (not findings)

- DELEGATION.md:38 points at `/afk:team`, absent on HEAD (`skills/afk/team` missing). Tracked: `.claude/wiring-ious.md:36`, closes with 0015-team-skill-and-manifests.
- DELEGATION.md:24 and :38 name "the team entry script's start verb" and "the file the team entry script writes". No such script is on HEAD (`scripts/team/` holds `knowledge`, `manifest`, `permission`, `probe`, `resolver`); planned in 0010-team-entry-script. No `.claude/wiring-ious.md` line names these 2 pointers.
- DELEGATION.md:24 says "A start request past the nesting cap below is refused", and :30 says "a chain of start requests adds no level, because the contact agent starts every pane agent". Both match their sources (PRD AC-043, SDD §14). Together they give the contact agent no depth at which a start request is past the cap.
- `afk-config.py get transport.pane-switch` returns `panes` without refusal; only `validate` refuses it. That is the configuration reader's contract, outside this slice's Scope.

## Information diet

No slice diff, branch commit, review finding or test source of this slice was read. Grep output lines from `scripts/tests/test_afk_config.py` and `scripts/tests/test_team_probe.py` (other subtasks' tests, outside this Scope) and one assertion message of `scripts/tests/test_model_tier_gate.py` entered context. None describes this slice's implementation. The verdict is not tainted.
