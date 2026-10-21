# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — which states the diagnosis check script derives
- 2026-10-20 · decided by execute (0001-diagnosis-format)
- Options: the check script derives only the states its file holds, and `/afk:fix` reads Fixed and the grill return vs the script also reading git history, tier results and a grill log
- Chosen: file-borne states only. SDD §8 gives the script one input ("path in → accept or refuse with the missing parts; state"). Fixed is read from commits and tiers, and the grill return from a size-call row whose grammar slice 0004 defines; neither is in the file.
- Supersedes: none (narrows SDD §6 "Read from" to the rows a file can answer)
- To reverse: add those inputs to `check_diagnosis.py` and its format-file state table

## D-2 — which passage D-1 supersedes
- 2026-10-20 · decided by execute (0001-diagnosis-format, review fix)
- Options: D-1 stands with `Supersedes: none` vs record the passages its narrowing overrides
- Chosen: record them. D-1 drops two §6 rows from the check script, so the contract bullet citing that table no longer holds as written; a ledger entry overrides only the passage it quotes.
- Supersedes: 0001-diagnosis-format Acceptance "The check script derives the state from the file per the §6 \"Read from\" table and nothing stores it (design ADR-0002)" and SDD §6 "Read from" rows Fixed and the grill return, for the check script only; `/afk:fix` reads both
- To reverse: as D-1

## D-3 — what the adversary gate probes for a slice with no running app
- 2026-10-20 · decided by execute (0001-diagnosis-format, Step 10.5)
- Options: skip the gate as not applicable vs probe the slice's runtime surface — the check script's command line and the helper's public functions — from the contract and the format file alone
- Chosen: probe the runtime surface. The gate is on by default and only a human may skip it; the slice's promises are observable by running the script and calling the helper, and the format file is the published contract the script reads.
- Supersedes: none
- To reverse: skip Step 10.5 for script-only slices and rerun nothing

## D-4 — how the developer-settings slice reads "the assignee", and where the bug pipeline's own stop rules stay
- 2026-10-20 · decided by execute (0002-developer-settings, Step 4)
- Options: (a) `none` reads as unset for `mrAssignee` and `mrReviewer` only vs for all three person keys, `trackerAssignee` included; (b) move the bug pipeline's per-operation stop table into `CONFIG.md` vs leave it on the bug skill's page until that skill is removed
- Chosen: (a) all three person keys — ADR-0010 names a ticket filed unassigned and a change opened unassigned, so "the assignee" covers both assignees, and a recorded `none` passed to the tracker as a user name can never resolve; (b) leave it — the table describes `/afk:bug`'s own operations, not the keys, and moving it would change that skill's behaviour outside this slice. The key definitions, the resolution order and the general missing-value rule move. The scripted ground check could not run (`seed_map` stops at its 20000-hit class cap on INV-026's declared aliases); every line INV-026 cites for this seam was re-read at the current head and still holds, and every reader of the three keys resolves through `afk-config.py resolve`.
- Supersedes: none
- To reverse: map `none` only for the two forge keys in `developer_value`; move the stop table with the keys

## D-5 — how the tracker slice's ground is re-taken when the scripted check cannot run
- 2026-10-20 · decided by execute (0003-tracker-attach, Step 4)
- Options: run a fresh /afk:investigate over the INV-024 ground vs diff the seam files INV-024 cites against its head
- Chosen: diff the cited files. The 8-root seed map stops at its 20000-hit class cap (22798, grown by this feature's own plan and investigation files), and a per-root split searches other patterns, so ground_diff reports moved for every root without measuring drift. `git diff d346cfb..HEAD` over every file INV-024 cites for this seam (tracker adapters, MCP server, ADAPTERS.md, registry check, gate, publishers, CONFORMANCE.md, .mcp.json, comment gate, the four seam tests, CI) changes only test_plugin_source_gates.py, which gained behavior-registry fixtures from main; its check-E tests shift lines but are unchanged. The ground held.
- Supersedes: none
- To reverse: run /afk:investigate Q3 on the five seam symbols at the current head and re-plan from its ledger

## D-6 — the H6 probe's test file joins the developer-settings slice's scope
- 2026-10-20 · decided by execute (0002-developer-settings, review round 1)
- Options: stop `blocked` for a re-slice vs add `scripts/tests/test_setup_h6_probe.py` to this slice's Scope
- Chosen: add it. `skills/afk/setup/MANIFEST.md` is in Scope and its H6 probe had to change with the `none` rule; that test file runs the probe block verbatim and is the only place its branches can be pinned. A re-slice would move one test file into an identical contract.
- Supersedes: 0002-developer-settings ## Scope, for this one file
- To reverse: revert the test additions in that file; the probe change stays covered only through `developer_values.py status`
