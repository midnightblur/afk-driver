midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-010-settings-write-atomicity/COVERAGE.json

## Answer

No shared atomic-write or lock helper exists; each writer carries its own copy. `install_block.py` `_target_lock` + `_atomic_write_locked` (:146-224) is the only one combining OS lock (msvcrt/fcntl), compare-before-replace, `mkstemp` temp, fsync, mode keep, temp cleanup; private, imported only by tests. Inference: a new writer should reuse that shape, extracted to one shared module. Windows: `os.replace` / `Path.replace` overwrite, but raise PermissionError (WinError 5) while any process holds the target open; nothing retries. `os.rename` onto an existing file raises FileExistsError (Python docs; experiment).

| Writer | Write | Lock | Two writers / interruption | Test |
|---|---|---|---|---|
| `developer_values.py` write_block :57-86 | read-modify-write, fixed `config.yaml.tmp`, `Path.replace`, no fsync | none | lost 50-80 of 100 keys; PermissionError tracebacks (:233); temp left; drops in-block comments, CRLF on Windows; `developer:  # note` header → duplicate `developer` key, file unreadable | unguarded |
| `setup_secrets.py` ~/.claude.json :185/:243/:252 | read, prompts + 30 s Jira call, dated backup, fixed `.claude.json.afk-tmp`, `os.replace` (:105-109) | none | inferred: harness edits in the window lost; POSIX mode not kept (token file may widen from 0600) | unguarded |
| `afk-config.py` init :1153/:1168 | in-place `write_text` after existence check | none | inferred: reader sees empty/partial file; interrupt truncates; `--force` no backup | refuse/force pinned; interruption unguarded |
| `occupancy.py` claim :104-123 | per-pid temp, `os.replace` | O_EXCL `.lock`, 2 s wait → Busy (guard refuses, :342), 10 s stale takeover | other errors pass unregistered (:344); unlocked `read()` fails open (:87) | `test_occupancy.py` |
| `change_meter.py` _write/_keep :111-160 | per-pid temp, `os.replace` | none | `_take` read-then-unlink unlocked; `*.tmp` never swept | unguarded |
| `lesson-append.sh` :64-66, :98 | `>>` append | none | duplicate L-NNNN (40 rows, 20 ids); long lines tore 36-68/1000; digest merges same-id events (:164), skips bad lines (:157) | unguarded |

Other private copies: `bounded_scan.py` (kernel lock + mkstemp), `codex_marketplace_ref.py` atomic_write (fsync + mode, no lock), `python_runtime.py` write_atomically (fixed `.new`), `forge_ledger.py` _write_atomic (fixed `.tmp`), `main_sync.py`, `protected-lookup.py`, `worktree_owner.py`, `remove-worktree.py`, `lavish/inject.py`, `create-worktree` mkdir lock.

Documents refuted: `skills/afk/lessons/LEDGER-FORMAT.md:27` "multi-writer safe", `AGENTS.md:183`; `providers/PARITY.md:118-119` cites lesson coverage `hooks/tests` lacks.

## Sites

`skills/afk/setup/scripts/developer_values.py:57-86,233` · `skills/afk/setup/scripts/setup_secrets.py:105-109,185,243-252` · `scripts/afk-config.py:1148-1170` · `hooks/lib/occupancy.py:55-123` · `hooks/lib/protected_branch_guard.py:339-344` · `hooks/lib/change_meter.py:111-235` · `hooks/lesson-append.sh:64-98` · `hooks/lesson-digest.sh:157,164` · `skills/afk/setup/scripts/install_block.py:105-234` · full list in COVERAGE.json.

## Frontier

- B14: the harness and other plugin versions writing the same files; other repositories; hand edits of LEDGER.jsonl.

## Unverified

- setup_secrets concurrency not run (interactive script); same shape as write_block.
- Harness use of `CLAUDE_CONFIG_DIR` for .claude.json, and its file mode (external).
- Interrupted `>>` append joining two events: reasoned, not reproduced.
- Seed claim c-64b793f3 (hit set complete over searched forms): not load-bearing.
