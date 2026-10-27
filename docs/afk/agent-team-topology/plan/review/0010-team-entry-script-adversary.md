# Adversary report — 0010-team-entry-script

Contract: `plan/0010-team-entry-script.md` at head 684aa31. Mode: driven. Verdict: `findings`.

## Set-up

- The running system is the command line in the worktree: `afk-python scripts/afk-team.py <verb> '<json>'`. No source under `scripts/` or `hooks/` was read.
- Every run lived under `AFK_TEAM_ROOT` = `<scratch>/0010/adv/runs`. `<scratch>` is `C:/Users/mvu/AppData/Local/Temp/claude/C--Users-mvu-PersonalProjects-afk-driver-agent-teams/96c58aef-58cc-4e51-8bc9-2259fed7dd71/scratchpad`.
- No real herdr, Claude Code or Codex ran. `HERDR_*` and `CLAUDE*` variables were unset, and the real herdr folder was removed from `PATH`. A herdr emulator (`<scratch>/0010/adv/fakebin/fakeherdr.py`, with `herdr` and `herdr.cmd` shims) answered the herdr commands. It logged each call, and it started a throwaway Python sleep process for `agent start` and `pane run`. Fake `claude` and `codex` shims logged their argument list, environment and folder.
- The manifest entries that the contact agent writes were written by hand with `<scratch>/0010/adv/ent.py`. Helper shell functions are in `<scratch>/0010/adv/env.sh` and `<scratch>/0010/adv/mk.sh`.
- Refusals recorded:
  - The protected-branch guard refused `git -C $M init -q -b main` in the scratch folder: "it runs in a folder the guard cannot know … Move: write inside this session's worktree". As a result, no scratch git repository or linked worktree existed.
  - The auto-mode classifier refused `powershell -ExecutionPolicy Bypass -File ls.ps1` with "[Security Weaken]". The process listing ran through the PowerShell tool instead.
- Every process the probe started was killed at the end. A final listing found 0 processes. `git status` of the worktree is unchanged.

## Findings (most severe first)

| # | Severity | Class | Promise broken | One line |
|---|---|---|---|---|
| A-1 | medium | correctness | Acceptance "agent-stop kills only after the identity check, for an agent entry as for a process entry"; SDD §4 process entry started-at ("the operating system's creation time, at the precision the system gives … compares it exactly") | A process entry whose started-at holds the exact creation time at sub-second precision is never killed. agent-stop answers `already gone` while the process runs. |
| A-2 | medium | correctness | Acceptance "a failed copy leaves no partial file, starts no agent, and the error names the copy" (PRD AC-064) | When the settings copy cannot be made, the script reports `skipped the copy: … exists` for a file that does not exist, starts the agent, and exits 0. |
| A-3 | low | spec | Acceptance "Before the first start in a worktree the run created, agent-start copies the main checkout's `.claude/settings.local.json` into it" (PRD AC-064) | The copy runs into any `cwd`, including a folder that is no git worktree. It reads the source from the main checkout of the caller's repository, not of the `cwd`. |
| A-4 | low | robustness | SDD §3 "After exits 2, 3 and 4 no agent runs" (§7 'agent-start fails'); Acceptance exit 5 path | When the transport fails after the agent process started, agent-start answers exit 4 and stops nothing. A live, unrecorded agent and its pane remain. |
| A-5 | low | spec | Acceptance "A message along an undeclared edge … gets exit code 2 naming the edge" (SDD §3) | agent-send to a target that is no role of the pattern answers exit 4 `receiver_gone`, not exit 2 naming the edge. |

### A-1 — process entry with OS-precision started-at is never killed

Repro (run `adv-bv` open; any live throwaway process):

```sh
. <scratch>/0010/adv/env.sh; pane
P=$(afk-python <scratch>/0010/adv/spawn.py)        # python -c "import time; time.sleep(3600)", detached
C=$(powershell -NoProfile -c "(Get-CimInstance Win32_Process -Filter 'ProcessId=$P').CreationDate.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ')")
# add {"pid":P,"owner":"s1","label":"adv probe proc","started_at":C} to manifest.json "processes"
afk-python scripts/afk-team.py agent-stop '{"run":"adv-bv","pid":'$P'}'
```

