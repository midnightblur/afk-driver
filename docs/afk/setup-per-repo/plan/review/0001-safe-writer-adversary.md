# Adversary report — 0001-safe-writer

- Date: 2026-10-27 · branch `feat/setup-per-repo` at `e497769`
- Target: no app (`plan/DECISIONS.md` D-2). Probed at runtime: `scripts/safe_write.py` (`update_locked`, `SafeWriteError`), `skills/afk/setup/scripts/install_block.py` (CLI `install` / `teardown`; names `install`, `teardown`, `write_if_unchanged`, `InstallError`), and `.afk/config.yaml` through `scripts/afk-config.py`.
- Hosts: Windows 11 (`afk-python` 3.14.8); WSL Linux (`afk-python` 3.14.8, the two module files copied to `/tmp`). macOS: unprobed, no host.
- Concurrency: real separate `afk-python` processes (second writer, lock holder, open-file holder, killed holder, 4 counting writers).
- Scratch: `C:/t/adv/` (probe scripts in `s1/`, `s2/`, `wsl/`; results in `r1/`–`r6/`).

## Verdict

`findings` — 85 scenarios, 2 low findings. Every Acceptance promise held. Both findings are edge cases outside the 3 failure rows of SDD §7.

## Findings (most severe first)

### F-1 · correctness · low — an empty file created or deleted mid-update is not detected

- Promise broken: Acceptance 1 / ADR-0005 — "refuses ... when the file changed between the read and the write".
- Cause (observed behaviour only): a missing file and an empty file both hand the transform `""`, so the re-read compare treats them as equal.
- Repro A (Windows, also expected on Linux by the same compare): target missing; inside the transform a second process runs `open(p,'wb').close()`; the transform returns `"mine\n"`.
  - Expected: `SafeWriteError` "changed during update"; the file stays empty.
  - Actual: returns `True`; file bytes `b'mine\n'`.
- Repro B: target holds `b""`; inside the transform a second process runs `os.remove(p)`; transform returns `"mine\n"`.
  - Expected: refusal; the file stays deleted.
  - Actual: returns `True`; the file is re-created with `b'mine\n'`.
- Impact: the lost change carries no content, so no text is lost; a deletion by another writer is undone.
- Lift as a test:
  ```python
  def test_refuses_when_empty_file_appears_mid_update(tmp_path):
      p = tmp_path / "a.txt"
      def tf(t):
          subprocess.run([sys.executable, "-c", f"open({str(p)!r},'wb').close()"], check=True)
          return "mine\n"
      with pytest.raises(SafeWriteError):
          update_locked(p, tf)
      assert p.read_bytes() == b""
  ```

### F-2 · robustness · low — 2 failure paths raise a raw `PermissionError`, not `SafeWriteError`

- Promise broken: ADR-0005 — "a failure names the file ... The writer raises its own error". SDD §14 row "settings writer" says the settings writer's catch names the safe writer's own error, so a raw `OSError` escapes that catch.
- Repro A (Windows): the target path is a directory → `PermissionError: [Errno 13] Permission denied: '<dir>\a.txt'`.
- Repro B (Windows): `.a.txt.afk.lock` exists and is read-only (`chmod 0o444`) → `PermissionError: [Errno 13] Permission denied: '<dir>\.a.txt.afk.lock'`. The message names the lock file, not the target.
- Expected: `SafeWriteError` with `path` = the target.
- Contained: the installer CLI still exits 2 with a one-line message (directory case observed: `install_block: [Errno 13] Permission denied: '<target>'`), same as 1.16.0. Target unchanged, no temp file left, in both repros.
- Lift as a test:
  ```python
  def test_read_only_lock_file_refuses_with_own_error(tmp_path):
      p = tmp_path / "a.txt"; p.write_text("orig\n")
      lock = tmp_path / ".a.txt.afk.lock"; lock.write_bytes(b"\0"); os.chmod(lock, 0o444)
      with pytest.raises(SafeWriteError) as e:
          update_locked(p, lambda t: t + "x\n")
      assert e.value.path == p and p.read_text() == "orig\n"
  ```

## Promises that held

