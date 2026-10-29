# One AFK rule set per session; v2 takes over from v1

> Status: Accepted
> Audited: 2026-10-29
> Layer: Requirements
> Context ticket: GitHub #153

A session carries exactly one AFK rule set. On Claude, one of `afk` and `afkv2` is enabled per project. On Codex, one is enabled on the machine, because no per-session switch is proven. v2 takes over the user instruction files: setup removes the v1 block, but only after the session shows the afkv2 hook marker. Setup keeps a backup, and a switch-back step restores v1. v2 does not run v1 plans: a v1 feature finishes on v1 or is sliced again. Why: two rule sets in one session give conflicting instructions. An untrusted Codex hook does not run, so removing the block first could leave a session with no rules (GRILL-LOG C-1, C-4, C-5, H-2, D-2).
