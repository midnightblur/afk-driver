# Adversary report — 0001-skeleton-manifests-hooks

Verdict: findings. Probed about 340 scenarios. Critical 0, high 1, medium 1, low 7.
Commit under test: b334a805. Diet: held (no source, no tests, no git history, no review files read). Not tainted.
Surface: `afk-python afkv2/scripts/plugin_check.py`, `afkv2/scripts/afkv2_config.py`, `afkv2/hooks/*.cmd` via `cmd.exe /d /c`, the manifests, `hooks.json`, 3 Claude sessions (Claude Code 2.1.314, model haiku).
Scratch trees: `C:/Users/mvu/AppData/Local/Temp/claude/C--Users-mvu-PersonalProjects-afk-driver-worktrees-afkv2-s1/cdbc7530-8eab-4f59-ba9d-f7a966f0e317/scratchpad/adv/`. Probe scripts: `.../scratchpad/tools/`. Every hook run set `LOCALAPPDATA` to a scratch folder. The real data folder was not written by these runs (its record is dated 05:02:46, before the first probe).

Authz class: not applicable. Terms: "printed text" = stdout of the hook; "core text" = the source `afkv2/core/CORE-BEHAVIORS.md`.

## Promises held (no finding)

| Promise | Evidence |
|---|---|
| Manifests name `afkv2`; plugin loads from this worktree (Acceptance 1) | live init event: `afkv2@inline`, version `2.0.0-beta.1` |
| Config reader answers one JSON object; exit 0, 1 or 2 (Acceptance 2) | about 70 inputs; stdout is always one JSON line, stderr empty; ok=0, bad value/no config=1, usage/unreadable=2; unicode and 5 MB files answer correctly |
| Reader refuses `..`, absolute, UNC, drive-relative `spec_folder` | `docs/../x`, `/etc/x`, `\\host\share`, `C:foo` all exit 1 `bad-value` |
| Reader does not use a config above the repository root | `outer/.afkv2` above `outer/repo/.git` is ignored; `.git` as a file (linked worktree) works |
| Hook prints only the prebuilt text, per provider (Acceptance 3) | claude/codex session-start: plain text, 151 B, stderr empty; claude subagent-start: JSON, `additionalContext` equals the session text byte for byte; codex subagent-start: plain text |
| Markers and sha12 (Acceptance 4) | independent SHA-256 over the text between the marker lines equals sha12 for 10 core texts (ascii, unicode, CRLF source, lone CR, tabs, no final newline). Begin and end sha12 equal |
| Fired record per provider, overwritten (Acceptance 5) | `fired-claude.txt` / `fired-codex.txt` under `<LOCALAPPDATA>\afkv2`; 40 parallel runs: no corruption, no failure |
| Hook time (Acceptance 6) | 35 interleaved runs per hook: median 39–42 ms, bare `cmd /d /c exit 0` 32 ms; every median-of-7 window 38–45 ms. An earlier pass showed windows of 48–65 ms for `subagent-start.cmd codex` under load; not reproduced when interleaved. First run after a pause: 326–361 ms (cold). Headroom is 5–10 ms |
| Hook parses no shell command | stdin with `& echo X | calc ^ %PATH% !`, 1 MB, binary, empty, closed: output unchanged. Provider argument is allow-listed: `claude&echo..`, `..\..\evil`, `%PATH%`, `^`, `*`, `"` all exit 2 with no output and no file written |
| Check builds, refuses stale, refuses 8,001 characters, refuses v1 names (Acceptance 7) | stale source, tampered text, wrong sha, tampered or malformed JSON, missing files all exit 1 with the file named; 7,999 and 8,000 pass; 8,001 fails; 28 v1-name spellings fail (env var, file name, CSS class, storage key, marker, dot-folder, UTF-16 file); `afkv2` spellings pass; `build` is idempotent |
| Check refuses prefix or substring marker use (Acceptance 8) | 30 of 34 shapes fail correctly (see A-2 for the misses) |
| Live Claude check (Acceptance 10) | session A: model quoted `afkv2-core-behaviors begin 7f976c7ee15c` and `... end 7f976c7ee15c`; record written. Session C: `/compact` ran (18.4 s, `compact_boundary` event); the record timestamp 05:18:45.47 is 21 s after the run start 05:18:24, so the hook fired after the compaction |

## Findings (most severe first)

### A-1 [high, correctness] A CRLF checkout prints text whose hash does not match the marker; the check passes

Promise: the printed text starts and ends with marker lines, sha12 is the hash of the text between them (Acceptance 4; ADR-0005; SDD §8 "marker hash"). The check must refuse a stale prebuilt file (Acceptance 7).

Cause seen: `afkv2/hooks/built/*.txt` has no `eol` rule in `.gitattributes`. `core.autocrlf=true` is the Git for Windows system default on this machine (`git config --show-origin core.autocrlf` → `file:C:/Program Files/Git/etc/gitconfig true`).

