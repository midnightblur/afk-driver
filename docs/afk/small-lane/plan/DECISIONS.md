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
