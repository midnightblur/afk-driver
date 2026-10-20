midnightblur/afk-driver@80b6f50c4d6c8acc977ae3bfd35ce04fb8b76526 · closed-with-frontier · boundaries 13/14 · unverified 2 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-079-wait-script-ground/COVERAGE.json

## Answer

The stall watchdog waits with a sleep loop: it sleeps `--poll-sec`, then looks for a file newer than the last activity. It wakes the orchestrator only by exiting: 3 when stale, 4 at the cap, 2 on a usage error, never 0 (hooks/stall-watchdog.sh:31-65). A non-numeric limit ends it with exit 1, and a trailing `--path` never ends (:35, :53). It is armed from DELEGATION.md:34-39, skills/afk/autopilot/SKILL.md:40 and skills/utils/investigate/SKILL.md:44. No arm site names the harness tool parameter. Preflight PF-6 runs `forge ci-wait` as a background task, using the same kind of sleep loop (skills/afk/preflight/SKILL.md:192-210). The bug fixer prompt runs ci-wait in the foreground (skills/afk/bug/FIXER-PROMPT.md:32). LAVISH.md:123 runs each blocking poll as a tracked background job.

No CAPABILITIES.md row covers a harness waking on a background job's exit. No conformance probe asserts it, and providers/PARITY.md:117 says no timing probe was run.

Adding hooks/inbox-wait.sh, its rows and its smoke case breaks nothing, under these conditions:
- The script reads no upper-case environment variable (registry check C, hooks/skill-registry-gate.sh:138-185). Bash's own variables are exempt.
- It is LF (rule I) and names no bare python (rule J). It is outside rule M.
- The hooks/README.md row and the AGENTS.md entry name no harness and carry no ticket-shaped id (rule A, hooks/native-contract-gate.sh:90-152; genericity gate). The changelog is exempt from the ticket check (hooks/genericity-gate.sh:256-258).
- No *.md line cites an `/afk:execute` step that does not exist (scripts/tests/test_execute_step_pointers.py:44-51).

A new CAPABILITIES.md row leaves rule E, the twin test and the behavior registry unchanged. The wiring gate derives the token `inbox-wait` (hooks/wiring-gate.sh:176-178), which plan files already name. The park-until argument takes the manifest's form `YYYY-MM-DDTHH:MM:SSZ` (scripts/team/manifest.py:42, :48). The run-start notice that reads the new row is plan/0015's AC-065 bullet. 0015's Consumes names no anchor from this slice. Later callers of the script are plan/0010, 0014 and 0015. No deployment order applies.

## Corrections folded in

The counter-search corrected claims c-8d2f262e, c-339431c6, c-23b20a3a, c-d2060ab5 and c-533c3cc6. The corrections are claims c-2e5751b0, c-487624e5, c-2b396f5f, c-9654c612 and c-81979461; where a pair disagrees, the correction wins.

## Frontier

- B14: whether a background job's exit wakes an idle agent depends on the harness version, and that behaviour lives outside this repository (claim c-95c55d61).

## Unverified

- c-0e786d52, inference: on one harness, a running wait job may block the worktree move, which counts "background terminal" as a refusal (hooks/lib/providers/codex.json:18). No conformance row covers this.
- providers/PARITY.md stays one script short. Nothing reads it, and the claim is not load-bearing.