Repro (from the worktree):
```
git clone -q --no-hardlinks -c core.autocrlf=true C:/Users/mvu/PersonalProjects/afk-driver-worktrees/afkv2-s1 <dir>
git -C <dir> ls-files --eol afkv2/hooks      # built .txt: i/lf w/crlf
afk-python <dir>/afkv2/scripts/plugin_check.py check --root <dir>/afkv2     # {"ok": true}, exit 0
set LOCALAPPDATA=<tmp>
cmd.exe /d /c <dir>\afkv2\hooks\session-start.cmd claude < NUL > out.bin
```
Actual: `out.bin` holds 5 CR bytes. The begin line is `afkv2-core-behaviors begin 7f976c7ee15c\r`, so it is not a full-line match. SHA-256 over the printed text between the marker lines gives `c74814476337`, not `7f976c7ee15c`. The same holds for codex session-start and codex subagent-start. The check exits 0.
Expected: no CR in the printed text; sha12 of the printed text equals the marker; or the check exits 1.
Not affected: the Claude subagent JSON (`additionalContext` has 0 CR bytes, hash correct).
Unverified: whether a harness install clones with the user's git config (inferred), and whether setup's proof recomputes the hash from printed text.
Fix direction: pin `afkv2/hooks/built/*` to LF in `.gitattributes`, and make `check` compare bytes with no newline normalisation.

### A-2 [medium, spec] The marker rule misses wrapped calls and constants

Promise: the check fails on code that matches a marker by prefix or substring (Acceptance 8; SDD §7 "v1 defects afkv2 must not repeat" row 1).

Repro (each file added under `<root>/scripts/`, then `plugin_check.py check --root <root>`):
```
# wrapped.py                       # exit 0, expected 1
if l.startswith(
    "afkv2-core-behaviors"
):
    pass
# held.py                          # exit 0, expected 1
MARK = "afkv2-core-behaviors begin"
def f(t): return MARK in t
# pattern.py                       # exit 0, expected 1
import re
PAT = r"afkv2-core-behaviors (begin|end)"
re.search(PAT, t)
```
Also passing, expected fail: a multi-line `("afkv2-core-behaviors begin"\n in text)`, `t.__contains__("afkv2-core-behaviors")`, a name built with `"-".join(...)` or `.format(...)`. The same-line forms (34 shapes in py, sh, cmd, js, ps1) fail correctly.
Impact: a formatter that wraps a long call, or a marker held in a constant (the usual style), removes the protection. The rule is line-based.

### A-3 [low, robustness] A plugin root path with `(`, `&`, `^` or `%` runs no hook, silently

Promise: the session-start hook runs and prints the core text (Acceptance 3).
Repro (copy of `afkv2` without tests to `<dir>\pl(x)ug`; same for `pl&ug`, `pl^ug`, `pl%TEMP%ug`):
```
cmd.exe /d /c "<dir>\pl(x)ug\hooks\session-start.cmd" claude
```
Actual: exit 1, stdout empty, `'C:\...\pl' is not recognized` (for `(` and `&`); no fired record. `cmd` strips the outer quotes when the line has special characters. With the outer-wrapped form `cmd.exe /d /c ""<path>" codex"` the `(`, `&` and `^` cases print the text; the `%` case still fails.
Expected: exit 0 and the text, or a registration that survives these paths. The `hooks.json` Claude entry and the Codex `commandWindows` entry use the unwrapped form.
Unverified: how each harness builds the command line from `args` / `commandWindows`.

### A-4 [low, spec] The check accepts core text that breaks the marker contract

Promise: the printed text starts and ends with its own marker lines; markers match only as full lines (Acceptance 4, 8).
Repro:
```
# empty core text
(write an empty file to core/CORE-BEHAVIORS.md)  ->  plugin_check.py build / check: exit 0
hook prints: afkv2-core-behaviors begin e3b0c44298fc / (empty line) / afkv2-core-behaviors end e3b0c44298fc
# marker line inside the body
core/CORE-BEHAVIORS.md = "# t\nafkv2-core-behaviors end 111111111111\nafter\n"  ->  build / check: exit 0
hook prints a second end line, with another sha12, before the real end line
```
Expected: `build` and `check` exit 1 (empty rules; a marker line inside the text). A reader that scans for the first end line gets a wrong hash.

### A-5 [low, spec] The size limit counts source code points, not the printed text

Promise: the check fails at 8,001 characters or more (Acceptance 7); the Claude cut-off is 10,000 characters (SDD §9b).
Repro: core text of 8,000 ASCII characters passes; the printed text is 8,078 characters (two marker lines added). Core text `"# t\n" + "😀"*4500` passes (4,504 code points); `"😀"*5000` would pass at 5,004 code points while the printed text is above 10,000 UTF-16 units.
Expected: one stated unit for "characters" and a check on the text that is printed.
Unverified: the unit (code points, UTF-16 units, bytes) that Claude uses for its 10,000 cut-off.

### A-6 [low, correctness] The check refuses some safe code and file names

