# Adversary report: 0027-afk-team-launcher (HEAD 9261a89)

Verdict: `findings` — probed=143, crit=0 high=0 med=1 low=2.

Target: the command-line surface the contract names (plan decision D-40): `skills/afk/setup/scripts/python_runtime.py plan|install|check`, `scripts/team/permission.py check|rule`, the provider function `afk_claude_spawn_allow_rule` in `hooks/lib/providers/claude.sh`, and the afk-team launchers that install writes. Runs used a `git archive 9261a89` copy under the session scratch folder (`<S>` below = `C:/Users/mvu/AppData/Local/Temp/claude/C--Users-mvu-PersonalProjects-afk-driver-agent-teams/96c58aef-58cc-4e51-8bc9-2259fed7dd71/scratchpad/adv0027`). Every probe set HOME, USERPROFILE, LOCALAPPDATA, XDG_DATA_HOME and CLAUDE_CONFIG_DIR to scratch folders, removed the real afk-bin from PATH and removed every `HERDR_*` variable.

Isolation device: install's last step runs `uv tool update-shell`, which on Windows edits the user PATH in the registry (inferred from uv behavior, not checked). A scratch `uv.exe` shim forwarded every call to the real uv 0.12.23 except `tool update-shell`, which it skipped. So install's path step was not exercised. The shim also simulated the E13 sync that wipes `python/` and then fails.

Diet disclosure: no slice diff, test, review file or commit of this branch was read. Launcher file bytes were read because they are the runtime output of install. Provider function names came from `compgen -A function` after sourcing `claude.sh`. The head of `0009-spawn-permission-check-adversary.md` (another slice) was read for report format only.

## Findings (worst first)

| Id | Severity | Class | Promise it breaks |
|---|---|---|---|
| A-1 (PATH spelling refused) | medium | correctness | SDD §8 row "Spawn permission check": afk-team on PATH is the launcher in afk-bin → ok |
| A-2 (`%` breaks afk-team.cmd) | low | robustness | SDD §7 E13: each file holds one line that runs the team script of the plugin folder that ran setup; Acceptance: check reports a broken launcher |
| A-3 (BOM or broken settings read as "missing") | low | robustness | SDD §8 row "Spawn permission check": the rule is in the user's settings → refuse naming the rule only when it is absent |

### A-1 — Check 2 refuses the real afk-bin launcher when PATH spells the afk-bin folder differently

