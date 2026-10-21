# Adversary report: 0009-spawn-permission-check (run r3, HEAD 6be1a04)

Verdict: `findings` — probed=81, crit=0 high=0 med=1 low=3.

Target: command-line and module surface of `scripts/team/permission.py` and the provider functions in `hooks/lib/providers/claude.sh` (plan decision D-40), run from a `git archive HEAD` copy under the session scratch folder with `afk-python`. Every settings file lived under that scratch folder; HOME and USERPROFILE pointed at fake homes, except in 2 deliberate probes (finding A-1). One extra run used WSL Linux for the worktree case.

Diet disclosure: finding A-4's refusal text printed about 250 characters of the bash program the check runs. That text came from the check's own output, not from a source read. All scenarios were designed before it appeared, and no later scenario used it. The invoker decides whether this counts as a diet breach.

## Findings (worst first)

| Id | Severity | Class | Promise it breaks |
|---|---|---|---|
| A-1 (check reads HOME, harness reads USERPROFILE) | medium | correctness | SDD §8 row "Spawn permission check": confirm the harness will let the agent run every verb; refuse when it will not |
| A-2 (tool-name glob deny/ask not seen) | low | correctness | same SDD §8 row; SDD §9b row "Claude Code auto-mode classifier" |
| A-3 (equivalent `:*` rule refused as stale) | low | robustness | ADR-0005: confirm the rule the human added; SDD §8 "ok" path |
| A-4 (slow block lists end in a refusal that omits the rule) | low | robustness | SDD §9b row "Claude Code auto-mode classifier": refuse naming the rule and `/afk:setup` |

### A-1 — On Windows the check reads `$HOME/.claude/settings.json`; Claude Code reads `%USERPROFILE%\.claude\settings.json`

