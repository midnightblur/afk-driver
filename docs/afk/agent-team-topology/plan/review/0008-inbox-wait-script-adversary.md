# Adversary report: 0008-inbox-wait-script

Target: hooks/inbox-wait.sh run from a scratch folder. Diet kept: no source, tests or history read.

ADVERSARY: clean — probed=26
In plain terms: the wait script behaved as the contract promises in every run, so it can ship; the harness-wake probes in the contract stay environment-gated and were not run here.

## Findings
None.

## Observed (runtime)
- Bad calls (0, 3 args, missing folder, malformed/empty/date-only/offset/no-Z park-until): usage line, exit 2, no hang.
- File already present: exit 0 at once (first look before first wait). With a past park-until too: file wins, exit 0.
- Past park-until, empty inbox: exit 3 at once. Park +12s: exit 3 at 12s (end time honoured to the second).
- Nothing parked, no file: runs until stopped (killed at 25s by timeout; SIGTERM ends it at once, no orphan sleep).
- File lands mid-wait (4s): exit 0 at 11s, within the 10-second wake bound. A temp-named file is skipped until renamed, then found within 8s.
- Folder removed mid-wait: exit 2 after 10s. Path with spaces works. Several files: exit 0, files left untouched.

## Notes (not findings)
- Dot-files and subfolders are ignored as non-messages; the contract says "a file", so a dot-named message would be missed (low, hypothesis only: the real writer's naming not read here).
- Not probed (gated, outside this gate): per-harness wake and session-end probes (V25, Q4).