| started-at written | Answer | Process after |
|---|---|---|
| `2026-10-27T21:56:00.435539Z` (6 digits) | `{"method": "already gone", "stopped": true}` | alive (pid 45488) |
| `2026-10-27T21:56:33.0134820Z` (7 digits, the Windows precision) | `{"method": "already gone", "stopped": true}` | alive (pid 31916) |
| `"1793138204.288"` and `1793138208.64` (epoch) | `already gone` | alive |
| `2026-10-27T21:56:37Z` (whole second) | `{"method": "killed the process tree", "stopped": true}` | gone |

Expected: kill when the entry's started-at equals the live creation time, which it does in rows 1 and 2. Actual: only a whole-second value matches. A wait job or job supervisor entry written as the SDD specifies is answered `already gone`. Cleanup then removes the entry and leaves the process running. Inferred: the comparison cuts the live time to the second for process entries too. Unverified: the format that the real writer of process entries (the contact agent through the manifest module) uses.

### A-2 — a failed settings copy is reported as skipped, and the agent starts

Repro:

```sh
mkdir <scratch>/0010/adv/wtfail; touch <scratch>/0010/adv/wtfail/.claude   # .claude is a file, so no copy can land
# entry g2 in state starting, run PROJ-1220 (build-verify)
afk-python scripts/afk-team.py agent-start '{"run":"PROJ-1220","agent_id":"g2","role":"builder","model":"implementation@claude","brief_path":"<scratch>/0010/adv/briefs/b1.md","cwd":"<scratch>/0010/adv/wtfail","effort":"lo"}'
```

- Actual: exit 0, `"settings": "skipped the copy: …\\wtfail\\.claude\\settings.local.json exists"`, `handle` `wf:p27`, pid 51980. The emulator log shows `agent start`.
- `ls -la wtfail` shows only the 0-byte `.claude` file, so `settings.local.json` does not exist.
- Expected: exit 4 naming the copy, no partial file, and no agent started.

### A-3 — the copy reaches folders the run did not create

Repro: give agent-start a `cwd` that is a plain folder with no git metadata (`<scratch>/0010/adv/wtfresh`).

- Actual: `"settings": "copied C:\\Users\\mvu\\PersonalProjects\\afk-driver\\.claude\\settings.local.json to …\\wtfresh\\.claude\\settings.local.json"`. The same copy landed in `wtplain` on the first start there; its md5 equals that of the afk-driver main checkout's file.
- The same call printed `could not add … to the owners of …wtfresh: git rev-parse --show-toplevel failed`, so the script knew the folder is no git worktree.
- Expected: the copy runs only into a worktree the run created, from that worktree's main checkout.
- Inferred: the source comes from the main checkout of the script's own repository. In a real run the `cwd` is the run's worktree, so the impact is low. A wrong `cwd` still writes the developer's local permission allow list into any folder.

### A-4 — exit 4 after the agent started leaves a live, unrecorded agent

Trigger: the herdr emulator answered `pane process-info` and `agent get` in a shape the transport did not parse. This was the first `agent-start` of `b1` in run `adv-bv`.

- Actual: `{"agent_id": "b1", "operation": "agent-start", "reason": "agent-start failed: AttributeError: 'str' object has no attribute 'get'", "unavailable": true}`, exit 4.
- The emulator log shows `tab create`, `pane rename`, `agent start`, `agent get`, `pane process-info`, `agent get`, and no `pane close`.
- The started process (pid 35708 and its children) stayed alive until the probe killed it. The entry kept `pid` null.
- Expected: after exit 4 no agent runs. The design's answer for "the start worked, then something failed" is the exit 5 stop.
- Not verified: whether real herdr can return such output. The fault may sit in the transport kind (`0006-transport-family-and-herdr`) and not in the entry script. The trigger was malformed tool output.

### A-5 — unknown target answers exit 4, not exit 2

Repro (run `adv-bv`, sender `ra1` role `reviewer-a`):

```sh
afk-python scripts/afk-team.py agent-send '{"run":"adv-bv","agent_id":"ra1","generation":1,"target":"ghost","kind":"message","message_id":"ra1-76","body_path":"<scratch>/0010/adv/bodies/x.txt"}'
```

