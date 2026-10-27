midnightblur/afk-driver@2b1929aba62ae9ebbed1292f3cd702bc92187a2f · closed-with-frontier · boundaries 13/14 · unverified 3 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-023-safe-writer-move/COVERAGE.json

## Answer

The move breaks no caller. The only production code that depends on the moved writer is `skills/afk/setup/scripts/install_block.py`, which loads `scripts/safe_write.py` by path and wraps every `SafeWriteError` as `InstallError`, so the CLI still exits 2 on a refusal. `_target_lock`, `write_if_unchanged` and `InstallError` keep their names and signatures; `_atomic_write_locked` has no code reference left, only plan and SDD text. The CLI callers (`MANIFEST.md:254`, `SKILL.md:35`, `hooks/tests/hook-smoke.sh:573-672`) see unchanged arguments, output and exit codes. The lock file `.<name>.afk.lock` is unchanged, so an older installer and the moved writer still exclude each other. `scripts/behavior_registry.py:545` still finds its three required test names.

Behaviour changes: on Windows a busy file swap is now retried 10 times at 50 ms, then refused as InstallError (exit 2) instead of a traceback (exit 1).

Inference: a later rename of `_file_lock`, `update_locked`, `SafeWriteError`, `ENCODING` or `ERRORS` breaks the installer; later slices consume `scripts/safe_write.py#def update_locked(` (plans 0003, 0008, 0009).

Stale or refuted text:
- `scripts/tests/test_install_block.py:286-287` names `_LOCK_MAX_ATTEMPTS` and `_LOCK_POLL_SECONDS`, both gone.
- `plan/DECISIONS.md` D-1 calls `developer_values.py`, `setup_secrets.py` and `set_instruction_files.py` installer callers; none references the installer.
- No `FRESHNESS.md` row names `scripts/safe_write.py`.

A missing `scripts/safe_write.py` ends the installer with a traceback (exit 1), not exit 2.

## Sites

`scripts/safe_write.py` · `skills/afk/setup/scripts/install_block.py:50,265,290` · `skills/afk/setup/MANIFEST.md:254` · `skills/afk/setup/SKILL.md:35` · `hooks/tests/hook-smoke.sh:573-672` · `scripts/behavior_registry.py:545` · `scripts/tests/test_install_block.py:286-287` · `FRESHNESS.md:69` · full list in COVERAGE.json.

## Frontier

- B14: harness and other plugin versions writing the same instruction files; other repositories.

## Unverified

- The tracer did not run the new tests on Linux or macOS, nor the smoke tier; the executor ran both separately.
- Whether the same-commit rule needs a `FRESHNESS.md` row for `scripts/safe_write.py`: not checked.
- Seed claim c-3111887c (hit set complete over searched forms): not load-bearing.