Primary source: Claude Code settings documentation (https://code.claude.com/docs/en/settings): "On Windows, `~/.claude` means `%USERPROFILE%\.claude`." Node `os.homedir()` (https://nodejs.org/api/os.html): "On Windows, it uses the `USERPROFILE` environment variable if defined."

Observed (Windows, Git Bash):

| Setup | Check answer | Harness behaviour per the documentation |
|---|---|---|
| Rule only in `$USERPROFILE/.claude/settings.json`, HOME elsewhere | `ok=false problem=missing`, `files=[]` | rule applies |
| Rule in `$HOME/.claude/settings.json`; `{"permissions":{"deny":["Bash"]}}` in `$USERPROFILE/.claude/settings.json` | `ok=true`, `files=[$HOME/.claude/settings.json]` | every verb denied |
| HOME unset, USERPROFILE = fake home holding the rule | `files=["C:/Users/mvu/.claude/settings.json"]` (the real account home, read only), `problem=missing` | rule applies |

Repro:
```
H=<scratch>/home U=<scratch>/up R=<scratch>/proj; mkdir -p $H/.claude $U/.claude $R
echo '{"permissions":{"allow":["Bash(afk-python \"${AFK_PLUGIN_ROOT}/scripts/afk-team.py\" *)"]}}' > $H/.claude/settings.json
echo '{"permissions":{"deny":["Bash"]}}' > $U/.claude/settings.json
cd $R; HOME=$H USERPROFILE=$U afk-python <copy>/scripts/team/permission.py check --root $R
# actual: exit 0, "ok": true   expected: exit 1, "problem": "blocked", naming $U/.claude/settings.json
```
`afk_claude_spawn_rule_files` prints the same HOME-based path, so the provider function is the source. CLAUDE_CONFIG_DIR is honoured (held). Linux reads HOME correctly (held, WSL run). Impact: a Windows user with HOME set to another folder gets a false ok (a run that the harness then stops) or a false refusal.

### A-2 — Deny and ask entries with a tool-name glob are not matched

Primary source: Claude Code permissions documentation (https://code.claude.com/docs/en/permissions, "Tool name wildcards"): "Deny and ask rules also accept glob patterns in the tool-name position. The pattern must match the full tool name: `"*"` matches every tool."

Observed: with the spawn rule in user `permissions.allow`, each of these in project `permissions.deny` or user `permissions.ask` gives `ok=true`, exit 0: `"*"`, `"B*"`, `"Bash*"`. Specifier forms such as `Bash(*)`, `Bash(* agent-send *)`, `Bash(*afk-team.py*)` and `Bash(... agent-stop:*)` are refused correctly.

Repro:
```
echo '{"permissions":{"allow":["Bash(afk-python \"${AFK_PLUGIN_ROOT}/scripts/afk-team.py\" *)"]}}' > $H/.claude/settings.json
echo '{"permissions":{"ask":["*"]}}' > $R/.claude/settings.json
cd $R; HOME=$H USERPROFILE=$H afk-python <copy>/scripts/team/permission.py check --root $R
# actual: exit 0, "ok": true   expected: exit 1, "problem": "blocked", naming the ask entry
```
Impact: such entries are rare. When present, the harness prompts or denies at the first verb after the check said ok.

### A-3 — An allow entry equal to the rule in `:*` form is refused as stale

Primary source: permissions documentation, "Wildcard patterns": "The `:*` suffix is an equivalent way to write a trailing wildcard, so `Bash(ls:*)` matches the same commands as `Bash(ls *)`."

Observed: `permissions.allow` holding `Bash(afk-python "${AFK_PLUGIN_ROOT}/scripts/afk-team.py":*)` gives `ok=false problem=stale`, "which is not the current spawn rule; replace it with …". The refusal names the rule and `/afk:setup`, so the run fails closed. Impact: a false refusal for a rule the harness honours; the human must retype it.

Repro:
```
echo '{"permissions":{"allow":["Bash(afk-python \"${AFK_PLUGIN_ROOT}/scripts/afk-team.py\":*)"]}}' > $H/.claude/settings.json
cd $R; HOME=$H USERPROFILE=$H afk-python <copy>/scripts/team/permission.py check --root $R
# actual: exit 1, "problem": "stale"   expected (per documented syntax): exit 0, "ok": true
```

### A-4 — Check time grows by about 35 ms per block entry; a long list ends in a `provider-layer` refusal that does not name the rule

Observed (Windows): 100 deny entries 4.7 s, 300 entries 11.2 s, 3000 entries 103 s then `ok=false problem=provider-layer`. The `says` text is 1217 characters. It contains `/afk:setup` but not the rule text, and it embeds the internal bash command line. 3000 allow entries take 1.1 s, so only block lists cost time.

Repro:
```
afk-python -c "import json;print(json.dumps({'permissions':{'deny':['Bash(npm run x%d *)'%i for i in range(3000)]}}))" > $R/.claude/settings.json
cd $R; HOME=$H USERPROFILE=$H afk-python <copy>/scripts/team/permission.py check --root $R
# actual: ~103 s, exit 1, "problem": "provider-layer", says omits the rule and prints the bash program
# expected: a refusal naming the rule and /afk:setup, with no internal command text
```
Impact: 3000 deny entries is not a common setup; a few hundred adds about 10 s before every run.

## Promises that held

| Area | Scenarios | Result |
|---|---|---|
| Rule in user, project or local `permissions.allow` | 3 | ok, exit 0, names the file |
| No settings files, missing root, root is a file | 3 | `missing`, exit 1, names the rule and `/afk:setup`, "nothing was started" |
| Rule in deny or ask; rule in allow plus deny or ask in another scope (`Bash`, `Bash(*)`, `Bash(afk-python:*)`, per-verb entries) | 18 | `blocked`, exit 1, names file, entry, matched verb command, rule and `/afk:setup` |
| Partial rule (start only), six per-verb rules, old path, spaces inside, trailing space, expanded path | 8 | `stale` or `missing`, exit 1 |
| Broader allow entries (`Bash`, `Bash(*)`, `Bash(afk-python:*)`) | 3 | refused; consistent with ADR-0005 "no silent pattern substitution" |
| Stale entry next to the exact rule | 1 | ok |
| Malformed files: bad JSON, empty, wrong types, top-level array, comment, duplicate key, directory | 12 | file skipped, answer from other files; consistent with the documented Settings Error skip |
| CLAUDE_CONFIG_DIR (forward and backslash paths) | 3 | that file replaces the home file |
| Paths with spaces and non-ASCII letters | 1 | read and matched |
| Worktree and git subfolder roots, Windows and WSL Linux | 5 | Windows reads the root's own files; Linux adds the main checkout's `settings.local.json`, matching the documented locations |
| AFK_PROVIDER claude, codex, unknown; AFK_PLUGIN_ROOT unset or wrong | 5 | Claude Code checked; codex and unknown answer ok with an explicit "no rule" text |
| Side effects: marker-writing entry script, file timestamps | 3 runs | nothing started, no file written |
| `rule`, `rule --json`, `verb_commands()` | 3 | rule printed; six verb commands listed |

## Not probed (unverified)

- Organization-managed settings and `allowManagedPermissionRulesOnly`: the check states it does not read them; writing a system path is outside the safe scope, so the effect is unverified.
- `--settings` session settings and headless (`claude -p`) sessions, where project allow rules wait for workspace trust: no file the check could read.
- UTF-8 byte order mark: the check skips such a file and refuses `missing`; whether Claude Code accepts it is unverified.
- The `/afk:setup` register row and rule coverage of tab create, pane split and settings copy: the setup file is outside the diet and no transport ran.
