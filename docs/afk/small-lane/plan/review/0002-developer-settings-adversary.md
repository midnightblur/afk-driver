# Adversary report: 0002-developer-settings

Verdict: findings, crit=0 high=1 med=5 low=5. About 465 scenarios were probed against head 2f68fbd by running `afk-config.py`, `developer_values.py` and the H6 probe block in throwaway repositories (D-3). The prober read only the contract, the `CONFIG.md` developer-settings section, the H6 section of `MANIFEST.md` and each tool's usage; it saw no source, tests, review files or diffs.

Gate outcome (D-7): the high finding F1 and the medium findings F2, F4 and F5 break promises `CONFIG.md` states, and F1 reproduces unchanged on main 82c3db8, so 0002 did not cause them. They route to slice `0013-config-contract`. F3, F6 and the low findings are advisory.

Held up: a literal `none` reads as unset for K1, K2 and K5 in every spelling and at every layer; layer order holds both ways; K3 and K4 keep `none` as a value; `status` treats a recorded `none` as answered, a blank as missing and a machine-only value as inherited; need by tracker and forge kind; the H6 probe passes and fails in every kind × layer case, skips outside a repository and fails when `developer_values.py` is missing or crashes; a linked worktree shares the repository layer; K3 derives the same value from every checkout and subdirectory; `set` refuses bad keys and a machine `worktreeBasePath`, and keeps other keys.

## Findings

| # | Severity | Class | Finding | Route |
|---|---|---|---|---|
| F1 | high | spec | A `developer:` block in the committed `.afk/config.yaml` passes `validate` and wins over the developer's machine value; `status` labels it derived and the probe prints `ok`. | 0013 |
| F2 | medium | spec | A bare clone still derives K3 from the bare repository's parent folder. | 0013 |
| F3 | medium | robustness | A wrong-shape `developer:` value makes `resolve` exit 1 with no message, and `status` crashes with a traceback. | advisory |
| F4 | medium | spec | A misspelled developer key is ignored by `resolve`, `status` and the probe; only `validate` names it. | 0013 |
| F5 | medium | correctness | An empty `developer:` in the checkout file erases the broader layers' values, and `status` lists the key as both missing and inherited. | 0013 |
| F6 | medium | robustness | `set` accepts values such as `[x]`, `&anc` or a newline that break the shared file for every worktree. | advisory |
| F7 | low | spec | With a separate git dir, K3 derives beside the git dir, not the checkout (unverified: the contract also says it reads `--git-common-dir`). | advisory |
| F8 | low | robustness | The probe prints `ok` when `status` exits non-zero with parseable JSON, and `i=` has no failure fallback (unverified: needs a malformed `status`; `i=` predates 0002). | advisory |
| F9 | low | spec | `set` drops an inline comment on a key it did not name. | advisory |
| F10 | low | robustness | `resolve developer.mrReviewer` exits 1 (unset) rather than 2 (not a developer key). | advisory |
| F11 | low | spec | The `init` scaffold comment points developers at `~/.afk/config.yaml`, not the repository file `CONFIG.md` makes the default (unverified: may be outside the slice). | advisory |

Repro scripts: the prober's session scratch (`adv-0002/s1.py` … `s6.py`, harness `h.py`, probe copy `probe.sh`).
