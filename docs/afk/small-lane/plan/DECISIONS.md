# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — which states the diagnosis check script derives
- 2026-10-20 · decided by execute (0001-diagnosis-format)
- Options: the check script derives only the states its file holds, and `/afk:fix` reads Fixed and the grill return vs the script also reading git history, tier results and a grill log
- Chosen: file-borne states only. SDD §8 gives the script one input ("path in → accept or refuse with the missing parts; state"). Fixed is read from commits and tiers, and the grill return from a size-call row whose grammar slice 0004 defines; neither is in the file.
- Supersedes: none (narrows SDD §6 "Read from" to the rows a file can answer)
- To reverse: add those inputs to `check_diagnosis.py` and its format-file state table
