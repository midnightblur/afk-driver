# Adversary report — 0013-config-contract

- Verdict: `findings`
- Head: 261295d. Runtime surface (D-3): `scripts/afk-config.py` (`validate`, `resolve`, `get`, `effective --json`), `skills/afk/setup/scripts/developer_values.py` (`status`, `set`), and the H6 probe block of `skills/afk/setup/MANIFEST.md`, run with Git Bash and `AFK_PYTHON` set to Python 3.14.
- Probed: 592 checks across 118 throwaway scenarios under `C:/Users/mvu/AppData/Local/Temp/adv13/`. Each scenario had its own `HOME`/`USERPROFILE`, with `AFK_CONFIG` and the harness project-folder variable unset unless the scenario set them. No network.
- Diet: I read only the contract, `CONFIG.md` (Discovery, "Developer settings (K1–K5)"), `MANIFEST.md` H6, `plan/DECISIONS.md`, and the usage text of each tool. I read no source body, test, diff or git log.
- Driver: `C:/Users/mvu/AppData/Local/Temp/claude/C--Users-mvu-PersonalProjects-afk-driver/09b46021-b22c-4c43-8660-0afec6a6c67e/scratchpad/scen.py` and `scen2.py` to `scen4.py`, with helpers in `advlib.py` and `scen_common.py`.

## Held up