Repro:
- file `scripts/kafka-client.py`: exit 1 "file name uses a v1 name" (contains `afk` inside a word). `KAFKA_URL` inside a file passes, so the two rules disagree.
- `re.match(r"^afkv2-core-behaviors begin [0-9a-f]{12}$", l)` and `re.search(r"^...$", t, re.M)` (anchored, full-line): exit 1 "marker matched by prefix or substring".
- `if l in ("afkv2-core-behaviors begin x",):` (full-line membership): exit 1.
Expected: full-line forms pass; word-internal `afk` passes.

### A-7 [low, spec] The check does not guard the hook registration

Promise: the hook runs on startup, resume, clear and compact; subagent start has its own hook (Acceptance 3).
Repro (copy `afkv2` to a tree, edit, `plugin_check.py check --root`): each of these exits 0, expected 1:
- `SessionStart.matcher` = `startup`, or `startup|resume|clear`, or `start|resume|clear|compact`, or `.*`
- SessionStart args point at `hooks\nope.cmd`
- SubagentStart registered to `session-start.cmd`, or Claude entry given provider `codex`
- `session-start.cmd` replaced by an empty file
- `.codex-plugin/plugin.json` without `hooks`, or with `hooks` pointing at a missing file
- Claude and Codex manifests with different `version`
Impact: the live check is the only guard for these; the check is silent.

### A-8 [low, robustness] The config reader accepts and refuses the wrong values

Promise: one JSON answer; values resolved from `.afkv2` (Acceptance 2).
Repro (`.afkv2/config.json` in a scratch repo with an empty `.git` folder; `afk-python afkv2/scripts/afkv2_config.py read --start <repo>`):
- `{"spec_folder":"NUL",...}`, `"a\u0000b"`, `" docs/x "` → `ok: true` with that string as the path (expected `bad-value`).
- `ownership: {"own":["a"],"shared":["a"]}` → `ok: true` (one path in two grades); `{"own":["../../a"],"shared":["/abs"]}` → `ok: true` (globs outside the repository).
- `ownership` absent → `"ownership": null`; `{"own":[]}` → no `shared` key (two shapes for one meaning).
- a junction `docs` → outside folder: `spec_folder` `<repo>\docs\x` accepted (lexical check only).
- config file with a UTF-8 BOM (PowerShell 5 `Set-Content -Encoding UTF8` writes one) → exit 2 `unreadable: Unexpected UTF-8 BOM`. The same BOM in `plugin.json` fails the check.
- `LOCALAPPDATA` unset → whole read fails `no-data-folder`, though spec folder and tracker resolve; a relative `LOCALAPPDATA` (`rel`) answers `data_folder: rel\afkv2`.
Expected: refuse the first three groups with `bad-value`; one shape for `ownership`; accept a BOM.

### A-9 [low, robustness] Hook failure modes give no signal or a misleading one

Promise: each hook run writes the fired record; extra output or no text fails (Acceptance 3, 5).
Repro (copy `afkv2` without tests; set `LOCALAPPDATA`):
- `hooks\built\afkv2-core-behaviors.txt` empty → `session-start.cmd claude`: exit 0, stdout empty, `fired-claude.txt` written. The record says "fired" with no text delivered. An empty `.claude-subagent.json` does the same.
- built `.txt` replaced by a stale text → printed as is, exit 0 (the hook does not check; only the build check does).
- unknown, empty or upper-case provider (`gemini`, `""`, `CLAUDE`) → exit 2, no stdout, no stderr, no record.
- afkv2 data path is an existing file, read-only record file, or missing drive → exit 0, text printed, record not updated (read-only case keeps `old`). No signal.
- `subagent-start.cmd` overwrites the `session-start` record (`fired-claude.txt` then reads `claude subagent-start ...`). The time field is locale text (`Fri 10/30/2026  5:08:55.79`).
Expected: a record only when text was printed; a one-line stderr reason for the refused cases. Setup's two-part proof (record plus end marker) covers the empty case.

## Not verified

| Item | Reason |
|---|---|
| Claude subagent-start hook live (JSON wrapper accepted by the harness) | the 3-session budget is spent: session B was lost because Git Bash turned `/compact` into a path; sessions A and C ran. The JSON output was checked offline only |
| Model answer after a compaction (Acceptance 10, AC-012) | no session left to ask. Evidence is the hook timestamp after `compact_boundary`. A resume also runs the hook, so the timestamp alone cannot name the source |
| Afkv2 disabled holds no rule text (Acceptance 9, AC-011) | no session run without `--plugin-dir`; the v1 hook registration was not read |
| Marketplace v1 entry byte-identical (Acceptance 12) | needs a git comparison, outside the diet. Both entries are present in `.claude-plugin/marketplace.json` |
| Codex accepts the `.cmd` hook; Codex compaction | owner-run (`afkv2/tests/live/CODEX-LIVE-CHECKS.md`). The Codex `commandWindows` string has no `/d`, so a cmd `AutoRun` command would add lines before the begin marker; that document already lists it |

## Journal inputs

Evidence files: `.../scratchpad/adv/liveA.json`, `liveB.json`, `liveC.json` (Claude sessions); `.../scratchpad/adv/clone/` (CRLF clone); `.../scratchpad/tools/check*.py`, `hookprobe*.py`, `cfgprobe*.py` (probe scripts).
