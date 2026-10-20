# Adversary report: 0001-diagnosis-format

Verdict: findings, crit=0 high=0 med=2 low=7. About 150 scenarios were probed against head 9f54e99 by running the check script's command line and calling the helper's functions (D-3). The prober saw no source, tests, review files or diffs.

Held up: exit codes 0/1/2; missing parts named per verdict; unmarked facts refused; state precedence follows the State table, and an edited `--format` copy changes the result; BOM and CRLF files accepted; append idempotent and refuses bad kinds, bad markers and `\n` without touching the file; retry waits 5 s then 20 s, at most 3 writes; `read_first` works.

## Findings

| # | Severity | Class | Finding |
|---|---|---|---|
| F1 | medium | robustness | `append_outside_write` accepts an entry holding a bare `\r`; the checker then reads the part after it as a non-list line and refuses the file for good. `\x0b`, ` ` and `\x00` are also written. |
| F2 | medium | correctness | An indented first line in a fact part with no mark (`  unmarked`, or `\t- [verified] x`) is accepted. |
| F3 | low | spec | `failed({"key": ""})` is False; an empty key fails only when the caller passes `key="key"`. |
| F4 | low | spec | The Verdict part accepts `V-1`, a wrong name, and a second verdict line. |
| F5 | low | correctness | A read-back answering `{}` counts as found. |
| F6 | low | spec | `- [verified]` with no statement, and `- [verified]x`, are accepted. |
| F7 | low | spec | Part order and unknown parts are not enforced. |
| F8 | low | robustness | An `unsupported` answer is retried after a sleep. |
| F9 | low | robustness | Append writes to a file the checker already refuses (duplicate `## Outside writes`, or a non-list line in it). |

No critical or high finding, so per execute Step 10.5 these are advisory. They are noted on the pull request; F1 and F2 are the ones to fix before the feature ships.

Probe scripts: the session scratchpad `adversary-0001/p1.py`–`p8.py` (not kept).
