C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · closed-with-frontier · boundaries 13/14 · unverified 5 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-012-manifest-gate-reachers/COVERAGE.json

## Answer

Two hook paths reach gate_native_contract, and only its two dispatchers read its result. Stop: hooks/hooks.json:59 (twin hooks.codex.json:59) → hooks/run-hook.py:315 → hooks/stop-gates.sh:130, only when the plugin scope, .agents/ or .codex/ changed (:119-121); run_gate builds the file and function names from the key native-contract (:85, :89) and calls at :94. Commit: SessionStart hooks.json:9 → install-git-hooks.sh installs a pre-commit stub (:96, :103), only in a repository carrying .afk/ (:48-51) → hooks/precommit-gates.sh:154, pass cache disabled (:153); names built at :94, :105, call at :109. /afk:setup register H5 (skills/afk/setup/MANIFEST.md:77) is a second install path. manifest_skills has one caller: the check C loop at hooks/native-contract-gate.sh:188-190 over both plugin.json files; its findings leave only through the gate's exit 2 (:349, :361). No test, no CI job and no tracked script runs the gate: unguarded.

## Sites

- Result readers: stop-gates.sh:97 → blocked Stop (:147, :150), pass → all-green stamp (:163) that short-circuits later Stops (:57-60); precommit-gates.sh:113 → blocked commit (:166). Any other non-zero exit is reported as crashed, never blocks (stop-gates.sh:95-100, precommit-gates.sh:111-115).
- Side outputs: cache entry read only by the gate itself (gate-cache.sh:78 via native-contract-gate.sh:41); metrics lines read by hooks/gate-metrics-report.sh:14, a manual script, and through it by /afk:retro (skills/afk/retro/SKILL.md:32).
- Switches that stop it: NATIVE_CONTRACT_GATE_DISABLE=1 (native-contract-gate.sh:31); .claude/hooks/.gate-disabled (:32, stop-gates.sh:36); commit path only: AFK_SKIP_PRECOMMIT_GATES=1 or a non-agent session (precommit-gates.sh:37, :42).
- Manual entry (native-contract-gate.sh:370-382), instructed by README.md:325, providers/CONFORMANCE.md:303, skills/afk/setup/AUDIT.md:70, skills/afk/claude-md/SKILL.md:46, skills/utils/writing-for-agents/SKILL.md:15.
- No reach: .github/workflows/release-gate.yml:36 runs hooks/release-gate.sh only; .afk/hooks.json:1 is empty; hooks/tests and scripts/tests name none of the gate's forms (c-61605d25, c-1d07cb6a).
- Overlap, no dependence: skill-registry-gate.sh check A (:6, :56) re-checks Claude-manifest membership; AUDIT.md:13 re-checks both skills arrays by hand.
- Documents that agree with the code: dispatch — AGENTS.md:201, CLAUDE.md:201, CHANGELOG.md:1255, hooks/README.md:7, :8, :63, :90, skills/afk/setup/MANIFEST.md:219, providers/CONFORMANCE.md:23, GRILL-LOG.md:261, INV-004-twin-manifest-gate/REPORT.md:5; check C — CLAUDE.md:15, FRESHNESS.md:63, hooks/README.md:63, :104, CHANGELOG.md:1255, CONFORMANCE.md:23, GRILL-LOG.md:222, :239, :261, INV-004 REPORT.md:5.
- Documents refuted: providers/PARITY.md:103 (the hooks.codex.json twin diff lives in hooks/tests/hook-smoke.sh:243, not the gate); AGENTS.md:15 names `.Codex-plugin/` for `.claude-plugin/` (gate reads .claude-plugin/plugin.json at :188; AGENTS.md is untracked); INV-006-stage-skills/REPORT.md:5 (check A scans every *.md, SKILL.md bodies included, :79-135); MANIFEST.md:685 lists the gate as a CLAUDECODE reader, but :115 is only a prose regex.
- Incomplete, not wrong: hooks/README.md:63 lists checks A-H; the gate header adds I and J (:6-23). MANIFEST.md:219 "fire every turn" holds for the Stop hook, not this gate, which is scope-gated (stop-gates.sh:119-130; inferred intended meaning).
- Stale comment (inferred): hooks/gate-context.sh:133-135 says the gate calls gate_ctx_mergebase; it does not; only its Stop scope test uses the merge-base (:156-159, stop-gates.sh:115).
- Records only: 921 hits in investigations/*/COVERAGE.json and 4 in grill-solution.round.json invoke nothing; check A globs *.md (:80).

## Frontier

- B14: other repositories, deployment manifests, live consumers — outside this repository.

## Unverified

None load-bearing.

- c-e259ed8f: the hit set is complete over the name forms searched.
- c-e4fcf1aa: which plugin root the installed pre-commit stub runs is machine state in the main checkout's .git/hooks, not repository state.
- c-2f8bd546: the negative probe at providers/PARITY.md:112 (six findings) was not re-run; the gate now carries ten checks.
- c-7ec33061: INV-007-setup-offer/REPORT.md:38 ("no test pins check C") not re-checked in the documents partition; c-61605d25 and c-1d07cb6a ground the same fact.
- c-86ee7c92: seed node grill-solution.html:388 no longer matches its hash after a re-render; the current hit :396 copies grill-solution.round.json:2506.

## Run notes

- Inferred (c-29058c42): the Claude harness loads hooks/hooks.json from its default location; .claude-plugin/plugin.json declares no hooks key, .codex-plugin/plugin.json:53 names hooks.codex.json.