The check compares the PATH hit with the expected afk-bin path as strings. Two spellings of the same folder are refused: an 8.3 short name and a junction (a Windows folder link). Git Bash runs the same launcher through that PATH entry with no error. The refusal tells the user to run `/afk:setup`; setup rewrites the same file and cannot change the PATH spelling (inferred: setup's path step was not exercised). Case, slash direction and a trailing separator are normalized (held). Check 3 normalizes the plugin root to the long form (held, short-form root passes). Only check 2 is spelling-bound.

| PATH entry for afk-bin | Bash runs `afk-team agent-list '{"run": "adv-x"}'` | `permission.py check` |
|---|---|---|
| `<S>/sb/s 3/local/afk/python/afk-bin` | exit 3, valid JSON reply | `ok: true` |
| `C:/Users/mvu/AppData/Local/Temp/claude/C-A053~1/96C58A~1/SCRATC~1/adv0027/sb/S333A1~1/local/afk/python/afk-bin` (8.3 form of the row above) | exit 3, valid JSON reply | `ok: false, problem: launcher`, "afk-team on PATH is …S333A1~1…/afk-team, not the launcher …\sb\s 3\…\afk-team; run /afk:setup; nothing was started" |
| `<S>/junc-bin` (junction → `<S>/sb/s1/local/afk/python/afk-bin`) | not run | `ok: false, problem: launcher`, same text |

Repro (Windows, Git Bash; `L` = a scratch LOCALAPPDATA after install):
```
AB="$L/afk/python/afk-bin"
SHORT=<8.3 form of $AB>   # the probe got it from kernel32 GetShortPathNameW (p_short.py)
echo '{"permissions":{"allow":["Bash(afk-team *)"]}}' > "$CLAUDE_CONFIG_DIR/settings.json"
PATH="$SHORT;$PATH" LOCALAPPDATA="$L" afk-python "$AFK_PLUGIN_ROOT/scripts/team/permission.py" check --root "$AFK_PLUGIN_ROOT"
# expected: exit 0, "ok": true (afk-team resolves to the afk-bin launcher)
# actual:   exit 1, "ok": false, "problem": "launcher", "...not the launcher...; run /afk:setup"
```
Probe scripts: `<S>/probes/p_short.py`, `<S>/probes/p_perm.py`. Impact: a user whose PATH or LOCALAPPDATA holds a short or linked spelling (redirected profile, moved AppData) gets a refusal on every team run, and the named fix does not clear it.

### A-2 — afk-team.cmd fails when the plugin folder contains `%`; install and check report it ok

The `.cmd` line embeds the folder path raw. cmd.exe reads `%…%` as a variable, which cuts the script path and swallows the `%*` arguments. The sh launcher and the `.ps1` handle the same folder correctly (both reached the team script). The same mechanism applies to a `%` in the afk-bin path (inferred, not run).

Repro (Windows; plugin copy at `<S>/pct50%off/tree`):
```
python_runtime.py install          # AFK_PLUGIN_ROOT=<S>/pct50%off/tree → "ok afk-team.cmd"
python_runtime.py check            # → "ok afk-team.cmd"
cmd /d /c "afk-team agent-list {} & call echo exit=%^ERRORLEVEL%"
# expected: the team script runs and answers JSON (the normal-folder control answers
#           {"error": true, "operation": "agent-list", ...})
# actual:   afk-python.exe: can't open file '...\adv0027\pct50*': [Errno 22] Invalid argument
#           exit=2
```
Probe script: `<S>/probes/p_cmd.py`. Impact: low; `%` in a profile or plugin path is rare, and PowerShell and Bash do not use the `.cmd`.

### A-3 — A settings file with a UTF-8 byte order mark, or with broken JSON, reads as "rule missing"

With `\xEF\xBB\xBF{"permissions":{"allow":["Bash(afk-team *)"]}}` in `$CLAUDE_CONFIG_DIR/settings.json` (and the same in `$HOME/.claude/settings.json`), the check answers `files: []`, `problem: missing`, "the spawn rule `Bash(afk-team *)` is in no allow list of the settings files read; add it to permissions.allow in <that file>". The file already holds the rule. Broken JSON gives the same text, with no word that the file could not be parsed. The check fails closed, so nothing unsafe starts. unverified: whether Claude Code applies an allow rule from a settings file that starts with a byte order mark (no Claude session was started). Windows PowerShell 5.1 `Set-Content -Encoding UTF8` writes such a mark.

Repro:
```
printf '\xef\xbb\xbf{"permissions":{"allow":["Bash(afk-team *)"]}}' > "$CLAUDE_CONFIG_DIR/settings.json"
afk-python "$AFK_PLUGIN_ROOT/scripts/team/permission.py" check --root "$AFK_PLUGIN_ROOT"
# expected: ok, or a refusal that names the unreadable file
# actual:   "files": [], "problem": "missing", "...add it to permissions.allow in <same file>..."
```

## Promises that held

| Promise (source) | Probes | Result |
|---|---|---|
| install writes afk-team, afk-team.cmd, afk-team.ps1 into afk-bin after the sync and after afk-python (E13) | `plan` order; fresh install | held: order uv, python, environment, launcher, afk-team, path |
| Write only when bytes differ; staged then moved (E13) | repeat install; install from a second folder | held: repeat run "ok afk-team unchanged", same inode and time; rewrite gives new inodes, no staging leftovers |
| check reports missing launcher, wrong folder; `launcher` key keeps meaning afk-python (§14 Python runtime row) | 3 files removed; `.cmd`/`.ps1` removed; launcher from `tree2` | held: "launcher missing" per file; "names the plugin folder …tree2, want …tree" (prefix collision `tree`/`tree2` caught); `launcher` line still checks afk-python.exe |
| Sync wipes afk-bin then fails → both commands missing, check refuses naming /afk:setup (E13 failure row) | shim wipe + fail | held |
| Rule constant is Bash(afk-team *) | `afk_claude_spawn_allow_rule`; `permission.py rule [--json]` | held |
| Check 1: rule present / missing / old full-path rule; deny entries | 13 settings shapes | held: ok, `missing` naming the rule, `stale` for the old rule; `blocked` for a deny entry |
| Check 2: foreign afk-team earlier on PATH; launcher missing | fake script, fake `.exe`, another user's afk-bin, missing file | held: refusal naming /afk:setup |
| Check 3: launcher names another plugin folder | `tree2` launcher, `tree` running; 5 spellings of the same root | held |
| Other harnesses pass | CLAUDE* unset (2 variants) | held: `provider: unknown`, ok |
| Launchers deliver the JSON payload intact (Q56) | sh, PowerShell 5.1, pwsh 7: `{}` and `{"run": ...}`; 17 hard values × 2 PowerShell versions through afk-team.ps1 (quotes, trailing backslashes, `$()`, backtick, `--%`, newline, non-ASCII); 3 values through the sh launcher from a file | held; exit codes 2 and 3 pass through |
| Paths with spaces, `'`, `&`, `$` | plugin folder and afk-bin folder with a space; plugin folder `o'b &100% $x` | held for sh and `.ps1` (`.cmd` → A-2) |
| No agent writes the launcher during a run | afk-bin times and inodes before and after a check plus 2 launches | held: unchanged |
| `.ps1` under a blocking policy | pwsh 7 `-ExecutionPolicy Restricted`/`AllSigned` | shows "cannot be loaded because running scripts is disabled"; no fallback, as packet HL5-8 states |

## Observations (not findings)

- A read-only `afk-team.cmd` is moved aside to `afk-team.cmd.old`, and a later install leaves the `.old` file in afk-bin. No shell runs it. The human's real afk-bin shows the same pattern for `afk-python.exe.old`.
- Windows PowerShell 5.1 ran the `.ps1` under process-scope `Restricted` and `AllSigned`; likely a machine policy on this host outranks process scope (inferred, not checked).
- With the plugin folder `o'b &100% $x`, the team script started through sh and `.ps1`, then failed inside its transport adapter call (`can't open file "C:\\tmp\\claude\\…\\adapters\\transport\\subagent\\subagent.py"`, run with the real account's afk-python). The plain-space folder worked. This is past the launcher, outside this slice; owner not traced.
- An empty `run` value reads as unset in the team script (input rule of the team script, not the launcher).
- The 3 shell probes inside install and check (`powershell`, `cmd`, `git-bash`) failed in every sandbox run because the spawned shells found the real account's afk-python. This is an artifact of the sandbox, not of the slice.

## Not probed

- Joined command `afk-team … && other` checked part by part: harness behavior; needs a Claude Code session (not allowed in this run).
- Live rows in `providers/CONFORMANCE.md` (Claude pane in default and auto mode, Codex pane on Windows, setup in auto mode): need Claude Code, Codex and herdr panes. Only the anchor "afk-team launcher probes" was confirmed to exist.
- Install's path step (`uv tool update-shell`): suppressed to protect the real user PATH.
- Linux and macOS: the sh launcher ran only under Git Bash on Windows.