| Promise | Evidence |
|---|---|
| AC-1: `validate` refuses a committed `developer:` block and names the file | It refuses with exit 2 and names the file in every case tested. Cases: no FILE, an absolute path with `/` or `\`, a relative path from a subdirectory, an upper-case path, an 8.3 short path, and an untracked repository-layer file. Block forms tested: full, empty, comment-only, blank-key, `developer: none` and `developer: ""`. |
| AC-1: `resolve`, `status` and H6 ignore the current checkout's committed block | Tested from the root, a subdirectory and a linked worktree, and through `AFK_CONFIG` spelled 7 ways: absolute `/`, absolute `\`, relative, `..`, upper-case, 8.3 and `./`. None of these reads the block. `status` lists the block in `problems`, and H6 exits 1 with an `edit by hand` line. A machine value beats a committed one. `get developer.mrReviewer` exits 1. |
| AC-2: bare clone | `resolve worktreeBasePath` exits 1 with empty stdout in each layout tested: the bare root, `refs/`, `hooks/`, a bare clone named `.git` (from inside it and from its parent), a linked worktree of `bare.git`, and a linked worktree of a bare clone named `.git`. |
| K3 derivation layouts | Main checkout, linked worktree and subdirectory derive `<main>-worktrees`. A separate git directory named `.git` derives `<parent>-worktrees`, which matches the first entry of `git worktree list`; this also holds from a subdirectory and from a linked worktree. A separate git directory not named `.git`, a linked worktree of it, a submodule, and a directory outside any repository all derive nothing. |
| AC-3: misspelled key in the machine, shared, local or `AFK_CONFIG` layer | Key forms: a typo, a case change, snake_case, a blank typo, and a typo beside a valid key. In each case `resolve` names the key and the file on stderr for 3 keys, including keys unrelated to the typo. `status` `problems` names it, H6 exits 1 with `edit by hand`, and `validate` names it. This also holds outside any repository. A quoted key is a parse error that names `file:line`. |
| AC-4: empty or blank narrower layer | Layers: local, shared and explicit. Forms: `developer:` alone, comment-only, every key blank, `""`, `''`, `"  "`, and blank with a trailing comment. In each case all 5 machine values stay in force and `validate` exits 0. An empty local block leaves the repository-layer values in force. A blank `worktreeBasePath` falls back to the machine value, or to the derived value when no machine value exists. |
| Precedence and layers | The order is explicit > local > shared > machine. `AFK_CONFIG=""` reads as unset. The main checkout's local overlay is not read in a linked worktree, and the reverse also holds. A submodule reads its own `.git/modules/<name>/afk/config.yaml` and its own local file. It reads none of the superproject's local, shared or committed layers. |
| `none` | A local `mrReviewer: none` beats a machine value. `resolve` then exits 1, and `status` does not list the key as missing. |
| `status` never lists a key as both missing and inherited | This held in every valid configuration tested. It fails for the input in F1. |

Interpretation, not a finding: a misspelled key inside a committed block is reported through the committed-block refusal, not by the key's name. Moving the block as instructed then names the key.

## Findings

| # | Severity | Class | Finding | Promise broken |
|---|---|---|---|---|
| F1 | medium | correctness | Put `developer: ""` (or `''`) in a narrower layer (local, shared or `AFK_CONFIG`). `resolve` then drops every broader developer value: it exits 1 with no stderr. `status` lists `trackerAssignee` and `mrReviewer` in both `missing` and `inherited`, with an empty `problems` list. H6 prints the same keys under both `unresolved:` and `inherited from the machine file, confirm:`. | Contract AC-4: "`status` never lists one key as both missing and inherited", and "an empty `developer:` block in a narrower layer leaves the broader layers' values in force". `CONFIG.md`: "An empty `developer:` block, or a key left blank, overrides nothing." |
| F2 | medium | robustness | Put a non-mapping scalar under `developer:` (`developer: none`) in any layer: machine, shared, local or explicit. `status` then crashes with `AttributeError: 'str' object has no attribute 'items'`, exits 1 and prints nothing on stdout. H6 prints only `unresolved: (developer_values.py status failed)`. `resolve` silently drops the broader values: it exits 1 with no stderr. `validate` says `developer: must be a mapping` and names no file. | MANIFEST H6 says the probe names each unread block "with the file that holds it". `CONFIG.md`: "a typo is named rather than silently ignored". |
| F3 | medium | spec | `AFK_CONFIG` can name a committed `.afk/config.yaml` that is not the current checkout's own. `resolve`, `status` (`source: explicit`) and H6 then take its developer values. Reproduced in 4 cases: (a) from a linked worktree, naming the main checkout's committed file; (b) from another repository; (c) from a directory outside any repository; (d) through a hard link to the current checkout's committed file. In (a), `resolve` prints the refusal for the worktree's own committed file on stderr while it returns the main checkout's value. `validate FILE` refuses those same files. | `CONFIG.md`: "`validate` refuses a `developer:` block there, and nothing reads one, even through `$AFK_CONFIG`." Contract AC-1: "`resolve`, `developer_values.py status` and the H6 probe never take a developer value from it." |
| F4 | low | robustness | A key with a mapping or list value (`mrReviewer:` followed by `nested: x`, or `- a`) in a narrower layer drops the broader string value. `resolve mrReviewer` exits 1 with no stderr. `validate` says `developer.mrReviewer: must be a string` and names no file. | `CONFIG.md` K1–K5 "Type: string". It is not named on the `resolve` path, unlike an unknown key. |
| F5 | low | robustness | The H6 block discards `status` stderr, so it hides why `status` failed. From a bare clone root, `status` refuses with `run inside a git checkout`. With a parse error in any layer, `status` exits 2 and names `file:line`. In both cases H6 prints only `(developer_values.py status failed)`. In addition, a bare clone root ignores `<bare>/afk/config.yaml`: `resolve worktreeBasePath` exits 1 at the bare root but returns the value from a linked worktree of the same bare clone. `status --repo <bare>` and `set --repo <bare>` refuse with `not a git checkout`. As a result, the only place to record the key that a bare clone "needs" is the machine file. | MANIFEST H6 Fix step 1: "Show the human each `problems` line". `CONFIG.md` K3: a bare clone "derives nothing and needs the key". |
| F6 | low | robustness | `afk-config.py` writes stderr in the Windows ANSI code page. The en dash in `(CONFIG.md "Developer settings (K1–K5)")` arrives as byte `0x96`. Git Bash and any UTF-8 reader show `K1�K5`, including the H6 `edit by hand:` line. `status` JSON escapes the dash as `\u2013` and reads correctly. With `PYTHONUTF8=1`, `afk-config.py` writes UTF-8. | Readability of the refusal that AC-1 requires. |

## Repros

Common setup: `git init r`, then commit `r/.afk/config.yaml` with this content: `schema: 1`, `tracker: github-issues`, `forge: github`, and `github-issues:` with child `repo: x/y`. The machine file `$HOME/.afk/config.yaml` contains a `developer:` block that sets all 5 keys: `trackerAssignee: m-t`, `mrReviewer: m-r`, `mrAssignee: m-a`, `ideBinary: C:/m/ide.exe` and `worktreeBasePath: C:/m/wt`. Set `HOME` and `USERPROFILE` to the same temporary directory.

- **F1**: write `r/.afk/config.local.yaml` as the single line `developer: ""`.
  - `afk-python scripts/afk-config.py resolve mrReviewer` gives `rc=1`, empty stdout, empty stderr. Expected: `m-r`, or a named error.
  - `afk-python skills/afk/setup/scripts/developer_values.py status` gives `"missing": ["trackerAssignee","mrReviewer"]`, `"inherited": ["trackerAssignee","mrReviewer","mrAssignee","worktreeBasePath"]` and `"problems": []`.
  - The same happens with the line in `<git common dir>/afk/config.yaml`, or in a file named by `AFK_CONFIG`.
- **F2**: write `r/.afk/config.local.yaml` as the single line `developer: none`.
  - `developer_values.py status` gives `rc=1`, a traceback ending `AttributeError: 'str' object has no attribute 'items'`, and empty stdout.
  - `resolve mrReviewer` gives `rc=1` with empty stderr.
  - The H6 block gives `unresolved: (developer_values.py status failed)`.
  - `validate` gives `afk-config: developer: must be a mapping`, which names no file.
  - The same happens with the line in the machine file, the shared file or an `AFK_CONFIG` file.
- **F3**: commit `a/.afk/config.yaml` with the base content plus `developer:` and `mrReviewer: a-c`. Create a second repository `b`, and a directory `plain` that is not a repository.
  - `cd b && AFK_CONFIG=<a>/.afk/config.yaml python scripts/afk-config.py resolve mrReviewer` gives `rc=0` and `a-c`. Expected: `rc=1`.
  - From `plain`, the same command gives `a-c`. From `plain`, `resolve worktreeBasePath` returns the committed `C:/a/wt`.
  - `status`, run in `b` with the same `AFK_CONFIG`, gives `{"value": "a-c", "source": "explicit"}`. H6 in `b` does not report `mrReviewer` as unresolved.
  - Linked-worktree case: `git worktree add ../lw` from `r`. Add a `developer:` block with `mrAssignee: main-c` to `r/.afk/config.yaml`. Then run `cd lw && AFK_CONFIG=<r>/.afk/config.yaml python scripts/afk-config.py resolve mrAssignee`. It gives `main-c`.
  - Hard-link case: `os.link(r/.afk/config.yaml, r/.afk/hard.yaml)`, then `AFK_CONFIG=r/.afk/hard.yaml resolve mrReviewer` returns the committed value.
- **F4**: write `r/.afk/config.local.yaml` with `developer:`, then `  mrReviewer:`, then `    nested: x`.
  - `resolve mrReviewer` gives `rc=1` with empty stderr. Expected: `m-r`, or a named error.
  - `validate` gives `developer.mrReviewer: must be a string`, which names no file.
- **F5**: `git clone --bare src bare.git`, then write `bare.git/afk/config.yaml` with `developer:` and `worktreeBasePath: C:/sh/wt`.
  - `cd bare.git && resolve worktreeBasePath` gives `rc=1`.
  - `git -C bare.git worktree add ../bwt`, then `cd bwt && resolve worktreeBasePath` gives `C:/sh/wt`.
  - H6 in `bare.git` gives `unresolved: (developer_values.py status failed)`.
  - Parse-error case: write `r/.afk/config.local.yaml` with `developer:` and `  "mrReveiwer": x`. H6 then prints `(developer_values.py status failed)`, and `status` stderr names `config.local.yaml:2`.
- **F6**: commit a `developer:` block in `r/.afk/config.yaml`, then run `afk-python scripts/afk-config.py validate` and capture stderr as bytes. The bytes contain `\x96` and do not contain `\xe2\x80\x93`.

ADVERSARY: findings — probed=592 crit=0 high=0 med=3 low=3 [report: docs/afk/small-lane/plan/review/0013-config-contract-adversary.md]
In plain terms: the settings reader keeps every promise for normal files. Three unusual hand edits still make it drop a person's settings without saying so, crash the setup check, or read names from a shared committed file. None blocks normal use, but each one breaks a promise the documentation makes.