- Actual: `{"reason": "target ghost names no live agent", "receiver_gone": true, "target": "ghost", "unavailable": true}`, exit 4.
- Expected: exit 2 naming the edge `reviewer-a -> ghost`. A declared role on an undeclared edge (for example `verifier -> reviewer-a`) does get exit 2.
- An exit 4 tells the sender to send again with the same id, and that retry can never succeed.

## Promises that held (171 scenarios)

| Area | Scenarios | Result |
|---|---|---|
| Payload and dispatch | 25: not JSON, array, string, null, 2 arguments, unknown verb (exit 3), unknown field, bad generation types, bad kind, unknown sender, missing or unreadable body, message id of another sender, path characters in id, unknown run, `../` in run | exit 2 with `operation` and `reason` throughout |
| Edges | 16 | sibling, undeclared and unlisted-kind sends exit 2 naming the edge; role ↔ report target both ways delivered; contact → started agent delivered; requester pair is per agent, not per role |
| Inbox and envelope | 6 | contact messages land as `inbox/<id>.json` with the 8 envelope fields; body copied to `bodies/<id>`; pane agents get `agent prompt` |
| finished and lifecycle | 13 | report target from the pattern or manifest, whatever target was written; completion signal written before delivery; contact copy with the same id; progress message sends no copy; failed pane: inbox copy plus exit 4 naming the target; failed inbox: exit 4 naming the inbox; unknown or missing body version, non-JSON body and extra field: exit 2; contact as target: one envelope, no pane |
| start-request | 51 | each missing or malformed field, unknown version (`2`, `"1"`, `true`), unknown step, role not in step, lifespan, effort and dead or unknown requester refused with exit 2 naming the check; only to contact; `solo:` accepted only for the 5 agent types and refused from a stage-mapped stage; a chain of 4 requesters accepted, per DELEGATION.md:30 ("a chain of start requests adds no level") |
| agent-start | 43 | no entry or not starting: exit 2; unknown effort: exit 2 naming the field; failed write before the call: exit 4 with no herdr call; label and name written before the call, pid and session id after it; started-at equals the OS creation time cut to the second; `#2`, `#3` and `-2`, `-3`; vendor prefix dropped (`gpt-6-sol` → `g-6-sol`); goal cut (16 in the label, room in the name); `g-` prefix; no-room names refused with exit 2 naming the name; contact tab never used; 5th pane opens a new tab; tab failure exit 4 naming the tab; blocked start exit 4 `dialog` true with pane closed; exit 5 path with all fields, process killed and pane closed; `AFK_PROVIDER` per kind; `AFK_CHARTER_FILE` and charter-first launch prompt; `solo:` agent gets no charter and a brief-only prompt; resume names the charter first; Codex resume uses `pane run`; failed resume exit 4 naming the resume |
| agent-stop | 18 | no entry: exit 0 `stopped` false; kill and close; second stop idempotent; creation-time mismatch kills nothing and answers `already gone`; no started-at: `identity unknown` and unkillable, later `already gone` and cleaned; `nothing recorded`; failed close: `pane_closed` false and unkillable; process entry gets no state write |
| agent-list | 3 | prefix is the shortest common prefix (`adv-bv`, `g-9`, `a-very-long-fea`); strays listed |
| Spawn permission check | 1 | missing rule refuses run-open before any transport verb; only detection reads (`herdr status`, `integration status`) ran first |

## Not verified

- Job supervisor start: `scripts/team/supervisor.py` is not in this branch. Every supervisor start answers exit 4 "is not installed" before the second-supervisor check, so the supervisor checks and the label could not be observed.
- Owner record append (§13 V37): no git worktree could be made (guard refusal). Every start printed `could not add … to the owners`.
- One wait job per run: neither run-open nor agent-start wrote a process entry for a wait job. The `wait` verb blocks in the foreground until a file lands. Who starts the job is not settled by this probe.
- The exit 5 stop budget (5 s before 120 s) and the 60 s agent-stop bound were not timed. An exit 5 call took 20.3 s.
- Real herdr and harness behaviour: every pane fact above is against the emulator. The JSON shapes were inferred from the transport's own errors.
- Requester spoofing: a sender may name another live agent as requester (`v1` naming `b1` was delivered). No acceptance bullet forbids it.
