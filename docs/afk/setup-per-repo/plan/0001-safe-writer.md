# 0001-safe-writer — shared safe writer, and this repository's verification tiers

## Goal
Move the instruction-file installer's locked writer into the scripts folder as the one safe writer every file this feature writes goes through, keep the installer's names and error type, and add `verification.tiers` (`unit`, `smoke`, `static`) to this repository's `.afk/config.yaml` so every later subtask's tier keys resolve.

## Complexity
standard

## Review
opt-in: resilience

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — rows "safe writer (moved)" and "instruction-file installer (changed)"
- SDD: SDD.md#§7 L6 — Process & Coordination — failure matrix rows for the safe writer
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "safe writer `_atomic_write_locked` from `install_block`"
- ADR: adr/design/0005-shared-safe-writer.md — one locked update, caller supplies the transform

## Scope
- scripts/safe_write.py
- skills/afk/setup/scripts/install_block.py
- scripts/tests/test_safe_write.py
- scripts/tests/test_install_block.py
- .afk/config.yaml

## Seams
- implement: safe writer `_atomic_write_locked` from `install_block` — moves to the scripts folder; the installer wraps its error (INV-010)

## Acceptance
- [ ] One call locks the file, hands the caller the file's current text, writes back the text the caller returns, and refuses with the safe writer's own error naming the file when the file changed between the read and the write (ADR-0005)
- [ ] An owner-only option leaves the written file readable and writable by its owner alone on Linux and macOS (SDD §8)
- [ ] A lock held longer than 2000 ms ends the wait with an error naming the file; the temp file is deleted and the target is unchanged (SDD §7)
- [ ] On Windows a busy file swap retries 10 times at 50 ms before failing (SDD §10)
- [ ] The written file keeps its previous file mode, and the lock file stays in place after the write (SDD §14 row "safe writer `_atomic_write_locked` from `install_block`")
- [ ] The instruction-file installer keeps every public name and its existing error type: a safe-writer error reaches its callers as the installer's own error, and the existing installer tests pass unchanged (SDD §8)
- [ ] Implements the public interface in SDD §8 row "safe writer (moved)" unmodified, standard library only (SDD §8)
- [ ] `.afk/config.yaml` declares `verification.tiers` with `unit` = `afk-python -m pytest scripts/tests -q`, `smoke` = `bash hooks/tests/hook-smoke.sh`, `static` = `bash hooks/plugin-source-gates.sh --range origin/main HEAD`, each an argument vector per `CONFIG.md` "Verification tiers", and `afk-config.py validate` accepts the file (VERIFICATION-PLAN.md header, GRILL-LOG Verification grill R-1 V-2)
- [ ] Every artifact in ## Produces exists and matches its declared contract (SDD §8)
- [ ] Every new test passes on Windows and on Linux (SDD §10)

## Produces
- scripts/safe_write.py#class SafeWriteError — the safe writer's own error type, naming the file
- scripts/safe_write.py#def update_locked( — lock, hand current text, write back returned text, refuse on change; owner-only option
- .afk/config.yaml#verification: — the `unit`, `smoke` and `static` tier keys

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier + grep each ## Produces anchor | gates pass on the branch; declared symbols present |
| unit | `unit` tier; new `scripts/tests/test_safe_write.py` (changed-file refusal, 2000 ms lock wait, swap retries with a stubbed busy replace, owner-only mode, mode kept) and `scripts/tests/test_install_block.py` unchanged | safe-writer behaviour; installer contract unchanged |
| unit | seam test in `scripts/tests/test_safe_write.py`: a second process rewrites the file between the hand-out and the write-back; assert the real file on disk keeps the second writer's bytes and the call raises `SafeWriteError` | the write-never-loses-a-write invariant at the file system |
| smoke | `smoke` tier | hooks still run end to end |

## Context excerpts
> (ADR-0005) The installer's locked writer moves to the scripts folder as the safe writer. The repository list, the markers, the settings writer and the secret step use it. One call locks the file, hands the caller its current text, writes back the returned text, and refuses when the file changed meanwhile; an option sets owner-only access. On Windows the swap retries 10 times at 50 ms; a lock waits 2000 ms; a failure names the file, deletes the temp file and changes nothing. The writer raises its own error; the installer turns it into its existing error, so its callers see what they see today. Markers are written under the list's lock, so no lock file sits in a folder under the root.

> (SDD §8 row "safe writer (moved)") locked read-modify-write | one call: lock, give current text, write back the returned text, refuse when the file changed; owner-only option; its own error type | standard library | every written file

> (SDD §8 row "instruction-file installer (changed)") unchanged role | unchanged names; turns the safe writer's error into its own existing error | safe writer

> (SDD §14 row "safe writer `_atomic_write_locked` from `install_block`") lock wait 2000 ms, change refusal, temp then replace, keeps file mode, lock file kept (INV-010, INV-015) | moved to the scripts folder with its own error type; the installer wraps it into its existing error | installer callers and tests (INV-015, INV-020) | the installer keeps its names and error type | extends (ADR-0005)

> (SDD §7 failure matrix) file swap busy on Windows | replace error | 10 retries at 50 ms | rerun setup | safe writer
> lock held past 2000 ms | lock wait ends | fail naming the file, temp deleted, nothing changed | rerun setup | safe writer
> file changed during an update | compare after re-read | refuse, nothing changed | rerun setup | safe writer

> (CONFIG.md "Verification tiers") Skills name tier KEYS, never commands. A tier is executed as an argument vector, never through a shell string, and only the documented placeholders `{module}`, `{tags}`, `{env}` are expanded.

## Parent PRD
docs/afk/setup-per-repo/PRD.md

## Parent SDD
docs/afk/setup-per-repo/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