| Promise (citation) | Scenarios | Observed |
|---|---|---|
| Lock, hand current text, write back returned text (Acceptance 1, ADR-0005) | new file, existing file, relative path, missing parent folder, unchanged text | transform got `""` / current text; written bytes exact; unchanged text returns `False` and keeps mtime; a missing parent folder is created |
| Refuse a file changed mid-update, naming the file (Acceptance 1; seam row INV-010) | second process: rewrite, same-length rewrite, replace with new file, append, delete, create when missing; same on Linux | `SafeWriteError("changed during update", path)`; disk keeps the second writer's bytes; no temp file. Same-bytes rewrite is not a text change and writes through (by design) |
| No lost write among safe-writer callers (SDD §7 invariant) | 4 processes × 25 increments, Windows and Linux | final count 100 of 100 on both |
| Lock wait 2000 ms, then fail naming the file; temp deleted; target unchanged (Acceptance 3, SDD §7) | holder 3000 ms, 2300 ms, 1500 ms; Windows and Linux | 3000/2300 ms: `is locked` after 2.008–2.021 s, target = holder's bytes only, no temp; 1500 ms: waits 1.52–1.57 s then succeeds |
| Crashed holder does not block (robustness) | holder killed mid-transform; lock file with junk bytes | next call succeeds in 0.011–0.058 s |
| Windows busy swap: 10 retries at 50 ms (Acceptance 4, SDD §7/§10) | target held open 200 ms, 480 ms, 3000 ms | 1 try + 10 retries, gaps 0.051–0.052 s; 3000 ms: `file swap stayed busy` after 0.52 s, target unchanged, no temp |
| Read-only target on Windows refused at once (D-8) | `chmod 0o444` | `is read-only` in 0.008 s, target unchanged, no temp |
| Keep previous file mode (Acceptance 5) | Linux: 640, 755, 604, 444 | each mode kept; new file under umask 022 gets 644 |
| Owner-only option (Acceptance 2) | Linux: from 644, unchanged text, new file; temp files watched over 300 writes | 600 in all 3; every observed temp file was 600 |
| Lock file kept after write (Acceptance 5) | every scenario above | `.<name>.afk.lock` present after success and after every refusal |
| Transform errors | raises, returns `bytes`, returns `None` | error propagates / `TypeError`; file unchanged; next call succeeds |
| Bytes round-trip | non-UTF-8 bytes + CRLF lines, identity transform on CRLF | untouched bytes and CRLF kept; identity returns `False` |
| Symlinked target (Linux) | link → 600 file | link kept, real file written, mode 600 kept |
| Installer keeps names and error type (Acceptance 6) | runtime `dir()` + `inspect.signature` against the released 1.16.0 module | no public function or class removed; signatures equal; `InstallError` still a `ValueError`; only module imports differ |
| Installer behaviour unchanged (Acceptance 6) | 22 differential runs vs 1.16.0 (`install` and `teardown` × missing, empty, CRLF, existing, duplicate, legacy, unclosed, CRLF source, source without block, already current, non-UTF-8) | result and target bytes identical in 22 of 22 |
| Safe-writer error reaches callers as `InstallError` (Acceptance 6) | lock held 3000 ms (API, CLI); busy swap (API, CLI); read-only target (API, CLI) | API: `InstallError("target is locked/file swap stayed busy/is read-only: <path>")`, cause `SafeWriteError`; CLI: exit 2, one stderr line, no traceback. 1.16.0 raised a raw `PermissionError` for busy and read-only and left 2 temp files |
| `write_if_unchanged` | mismatch, match, missing with expected `b""` | identical to 1.16.0 |
| Standard library only (Acceptance 7) | runtime module members | imports: `contextlib`, `os`, `pathlib`, `secrets`, `stat`, `time`, `typing.Callable` |
| `verification.tiers` (Acceptance 8) | `afk-config.py validate`, `effective --json` | valid; `unit` = `afk-python -m pytest scripts/tests -q`, `smoke` = `bash hooks/tests/hook-smoke.sh`, `static` = `bash hooks/plugin-source-gates.sh --range origin/main HEAD`, each as `command` + `args` |

## Observations (no promise covers them)

- Read-only target: Windows refuses (`is read-only`); Linux writes through and keeps mode 444. The two platforms differ.
- A nested call on the same file in one process waits 2 s and fails `is locked` (no re-entry).
- `teardown` on a missing target leaves `.target.md.afk.lock` beside it; 1.16.0 did the same.
- Unprobed: macOS; the window between the re-read compare and the replace for a writer that skips the lock (no deterministic trigger).

## Information diet

- Read: the contract, SDD §7/§8/§10/§14 rows, ADR-0005, `plan/DECISIONS.md` (named by the brief for D-2), `CONFIG.md` "Verification tiers", `MANIFEST.md` H7, `--help`, module docstrings and signatures at runtime.
- Disclosed: `plan/DECISIONS.md` D-6 and D-8 name internal details (a removed constant, an `os.access` check in `_swap`). No probe depended on them.
- Loaded the released 1.16.0 installer from the plugin cache at runtime for differential runs only; its source was not read.
- Not read: the slice diff, any file under `scripts/tests/`, the source of either module, `plan/review/`, branch commits, the pull request.
